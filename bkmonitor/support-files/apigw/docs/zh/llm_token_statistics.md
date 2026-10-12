# 查询 Trace 内 Agent Token 统计

一次查询返回指定 Trace 中所有 Agent Span 的 Token 统计，供前端按 Span ID 查找并展示。

## 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| bk_biz_id | int | 是 | 业务 ID |
| app_name | string | 是 | APM 应用名称 |
| trace_id | string | 是 | Trace ID |

## 请求示例

```json
{
  "bk_biz_id": 11,
  "app_name": "sand_local_dev",
  "trace_id": "e61291b15858305c87ecc0a40204b39b"
}
```

## 响应数据

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| trace_id | string | Trace ID |
| statistics | object | 以 Agent Span ID 为键的 Token 统计映射 |
| statistics.{span_id}.input_tokens | int | 输入 Token 数量 |
| statistics.{span_id}.output_tokens | int | 输出 Token 数量 |
| statistics.{span_id}.total_tokens | int | 输入与输出 Token 数量之和 |
| statistics.{span_id}.cache_read_input_tokens | int | 缓存读取 Token 数量 |
| statistics.{span_id}.cache_write_input_tokens | int | 缓存写入 Token 数量 |

## 响应示例

```json
{
  "trace_id": "e61291b15858305c87ecc0a40204b39b",
  "statistics": {
    "8436ce649940adeb": {
      "input_tokens": 5822513,
      "output_tokens": 10882,
      "total_tokens": 5833395,
      "cache_read_input_tokens": 2881152,
      "cache_write_input_tokens": 0
    }
  }
}
```

接口不会根据文本自行分词或估算 Token。Agent Span 已上报输入或输出 Token 时直接使用其上报值；两者均为 0 或缺失时，累计该 Agent 子树内已识别模型调用 Span 上报的 Token。缓存读写 Token 是输入 Token 的细分项，不重复计入 `total_tokens`。
