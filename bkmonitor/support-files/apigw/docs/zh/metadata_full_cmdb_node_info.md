### 功能描述

根据结果表 ID 补充 CMDB 节点信息

### 请求参数

| 字段       | 类型  | 必选 | 描述     |
|----------|-----|----|--------|
| table_id | str | 是  | 结果表 ID |

### 请求参数示例

```json
{
    "table_id": "system.cpu_detail"
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
