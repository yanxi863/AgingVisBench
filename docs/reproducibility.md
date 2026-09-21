# 可复现性说明

AgingVisBench V0.5 区分三种可复现性。

## 1. 结构可复现

公开仓库可以在无 API、无私有数据的情况下验证：

- 配置加载和路径解析；
- 图像目录发现和 manifest 字段；
- JSON/枚举清洗；
- 年龄分组与 stats-ready 派生函数；
- development-oriented agency 规则；
- agreement 与 Cohen's kappa 计算；
- dry-run、文档链接和公开边界检查。

`examples/` 和 public CI 只覆盖这一层。

## 2. 管线可复现

用户自备合法图像、YOLO 权重和 DashScope 凭据后，可以运行 CV/VLM 审计及本地输出。结果会受依赖版本、权重、provider 模型和服务端更新影响。

## 3. V0.5 数值结果复现

本仓库不包含生成图像、行级测量数据或完整人工复核工作簿，因此不能从公开文件独立重算 `reports/` 中的历史数值。聚合结果用于透明展示既有研究，不是由 synthetic fixtures 生成。

## R 分析

`analysis/RQ2_NAR_analysis.R` 保留了原研究的分模型统计流程，但需要私有 stats-ready CSV。脚本不自动安装包，并通过 `--pipeline-dir` 和 `--output-dir` 接收本地路径。

## 解释边界

- 显著差异不等于偏见；
- 自动测量可靠性、现实证据质量和最终证据置信度不是同一个概念；
- 多模型结果优先分模型报告；
- 老年图像中的传统、乡村、家庭或单人场景不天然构成负面判断。
