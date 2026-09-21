# AI / VLM 配置说明

## VLM 在项目中的角色

DashScope 多模态模型用于对**可见图像元素**进行结构化语义编码，包括行动、场景、空间、物体及现代/传统符号。它是测量工具之一，不负责最终偏见裁决。

## 环境变量

```env
DASHSCOPE_API_KEY=
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/api/v1
DASHSCOPE_MODEL=qwen-vl-plus
```

- API key 只从环境变量读取；
- base URL 和 model alias 可由本地环境覆盖；
- public CI 和默认 dry-run 不调用 API；
- 缺少 key 时，API stage 应失败或被明确跳过，而不是生成伪标签。

## Prompt 原则

内置 prompt 要求：

- 仅依据可观察的视觉元素；
- 不推测身份、职业、文化背景或故事；
- 不确定时保留 null / unknown；
- 返回限定 JSON；
- 自动结果后续仍需可靠性复核和证据校准。

## 结果限制

VLM 输出可能受到 provider 更新、图像分辨率、提示词、解析失败和小物体识别能力影响。semantic 标签不能单独证明偏见。运行者应记录模型 alias、日期、prompt 版本、错误率和人工复核结果。

## 其他 AI provider

原研究曾使用多个 provider-specific 图像生成客户端。由于生成协议和版本 provenance 尚未形成稳定 public package，本仓库没有发布这些客户端，也没有将其替换为其他厂商 SDK。
