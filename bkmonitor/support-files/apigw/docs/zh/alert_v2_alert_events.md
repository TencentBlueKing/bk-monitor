### 功能描述

【告警V2】告警事件列表查询

### 请求参数

| 字段       | 类型        | 必选 | 描述                                                               |
|----------|-----------|----|------------------------------------------------------------------|
| alert_id | str       | 是  | 告警ID                                                             |
| sources  | list[str] | 否  | 事件来源列表，可选值：HOST（主机）、BCS（容器）、BKCI（蓝盾）、DEFAULT（业务上报），不传或为空表示查询所有来源 |
| limit    | int       | 否  | 返回事件的最大数量，默认为10                                                  |
| offset   | int       | 否  | 分页偏移量，默认为0                                                       |

### 请求参数示例

```json
{
    "alert_id": "f1c6877ba046e2d32bfd8393b4dd26f7.1763554080.2860.2978.2",
    "sources": ["HOST", "BCS"],
    "limit": 10,
    "offset": 0
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 返回数据   |

#### data 字段说明

| 字段           | 类型   | 描述          |
|--------------|------|-------------|
| list         | list | 事件列表        |
| query_config | dict | 查询配置，用于前端跳转 |

#### list 元素字段说明

| 字段            | 类型   | 描述          |
|---------------|------|-------------|
| time          | dict | 事件时间信息      |
| type          | dict | 事件等级信息      |
| event_name    | dict | 事件名称信息      |
| event.content | dict | 事件内容信息      |
| target        | dict | 目标对象信息      |
| source        | dict | 事件来源信息      |
| _meta         | dict | 元数据信息       |
| origin_data   | dict | 原始事件数据（扁平化） |

#### time 字段说明

| 字段    | 类型  | 描述                |
|-------|-----|-------------------|
| value | int | 事件时间戳（Unix时间戳，毫秒） |
| alias | int | 时间戳别名（同value）     |

#### type 字段说明

| 字段    | 类型     | 描述                            |
|-------|--------|-------------------------------|
| value | string | 事件等级值（normal/warning/default） |
| alias | string | 事件等级别名                        |

#### event_name 字段说明

| 字段    | 类型     | 描述     |
|-------|--------|--------|
| value | string | 事件名称值  |
| alias | string | 事件名称别名 |

#### event.content 字段说明

| 字段     | 类型     | 描述                          |
|--------|--------|-----------------------------|
| value  | string | 事件内容值                       |
| alias  | string | 事件内容别名                      |
| detail | dict   | 事件内容详情（字段根据事件来源不同而不同，见下方说明） |

##### event.content.detail 字段说明

detail 字段的内容根据事件来源（source）不同而不同：

**主机事件（source=HOST）** 包含字段：

- `target` - 目标主机信息（dict，包含value、alias、url）
- `event.content` - 事件内容信息（dict，包含label、value、alias）
- 其他字段根据具体事件类型而定（如：OOM事件包含进程信息，磁盘事件包含磁盘路径等）

**容器事件（source=BCS）** 包含字段：

- `bcs_cluster_id` - 集群ID（dict，包含label、value、alias、url）
- `namespace` - 命名空间（dict，包含label、value、alias、url）
- `kind` - 资源类型（dict，包含label、value、alias）
- `name` - 资源名称（dict，包含label、value、alias、url）
- `host` - 主机信息（dict，包含label、value、alias、url）
- `event.content` - 事件内容信息（dict，包含label、value、alias）

**蓝盾事件（source=BKCI）** 包含字段：

- `pipelineName` - 流水线名称（dict，包含label、value、alias、url）
- `projectId` - 项目ID（dict，包含label、value、alias）
- `buildId` - 构建ID（dict，包含label、value、alias）
- `pipelineId` - 流水线ID（dict，包含label、value、alias）
- `duration` - 持续时间（dict，包含label、value、alias）
- `trigger` - 触发方式（dict，包含label、value、alias）
- `triggerUser` - 触发用户（dict，包含label、value、alias）
- `status` - 状态（dict，包含label、value、alias）
- `startTime` - 开始时间（dict，包含label、value、alias）

**业务上报事件（source=DEFAULT）** 包含字段：

- `event.content` - 事件内容信息（dict，包含label、value、alias）
- 其他字段根据业务自定义上报的数据而定

#### target 字段说明

| 字段    | 类型     | 描述     |
|-------|--------|--------|
| value | string | 目标对象值  |
| alias | string | 目标对象别名 |
| url   | string | 目标对象链接 |

#### source 字段说明

| 字段    | 类型     | 描述                           |
|-------|--------|------------------------------|
| value | string | 事件来源值（HOST/BCS/BKCI/DEFAULT） |
| alias | string | 事件来源别名（如：主机/容器/蓝盾/业务上报）      |

#### _meta 字段说明

| 字段           | 类型     | 描述     |
|--------------|--------|--------|
| __doc_id     | string | 文档唯一标识 |
| __source     | string | 事件来源   |
| __domain     | string | 事件域    |
| __data_label | string | 数据标签   |
| _time_       | int    | 时间戳    |

#### origin_data 字段说明

原始事件数据为扁平化的字典结构，包含所有原始字段（如：time、dimensions.xxx、tags.xxx等），字段根据事件来源和类型不同而不同。

#### query_config 字段说明

| 字段            | 类型         | 描述              |
|---------------|------------|-----------------|
| bk_biz_id     | int        | 业务ID            |
| start_time    | int        | 开始时间（Unix时间戳，秒） |
| end_time      | int        | 结束时间（Unix时间戳，秒） |
| limit         | int        | 返回事件的最大数量       |
| offset        | int        | 分页偏移量           |
| query_configs | list[dict] | 查询配置列表          |
| app_name      | string     | 应用名称（APM告警场景）   |
| service_name  | string     | 服务名称（APM告警场景）   |

#### query_configs 元素字段说明

| 字段                | 类型         | 描述                                          |
|-------------------|------------|---------------------------------------------|
| data_source_label | string     | 数据源标签（如：custom、bk_monitor_collector、bk_apm） |
| data_type_label   | string     | 数据类型标签（如：event、log）                         |
| table             | string     | 结果表ID                                       |
| where             | list[dict] | 过滤条件列表                                      |
| filter_dict       | dict       | 过滤条件字典                                      |
| query_string      | str        | 查询语句（请优先使用 where）                           |
| time_field        | string     | 时间字段名                                       |

#### where 元素字段说明

| 字段        | 类型     | 描述                       |
|-----------|--------|--------------------------|
| key       | string | 字段名                      |
| method    | string | 匹配方法（如：eq、neq、contains等） |
| value     | list   | 匹配值列表                    |
| condition | string | 条件关系（and/or）             |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "list": [
            {
                "time": {
                    "value": 1763554080000,
                    "alias": 1763554080000
                },
                "type": {
                    "value": "warning",
                    "alias": "warning"
                },
                "event_name": {
                    "value": "磁盘只读",
                    "alias": "磁盘只读"
                },
                "event.content": {
                    "value": "磁盘空间不足导致只读",
                    "alias": "磁盘空间不足导致只读",
                    "detail": {
                        "event.content": {
                            "label": "内容",
                            "value": "磁盘空间不足导致只读",
                            "alias": "磁盘空间不足导致只读"
                        }
                    }
                },
                "target": {
                    "value": "0:127.0.0.1",
                    "alias": "0:127.0.0.1",
                    "url": ""
                },
                "source": {
                    "value": "HOST",
                    "alias": "主机/主机"
                },
                "_meta": {
                    "__doc_id": "abc123def456",
                    "__source": "HOST",
                    "__domain": "HOST",
                    "__data_label": "custom_event",
                    "_time_": 1763554080000
                },
                "origin_data": {
                    "time": 1763554080000,
                    "event_name": "磁盘只读",
                    "target": "0:127.0.0.1",
                    "dimensions.ip": "127.0.0.1",
                    "dimensions.bk_cloud_id": 0,
                    "dimensions.disk": "/data"
                }
            },
            {
                "time": {
                    "value": 1763554140000,
                    "alias": 1763554140000
                },
                "type": {
                    "value": "normal",
                    "alias": "normal"
                },
                "event_name": {
                    "value": "Pod重启",
                    "alias": "Pod重启"
                },
                "event.content": {
                    "value": "Pod异常重启",
                    "alias": "Pod异常重启",
                    "detail": {
                        "event.content": {
                            "label": "内容",
                            "value": "Pod异常重启",
                            "alias": "Pod异常重启"
                        }
                    }
                },
                "target": {
                    "value": "BCS-K8S-00000",
                    "alias": "BCS-K8S-00000",
                    "url": ""
                },
                "source": {
                    "value": "BCS",
                    "alias": "容器/容器"
                },
                "_meta": {
                    "__doc_id": "def789ghi012",
                    "__source": "BCS",
                    "__domain": "BCS",
                    "__data_label": "bcs_event",
                    "_time_": 1763554140000
                },
                "origin_data": {
                    "time": 1763554140000,
                    "event_name": "Pod重启",
                    "target": "BCS-K8S-00000",
                    "dimensions.namespace": "default",
                    "dimensions.pod": "nginx-pod"
                }
            }
        ],
        "query_config": {
            "bk_biz_id": 2,
            "start_time": 1763553000,
            "end_time": 1763557000,
            "limit": 10,
            "offset": 0,
            "query_configs": [
                {
                    "data_source_label": "custom",
                    "data_type_label": "event",
                    "table": "gse_system_event",
                    "where": [
                        {
                            "key": "source",
                            "method": "eq",
                            "value": ["HOST", "BCS"],
                            "condition": "and"
                        }
                    ],
                    "filter_dict": {},
                    "time_field": "time"
                }
            ]
        }
    }
}
```
