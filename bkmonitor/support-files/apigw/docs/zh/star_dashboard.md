### 功能描述

收藏指定仪表盘

### 请求参数

| 字段           | 类型     | 必选 | 描述    |
|--------------|--------|----|-------|
| bk_biz_id    | int    | 是  | 业务ID  |
| dashboard_id | string | 是  | 仪表盘ID |

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "dashboard_id": "123"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | object | 返回数据   |

#### data 字段说明

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| message | string | 操作结果消息 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "message": "Dashboard starred"
    }
}
```
