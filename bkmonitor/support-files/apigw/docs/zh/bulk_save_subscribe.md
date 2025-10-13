### 功能描述

批量新增/保存策略订阅

#### 请求方法

POST

#### 请求路径

`/app/subscribe/bulk_save/`

#### 接口参数

| 字段           | 类型                    | 必须 | 描述                     |
|--------------|----------------------|----|------------------------|
| bk_biz_id    | int                  | 是  | 业务ID                   |
| subscriptions| list[subscription]   | 是  | 订阅列表                   |

##### subscription 数据格式

| 字段         | 类型              | 必须 | 描述                     |
|------------|-----------------|----|--------------------------|
| id         | int             | 否  | 订阅ID，存在则更新             |
| username   | string          | 是  | 用户名                    |
| conditions | list[condition] | 是  | 条件列表                   |
| notice_ways| list[string]    | 是  | 通知方式，支持：weixin,rtx,wecom_robot,mail,sms,voice,wxwork-bot,bkchat               |
| priority   | int             | 否  | 优先级（暂未实现功能）            |
| is_enable  | bool            | 否  | 是否启用                   |
| user_type  | string          | 否  | 用户类型，`main`/`follower` |

##### condition 数据格式

| 字段       | 类型        | 必须 | 描述                          |
|----------|-----------|----|-----------------------------|
| field    | string    | 是  | 过滤字段，例如 `alert.strategy_id` |
| value    | list      | 是  | 取值列表，例如 `[15070, 16763]`    |
| method   | string    | 是  | 匹配方式，例如 `eq`                |
| condition| string    | 是  | 条件连接符，`and` 或 `or`          |

#### 请求示例

```json
{
  "bk_biz_id": 2,
  "subscriptions": [
    {
      "id": 123,
      "username": "admin",
      "conditions": [
        {"field": "alert.strategy_id", "value": [15070, 16763], "method": "eq", "condition": "and"},
        {"field": "alert.severity", "value": [1, 2], "method": "eq", "condition": "and"}
      ],
      "notice_ways": ["rtx", "mail"],
      "priority": 111,
      "is_enable": true,
      "user_type": "follower"
    },
    {
      "username": "user2",
      "conditions": [
        {"field": "alert.strategy_id", "value": [15072], "method": "eq", "condition": "and"}
      ],
      "notice_ways": ["weixin"],
      "priority": 100,
      "is_enable": true,
      "user_type": "main"
    }
  ]
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

| 字段      | 类型  | 描述       |
|---------|-----|----------|
| created | int | 新创建的订阅数量 |
| updated | int | 更新的订阅数量  |

#### 示例数据

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "created": 1,
    "updated": 1
  }
}
```

#### 说明

- 当 `subscription` 中包含 `id` 字段时，会尝试更新对应的订阅记录
- 当 `subscription` 中不包含 `id` 字段时，会创建新的订阅记录
- 所有操作在同一个事务中执行，确保数据一致性
- 如果更新的订阅ID在指定业务下不存在，操作会失败并回滚