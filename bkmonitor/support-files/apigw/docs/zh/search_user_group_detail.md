### 功能描述

查询告警组

### 请求参数

| 字段 | 类型  | 必选 | 描述    |
|----|-----|----|-------|
| id | int | 是  | 告警组ID |

### 请求参数示例

```json
{
    "id": 77
}
```

### 响应参数

| 字段         | 类型     | 描述        |
|------------|--------|-----------|
| result     | bool   | 请求是否成功    |
| code       | int    | 返回的状态码    |
| message    | string | 描述信息      |
| data       | dict   | 数据        |
| request_id | str    | ESB记录请求ID |

#### data字段说明

| 字段              | 类型        | 描述                    |
|-----------------|-----------|-----------------------|
| id              | int       | 告警组ID                 |
| name            | string    | 名称                    |
| bk_biz_id       | int       | 业务ID                  |
| desc            | string    | 说明                    |
| need_duty       | bool      | 是否轮值                  |
| channels        | list[str] | 通知渠道列表                |
| duty_arranges   | list      | 轮值安排列表                |
| duty_rules      | list[int] | 轮值规则ID列表              |
| duty_rules_info | list      | 轮值规则详细信息              |
| duty_plans      | list      | 值班计划列表                |
| alert_notice    | list      | 告警通知方式                |
| action_notice   | list      | 告警处理通知配置              |
| duty_notice     | dict      | 轮值计划通知                |
| path            | string    | 路径                    |
| timezone        | string    | 时区，默认 Asia/Shanghai   |
| mention_list    | list      | 提醒用户列表                |
| mention_type    | int       | 提醒类型                  |
| users           | list      | 当前值班用户列表              |
| strategy_count  | int       | 关联的告警策略数量             |
| rule_count      | int       | 关联的分派规则数量             |
| delete_allowed  | bool      | 是否可删除                 |
| edit_allowed    | bool      | 是否可编辑                 |
| config_source   | string    | 配置来源，可选项 `UI`, `YAML` |
| update_time     | string    | 更新时间                  |
| update_user     | string    | 更新人                   |
| create_time     | string    | 创建时间                  |
| create_user     | string    | 创建人                   |

#### `duty_notice` 数据格式

| 字段              | 类型   | 描述       |
|-----------------|------|----------|
| plan_notice     | dict | 轮值计划通知配置 |
| personal_notice | dict | 值班人员通知配置 |

##### `plan_notice` 数据格式

| 字段       | 类型        | 描述       |
|----------|-----------|----------|
| enabled  | bool      | 是否发送     |
| period   | dict      | 发送时间配置   |
| days     | int       | 发送多久以后的  |
| chat_ids | list[str] | 企业微信ID列表 |

##### `period` 数据格式

| 字段   | 类型        | 描述                              |
|------|-----------|---------------------------------|
| type | string    | 周期类型，`daily` `weekly` `monthly` |
| date | list[int] | 发送日期，数字表示， `daily`的情况下可为空       |
| time | string    | 交班时间， 格式 `08:00`                |

##### `personal_notice` 数据格式

| 字段         | 类型        | 描述         |
|------------|-----------|------------|
| enabled    | bool      | 是否发送       |
| hours_ago  | int       | 单位小时，值班前多久 |
| duty_rules | list[int] | 指定轮值规则     |

#### `duty_arranges` 数据格式

| 字段             | 类型               | 描述                                   |
|----------------|------------------|--------------------------------------|
| id             | int              | 轮值ID                                 |
| user_group_id  | int              | 告警组ID                                |
| duty_rule_id   | int              | 轮值规则ID                               |
| need_rotation  | bool             | 是否需要交接班                              |
| handoff_time   | object           | 轮班交接时间安排                             |
| effective_time | string           | 生效时间                                 |
| duty_time      | list[object]     | 轮班时间安排                               |
| duty_users     | list[list[user]] | 值班人员组                                |
| users          | list[user]       | 值班人员兼容老接口，不需要轮值的时候可以保留该字段            |
| backups        | list[object]     | 备份安排                                 |
| order          | int              | 轮班组的顺序                               |
| hash           | string           | 原始配置摘要                               |
| group_type     | string           | 分组类型，可选项 `specified`(指定), `auto`(自动) |
| group_number   | int              | 自动分组时每个班次对应的人数                       |

##### `user` 选项说明

| 字段   | 类型     | 描述                |
|------|--------|-------------------|
| id   | string | 用户英文名或者角色代号       |
| type | string | `group` or `user` |

##### `handoff_time` 选项说明

| 字段            | 类型     | 描述               |
|---------------|--------|------------------|
| rotation_type | string | 轮值类型，默认 `daily`  |
| date          | int    | 交班日期             |
| time          | string | 交班时间， 格式 `08:00` |

##### `rotation_type`类型对应日期选择说明

| 轮值类型    | 对应选项说明                                               |
|---------|------------------------------------------------------|
| daily   | 为空，不需要设置                                             |
| weekly  | 1，2，3，4，5，6，7 代表周一 至 周日， 如有全部选项，则设置为 [1,2,3,4,5,6,7] |
| monthly | 1-31号之间选择，如有全部选项，则设置为 [1,2,3,4,5,6,7...31]           |

##### `duty_time`  内元素选项说明

| 字段        | 类型        | 必须 | 描述                                               |
|-----------|-----------|----|--------------------------------------------------|
| work_type | string    | 是  | 轮值类型，默认 `daily`， 可选项 `daily`，`weekly`, `monthly` |
| work_days | list[int] | 否  | 工作日期， 选项根据`work_type`,参考rotation_type的对应日期选项说明   |
| work_time | string    | 是  | 工作时间段 格式 `00:00--23:59`                          |

#### users 格式说明

| 字段           | 类型     | 描述                       |
|--------------|--------|--------------------------|
| id           | string | 角色key或者用户ID              |
| display_name | string | 显示名                      |
| type         | string | 类型，可选项`group`，`user`     |
| members      | list   | 对应的人员信息（仅当type为group时有值） |

#### `duty_plans` 数据格式

| 字段              | 类型     | 描述         |
|-----------------|--------|------------|
| id              | int    | 值班计划ID     |
| user_group_id   | int    | 告警组ID      |
| duty_arrange_id | int    | 轮值安排ID     |
| duty_rule_id    | int    | 轮值规则ID     |
| duty_time       | list   | 工作时间配置     |
| begin_time      | string | 开始时间       |
| end_time        | string | 结束时间       |
| start_time      | string | 开始时间（兼容字段） |
| finished_time   | string | 结束时间（兼容字段） |
| work_times      | list   | 工作时间段列表    |
| users           | list   | 值班人员列表     |
| order           | int    | 顺序         |
| is_active       | bool   | 是否为当前生效的计划 |
| last_send_time  | string | 最后发送通知时间   |

#### `duty_rules_info` 数据格式

| 字段             | 类型     | 描述     |
|----------------|--------|--------|
| id             | int    | 轮值规则ID |
| name           | string | 轮值规则名称 |
| bk_biz_id      | int    | 业务ID   |
| effective_time | string | 生效时间   |
| end_time       | string | 结束时间   |
| enabled        | bool   | 是否启用   |
| category       | string | 分类     |
| update_time    | string | 更新时间   |
| update_user    | string | 更新人    |
| create_time    | string | 创建时间   |
| create_user    | string | 创建人    |

#### mention_list 格式说明

| 字段   | 类型     | 描述                       |
|------|--------|--------------------------|
| id   | string | 通知对象ID，如`all`表示所有人       |
| type | string | 通知对象类别，可选项`group`，`user` |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "id": 69,
        "name": "lunzhi",
        "bk_biz_id": 2,
        "desc": "",
        "need_duty": true,
        "channels": [
            "user",
            "wxwork-bot"
        ],
        "timezone": "Asia/Shanghai",
        "mention_list": [],
        "mention_type": 1,
        "path": "",
        "update_user": "admin",
        "update_time": "2023-07-25 11:48:19+0800",
        "create_user": "admin",
        "create_time": "2023-07-25 11:48:19+0800",
        "duty_arranges": [
            {
                "id": 90,
                "user_group_id": 69,
                "duty_rule_id": null,
                "need_rotation": false,
                "duty_time": [
                    {
                        "work_type": "daily",
                        "work_days": [],
                        "work_time": "00:00--23:59"
                    }
                ],
                "effective_time": "2023-07-25T11:48:00+08:00",
                "handoff_time": {
                    "date": 1,
                    "time": "00:00",
                    "rotation_type": "daily"
                },
                "duty_users": [
                    [
                        {
                            "id": "bk_biz_maintainer",
                            "display_name": "运维人员",
                            "logo": "",
                            "type": "group",
                            "members": []
                        }
                    ]
                ],
                "users": [],
                "backups": [],
                "order": 1,
                "hash": "",
                "group_type": "specified",
                "group_number": 0
            }
        ],
        "duty_rules": [],
        "duty_rules_info": [],
        "alert_notice": [
            {
                "time_range": "00:00:00--23:59:00",
                "notify_config": [
                    {
                        "type": [],
                        "notice_ways": [
                            {
                                "name": "weixin",
                                "receivers": []
                            }
                        ],
                        "level": 3
                    },
                    {
                        "type": [],
                        "notice_ways": [
                            {
                                "name": "weixin",
                                "receivers": []
                            }
                        ],
                        "level": 2
                    },
                    {
                        "type": [],
                        "notice_ways": [
                            {
                                "name": "weixin",
                                "receivers": []
                            }
                        ],
                        "level": 1
                    }
                ]
            }
        ],
        "action_notice": [
            {
                "time_range": "00:00:00--23:59:00",
                "notify_config": [
                    {
                        "type": [],
                        "notice_ways": [
                            {
                                "name": "weixin",
                                "receivers": []
                            }
                        ],
                        "phase": 3
                    },
                    {
                        "type": [],
                        "notice_ways": [
                            {
                                "name": "weixin",
                                "receivers": []
                            }
                        ],
                        "phase": 2
                    },
                    {
                        "type": [],
                        "notice_ways": [
                            {
                                "name": "weixin",
                                "receivers": []
                            }
                        ],
                        "phase": 1
                    }
                ]
            }
        ],
        "duty_notice": {
            "plan_notice": {
                "enabled": false,
                "days": 1,
                "chat_ids": []
            },
            "personal_notice": {
                "enabled": false,
                "hours_ago": 1,
                "duty_rules": []
            }
        },
        "users": [],
        "strategy_count": 1,
        "rule_count": 0,
        "delete_allowed": false,
        "edit_allowed": true,
        "config_source": "UI",
        "duty_plans": [
            {
                "id": 1,
                "user_group_id": 69,
                "duty_arrange_id": 90,
                "duty_rule_id": null,
                "duty_time": [
                    {
                        "work_days": [],
                        "work_time": "00:00--23:59",
                        "work_type": "daily"
                    }
                ],
                "begin_time": "2023-07-25 11:49:00+0800",
                "end_time": null,
                "users": [
                    {
                        "id": "bk_biz_maintainer",
                        "display_name": "运维人员",
                        "logo": "",
                        "type": "group",
                        "members": []
                    }
                ],
                "order": 1,
                "is_active": true
            }
        ]
    },
    "request_id": "496391f5c8a247709dc5a7184ddf9ab5"
}
```

