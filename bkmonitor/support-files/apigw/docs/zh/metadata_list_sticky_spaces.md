### 功能描述

查询当前用户的置顶空间列表

### 请求参数

无

### 请求参数示例

无

### 响应参数

| 字段      | 类型        | 描述          |
|---------|-----------|-------------|
| result  | bool      | 请求是否成功      |
| code    | int       | 返回的状态码      |
| message | string    | 描述信息        |
| data    | list[str] | 置顶空间 UID 列表 |

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
