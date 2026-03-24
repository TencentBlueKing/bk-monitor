### 功能描述

置顶或取消置顶空间

### 请求参数

| 字段        | 类型  | 必选 | 描述                                       |
|-----------|-----|----|------------------------------------------|
| space_uid | str | 是  | 空间唯一标识，格式为 `{space_type_id}__{space_id}` |
| action    | str | 是  | 置顶动作，`on` 表示置顶，`off` 表示取消置顶              |
| username  | str | 是  | 用户名                                      |

### 请求参数示例

```json
{
    "space_uid": "bkcc__2",
    "action": "on",
    "username": "admin"
}
```

### 响应参数

| 字段      | 类型        | 描述              |
|---------|-----------|-----------------|
| result  | bool      | 请求是否成功          |
| code    | int       | 返回的状态码          |
| message | string    | 描述信息            |
| data    | list[str] | 当前用户置顶空间 UID 列表 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        "bkcc__2",
        "bkci__myproject"
    ]
}
```
