# AgingVisBench

**A multi-evidence benchmark prototype for auditing aging-related visual representation in text-to-image models.**  
面向文生图模型老龄化视觉表征的多证据校准评测原型。

> **Release status — V0.5 research snapshot**
>
> 本仓库公开安全化后的审计代码、评测文档、聚合报告和 synthetic 示例。原始/生成图像语料、行级研究数据、人工复核工作簿、模型权重和 API 凭据不公开。`reports/` 中的数值是历史研究快照，不能由 synthetic 示例复现，也不代表托管服务的当前模型版本。

## 项目解决什么问题？

文生图模型并不只生成“人物图片”；它们也会重复安排人物的行动、空间、物体、身体姿态和视觉氛围。对于老年形象，单一的家庭化、维护性活动、去现代化、医疗化或视觉边缘化模式，可能压缩其可见的生活可能性。

AgingVisBench 把这一问题转化为可测量、可复核、可解释的评测流程。它不把统计显著差异直接等同于偏见，也不输出单一偏见总分或模型排行榜。

## 核心逻辑

```text
已有图像语料 / image corpus
  → 自动视觉与语义测量 / CV + VLM measurement
  → stats-ready 数据
  → 人工可靠性复核 / human reliability audit
  → 现实证据与积极老龄化理论校准
  → 规则化风险裁决
  → 分模型风险画像
  → 下一轮证据补强与验证
```

这是一个 benchmark 与审计产品原型，而不是普通的汇总性数据分析项目。其关键产物包括：

- 指标注册表与机器可读配置；
- 自动测量和人工复核的可靠性证据；
- 六类非线性风险裁决与四级证据置信度；
- 逐指标的跨模型风险矩阵；
- GPT、Midjourney、即梦和通义的分模型风险画像。

完整方法边界见 [Benchmark Card](BENCHMARK_CARD.md)，聚合结果入口见 [reports/README.md](reports/README.md)。

## 当前实现

### 自动测量

- YOLO：人物数量、人物占图像比、视觉中心距离；
- MediaPipe：姿态子特征与实验性 BHI；
- 传统计算机视觉：背景亮度、饱和度和信息熵；
- DashScope VLM：行动、场景、空间、可见物体、现代/传统符号；
- 规则化派生：发展导向行为、是否独处、乡村生活符号等。

### 证据与裁决

- 200 张图像人工可靠性复核的聚合结果；
- 现实证据质量分级；
- 积极老龄化理论审查表；
- 六类风险结果和独立的证据置信度；
- 12 个风险维度的跨模型矩阵及模型卡。

### 公开范围

公开仓库从**已有图像语料**开始。历史图像生成客户端没有被包装为稳定的 public generation package：原实验使用多个 provider-specific 脚本，而采样协议和精确托管模型版本尚未达到可独立复现的公开标准。相关限制见 [模型版本说明](docs/model_versioning.md)。

## Repository layout

```text
.
├── processing/          # 主入口、CV/VLM 审计、城乡补充审计、可靠性计算
├── process/             # development-oriented agency 规则化重编码
├── analysis/            # 需要私有 stats-ready 数据的 R 分析脚本
├── config/              # 指标、理论、裁决和 pipeline 配置
├── docs/                # 方法、可靠性、证据与裁决文档
├── benchmark_cards/     # 分模型和指标卡
├── reports/             # V0.5 聚合结果快照
├── evidence/            # 证据映射和空白模板
├── templates/           # 裁决记录模板
├── examples/            # 无隐私 synthetic 示例
├── scripts/             # public-repo 安全检查
└── tests/               # 无 API、无私有数据的测试
```

## Quick Start

### 1. 创建最小环境

推荐 Python 3.10（原研究环境基线）：

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

macOS/Linux 请使用 `.venv/bin/python`。

按需安装可选能力：

```bash
# YOLO + MediaPipe + OpenCV
.venv/Scripts/python -m pip install -r requirements-vision.txt

# DashScope VLM semantic audit
.venv/Scripts/python -m pip install -r requirements-semantic.txt
```

也可以使用 `environment.yml` 创建精简 Conda 环境。

### 2. 查看状态（无写入、无 API）

```bash
.venv/Scripts/python processing/run_full_audit_pipeline.py \
  --stage status \
  --config config/pipeline.example.yml
```

### 3. 使用 synthetic corpus 验证 discovery dry-run

```bash
.venv/Scripts/python processing/run_rq2_full_pipeline.py \
  --image-root examples/sample_corpus \
  --output-root outputs/synthetic \
  --models synthetic_model \
  --max-images 1 \
  --skip-api \
  --dry-run
```

该命令只打印发现结果和执行计划，不创建目录、manifest 或结果文件。

### 4. 查看完整 pipeline 计划

```bash
.venv/Scripts/python processing/run_full_audit_pipeline.py \
  --stage all \
  --config config/pipeline.example.yml \
  --dry-run \
  --max-images 1 \
  --skip-api
```

### 5. 运行 synthetic reliability 示例

```bash
.venv/Scripts/python processing/compute_reliability.py \
  --input examples/sample_reliability.csv
```

这些结果只验证计算接口，不是研究发现。

## 使用私有语料执行审计

### 输入结构

图像根目录的一级目录是模型名；实验组目录采用 `年龄_国籍_性别` 形式：

```text
data/images/
└── model_name/
    └── 60yo_China_Woman/
        ├── image_001.png
        └── split/                 # 可选：四宫格拆分结果
            └── image_001_1.png
```

复制配置并只在本机填写路径：

```bash
cp config/pipeline.example.yml config/pipeline.local.yml
cp .env.example .env
```

本项目不会自动读取或提交 `.env`。请在 shell/IDE 中加载环境变量。执行前先 dry-run，再小样本运行：

```bash
.venv/Scripts/python processing/run_full_audit_pipeline.py \
  --stage rq2 \
  --config config/pipeline.local.yml \
  --max-images 5 \
  --execute
```

CV stage 需要本地 YOLO 权重；仓库不会自动下载或跟踪权重。semantic stage 需要 `DASHSCOPE_API_KEY`。若使用 `--skip-api --execute`，只运行非 API 部分，并明确跳过 semantic merge；不会伪造 `unknown` 标签来冒充审计结果。

## 输入与输出

主要输入：

- 按模型、年龄、国籍、性别组织的图像；
- 本地 pipeline 配置；
- 可选 DashScope 凭据和模型名；
- 人工复核 CSV（可靠性计算）；
- 证据与裁决记录。

本地输出默认写入被 Git 忽略的 `outputs/`：

- discovery summary 与 manifest；
- CV 和 semantic checkpoint；
- merged / stats-ready CSV、XLSX；
- 城乡补充审计；
- reliability summary；
- 私有统计分析结果。

公开聚合输出见：

- [执行摘要](reports/executive_summary.md)
- [跨模型风险矩阵](reports/cross_model_risk_matrix.md)
- [模型风险画像](benchmark_cards/models/README.md)
- [可靠性报告](docs/reliability/reliability_report.md)

## V0.5 关键结果（谨慎摘要）

历史样本中，科技/现代生活符号下降与传统文化符号增加是较稳定的跨模型模式；发展导向行为在多数模型下降，但 Midjourney 构成重要反例。即梦更突出家庭化和独处化，Midjourney 的风险更集中于符号与构图层，通义更突出传统化、庭院化与医疗化。

这些概括：

- 不是总分或排行榜；
- 不代表模型当前版本；
- 必须与可靠性、证据置信度和模型特异限制一起读取；
- 不意味着传统文化、乡村场景或单人图像本身就是偏见。

## 数据、隐私与可复现边界

- 原始/生成图像约 6.2 GB，未公开；
- 行级 CSV/XLSX 包含本机路径等信息，未公开；
- 人工复核工作簿和 review images 未公开；
- YOLO 权重和第三方论文模板未公开；
- 聚合报告可审阅，但不能仅由本仓库中的 synthetic data 复算；
- public CI 不调用 API、不下载模型、不验证历史数值。

详见 [数据与隐私](docs/data_and_privacy.md) 和 [可复现性说明](docs/reproducibility.md)。

## 已知限制

- V0.5 的生成 prompt、采样协议和精确模型版本记录不完整；
- 完整 end-to-end 运行需要未公开的私有语料；
- BHI 和 R 层视觉特征属于技术测量，不应被表述为临床指标；
- `is_alone` 没有直接人工一致性结果，医疗物体变量的有效人工复核样本为 0；
- 裁决以规则化手册为主，尚未完成多裁决者一致性；
- R 分析脚本保留研究期数据结构，运行前需提供私有 stats-ready 文件；
- public code productization 没有改变或重新验证历史统计结论。

## 后续扩展

- 标准化可公开的生成协议与模型版本记录；
- 建立可授权发布的小规模 benchmark 数据集；
- 增加多裁决者复核和版本化复测；
- 完成现实证据库及指标证据卡；
- 使用新模型版本进行独立复验，而不是把 V0.5 外推为当前结论。

## Development

```bash
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest
.venv/Scripts/python scripts/check_public_repo.py
```

上传前还应运行 [GitHub Release Checklist](GITHUB_RELEASE_CHECKLIST.md)。

## License status

本仓库目前**尚未选择开源许可证**。代码可供审阅不等于已授予复制、修改或再分发许可；公开发布前请由项目所有者决定许可证和数据/报告授权边界。
