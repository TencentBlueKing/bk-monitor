### 功能描述

删除日志分组

### 请求参数

| 字段           | 类型     | 必选 | 描述     |
|--------------|--------|----|--------|
| log_group_id | int    | 是  | 日志分组ID |
| operator     | string | 是  | 操作者    |

### 请求参数示例

```json
{
    "log_group_id": 1,
    "operator": "admin"
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
