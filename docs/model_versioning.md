# 模型与版本说明

V0.5 历史样本覆盖 ChatGPT/GPT image、Midjourney、即梦和通义生成系统。研究期文件记录了模型家族、生成批次和部分脚本配置，但没有为每张公开报告中的图像保存完整、可验证、长期稳定的 provider model revision。

因此：

- 报告中的模型名表示历史研究样本来源，不是对当前服务版本的声明；
- 托管服务可能在相同产品名下更新权重、过滤器、默认参数和生成行为；
- 当前 API alias（例如 VLM semantic audit 使用的 `qwen-vl-plus`）也可能变化；
- 不应把 V0.5 风险画像外推为所有版本、所有 prompt 或当前线上服务的固定属性；
- 新复验应记录 provider、model ID/alias、日期、区域、参数、prompt hash、采样数和失败记录。

本次公开化没有补造缺失的模型版本信息。未来 release 应将模型 provenance 作为必填元数据。
