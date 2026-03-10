### 功能描述

查询数据源指定 tag/dimension 的可选值

### 请求参数

| 字段       | 类型     | 必选 | 描述                |
|----------|--------|----|-------------------|
| table_id | string | 是  | 结果表ID             |
| tag_name | string | 是  | tag/dimension 字段名 |

### 请求参数示例

```json
{
    "table_id": "2_bkmonitor_time_series_1500514.base",
    "tag_name": "target"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 返回数据   |

#### data 字段说明

| 字段         | 类型        | 描述                   |
|------------|-----------|----------------------|
| tag_values | list[str] | tag/dimension 的可选值列表 |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "tag_values": ["target1", "target2"]
    },
    "result": true
}
```