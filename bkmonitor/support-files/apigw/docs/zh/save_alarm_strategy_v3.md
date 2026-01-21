### 功能描述

保存告警策略(迁移)

### 请求参数

| 字段名                | 类型           | 是否必选 | 描述               |
|--------------------|--------------|------|------------------|
| bk_biz_id          | int          | 是    | 业务ID             |
| id                 | int          | 否    | 策略ID             |
| name               | str          | 是    | 策略名称             |
| type               | str          | 否    | 策略类型，默认"monitor" |
| source             | str          | 否    | 来源应用，默认当前应用      |
| scenario           | str          | 是    | 监控场景             |
| is_enabled         | bool         | 否    | 是否启用，默认true      |
| is_invalid         | bool         | 否    | 是否失效，默认false     |
| invalid_type       | str          | 否    | 失效类型             |
| items              | list[object] | 是    | 监控项配置列表          |
| detects            | list[object] | 是    | 检测算法配置列表         |
| actions            | list[object] | 否    | 动作配置列表           |
| notice             | object       | 是    | 通知配置             |
| labels             | list[str]    | 否    | 标签列表             |
| app                | str          | 否    | 应用标识             |
| path               | str          | 否    | 路径标识             |
| priority           | int          | 否    | 优先级（0-10000）     |
| priority_group_key | str          | 否    | 优先级分组键           |
| metric_type        | str          | 否    | 指标类型             |

#### items 监控项参数

| 字段名            | 类型                 | 是否必选 | 描述     |
|----------------|--------------------|------|--------|
| id             | int                | 否    | 监控项ID  |
| name           | str                | 是    | 监控项名称  |
| expression     | str                | 否    | 表达式    |
| functions      | list[object]       | 否    | 函数配置列表 |
| origin_sql     | str                | 否    | 原始SQL  |
| target         | list[list[object]] | 否    | 监控目标配置 |
| no_data_config | object             | 是    | 无数据配置  |
| query_configs  | list[object]       | 是    | 查询配置列表 |
| algorithms     | list[object]       | 是    | 算法配置列表 |
| metric_type    | string             | 否    | 指标类型   |

#### items.functions

| 字段名    | 类型         | 是否必选 | 描述     |
|--------|------------|------|--------|
| id     | str        | 是    | 函数配置ID |
| params | list[dict] | 否    | 函数配置参数 |

#### items.functions.params

| 字段名   | 类型  | 是否必选 | 描述     |
|-------|-----|------|--------|
| id    | str | 是    | 函数参数ID |
| value | str | 是    | 函数参数值  |

#### items.target

| 字段     | 类型         | 必选 | 描述                         |
|--------|------------|----|----------------------------|
| field  | str        | 是  | 监控目标类型                     |
| value  | list[dict] | 是  | 监控目标数据项,具体字段结构取决于field字段的值 |
| method | str        | 是  | 监控目标方法                     |

**value字段的具体结构（根据不同的field类型）：**

##### 1. field为"ip"（主机IP目标）

```json
{
  "ip": "127.0.0.1",
  "bk_cloud_id": 0,
  "bk_host_id": 1
}
```

##### 2. field为"host_topo_node"（拓扑节点目标）

```json
{
  "bk_obj_id": "module",
  "bk_inst_id": 123
}
```

##### 3. field为"host_set_template"（集群模板目标）

```json
{
  "bk_obj_id": "SET_TEMPLATE",
  "bk_inst_id": 456
}
```

##### 4. field为"host_service_template"服务模板目标）

```json
{
  "bk_obj_id": "SERVICE_TEMPLATE",
  "bk_inst_id": 789
}
```

##### 5. field为"dynamic_group"（动态分组目标）

```json
{
  "dynamic_group_id": 999
}
```

**完整示例：**

```json
{
  "field": "host_ip",
  "method": "eq",
  "value": [
    {
      "ip": "127.0.0.1",
      "bk_cloud_id": 0,
      "bk_host_id": 1
    },
    {
      "ip": "127.0.0.2",
      "bk_cloud_id": 0,
      "bk_host_id": 2
    }
  ]
}
```

#### items.query_configs

| 字段                | 类型           | 必选 | 描述     |
|-------------------|--------------|----|--------|
| alias             | str          | 是  | 别名     |
| data_source_label | str          | 是  | 数据源标签  |
| data_type_label   | str          | 是  | 数据类型标签 |
| metric_field      | str          | 否  | 监控指标别名 |
| unit              | str          | 否  | 单位     |
| agg_dimension     | list[str]    | 否  | 聚合维度   |
| result_table_id   | str          | 否  | 表名     |
| agg_method        | str          | 否  | 聚合算法   |
| agg_interval      | int          | 否  | 聚合周期   |
| agg_condition     | list[object] | 否  | 聚合条件   |

**agg_condition聚合条件字段结构：**

| 字段名            | 类型        | 必选 | 描述              |
|----------------|-----------|----|-----------------|
| key            | str       | 是  | 条件字段名           |
| method         | str       | 是  | 条件方法            |
| value          | list[str] | 是  | 条件值列表           |
| condition      | str       | 是  | 条件类型(and 或者 or) |
| dimension_name | str       | 是  | 维度名称            |

**agg_condition示例：**

```json
[
  {
    "key": "ip",
    "method": "eq", 
    "value": ["127.0.0.1", "127.0.0.2"],
    "condition": "and",
    "dimension_name": "目标IP"
  }
]
```

#### items.algorithms

| 字段名         | 类型     | 是否必选 | 描述     |
|-------------|--------|------|--------|
| id          | int    | 否    | 算法ID   |
| type        | str    | 是    | 检测算法类型 |
| level       | int    | 是    | 告警级别   |
| unit_prefix | str    | 否    | 单位前缀   |
| config      | object | 是    | 算法配置详情 |

#### detects 检测算法参数

| 字段名             | 类型     | 是否必选 | 描述     |
|-----------------|--------|------|--------|
| id              | int    | 否    | 检测算法ID |
| level           | int    | 是    | 告警级别   |
| expression      | str    | 否    | 表达式    |
| trigger_config  | object | 是    | 触发配置   |
| recovery_config | object | 是    | 恢复配置   |
| connector       | str    | 否    | 连接符    |

#### detects.trigger_config 触发配置参数

| 字段名          | 类型     | 是否必选 | 描述       |
|--------------|--------|------|----------|
| count        | int    | 是    | 触发次数     |
| check_window | int    | 是    | 检测周期（分钟） |
| uptime       | object | 否    | 生效时间配置   |

#### detects.trigger_config.uptime 生效时间配置参数

| 字段名              | 类型           | 是否必选 | 描述       |
|------------------|--------------|------|----------|
| time_ranges      | list[object] | 否    | 生效时间范围列表 |
| calendars        | list[int]    | 否    | 不生效日历列表  |
| active_calendars | list[int]    | 否    | 生效日历列表   |

#### detects.trigger_config.uptime.time_ranges 生效时间范围参数

| 字段名   | 类型  | 是否必选 | 描述   |
|-------|-----|------|------|
| start | str | 是    | 开始时间 |
| end   | str | 是    | 结束时间 |

#### detects.recovery_config 恢复配置参数

| 字段名           | 类型  | 是否必选 | 描述                                                             |
|---------------|-----|------|----------------------------------------------------------------|
| check_window  | int | 是    | 检测周期（分钟）                                                       |
| status_setter | str | 否    | 告警恢复目标状态，可选值："recovery"、"close"、"recovery-nodata"，默认"recovery" |

#### actions 动作配置参数

| 字段名         | 类型        | 是否必选 | 描述      |
|-------------|-----------|------|---------|
| config_id   | int       | 否    | 套餐ID    |
| user_groups | list[int] | 否    | 通知组ID列表 |
| signal      | list[str] | 是    | 触发信号列表  |
| options     | object    | 是    | 动作选项配置  |

**signal 触发信号可选值：**

- abnormal: 异常信号
- recovered: 恢复信号
- closed: 关闭信号
- ack: 确认信号
- no_data: 无数据信号
- execute: 执行信号
- execute_success: 执行成功信号
- execute_failed: 执行失败信号
- incident: 事件信号

#### actions.options 动作选项配置参数

| 字段名             | 类型     | 是否必选 | 描述        |
|-----------------|--------|------|-----------|
| converge_config | object | 否    | 收敛配置      |
| skip_delay      | int    | 否    | 跳过延迟时间（秒） |

#### actions.options.converge_config 收敛配置参数

| 字段名           | 类型   | 是否必选 | 描述         |
|---------------|------|------|------------|
| is_enabled    | bool | 否    | 是否启用防御     |
| converge_func | str  | 否    | 收敛函数       |
| timedelta     | int  | 否    | 收敛时间窗口（分钟） |
| count         | int  | 否    | 收敛数量       |

#### notice 通知配置参数

| 字段名         | 类型        | 是否必选 | 描述      |
|-------------|-----------|------|---------|
| config_id   | int       | 否    | 套餐ID    |
| user_groups | list[int] | 否    | 通知组ID列表 |
| signal      | list[str] | 是    | 触发信号列表  |
| config      | object    | 是    | 通知配置详情  |
| options     | object    | 是    | 通知选项配置  |

**signal 触发信号可选值：**

- abnormal: 异常信号
- recovered: 恢复信号
- closed: 关闭信号
- ack: 确认信号
- no_data: 无数据信号
- execute: 执行信号
- execute_success: 执行成功信号
- execute_failed: 执行失败信号
- incident: 事件信号

#### notice.options 通知选项配置参数

| 字段名                 | 类型        | 是否必选 | 描述                  |
|---------------------|-----------|------|---------------------|
| converge_config     | object    | 否    | 收敛配置                |
| noise_reduce_config | object    | 否    | 降噪配置                |
| assign_mode         | list[str] | 否    | 分派模式列表              |
| upgrade_config      | object    | 否    | 升级配置                |
| exclude_notice_ways | object    | 否    | 排除的通知方式             |
| start_time          | str       | 否    | 生效开始时间，默认"00:00:00" |
| end_time            | str       | 否    | 生效结束时间，默认"23:59:59" |
| chart_image_enabled | bool      | 否    | 是否附带图片，默认true       |

#### notice.config 通知配置详情参数

| 字段名                  | 类型     | 是否必选 | 描述     |
|----------------------|--------|------|--------|
| voice_notice         | string | 否    | 语音通知模式，可选值：parallel(并行，默认值)、serial(串行) |
| template             | object | 否    | 通知模板配置 |
| need_poll            | bool   | 否    | 是否需要轮询 |
| notify_interval      | int    | 否    | 通知间隔   |
| interval_notify_mode | str    | 否    | 间隔通知模式 |

#### notice.config.template 通知模板配置

| 字段名          | 类型  | 是否必选 | 描述   |
|--------------|-----|------|------|
| signal       | str | 是    | 触发信号 |
| message_tmpl | str | 否    | 消息模板 |
| title_tmpl   | str | 否    | 标题模板 |

### 请求参数示例

```json
{
    "type": "monitor",
    "bk_biz_id": 2,
    "scenario": "os",
    "name": "test4",
    "labels": [],
    "is_enabled": true,
    "priority": null,
    "items": [
        {
            "name": "AVG(CPU使用率)",
            "no_data_config": {
                "continuous": 10,
                "is_enabled": false,
                "agg_dimension": [
                    "bk_target_ip",
                    "bk_target_cloud_id"
                ],
                "level": 2
            },
            "target": [
                [
                    {
                        "field": "ip",
                        "method": "eq",
                        "value": [
                            {
                                "ip": "127.0.0.1",
                                "bk_cloud_id": 0,
                                "bk_host_id": 580
                            }
                        ]
                    }
                ]
            ],
            "expression": "a",
            "functions": [],
            "origin_sql": "",
            "query_configs": [
                {
                    "data_source_label": "bk_monitor",
                    "data_type_label": "time_series",
                    "alias": "a",
                    "result_table_id": "system.cpu_summary",
                    "agg_method": "AVG",
                    "agg_interval": 60,
                    "agg_dimension": [
                        "bk_target_ip",
                        "bk_target_cloud_id"
                    ],
                    "agg_condition": [],
                    "metric_field": "usage",
                    "unit": "percent",
                    "metric_id": "bk_monitor.system.cpu_summary.usage",
                    "index_set_id": "",
                    "query_string": "*",
                    "custom_event_name": "",
                    "functions": [],
                    "time_field": "dtEventTimeStamp",
                    "bkmonitor_strategy_id": "usage",
                    "alert_name": "usage"
                }
            ],
            "algorithms": [
                {
                    "level": 3,
                    "type": "IntelligentDetect",
                    "config": {
                        "plan_id": 11,
                        "args": {
                            "$alert_down": "1",
                            "$alert_slight_shake": "0",
                            "$alert_upward": "1",
                            "$sensitivity": 5
                        }
                    },
                    "unit_prefix": "%"
                }
            ]
        }
    ],
    "detects": [
        {
            "level": 3,
            "expression": "",
            "trigger_config": {
                "count": 2,
                "check_window": 5,
                "uptime": {
                    "calendars": [],
                    "active_calendars": [],
                    "time_ranges": [
                        {
                            "start": "00:00",
                            "end": "23:59"
                        }
                    ]
                }
            },
            "recovery_config": {
                "check_window": 5,
                "status_setter": "recovery"
            },
            "connector": "and"
        }
    ],
    "actions": [
        {
            "config_id": 64018,
            "signal": [
                "abnormal"
            ],
            "user_groups": [],
            "options": {
                "converge_config": {
                    "is_enabled": true,
                    "converge_func": "skip_when_success",
                    "timedelta": 60,
                    "count": 1
                },
                "skip_delay": 0
            }
        }
    ],
    "notice": {
        "config_id": 0,
        "user_groups": [
            602
        ],
        "signal": [
            "abnormal"
        ],
        "options": {
            "converge_config": {
                "need_biz_converge": true
            },
            "exclude_notice_ways": {
                "recovered": [],
                "closed": [],
                "ack": []
            },
            "noise_reduce_config": {
                "is_enabled": false,
                "count": 10,
                "dimensions": []
            },
            "upgrade_config": {
                "is_enabled": false,
                "user_groups": []
            },
            "assign_mode": [
                "by_rule",
                "only_notice"
            ],
            "chart_image_enabled": true
        },
        "config": {
            "interval_notify_mode": "standard",
            "notify_interval": 7200,
            "voice_notice": "parallel",
            "template": [
                {
                    "signal": "abnormal",
                    "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}\n{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n{{content.assign_detail}}\n{{content.related_info}}",
                    "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}"
                },
                {
                    "signal": "recovered",
                    "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}\n{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n{{content.assign_detail}}\n{{content.related_info}}",
                    "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}"
                },
                {
                    "signal": "closed",
                    "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}\n{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n{{content.assign_detail}}\n{{content.related_info}}",
                    "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}"
                }
            ]
        }
    },
    "metric_type": "time_series",
    "priority_group_key": ""
}
```

### 响应参数

| 字段名     | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 数据     |

#### data 字段结构

| 字段名                | 类型           | 描述                  |
|--------------------|--------------|---------------------|
| id                 | int          | 策略ID                |
| version            | str          | 策略版本                |
| bk_biz_id          | int          | 业务ID                |
| name               | str          | 策略名称                |
| source             | str          | 来源应用                |
| scenario           | str          | 监控场景                |
| type               | str          | 策略类型                |
| is_enabled         | bool         | 是否启用                |
| is_invalid         | bool         | 是否失效                |
| invalid_type       | str          | 失效类型                |
| create_time        | str          | 创建时间                |
| update_time        | str          | 更新时间                |
| create_user        | str          | 创建用户                |
| update_user        | str          | 更新用户                |
| items              | list[object] | 监控项配置列表             |
| detects            | list[object] | 检测算法配置列表            |
| actions            | list[object] | 动作配置列表              |
| notice             | object       | 通知配置                |
| labels             | list[str]    | 标签列表                |
| app                | str          | 应用标识                |
| path               | str          | 路径标识                |
| priority           | int          | 优先级（0-10000）        |
| priority_group_key | str          | 优先级分组键              |
| edit_allowed       | bool         | 是否允许编辑              |
| metric_type        | str          | 指标类型，如"time_series" |

##### data.items

| 字段名            | 类型                 | 描述     |
|----------------|--------------------|--------|
| id             | int                | 监控项ID  |
| name           | str                | 监控项名称  |
| no_data_config | object             | 无数据配置  |
| target         | list[list[object]] | 监控目标配置 |
| expression     | str                | 表达式    |
| functions      | list[object]       | 函数配置列表 |
| origin_sql     | str                | 原始SQL  |
| query_configs  | list[object]       | 查询配置列表 |
| algorithms     | list[object]       | 算法配置列表 |
| metric_type    | string             | 指标类型   |
| time_delay     | int                | 时间延迟   |

##### data.detects

| 字段名             | 类型     | 描述     |
|-----------------|--------|--------|
| id              | int    | 检测算法ID |
| level           | int    | 告警级别   |
| expression      | str    | 表达式    |
| trigger_config  | object | 触发配置   |
| recovery_config | object | 恢复配置   |
| connector       | str    | 连接符    |

##### data.actions

| 字段名         | 类型        | 描述      |
|-------------|-----------|---------|
| id          | int       | 动作ID    |
| config_id   | int       | 套餐ID    |
| user_groups | list[int] | 用户组ID列表 |
| user_type   | str       | 用户类型    |
| signal      | list[str] | 触发信号列表  |
| options     | object    | 动作选项配置  |
| relate_type | str       | 关联类型    |
| config      | object    | 配置详情    |

##### data.notice

| 字段名         | 类型        | 描述      |
|-------------|-----------|---------|
| id          | int       | 通知ID    |
| config_id   | int       | 配置ID    |
| user_groups | list[int] | 用户组ID列表 |
| user_type   | str       | 用户类型    |
| signal      | list[str] | 触发信号列表  |
| options     | object    | 通知选项配置  |
| relate_type | str       | 关联类型    |
| config      | object    | 通知配置详情  |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "id": 65140,
        "version": "v2",
        "bk_biz_id": 2,
        "name": "test4",
        "source": "bk_monitorv3",
        "scenario": "os",
        "type": "monitor",
        "items": [
            {
                "id": 65138,
                "name": "AVG(CPU使用率)",
                "no_data_config": {
                    "continuous": 10,
                    "is_enabled": false,
                    "agg_dimension": [
                        "bk_target_ip",
                        "bk_target_cloud_id"
                    ],
                    "level": 2
                },
                "target": [
                    [
                        {
                            "field": "ip",
                            "value": [
                                {
                                    "ip": "127.0.0.1",
                                    "bk_cloud_id": 0,
                                    "bk_host_id": 580
                                }
                            ],
                            "method": "eq"
                        }
                    ]
                ],
                "expression": "a",
                "functions": [],
                "origin_sql": "",
                "query_configs": [
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "alias": "a",
                        "metric_id": "bk_monitor.system.cpu_summary.usage",
                        "id": 65471,
                        "functions": [],
                        "intelligent_detect": {
                            "status": "pending",
                            "retries": 0,
                            "message": "",
                            "task_id": "829ab22e-b0a1-4aa1-b7ec-57cfa7d567f6"
                        },
                        "result_table_id": "system.cpu_summary",
                        "agg_method": "AVG",
                        "agg_interval": 60,
                        "agg_dimension": [
                            "bk_target_cloud_id",
                            "bk_target_ip"
                        ],
                        "agg_condition": [],
                        "metric_field": "usage",
                        "unit": "percent"
                    }
                ],
                "algorithms": [
                    {
                        "id": 77855,
                        "type": "IntelligentDetect",
                        "level": 3,
                        "config": {
                            "args": {
                                "$alert_down": "1",
                                "$alert_slight_shake": "0",
                                "$alert_upward": "1",
                                "$sensitivity": 5
                            },
                            "plan_id": 11,
                            "visual_type": "none",
                            "service_name": "default"
                        },
                        "unit_prefix": "%"
                    }
                ],
                "metric_type": "time_series",
                "time_delay": 0
            }
        ],
        "detects": [
            {
                "id": 77845,
                "level": 3,
                "expression": "",
                "trigger_config": {
                    "count": 2,
                    "check_window": 5,
                    "uptime": {
                        "time_ranges": [
                            {
                                "start": "00:00",
                                "end": "23:59"
                            }
                        ],
                        "calendars": [],
                        "active_calendars": []
                    }
                },
                "recovery_config": {
                    "check_window": 5,
                    "status_setter": "recovery"
                },
                "connector": "and"
            }
        ],
        "actions": [
            {
                "id": 65186,
                "config_id": 64018,
                "user_groups": [
                    602
                ],
                "user_type": "main",
                "signal": [
                    "abnormal"
                ],
                "options": {
                    "converge_config": {
                        "is_enabled": true,
                        "converge_func": "skip_when_success",
                        "timedelta": 60,
                        "count": 1,
                        "condition": [
                            {
                                "dimension": "action_info",
                                "value": [
                                    "self"
                                ]
                            }
                        ],
                        "need_biz_converge": true
                    },
                    "skip_delay": 0,
                    "start_time": "00:00:00",
                    "end_time": "23:59:59"
                },
                "relate_type": "ACTION",
                "config": {}
            }
        ],
        "notice": {
            "id": 65187,
            "config_id": 66281,
            "user_groups": [
                602
            ],
            "user_type": "main",
            "signal": [
                "abnormal",
                "no_data"
            ],
            "options": {
                "converge_config": {
                    "is_enabled": true,
                    "converge_func": "collect",
                    "timedelta": 60,
                    "count": 1,
                    "condition": [
                        {
                            "dimension": "strategy_id",
                            "value": [
                                "self"
                            ]
                        },
                        {
                            "dimension": "dimensions",
                            "value": [
                                "self"
                            ]
                        },
                        {
                            "dimension": "alert_level",
                            "value": [
                                "self"
                            ]
                        },
                        {
                            "dimension": "signal",
                            "value": [
                                "self"
                            ]
                        },
                        {
                            "dimension": "bk_biz_id",
                            "value": [
                                "self"
                            ]
                        },
                        {
                            "dimension": "notice_receiver",
                            "value": [
                                "self"
                            ]
                        },
                        {
                            "dimension": "notice_way",
                            "value": [
                                "self"
                            ]
                        }
                    ],
                    "need_biz_converge": true,
                    "sub_converge_config": {
                        "timedelta": 60,
                        "count": 2,
                        "condition": [
                            {
                                "dimension": "bk_biz_id",
                                "value": [
                                    "self"
                                ]
                            },
                            {
                                "dimension": "notice_receiver",
                                "value": [
                                    "self"
                                ]
                            },
                            {
                                "dimension": "notice_way",
                                "value": [
                                    "self"
                                ]
                            },
                            {
                                "dimension": "alert_level",
                                "value": [
                                    "self"
                                ]
                            },
                            {
                                "dimension": "signal",
                                "value": [
                                    "self"
                                ]
                            }
                        ],
                        "converge_func": "collect_alarm"
                    }
                },
                "noise_reduce_config": {
                    "is_enabled": false,
                    "dimensions": [],
                    "count": 10,
                    "unit": "percent",
                    "timedelta": 5
                },
                "assign_mode": [
                    "by_rule",
                    "only_notice"
                ],
                "upgrade_config": {
                    "is_enabled": false,
                    "upgrade_interval": 1440,
                    "user_groups": []
                },
                "exclude_notice_ways": {
                    "recovered": [],
                    "closed": [],
                    "ack": []
                },
                "start_time": "00:00:00",
                "end_time": "23:59:59",
                "chart_image_enabled": true
            },
            "relate_type": "NOTICE",
            "config": {
                "need_poll": true,
                "notify_interval": 7200,
                "interval_notify_mode": "standard",
                "voice_notice": "parallel",
                "template": [
                    {
                        "signal": "abnormal",
                        "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}\n{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n{{content.assign_detail}}\n{{content.related_info}}",
                        "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}"
                    },
                    {
                        "signal": "recovered",
                        "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}\n{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n{{content.assign_detail}}\n{{content.related_info}}",
                        "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}"
                    },
                    {
                        "signal": "closed",
                        "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}\n{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n{{content.assign_detail}}\n{{content.related_info}}",
                        "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}"
                    }
                ]
            }
        },
        "is_enabled": true,
        "is_invalid": false,
        "invalid_type": "",
        "update_time": "2025-11-25 16:58:55+0800",
        "update_user": "",
        "create_time": "2025-11-25 16:58:55+0800",
        "create_user": "",
        "labels": [],
        "app": "",
        "path": "",
        "priority": null,
        "priority_group_key": "",
        "edit_allowed": true,
        "metric_type": "time_series"
    }
}
```