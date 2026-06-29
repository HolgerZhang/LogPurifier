# Spec 01 — 依赖分数计算（dependency.py）

对照论文 §III-A。

## 数据表示

- 一条日志 `l` = 模板 id 的有序序列（list[int]），按时间戳排序后得到。
- 日志集合 `L` = list[list[int]]。
- `rev(L)` = 把 `L` 中每条 `l` 各自反转。

## 定义

### distance(ex, ey, l)
两条 entry 在同一条 `l` 中的索引差（绝对值）。相邻 = 1。

### first-following log entry
给定模板 `x` 的一次出现 `ex`（位于索引 i），`y` 的 first-following entry 是：
在区间 `(i, j)` 内 `y` 的第一次出现，其中 `j` 是 `x` 的**下一次出现**索引
（若 x 此后不再出现，则区间到 `l` 末尾）。若区间内无 `y`，则不存在 first-following。

### cScore(ex, ey, l)
- 存在 first-following `ey` → `1 / distance(ex, ey, l)`。
- 不存在（"Not an Entry", NaE）→ `0`。

### dScore_f(x, y, L) — forward dependency score
```
dScore_f(x, y, L) = ( Σ_{l∈L} Σ_{ex∈Ex,l} cScore(ex, ey, l) ) / n
```
其中 `n` = `x` 在整个 `L` 中的出现总次数（论文："n is the total number of log entries of x in L"）。
`Ex,l` = `x` 在 `l` 中的所有出现。

### dScore_b(x, y, L) — backward dependency score
`dScore_b(x, y, L) = dScore_f(x, y, rev(L))`。

### dScoreCalc(x, y, L)
`max(dScore_f(x, y, L), dScore_b(x, y, L))`。

### mScore[x]
`max over y ∈ T\{x}` of `dScoreCalc(x, y, L)`。
（取最大而非平均：regular 模板只要与某一个模板强相关就不应被判为 free-standing。）

## API

```python
def m_score(logs: list[list[int]], templates: Iterable[int]) -> dict[int, float]
def d_score_calc(x, y, logs) -> float          # max(forward, backward)
def d_score_forward(x, y, logs) -> float
def d_score_backward(x, y, logs) -> float
```

## 验收（论文 Fig.1 running example 黄金数值）

running example：`l_eg = [send, check, memory, send, check, send, check, send, memory, check]`
（11 条，但论文 e10 与 e9 时间戳相同；按论文给定序列，模板集合 T = {send, check, memory}）。

- `d_score_forward(memory, send, L) == 0.5`
- `m_score[memory] == 0.75`
- `m_score[send] == 0.875`
- `m_score[check] == 0.875`

精确浮点相等（容差 1e-9）。
