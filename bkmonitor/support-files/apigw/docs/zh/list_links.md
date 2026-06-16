### 功能描述

查询 APM Span 的关联 Links，同时返回当前 Span 上报的正向 Links 和链接到当前 Trace / Span 的反向 Links。

接口返回统一的 OpenTelemetry Link 列表，可用于在 Span 详情中跳转到关联的 Trace 或 Span。

### 请求参数

| 字段名       | 类型 | 必选 | 描述                                      |
|-----------|----|----|-----------------------------------------|
| bk_biz_id | int | 是  | 业务 ID                                   |
| app_name  | str | 是  | APM 应用名称                                |
| trace_id  | str | 否  | Trace ID，与 `span_id` 至少提供一个             |
| span_id   | str | 否  | Span ID，与 `trace_id` 至少提供一个              |

### 查询规则

1. `trace_id` 和 `span_id` 至少提供一个。
2. 同时提供 `trace_id` 和 `span_id` 时，两个条件使用 `AND` 关系。
3. 接口不校验 `trace_id` 与 `span_id` 是否属于同一个 Span。过滤条件不匹配时，返回空列表。
4. 接口在当前 APM 应用的数据保留范围内查询，无需传入开始时间和结束时间。
5. 返回结果包含以下两类 Link：
   - 正向 Link：请求条件命中的 Span 自身上报的 `links`。
   - 反向 Link：查询 `links` 指向请求 Trace / Span 的来源 Span，并将来源 Span 转换为 Link。
6. 同时提供 `trace_id` 和 `span_id` 时，反向 Link 要求来源 Span 的同一个 `links[]` 对象同时命中两个条件。
7. 正向与反向 Link 合并后按照 Link 完整内容去重。
8. 首版接口每路最多查询 1000 条候选 Span。
9. 响应不额外返回 Link 方向字段，前端应将每个元素统一视为可跳转的关联 Span。

### 请求参数示例

#### 使用 Trace ID 和 Span ID 查询

```json
{
    "bk_biz_id": 2,
    "app_name": "demo",
    "trace_id": "38f6df9232036f09a9baecf246967ecb",
    "span_id": "8b1fa48d1af1f60d"
}
```

#### 仅使用 Trace ID 查询

```json
{
    "bk_biz_id": 2,
    "app_name": "demo",
    "trace_id": "38f6df9232036f09a9baecf246967ecb"
}
```

### 响应参数

| 字段名     | 类型   | 描述              |
|---------|------|-----------------|
| result  | bool | 请求是否成功          |
| code    | int  | 返回的状态码          |
| message | str  | 描述信息            |
| data    | list | OpenTelemetry Link 列表 |

#### data 列表中的 Link 对象字段

| 字段名        | 类型   | 描述                                                 |
|------------|------|----------------------------------------------------|
| trace_id   | str  | Link 指向的 Trace ID                                   |
| span_id    | str  | Link 指向的 Span ID                                    |
| trace_state | str  | Link 关联的 TraceState，无值时返回空字符串                      |
| attributes | dict | Link 属性，无属性时返回空对象 `{}`；反向 Link 的该字段固定为 `{}` |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "trace_id": "1a2b3c4d5e6f708192a3b4c5d6e7f809",
            "span_id": "0123456789abcdef",
            "trace_state": "",
            "attributes": {
                "relation.index": 2,
                "relation.step": "SpanLinkDemo"
            }
        },
        {
            "trace_id": "abcdef0123456789abcdef0123456789",
            "span_id": "fedcba9876543210",
            "trace_state": "vendor=value",
            "attributes": {}
        }
    ]
}
```

### 空结果示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": []
}
```

### 字段说明

- `trace_id` 对应 OpenTelemetry Link 中关联 Span 所属 Trace 的唯一标识。
- `span_id` 对应 OpenTelemetry Link 中关联 Span 的唯一标识。
- `trace_state` 用于携带与关联 Span 上下文相关的厂商信息。
- `attributes` 描述 Link 关系本身。反向 Link 由来源 Span 投影生成，不复用原始 Link 的属性，因此返回空对象。
