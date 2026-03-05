### 功能描述

查询空间类型列表

### 请求参数

无

### 请求参数示例

无

### 响应参数

| 字段      | 类型         | 描述     |
|---------|------------|--------|
| result  | bool       | 请求是否成功 |
| code    | int        | 返回的状态码 |
| message | string     | 描述信息   |
| data    | list[dict] | 空间类型列表 |

#### data 元素字段说明

| 字段               | 类型        | 描述             |
|------------------|-----------|----------------|
| type_id          | str       | 空间类型 ID        |
| type_name        | str       | 空间类型名称         |
| allow_merge      | bool      | 是否允许合并空间       |
| allow_bind       | bool      | 是否允许绑定资源       |
| dimension_fields | list[str] | 该空间类型支持的维度字段列表 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "type_id": "bkcc",
            "type_name": "业务",
            "allow_merge": false,
            "allow_bind": false,
            "dimension_fields": ["bk_biz_id"]
        },
        {
            "type_id": "bkci",
            "type_name": "研发项目",
            "allow_merge": true,
            "allow_bind": true,
            "dimension_fields": ["projectId"]
        }
    ]
}
```
