### 功能描述

通过空间获取接入 VM 的指标结果表列表

### 请求参数

| 字段         | 类型  | 必选 | 描述    |
|------------|-----|----|-------|
| space_type | str | 是  | 空间类型  |
| space_id   | str | 是  | 空间 ID |

### 请求参数示例

```json
{
    "space_type": "bkcc",
    "space_id": "2"
}
```

### 响应参数

| 字段      | 类型        | 描述     |
|---------|-----------|--------|
| result  | bool      | 请求是否成功 |
| code    | int       | 返回的状态码 |
| message | string    | 描述信息   |
| data    | list[str] | 返回数据   |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        "vm_result_table_id_1",
        "vm_result_table_id_2"
    ]
}
```
