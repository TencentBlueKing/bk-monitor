### 功能描述

保存告警策略


### 请求参数
| 字段                | 类型      | 必选  | 描述                                      |
|:------------------|---------|-----|----------------------------------------|
| bk_biz_id         | int     | 是   | 业务ID                                   |
| name              | string  | 是   | 策略名称                                   |
| scenario          | string  | 是   | 监控对象                                   |
| items             | list    | 是   | 监控项列表(Item)                            |
| detects           | list    | 是   | 检测配置列表(Detect)                        |
| notice            | object  | 是   | 通知套餐(NoticeRelation)                  |
| actions           | list    | 否   | 处理套餐列表(ActionRelation)，允许为空列表         |
| id                | int     | 否   | 策略ID（更新时必填，创建时不填）                     |
| type              | string  | 否   | 策略类型，默认为monitor                       |
| source            | string  | 否   | 监控源，默认为当前应用code                       |
| is_enabled        | boolean | 否   | 是否启用，默认为true                          |
| is_invalid        | boolean | 否   | 是否失效，默认为false                         |
| invalid_type      | string  | 否   | 失效类型，默认为空字符串                          |
| labels            | list    | 否   | 策略标签列表，默认为空列表                         |
| app               | string  | 否   | 应用名称，默认为空字符串                          |
| path              | string  | 否   | 路径，默认为空字符串                            |
| priority          | int     | 否   | 优先级（0-10000），默认为null                  |
| priority_group_key| string  | 否   | 优先级分组key，最大长度60，默认为空字符串              |
| metric_type       | string  | 否   | 指标类型，默认为空字符串                          |

#### ActionRelation

| 字段                        | 类型     | 必选  | 描述                                                    |
|---------------------------|--------|-----|-------------------------------------------------------|
| config_id                 | int    | 否   | 套餐ID                                                  |
| user_groups               | list   | 否   | 通知组ID列表                                               |
| signal                    | list   | 是   | 处理信号，允许为空，ACTION_SIGNAL多选                             |
| options                   | object | 是   | 处理套餐配置                                                |
| options.converge_config   | object | 是   | 收敛配置(ConvergeConfig)                                  |
| options.skip_delay        | int    | 否   | 跳过延迟时间（秒），默认为0                                        |


#### NoticeRelation

| 字段                                  | 类型      | 必选  | 描述                                      |
|-------------------------------------|---------|-----|------------------------------------------|
| config_id                           | int     | 否   | 套餐ID                                    |
| user_groups                         | list    | 否   | 通知组ID列表                                 |
| signal                              | list    | 是   | 处理信号，允许为空，NOTICE_SIGNAL多选               |
| options                             | object  | 是   | 通知套餐配置                                  |
| options.converge_config             | object  | 是   | 收敛配置(ConvergeConfig)                    |
| options.noise_reduce_config         | object  | 否   | 降噪配置(NoiseReduceConfig)，默认为空对象，不开启     |
| options.assign_mode                 | list    | 否   | 分派模式，默认为["only_notice", "by_rule"]    |
| options.upgrade_config              | object  | 否   | 升级配置(UpgradeConfig)，默认为空对象，不开启         |
| options.exclude_notice_ways         | object  | 否   | 排除的通知方式，默认为空对象                         |
| options.start_time                  | string  | 否   | 生效开始时间（格式：00:00:00），默认为"00:00:00"     |
| options.end_time                    | string  | 否   | 生效结束时间（格式：23:59:59），默认为"23:59:59"     |
| options.chart_image_enabled         | boolean | 否   | 是否附带图片，默认为true                          |
| config                              | object  | 是   | 通知配置                                    |
| config.need_poll                    | boolean | 否   | 是否需要轮询，默认为true                          |
| config.notify_interval              | int     | 否   | 通知间隔（秒），默认为3600，最小值60                   |
| config.interval_notify_mode         | string  | 否   | 间隔通知模式，默认为standard                      |
| config.voice_notice                 | string  | 否   | 语音通知模式，可选值：parallel(并行，默认值)、serial(串行) |
| config.template                     | list    | 是   | 通知模板配置(Template)                        |
| config.template.signal              | string  | 是   | 触发信号，NOTICE_SIGNAL单选                    |
| config.template.message_tmpl        | string  | 否   | 通知信息模板，默认为空字符串                          |
| config.template.title_tmpl          | string  | 否   | 通知标题模板，默认为空字符串                          |

#### ConvergeConfig

| 字段                  | 类型      | 必选  | 描述                                                  |
|---------------------|---------|-----|-----------------------------------------------------|
| is_enabled          | boolean | 否   | 是否启用防御，默认为true                                     |
| converge_func       | string  | 否   | 收敛函数，默认为skip_when_exceed，可选值见CONVERGE_FUNCTION    |
| timedelta           | int     | 否   | 收敛时间窗口（秒），默认为60，最小值0                              |
| count               | int     | 否   | 收敛数量，默认为1，最小值1                                     |
| condition           | list    | 否   | 收敛条件，默认为[{"dimension": "strategy_id", "value": ["self"]}] |
| need_biz_converge   | boolean | 否   | 是否需要业务汇总（仅用于NoticeRelation），默认为true               |
| sub_converge_config | object  | 否   | 二级收敛配置（仅用于NoticeRelation），结构同ConvergeConfig，优先级高于一级收敛 |

#### NoiseReduceConfig

| 字段         | 类型      | 必选  | 描述                                  |
|------------|---------|-----|-------------------------------------|
| is_enabled | boolean | 否   | 是否开启降噪，默认为false                    |
| count      | int     | 否   | 降噪阈值，开启之后必填                         |
| dimensions | list    | 否   | 降噪的对比维度，开启之后必填                      |
| unit       | string  | 否   | 单位，默认为percent                       |
| timedelta  | int     | 否   | 降噪时间窗口（分钟），默认为settings.NOISE_REDUCE_TIMEDELTA |


#### UpgradeConfig

| 字段              | 类型      | 必选  | 描述                      |
|-----------------|---------|-----|-------------------------|
| is_enabled      | boolean | 否   | 是否开启，默认为false          |
| upgrade_interval| int     | 否   | 升级间隔（分钟），默认为1440（24小时），开启之后必填 |
| user_groups     | list    | 否   | 升级通知组ID列表，开启之后必填       |

#### 相关选项
##### NOTICE_SIGNAL
| 字段              | 标签      |
|-----------------|----------|
| MANUAL          | 手动       |
| ABNORMAL        | 告警触发时    |
| RECOVERED       | 告警恢复时    |
| CLOSED          | 告警关闭时    |
| ACK             | 确认       |
| NO_DATA         | 无数据时     |
| EXECUTE         | 执行动作时    |
| EXECUTE_SUCCESS | 执行成功时    |
| EXECUTE_FAILED  | 执行失败时    |
| INCIDENT        | 故障       |

##### ACTION_SIGNAL
| 字段              | 标签      |
|-----------------|----------|
| ABNORMAL        | 告警触发时    |
| RECOVERED       | 告警恢复时    |
| CLOSED          | 告警关闭时    |
| ACK             | 确认       |
| NO_DATA         | 无数据时     |
| EXECUTE         | 执行动作时    |
| EXECUTE_SUCCESS | 执行成功时    |
| EXECUTE_FAILED  | 执行失败时    |
| INCIDENT        | 故障       |

##### CONVERGE_FUNCTION
| 字段                 | 标签      |
|--------------------|----------|
| SKIP_WHEN_SUCCESS  | 成功后跳过    |
| SKIP_WHEN_PROCEED  | 执行中跳过    |
| WAIT_WHEN_PROCEED  | 执行中等待    |
| SKIP_WHEN_EXCEED   | 超出后忽略    |
| DEFENSE            | 异常防御审批   |
| COLLECT            | 超出后汇总    |
| COLLECT_ALARM      | 汇总通知     |


#### Detect

| 字段                                      | 类型     | 必选  | 描述                                                    |
|-----------------------------------------|--------|-----|-------------------------------------------------------|
| level                                   | int    | 是   | 告警级别                                                  |
| trigger_config                          | object | 是   | 触发条件配置                                                |
| trigger_config.count                    | int    | 是   | 触发次数                                                  |
| trigger_config.check_window             | int    | 是   | 触发周期                                                  |
| trigger_config.uptime                   | object | 否   | 生效时间配置                                                |
| trigger_config.uptime.time_ranges       | list   | 否   | 生效时间范围列表，默认为空列表                                       |
| trigger_config.uptime.calendars         | list   | 否   | 不生效日历ID列表，默认为空列表                                      |
| trigger_config.uptime.active_calendars  | list   | 否   | 生效日历ID列表，默认为空列表                                       |
| recovery_config                         | object | 是   | 恢复条件配置                                                |
| recovery_config.check_window            | int    | 是   | 恢复周期                                                  |
| recovery_config.status_setter           | string | 否   | 告警恢复目标状态，可选值：recovery/close/recovery-nodata，默认为recovery |
| id                                      | int    | 否   | 检测id（更新时使用）                                           |
| expression                              | string | 否   | 计算公式，默认为空字符串                                          |
| connector                               | string | 否   | 同级别算法连接符，默认为and                                       |

#### Item

| 字段                        | 类型     | 必选  | 描述                                    |
|---------------------------|--------|-----|---------------------------------------|
| name                      | string | 是   | 监控项名称                                 |
| query_configs             | list   | 是   | 指标查询配置列表(QueryConfig)                 |
| algorithms                | list   | 是   | 算法配置列表(Algorithm)                     |
| no_data_config            | object | 是   | 无数据配置                                 |
| no_data_config.is_enabled | bool   | 是   | 是否开启无数据告警                             |
| no_data_config.continuous | int    | 否   | 无数据告警检测周期数                            |
| target                    | list   | 否   | 监控目标，默认为空列表                           |
| id                        | int    | 否   | 监控项配置id（更新时使用），默认为0                   |
| expression                | string | 否   | 计算公式，默认为空字符串                          |
| functions                 | list   | 否   | 函数列表，默认为空列表                           |
| origin_sql                | string | 否   | 源sql，默认为空字符串                          |
| metric_type               | string | 否   | 指标类型，默认为空字符串（不填时自动从query_configs推断） |

#### Target

| 字段     | 类型     | 必选  | 描述      |
|--------|--------|-----|---------|
| field  | string | 是   | 监控目标类型  |
| value  | dict   | 是   | 监控目标数据项 |
| method | string | 是   | 监控目标方法  |

field - 根据目标节点类型和目标对象类型组合
host_target_ip
host_ip
host_topo
service_topo
service_service_template
service_set_template
host_service_template
host_set_template

```json
{
  "target": [
    [
      {
        "field": "host_topo_node",
        "method": "eq",
        "value": [
          {
            "bk_inst_id": 7,
            "bk_obj_id": "biz"
          }
        ]
      }
    ]
  ]
}
```

#### QueryConfig

| 字段                | 类型     | 必选  | 描述     |
|-------------------|--------|-----|--------|
| alias             | string | 是   | 别名     |
| data_source_label | string | 是   | 数据源标签  |
| data_type_label   | string | 是   | 数据类型标签 |

##### BkMonitorTimeSeries类型

```json
{
  "data_source_label": "bk_monitor",
  "data_type_label": "time_series"
}
```

| 字段              | 类型     | 必选  | 描述    |
|-----------------|--------|-----|-------|
| metric_field    | string | 是   | 指标    |
| unit            | string | 是   | 单位    |
| agg_condition   | list   | 是   | 查询条件  |
| agg_dimension   | list   | 是   | 聚合维度  |
| agg_method      | string | 是   | 聚合方法  |
| agg_interval    | int    | 是   | 聚合周期  |
| result_table_id | string | 是   | 结果表ID |

##### BkMonitorLog类型

```json
{
  "data_source_label": "bk_monitor",
  "data_type_label": "log"
}
```

| 字段              | 类型     | 必选  | 描述   |
|-----------------|--------|-----|------|
| agg_method      | string | 是   | 聚合方法 |
| agg_condition   | list   | 是   | 查询条件 |
| result_table_id | string | 是   | 结果表  |
| agg_interval    | int    | 是   | 聚合周期 |

##### BkMonitorEvent类型

```json
{
  "data_source_label": "bk_monitor",
  "data_type_label": "event"
}
```

| 字段              | 类型     | 必选  | 描述   |
|-----------------|--------|-----|------|
| metric_field    | string | 是   | 指标   |
| agg_condition   | list   | 是   | 查询条件 |
| result_table_id | string | 是   | 结果表  |

##### BkLogSearchTimeSeries类型

```json
{
  "data_source_label": "bk_log_search",
  "data_type_label": "time_series"
}
```

| 字段              | 类型     | 必选  | 描述    |
|-----------------|--------|-----|-------|
| metric_field    | string | 是   | 指标    |
| index_set_id    | int    | 是   | 索引集ID |
| agg_condition   | list   | 是   | 查询条件  |
| agg_dimension   | list   | 是   | 聚合维度  |
| agg_method      | string | 是   | 聚合方法  |
| result_table_id | string | 是   | 索引    |
| agg_interval    | int    | 是   | 聚合周期  |
| time_field      | string | 是   | 时间字段  |
| unit            | string | 是   | 单位    |

##### BkLogSearchLog类型

```json
{
  "data_source_label": "bk_log_search",
  "data_type_label": "log"
}
```

| 字段              | 类型     | 必选  | 描述    |
|-----------------|--------|-----|-------|
| index_set_id    | int    | 是   | 索引集ID |
| agg_condition   | list   | 是   | 查询条件  |
| query_string    | int    | 是   | 查询语句  |
| agg_dimension   | list   | 是   | 聚合维度  |
| result_table_id | string | 是   | 索引    |
| agg_interval    | int    | 是   | 聚合周期  |
| time_field      | string | 是   | 时间字段  |

##### CustomEvent类型

```json
{
  "data_source_label": "custom",
  "data_type_label": "event"
}
```

| 字段                | 类型     | 必选  | 描述      |
|-------------------|--------|-----|---------|
| custom_event_name | string | 是   | 自定义事件名称 |
| agg_condition     | list   | 是   | 查询条件    |
| agg_interval      | int    | 是   | 聚合周期    |
| agg_dimension     | list   | 是   | 查询维度    |
| agg_method        | string | 是   | 聚合方法    |
| result_table_id   | string | 是   | 结果表ID   |

##### CustomTimeSeries类型

```json
{
  "data_source_label": "custom",
  "data_type_label": "time_series"
}
```
 | 字段              | 类型     | 必选  | 描述    |
|-----------------|--------|-----|-------|
| metric_field    | string | 是   | 指标    |
| unit            | string | 是   | 单位    |
| agg_condition   | list   | 是   | 查询条件  |
| agg_dimension   | list   | 是   | 聚合维度  |
| agg_method      | string | 是   | 聚合方法  |
| agg_interval    | int    | 是   | 聚合周期  |
| result_table_id | string | 是   | 结果表ID |

##### BkDataTimeSeries类型

```json
{
  "data_source_label": "bk_data",
  "data_type_label": "time_series"
}
```

| 字段              | 类型     | 必选  | 描述   |
|-----------------|--------|-----|------|
| metric_field    | string | 是   | 指标   |
| unit            | string | 是   | 单位   |
| agg_condition   | list   | 是   | 查询条件 |
| agg_dimension   | list   | 是   | 聚合维度 |
| agg_method      | string | 是   | 聚合方法 |
| agg_interval    | int    | 是   | 聚合周期 |
| result_table_id | string | 是   | 结果表  |
| time_field      | string | 是   | 时间字段 |



#### Algorithm

| 字段          | 类型     | 必选  | 描述                     |
|-------------|--------|-----|------------------------|
| type        | string | 是   | 算法类型                   |
| level       | int    | 是   | 告警级别                   |
| config      | list   | 是   | 算法配置列表（具体格式见下方算法配置说明） |
| id          | int    | 否   | 算法id（更新时使用），默认为0      |
| unit_prefix | string | 否   | 算法单位前缀，默认为空字符串         |

#### 算法配置config

##### 静态阈值Threshold

```json
[
  {
    "method": "gt", // gt,gte,lt,lte,eq,neq
    "threshold": "1"
  }
]
```

##### 简单环比SimpleRingRatio

```json
{
  "floor": "1",
  "ceil": "1"
}
```

##### 简单同比SimpleYearRound

```json
{
  "floor": "1",
  "ceil": "1"
}
```

##### 高级环比AdvancedRingRatio

```json
{
  "floor": "1",
  "ceil": "1",
  "floor_interval": 1,
  "ceil_interval": 1
}
```

##### 高级同比AdvancedYearRound

与高级环比检测算法配置格式一致

##### 智能异常检测IntelligentDetect

```json
{
  "sensitivity_value": 1 // 0-100
  "anomaly_detect_direct": "ceil" // "ceil", "floor", "all"(default)
}
```

##### 同比振幅YearRoundAmplitude

```json
{
  "ratio": 1,
  "shock": 1,
  "days": 1,
  "method": "gte" // gt,gte,lt,lte,eq,neq
}
```

##### 同比区间YearRoundRange

与同比振幅配置格式一致

##### 环比振幅RingRatioAmplitude

```json
{
  "ratio": 1,
  "shock": 1,
  "days": 1,
  "threshold": 1
}
```

### 请求参数示例

```json
{
    "id": 36,
    "bk_biz_id": 7,
    "scenario": "host_process",
    "name": "进程端口",
    "labels": [],
    "is_enabled": true,
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
            "target": [],
            "expression": "a",
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
                    "custom_event_name": "usage",
                    "functions": [],
                    "time_field": "time",
                    "bkmonitor_strategy_id": "usage",
                    "alert_name": "usage"
                }
            ],
            "algorithms": [
                {
                    "level": 1,
                    "type": "Threshold",
                    "config": [
                        [
                            {
                                "method": "gte",
                                "threshold": "80"
                            }
                        ]
                    ],
                    "unit_prefix": "%"
                }
            ]
        }
    ],
    "detects": [
    {
          "level": 2,
          "expression": "",
          "trigger_config": {
            "count": 1,
            "check_window": 5
          },
          "recovery_config": {
            "check_window": 5
          },
          "connector": "and"
    }
    ],
    "notice": {    // 通知设置
        "config_id":0,   // 套餐ID，如果不选套餐请置为0
        "user_groups":[  // 告警组ID
            1,
            2
        ],
        "signal":["abnormal", "recovered"],   // 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
        "options": {
            "converge_config": {
                "need_biz_converge": true    // 告警风暴开关
            },
          "noise_reduce_config": {
              "is_enabled": true,    // 降噪开关
              "count": 10, //降噪百分比
              "dimensions": ["ip"] //降噪维度
            },
            "start_time": "00:00:00",
            "end_time": "23:59:59"
        },
        "config": {
            "interval_notify_mode": "standard",    // 间隔模式
            "notify_interval": 7200,    // 通知间隔
            "voice_notice": "parallel",  //语音通知模式，可选值：parallel(并行，默认值)、serial(串行，合并通知组用户后通知一次)  |
            "template": [   // 通知模板配置
                {
                    "signal": "abnormal",   // 触发信号：abnormal-告警触发时，recovered-告警恢复时，closed-告警关闭时
                    "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}\n{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n{{content.related_info}}",
                    "title_tmpl": "【{{level_name}}】{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}"
                },
                {
                    "signal": "recovered",
                    "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}\n{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n{{content.related_info}}",
                    "title_tmpl": "【{{level_name}}】{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}"
                },
                {
                    "signal": "closed",
                    "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}\n{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n{{content.related_info}}",
                    "title_tmpl": "【{{level_name}}】{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}"
                }
            ]
        }
    },
    "actions":[   // 如果用户没有选处理动作，请置为空列表
        {
           "config_id":333,   // 套餐ID
           "user_groups":[    // 告警组ID，提交时请与通知中设置的告警组保持一致
               1,
               2
           ],
           "options": {
               "converge_config": {
                   "converge_func": "skip_when_success",    // 防御动作
                   "timedelta": 60,     // 防御窗口大小（秒），默认设置为 60
                   "count": 1           // 执行次数，默认设置为 1
               }
           }
        }
    ]
}
```

### 响应参数

| 字段      | 类型     | 描述     |
| ------- |--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 策略信息   |

#### data返回保存后的完整策略结构，包含以下字段：

| 字段                | 类型      | 描述                                      |
|-------------------|---------|------------------------------------------|
| id                | int     | 策略ID                                    |
| bk_biz_id         | int     | 业务ID                                    |
| name              | string  | 策略名称                                    |
| type              | string  | 策略类型                                    |
| source            | string  | 监控源                                     |
| scenario          | string  | 监控对象                                    |
| is_enabled        | boolean | 是否启用                                    |
| is_invalid        | boolean | 是否失效                                    |
| invalid_type      | string  | 失效类型                                    |
| items             | list    | 监控项列表，结构同请求参数                           |
| detects           | list    | 检测配置列表，结构同请求参数                          |
| actions           | list    | 处理套餐列表，结构同请求参数                          |
| notice            | object  | 通知套餐，结构同请求参数                            |
| labels            | list    | 策略标签列表                                  |
| app               | string  | 应用名称                                    |
| path              | string  | 路径                                      |
| priority          | int     | 优先级                                     |
| priority_group_key| string  | 优先级分组key                                |
| metric_type       | string  | 指标类型                                    |
| create_time       | string  | 创建时间                                    |
| update_time       | string  | 更新时间                                    |
| create_user       | string  | 创建者                                     |
| update_user       | string  | 更新者                                     |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "id": 36,
    "bk_biz_id": 7,
    "name": "进程端口",
    "type": "monitor",
    "source": "bk_monitor",
    "scenario": "host_process",
    "is_enabled": true,
    "is_invalid": false,
    "invalid_type": "",
    "labels": [],
    "app": "",
    "path": "",
    "priority": null,
    "priority_group_key": "",
    "metric_type": "time_series",
    "items": [
      {
        "id": 1,
        "name": "AVG(CPU使用率)",
        "expression": "a",
        "origin_sql": "",
        "functions": [],
        "query_configs": [
          {
            "alias": "a",
            "data_source_label": "bk_monitor",
            "data_type_label": "time_series",
            "result_table_id": "system.cpu_summary",
            "agg_method": "AVG",
            "agg_interval": 60,
            "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
            "agg_condition": [],
            "metric_field": "usage",
            "unit": "percent"
          }
        ],
        "algorithms": [
          {
            "id": 1,
            "type": "Threshold",
            "level": 1,
            "config": [[{"method": "gte", "threshold": "80"}]],
            "unit_prefix": "%"
          }
        ],
        "no_data_config": {
          "is_enabled": false,
          "continuous": 10
        },
        "target": []
      }
    ],
    "detects": [
      {
        "id": 1,
        "level": 2,
        "expression": "",
        "connector": "and",
        "trigger_config": {
          "count": 1,
          "check_window": 5,
          "uptime": {
            "time_ranges": [],
            "calendars": [],
            "active_calendars": []
          }
        },
        "recovery_config": {
          "check_window": 5,
          "status_setter": "recovery"
        }
      }
    ],
    "notice": {
      "config_id": 0,
      "user_groups": [1, 2],
      "signal": ["abnormal", "recovered"],
      "options": {
        "converge_config": {
          "is_enabled": true,
          "converge_func": "skip_when_exceed",
          "timedelta": 60,
          "count": 1,
          "condition": [{"dimension": "strategy_id", "value": ["self"]}],
          "need_biz_converge": true
        },
        "noise_reduce_config": {
          "is_enabled": true,
          "count": 10,
          "dimensions": ["ip"],
          "unit": "percent"
        },
        "assign_mode": ["only_notice", "by_rule"],
        "upgrade_config": {
          "is_enabled": false
        },
        "exclude_notice_ways": {},
        "start_time": "00:00:00",
        "end_time": "23:59:59",
        "chart_image_enabled": true
      },
      "config": {
        "need_poll": true,
        "notify_interval": 7200,
        "interval_notify_mode": "standard",
        "voice_notice": "parallel",
        "template": [
          {
            "signal": "abnormal",
            "message_tmpl": "{{content.level}}\n{{content.begin_time}}",
            "title_tmpl": "【{{level_name}}】{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}"
          },
          {
            "signal": "recovered",
            "message_tmpl": "{{content.level}}\n{{content.begin_time}}",
            "title_tmpl": "【{{level_name}}】{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}"
          }
        ]
      }
    },
    "actions": [
      {
        "config_id": 333,
        "user_groups": [1, 2],
        "signal": ["abnormal"],
        "options": {
          "converge_config": {
            "is_enabled": true,
            "converge_func": "skip_when_success",
            "timedelta": 60,
            "count": 1,
            "condition": [{"dimension": "strategy_id", "value": ["self"]}]
          },
          "skip_delay": 0
        }
      }
    ],
    "create_time": "2024-01-01 12:00:00",
    "update_time": "2024-01-01 12:00:00",
    "create_user": "admin",
    "update_user": "admin"
  }
}
```





