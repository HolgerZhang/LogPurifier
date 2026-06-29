# Spec 00 — 总览

## 复现对象

论文 *Cleaning Logs for Downstream Tasks (Registered Report)*（arXiv:2606.27000v1）的
**LogPurifier** 方法，**仅复现异常检测（AD）下游任务**的评估。

## 范围

| 项 | 是否复现 | 说明 |
|----|---------|------|
| LogPurifier 核心算法（依赖分数 + Mean-Shift 分割 + 清洗） | ✅ | 论文 §III，本复现核心 |
| 异常检测（AD）评估 | ✅ | 论文 §IV-C / §V，IM + OC-SVM |
| 模型推断（MI）评估 | ❌ | 本次不做 |
| LMM 统计分析（§V） | ❌ | 仅产出原始 P/R/F1，不做混合效应建模 |

## 研究问题（本复现关注 AD 部分）

- **RQ1（有效性）**：用 LogPurifier 清洗后，AD 工具的 precision/recall/F1 如何变化？
- **RQ2（效率）**：清洗后训练时间如何变化？（本复现记录耗时，作为参考。）

## 与论文的模块对应

| 论文 | 本仓库 |
|------|--------|
| §III-A 依赖分数 dScore/mScore | `src/logpurifier/dependency.py` |
| §III-B Mean-Shift 聚类分割 | `src/logpurifier/clustering.py` |
| Algorithm 1 LogPurifier | `src/logpurifier/purifier.py` |
| §IV-C Drain 解析 + 时间窗口 | `src/logpurifier/parsing.py` / `windowing.py` |
| §IV-C IM + OC-SVM（Loglizer） | `src/logpurifier/models.py`（vendored loglizer + sklearn） |
| §IV-C / §V 评估流程与指标 | `src/logpurifier/ad_eval.py` |

## 已知偏差（与论文/官方实现的差异）

1. **OC-SVM 自实现**：论文用 Loglizer 的 OC-SVM（半监督，仅用正常数据训练）。
   vendored loglizer 自带的 `SVM` 实为**监督式 `LinearSVC`**，语义不符，故本复现用
   `sklearn.svm.OneClassSVM` 实现符合论文语义的半监督 OC-SVM。IM 直接用 loglizer。
2. **分割用纯 cluster label**：直接取 Mean-Shift 分到「最低中心簇」的模板为 free-standing。
   存在边界模板误删风险（如 mScore 0.31 被删而 0.29 被留的反常情形）。
   `clustering.py` 保留 `strategy="threshold"` 接口但默认 `label`。
3. **不含 MI 与 LMM 统计**。
4. **真实数据集需自行下载**（见 `data/BGL/README.md`）；端到端测试用 BGL 200k 切片。
5. **非比特级对齐**：论文是 Registered Report，无官方代码与结果，本复现基于论文文字描述。
6. **IM 特征限维**：IM 对高维事件矩阵组合爆炸（实测全维度不限长会超时），故特征阶段用
   loglizer 原生 OOV 合并低频模板限维；IM 不另设 longest_invarant。IM 在 BGL 时间窗下
   常挖不出有效不变量（PRF 偏低），如实报告为方法局限。
7. **扩展模型**：除论文的 IM/OCSVM，另接入 loglizer 的 PCA/IsolationForest/LogClustering
   做对照与 case study（models.MODEL_REGISTRY）。

## Spec-Driven 工作方式

每个核心模块先有 spec（本目录），再有实现（`src/`）与可执行验收（`tests/`）。
算法正确性以论文 Fig.1 running example 的精确数值为黄金标准；端到端以真实 BGL 切片验证。

