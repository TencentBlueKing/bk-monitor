### 功能描述

保存告警组


### 请求参数

| 字段            | 类型                 | 必须  | 描述                                           |
|---------------|--------------------|-----|-------------------------------------------------|
| id            | int                | 否   | 告警组ID（没有表示新建，有表示更新）                                |
| bk_biz_id     | int                | 是   | 业务ID                                         |
| name          | string             | 是   | 名称                                           |
| timezone      | string             | 否   | 时区，默认`Asia/Shanghai`                                   |
| need_duty     | bool               | 否   | 是否轮值，默认`false`                                         |
| channels      | list[str]          | 否   | 通知渠道 可选项 `user(内部用户)`, `wxwork-bot(企业微信机器人)` |
| desc          | string             | 否   | 说明                                           |
| alert_notice  | list               | 是   | 告警通知方式                                       |
| action_notice | list               | 是   | 告警处理通知配置                                     |
| duty_arranges | list[duty_arrange] | 否   | 轮值安排列表                                 |
| duty_rules    | list[int]          | 否   | 轮值对应的规则组ID列表，need_duty 情况下必填                     |
| duty_notice   | dict               | 否   | 轮值相关的通知设置                                    |
| path          | string             | 否   | 路径                                    |
| mention_list  | list[user]         | 否   | 提醒用户列表                                    |
| mention_type  | int                | 否   | 提醒类型                                    |

#### `alert_notice` 数据格式

| 字段            | 类型                        | 必须  | 描述     |
|---------------|---------------------------|-----|--------|
| time_range    | string                    | 是   | 生效时间范围 |
| notify_config | list[alert_notice_config] | 是   | 生效时间范围 |

#### `action_notice` 数据格式

| 字段            | 类型                         | 必须  | 描述     |
|---------------|----------------------------|-----|--------|
| time_range    | string                     | 是   | 生效时间范围 |
| notify_config | list[action_notice_config] | 是   | 生效时间范围 |

#### `alert_notice_config` 数据格式

| 字段          | 类型               | 必须  | 描述                |
|-------------|------------------|-----|-------------------|
| level       | int              | 是   | 1(致命)，2(预警)，3(提醒) |
| type        | list[str]        | 否   | 通知类型（兼容字段），默认为空列表 |
| chatid      | string           | 否   | 企业微信群ID（兼容字段） |
| notice_ways | list[notice_way] | 否   | 通知方式列表，默认为空列表 |

#### `action_notice_config` 数据格式

| 字段          | 类型               | 必须  | 描述                   |
|-------------|------------------|-----|----------------------|
| phase       | int              | 是   | 1(失败时)，2(成功时)，3(执行前) |
| type        | list[str]        | 否   | 通知类型（兼容字段），默认为空列表 |
| chatid      | string           | 否   | 企业微信群ID（兼容字段） |
| notice_ways | list[notice_way] | 否   | 通知方式列表，默认为空列表 |

#### `notice_way` 数据格式

| 字段 | 类型 | 必须 | 描述 |
|------------|--------|--|--------------------------------|
| name | string | 是 | 通知方式名称，可选项：`weixin（微信）`, `mail(邮件)`, `sms(短信)`, `voice(语音通知)`, `wxwork-bot(企业微信机器人)` 等 |
| receivers | list[str] | 否 | 通知接收人员 |

#### `duty_notice` 数据格式

| 字段              | 类型   | 必须  | 描述       |
|-----------------|------|-----|----------|
| plan_notice     | dict | 否   | 轮值计划通知配置 |
| personal_notice | dict | 否   | 值班人员通知配置 |
| hit_first_duty  | bool | 否   | 是否命中第一班，默认true |

#### `plan_notice` 数据格式

| 字段       | 类型        | 必须  | 描述                              |
|----------|-----------|-----|---------------------------------|
| enabled  | bool      | 否   | 是否发送，默认true                            |
| days     | int       | 是   | 发送多久以后的                         |
| chat_ids | list[str] | 是   | 企业微信ID列表                        |
| type     | string    | 是   | 周期类型，`daily` `weekly` `monthly` |
| date     | int       | 否   | 发送日期，数字表示， `daily`的情况下可为空       |
| time     | string    | 是   | 交班时间， 格式 `08:00`                |

#### `personal_notice` 数据格式

| 字段         | 类型        | 必须  | 描述         |
|------------|-----------|-----|------------|
| enabled    | bool      | 否   | 是否发送，默认true       |
| hours_ago  | int       | 是   | 单位小时，值班前多久 |
| duty_rules | list[int] | 否   | 指定轮值规则，默认为空列表     |

#### `duty_arranges` 数据格式

| 字段           | 类型             | 必须 | 描述                                               |
| -------------- | ---------------- | ---- | -------------------------------------------------- |
| id             | int              | 否   | 轮值ID，保存时有id表示更新，没有id表示新增         |
| user_group_id  | int              | 否   | 用户组ID                                           |
| duty_rule_id   | int              | 否   | 轮值规则ID                                           |
| need_rotation  | bool             | 否   | 是否需要交接班，默认false                                     |
| handoff_time   | object           | 否   | 轮班交接时间安排，`need_rotation` 为`True`时此字段必填               |
| effective_time | string           | 否   | 生效时间， 格式 `2022-03-11 00:00:00`              |
| duty_time      | list[duty_time_item]     | 否   | 工作时间配置，默认为每天 24小时工作                |
| duty_users     | list[list[user]] | 否   | 值班人员组                                         |
| users          | list[user]       | 否   | 值班人员兼容老接口，不需要轮值的时候可以保留该字段 |
| backups        | list[backup_item]             | 否   | 备份安排列表                                           |
| order          | int              | 否   | 轮班组的顺序，默认0                                       |
| group_type     | string           | 否   | 分组类型，可选项 `specified`(指定), `auto`(自动)，默认`specified` |
| group_number   | int              | 否   | 自动分组时每个班次对应的人数                      |
| hash           | string           | 否   | 原始配置摘要，最大64字符，默认为空字符串                      |

#### `handoff_time` 数据格式

| 字段          | 类型   | 必须 | 描述                                                         |
| ------------- | ------ | ---- | ------------------------------------------------------------ |
| rotation_type | string | 是   | 轮值类型，可选项 `daily`(每天), `weekly`(每周), `monthly`(每月) |
| date          | int    | 否   | 交接日期，`weekly`时为1-7(周一至周日)，`monthly`时为1-31，`daily`时不需要 |
| time          | string | 是   | 交接时间点，格式 `HH:MM`，如 `08:00`                         |

#### `duty_time_item` 数据格式

| 字段            | 类型        | 必须 | 描述                                                         |
| --------------- | ----------- | ---- | ------------------------------------------------------------ |
| is_custom       | bool        | 否   | 是否自定义，默认false                                        |
| work_type       | string      | 是   | 工作类型，可选项 `daily`(每天), `weekly`(每周), `monthly`(每月) |
| work_days       | list[int]   | 否   | 工作日期，`weekly`时为1-7(周一至周日)，`monthly`时为1-31     |
| work_date_range | list[str]   | 否   | 工作日期范围                                                 |
| work_time_type  | string      | 否   | 工作时间类型，可选项 `time_range`(时间范围), `datetime_range`(日期时间范围)，默认`time_range` |
| work_time       | list[str]   | 是   | 工作时间段列表，格式 `HH:MM--HH:MM`(如`00:00--23:59`)或 `DD HH:MM--DD HH:MM`(如`01 00:00--01 23:59`) |
| period_settings | dict        | 否   | 周期分配设置                                                 |

#### `backup_item` 数据格式

| 字段             | 类型             | 必须 | 描述                                     |
| ---------------- | ---------------- |----| ---------------------------------------- |
| users            | list[user]       | 是  | 备份值班人员列表                         |
| begin_time       | string           | 是  | 备份开始时间，格式 `2022-03-11 00:00:00` |
| end_time         | string           | 是  | 备份结束时间，格式 `2022-03-11 00:00:00` |
| duty_time        | duty_time_item   | 是  | 工作时间段配置                           |
| exclude_settings | list[exclude_setting] | 是  | 排除时间段列表                           |

#### `exclude_setting` 数据格式

| 字段 | 类型   | 必须 | 描述                                   |
| ---- | ------ | ---- | -------------------------------------- |
| date | string | 是   | 排除日期，格式 `YYYY-MM-DD`，如 `2023-03-21` |
| time | string | 是   | 排除时间段，格式 `HH:MM--HH:MM`，如 `10:00--18:00` |

#### `user` 格式说明

| 字段           | 类型     | 必须 | 描述                   |
|--------------|--------|------|----------------------|
| id           | string | 是   | 角色key或者用户ID，通知对象ID          |
| type         | string | 是   | 类型，可选项`group`(用户组)，`user`(用户) |
| display_name | string | 否   | 显示名                  |
| logo         | string | 否   | 头像                  |
| members      | list   | 否   | 对应的人员信息（针对group类型）   |

##### members 元素格式说明

| 字段           | 类型     | 描述                   |
|--------------|--------|----------------------|
| id           | string | 用户ID          |
| display_name | string | 用户显示名                  |

### 请求参数示例

#### 示例1：基础轮值配置（每日轮值）

```json
{
  "id": 69,
  "name": "运维值班组",
  "bk_biz_id": 2,
  "desc": "运维团队7x24小时值班组",
  "timezone": "Asia/Shanghai",
  "need_duty": true,
  "channels": [
    "user",
    "wxwork-bot"
  ],
  "path": "/ops/duty",
  "mention_list": [
    {
      "id": "admin",
      "type": "user",
      "display_name": "管理员"
    }
  ],
  "mention_type": 1,
  "duty_arranges": [
    {
      "id": 90,
      "user_group_id": 69,
      "need_rotation": true,
      "effective_time": "2023-07-25 00:00:00",
      "handoff_time": {
        "rotation_type": "daily",
        "date": 1,
        "time": "09:00"
      },
      "duty_time": [
        {
          "is_custom": false,
          "work_type": "daily",
          "work_days": [],
          "work_time_type": "time_range",
          "work_time": ["00:00--23:59"]
        }
      ],
      "duty_users": [
        [
          {
            "id": "user001",
            "type": "user",
            "display_name": "张三",
            "logo": ""
          }
        ],
        [
          {
            "id": "user002",
            "type": "user",
            "display_name": "李四",
            "logo": ""
          }
        ]
      ],
      "backups": [],
      "order": 1,
      "group_type": "specified",
      "group_number": 1
    }
  ],
  "alert_notice": [
    {
      "time_range": "00:00:00--23:59:59",
      "notify_config": [
        {
          "level": 1,
          "type": [],
          "notice_ways": [
            {
              "name": "weixin",
              "receivers": []
            },
            {
              "name": "mail",
              "receivers": []
            },
            {
              "name": "sms",
              "receivers": []
            }
          ]
        },
        {
          "level": 2,
          "type": [],
          "notice_ways": [
            {
              "name": "weixin",
              "receivers": []
            },
            {
              "name": "mail",
              "receivers": []
            }
          ]
        },
        {
          "level": 3,
          "type": [],
          "notice_ways": [
            {
              "name": "weixin",
              "receivers": []
            }
          ]
        }
      ]
    }
  ],
  "action_notice": [
    {
      "time_range": "00:00:00--23:59:59",
      "notify_config": [
        {
          "phase": 3,
          "type": [],
          "notice_ways": [
            {
              "name": "weixin",
              "receivers": []
            }
          ]
        },
        {
          "phase": 2,
          "type": [],
          "notice_ways": [
            {
              "name": "weixin",
              "receivers": []
            }
          ]
        },
        {
          "phase": 1,
          "type": [],
          "notice_ways": [
            {
              "name": "weixin",
              "receivers": []
            }
          ]
        }
      ]
    }
  ],
  "duty_notice": {
    "plan_notice": {
      "enabled": true,
      "days": 7,
      "chat_ids": ["ww123456"],
      "type": "weekly",
      "date": 1,
      "time": "09:00"
    },
    "personal_notice": {
      "enabled": true,
      "hours_ago": 2,
      "duty_rules": []
    },
    "hit_first_duty": true
  }
}
```

#### 示例2：复杂轮值配置（包含备份安排和排除时间）

```json
{
  "name": "开发值班组",
  "bk_biz_id": 2,
  "desc": "开发团队工作日值班组",
  "timezone": "Asia/Shanghai",
  "need_duty": true,
  "channels": ["user"],
  "duty_arranges": [
    {
      "need_rotation": true,
      "effective_time": "2023-08-01 00:00:00",
      "handoff_time": {
        "rotation_type": "weekly",
        "date": 1,
        "time": "09:00"
      },
      "duty_time": [
        {
          "is_custom": true,
          "work_type": "weekly",
          "work_days": [1, 2, 3, 4, 5],
          "work_time_type": "time_range",
          "work_time": ["09:00--18:00"]
        }
      ],
      "duty_users": [
        [
          {
            "id": "bk_biz_developer",
            "type": "group",
            "display_name": "开发人员",
            "logo": "",
            "members": [
              {
                "id": "dev001",
                "display_name": "开发A"
              },
              {
                "id": "dev002",
                "display_name": "开发B"
              }
            ]
          }
        ]
      ],
      "backups": [
        {
          "users": [
            {
              "id": "backup001",
              "type": "user",
              "display_name": "备份值班员",
              "logo": ""
            }
          ],
          "begin_time": "2023-08-15 00:00:00",
          "end_time": "2023-08-20 23:59:59",
          "duty_time": {
            "is_custom": false,
            "work_type": "daily",
            "work_days": [],
            "work_time_type": "time_range",
            "work_time": ["00:00--23:59"]
          },
          "exclude_settings": [
            {
              "date": "2023-08-16",
              "time": "12:00--14:00"
            },
            {
              "date": "2023-08-17",
              "time": "12:00--14:00"
            }
          ]
        }
      ],
      "order": 1,
      "group_type": "specified"
    }
  ],
  "alert_notice": [
    {
      "time_range": "00:00:00--23:59:59",
      "notify_config": [
        {
          "level": 1,
          "notice_ways": [
            {
              "name": "weixin",
              "receivers": []
            },
            {
              "name": "wxwork-bot",
              "receivers": ["ww123456"]
            }
          ]
        },
        {
          "level": 2,
          "notice_ways": [
            {
              "name": "weixin",
              "receivers": []
            }
          ]
        },
        {
          "level": 3,
          "notice_ways": [
            {
              "name": "mail",
              "receivers": []
            }
          ]
        }
      ]
    }
  ],
  "action_notice": [
    {
      "time_range": "00:00:00--23:59:59",
      "notify_config": [
        {
          "phase": 3,
          "notice_ways": [
            {
              "name": "weixin",
              "receivers": []
            }
          ]
        },
        {
          "phase": 2,
          "notice_ways": [
            {
              "name": "mail",
              "receivers": []
            }
          ]
        },
        {
          "phase": 1,
          "notice_ways": [
            {
              "name": "weixin",
              "receivers": []
            }
          ]
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
      "enabled": true,
      "hours_ago": 1,
      "duty_rules": []
    },
    "hit_first_duty": true
  },
  "duty_rules": []
}
```

### 响应参数

| 字段       | 类型   | 描述          |
| ---------- | ------ | ------------- |
| result     | bool   | 请求是否成功  |
| code       | int    | 返回的状态码  |
| message    | string | 描述信息      |
| data       | dict   | 数据          |
| request_id | str    | ESB记录请求ID |

#### data字段说明

| 字段           | 类型      | 描述                                                         |
| -------------- | --------- | ------------------------------------------------------------ |
| id             | int       | 告警组ID                                                     |
| name           | string    | 名称                                                         |
| bk_biz_id      | int       | 业务ID                                                       |
| desc           | string    | 说明                                                         |
| need_duty      | bool      | 是否轮值                                                     |
| channels       | list[str] | 通知渠道 可选项 `user(内部用户)`, `wxwork-bot(企业微信机器人)` |
| timezone       | string    | 时区，默认 Asia/Shanghai                                     |
| mention_list   | list      | 提醒用户列表                                                 |
| mention_type   | int       | 提醒类型                                                     |
| path           | string    | 路径                                                         |
| duty_rules     | list[int] | 轮值规则ID列表                                                     |
| duty_arranges  | list      | 通知接收人员                                                 |
| alert_notice   | list      | 告警通知方式                                                 |
| action_notice  | list      | 告警处理通知配置                                             |
| duty_notice    | dict      | 轮值计划通知                                                 |
| users          | list      | 用户列表                                                     |
| duty_plans     | list      | 轮值计划                                                     |
| strategy_count | int       | 关联的告警策略数量                                           |
| rule_count     | int       | 关联的分派规则数量                                           |
| delete_allowed | bool      | 是否可删除                                                   |
| edit_allowed   | bool      | 是否可编辑                                                   |
| config_source  | string    | 配置来源，可选项 `UI`, `YAML`                                                     |
| update_time    | string    | 更新时间                                                     |
| update_user    | string    | 更新人                                                       |
| create_time    | string    | 创建时间                                                     |
| create_user    | string    | 创建人                                                       |

#### `duty_notice` 数据格式

| 字段            | 类型 | 描述             |
| --------------- | ---- | ---------------- |
| plan_notice     | dict | 轮值计划通知配置 |
| personal_notice | dict | 值班人员通知配置 |
| hit_first_duty  | bool | 是否命中第一班   |

#### `plan_notice` 数据格式

| 字段     | 类型      | 描述                                       |
| -------- | --------- | ------------------------------------------ |
| enabled  | bool      | 是否发送                                   |
| days     | int       | 发送多久以后的                             |
| chat_ids | list[str] | 企业微信ID列表                             |
| type     | string    | 周期类型，`daily` `weekly` `monthly`       |
| date     | int       | 发送日期，数字表示， `daily`的情况下可为空 |
| time     | string    | 交班时间， 格式 `08:00`                    |

#### `personal_notice` 数据格式

| 字段       | 类型      | 描述                 |
| ---------- | --------- | -------------------- |
| enabled    | bool      | 是否发送             |
| hours_ago  | int       | 单位小时，值班前多久 |
| duty_rules | list[int] | 指定轮值规则         |

#### `duty_arranges` 数据格式

| 字段           | 类型             | 描述                                               |
| -------------- | ---------------- | -------------------------------------------------- |
| id             | int              | 轮值ID，保存时有id表示更新，没有id表示新增         |
| user_group_id  | int              | 用户组ID                                           |
| duty_rule_id   | int              | 轮值规则ID                                           |
| need_rotation  | bool             | 是否需要交接班                                     |
| handoff_time   | object           | 轮班交接时间安排，`need_rotation` 为`True`时此字段必填               |
| effective_time | string           | 生效时间， 格式 `2022-03-11 00:00:00`              |
| duty_time      | list[object]     | 工作时间配置，默认为每天 24小时工作                |
| duty_users     | list[list[user]] | 值班人员组                                         |
| users          | list[user]       | 值班人员兼容老接口，不需要轮值的时候可以保留该字段 |
| backups        | list             | 备份安排                                           |
| order          | int              | 轮班组的顺序                                       |
| hash           | string           | 原始配置摘要                                       |
| group_type     | string           | 分组类型，可选项 `specified`(指定), `auto`(自动)  |
| group_number   | int              | 自动分组时每个班次对应的人数                       |

> **注意**: `handoff_time`、`duty_time`、`backups` 等字段的详细结构请参考请求参数部分的说明。

#### `user` 选项说明

| 字段         | 类型   | 描述                      |
| ------------ | ------ | ------------------------- |
| id           | string | 用户英文名或者角色代号    |
| type         | string | `group` or `user`         |
| display_name | string | 显示名                    |
| logo         | string | 头像                      |
| members      | list   | 成员列表（针对group类型） |

#### `handoff_time` 选项说明

| 字段          | 类型   | 描述                    |
| ------------- | ------ | ----------------------- |
| rotation_type | string | 轮值类型，默认 `daily`  |
| date          | int    | 交班日期                |
| time          | string | 交班时间， 格式 `08:00` |

#### `rotation_type`类型对应日期选择说明

| 轮值类型 | 对应选项说明                                                 |
| -------- | ------------------------------------------------------------ |
| daily    | 为空，不需要设置                                             |
| weekly   | 1，2，3，4，5，6，7 代表周一 至 周日， 如有全部选项，则设置为 [1,2,3,4,5,6,7] |
| monthly  | 1-31号之间选择，如有全部选项，则设置为 [1,2,3,4,5,6,7...31]  |

#### `duty_time`  内元素选项说明

| 字段      | 类型      | 描述                                                         |
| --------- | --------- | ------------------------------------------------------------ |
| work_type | string    | 轮值类型，默认 `daily`， 可选项 `daily`，`weekly`, `monthly` |
| work_days | list[int] | 工作日期， 选项根据`work_type`,参考rotation_type的对应日期选项说明 |
| work_time | string    | 工作时间段 格式 `00:00--23:59`                               |

#### `alert_notice` 数据格式

| 字段          | 类型                      | 描述         |
| ------------- | ------------------------- | ------------ |
| time_range    | string                    | 生效时间范围 |
| notify_config | list[alert_notice_config] | 通知配置     |

#### `action_notice` 数据格式

| 字段          | 类型                       | 描述         |
| ------------- | -------------------------- | ------------ |
| time_range    | string                     | 生效时间范围 |
| notify_config | list[action_notice_config] | 通知配置     |

#### `notify_config` 数据格式

| 字段        | 类型             | 描述     |
| ----------- | ---------------- | -------- |
| type        | list             | 通知类型（兼容字段） |
| notice_ways | list[notice_way] | 通知方式 |
| level       | int              | 告警级别（alert_notice中使用） |
| phase       | int              | 处理阶段（action_notice中使用） |

#### `notice_way` 数据格式

| 字段      | 类型      | 描述         |
| --------- | --------- | ------------ |
| name      | string    | 通知方式名称 |
| receivers | list[str] | 接收人列表   |

#### `duty_plans` 数据格式

| 字段              | 类型        | 描述                                  |
|-----------------|-----------|-------------------------------------|
| id              | int       | 值班计划ID                              |
| user_group_id   | int       | 告警组ID                               |
| duty_arrange_id | int       | 轮值安排ID                              |
| duty_rule_id    | int       | 轮值规则ID                              |
| duty_time       | list      | 工作时间配置                              |
| begin_time      | string    | 开始时间                                |
| end_time        | string    | 结束时间                                |
| users           | list      | 值班人员列表                              |
| order           | int       | 顺序                                  |
| is_active       | bool      | 是否为当前生效的计划                          |

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




