# Spec 06 — 容器化与 K8s 编排

## 目标

将 LogPurifier 打包成 Docker 镜像,用 GitHub Actions 自动推送到阿里云 ACR,提供 K8s Job/CronJob 模板供集群环境复现实验。

## 镜像设计

### 基础镜像
- `python:3.11-slim`(官方 Debian-based,体积适中)。

### 工作目录与权限
- `/app` 作为工作目录。
- 非 root 用户 `logpurifier` (uid 1000) 运行,符合安全最佳实践。

### 依赖安装
- `uv` 安装依赖(速度快)。
- 只装运行时依赖(`uv sync --frozen --no-dev`),不含 pytest 等开发工具。

### 数据与产物挂载点
- `/app/data`:数据集输入(ro 只读挂载)。
- `/app/artifacts`:中间结果与最终结果输出(rw 读写挂载)。
- `/app/logs`:日志输出(rw)。

### 默认入口
- `ENTRYPOINT ["uv", "run", "python", "scripts/run_ad.py"]`,允许 K8s 通过 `args` 传参。

### 镜像命名
- `registry.cn-shanghai.aliyuncs.com/holgercloud/logexp-logpurifier:v<版本>`
- 版本号遵循语义化版本(v0.1.0 起步,Git tag 触发构建)。

## GitHub Actions CI

### 触发条件
- push tag `v*`(如 `v0.1.0`)自动触发镜像构建与推送。

### Secrets
- `ACR_USERNAME`:阿里云 ACR 用户名。
- `ACR_PASSWORD`:阿里云 ACR 密码。

存储位置:GitHub repo → Settings → Secrets and variables → Actions。

### 构建步骤
1. Checkout 代码(含 tag)。
2. 提取版本号(去掉 `v` 前缀)。
3. 登录阿里云 ACR(`docker login`)。
4. 构建镜像(打 `latest` 与 `<version>` 双标签)。
5. 推送镜像。

## K8s 编排

为所有数据集与模型组合预生成 Job 配置,部署到 `logexp` 命名空间。

### 命名空间

- **名称**: `logexp`
- **用途**: 隔离日志分析实验资源。

### Job 矩阵

共 110 个 Job:

- **行级数据集**(BGL/Thunderbird/Spirit): 5 模型 × 7 窗口(60/100/120/300/600/1800/3600s) = 35 个/数据集
- **HDFS**(session): 5 模型 × 1 = 5 个
- **命名**: `logexp-logpurifier-job-{dataset}-{model}-w{window}`(全小写)
- **run_id**: `{dataset}-{model}-w{window}`(例如 `bgl-im-w300`)
- **文件组织**: `k8s/jobs/{dataset}/{dataset}-{model}-w{window}.yaml`

### Job 生成

用 `scripts/generate_k8s_jobs.py` 生成 Job 配置,支持指定镜像 tag:

```bash
python scripts/generate_k8s_jobs.py v0.1.0    # 使用指定版本
python scripts/generate_k8s_jobs.py           # 默认 latest
```

生成的 Job YAML 统一引用指定镜像版本,避免 `latest` 的不确定性。

### Job 配置

每个 Job:
- **资源限制**:requests(2CPU/4Gi) + limits(4CPU/8Gi),防止 OOM。
- **超时**:`activeDeadlineSeconds: 86400`(24 小时),超时自动终止。
- **重启策略**:`restartPolicy: Never`, `backoffLimit: 0`(失败不重试,便于排查)。
- **Volume**:
  - `data-volume`:hostPath 挂 `/nas/LAD/Dataset` 到 `/app/data`(只读)。
  - `artifacts-volume`:hostPath 挂 `/nas/logexp-data/reproduction-logpurifier/artifacts` 到 `/app/artifacts`(读写)。
  - `logs-volume`:hostPath 挂 `/nas/logexp-data/reproduction-logpurifier/logs` 到 `/app/logs`(读写)。
- **Labels**:
  - `app: logexp-logpurifier`
  - `component: experiment`
  - `dataset: {dataset}`
  - `model: {model}`

### 数据准备

K8s 集群需预先挂载 NAS:
1. 数据集:`/nas/LAD/Dataset`,与仓库 `data/` 同构(每个数据集一个子目录,如 `BGL/BGL.log`、`HDFS/HDFS.log`+`HDFS/anomaly_label.csv`)。
2. 产物:`/nas/logexp-data/reproduction-logpurifier/artifacts`(读写)。
3. 日志:`/nas/logexp-data/reproduction-logpurifier/logs`(读写)。

## 文件清单

| 文件 | 用途 |
|------|------|
| `Dockerfile` | 镜像构建定义 |
| `.dockerignore` | 构建排除规则 |
| `.github/workflows/docker-build.yml` | CI 自动构建推送 |
| `k8s/namespace.yaml` | logexp 命名空间 |
| `k8s/jobs/{dataset}/*.yaml` | 110 个实验 Job,按数据集分文件夹 |
| `k8s/README.md` | K8s 部署指引(中文) |
| `scripts/generate_k8s_jobs.py` | Job YAML 生成脚本 |
| `DEPLOYMENT.md` | Docker/K8s 使用指南 |

## 验证

本地验证镜像:
```bash
docker build -t logpurifier:test .
docker run --rm \
  -v $(pwd)/data:/app/data:ro \
  -v $(pwd)/artifacts:/app/artifacts \
  logpurifier:test --dataset BGL --max-lines 10000 --run-id docker-test
```

K8s 验证:
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/jobs/bgl/bgl-im-w300.yaml
kubectl logs -n logexp -f job/logexp-logpurifier-job-bgl-im-w300
# 结果在 NAS: /nas/logexp-data/reproduction-logpurifier/artifacts/BGL/bgl-im-w300/
```
