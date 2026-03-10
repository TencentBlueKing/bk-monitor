### 功能描述

【告警V2】告警事件标签详情查询

### 请求参数

| 字段         | 类型        | 必选 | 描述                                                               |
|------------|-----------|----|------------------------------------------------------------------|
| alert_id   | str       | 是  | 告警ID                                                             |
| sources    | list[str] | 否  | 事件来源列表，可选值：HOST（主机）、BCS（容器）、BKCI（蓝盾）、DEFAULT（业务上报），不传或为空表示查询所有来源 |
| interval   | int       | 否  | 汇聚周期（秒），默认为60                                                    |
| start_time | int       | 是  | 查询的开始时间戳（Unix时间戳，秒）                                              |
| limit      | int       | 否  | 返回事件的最大数量，默认为5                                                   |

### 请求参数示例

```json
{
    "alert_id": "f1c6877ba046e2d32bfd8393b4dd26f7.1763554080.2860.2978.2",
    "sources": ["HOST"],
    "interval": 60,
    "start_time": 1763554080,
    "limit": 5
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

data 是一个字典，包含两个key：`Warning` 和 `All`，分别表示告警类型事件和所有类型事件的统计信息。

| 字段      | 类型   | 描述                 |
|---------|------|--------------------|
| Warning | dict | 告警类型（Warning）事件的详情 |
| All     | dict | 所有类型事件的详情          |

#### Warning/All 字段说明

| 字段    | 类型   | 描述                                  |
|-------|------|-------------------------------------|
| time  | int  | 查询的开始时间戳（Unix时间戳，秒）                 |
| total | int  | 该时间段内的事件总数                          |
| topk  | list | TopN事件列表（仅当total > 20时返回，按事件数量倒序排列） |
| list  | list | 事件详情列表（仅当total <= 20时返回）            |

#### topk 元素字段说明（当total > 20时）

| 字段          | 类型     | 描述           |
|-------------|--------|--------------|
| domain      | dict   | 事件领域信息       |
| source      | dict   | 事件来源信息       |
| event_name  | dict   | 事件名称信息       |
| count       | int    | 事件数量         |
| proportions | string | 事件占比（百分比字符串） |

##### domain 字段说明

| 字段    | 类型     | 描述                           |
|-------|--------|------------------------------|
| value | string | 领域值（K8S/CICD/SYSTEM/DEFAULT） |
| alias | string | 领域别名（显示名称）                   |

##### source 字段说明

| 字段    | 类型     | 描述                         |
|-------|--------|----------------------------|
| value | string | 来源值（HOST/BCS/BKCI/DEFAULT） |
| alias | string | 来源别名（显示名称）                 |

##### event_name 字段说明

| 字段    | 类型     | 描述           |
|-------|--------|--------------|
| value | string | 事件名称原始值      |
| alias | string | 事件名称别名（显示名称） |

#### list 元素字段说明（当total <= 20时）

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

##### time 字段说明

| 字段    | 类型  | 描述                |
|-------|-----|-------------------| 
| value | int | 事件时间戳（Unix时间戳，毫秒） |
| alias | int | 时间戳别名（同value）     |

##### type 字段说明

| 字段    | 类型     | 描述                            |
|-------|--------|-------------------------------| 
| value | string | 事件等级值（normal/warning/default） |
| alias | string | 事件等级别名                        |

##### event_name 字段说明

| 字段    | 类型     | 描述     |
|-------|--------|--------|
| value | string | 事件名称值  |
| alias | string | 事件名称别名 |

##### event.content 字段说明

| 字段     | 类型     | 描述                    |
|--------|--------|-----------------------|
| value  | string | 事件内容值                 |
| alias  | string | 事件内容别名                |
| detail | dict   | 事件内容详情（字段根据事件来源不同而不同） |

**event.content.detail 字段说明：**

detail 字段的内容根据事件来源（source）不同而不同：

- **主机事件（source=HOST）**：包含 target、event.content 以及特定事件类型的字段
- **容器事件（source=BCS）**：包含 bcs_cluster_id、namespace、kind、name、host、event.content
- **蓝盾事件（source=BKCI）**：包含 pipelineName、projectId、buildId、pipelineId、duration、trigger、triggerUser、status、startTime
- **业务上报事件（source=DEFAULT）**：包含 event.content 和业务自定义的字段

##### target 字段说明

| 字段    | 类型     | 描述     |
|-------|--------|--------|
| value | string | 目标对象值  |
| alias | string | 目标对象别名 |
| url   | string | 目标对象链接 |

##### source 字段说明

| 字段    | 类型     | 描述                           |
|-------|--------|------------------------------| 
| value | string | 事件来源值（HOST/BCS/BKCI/DEFAULT） |
| alias | string | 事件来源别名（如：主机/容器/蓝盾/业务上报）      |

##### _meta 字段说明

| 字段           | 类型     | 描述     |
|--------------|--------|--------|
| __doc_id     | string | 文档唯一标识 |
| __source     | string | 事件来源   |
| __domain     | string | 事件域    |
| __data_label | string | 数据标签   |
| _time_       | int    | 时间戳    |

##### origin_data 字段说明

原始事件数据为扁平化的字典结构，包含所有原始字段（如：time、dimensions.xxx、tags.xxx等），字段根据事件来源和类型不同而不同。

### 响应参数示例

#### 示例1：事件总数 > 20（返回topk）

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "Warning": {
            "time": 1763554080,
            "total": 156,
            "topk": [
                {
                    "domain": {
                        "value": "SYSTEM",
                        "alias": "系统"
                    },
                    "source": {
                        "value": "HOST",
                        "alias": "主机"
                    },
                    "event_name": {
                        "value": "disk_readonly",
                        "alias": "磁盘只读（disk_readonly）"
                    },
                    "count": 45,
                    "proportions": "28.846%"
                },
                {
                    "domain": {
                        "value": "K8S",
                        "alias": "容器"
                    },
                    "source": {
                        "value": "BCS",
                        "alias": "容器"
                    },
                    "event_name": {
                        "value": "pod_oom_killed",
                        "alias": "Pod OOM被杀（pod_oom_killed）"
                    },
                    "count": 32,
                    "proportions": "20.513%"
                }
            ]
        },
        "All": {
            "time": 1763554080,
            "total": 203,
            "topk": [
                {
                    "domain": {
                        "value": "SYSTEM",
                        "alias": "系统"
                    },
                    "source": {
                        "value": "HOST",
                        "alias": "主机"
                    },
                    "event_name": {
                        "value": "disk_readonly",
                        "alias": "磁盘只读（disk_readonly）"
                    },
                    "count": 45,
                    "proportions": "22.167%"
                },
                {
                    "domain": {
                        "value": "K8S",
                        "alias": "容器"
                    },
                    "source": {
                        "value": "BCS",
                        "alias": "容器"
                    },
                    "event_name": {
                        "value": "pod_oom_killed",
                        "alias": "Pod OOM被杀（pod_oom_killed）"
                    },
                    "count": 32,
                    "proportions": "15.764%"
                }
            ]
        }
    }
}
```

#### 示例2：事件总数 <= 20（返回list）

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "Warning": {
            "time": 1763554080,
            "total": 8,
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
                        "value": "disk_readonly",
                        "alias": "磁盘只读"
                    },
                    "event.content": {
                        "value": "磁盘空间不足导致只读",
                        "alias": "磁盘空间不足导致只读",
                        "detail": {
                            "target": {
                                "label": "目标",
                                "value": "0:127.0.0.1",
                                "alias": "0:127.0.0.1",
                                "url": ""
                            },
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
                        "__domain": "SYSTEM",
                        "__data_label": "custom_event",
                        "_time_": 1763554080000
                    },
                    "origin_data": {
                        "time": 1763554080000,
                        "event_name": "disk_readonly",
                        "target": "0:127.0.0.1",
                        "dimensions.ip": "127.0.0.1",
                        "dimensions.bk_cloud_id": 0,
                        "tags.disk": "/data"
                    }
                }
            ]
        },
        "All": {
            "time": 1763554080,
            "total": 15,
            "list": [
                {
                    "time": {
                        "value": 1763554080000,
                        "alias": 1763554080000
                    },
                    "type": {
                        "value": "normal",
                        "alias": "normal"
                    },
                    "event_name": {
                        "value": "disk_check",
                        "alias": "磁盘检查"
                    },
                    "event.content": {
                        "value": "磁盘检查正常",
                        "alias": "磁盘检查正常",
                        "detail": {
                            "target": {
                                "label": "目标",
                                "value": "0:127.0.0.1",
                                "alias": "0:127.0.0.1",
                                "url": ""
                            },
                            "event.content": {
                                "label": "内容",
                                "value": "磁盘检查正常",
                                "alias": "磁盘检查正常"
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
                        "__doc_id": "def789ghi012",
                        "__source": "HOST",
                        "__domain": "SYSTEM",
                        "__data_label": "custom_event",
                        "_time_": 1763554080000
                    },
                    "origin_data": {
                        "time": 1763554080000,
                        "event_name": "disk_check",
                        "target": "0:127.0.0.1",
                        "dimensions.ip": "127.0.0.1",
                        "dimensions.bk_cloud_id": 0,
                        "tags.disk": "/data"
                    }
                }
            ]
        }
    }
}
```
