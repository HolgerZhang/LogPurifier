# Spec 04 — 数据集

论文 §IV-C 用 BGL / Thunderbird / Spirit；本复现接入这三个，并额外加 HDFS v1。
数据集分两类，统一产出 `(sequences: list[list[int]], labels: list[int])` 供下游复用。

## 两类数据集

| 类型 | 数据集 | 标签来源 | 切分方式 |
|------|--------|----------|----------|
| 行级标签 + 时间窗口 | BGL / Thunderbird / Spirit | 行首 `Label`（`-`=正常，其余=告警） | 固定时间窗口（7 档秒数） |
| session 标签 | HDFS v1 | 单独 `anomaly_label.csv`（BlockId→Normal/Anomaly） | 按 block_id 分组成 session |

抽象（`datasets.py`）：
- 行级类用 `LineDatasetSpec`（name + regex），共用 `parse_lines + fixed_time_windows`。
- HDFS 独立 `load_hdfs_sessions`（block_id 分组 + label 文件），**无时间窗口概念**，window 参数对其无效。
- `is_session_dataset(name)` 判别走哪条路径。

## 行级数据集格式

均：行首 `Label`（`-`=正常），紧跟 Unix 秒 `Timestamp`，尾部为消息 `Content`。
解析只需稳健捕获 **Label / Timestamp / Content** 三个关键字段（中间元数据列不参与模板）。

- **BGL**（10 字段，`BGL_REGEX`）：
  `<Label> <Timestamp> <Date> <Node> <Time> <NodeRepeat> <Type> <Component> <Level> <Content>`
- **Thunderbird / Spirit**（同格式，`TB_SPIRIT_REGEX`）：
  `<Label> <Timestamp> <Date> <User> <Month> <Day> <Time> <Location> <Content>`

异常判定统一：`Label != "-"` 即异常行；Timestamp 为 Unix 秒，用于时间窗口切分。

## HDFS v1 格式

- 行格式：`<Date> <Time> <Pid> <Level> <Component>: <Content>`，Drain3 提模板得 template_id。
- 序列：从每行 Content 用 `blk_-?\d+` 提取 block_id，按 block_id 分组（一行可属多个 block），
  每个 block 一个 template_id 序列（保持出现顺序）。
- 标签：`anomaly_label.csv`（列 `BlockId,Label`），`Label=="Anomaly"` → 1，否则 0。
- 借鉴 loglizer `dataloader.load_HDFS` 的 block_id 分组与 label 映射逻辑。

## 文件与获取

| 文件 | 用途 | 是否入库 |
|------|------|----------|
| `data/BGL/BGL.log` | 全量 474 万行，709MB | 否（.gitignore，需自备） |
| `data/BGL/BGL_200k.log` | 端到端测试夹具 | 否（测试按需从全量自动生成） |
| `data/Thunderbird/Thunderbird.log` | 全量 | 否，需自备 |
| `data/Spirit/spirit2` | 全量 | 否，需自备 |
| `data/HDFS/HDFS.log` + `data/HDFS/anomaly_label.csv` | 日志 + block 标签 | 否，需自备 |

`data/<name>/README.md` 提供各数据集下载指引（BGL/Thunderbird/HDFS 来自 loghub，Spirit 来自 USENIX CFDR）。

## 数据规模说明

- 行级数据集体量大（Thunderbird/Spirit 全量很大），用 `--max-lines` 限制解析行数。
- 过小切片异常率失真（如 BGL 官方 2k 样本测试集异常窗占比约 39% vs 真实 ~1.4%），不用于产出可信指标。
- Drain3 解析后模板数随数据量变化；IM 对高维事件矩阵组合爆炸，特征阶段用 loglizer 原生 OOV
  （`oov=True, min_count=N`）限维，详见 specs/03-ad-pipeline.md。
