### 功能描述

解除屏蔽配置

### 请求参数

| 字段                     | 类型        | 必选 | 描述                          |
|------------------------|-----------|----|-----------------------------|
| id                     | list[int] | 是  | 屏蔽配置ID列表                    |
| bk_biz_id              | int       | 否  | 业务ID                        |
| verify_user_permission | bool      | 否  | 是否额外验证用户权限(apigw场景)，默认false |

### 请求参数示例

```json
{
    "id": [1, 2, 3],
    "bk_biz_id": 2
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | string | 返回数据   |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "success",
    "data": "success"
}
```
