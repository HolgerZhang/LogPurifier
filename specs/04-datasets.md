# Spec 04 — 数据集

## 真实数据集（BGL）

论文 §IV-C 用 BGL / Thunderbird / Spirit。本复现以 **BGL** 为主。

| 文件 | 用途 | 是否入库 |
|------|------|----------|
| `data/BGL/BGL.log` | 全量 474 万行，709MB，最终评估 | 否（.gitignore，需自备） |
| `data/BGL/BGL_200k.log` | 前 20 万行切片，端到端测试夹具 | 否（端到端测试按需从全量自动生成） |

### 获取

BGL 来自 loghub（github.com/logpai/loghub）。下载全量后：

```bash
head -200000 data/BGL/BGL.log > data/BGL/BGL_200k.log   # 生成测试切片
```

`data/BGL/README.md` 提供数据集说明与下载链接。

### 格式

每行 10 个空格分隔字段：

```
<Label> <Timestamp> <Date> <Node> <Time> <NodeRepeat> <Type> <Component> <Level> <Content>
```

- **异常判定**：`Label != "-"` 即异常行（见 `parsing.BGL_LOG_REGEX`）。
- **Timestamp**：Unix 秒，用于时间窗口切分。
- 实测：全量异常率约 1.4%；前 20 万行异常率 1.38%（首个异常在第 14737 行）。

### 切片选择说明

- **200k 切片**异常率 1.38%，接近全量，适合端到端测试。
- **全量**用于最终 case study。
- 注：过小的切片（如官方 2k 样本）异常率严重失真（测试集异常窗占比可达约 39% vs
  真实 ~1.4%），不适合产出可信指标，故本复现不采用。

## 模板数与维度

Drain3 解析后模板数随切片变化（如 50 万行→34、全量更多）。
IM 对高维事件矩阵组合爆炸，特征阶段用 loglizer 原生 OOV（`oov=True, min_count=N`）
把低频模板合并为一维以限维，详见 specs/03-ad-pipeline.md。
