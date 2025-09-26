### 功能描述

新增/保存策略订阅

#### 请求方法

POST

#### 请求路径

`/app/subscribe/save/`

#### 接口参数

| 字段         | 类型              | 必须 | 描述                     |
|------------|-----------------|----|------------------------|
| id         | int             | 否  | 订阅ID，存在则更新             |
| username   | string          | 是  | 用户名                    |
| bk_biz_id  | int             | 是  | 业务ID                   |
| conditions | list[condition] | 是  | 条件列表                   |
| notice_ways| list[string]    | 是  | 通知方式，支持：weixin,rtx,wecom_robot,mail,sms,voice,wxwork-bot,bkchat               |
| priority   | int             | 否  | 优先级（暂未实现功能）            |
| is_enable  | bool            | 否  | 是否启用                   |
| user_type  | string          | 否  | 用户类型，`main`/`follower` |

##### condition 数据格式

| 字段       | 类型        | 必须 | 描述                                 |
|----------|-----------|----|------------------------------------|
| field    | string    | 是  | 过滤字段，例如 `alert.strategy_id`         |
| value    | list      | 是  | 取值列表，例如 `[15070, 16763]`            |
| method   | string    | 是  | 匹配方式，例如 `eq`                   |
| condition| string    | 是  | 条件连接符，`and` 或 `or`                 |

#### 请求示例

```json
{
  "id": 123,
  "username": "admin",
  "bk_biz_id": 2,
  "conditions": [
    {"field": "alert.strategy_id", "value": [15070, 16763], "method": "eq", "condition": "and"},
    {"field": "alert.severity", "value": [1, 2], "method": "eq", "condition": "and"}
  ],
  "notice_ways": ["rtx", "mail"],
  "priority": 111,
  "is_enable": true,
  "user_type": "follower"
}
```

### 响应参数

| 字段       | 类型   | 描述         |
|----------|------|------------|
| result   | bool | 请求是否成功     |
| code     | int  | 返回的状态码     |
| message  | string | 描述信息       |
| data     | dict | 数据         |
| request_id | string | 请求ID       |

#### data 字段说明

| 字段         | 类型           | 描述           |
|------------|--------------|--------------|
| id         | int          | 订阅ID         |
| username   | string       | 用户名          |
| bk_biz_id  | int          | 业务ID         |
| conditions | list         | 条件列表         |
| notice_ways| list[string] | 通知方式         |
| priority   | int          | 优先级          |
| user_type  | string       | 用户类型         |
| is_enable  | bool         | 是否启用         |

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
    "conditions": [
      {"field": "alert.strategy_id", "value": [15070, 16763], "method": "eq", "condition": "and"},
      {"field": "alert.severity", "value": [1, 2], "method": "eq", "condition": "and"}
    ],
    "notice_ways": ["rtx", "mail"],
    "priority": 111,
    "user_type": "follower",
    "is_enable": true
  },
  "request_id": "xxxxxxxxxx"
}
```


