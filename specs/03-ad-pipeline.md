# Spec 03 — AD 评估流程（parsing / windowing / ad_eval）

对照论文 §IV-C（Anomaly Detection 实验设置）。

## 3.1 解析（parsing.py）

- 用 **Drain3**（`drain3==0.9.11`）在线提取模板，每行日志得到一个 TemplateId
  （`TemplateMiner.add_log_message(content)["cluster_id"]`）。
- 数据集相关的行格式由正则定义，借鉴 event-purger：
  - **BGL**：`^(?P<Label>...) (?P<Timestamp>...) (?P<Date>...) (?P<Node>...) (?P<Time>...) ...(?P<Content>.*)$`，
    异常判定：行首 `Label != "-"` 即异常行；Timestamp 为 Unix 秒。
- 解析产物：`list[ParsedEntry(timestamp: float, template_id: int, is_anomaly: bool)]`。
- 另提供 `parse_structured`，从内存中 (timestamp, template_id, is_anomaly) 元组构造
  ParsedEntry，供测试使用。

## 3.2 时间窗口切分（windowing.py）

- **固定时间窗口**：按 `window_seconds` 把按时间排序的 entry 切成不重叠的连续窗口。
  支持 7 档：60/100/120/300/600/1800/3600 秒（论文设定）。
- 每个窗口 → 一个事件序列 `list[int]`（窗口内 entry 的 TemplateId，保持时间顺序）。
- 窗口标签：窗口内**任一** entry 为 anomaly → 该序列标 1（异常），否则 0（正常）。
  （AD 常规做法：异常事件落入的时间窗即异常窗。）
- 输出：`(sequences: list[list[int]], labels: list[int])`。

## 3.3 训练/测试划分（ad_eval.py）

- 从 normal 序列（label==0）采样 **80%** 作训练集；
  测试集 = 剩余 20% normal + **全部** anomalous 序列（label==1）。
- 采样可固定随机种子，保证可复现。

## 3.4 清洗施加方式（论文关键点）

- 在**训练集序列**上跑 LogPurifier（`identify_free_standing`）识别 `Tfs`；
- 从**训练集与测试集同时**删除 `Tfs` 的模板消息，得到清洗版（L_cl）；
- 同时保留未清洗版（L_org）作对照。

## 3.5 特征与模型（models.py）

- 特征：vendored loglizer `FeatureExtractor`，**开启 OOV**（`oov=True, min_count=N`）把
  低频模板合并为一维以限维（IM 对高维事件矩阵组合爆炸，实测全维度不限长会超时）。
- **IM**：loglizer `InvariantsMiner`（无监督，**不限长**；维度由 OOV 控制）。
- **OC-SVM**：`sklearn.svm.OneClassSVM`（半监督，只 fit 训练集正常矩阵；
  predict +1=正常/-1=异常 → 0/1）。不用 loglizer 自带 SVM（监督式 LinearSVC，语义不符）。
- **扩展模型**（models.MODEL_REGISTRY，用于 case study）：PCA / IsolationForest /
  LogClustering，均为 loglizer 自带无监督/半监督模型，统一 `fit(X)/predict→0/1` 接口。

## 3.6 指标

- precision / recall / F1（sklearn binary，`zero_division=0`）。
- 对每个模型 × 每个窗口，分别报告 org 与 cleaned，并记录训练耗时（RQ2 参考）。

## 验收

- `test_windowing.py`：固定窗口切分边界、标签传播正确。
- `test_models.py`：每个注册模型 fit/predict→0/1。
- `test_end_to_end_bgl.py`：真实 BGL 200k 切片端到端跑通，指标合法、缓存命中。

