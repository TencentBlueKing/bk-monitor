### 功能描述

将结果表接入到计算平台

### 请求参数

| 字段            | 类型     | 必选 | 描述                     |
|---------------|--------|----|------------------------|
| table_id      | string | 是  | 结果表ID                  |
| is_access_now | bool   | 否  | 是否立即接入，默认为 false（异步接入） |

### 请求参数示例

```json
{
    "table_id": "2_bkmonitor_time_series_1500001.base",
    "is_access_now": false
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | null   | 无返回数据  |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": null,
    "result": true
}
```
