# Spec 02 — Mean-Shift 聚类分割（clustering.py）

对照论文 §III-B。

## 目标

输入每个模板的 `mScore`，输出 free-standing 模板集合 `Tfs`。

## 算法（忠实论文 §III-B）

论文原文只规定两点：(a) 用 **Mean-Shift** 对一维 `mScore` 聚类（不预设簇数，因为
regular 模板常形成多个分数层级）；(b) 取 **mScore 最小的簇**作为 free-standing 模板集合。
本实现只做这一件事，不引入论文之外的分割策略。

1. 把所有模板的 `mScore` 排成一维数组。
2. 用 `sklearn.cluster.MeanShift` 聚类（不预设簇数）。
3. **选择中心最小的簇**作为 free-standing 模板簇（这些模板与其它模板依赖最弱）。
   - 一维、非交叠的 Mean-Shift 簇里，「中心最小的簇」即「包含全局最小 `mScore` 的簇」，
     与论文「smallest mScore 的簇」等价。

## 带宽选择（论文留白，此处做有据补全）

论文只写「用 Mean-Shift [28]」，**未规定带宽**，把带宽完全交给引用。Mean-Shift 的带宽本质
就是核密度估计（KDE）的核宽（Comaniciu & Meer 2002），因此在论文沉默处采用 KDE 的标准
带宽选择，而非任意常数：

1. 主用 `sklearn.cluster.estimate_bandwidth`（sklearn 为 Mean-Shift 配套的默认估计器）。
2. **回退（当估计 ≤ 0）**：改用 **Silverman 经验法则**（Silverman 1986）
   `h = 0.9 · min(std, IQR/1.34) · n^(-1/5)`。
   - 触发原因：`estimate_bandwidth` 基于「近邻距离分位数」，当大量 `mScore` 取值相同
     （打结）时会退化为 0；而 `MeanShift(bandwidth=0)` 直接抛 `InvalidParameterError`。
     这是**带宽估计器**在打结数据上的退化，**不是** Mean-Shift 本身无法区分——只要给出
     正带宽，即便多数点取值相同，可分的层级仍能被正确分开（见验收用例 4）。
   - `min(std, IQR/1.34)` 对离群天然稳健；`mScore ∈ [0,1]` 有界，此回退恒为正
     （进入此步时已保证至少两个不同取值，故 std > 0）。

> 说明：`span/3`（极差三分之一）这类拍脑袋常数已弃用——它没有任何理论推导，仅在「两组
> 均衡数据」下恰好近似 Silverman，不作为依据。

## 退化情形

- 模板数 ≤ 1：无可分割，返回空 `Tfs`（不删除任何模板）。
- 所有 `mScore` 完全相同（极差为 0）：无可分性，返回空 `Tfs`。
- 只聚出 1 个簇：说明所有模板依赖分数相近，无明显 free-standing，返回空 `Tfs`。

## 方法固有极限（如实标注）

当 free-standing 与 regular 的 `mScore` 本身**没有间隙**（真的挤在同一值附近）时，任何一维
聚类都无法区分。这是 mScore-聚类这套 heuristic 的固有极限，论文亦仅称其为启发式，与带宽
选择无关。

## API

```python
def segment_free_standing(m_scores: dict[int, float]) -> set[int]
```

## 验收（tests/test_clustering.py）

1. running example `mScore` `{send:0.875, check:0.875, memory:0.75}`：memory 落在最低簇
   （小样本三点带宽可能同簇 → 该用例允许「无分割」，分簇逻辑由用例 2 兜底）；无论如何
   send/check 不得被删。
2. 分散合成 `mScore`（一组高 ~0.9、一组低 ~0.1）：低组被完整识别为 `Tfs`，高组不在其中。
3. 单模板 / 全相同分数 / 空输入：返回空集合。
4. 打结但可分（如 `{0.5, 0.5, 0.5, 0.5, 0.875, 0.875}`，`estimate_bandwidth` 会给 0）：
   Silverman 回退使 Mean-Shift 仍分出两层，低层（0.5 组）被识别为 `Tfs`。
