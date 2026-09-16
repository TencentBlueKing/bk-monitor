# 查询 Agent Span Token 统计

根据 Trace ID 和 Agent Span ID，累计该 Agent 子树内模型调用的 Token 数量。

## 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| bk_biz_id | int | 是 | 业务 ID |
| app_name | string | 是 | APM 应用名称 |
| trace_id | string | 是 | Trace ID |
| span_id | string | 是 | Agent Span ID |

## 请求示例

```json
{
  "bk_biz_id": 11,
  "app_name": "sand_local_dev",
  "trace_id": "e61291b15858305c87ecc0a40204b39b",
  "span_id": "8436ce649940adeb"
}
```

## 响应数据

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| trace_id | string | Trace ID |
| span_id | string | Span ID |
| input_tokens | int | 输入 Token 总数 |
| output_tokens | int | 输出 Token 总数 |
| total_tokens | int | 输入和输出 Token 总数 |
| cache_read_input_tokens | int | 缓存读取 Token 总数 |
| cache_write_input_tokens | int | 缓存写入 Token 总数 |

统计只包含该 Agent Span 子树中识别为模型调用的 Span。Agent Span 已有 Token 数据时保持原值。
