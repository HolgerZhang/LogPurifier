# Kubernetes 部署指南

在 Kubernetes 集群上运行 LogPurifier 实验。所有资源部署在 `logexp` 命名空间下。

## 前置条件

- Kubernetes 集群(1.20+)
- `kubectl` 已配置访问集群
- 集群内各节点 NAS 挂载点可用:
  - `/nas/LAD/Dataset`:数据集目录,与仓库 `data/` 同构(每个数据集一个子目录,如 `BGL/BGL.log`、`HDFS/HDFS.log`+`HDFS/anomaly_label.csv`)
  - `/nas/logexp-data/reproduction-logpurifier/`:结果输出目录

## 生成 Job 配置

**首次使用或镜像版本更新时**,需重新生成 Job 配置:

```bash
# 使用指定镜像版本(推荐)
python scripts/generate_k8s_jobs.py v0.1.0

# 或使用 latest(默认)
python scripts/generate_k8s_jobs.py
```

这会生成 110 个 Job YAML 文件到 `k8s/jobs/{dataset}/` 目录,所有 Job 使用统一的镜像版本。

## 快速开始

### 1. 创建命名空间

```bash
kubectl apply -f namespace.yaml
```

### 2. 提交实验 Job

**单个 Job**:
```bash
kubectl apply -f jobs/bgl/bgl-im-w300.yaml
```

**批量提交**(所有 110 个 Job):
```bash
kubectl apply -f jobs/ -R
```

**按数据集提交**:
```bash
kubectl apply -f jobs/bgl/              # 所有 BGL 实验(35 个)
kubectl apply -f jobs/thunderbird/
```

**按窗口大小提交**:
```bash
kubectl apply -f jobs/bgl/*-w300.yaml   # BGL 300s 窗口的所有模型
kubectl apply -f jobs/*/*/*-w300.yaml   # 所有数据集 300s 窗口
```

**按模型提交**:
```bash
kubectl apply -f jobs/bgl/*-ocsvm-*.yaml        # BGL 所有窗口的 OCSVM
kubectl apply -f jobs/*/*/*-ocsvm-*.yaml        # 所有数据集所有窗口的 OCSVM
```

### 3. 查看状态

```bash
# 所有 Job
kubectl get jobs -n logexp

# 按数据集查看
kubectl get jobs -n logexp -l dataset=bgl

# 按模型查看
kubectl get jobs -n logexp -l model=ocsvm

# Pod 状态
kubectl get pods -n logexp -l app=logexp-logpurifier

# 实时日志(示例)
kubectl logs -n logexp -f job/logexp-logpurifier-job-bgl-im-w300
```

### 4. 查看结果

结果直接写入 NAS,无需从 Pod 复制:

```bash
ls /nas/logexp-data/reproduction-logpurifier/artifacts/
```

每个 Job 产物在 `artifacts/<dataset>/<run_id>/` 下,例如:
- `artifacts/BGL/bgl-im-w300/results_w300_s42_label.csv`
- `artifacts/Thunderbird/thunderbird-ocsvm-w600/results_w600_s42_label.csv`

日志在 `/nas/logexp-data/reproduction-logpurifier/logs/`。

## Job 矩阵

共 110 个 Job:
- **行级数据集**(BGL/Thunderbird/Spirit): 5 模型 × 7 窗口 = 35 个/数据集
- **HDFS**(session): 5 模型 × 1 = 5 个

| 数据集 | 窗口(秒) | 模型 | Job 数量 |
|--------|---------|------|----------|
| BGL | 60, 100, 120, 300, 600, 1800, 3600 | IM/OCSVM/PCA/IForest/LogCluster | 35 |
| Thunderbird | 60, 100, 120, 300, 600, 1800, 3600 | IM/OCSVM/PCA/IForest/LogCluster | 35 |
| Spirit | 60, 100, 120, 300, 600, 1800, 3600 | IM/OCSVM/PCA/IForest/LogCluster | 35 |
| HDFS | 0(session) | IM/OCSVM/PCA/IForest/LogCluster | 5 |

**Job 命名**: `logexp-logpurifier-job-{dataset}-{model}-w{window}`
**run_id**: `{dataset}-{model}-w{window}`

每个 Job:
- **超时**: 24 小时(`activeDeadlineSeconds: 86400`)
- **资源**: 2 CPU / 4Gi 内存(requests), 4 CPU / 8Gi(limits)
- **重启策略**: 失败不重试(`backoffLimit: 0`)

## 清理

**删除单个 Job**:
```bash
kubectl delete job -n logexp logexp-logpurifier-job-bgl-im-w300
```

**按标签批量删除**:
```bash
# 删除所有 BGL 实验
kubectl delete job -n logexp -l dataset=bgl

# 删除所有 OCSVM 实验
kubectl delete job -n logexp -l model=ocsvm

# 删除所有 300s 窗口实验
kubectl delete job -n logexp -l window=w300

# 删除所有 Job
kubectl delete job -n logexp -l app=logexp-logpurifier
```

**删除命名空间**(会删除所有资源, 但保留 NAS 数据):
```bash
kubectl delete namespace logexp
```

## 失败重跑

相同 `--run-id` 的 Job 会复用已完成阶段的缓存。重跑步骤:

```bash
# 删除失败的 Job
kubectl delete job -n logexp logexp-logpurifier-job-bgl-im-w300

# 重新提交(run_id 不变,自动复用缓存)
kubectl apply -f jobs/bgl/bgl-im-w300.yaml
```

## 监控

查看整体进度:

```bash
# 统计完成数
kubectl get jobs -n logexp -o json | jq '[.items[] | select(.status.succeeded==1)] | length'

# 查看运行时间最长的 Job
kubectl get jobs -n logexp --sort-by=.status.startTime
```
