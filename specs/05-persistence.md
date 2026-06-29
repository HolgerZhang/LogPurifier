# Spec 05 — 分阶段落盘缓存（pipeline.py）

复现流程在 K8s 上运行，需保存关键中间结果，支持复用与断点续跑。

## 阶段与产物

| 阶段 | 输入 | 产物文件（artifacts/<run>/） | 复用价值 |
|------|------|------------------------------|----------|
| parse | BGL.log, max_lines | `parsed_{max_lines}.parquet`（timestamp/template_id/is_anomaly） | 改窗口不必重解析（解析最重） |
| window | parsed, window_seconds | `windows_w{W}.npz`（sequences, labels） | 改划分/模型不必重分窗 |
| split | windows, ratio, seed | `split_w{W}_s{seed}.npz`（train/test/labels） | 固定划分，模型间共享 |
| purify | train_seqs, strategy | `tfs_w{W}_s{seed}_{strategy}.json`（Tfs） | 清洗结果复用 |
| evaluate | split, tfs, 模型参数 | `results_w{W}_s{seed}_{strategy}.csv`（P/R/F1/train_s） | 最终指标 |

## 缓存键与命中

- 每个产物文件名编码其依赖参数（max_lines/window/seed/strategy 等）；参数不同即不同文件，
  天然避免误复用。
- 运行前先查产物是否存在：存在则直接加载（除非 `--force` 重算）。
- `run` 子目录默认按数据集命名（如 `artifacts/BGL/`）；另写 `meta.json` 记录本次
  max_lines/window/seed，便于人工查看。

## 格式

- 表格/结构化（parsed）：parquet（pandas）。
- 数组（sequences/labels/矩阵）：npz（numpy），变长序列存为 object 数组或 ragged 编码。
- 集合/标量（Tfs/meta）：json。

## 接口

```python
run_pipeline(bgl_path, dataset, window, max_lines, strategy, seed, train_ratio,
             models, oov_min_count, model_kwargs, artifacts_dir, force=False)
  -> (results, tfs)   # 各阶段自动缓存
```

## 验收

- 连续两次运行：第二次解析/分窗阶段命中缓存、秒级跳过。
- 删除某阶段产物后重跑：仅该阶段及其下游重算。
