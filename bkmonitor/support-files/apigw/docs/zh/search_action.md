### 功能描述

查询处理记录列表


### 请求参数

| 字段           | 类型              | 必选 | 描述                                                         |
| -------------- | ----------------- | ---- | ------------------------------------------------------------ |
| bk_biz_ids     | list[int]         | 否   | 业务ID列表，默认为 null                                      |
| alert_ids      | list[str]         | 否   | 告警ID列表                                                   |
| status         | list[str]         | 否   | 状态，可选 `MINE`, `ABNORMAL`, `CLOSED`, `RECOVERED`         |
| conditions     | list[Condition]   | 否   | 过滤条件，默认为空列表                                       |
| query_string   | str               | 否   | 查询字符串，默认为空字符串，语法：https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-query-string-query.html#query-string-query-notes |
| ordering       | list[str]         | 否   | 排序字段，字段前面加 "-" 代表倒序，默认为空列表             |
| start_time     | int               | 否   | 开始时间（时间戳）                                           |
| end_time       | int               | 否   | 结束时间（时间戳）                                           |
| page           | int               | 否   | 页数，默认为 1，最小值为 1                                   |
| page_size      | int               | 否   | 每页条数，默认为 10，最小值为 0，最大值为 1000               |
| show_overview  | bool              | 否   | 是否返回总览统计信息，默认为 true                            |
| show_aggs      | bool              | 否   | 是否返回聚合统计信息，默认为 true                            |
| show_dsl       | bool              | 否   | 是否返回DSL，默认为 false                                    |
| record_history | bool              | 否   | 是否保存收藏历史，默认为 false                               |

#### 过滤条件（Condition）

| 字段      | 类型     | 必选 | 描述                                                         |
| :-------- | :------- | :--- | :----------------------------------------------------------- |
| key       | str      | 是   | 匹配字段名                                                   |
| value     | list     | 是   | 匹配值列表。当 `method = eq`，则满足其一即可；当 `method = neq`，则全都不满足；当 `method = include`，则包含其一即可；当 `method = exclude`，则全都不包含 |
| method    | str      | 否   | 匹配方法，可选值：`eq`（等于）, `neq`（不等于）, `include`（包含）, `exclude`（排除）, `gt`（大于）, `gte`（大于等于）, `lt`（小于）, `lte`（小于等于），默认为 `eq` |
| condition | str      | 否   | 复合条件，可选值：`and`（且）, `or`（或）, `""`（空字符串），默认为空字符串 |

### 请求参数示例

```json
{
    "alert_ids": ["16424876305819838"],
    "bk_biz_id": 5000140,
    "conditions": [
        {
            "key": "parent_action_id", 
            "value": [0], 
            "method": "eq"
        }
    ],
    "ordering": ["create_time"],
    "page": 1,
    "page_size": 100,
    "status": ["failure", "success"]
}
```

### 响应参数

| 字段    | 类型   | 描述         |
| ------- | ------ | ------------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息     |
| data    | dict   | 返回数据     |

#### data 字段说明

| 字段     | 类型 | 描述               |
| -------- | ---- | ------------------ |
| actions  | list | 所有的处理记录列表 |
| total    | int  | 返回处理记录的条数 |
| aggs     | list | 返回的聚合统计信息 |
| overview | dict | 返回的总览统计信息 |

#### data.actions字段说明

| 字段                       | 类型       | 描述                                                         |
| -------------------------- | ---------- | ------------------------------------------------------------ |
| action_config              | dict       | 套餐配置                                                     |
| action_config_id           | int        | 套餐ID                                                       |
| action_name                | str        | 套餐名称                                                     |
| action_plugin              | dict       | 套餐插件快照                                                 |
| action_plugin_type         | str        | 套餐类型                                                     |
| action_plugin_type_display | str        | 套餐类型名称                                                 |
| alert_id                   | list[str]  | 告警ID列表                                                   |
| alert_level                | int        | 告警级别                                                     |
| bk_biz_id                  | str        | 业务ID                                                       |
| bk_biz_name                | str        | 业务名称                                                     |
| bk_module_ids              | list[int]  | 模块ID列表                                                   |
| bk_module_names            | str        | 模块名称（以`,`分割）                                        |
| bk_set_ids                 | list[int]  | 集群ID列表                                                   |
| bk_set_names               | str        | 集群名称（以`,`分割）                                        |
| bk_target_display          | str        | 目标                                                         |
| content                    | dict       | 处理内容                                                     |
| converge_count             | int        | 告警收敛数量                                                 |
| converge_id                | int        | 告警收敛记录ID                                               |
| create_time                | int        | 创建时间（时间戳）                                           |
| dimension_string           | str        | 维度信息字符串                                               |
| dimensions                 | list[dict] | 维度信息列表                                                 |
| duration                   | str        | 处理时长                                                     |
| end_time                   | int        | 结束时间（时间戳）                                           |
| ex_data                    | dict       | 异常信息                                                     |
| execute_times              | int        | 执行次数                                                     |
| failure_type               | str        | 失败类型                                                     |
| id                         | str        | 处理记录ID                                                   |
| inputs                     | dict       | 动作输入                                                     |
| is_converge_primary        | bool       | 是否为收敛关键记录                                           |
| is_parent_action           | bool       | 是否为父任务                                                 |
| operate_target_string      | str        | 执行对象                                                     |
| operator                   | list[str]  | 负责人列表                                                   |
| outputs                    | dict       | 输出动作                                                     |
| parent_action_id           | int        | 父记录ID                                                     |
| raw_id                     | int        | 原始ID                                                       |
| related_action_ids         | list       | 关联的任务ID列表                                             |
| signal                     | str        | 触发信号                                                     |
| signal_display             | str        | 触发信号别名                                                 |
| status                     | str        | 状态：running - 执行中, success - 成功, failure - 失败, skipped - 已收敛, shield - 被屏蔽 |
| status_tips                | str        | 状态别名                                                     |
| strategy_id                | int        | 策略ID                                                       |
| strategy_name              | str        | 策略名称                                                     |
| update_time                | int        | 更新时间（时间戳）                                           |

#### data.aggs字段说明（overview结构与之类似）

| 字段     | 类型       | 描述               |
| -------- | ---------- | ------------------ |
| id       | str        | 聚合统计ID         |
| name     | str        | 聚合统计名称       |
| count    | int        | 相关数量           |
| children | list[dict] | 该聚合统计可选内容，每个元素结构与父级相同 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "actions": [
            {
                "id": "164248763151725306",
                "converge_id": 0,
                "is_converge_primary": false,
                "status": "success",
                "failure_type": "",
                "ex_data": {
                    "message": "执行任务成功"
                },
                "strategy_id": 41868,
                "strategy_name": "CPU使用率告警",
                "signal": "abnormal",
                "alert_id": [
                    "16424876305819838"
                ],
                "alert_level": 3,
                "operator": [
                    "xxxx"
                ],
                "inputs": {
                    "last_notify_interval": 0,
                    "time_range": "00:00:00--23:59:59",
                    "notify_info": {
                        "rtx": [
                            "xxxxx"
                        ],
                        "mail": [
                            "xxxx"
                        ],
                        "voice": [
                            [
                                "xxxx"
                            ]
                        ]
                    }
                },
                "outputs": {
                    "retry_times": 1,
                    "execute_notify_result": {},
                    "target_info": {
                        "bk_biz_name": "demo",
                        "bk_target_display": "127.0.0.1|0",
                        "dimensions": [
                            {
                                "key": "ip",
                                "value": "127.0.0.1",
                                "display_key": "目标IP",
                                "display_value": "127.0.0.1"
                            },
                            {
                                "key": "bk_cloud_id",
                                "value": 0,
                                "display_key": "云区域ID",
                                "display_value": 0
                            }
                        ],
                        "strategy_name": "CPU使用率告警",
                        "operate_target_string": "None",
                        "bk_set_ids": [
                            5001664
                        ],
                        "bk_set_names": "web服务",
                        "bk_module_ids": [
                            5004315
                        ],
                        "bk_module_names": "nginx"
                    }
                },
                "execute_times": 1,
                "action_plugin_type": "notice",
                "action_plugin": {
                    "id": 1,
                    "name": "通知",
                    "plugin_type": "notice",
                    "plugin_key": "notice",
                    "update_user": "admin",
                    "update_time": "2022-01-14T10:05:19.568322+08:00",
                    "is_enabled": true,
                    "config_schema": {
                        "content_template": "发送{{notice_way_display}}告警通知给{{notice_receiver}}{{status_display}}",
                        "content_template_with_url": "达到通知告警的执行条件【{{action_signal}}】，已触发告警通知"
                    },
                    "backend_config": [
                        {
                            "function": "execute_notify",
                            "name": "发送通知"
                        }
                    ]
                },
                "action_name": "告警通知",
                "action_config": {
                    "id": 36457,
                    "name": "告警通知",
                    "plugin_id": 1,
                    "bk_biz_id": 0,
                    "desc": "通知套餐，策略ID: 41868",
                    "execute_config": {
                        "template_detail": {
                            "need_poll": true,
                            "notify_interval": 7200,
                            "interval_notify_mode": "standard",
                            "template": [
                                {
                                    "signal": "abnormal",
                                    "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}\n{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n{{content.related_info}}",
                                    "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}"
                                },
                                {
                                    "signal": "recovered",
                                    "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}\n{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n{{content.related_info}}",
                                    "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}"
                                },
                                {
                                    "signal": "closed",
                                    "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}\n{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n{{content.related_info}}",
                                    "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}"
                                }
                            ]
                        }
                    },
                    "is_enabled": true,
                    "is_deleted": false,
                    "create_user": "xxxx",
                    "create_time": "2022-01-18T14:27:33.503839+08:00",
                    "update_user": "xxxx",
                    "update_time": "2022-01-18T14:27:50.870734+08:00",
                    "is_builtin": false,
                    "plugin_name": "通知",
                    "plugin_type": "notice"
                },
                "action_config_id": 36457,
                "is_parent_action": true,
                "related_action_ids": null,
                "parent_action_id": 0,
                "create_time": 1642487631,
                "update_time": 1642487631,
                "end_time": 1642487631,
                "bk_target_display": "127.0.0.1|0",
                "bk_biz_id": "5000140",
                "bk_biz_name": "demo",
                "bk_set_ids": [
                    5001664
                ],
                "bk_set_names": "web服务",
                "bk_module_ids": [
                    5004315
                ],
                "bk_module_names": "nginx",
                "raw_id": 51725306,
                "duration": "0s",
                "operate_target_string": "None",
                "content": {
                    "text": "达到通知告警的执行条件【告警触发时】，已触发告警通知",
                    "url": "xxxxxxx",
                    "action_plugin_type": "notice"
                },
                "dimensions": [
                    {
                        "key": "ip",
                        "value": "127.0.0.1",
                        "display_key": "目标IP",
                        "display_value": "127.0.0.1"
                    },
                    {
                        "key": "bk_cloud_id",
                        "value": 0,
                        "display_key": "云区域ID",
                        "display_value": 0
                    }
                ],
                "dimension_string": "目标IP(127.0.0.1) - 云区域ID(0)",
                "status_tips": "执行任务成功",
                "converge_count": 0,
                "action_plugin_type_display": "通知",
                "signal_display": "告警触发时"
            }
        ],
        "total": 1,
        "overview": {
            "id": "action",
            "name": "处理记录",
            "count": 2,
            "children": [
                {
                    "id": "success",
                    "name": "成功",
                    "count": 2
                },
                {
                    "id": "failure",
                    "name": "失败",
                    "count": 0
                }
            ]
        },
        "aggs": [
            {
                "id": "action_plugin_type",
                "name": "套餐类型",
                "count": 2,
                "children": [
                    {
                        "id": "notice",
                        "name": "通知",
                        "count": 2
                    },
                    {
                        "id": "webhook",
                        "name": "HTTP回调",
                        "count": 0
                    },
                    {
                        "id": "job",
                        "name": "作业平台",
                        "count": 0
                    },
                    {
                        "id": "sops",
                        "name": "标准运维",
                        "count": 0
                    },
                    {
                        "id": "itsm",
                        "name": "流程服务",
                        "count": 0
                    },
                    {
                        "id": "sops_common",
                        "name": "标准运维公共流程",
                        "count": 0
                    },
                    {
                        "id": "authorize",
                        "name": "内置授权套餐",
                        "count": 0
                    }
                ]
            },
            {
                "id": "signal",
                "name": "触发信号",
                "count": 2,
                "children": [
                    {
                        "id": "manual",
                        "name": "手动",
                        "count": 0
                    },
                    {
                        "id": "abnormal",
                        "name": "告警触发时",
                        "count": 2
                    },
                    {
                        "id": "recovered",
                        "name": "告警恢复时",
                        "count": 0
                    },
                    {
                        "id": "closed",
                        "name": "告警关闭时",
                        "count": 0
                    },
                    {
                        "id": "no_data",
                        "name": "无数据时",
                        "count": 0
                    },
                    {
                        "id": "collect",
                        "name": "汇总",
                        "count": 0
                    },
                    {
                        "id": "execute_success",
                        "name": "执行成功时",
                        "count": 0
                    },
                    {
                        "id": "execute_failed",
                        "name": "执行失败时",
                        "count": 0
                    },
                    {
                        "id": "demo",
                        "name": "调试",
                        "count": 0
                    }
                ]
            },
            {
                "id": "duration",
                "name": "处理时长",
                "count": 2,
                "children": [
                    {
                        "id": "minute",
                        "name": "小于1h",
                        "count": 2
                    },
                    {
                        "id": "hour",
                        "name": "大于1h且小于1d",
                        "count": 0
                    },
                    {
                        "id": "day",
                        "name": "大于1d",
                        "count": 0
                    }
                ]
            }
        ]
    }
}
```