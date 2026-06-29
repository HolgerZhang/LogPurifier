# Spec 02 — Mean-Shift 聚类分割（clustering.py）

对照论文 §III-B。

## 目标

输入每个模板的 `mScore`，输出 free-standing 模板集合 `Tfs`。

## 算法

1. 把所有模板的 mScore 排成一维数组。
2. 用 `sklearn.cluster.MeanShift` 聚类（不预设簇数；regular 模板可能形成多个分数层级，
   固定二分类阈值受系统规模/结构影响，故用 Mean-Shift 自动成簇）。
   - bandwidth：用 `sklearn.cluster.estimate_bandwidth` 自动估计；估计为 0 或失败时回退
     到一个小正数（基于数据极差），保证可运行。
3. **选择中心最小的簇**作为 free-standing 模板簇（这些模板与其它模板依赖最弱）。

## 策略开关

- `strategy="label"`（默认，忠实论文）：返回被分配到「最低中心簇」label 的模板集合。
- `strategy="threshold"`（可选）：以「最低簇上界与次低簇下界的中点」为阈值，删除 mScore
  低于阈值的模板。用于规避边界误删风险（如 0.31 被删而 0.29 被留的反常）。
  **默认不启用**，仅作为对比/研究接口保留。

## 退化情形

- 模板数 ≤ 1：无可分割，返回空 `Tfs`（不删除任何模板）。
- 只聚出 1 个簇：说明所有模板依赖分数相近，无明显 free-standing，返回空 `Tfs`。

## API

```python
def segment_free_standing(
    m_scores: dict[int, float], strategy: str = "label"
) -> set[int]
```

## 验收（tests/test_clustering.py）

1. running example mScore `{send:0.875, check:0.875, memory:0.75}`：memory 落在最低簇
   （小样本三点 bandwidth 可能同簇 → 该用例允许"无分割"，分簇逻辑由用例 2 兜底）。
2. 分散合成 mScore（一组高 ~0.9、一组低 ~0.1）：低组被完整识别为 `Tfs`，高组不在其中。
3. 单模板 / 全相同分数：返回空集合。
