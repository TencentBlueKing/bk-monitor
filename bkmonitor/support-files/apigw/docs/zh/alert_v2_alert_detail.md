### 功能描述

【告警V2】告警详情查询

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| id   | str  | 是   | 告警ID |

### 请求参数示例

```json
{
    "id": "f1c6877ba046e2d32bfd8393b4dd26f7.1763554080.2860.2978.2"
}
```

### 响应参数

| 字段                | 类型   | 描述                   |
|-------------------|--------|------------------------|
| result            | bool   | 请求是否成功             |
| code              | int    | 返回的状态码             |
| message           | string | 描述信息               |
| data              | dict   | 告警详情数据             |

#### data 字段说明

| 字段                  | 类型     | 描述                     |
|---------------------|----------|--------------------------|
| id                  | string   | 告警ID                   |
| alert_name          | string   | 告警名称                 |
| description         | string   | 告警描述                 |
| status              | string   | 告警状态（ABNORMAL/RECOVERED/CLOSED） |
| severity            | int      | 告警级别（1-致命/2-预警/3-提醒） |
| bk_biz_id           | int      | 业务ID                   |
| ip                  | string   | 目标IP                   |
| ipv6                | string   | 目标IPv6                 |
| bk_cloud_id         | int      | 云区域ID                 |
| bk_service_instance_id | string | 服务实例ID              |
| bk_host_id          | int      | 主机ID                   |
| bk_topo_node        | list[string] | 目标节点             |
| assignee            | list[string] | 告警接收人列表       |
| appointee           | list[string] | 负责人列表           |
| supervisor          | list[string] | 知会人列表           |
| follower            | list[string] | 关注人列表           |
| is_shielded         | bool     | 是否被屏蔽               |
| is_handled          | bool     | 是否已处理               |
| is_ack              | bool     | 是否已确认               |
| is_blocked          | bool     | 是否熔断                 |
| shield_id           | int      | 屏蔽配置ID               |
| shield_left_time    | string   | 剩余屏蔽时间             |
| strategy_id         | int      | 策略ID                   |
| strategy_name       | string   | 策略名称                 |
| labels              | list[string] | 策略标签列表         |
| metric              | list[string] | 指标ID列表           |
| category            | string   | 分类                     |
| category_display    | string   | 分类显示名称             |
| target_type         | string   | 目标类型                 |
| target              | string   | 目标对象                 |
| duration            | string   | 持续时间                 |
| ack_duration        | int      | 确认时间                 |
| stage_display       | string   | 阶段显示                 |
| data_type           | string   | 数据类型                 |
| event_id            | string   | 事件ID                   |
| seq_id              | int      | 序列ID                   |
| dedupe_md5          | string   | 去重MD5                  |
| dedupe_keys         | list[string] | 去重键列表           |
| first_anomaly_time  | int      | 首次异常时间（Unix时间戳，秒） |
| latest_time         | int      | 最新事件时间（Unix时间戳，秒） |
| begin_time          | int      | 开始时间（Unix时间戳，秒） |
| create_time         | int      | 创建时间（Unix时间戳，秒） |
| end_time            | int      | 结束时间（Unix时间戳，秒） |
| update_time         | int      | 更新时间（Unix时间戳，秒） |
| dimensions          | list[dict] | 告警维度信息           |
| dimension_message   | string   | 维度信息描述             |
| target_key          | string   | 目标键                   |
| metric_display      | list[dict] | 指标显示信息         |
| plugin_id           | string   | 插件ID                   |
| plugin_display_name | string   | 插件显示名称             |
| extend_info         | dict     | 扩展信息                 |
| graph_panel         | dict     | 图表面板信息             |
| relation_info       | string   | 关联信息                 |
| anomaly_timestamps  | list[int]| 异常时间戳列表           |
| items               | list[dict] | 策略配置项列表         |

#### dimensions 元素字段说明

| 字段          | 类型   | 描述     |
|-------------|--------|----------|
| key         | string | 维度键   |
| value       | string | 维度值   |
| display_key | string | 显示键名 |
| display_value | string | 显示值 |

#### metric_display 元素字段说明

| 字段 | 类型   | 描述     |
|-----|--------|----------|
| id  | string | 指标ID   |
| name| string | 指标名称 |

#### extend_info 字段说明

| 字段        | 类型 | 描述                 |
|-----------|------|----------------------|
| strategy  | dict | 策略详细信息         |
| origin_alarm | dict | 原始告警信息      |
| agg_dimensions | list[dict] | 聚合维度信息 |

#### graph_panel 字段说明

| 字段    | 类型   | 描述         |
|-------|--------|--------------|
| id    | string | 面板ID       |
| type  | string | 面板类型     |
| title | string | 面板标题     |
| targets | list[dict] | 查询目标列表 |

#### items 元素字段说明

| 字段          | 类型       | 描述         |
|-------------|------------|--------------|
| id          | int        | 配置项ID     |
| name        | string     | 配置项名称   |
| expression  | string     | 表达式       |
| functions   | list[dict] | 函数列表     |
| origin_sql  | string     | 原始SQL      |
| query_configs | list[dict] | 查询配置列表 |

#### query_configs 元素字段说明

| 字段          | 类型       | 描述         |
|-------------|------------|--------------|
| alias       | string     | 别名         |
| metric_id   | string     | 指标ID       |
| functions   | list[dict] | 函数列表     |
| agg_method  | string     | 聚合方法     |
| agg_interval| int        | 聚合周期     |
| agg_dimension | dict     | 聚合维度     |
| agg_condition | list[dict] | 聚合条件   |

#### agg_condition 元素字段说明

| 字段            | 类型   | 描述         |
|---------------|--------|--------------|
| key           | string | 条件键       |
| value         | list   | 条件值列表   |
| method        | string | 匹配方法     |
| condition     | string | 条件关系     |
| dimension_name| string | 维度名称     |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "id": "f1c6877ba046e2d32bfd8393b4dd26f7.1763554080.2860.2978.2",
        "alert_name": "CPU使用率过高",
        "description": "CPU使用率超过阈值",
        "status": "ABNORMAL",
        "severity": 1,
        "bk_biz_id": 2,
        "ip": "127.0.0.1",
        "bk_cloud_id": 0,
        "bk_host_id": 1001,
        "assignee": ["admin"],
        "appointee": [],
        "supervisor": [],
        "is_shielded": false,
        "is_handled": false,
        "is_ack": false,
        "strategy_id": 100,
        "strategy_name": "主机CPU使用率告警",
        "labels": ["主机监控"],
        "metric": ["system.cpu_summary.usage"],
        "category": "host",
        "category_display": "主机",
        "target_type": "HOST",
        "target": "127.0.0.1",
        "duration": "10分钟",
        "stage_display": "未恢复",
        "shield_left_time": "0秒",
        "seq_id": 1,
        "dedupe_md5": "abc123",
        "dedupe_keys": ["ip", "bk_cloud_id"],
        "first_anomaly_time": 1763554080,
        "latest_time": 1763554200,
        "begin_time": 1763554080,
        "create_time": 1763554080,
        "end_time": 0,
        "update_time": 1763554200,
        "dimensions": [
            {
                "key": "bk_target_ip",
                "value": "127.0.0.1",
                "display_key": "目标IP",
                "display_value": "127.0.0.1"
            }
        ],
        "dimension_message": "目标IP: 127.0.0.1",
        "target_key": "127.0.0.1|0",
        "metric_display": [
            {
                "id": "system.cpu_summary.usage",
                "name": "CPU使用率"
            }
        ],
        "plugin_id": "bkmonitor",
        "plugin_display_name": "蓝鲸监控",
        "extend_info": {
            "strategy": {},
            "origin_alarm": {},
            "agg_dimensions": []
        },
        "graph_panel": {
            "id": "panel_1",
            "type": "graph",
            "title": "CPU使用率趋势",
            "targets": []
        },
        "relation_info": "蓝鲸 / 作业平台 / job-manage",
        "anomaly_timestamps": [1763554080, 1763554140, 1763554200],
        "items": [
            {
                "id": 1,
                "name": "CPU使用率",
                "expression": "a > 80",
                "functions": [],
                "origin_sql": "",
                "query_configs": [
                    {
                        "alias": "a",
                        "metric_id": "system.cpu_summary.usage",
                        "functions": [],
                        "agg_method": "AVG",
                        "agg_interval": 60,
                        "agg_dimension": {},
                        "agg_condition": []
                    }
                ]
            }
        ]
    }
}
```
