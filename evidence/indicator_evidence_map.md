# 指标—现实证据映射表

**Indicator-to-Evidence Map for AgingVisBench V0.5**

本文件说明每个核心指标需要什么类型的现实证据，以及现实证据在裁决中应如何使用。

## 1. 场景与社会位置

### S1. 场景类型 / `scene_type`

- **建议证据类型**: national survey, time-use survey, ageing participation studies。
- **可参考现实维度**:
  - 老年人居家时间；
  - 公共空间参与；
  - 医疗/照护机构接触；
  - 社区活动参与。
- **可比性**: partial。
- **原因**: 生成图像中的场景类型不是现实时间使用或居住地点的直接测量。
- **裁决用途**: 若模型稳定将老年人置于 home/hospital/yard，并减少公共、学习、工作或社会参与空间，可作为空间压缩证据。

### S2. 是否独处 / `is_alone`

- **建议证据类型**: living arrangement statistics, loneliness/social contact surveys。
- **可参考现实维度**:
  - 独居比例；
  - 社会联系频率；
  - 家庭同住结构；
  - 社区参与。
- **可比性**: partial。
- **原因**: 图像中单人出现不等于现实孤独，也不等于独居。
- **裁决用途**: 若独处与家庭化、低发展导向行为、低科技生活符号共同出现，可作为社会连接弱化的辅助证据。

## 2. 行动层 A

### A1. 发展导向行为 / `development_oriented_agency`

- **建议证据类型**: national survey, labour participation, lifelong learning, volunteering, social participation studies。
- **可参考现实维度**:
  - 老年劳动参与；
  - 继续教育；
  - 志愿活动；
  - 社区参与；
  - 照护与家务劳动。
- **可比性**: partial。
- **原因**: 图像行动类型不是现实参与率，但可以和积极老龄化中的主体性、参与和发展维度对应。
- **裁决用途**: 若模型系统性将老年行动压缩为 maintenance，且现实证据不能充分解释，风险等级可上调。

### A2. 身体姿态收缩指数 / `bhi`

- **建议证据类型**: no comparable evidence。
- **可比性**: none。
- **原因**: BHI 是图像姿态/构图测量，不是现实健康或身体状态指标。
- **裁决用途**: 只作为辅助视觉证据，不单独作为偏见裁决依据。

### A3. 科技生活符号 / `modern_object`

- **建议证据类型**: official statistics, national survey, digital divide reports。
- **可参考现实维度**:
  - 老年人互联网使用率；
  - 智能手机使用率；
  - 数字设备拥有率；
  - 数字服务使用；
  - 科技融入与数字鸿沟。
- **可比性**: direct 或 partial。
- **原因**: 图像中的科技生活符号与现实数字使用存在较强对应，但不是一一对应。
- **裁决用途**: 若模型中老年科技生活符号显著降低，并且远超现实数字鸿沟或忽略老年数字融入趋势，可构成去现代化/数字排斥风险。

### A4. 传统文化符号 / `traditional_cultural_marker`

- **建议证据类型**: contextual cultural studies, media representation studies, ageing culture studies。
- **可参考现实维度**:
  - 传统文化实践；
  - 代际文化差异；
  - 中国/西方文化符号使用；
  - 媒介中的老年文化形象。
- **可比性**: contextual。
- **原因**: 传统文化符号不是现实行为率，文化含义依语境变化。
- **裁决用途**: 传统符号本身不构成偏见。只有当传统符号与去现代化、国籍刻板化或老年身份固定化结合时，才作为风险证据。

### A5. 乡村生活符号 / `rural_scene`

- **建议证据类型**: official urban/rural population statistics, residence distribution, metro/nonmetro statistics。
- **可参考现实维度**:
  - 老年人口城乡分布；
  - 城镇化率；
  - 中国与美国老年人口城乡/都会区分布；
  - 农村老龄化。
- **可比性**: partial。
- **原因**: 图像中的可见乡村线索不同于现实居住地统计。
- **裁决用途**: 若老年组或中国老年组被显著乡村化，应结合现实城乡结构和积极老龄化理论谨慎裁决。

## 3. 共鸣层 R

### R1-R5. 视觉共鸣指标

包括：

- `bg_brightness`
- `bg_saturation`
- `image_entropy_background`
- `center_distance`
- `area_ratio`

- **建议证据类型**: no comparable evidence。
- **可比性**: none。
- **原因**: 这些指标是图像视觉氛围和构图指标，没有直接现实人口基准。
- **裁决用途**:
  - 作为模型风格和视觉共鸣证据；
  - 支持“视觉边缘化”“氛围暗化/单调化”等谨慎解释；
  - 不单独构成偏见风险。

## 4. 证据缺失时的处理

如果某指标没有现实证据，应：

1. 标注 `no-comparable-evidence`；
2. 不使用现实证据支持强裁决；
3. 依赖理论审查、跨模型稳定性和可靠性证据；
4. 在最终风险矩阵中降低 evidence confidence。

## 5. 下一步填充优先级

优先补现实证据的指标：

1. `modern_object`：数字鸿沟/数字融入数据；
2. `development_oriented_agency`：老年社会参与、学习、劳动、志愿活动数据；
3. `rural_scene`：城乡/都会区人口分布数据；
4. `is_alone`：独居、社会联系、孤独感数据；
5. `scene_type`：居家、公共参与、医疗机构接触或时间使用数据。

传统文化符号和 R 层指标可以后续作为解释性或理论性证据补充，不必强求现实数值对照。
