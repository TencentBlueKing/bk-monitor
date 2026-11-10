# 分词词表

词表来自 [OpenAI tiktoken `0.9.0`](https://github.com/openai/tiktoken/tree/0.9.0)，采用同目录的 MIT 许可证。`TokenCounter` 从压缩 JSON 加载词表，不访问网络。

- `cl100k_base.json.gz`：`cl100k_base` 编码，包含 `100,256` 个合并项。
- `o200k_base.json.gz`：`o200k_base` 编码，包含 `199,998` 个合并项。

JSON 保存原编码对象的 `pat_str`、`special_tokens` 和 `mergeable_ranks` 参数，字节键使用 Base64 编码。模型编码映射为 `o200k_base` 时使用对应词表，其余模型使用 `cl100k_base` 估算。
