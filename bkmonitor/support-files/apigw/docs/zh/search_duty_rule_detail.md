### 功能描述

查询单个轮值规则的详情


### 请求参数

| 字段  | 类型   | 必选  | 描述    |
|-----|------|-----|-------|
| id  | int | 是   | 轮值规则ID |

### 请求参数示例

```json
{
  "id": 53
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

| 字段              | 类型        | 描述                                       |
| ----------------- | ----------- | ------------------------------------------ |
| id                | int         | 轮值规则ID                                   |
| bk_biz_id         | int         | 业务ID                                     |
| name              | str         | 轮值规则名称                               |
| labels            | list[str]   | 轮值规则标签                               |
| effective_time    | str         | 规则生效时间，格式 `2022-03-11 00:00:00`                               |
| end_time          | str         | 规则结束时间（可为空），格式 `2022-03-11 00:00:00`                     |
| category          | str         | 类型（regular:常规值班, handoff:交替轮值） |
| enabled           | bool        | 是否开启                                   |
| hash              | str         | 原始配置摘要                               |
| duty_arranges     | list[dict]  | 轮值安排列表                               |
| create_time       | str         | 创建时间                                   |
| create_user       | str         | 创建用户                                   |
| update_time       | str         | 更新时间                                   |
| update_user       | str         | 更新用户                                   |
| code_hash         | str         | 代码摘要                                   |
| app               | str         | 应用标识                                   |
| path              | str         | 路径标识                                   |
| snippet           | str         | 代码片段                                   |
| user_groups       | list[int]   | 关联的用户组ID列表                         |
| user_groups_count | int         | 关联的用户组数量                           |
| delete_allowed    | bool        | 是否允许删除（当user_groups_count为0时可删除）                               |
| edit_allowed      | bool        | 是否允许编辑（当bk_biz_id不为0时可编辑）                               |

#### duty_arranges 字段说明

| 字段           | 类型               | 描述                     |
| -------------- | ------------------ | ------------------------ |
| id             | int                | 轮值安排ID               |
| user_group_id  | int                | 关联的告警组ID（可为null）           |
| duty_rule_id   | int                | 轮值规则ID（可为null）               |
| need_rotation  | bool               | 是否轮班                 |
| duty_time      | list[dict]         | 轮班时间安排             |
| effective_time | str                | 配置生效时间（可为null）             |
| handoff_time   | dict               | 轮班交接时间安排         |
| users          | list[dict]         | 告警处理值班人员         |
| duty_users     | list[list[dict]]   | 轮班用户                 |
| backups        | list[dict]         | 备份安排                 |
| order          | int                | 轮班组的顺序             |
| hash           | str                | 原始配置摘要             |
| group_type     | str                | 分组类型（specified:手动指定/auto:自动分配） |
| group_number   | int                | 自动分组情况下每组人数   |

#### duty_time 字段说明

| 字段              | 类型           | 描述                                                                                   |
|-----------------|--------------|--------------------------------------------------------------------------------------|
| is_custom       | bool         | 是否为自定义类型, 默认为`false`                                                                 |
| work_type       | string       | 轮值类型，默认 `daily`， 可选项 `daily`，`weekly`, `monthly`, `work_day` `weekend`  `date_range` |
| work_days       | list[int]    | 工作日期， 选项根据`work_type`                                                 |
| work_date_range | list[string] | 工作日期范围， 选项根据`work_type`, 格式为["2019-10-01--2019-12-31"]                               |
| work_time_type  | string       | 工作时间类型 默认 `time_range`  ,可选项`time_range` `datetime_range`                            |
| work_time       | list[string] | 工作时间段 格式 `time_range`：[`00:00--23:59`]   `datetime_range`：[`01 00:00--02 23:59`]     |
| period_settings | dict         | 自定义周期     {'window_unit': "`day` `hour`",  "duration":1}                             |

#### handoff_time 字段说明

| 字段            | 类型     | 描述               |
|---------------|--------|------------------|
| rotation_type | string | 轮值类型，默认 `daily`  |
| date          | int    | 交班日期             |
| time          | string | 交班时间， 格式 `08:00` |

#### users/duty_users 字段说明

| 字段           | 类型     | 描述                   |
|--------------|--------|----------------------|
| id           | string | 角色key或者用户ID          |
| display_name | string | 显示名                  |
| type         | string | 类型，可选项`group`，`user` |
| logo         | string | 图标                   |
| members      | list   | 对应的人员信息（针对group类型）   |

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
  },
  "request_id": "496391f5c8a247709dc5a7184ddf9ab5"
}
```
