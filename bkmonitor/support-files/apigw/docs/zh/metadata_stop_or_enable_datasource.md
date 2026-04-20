### 功能描述

批量启用或停用数据源

### 请求参数

| 字段           | 类型        | 必选 | 描述                            |
|--------------|-----------|----|-------------------------------|
| data_id_list | list[int] | 是  | 数据源 ID 列表                     |
| is_enabled   | bool      | 否  | 是否启用数据源，`true` 为启用，默认为 `true` |

### 请求参数示例

```json
{
    "data_id_list": [1001, 1002, 1003],
    "is_enabled": false
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | null | 无返回数据  |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": null
}
```
