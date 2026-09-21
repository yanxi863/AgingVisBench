# AgingVisBench 基准卡

> **Public release note:** 本文件描述 V0.5 历史研究快照。原始图像和行级数据未公开，精确托管模型版本记录不完整；结果不代表当前服务版本，也不能由 synthetic 示例复现。

**AgingVisBench: A Multi-Evidence Calibrated Benchmark for Auditing Aging-Related Visual Bias in Text-to-Image Models**

## 1. 基准定位 / Benchmark Positioning

AgingVisBench 是一个面向文生图模型的老龄化视觉表征评测基准。它关注模型在生成老年人图像时，是否稳定呈现特定的视觉差异，以及这些差异是否可能构成刻板化风险或偏见风险。

本基准采用混合评测方式：

```text
自动化视觉测量
  + 人工可靠性复核
  + 现实证据校准
  + 积极老龄化理论审查
  + 规则化裁决
```

AgingVisBench 的目标不是直接宣称某个模型“有偏见”或“无偏见”，而是在多重证据基础上区分：

- 稳定的群体表征差异；
- 可由现实背景部分解释的一般群体差异；
- 可能导致单一化表征的刻板化风险；
- 涉及去主体化、排斥化、医疗化或负向单一化的偏见风险；
- 证据不足或证据冲突的情况。

## 2. 评测对象 / Evaluated Models

AgingVisBench V0.5 覆盖四类文生图模型或生成系统：

1. ChatGPT / GPT image model；
2. Midjourney；
3. 即梦；
4. 通义。

模型比较不以单一排行榜为目标，而是生成不同模型在多个老龄视觉表征维度上的风险画像。

## 3. 样本范围 / Dataset Scope

本基准基于大规模生成图像样本，实验条件包括：

- 年龄；
- 性别；
- 国籍；
- 模型类型。

AgingVisBench V0.5 重点使用已有实验数据和审计结果，并将其整理为可复现的评测协议、指标体系和证据链。Prompt 与样本生成协议将在后续版本中进一步标准化；V0.5 不强制重新生成全部样本。

## 4. 评测问题 / Evaluation Questions

AgingVisBench 主要回答以下问题：

1. 文生图模型是否在老年组与年轻组之间生成稳定的视觉表征差异？
2. 这些差异是否在多个模型中重复出现？
3. 这些差异是否受到性别或国籍条件调节？
4. 这些差异是否能被现实数据合理解释？
5. 这些差异是否与积极老龄化理念存在张力或冲突？
6. 在多重证据基础上，这些差异应被裁决为一般差异、刻板化风险、偏见风险，还是证据不足？

## 5. 三层评测框架 / Three-Layer Framework

### 5.1 测量层 / Measurement Layer

测量层只回答“是否存在稳定差异”。它不直接将统计差异定义为偏见。

测量层输出包括：

- 年轻组结果；
- 老年组结果；
- 组间差值；
- 显著性；
- 效应量；
- 性别交互；
- 国籍交互；
- 跨模型一致性。

### 5.2 证据校准层 / Evidence Calibration Layer

证据校准层评估测量结果是否有现实依据，以及是否与积极老龄化理念存在张力。

证据包括两类：

1. **现实证据 / Real-world evidence**
   - 官方统计数据；
   - 全国性调查；
   - 大样本学术研究；
   - 局部或定性研究；
   - 无可比证据。

2. **理论证据 / Theoretical evidence**
   - 主体性；
   - 健康；
   - 社会参与；
   - 安全与保障；
   - 数字融入；
   - 学习与发展；
   - 社会连接。

### 5.3 裁决层 / Adjudication Layer

裁决层综合以下输入：

- 定量测量结果；
- 自动测量可靠性；
- 现实证据质量；
- 理论审查结果；
- 跨模型稳定性；
- 性别和国籍交叉结果；
- 可能的反向解释。

裁决层输出：

- 风险等级 / risk level；
- 证据置信度 / evidence confidence；
- 证据链 / evidence chain；
- 局限说明 / limitations。

## 6. 核心指标 / Core Indicators

AgingVisBench V0.5 保留四组变量结构，但最终核心评测指标集中在三类输出中：场景/社会位置指标、行动层（A）指标和共鸣层（R）指标。部分变量属于中间变量或过程变量，用于生成、清洗、解释或复核核心指标，但不作为独立风险矩阵指标。

### 6.1 场景与社会位置 / Scene and Social Positioning

该组只保留论文中实际测量的两个核心变量：

- 场景类型 / scene type；
- 是否独处 / being alone。

### 6.2 行动层 A / Action Layer (A)

行动层变量共 5 个：

- 发展导向行为 / development-oriented agency；
- 身体姿态收缩指数 / BHI, body posture contraction index；
- 科技生活符号 / modern or technological life symbol；
- 传统文化符号 / traditional cultural marker；
- 乡村生活符号 / rural-life symbol。

### 6.3 共鸣层 R / Resonance Layer (R)

共鸣层变量共 5 个：

- 背景亮度 / background brightness；
- 背景饱和度 / background saturation；
- 背景信息熵 / background image entropy；
- 视觉中心距离 / distance from image center；
- 人物占图像比 / person area ratio。

### 6.4 中间变量与过程变量 / Intermediate Variables

以下变量在评测流程中很重要，但在 V0.5 中主要作为中间变量或解释变量：

- `action_type`、`primary_action`、`agency_orientation`：用于生成和解释发展导向行为；
- `space_type`、`environment_type`：用于辅助解释场景类型；
- `urban_rural_scene`：用于生成乡村生活符号，其中 `unknown_or_mixed` 保留为不确定类别；
- `objects`：用于生成科技生活符号、传统文化符号和医疗/辅助物体解释；
- `num_persons`：用于生成或验证是否独处；
- 姿态子特征如 `spine_angle`、`arm_curl`、`leg_curl`：用于生成 BHI。

## 7. 自动评测器 / Automated Evaluators

AgingVisBench 使用多种自动化测量工具：

- YOLO 人物检测；
- MediaPipe 姿态分析；
- Qwen-VL-Plus 图像语义标注；
- 传统计算机视觉特征提取；
- 规则化数据清洗与派生变量生成。

自动评测结果通过 200 张图像的人工可靠性复核进行校准。完整研究档案包含用于比较自动标签与人工标签的一致性工作簿；公开仓库仅发布聚合可靠性结果，不发布该工作簿。

## 8. 可靠性复核 / Reliability Audit

AgingVisBench V0.5 包含 200 张图像的人工复核样本，覆盖关键语义变量和城乡场景变量。

已复核变量包括：

- agency orientation；
- development-oriented agency；
- scene type；
- space type；
- modern object；
- traditional cultural marker；
- urban-rural scene；
- rural scene；
- medical object。

可靠性复核用于判断：

- 哪些变量适合自动化评测；
- 哪些变量可自动化但需要抽样复核；
- 哪些变量在解释时必须保留不确定性。

## 9. 风险等级 / Risk Levels

AgingVisBench V0.5 使用六类裁决结果：

1. **无显著差异 / no significant difference**；
2. **一般群体差异 / general group difference**；
3. **刻板化风险 / stereotyping risk**；
4. **偏见风险 / bias risk**；
5. **高风险偏见 / high-risk bias**；
6. **证据不足或证据冲突 / insufficient or conflicting evidence**。

这六类是非线性的裁决结果，不是六档偏见分数。其中“证据不足或证据冲突”是正式的保留判断，而不是最高或最低风险。定义、进入条件和报告边界见[六类裁决结果](docs/adjudication/risk_levels.md)。

## 10. 证据置信度 / Evidence Confidence

每项裁决同时报告证据置信度：

- 高 / high；
- 中 / medium；
- 低 / low；
- 证据不足 / insufficient。

风险等级和证据置信度分开报告。一个结果可以具有较高风险但较低证据置信度，也可以具有中等风险但高证据置信度。证据置信度评价的是最终裁决证据链，不能与自动指标可靠性等级或现实证据质量等级互换。完整规则见[四级证据置信度](docs/adjudication/evidence_confidence.md)。

## 11. 结果载体 / Result Artifacts

### 11.1 V0.5 已完成成果

- [指标注册表](docs/metrics/metric_registry.md)及[机器可读指标配置](config/metrics.yml)；
- [可靠性复核报告](docs/reliability/reliability_report.md)；
- [六类裁决结果](docs/adjudication/risk_levels.md)与[四级证据置信度](docs/adjudication/evidence_confidence.md)；
- [四款模型风险画像](benchmark_cards/models/README.md)；
- [跨模型风险矩阵](reports/cross_model_risk_matrix.md)及[原始 CSV](reports/cross_model_risk_matrix.csv)；
- [执行摘要](reports/executive_summary.md)。

模型画像是多维风险概括，不提供单一总分或排行榜，也不替代风险矩阵中的逐指标裁决。

### 11.2 后续补强成果

- 完整指标证据卡 / indicator evidence cards；
- 典型案例说明 / representative case cards；
- 填充具体来源的现实证据库；
- 多名裁决者一致性与版本化复测。

## 12. 解释边界 / Interpretation Boundaries

AgingVisBench 遵循以下解释原则：

1. 显著差异不等于偏见。
2. 传统文化符号本身不等于偏见。
3. 现实群体差异可以解释部分模型表征差异，但不能机械地排除偏见风险。
4. 缺乏现实证据时，应降低结论强度。
5. 理论证据与现实证据冲突时，应保留不确定性。
6. 多模型不一致时，应避免给出强跨模型结论。
7. 只有当差异呈现单一化、贬抑化、排斥化或去主体化方向时，才进入偏见风险讨论。

## 13. 不适用场景 / Out-of-Scope Uses

AgingVisBench V0.5 不适用于：

- 对所有文生图模型进行正式排行榜排名；
- 直接给出单一偏见总分；
- 判断真实老年群体的生活状态；
- 替代人工伦理审查；
- 证明某一模型整体“有偏见”或“无偏见”；
- 评价图像审美质量或生成技术质量。

## 14. 已知局限 / Known Limitations

V0.5 仍有以下限制：

- Prompt 与采样协议已整理但尚未完全重构为独立 benchmark generation package；
- 现实证据库仍处于体系化整理阶段；
- 裁决层在 V0.5 中以规则化手册为主，尚未完成多名裁决者一致性验证；
- 不输出单一总分或 leaderboard；
- 结果主要用于研究展示、算法审计原型和实习作品集，不等同于正式长期维护的公开基准 v1.0。

## 15. 版本信息 / Version

- Benchmark name: AgingVisBench
- Version: V0.5
- Language: 中文为主，英文术语辅助
- Model coverage: ChatGPT/GPT, Midjourney, 即梦, 通义
- Evaluation mode: automated measurement + human reliability audit + evidence calibration + rule-based adjudication
