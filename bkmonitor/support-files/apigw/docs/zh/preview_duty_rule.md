### 功能描述

保存轮值规则


### 请求参数

| 字段             | 类型     | 必须   | 描述                              |
|----------------|--------|------|---------------------------------|
| id             | int    | 否    | 轮值规则ID（source_type为DB的时候必填）     |
| bk_biz_id      | int    | 是    | 业务ID                            |
| begin_time | string | 是    | 预览生效开始时间（日期时间格式）                |
| days           | int    | 否    | 默认生效时间开始30天                     |
| source_type    | string | 否    | 数据来源类型 `API（接口参数）` `DB（DB存储内容）` |
| config         | dict   | 否    | 数据来源类型为API的时候必填，格式参考保存轮值规则      |

### 请求参数示例

#### source_type的值为db时

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
  "id": 2,
  "begin_time": "2023-12-01 00:00:00",
  "days": 7,
  "bk_biz_id": 2,
  "config": {
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
}
```

### 响应参数

| 字段         | 类型           | 描述        |
|------------|--------------|-----------|
| result     | bool         | 请求是否成功    |
| code       | int          | 返回的状态码    |
| message    | string       | 描述信息      |
| data       | list[object] | 预览数据      |
| request_id | str          | ESB记录请求ID |

#### data 字段说明： 

| 字段         | 类型 | 描述               |
| ------------ | ---- | ------------------ |
| `id`         | int  | 排班计划ID         |
| `order`      | int  | 轮班组的顺序       |
| `user_index` | int  | 轮班用户的分组索引 |
| `users`      | list | 值班人员列表       |
| `work_times` | list | 工作时间段列表     |

#### users 字段说明

| 字段           | 类型 | 描述               |
| -------------- | ---- | ------------------ |
| `id`           | str  | 用户或用户组ID     |
| `display_name` | str  | 显示名称           |
| `type`         | str  | 类型（user/group） |

#### work_times 字段说明

| 字段         | 类型 | 描述                                  |
| ------------ | ---- | ------------------------------------- |
| `start_time` | str  | 开始时间（格式：YYYY-MM-DD HH:MM:SS） |
| `end_time`   | str  | 结束时间（格式：YYYY-MM-DD HH:MM:SS） |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "success",
  "data": [
    {
      "id": 123,
      "order": 1,
      "user_index": 0,
      "users": [
        {
          "id": "admin",
          "display_name": "管理员",
          "type": "user"
        }
      ],
      "work_times": [
        {
          "start_time": "2023-12-01 00:00:00",
          "end_time": "2023-12-01 23:59:59"
        }
      ]
    },
    // ... 共7天的排班计划
  ]
}
```
