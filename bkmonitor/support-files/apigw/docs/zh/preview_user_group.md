### 功能描述

预览告警组的排班计划

该接口用于预览指定告警组在未来一段时间内的轮值排班情况，支持两种数据源：

- **DB（数据库）**：预览已保存的告警组的排班计划
- **API（接口参数）**：预览通过接口参数传入的轮值规则配置的排班计划

**预览逻辑说明：**

1. 对于已保存的告警组（source_type=DB），会基于告警组关联的轮值规则和历史快照生成预览
2. 对于临时配置（source_type=API），会基于传入的轮值规则ID生成预览
3. 预览结果包含指定时间范围内的所有排班计划，包括值班人员、工作时间段等信息

### 请求参数

| 字段          | 类型     | 必须 | 描述                                                     |
|-------------|--------|----|--------------------------------------------------------|
| bk_biz_id   | int    | 是  | 业务ID                                                   |
| id          | int    | 否  | 告警组ID（source_type为DB时必填）                               |
| begin_time  | string | 否  | 预览生效开始时间，格式：`YYYY-MM-DD HH:MM:SS`，不传则使用当前时间            |
| days        | int    | 否  | 预览天数，默认30天，表示从begin_time开始预览多少天的排班计划                   |
| timezone    | string | 否  | 时区，默认 `Asia/Shanghai`                                  |
| source_type | string | 否  | 数据来源类型，可选值：`DB`（数据库存储内容）、`API`（接口参数），默认 `API`          |
| config      | dict   | 否  | 数据来源类型为API时必填，格式为 `{"duty_rules": [1,2,3]}`，包含轮值规则ID列表 |

#### 请求参数说明

- **source_type = DB**：从数据库读取已保存的告警组配置进行预览
    - 必须提供 `id` 参数（告警组ID）
    - 系统会读取该告警组关联的所有轮值规则和历史快照

- **source_type = API**：使用接口参数中的配置进行预览
    - 必须提供 `config` 参数
    - `config.duty_rules` 为轮值规则ID列表，支持多个轮值规则

- **begin_time**：预览的起始时间
    - 不传则使用当前时间
    - 传入的时间会根据 `timezone` 参数进行时区转换

- **days**：预览的天数范围
    - 默认30天
    - 实际预览结束时间 = begin_time + days

### 请求参数示例

#### 示例1：预览已保存的告警组排班计划（source_type=DB）

```json
{
  "bk_biz_id": 2,
  "source_type": "DB",
  "id": 123,
  "begin_time": "2023-12-01 00:00:00",
  "days": 7,
  "timezone": "Asia/Shanghai"
}
```

#### 示例2：预览指定轮值规则的排班计划（source_type=API）

```json
{
  "bk_biz_id": 2,
  "source_type": "API",
  "begin_time": "2023-12-01 00:00:00",
  "days": 30,
  "timezone": "Asia/Shanghai",
  "config": {
    "duty_rules": [2, 3, 5]
  }
}
```

#### 示例3：使用默认参数预览（使用当前时间，预览30天）

```json
{
  "bk_biz_id": 2,
  "source_type": "DB",
  "id": 123
}
```

### 响应参数

| 字段      | 类型     | 描述         |
|---------|--------|------------|
| result  | bool   | 请求是否成功     |
| code    | int    | 返回的状态码     |
| message | string | 描述信息       |
| data    | list   | 轮值规则预览数据列表 |

#### data 字段说明

data 是一个数组，每个元素代表一个轮值规则的排班预览结果

| 字段         | 类型   | 描述         |
|------------|------|------------|
| rule_id    | int  | 轮值规则ID     |
| duty_plans | list | 该规则的轮值计划列表 |

#### duty_plans 字段说明

duty_plans 是一个数组，每个元素代表一个具体的排班计划

| 字段            | 类型     | 描述                                |
|---------------|--------|-----------------------------------|
| id            | int    | 轮班计划ID（已保存的计划才有此字段）               |
| order         | int    | 轮班组的顺序                            |
| user_index    | int    | 轮班用户的分组索引                         |
| users         | list   | 值班人员列表                            |
| work_times    | list   | 工作时间段列表                           |
| start_time    | string | 轮班生效开始时间，格式：`YYYY-MM-DD HH:MM:SS` |
| finished_time | string | 轮班生效结束时间，格式：`YYYY-MM-DD HH:MM:SS` |
| is_active     | bool   | 是否当前生效状态                          |

#### users 字段说明

users 是一个数组，每个元素代表一个值班人员或值班组

| 字段           | 类型     | 描述                               |
|--------------|--------|----------------------------------|
| id           | string | 用户ID（type=user）或角色代号（type=group） |
| display_name | string | 显示名称                             |
| type         | string | 类型，可选值：`user`（用户）、`group`（组）     |
| logo         | string | 头像URL或logo                       |
| members      | list   | 组成员信息（仅当type=group时存在）           |

#### members 字段说明（仅当 users.type=group 时存在）

| 字段           | 类型     | 描述   |
|--------------|--------|------|
| id           | string | 用户ID |
| display_name | string | 显示名称 |

#### work_times 字段说明

work_times 是一个数组，每个元素代表一个工作时间段

| 字段         | 类型     | 描述                            |
|------------|--------|-------------------------------|
| start_time | string | 开始时间，格式：`YYYY-MM-DD HH:MM:SS` |
| end_time   | string | 结束时间，格式：`YYYY-MM-DD HH:MM:SS` |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "rule_id": 2,
      "duty_plans": [
        {
          "id": 456,
          "order": 1,
          "user_index": 0,
          "users": [
            {
              "id": "admin",
              "display_name": "管理员",
              "type": "user",
              "logo": "",
              "members": []
            }
          ],
          "work_times": [
            {
              "start_time": "2023-12-01 00:00:00",
              "end_time": "2023-12-01 23:59:59"
            }
          ],
          "start_time": "2023-12-01 00:00:00",
          "finished_time": "2023-12-01 23:59:59",
          "is_active": true
        },
        {
          "id": 457,
          "order": 1,
          "user_index": 1,
          "users": [
            {
              "id": "operator",
              "display_name": "运维人员",
              "type": "user",
              "logo": "",
              "members": []
            }
          ],
          "work_times": [
            {
              "start_time": "2023-12-02 00:00:00",
              "end_time": "2023-12-02 23:59:59"
            }
          ],
          "start_time": "2023-12-02 00:00:00",
          "finished_time": "2023-12-02 23:59:59",
          "is_active": false
        }
      ]
    },
    {
      "rule_id": 3,
      "duty_plans": [
        {
          "id": 458,
          "order": 1,
          "user_index": 0,
          "users": [
            {
              "id": "bk_biz_maintainer",
              "display_name": "运维人员",
              "type": "group",
              "logo": "",
              "members": [
                {
                  "id": "admin",
                  "display_name": "管理员"
                },
                {
                  "id": "operator",
                  "display_name": "运维"
                }
              ]
            }
          ],
          "work_times": [
            {
              "start_time": "2023-12-01 09:00:00",
              "end_time": "2023-12-01 18:00:00"
            }
          ],
          "start_time": "2023-12-01 09:00:00",
          "finished_time": "2023-12-01 18:00:00",
          "is_active": true
        }
      ]
    }
  ]
}
```
