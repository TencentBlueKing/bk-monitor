### 功能描述

策略订阅详情

#### 请求方法

GET

#### 请求路径

`/app/subscribe/detail/`

#### 接口参数

| 字段 | 类型 | 必须 | 描述   |
|----|----|----|------|
| id | int | 是  | 订阅ID |

#### 请求示例

`GET /app/subscribe/detail/?id=1`

### 响应参数

| 字段       | 类型   | 描述         |
|----------|------|------------|
| result   | bool | 请求是否成功     |
| code     | int  | 返回的状态码     |
| message  | string | 描述信息       |
| data     | dict | 数据         |
| request_id | string | 请求ID       |

#### data 字段说明

| 字段         | 类型           | 描述     |
|------------|--------------|--------|
| id         | int          | 订阅ID   |
| username   | string       | 用户名    |
| bk_biz_id  | int          | 业务ID   |
| conditions | list         | 条件列表   |
| notice_ways| list[string] | 通知方式   |
| priority   | int          | 优先级    |
| user_type  | string       | 用户类型   |
| is_enable  | bool         | 是否启用   |

#### 示例数据

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "id": 1,
    "username": "admin",
    "bk_biz_id": 2,
    "conditions": [],
    "notice_ways": ["rtx", "mail"],
    "priority": 111,
    "user_type": "follower",
    "is_enable": true
  },
  "request_id": "xxxxxxxxxx"
}
```


