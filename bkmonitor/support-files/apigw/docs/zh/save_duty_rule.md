### 功能描述

保存轮值规则


### 请求参数

| 字段             | 类型        | 必须  | 描述                                   |
|----------------|-----------|-----|--------------------------------------|
| id             | int       | 是   | 告警组ID（没有表示新建）                        |
| bk_biz_id      | int       | 是   | 业务ID                                 |
| name           | string    | 是   | 名称                                   |
| category       | string    | 是   | 轮值类型 `regular(日常值班)` `handoff(交替轮值)` |
| labels         | list[str] | 是   | 规则标签                                 |
| enabled        | bool      | 否   | 是否开启，默认为否                            |
| duty_arranges  | list      | 是   | 轮值人员设置                               |
| effective_time | string    | 是   | 生效时间， 格式 `2022-03-11 00:00:00`       |
| end_time       | string    | 否   | 截止时间， 格式 `2022-03-11 00:00:00`       |

#### `duty_arranges` 数据格式

| 字段             | 类型               | 必须  | 描述                              |
|----------------|------------------|-----|---------------------------------|
| id             | int              | 否   | 轮值ID，保存时有id表示更新，没有id表示新增        |
| need_rotation  | bool             | 否   | 是否需要交接班                         |
| duty_time      | list[object]     | 否   | 工作时间配置，默认为每天 24小时工作             |
| group_type     | string           | 否   | `specified(手动指定)`  `auto(自动分配)` |
| group_number   | int              | 否   | `auto(自动分配)` 情况下每组人数            |
| duty_users     | list[list[user]] | 是   | 值班人员组,  当为自动分组的时候，默认取第一组        |

#### `user` 选项说明

| 字段   | 类型     | 必须  | 描述                |
|------|--------|-----|-------------------|
| id   | string | 是   | 用户英文名或者角色代号       |
| type | string | 是   | `group` or `user` |

#### `duty_time`  内元素选项说明

| 字段              | 类型           | 必须  | 描述                                                                                   |
|-----------------|--------------|-----|--------------------------------------------------------------------------------------|
| is_custom       | bool         | 否   | 是否为自定义类型, 默认为`false`                                                                 |
| work_type       | string       | 是   | 轮值类型，默认 `daily`， 可选项 `daily`，`weekly`, `monthly`, `work_day` `weekend`  `date_range` |
| work_days       | list[int]    | 否   | 工作日期， 选项根据`work_type`, 排列在第一位的表示起始日期                                                 |
| work_date_range | list[string] | 否   | 工作日期范围， 选项根据`work_type`, 格式为["2019-10-01--2019-12-31"]                               |
| work_time_type  | string       | 否   | 工作时间类型 默认 `time_range`  ,可选项`time_range` `datetime_range`                            |
| work_time       | list[string] | 是   | 工作时间段 格式 `time_range`：[`00:00--23:59`]   `datetime_range`：[`01 00:00--02 23:59`]     |
| period_settings | object       | 否   | 自定义周期     {'window_unit': "`day` `hour`",  \"duration\":1}                             |

#### `work_type` 类型对应日期`work_days`选择说明

| 轮值类型    | 对应选项说明                                               |
|---------|------------------------------------------------------|
| daily   | 为空，不需要设置                                             |
| weekly  | 1，2，3，4，5，6，7 代表周一 至 周日， 如有全部选项，则设置为 [1,2,3,4,5,6,7] |
| monthly | 1-31号之间选择，如有全部选项，则设置为 [1,2,3,4,5,6,7...31]           |

#### users 格式说明

| 字段           | 类型     | 描述                   |
|--------------|--------|----------------------|
| id           | string | 角色key或者用户ID          |
| display_name | string | 显示名                  |
| type         | string | 类型，可选项`group`，`user` |
| members      | list   | 对应的人员信息（针对group类型）   |

### 请求参数示例

```json
{
  "id": "00",
  "name": "test",
  "category": "handoff",
  "labels": [],
  "enabled": true,
  "duty_arranges": [
    {
      "id": 264924,
      "duty_time": [
        {
          "work_type": "daily",
          "work_time": [
            "00:00--23:59"
          ],
          "work_days": [
            1,
            2,
            3,
            4,
            5
          ],
          "work_time_type": "time_range"
        }
      ],
      "duty_users": [
        [
          {
            "id": "bk_biz_productor",
            "display_name": "产品人员",
            "logo": "",
            "type": "group",
            "members": []
          },
          {
            "id": "bk_biz_maintainer",
            "display_name": "运维人员",
            "logo": "",
            "type": "group",
            "members": []
          }
        ]
      ],
      "group_type": "auto",
      "group_number": 2
    }
  ],
  "effective_time": "2025-10-15 23:59:59",
  "end_time": "2025-11-30 23:59:59",
  "bk_biz_id": 2
}
```

#### 周期轮值自定义方案
```json
{
            "name": "handoff duty",
            "bk_biz_id": 2,
            "effective_time": "2023-07-25 11:00:00",
            "end_time": "",
            "labels": ["mysql", "redis", "business"],
            "enabled": true,
            "category": "handoff",
            "duty_arranges": [
                {
            "duty_time": [{"work_type": "daily",
                           "work_days": [],
                           "work_time_type": "time_range",
                           "work_time": ["00:00--23:59"],
                           "period_settings": {
                               "window_unit": "day",
                               "duration": 2
                           }
                           }],
            "duty_users": [
                [
                    {
                        "id": "admin",
                        "type": "user"
                    },
                    {
                        "id": "admin1",
                        "type": "user"
                    },
                    {
                        "id": "admin2",
                        "type": "user"
                    }, {
                    "id": "admin3",
                    "type": "user"
                }, {
                    "id": "admin4",
                    "type": "user"
                }, {
                    "id": "admin5",
                    "type": "user"
                }
                ]
            ],
            "group_type": "auto",
            "group_number": 2,
            "backups": []
        }
            ]
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

#### data 字段说明

| 字段              | 类型  | 描述                                       |
| ----------------- | ----- | ------------------------------------------ |
| id                | int   | 规则组ID                                   |
| bk_biz_id         | int   | 业务ID                                     |
| name              | str   | 轮值规则名称                               |
| labels            | list  | 轮值规则标签                               |
| effective_time    | str   | 规则生效时间                               |
| end_time          | str   | 规则结束时间（可为空）                     |
| category          | str   | 类型（regular:常规值班, handoff:交替轮值） |
| enabled           | bool  | 是否开启                                   |
| hash              | str   | 原始配置摘要                               |
| duty_arranges     | list  | 轮值安排列表                               |
| create_time       | str   | 创建时间                                   |
| create_user       | str   | 创建用户                                   |
| update_time       | str   | 更新时间                                   |
| update_user       | str   | 更新用户                                   |
| code_hash         | str   | 代码摘要                                   |
| app               | str   | 应用标识                                   |
| path              | str   | 路径标识                                   |
| snippet           | str   | 代码片段                                   |
| user_groups       | list  | 关联的用户组ID列表                         |
| user_groups_count | int   | 关联的用户组数量                           |
| delete_allowed    | bool  | 是否允许删除                               |
| edit_allowed      | bool  | 是否允许编辑                               |

#### duty_arranges 字段说明

| 字段           | 类型  | 描述                     |
| -------------- | ----- | ------------------------ |
| id             | int   | 轮值安排ID               |
| user_group_id  | int   | 关联的告警组ID           |
| duty_rule_id   | int   | 轮值规则ID               |
| need_rotation  | bool  | 是否轮班                 |
| duty_time      | list  | 轮班时间安排             |
| effective_time | str   | 配置生效时间             |
| handoff_time   | dict  | 轮班交接时间安排         |
| users          | list  | 告警处理值班人员         |
| duty_users     | list  | 轮班用户                 |
| backups        | list  | 备份安排                 |
| order          | int   | 轮班组的顺序             |
| hash           | str   | 原始配置摘要             |
| group_type     | str   | 分组类型（specified/auto） |
| group_number   | int   | 自动分组情况下每组人数   |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "id": 53,
    "bk_biz_id": 2,
    "name": "ooo_test",
    "labels": [],
    "effective_time": "2025-10-15 23:59:59",
    "end_time": "2025-11-30 23:59:59",
    "category": "handoff",
    "enabled": true,
    "hash": "47080de3e73bfbcf67f8cc39d253715b",
    "duty_arranges": [
      {
        "id": 264924,
        "user_group_id": null,
        "duty_rule_id": 53,
        "need_rotation": false,
        "duty_time": [
          {
            "is_custom": false,
            "work_type": "daily",
            "work_days": [
              1,
              2,
              3,
              4,
              5
            ],
            "work_time_type": "time_range",
            "work_time": [
              "00:00--23:59"
            ]
          }
        ],
        "effective_time": null,
        "handoff_time": {},
        "users": [],
        "duty_users": [
          [
            {
              "id": "bk_biz_productor",
              "display_name": "产品人员",
              "logo": "",
              "type": "group",
              "members": []
            },
            {
              "id": "bk_biz_maintainer",
              "display_name": "运维人员",
              "logo": "",
              "type": "group",
              "members": []
            }
          ]
        ],
        "backups": [],
        "order": 1,
        "hash": "c17aa4d60a70460cd85dd96c994de0a3",
        "group_type": "auto",
        "group_number": 2
      }
    ],
    "create_time": "2025-05-29 11:48:23+0800",
    "create_user": "admin",
    "update_time": "2025-10-16 14:55:38+0800",
    "update_user": "admin",
    "code_hash": "",
    "app": "",
    "path": "",
    "snippet": "",
    "user_groups": [
      431
    ],
    "user_groups_count": 1,
    "delete_allowed": false,
    "edit_allowed": true
  }
}
```

