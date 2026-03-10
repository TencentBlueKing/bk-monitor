### 功能描述

检查对应结果表的Kafka存储是否存在，不存在则创建

### 请求参数

| 字段        | 类型        | 必选 | 描述      |
|-----------|-----------|----|---------|
| table_ids | list[str] | 是  | 结果表ID列表 |

### 请求参数示例

```json
{
    "table_ids": ["2_bklog.test_index", "2_bklog.test_index2"]
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | null   | 返回数据   |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": null
}
```
