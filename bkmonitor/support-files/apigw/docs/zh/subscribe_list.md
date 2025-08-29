### 功能描述

策略订阅列表

#### 请求方法

GET

#### 请求路径

`/app/subscribe/list/`

#### 接口参数

| 字段        | 类型    | 必须 | 描述  |
|-----------|-------|----|-----|
| username  | string| 是  | 用户名 |
| bk_biz_id | int   | 是  | 业务ID |

#### 请求示例

`GET /app/subscribe/list/?username=admin&bk_biz_id=2`

### 响应参数

| 字段       | 类型   | 描述         |
|----------|------|------------|
| result   | bool | 请求是否成功     |
| code     | int  | 返回的状态码     |
| message  | string | 描述信息       |
| data     | list | 数据列表        |
| request_id | string | 请求ID       |

#### data.item 字段说明

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
  "data": [
    {
      "id": 1,
      "username": "xxxxx",
      "bk_biz_id": 2,
      "conditions": [
        {
          "field": "alert.strategy_id",
          "value": [
            1
          ],
          "method": "include",
          "condition": "and"
        },
        {
          "field": "ip",
          "value": [
            "127.0.0.1"
          ],
          "method": "eq",
          "condition": "and"
        }
      ],
      "notice_ways": [
        "weixin",
        "mail"
      ],
      "priority": -1,
      "user_type": "follower",
      "is_enable": true
    }
  ]
}
```


