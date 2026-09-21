# Public-copy migration notes

公开副本采用 allowlist 从原研究工作目录建立；原目录没有被修改。

## 保留

- 核心 YOLO / MediaPipe / VLM 测量与 stats-ready 逻辑；
- development-oriented agency 规则体系；
- R 分模型统计分析；
- 指标、可靠性、证据、裁决、风险矩阵和模型卡；
- 历史聚合数值和解释边界。

## 公开副本中的最小修正

- 统一 DashScope 环境变量和可配置 model/base URL；
- strict dry-run 不再创建 manifest 或输出目录；
- `--skip-api` 传递到 RQ2，并避免生成伪 semantic/城乡标签；
- YOLO 权重改为显式本地路径，不随仓库分发或自动下载；
- R 脚本去除本机绝对路径和自动安装包行为；
- reading + maintenance 规则先于通用 reading 规则，修复原先不可达的专门分支；
- 机器可读指标可靠性状态与公开 reliability summary 对齐。

## 未迁移

私有图像、行级数据、旧输出、checkpoint、权重、论文草稿、历史生成客户端、含凭据旧脚本、缓存和 IDE 文件均未复制。

本次迁移没有重新运行历史实验，也没有修改聚合风险判断。
