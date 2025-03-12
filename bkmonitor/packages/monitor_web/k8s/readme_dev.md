## 接口列表

### ListBCSCluster

获取集群列表

#### 请求方法

GET

#### 请求 url

rest/v2/k8s/resources/list_bcs_cluster/

#### 请求参数

| 字段      | 类型 | 必选 | 描述    |
|-----------|------|-----|-------|
| bk_biz_id | int  | 是   | 业务 ID |

#### 请求示例

```json
{"bk_biz_id": 2}
```

#### 响应示例

```json
[
  {
    "id": "BCS-K8S-00000",
    "name": "蓝鲸7.0(BCS-K8S-00000)"
  }
]
```

### ScenarioMetricList

获取指定场景的指标列表

目前支持性能和网络两种场景

#### 请求方法

GET

#### 请求 url

rest/v2/k8s/resources/scenario_metric_list/

#### 请求参数

| 字段      | 类型 | 必选 | 描述                                   |
|-----------|------|-----|--------------------------------------|
| bk_biz_id | int  | 是   | 业务 id                                |
| scenario  | str  | 是   | 接入场景, \["performance", "network"\] |

#### 请求示例

##### 获取性能场景的指标

```json
{
    "bk_biz_id": 2,
    "scenario": "performance"
}
```

##### 获取网络场景的指标

```json
{
    "bk_biz_id": 2,
    "scenario": "network"
}
```

#### 响应示例

##### 获取性能场景的指标

```json
[
  {
    "id": "CPU",
    "name": "CPU",
    "children": [
      {
        "id": "container_cpu_usage_seconds_total",
        "name": "CPU使用量",
        "unit": "core",
        "unsupported_resource": []
      },
      {
        "id": "kube_pod_cpu_requests_ratio",
        "name": "CPU request使用率",
        "unit": "percentunit",
        "unsupported_resource": [
          "namespace"
        ]
      },
      {
        "id": "kube_pod_cpu_limits_ratio",
        "name": "CPU limit使用率",
        "unit": "percentunit",
        "unsupported_resource": [
          "namespace"
        ]
      },
      {
        "id": "container_cpu_cfs_throttled_ratio",
        "name": "CPU 限流占比",
        "unit": "percentunit",
        "unsupported_resource": []
      }
    ]
  },
  {
    "id": "memory",
    "name": "内存",
    "children": [
      {
        "id": "container_memory_working_set_bytes",
        "name": "内存使用量(Working Set)",
        "unit": "bytes",
        "unsupported_resource": []
      },
      {
        "id": "kube_pod_memory_requests_ratio",
        "name": "内存 request使用率",
        "unit": "percentunit",
        "unsupported_resource": [
          "namespace"
        ]
      },
      {
        "id": "kube_pod_memory_limits_ratio",
        "name": "内存 limit使用率",
        "unit": "percentunit",
        "unsupported_resource": [
          "namespace"
        ]
      }
    ]
  },
  {
    "id": "network",
    "name": "流量",
    "children": [
      {
        "id": "container_network_receive_bytes_total",
        "name": "网络入带宽",
        "unit": "Bps",
        "unsupported_resource": [
          "container"
        ]
      },
      {
        "id": "container_network_transmit_bytes_total",
        "name": "网络出带宽",
        "unit": "Bps",
        "unsupported_resource": [
          "container"
        ]
      }
    ]
  }
]
```

##### 获取网络场景的指标

```json
[
  {
    "id": "traffic",
    "name": "流量",
    "children": [
      {
        "id": "nw_container_network_receive_bytes_total",
        "name": "网络入带宽",
        "unit": "Bps",
        "unsupported_resource": []
      },
      {
        "id": "nw_container_network_transmit_bytes_total",
        "name": "网络出带宽",
        "unit": "Bps",
        "unsupported_resource": [
          "namespace"
        ]
      }
    ]
  },
  {
    "id": "packets",
    "name": "包量",
    "children": [
      {
        "id": "nw_container_network_receive_packets_total",
        "name": "网络入包量",
        "unit": "pps",
        "unsupported_resource": []
      },
      {
        "id": "nw_container_network_transmit_packets_total",
        "name": "网络出包量",
        "unit": "pps",
        "unsupported_resource": []
      },
      {
        "id": "nw_container_network_receive_errors_total",
        "name": "网络入丢包量",
        "unit": "pps",
        "unsupported_resource": []
      },
      {
        "id": "nw_container_network_transmit_errors_total",
        "name": "网络出丢包量",
        "unit": "pps",
        "unsupported_resource": []
      },
      {
        "id": "nw_container_network_receive_errors_ratio",
        "name": "网络入丢包率",
        "unit": "pps",
        "unsupported_resource": []
      },
      {
        "id": "nw_container_network_transmit_errors_ratio",
        "name": "网络出丢包率",
        "unit": "pps",
        "unsupported_resource": []
      }
    ]
  }
]
```

### ListK8SResources

获取 k8s 集群资源列表

#### 请求方法

POST

#### 请求 url

rest/v2/k8s/resources/list_resources/

#### 请求参数

| 字段           | 类型 | 必选 | 描述                                                                            |
|----------------|------|-----|-------------------------------------------------------------------------------|
| bk_biz_id      | int  | 是   | 业务 id                                                                         |
| bcs_cluster_id | str  | 是   | 集群id                                                                          |
| filter_dict    | dict | 否   | 精确过滤字典                                                                    |
| resource_type  | str  | 是   | 资源类型, \["pod", "workload", "namespace", "container", "ingress", "service"\] |
| query_string   | str  | 否   | 名字过滤, 用于模糊查询                                                          |
| start_time     | int  | 是   | 开始时间                                                                        |
| end_time       | int  | 是   | 结束时间                                                                        |
| scenario       | str  | 是   | 场景, \["performance", "network"\]                                              |
| with_history   | bool | 否   | 是否查询包含历史的资源                                                          |
| page_size      | int  | 否   | 分页大小, 默认为5                                                               |
| page           | int  | 否   | 页数, 默认为1                                                                   |
| page_type      | str  | 否   | 分页标识, 默认为"scrolling", \["scrolling", "traditional"\]                     |
| order_by       | str  | 否   | 排序, 默认为"desc", \["desc", "asc"\]                                           |
| method         | str  | 否   | 聚合方法, 默认"sum", \["max", "avg", "min", "sum", "count"\]                    |
| column         | str  | 否   | [指标名](#场景指标列表), 默认为"container_cpu_usage_seconds_total"              |

#### 示例

##### 示例 1

TODO 等待真实数据进行不全

返回pod资源类型5条内容

###### 请求响应

```json
{
  "bk_biz_id": 2,
  "bcs_cluster_id": "BCS-K8S-00000",
  "resource_type": "pod",
  "start_time": 1732240257,
  "end_time": 1732243857,
  "sernario": "performance"
}
```

###### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": 163,
    "items": [
      {
        "pod": "pod-1",
        "namespace": "default",
        "workload": "Deployment:workload-1"
      },
      {
        "pod": "pod-2",
        "namespace": "default",
        "workload": "Deployment:workload-1"
      },
      {
        "pod": "pod-3",
        "namespace": "default",
        "workload": "Deployment:workload-2"
      },
      {
        "pod": "pod-4",
        "namespace": "default",
        "workload": "Deployment:workload-2"
      },
      {
        "pod": "pod-5",
        "namespace": "default",
        "workload": "Deployment:workload-3"
      }
    ]
  }
}
```

### GetResourceDetail

获取指定资源的详情

#### 请求方法

GET

#### 请求 url

rest/v2/k8s/resources/get_resource_detail

#### 请求参数

| 字段           | 类型 | 必选 | 描述                                                   |
|----------------|------|-----|------------------------------------------------------|
| bk_biz_id      | int  | 是   | 业务 id                                                |
| bcs_cluster_id | str  | 是   | 集群id                                                 |
| namespace      | str  | 是   | 命名空间                                               |
| resource_type  | str  | 是   | 资源类型,\["pod", "workload", "container", "cluster"\] |
| pod_name       | str  | 否   | pod 名称                                               |
| container_name | str  | 否   | container 名称                                         |
| workload_name  | str  | 否   | workload 名称                                          |
| workload_type  | str  | 否   | workload 类型                                          |

#### 请求示例

```json
{
  "bk_biz_id": 2,
  "pod_name": "python-backend--0--session-default---experiment-clear-backbvcgm",
  "resource_type": "pod",
  "namespace": "aiops-default",
  "bcs_cluster_id": "BCS-K8S-00000"
}
```

#### 响应示例

```json
[
  {
    "key": "name",
    "name": "Pod名称",
    "type": "string",
    "value": "python-backend--0--session-default---experiment-clear-backbvcgm"
  },
  {
    "key": "status",
    "name": "运行状态",
    "type": "string",
    "value": "Running"
  },
  {
    "key": "ready",
    "name": "是否就绪(实例运行数/期望数)",
    "type": "string",
    "value": "1/1"
  },
  {
    "key": "bcs_cluster_id",
    "name": "集群ID",
    "type": "string",
    "value": "BCS-K8S-00000"
  },
  {
    "key": "bk_cluster_name",
    "name": "集群名称",
    "type": "string",
    "value": "蓝鲸7.0"
  },
  {
    "key": "namespace",
    "name": "NameSpace",
    "type": "string",
    "value": "aiops-default"
  },
  {
    "key": "total_container_count",
    "name": "容器数量",
    "type": "string",
    "value": 1
  },
  {
    "key": "restarts",
    "name": "重启次数",
    "type": "number",
    "value": 0
  },
  {
    "key": "monitor_status",
    "name": "采集状态",
    "type": "status",
    "value": {
      "type": "success",
      "text": "正常"
    }
  },
  {
    "key": "age",
    "name": "存活时间",
    "type": "string",
    "value": "2 months"
  },
  {
    "key": "request_cpu_usage_ratio",
    "name": "CPU使用率(request)",
    "type": "progress",
    "value": {
      "value": 0.7,
      "label": "0.7%",
      "status": "SUCCESS"
    }
  },
  {
    "key": "limit_cpu_usage_ratio",
    "name": "CPU使用率(limit)",
    "type": "progress",
    "value": {
      "value": 0.35,
      "label": "0.35%",
      "status": "SUCCESS"
    }
  },
  {
    "key": "request_memory_usage_ratio",
    "name": "内存使用率(request)",
    "type": "progress",
    "value": {
      "value": 12.12,
      "label": "12.12%",
      "status": "SUCCESS"
    }
  },
  {
    "key": "limit_memory_usage_ratio",
    "name": "内存使用率(limit) ",
    "type": "progress",
    "value": {
      "value": 6.06,
      "label": "6.06%",
      "status": "SUCCESS"
    }
  },
  {
    "key": "resource_usage_cpu",
    "name": "CPU使用量",
    "type": "string",
    "value": "7m"
  },
  {
    "key": "resource_usage_memory",
    "name": "内存使用量",
    "type": "string",
    "value": "497MB"
  },
  {
    "key": "resource_usage_disk",
    "name": "磁盘使用量",
    "type": "string",
    "value": "2GB"
  },
  {
    "key": "resource_requests_cpu",
    "name": "cpu request",
    "type": "string",
    "value": "1000m"
  },
  {
    "key": "resource_limits_cpu",
    "name": "cpu limit",
    "type": "string",
    "value": "2000m"
  },
  {
    "key": "resource_requests_memory",
    "name": "memory request",
    "type": "string",
    "value": "4GB"
  },
  {
    "key": "resource_limits_memory",
    "name": "memory limit",
    "type": "string",
    "value": "8GB"
  },
  {
    "key": "pod_ip",
    "name": "Pod IP",
    "type": "string",
    "value": "127.0.0.1"
  },
  {
    "key": "node_ip",
    "name": "节点IP",
    "type": "string",
    "value": "127.0.0.1"
  },
  {
    "key": "node_name",
    "name": "节点名称",
    "type": "string",
    "value": "node-127-0-0-1"
  },
  {
    "key": "workload",
    "name": "工作负载",
    "type": "string",
    "value": "Deployment:python-backend--0--session-default---experiment-clear-backend---owned"
  },
  {
    "key": "label_list",
    "name": "标签",
    "type": "kv",
    "value": []
  },
  {
    "key": "images",
    "name": "镜像",
    "type": "list",
    "value": [
      "mirrors.tencent.com/build/blueking/bkbase-aiops:1.12.30"
    ]
  }
]
```

### WorkloadOverview

#### 请求方法

GET

#### 请求 url

rest/v2/k8s/resources/workload_overview/

#### 请求参数

| 字段           | 类型 | 必选 | 描述     |
|----------------|------|-----|--------|
| bk_biz_id      | int  | 是   | 业务 id  |
| bcs_cluster_id | str  | 是   | 集群id   |
| namespace      | str  | 否   | 命名空间 |
| query_string   | str  | 否   | 名字过滤 |

#### 请求示例

```json
{
  "bk_biz_id": 2,
  "bcs_cluster_id": "BCS-K8S-00000"
}
```

#### 响应示例

```json
[
  [ "Deployment", 608 ],
  [ "StatefulSet", 68 ],
  [ "DaemonSet", 11 ],
  [ "Job", 628 ],
  [ "CronJob", 7 ]
]
```

### ResourceTrendResource

#### 请求方法

POST

#### 请求 url

rest/v2/k8s/resources/resource_trend/

#### 请求参数

| 字段           | 类型        | 必选 | 描述                                                                            |
|----------------|-------------|-----|-------------------------------------------------------------------------------|
| bk_biz_id      | int         | 是   | 业务 id                                                                         |
| filter_dict    | dict        | 否   | 精确过滤字典                                                                    |
| bcs_cluster_id | str         | 是   | 集群id                                                                          |
| column         | str         | 是   | [指标名](#场景指标列表)                                                         |
| resource_type  | str         | 是   | 资源类型, \["pod", "workload", "namespace", "container", "ingress", "service"\] |
| method         | str         | 是   | 聚合方法, \["max", "avg", "min", "sum", "count"\]                               |
| resource_list  | List\[str\] | 是   | 资源列表                                                                        |
| start_time     | int         | 是   | 开始时间                                                                        |
| end_time       | int         | 是   | 结束时间                                                                        |
| scenario       | str         | 是   | 接入场景, \["performance", "network"\]                                          |

#### 请求示例

```json
{
    "scenario": "performance",
    "bcs_cluster_id": "BCS-K8S-00000",
    "start_time": 1741597068,
    "end_time": 1741600668,
    "filter_dict": {},
    "column": "container_cpu_cfs_throttled_ratio",
    "method": "sum",
    "resource_type": "namespace",
    "resource_list": [
        "bkmonitor-operator",
        "bkbase-flink",
        "bkmonitor-operator-bkte",
        "bkbase",
        "blueking",
        "deepflow",
        "trpc-micros-stag",
        "kube-system",
        "bk-bscp",
        "bk-system",
        "aiops-default",
        "bcs-system",
        "bkapp-bkaidev-prod",
        "bkapp-csu230208-stag",
        "bkapp-bk0us0cmdb0us0saas-prod",
        "bkapp-bkbase0us0admin0us0t-m-backend-stag",
        "bkapp-bk0us0dataweb-m-aiops-prod",
        "bkapp-bk0us0sops-m-pipeline-prod",
        "bkapp-bk0us0sops-m-pipeline-stag",
        "bkapp-csu230512-stag"
    ],
    "bk_biz_id": 2
}
```

#### 响应示例

```json
[
  {
    "resource_name": "aiops-default",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          0.002558,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "bcs-system",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          0,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "bk-bscp",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          0.466171,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "bk-system",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          0.013289,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "bkapp-bk0us0cmdb0us0saas-prod",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          0,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "bkapp-bk0us0dataweb-m-aiops-prod",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          0,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "bkapp-bk0us0sops-m-pipeline-prod",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          0,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "bkapp-bk0us0sops-m-pipeline-stag",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          0,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "bkapp-bkaidev-prod",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          0,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "bkapp-bkbase0us0admin0us0t-m-backend-stag",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          0,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "bkapp-csu230208-stag",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          0,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "bkapp-csu230512-stag",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          0,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "bkbase",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          4.702747,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "bkbase-flink",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          7.459486,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "bkmonitor-operator",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          18.265733,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "bkmonitor-operator-bkte",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          5.414493,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "blueking",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          4.240089,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "deepflow",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          1.544696,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "kube-system",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          0.556802,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  },
  {
    "resource_name": "trpc-micros-stag",
    "container_cpu_cfs_throttled_ratio": {
      "datapoints": [
        [
          1.086197,
          1741600560000
        ]
      ],
      "unit": "percentunit",
      "value_title": "CPU 限流占比"
    }
  }
]
```

## 场景指标列表

### 性能场景指标

| 值                                     | 描述                    |
|----------------------------------------|-----------------------|
| container_cpu_usage_seconds_total      | CPU使用量               |
| kube_pod_cpu_requests_ratio            | CPU request使用率       |
| kube_pod_cpu_limits_ratio              | CPU limit使用率         |
| container_memory_working_set_bytes     | 内存使用量(Working Set) |
| kube_pod_memory_requests_ratio         | 内存 request使用率      |
| kube_pod_memory_limits_ratio           | 内存 limit使用率        |
| container_cpu_cfs_throttled_ratio      | CPU 限流占比            |
| container_network_transmit_bytes_total | 网络出带宽              |
| container_network_receive_bytes_total  | 网络入带宽              |

### 网络场景指标

| 值                                          | 描述         |
|---------------------------------------------|------------|
| nw_container_network_transmit_bytes_total   | 网络出带宽   |
| nw_container_network_receive_bytes_total    | 网络入带宽   |
| nw_container_network_receive_errors_ratio   | 网络入丢包率 |
| nw_container_network_transmit_errors_ratio  | 网络出丢包率 |
| nw_container_network_transmit_errors_total  | 网络出丢包量 |
| nw_container_network_receive_errors_total   | 网络入丢包量 |
| nw_container_network_receive_packets_total  | 网络入包量   |
| nw_container_network_transmit_packets_total | 网络出包量   |

## 错误定义

### k8s.core.errors.K8sResourceNotFound

找不到对应的资源类型

### k8s.core.errors.MultiWorkloadError

不支持多个 workload 查询

## 过滤器定义

### k8s.core.filters.filter_options

全局字典，用于存储注册继承于 [ResourceFilter](#k8scorefiltersresourcefilterobject) 的 [过滤器子类](#过滤器子类)。
通过 `resource_type`，可以将不同类型的过滤器与它们对应的类关联起来。

### k8s.core.filters.ResourceFilter(object)

过滤器的基类

```python
def filter_uid(self):
    """
    返回一个唯一的标识符  
    由 resource_type + filter_field + value 构成
    """

def filter_dict(self) -> Dict:
    """
    过滤条件构建  
    根据 value 的长度和 fuzzy 标志，它构建相应的查询条件

    如果只有一个值且 fuzzy 为 True，则使用模糊匹配。  
    如果只有一个值且 fuzzy 为 False，则直接匹配。  
    如果有多个值，则使用 __in 进行查询。
    """

def filter_string(self) -> str:
    """
    用于PromQL条件生成

    根据 value 的长度和 fuzzy 标志，构建相应的查询字符串：
    如果 fuzzy 为 True => 'key=~"value1|value2|..."''
    如果只有一个值，构建简单的等式 => 'key=value'
    如果有多个值，构建正则表达式匹配 => 'key=~"^(value1|value2|...)$"''
    如果filter_dict有多个key => 'key1=value1, key2=value2'
    """
```

### 过滤器子类

| ClassName              | resource_type     | filter_field   |
|------------------------|-------------------|----------------|
| NamespaceFilter        | namespace         | namespace      |
| PodFilter              | pod               | pod_name       |
| WorkloadFilter         | workload          | workload       |
| ContainerFilter        | container         | container_name |
| DefaultContainerFilter | container_exclude | container_name |
| NodeFilter             | node              | node           |
| ClusterFilter          | bcs_cluster_id    | bcs_cluster_id |
| SpaceFilter            | bk_biz_id         | bk_biz_id      |
| IngressFilter          | ingress           | ingress        |
| ServiceFilter          | service           | service        |


### k8s.core.filters.register_filter(filter_cls)

一个装饰器
用于注册 [过滤器类 ResourceFilter](#过滤器子类)。

它接受一个过滤器类 `filter_cls:ResourceFilter` 作为参数，并将其 `resource_type` 属性和类本身存储在 [`filter_options`](#k8scorefiltersfilter_options) 字典中。这使得在需要时可以方便地查找和使用不同的过滤器。

### k8s.core.filters.load_resource_filter(resource_type: str, filter_value, fuzzy=False)

根据给定的资源类型、过滤值和模糊匹配标志来加载对应的资源过滤器

例如：当 `resource_type="pod"` 返回 `PodFilter()`


## 资源类定义

### k8s.core.meta.FilterCollection(object)

用于管理多个过滤条件，支持添加和移除[过滤器](#k8scorefiltersresourcefilterobject)。它可以用于构建复杂的查询

```python
class FilterCollection(object):
    """
    用于管理多个过滤条件，支持添加和移除过滤器。它可以用于构建复杂的查询
    过滤查询集合

    内部过滤条件是一个字典， 可以通过 add、remove 来增删过滤条件
    """
    def filter_queryset(self):
        """
        通过遍历 filters 中的每个过滤器对象，应用过滤条件，最终返回过滤后的 queryset
        """

    def transform_filter_dict(self, filter_obj) -> Dict:
        """
        将过滤器对象的过滤条件转换为适合ORM查询的格式
        """
        
    def filter_string(self, exclude="") -> str:
        """
        生成一个过滤条件的字符串。
        如果 exclude 参数指定，则跳过以该参数开头的过滤器。
        如果有多个 workload ID，则只取第一个进行查询。
        """
```

### k8s.core.meta.K8sResourceMeta(object)

资源元数据基类
定义了获取数据的来源有数据库和 prom 历史数据两个地方
根据不同的指标 `meta_prom_with_**` 通过构建 promql 查询语句来获取数据

```python
class K8sResourceMeta(object):
    """
    资源元数据基类
    """

    filter: FilterCollection = None
    resource_field = ""
    resource_class = None
    column_mapping = {}  # 数据库表字段映射
    only_fields = []  # 指定查询时只关注的字段。
    method = ""  # 聚合方法（如 sum、avg 等）。

    def __init__(self, bk_biz_id, bcs_cluster_id):
        """
        接收集群id 和 业务id
        设置默认过滤器 FilterCollection()
        初始化聚合间隔和方法
        """
    
    def setup_filter(self):
        """
        初始化过滤器，并添加初始过滤条件 bk_biz_id, bcs_cluster_id, container_exclude 
        """

    def set_agg_interval(self, start_time, end_time):
        """
        根据不同的聚合方法（如 count、sum 等）设置聚合查询的时间间隔。
        """
    
    def set_agg_method(self, method: Literal["max", "avg", "min", "sum", "count"] = "sum"):
        """
        设置聚合方法，并在方法为 count 时重置聚合间隔。
        """
    
    def get_form_meta(self):
        """
        资源数据获取方式
        
        通过ORM，从数据库获取
        """

    def get_from_promql(self, start_time, end_time, order_by="", page_size=20, method="sum"):
        """
        资源数据获取方式
        
        通过构建PromQL进行获取
        核心是通过 meta_prom_by_sort 生成对应指标的PromQL
        """
    def meta_prom_by_sort(self, order_by="", page_size=20) -> str:
        """
        调用 meta_prom_with_{order_by.strip("-")} 获取不同指标的PromQL
        并在PromQL最外层添加排序和查询数量设置
        """

    def meta_prom_with_xxx(self) -> str:
        """
        构建不同指标的PromQL
        """
```

### k8s 资源子类

| ClassName        | resource_field | resource_class | column_mapping                                               |
|------------------|----------------|----------------|--------------------------------------------------------------|
| K8sNodeMeta      |                |                |                                                              |
| K8sContainerMeta | container_name | BCSContainer   | {"workload_kind": "workload_type", "container_name": "name"} |
| K8sPodMeta       | pod_name       | BCSPod         | {"workload_kind": "workload_type", "pod_name": "name"}       |
| K8sWorkloadMeta  | workload_name  | BCSWorkload    | {"workload_kind": "type", "workload_name": "name"}           |
| K8sNamespaceMeta | namespace      | NameSpace      | {}                                                           |
| K8sIngressMeta   | ingress        | BCSIngress     | {"ingress": "name"}                                          |
| K8sServiceMeta   | service        | BCSService     | {"service": "name"}                                          |

### k8s.core.meta.load_resource_meta(resource_type,bk_biz_id,bcs_cluster_id)

根据给定的资源类型和其他参数加载对应[资源元信息类](#k8s-资源子类)的实例。

| resource_type  | ClassName        |
|----------------|------------------|
| node           | K8sNodeMeta      |
| container      | K8sContainerMeta |
| container_name | K8sContainerMeta |
| pod            | K8sPodMeta       |
| pod_name       | K8sPodMeta       |
| workload       | K8sWorkloadMeta  |
| namespace      | K8sNamespaceMeta |
| ingress        | K8sIngressMeta   |
| service        | K8sServiceMeta   |

e.g. 当  `resource_type = "container"`, 返回 `K8sContainerMeta(bk_biz_id, bcs_cluster_id)`

### k8s.core.meta.NetworkWithRelation

作为一个辅助类，用于网络场景，层级关联支持

```python
def label_join(self, filter_exclude=""):
    """
    聚合和链接 ingress 和 pod 相关的指标，计算出它们之间的关系并按特定标签进行聚合。
    """

def clean_metric_name(self, metric_name):
    """
    网络场景相关的指标名都是 `nw_` 开头的，需要将 `nw_` 去掉
    """
```
