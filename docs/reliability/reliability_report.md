# AgingVisBench 可靠性复核报告

**Reliability Audit Report for AgingVisBench V0.5**

> **Public snapshot:** 下述工作簿属于私有研究档案，未包含在公开仓库中；本仓库只发布由其计算得到的聚合 reliability summary。

## 1. 报告目的

本报告将项目中已有的 200 张图像人工复核文件整理为 AgingVisBench V0.5 的自动测量可靠性证据。它的作用不是替代完整人工编码，而是说明：

1. 哪些自动语义变量与人工复核结果高度一致；
2. 哪些变量可以进入 benchmark 测量层；
3. 哪些变量需要谨慎解释或继续人工复核；
4. 自动化视觉评测器在 V0.5 中的能力边界。

可靠性复核是 AgingVisBench 从“自动化测量”进入“证据校准”和“规则化裁决”的关键中间环节。

## 2. 数据来源

复核文件：

```text
RQ2_analysis_output/all_models/reliability_audit_200/manual_reliability_audit_sample_200_with_urban_rural.xlsx
```

该工作簿包含：

- `instructions`：人工复核说明；
- `audit_sample`：200 张图像的 AI 标签与人工复核标签；
- `summary`：部分变量的摘要；
- `codebook`：变量说明。

本报告基于 `audit_sample` 中可用的 AI-human 对照列重新计算一致率和 Cohen’s Kappa。

## 3. 样本设计

该复核样本包含 200 张图像，用于检查关键语义变量和城乡变量的自动标注可靠性。样本覆盖四类模型输出：

- ChatGPT / GPT；
- Midjourney；
- 即梦；
- 通义。

复核样本用于验证自动标签，而不是重新人工标注完整 6,000+ 图像数据集。因此，本报告应被理解为 V0.5 的 reliability audit，而不是完整人工编码研究。

## 4. 复核变量

本次工作簿中可计算 AI-human 一致性的变量包括：

| 变量 | 中文说明 | Benchmark 角色 |
|---|---|---|
| `agency_orientation` | 主体性取向 | A1 的过程变量 |
| `development_oriented_agency` | 发展导向行为 | A1 核心指标 |
| `scene_type` | 场景类型 | S1 核心指标 |
| `modern_object` | 科技生活符号 | A3 核心指标 |
| `traditional_cultural_marker` | 传统文化符号 | A4 核心指标 |
| `urban_rural_scene` | 城乡场景三分类 | A5 的过程变量 |
| `rural_scene` | 乡村生活符号 | A5 核心指标 |

工作簿中也包含 `space_type` 和 `has_medical_object` 的 AI/human/match 列，但当前版本中人工列未形成可计算复核结果，因此本报告将其标记为 `insufficient`，不把它们作为已经验证的 V0.5 可靠性证据。

## 5. 计算方法

对每个变量，报告以下指标：

- `n_reviewed`：AI 与 human 标签均非空的样本数；
- `agreement_rate`：AI 标签与人工标签一致比例；
- `cohen_kappa`：扣除随机一致后的 Cohen’s Kappa；
- `reliability_tier`：根据一致率和 Kappa 综合解释的可靠性等级。

可靠性等级采用以下规则：

| 等级 | 含义 |
|---|---|
| `high` | 自动标签与人工标签高度一致，可作为 V0.5 测量层证据 |
| `medium` | 自动标签总体可用，但建议抽样复核并谨慎解释 |
| `low` | 自动标签误差较多，只适合作为辅助线索 |
| `human-review-required` | 自动标签不足以独立支撑裁决 |
| `insufficient` | 当前人工复核数据不足，不能报告可靠性 |

## 6. 结果摘要

完整机器可读结果见：

```text
reports/reliability_summary.csv
```

核心结果如下：

| 变量 | n | Agreement | Cohen’s Kappa | 可靠性等级 | 解释 |
|---|---:|---:|---:|---|---|
| `agency_orientation` | 200 | 0.940 | 0.881 | high | 主体性取向作为 A1 过程变量具有较高一致性 |
| `development_oriented_agency` | 200 | 0.925 | 0.878 | high | 发展导向行为可作为核心 A 层指标进入测量层 |
| `scene_type` | 200 | 0.965 | 0.976 | high | 场景类型自动标注与人工复核高度一致 |
| `modern_object` | 200 | 0.895 | 0.789 | medium | 科技生活符号总体可用，但需要谨慎解释和抽样复核 |
| `traditional_cultural_marker` | 200 | 0.955 | 0.900 | high | 传统文化符号可靠性较高 |
| `urban_rural_scene` | 200 | 0.945 | 0.917 | high | 城乡三分类复核表现较好，可作为 A5 派生基础 |
| `rural_scene` | 200 | 0.980 | 0.952 | high | 乡村生活符号二元变量高度可靠 |
| `space_type` | 0 | — | — | insufficient | 当前复核版本缺少可计算人工标签 |
| `has_medical_object` | 0 | — | — | insufficient | 当前复核版本缺少可计算人工标签 |

## 7. 对核心指标的影响

### S1 场景类型

`scene_type` 的一致率和 Kappa 均较高，说明 VLM 场景标注在该 200 张样本中较稳定。它可以作为 AgingVisBench V0.5 的场景与社会位置核心指标。

但在裁决中仍需注意：家庭、院落或医院场景本身不等于偏见，必须结合年龄差异、效应量、现实证据和积极老龄化理论审查。

### S2 是否独处

本次可靠性表未直接报告 `is_alone`，但该指标通常由人物数量和语义规则派生。V0.5 中应将其视为可自动化测量但需要抽样复核的指标。后续如需强化该变量，应在人工复核表中加入 `human_is_alone` 和 `alone_match`。

### A1 发展导向行为

`development_oriented_agency` 的一致率为 0.925，Kappa 为 0.878，说明该变量在当前复核样本中具有较强可靠性。这对 AgingVisBench 很关键，因为它是判断老龄表征是否从发展性主体压缩为维持性主体的核心指标。

同时，`agency_orientation` 作为其上游过程变量也有较高一致性，支持将“发展导向行为”作为 V0.5 的行动层核心指标。

### A2 身体姿态收缩指数 BHI

BHI 属于自动计算的几何/姿态指标，不在该人工语义复核表中进行人类标签对照。V0.5 中应将 BHI 视为技术测量指标，需要通过检测质量、异常值处理和可视化检查进行 QA，而不是通过主观人工语义复核判断。

### A3 科技生活符号

`modern_object` 的一致率为 0.895，Kappa 为 0.789，略低于其他语义变量。它仍然可用，但应标记为 `medium` 可靠性。

解释时需要注意：小型数字设备、背景中的现代设施或模糊物体容易漏标。该指标可以进入风险矩阵，但证据置信度应结合人工复核和典型案例。

### A4 传统文化符号

`traditional_cultural_marker` 的一致率为 0.955，Kappa 为 0.900，说明该变量在当前复核样本中较可靠。

但裁决时仍需保留重要边界：传统文化符号本身不是负面，也不直接等于偏见。只有当它与去现代化、国籍刻板化或老年身份固定化结合时，才进入刻板化或偏见风险讨论。

### A5 乡村生活符号

`urban_rural_scene` 三分类一致率为 0.945，Kappa 为 0.917；派生出的 `rural_scene` 一致率为 0.980，Kappa 为 0.952。这说明在“可见线索”规则下，乡村生活符号具有较高复核可靠性。

该变量适合进入 V0.5 的行动层/符号层风险矩阵，但解释时不能直接等同于现实城乡人口结构。特别是 `unknown_or_mixed` 应保留为不确定类别，而不是强制二分。

### R 层变量

背景亮度、背景饱和度、背景信息熵、视觉中心距离和人物占图像比主要来自传统 CV 或几何计算，不在本人工语义复核表中计算 Kappa。它们应通过技术 QA、异常值检查和可视化检查进行可靠性说明。

V0.5 中，R 层变量主要作为视觉共鸣和构图证据，不建议单独承担强偏见裁决。

## 8. 自动评测能力边界

本次可靠性复核支持以下结论：

1. **发展导向行为可作为核心自动语义指标使用**，但仍需要在风险裁决中保留人工复核证据。
2. **场景类型和乡村生活符号可靠性较高**，适合进入 V0.5 风险矩阵。
3. **科技生活符号可靠性中等偏高**，可用但需要谨慎解释。
4. **传统文化符号可靠性较高**，但概念上不能直接被解释为负面。
5. **城乡三分类规则有效保留了不确定性**，`unknown_or_mixed` 不应被视为错误或缺失。
6. **space type 和 medical object 在当前完成版复核表中没有足够人工标签**，不应作为已验证变量来报告。
7. **BHI 和 R 层变量不依赖语义人工复核**，需要另行通过技术 QA 说明其可靠性。

## 9. V0.5 可靠性结论

AgingVisBench V0.5 已经具备一组经过 200 张人工样本复核的关键语义指标，能够支撑以下核心分析：

- 老年图像中的发展导向行为是否减少；
- 场景类型是否发生年龄差异；
- 科技生活符号是否减少；
- 传统文化符号是否增加；
- 乡村生活符号是否增加；
- 城乡三分类是否可用于派生乡村生活符号。

这些复核结果使 AgingVisBench 不只是纯自动化审计，而是具备 human-in-the-loop reliability evidence 的 V0.5 benchmark。

## 10. 后续改进

V1.0 可进一步增强：

1. 增加第二名人工复核者，计算 inter-coder agreement；
2. 为 `is_alone` 增加专门人工复核列；
3. 为 `has_medical_object` 和 `space_type` 补齐人工复核结果；
4. 对 BHI 和 R 层指标建立独立技术 QA 报告；
5. 对 mismatch cases 进行分类，记录 VLM 容易出错的视觉场景；
6. 将 reliability tier 自动接入风险矩阵中的 evidence confidence。
