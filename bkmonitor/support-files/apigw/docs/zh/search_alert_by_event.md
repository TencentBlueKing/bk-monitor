### 功能描述

根据事件ID获取告警处理信息

### 请求参数

| 字段       | 类型  | 必选 | 描述   |
|----------|-----|----|------|
| event_id | str | 是  | 事件ID |

### 请求参数示例

```json
{
    "event_id": "16424876305819838"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 返回数据   |

#### data 字段说明

| 字段                   | 类型     | 描述                                         |
|----------------------|--------|--------------------------------------------|
| id                   | str    | 告警ID                                       |
| create_time          | string | 告警创建时间                                     |
| begin_time           | string | 告警开始时间                                     |
| end_time             | string | 告警结束时间（未结束时为null）                          |
| bk_biz_id            | int    | 业务ID                                       |
| strategy_id          | int    | 策略ID                                       |
| level                | int    | 告警级别（1-致命，2-预警，3-提醒）                       |
| status               | string | 告警状态（ABNORMAL-异常，RECOVERED-已恢复，CLOSED-已关闭） |
| plugin_id            | str    | 插件ID                                       |
| is_builtin_assign    | bool   | 是否为内置分派组                                   |
| target_key           | string | 目标标识（格式：目标类型\|目标值）                         |
| assignee             | list   | 负责人列表                                      |
| event                | dict   | 关联的事件信息                                    |
| is_shielded          | bool   | 是否已屏蔽                                      |
| is_handled           | bool   | 是否已处理                                      |
| is_ack               | bool   | 是否已确认                                      |
| handle_actions       | list   | 处理动作列表（不包含通知类动作）                           |
| voice_notice_actions | list   | 语音通知动作列表                                   |

#### event 字段说明

| 字段          | 类型     | 描述                   |
|-------------|--------|----------------------|
| id          | str    | 事件文档ID               |
| event_id    | str    | 事件ID                 |
| create_time | string | 事件创建时间               |
| ip          | string | IP地址                 |
| bk_biz_id   | int    | 业务ID                 |
| bk_cloud_id | int    | 云区域ID                |
| target_type | string | 目标类型（如HOST、SERVICE等） |
| target      | string | 目标标识                 |

#### handle_actions 元素字段说明

| 字段                 | 类型     | 描述                                                  |
|--------------------|--------|-----------------------------------------------------|
| status             | string | 处理状态（SUCCESS-成功，FAILURE-失败，RUNNING-执行中，SKIPPED-已跳过） |
| action_plugin_type | string | 处理插件类型（如webhook、job、sops等）                          |

#### voice_notice_actions 元素字段说明

| 字段           | 类型     | 描述                                                  |
|--------------|--------|-----------------------------------------------------|
| status       | string | 通知状态（SUCCESS-成功，FAILURE-失败，RUNNING-执行中，SKIPPED-已跳过） |
| failure_type | string | 失败类型（当status为FAILURE时有值）                            |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "id": "16424876305819838",
        "create_time": "2024-01-01 10:00:00",
        "begin_time": "2024-01-01 10:00:00",
        "end_time": null,
        "bk_biz_id": 2,
        "strategy_id": 123,
        "level": 1,
        "status": "ABNORMAL",
        "plugin_id": "fta-plugin",
        "is_builtin_assign": false,
        "target_key": "host|127.0.0.1",
        "assignee": ["admin", "user1"],
        "event": {
            "id": "event_doc_123",
            "event_id": "16424876305819838",
            "create_time": "2024-01-01 10:00:00",
            "ip": "127.0.0.1",
            "bk_biz_id": 2,
            "bk_cloud_id": 0,
            "target_type": "HOST",
            "target": "127.0.0.1"
        },
        "is_shielded": false,
        "is_handled": true,
        "is_ack": false,
        "handle_actions": [
            {
                "status": "SUCCESS",
                "action_plugin_type": "webhook"
            },
            {
                "status": "RUNNING",
                "action_plugin_type": "job"
            }
        ],
        "voice_notice_actions": [
            {
                "status": "SUCCESS",
                "failure_type": ""
            }
        ]
    }
}
```
