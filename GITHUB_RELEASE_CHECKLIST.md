# GitHub Release Checklist

在创建 public remote 或执行第一次 push 前逐项确认。

## Release blockers

- [ ] 已在 DashScope/provider 后台轮换或吊销原工作目录中曾硬编码的凭据。
- [ ] 项目所有者确认 `reports/` 中的聚合结果和模型名称可以公开。
- [ ] 已决定许可证；若尚未决定，仓库保持无 `LICENSE`，README 不声称开源授权。
- [ ] 合作者、学校和第三方材料的公开边界已经确认。

## 必须包含

- [ ] README、Benchmark Card 和方法/裁决文档；
- [ ] 安全化后的 `processing/`、`process/` 与 R 分析脚本；
- [ ] `.env.example`、公开 pipeline 配置和依赖文件；
- [ ] synthetic 示例；
- [ ] 精选聚合 CSV/Markdown 报告；
- [ ] 数据、隐私、版本和可复现性说明；
- [ ] tests、CI 和 public-repo scanner。

## 禁止上传

- [ ] 无 `AI audit image/`、`Output data/`、`RQ2_analysis_output/`、`OLD-RQ2_analysis_output/`、`Result/`；
- [ ] 无 `.env`、API key、token、Authorization header 或原始 API response；
- [ ] 无模型权重、checkpoint、`.pyc`、缓存、IDE 和系统文件；
- [ ] 无 PDF/Office 论文草稿、学校模板或授权不明材料；
- [ ] 无本机绝对用户路径、用户名或私人 reviewer 数据；
- [ ] 无完整生成图像或行级研究数据。

## 自动验证

```bash
python -m pytest
python scripts/check_public_repo.py
python processing/run_full_audit_pipeline.py --help
python processing/run_full_audit_pipeline.py --stage status --config config/pipeline.example.yml
python processing/run_full_audit_pipeline.py --stage all --config config/pipeline.example.yml --dry-run --max-images 1 --skip-api
python processing/run_rq2_full_pipeline.py --image-root examples/sample_corpus --output-root outputs/synthetic --models synthetic_model --max-images 1 --skip-api --dry-run
```

确认 dry-run 前后没有新文件；`outputs/` 不应出现。

## Git 审核

```bash
git status --short --ignored
git ls-files
git diff --cached --stat
git diff --cached
```

- [ ] 精选 `reports/*.csv`、`templates/*.csv` 和 `evidence/*.csv` 可被跟踪；
- [ ] 私有输出、图片、权重和 Office/PDF 被忽略；
- [ ] 没有将 `.gitignore` 当作秘密清理工具：候选文件本身已通过 scanner；
- [ ] 第一次公开提交来自新的、独立的 Git 历史。

## 文档事实核查

- [ ] README 命令已在干净环境执行；
- [ ] README 未声称 synthetic data 可复现 V0.5 数值；
- [ ] README 未声称提供 leaderboard、单一偏见分数或当前模型结论；
- [ ] CV/VLM、可靠性、现实证据和裁决层的职责表述准确；
- [ ] 未虚构模型版本、样本来源、用户数量、工程能力或实验结果。

## 发布后

1. 用未登录浏览器查看仓库；
2. 在 GitHub 搜索 `sk-`、`api_key`、`Bearer`、`C:\Users`、本地用户名片段；
3. 检查大文件列表、Actions 日志和 release assets；
4. 确认 README 链接与 CSV 渲染正常；
5. 若发现秘密，立即轮换凭据并清理整个公开历史，而不只是删除最新文件。
