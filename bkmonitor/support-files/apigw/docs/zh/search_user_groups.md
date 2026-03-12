### 功能描述

查询告警组

### 请求参数

| 字段         | 类型        | 必选 | 描述            |
|------------|-----------|----|---------------|
| bk_biz_ids | list[int] | 否  | 业务ID列表        |
| ids        | list[int] | 否  | 告警组ID列表       |
| name       | string    | 否  | 告警组名称（支持模糊搜索） |

### 请求参数示例

```json
{
    "bk_biz_ids": [2],
    "ids": [1],
    "name": "test"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | list   | 告警组列表  |

#### data 字段说明

| 字段             | 类型           | 描述                    |
|----------------|--------------|-----------------------|
| id             | int          | 告警组ID                 |
| name           | string       | 告警组名称                 |
| bk_biz_id      | int          | 业务ID                  |
| need_duty      | bool         | 是否需要轮值                |
| channels       | list[string] | 通知渠道列表                |
| desc           | string       | 说明                    |
| timezone       | string       | 时区，默认 `Asia/Shanghai` |
| users          | list         | 当前生效的通知接收人员列表         |
| duty_rules     | list[int]    | 关联的轮值规则ID列表           |
| mention_list   | list         | @提醒人员列表               |
| mention_type   | int          | 提醒类型                  |
| app            | string       | 应用来源                  |
| strategy_count | int          | 关联的告警策略数量             |
| rules_count    | int          | 关联的分派规则数量             |
| delete_allowed | bool         | 是否允许删除                |
| edit_allowed   | bool         | 是否允许编辑                |
| config_source  | string       | 配置来源，`UI` 或 `YAML`    |
| update_user    | string       | 更新人                   |
| update_time    | string       | 更新时间                  |
| create_user    | string       | 创建人                   |
| create_time    | string       | 创建时间                  |

#### users 格式说明

| 字段           | 类型     | 描述                       |
|--------------|--------|--------------------------|
| id           | string | 角色key或者用户ID              |
| display_name | string | 显示名                      |
| type         | string | 类型，可选项`group`，`user`     |
| members      | list   | 对应的人员信息（仅当type为group时有值） |

##### members 元素格式说明

| 字段           | 类型     | 描述    |
|--------------|--------|-------|
| id           | string | 用户ID  |
| display_name | string | 用户显示名 |

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
    "data": [
        {
            "id": 62,
            "name": "企业微信机器人1234",
            "bk_biz_id": 2,
            "need_duty": false,
            "channels": [
                "user",
                "wxwork-bot"
            ],
            "desc": "",
            "timezone": "Asia/Shanghai",
            "update_user": "admin",
            "update_time": "2023-09-08 17:54:31+0800",
            "create_user": "admin",
            "create_time": "2023-04-07 12:52:50+0800",
            "duty_rules": [1, 2],
            "mention_list": [
                {
                    "type": "group",
                    "id": "all"
                }
            ],
            "mention_type": 0,
            "app": "default",
            "users": [
                {
                    "id": "bk_biz_maintainer",
                    "display_name": "运维人员",
                    "type": "group",
                    "members": [
                        {
                          "id": "admin",
                          "display_name": "管理员"
                        },
                        {
                          "id": "zhangsan",
                          "display_name": "张三"
                        }
                    ]
                },
               {
                    "id": "admin",
                    "display_name": "admin",
                    "type": "user"
                }
            ],
            "strategy_count": 6,
            "rules_count": 2,
            "delete_allowed": false,
            "edit_allowed": true,
            "config_source": "YAML"
        }
    ]
}
```

