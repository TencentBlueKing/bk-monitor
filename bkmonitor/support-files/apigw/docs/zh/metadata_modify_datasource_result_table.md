### 功能描述

修改数据源与结果表的关系

### 请求参数

| 字段         | 类型     | 必选 | 描述    |
|------------|--------|----|-------|
| table_id   | string | 是  | 结果表ID |
| bk_data_id | int    | 是  | 数据源ID |

### 请求参数示例

```json
{
    "table_id": "system.cpu",
    "bk_data_id": 1001
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | null   | 数据     |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": null,
    "result": true
}
```
