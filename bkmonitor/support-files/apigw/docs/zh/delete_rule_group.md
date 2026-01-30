### 功能描述

删除规则组及对应的规则

### 请求参数

| 字段        | 类型        | 必选 | 描述      |
|-----------|-----------|----|---------|
| bk_biz_id | int       | 是  | 业务ID    |
| group_ids | list[int] | 是  | 分派组ID列表 |

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "group_ids": [7]
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 删除结果数据 |

#### data 字段说明

| 字段                | 类型        | 描述          |
|-------------------|-----------|-------------|
| deleted_group_ids | list[int] | 已删除的分派组ID列表 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {"deleted_group_ids": [7]},
    "request_id": "b8cf17b82cd949e984011d890ac554df"
}
```

