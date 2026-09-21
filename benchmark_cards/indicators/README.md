# AgingVisBench 指标证据卡索引

**Indicator Evidence Cards Index**

本目录用于存放每个核心指标的证据卡。V0.5 当前已经完成指标注册表、可靠性报告、现实证据规则和裁决手册；后续可以为每个核心指标生成独立证据卡。

## 核心指标列表

### 场景与社会位置

| 指标 | 文件建议 | 当前状态 |
|---|---|---|
| 场景类型 / `scene_type` | `scene_type.md` | 待生成 |
| 是否独处 / `is_alone` | `is_alone.md` | 待生成 |

### 行动层 A

| 指标 | 文件建议 | 当前状态 |
|---|---|---|
| 发展导向行为 / `development_oriented_agency` | `development_oriented_agency.md` | 待生成 |
| 身体姿态收缩指数 / `bhi` | `bhi.md` | 待生成 |
| 科技生活符号 / `modern_object` | `modern_object.md` | 待生成 |
| 传统文化符号 / `traditional_cultural_marker` | `traditional_cultural_marker.md` | 待生成 |
| 乡村生活符号 / `rural_scene` | `rural_scene.md` | 待生成 |

### 共鸣层 R

| 指标 | 文件建议 | 当前状态 |
|---|---|---|
| 背景亮度 / `bg_brightness` | `bg_brightness.md` | 待生成 |
| 背景饱和度 / `bg_saturation` | `bg_saturation.md` | 待生成 |
| 背景信息熵 / `image_entropy_background` | `image_entropy_background.md` | 待生成 |
| 视觉中心距离 / `center_distance` | `center_distance.md` | 待生成 |
| 人物占图像比 / `area_ratio` | `area_ratio.md` | 待生成 |

## 证据卡模板

每张指标证据卡建议包含：

```text
1. 指标定义
2. 测量方法
3. 自动测量可靠性
4. 主要统计结果
5. 跨模型模式
6. 现实证据
7. 积极老龄化理论审查
8. 风险等级
9. 证据置信度
10. 反向解释
11. 局限
12. 典型案例
```

## 相关文件

- [指标注册表](../../docs/metrics/metric_registry.md)
- [机器可读指标配置](../../config/metrics.yml)
- [可靠性报告](../../docs/reliability/reliability_report.md)
- [现实证据质量规则](../../docs/evidence/evidence_quality_rubric.md)
- [六类裁决结果](../../docs/adjudication/risk_levels.md)
- [四级证据置信度](../../docs/adjudication/evidence_confidence.md)
- [裁决手册](../../docs/adjudication/adjudication_manual.md)
- [跨模型风险矩阵](../../reports/cross_model_risk_matrix.md)
- [原始风险矩阵 CSV](../../reports/cross_model_risk_matrix.csv)
- [四模型风险画像](../models/README.md)
