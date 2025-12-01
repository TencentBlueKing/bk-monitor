### 功能描述

保存轮值规则


### 请求参数

| 字段          | 类型     | 必须 | 描述                                            |
|-------------|--------|--|-----------------------------------------------|
| id          | int    | 否 | 轮值规则ID（source_type为DB的时候必填）                   |
| bk_biz_id   | int    | 是 | 业务ID                                          |
| begin_time  | string | 是 | 预览生效开始时间（日期时间格式）                              |
| days        | int    | 否 | 默认生效时间开始30天                                   |
| source_type | string | 否 | 数据来源类型 `API（接口参数）` `DB（DB存储内容）`               |
| config      | dict   | 否 | 数据来源类型为API的时候必填，格式为 `{"duty_rules": [1,2,3]}` |

### 请求参数示例

#### source_type的值为BD时

```json
{
  "source_type": "DB",
  "id": 2,
  "begin_time": "2023-12-01 00:00:00",
  "days": 7,
  "bk_biz_id": 2
}
```

#### source_type的值为API时
```json
{
  "source_type": "API",
  "begin_time": "2023-12-01 00:00:00",
  "days": 7,
  "bk_biz_id": 2,
  "config":{
            "duty_rules": [2, 3]
        }
}
```

### 响应参数

| 字段    | 类型   | 描述             |
| ------- | ------ | ---------------- |
| result  | bool   | 请求是否成功     |
| code    | int    | 返回的状态码     |
| message | string | 描述信息         |
| data    | list   | 轮值规则预览数据 |

#### data 字段说明

| 字段       | 类型 | 描述         |
| ---------- | ---- | ------------ |
| rule_id    | int  | 轮值规则ID   |
| duty_plans | list | 轮值计划列表 |

#### duty_plans 字段说明

| 字段          | 类型   | 描述               |
| ------------- | ------ | ------------------ |
| id            | int    | 轮班计划ID         |
| order         | int    | 轮班组的顺序       |
| user_index    | int    | 轮班用户的分组索引 |
| users         | list   | 值班人员列表       |
| work_times    | list   | 工作时间段列表     |
| start_time    | string | 轮班生效开始时间   |
| finished_time | string | 轮班生效结束时间   |
| is_active     | bool   | 是否生效状态       |

#### users 字段说明

| 字段         | 类型   | 描述                    |
| ------------ | ------ | ----------------------- |
| id           | string | 用户ID或角色代号        |
| display_name | string | 显示名称                |
| type         | string | 类型（user/group）      |
| logo         | string | 头像/logo               |
| members      | list   | 组成员信息（group类型） |

#### work_times 字段说明

| 字段       | 类型   | 描述     |
| ---------- | ------ | -------- |
| start_time | string | 开始时间 |
| end_time   | string | 结束时间 |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "rule_id": 123,
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
        }
      ]
    }
  ]
}
```

