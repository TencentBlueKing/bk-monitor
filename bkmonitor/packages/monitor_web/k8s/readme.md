
## ListBCSCluster

获取集群列表

### 请求方法

GET

### 请求 url

rest/v2/k8s/resources/list_bcs_cluster/

### 请求参数

| 字段        | 类型  | 必选  | 描述   |
| --------- | --- | --- | ---- |
| bk_biz_id | int | 是   | 业务 id |

### 请求示例

```json
{ "bk_biz_id": 2 }
```

### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [{ "id": "BCS-K8S-00000", "name": "蓝鲸7.0(BCS-K8S-00000)" }]
}
```

## WorkloadOverview

获取左侧工作负载列表的视图预览，展示不同类型的统计数量。
按照 `["Deployments","StatefulSets","DaemonSets","Jobs","CronJobs"]` 的顺序返回

### 请求方法

GET

### 请求 url

rest/v2/k8s/resources/workload_overview/

### 请求参数

| 字段             | 类型  | 必选  | 描述               |
| -------------- | --- | --- | ---------------- |
| bk_biz_id      | int | 是   | 业务 ID            |
| bcs_cluster_id | str | 是   | 集群 ID            |
| namespace      | str | 否   | 命名空间             |
| query_string   | str | 否   | workload_name 过滤 |

### 示例

#### 1. 查询集群下所有的 workload

当 `namespace` 和 `query_string` 不传时，返回该业务 - 集群下所有的 workload 的类型以及对应的数量

##### 请求示例

```json
{
  "bk_biz_id": 2,
  "bcs_cluster_id": "BCS-K8S-00000"
}
```

##### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    ["Deployments", 9],
    ["StatefulSets", 10],
    ["DaemonSets", 20],
    ["Jobs", 3],
    ["CronJobs", 5]
  ]
}
```

#### 2. 查询不到数据

当查询不到数据时，会按照顺序默认返回 0

##### 请求示例

```json
{
  "bk_biz_id": 2,
  "bcs_cluster_id": "BCS-K8S-00000",
  "namespace": "other"
}
```

##### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    ["Deployments", 0],
    ["StatefulSets", 0],
    ["DaemonSets", 0],
    ["Jobs", 0],
    ["CronJobs", 0]
  ]
}
```

## ScenarioMetricList

获取指定场景的指标列表

### 请求方法

GET

### 请求 url

rest/v2/k8s/resources/scenario_metric_list/

### 请求参数

| 字段       | 类型  | 必选  | 描述                        |
| -------- | --- | --- | ------------------------- |
| scenario | str | 是   | 接入场景。可选值为：["performance"] |

### 请求示例

```json
{
  "scenario": "performance"
}
```

### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": "CPU",
      "name": "CPU",
      "children": [
        { "id": "container_cpu_usage_seconds_total", "name": "CPU使用量" },
        { "id": "kube_pod_cpu_requests_ratio", "name": "CPU request使用率" },
        { "id": "kube_pod_cpu_limits_ratio", "name": "CPU limit使用率" }
      ]
    },
    {
      "id": "memory",
      "name": "内存",
      "children": [
        { "id": "container_memory_rss", "name": "内存使用量(rss)" },
        {
          "id": "kube_pod_memory_requests_ratio",
          "name": "内存 request使用率"
        },
        { "id": "kube_pod_memory_limits_ratio", "name": "内存 limit使用率" }
      ]
    }
  ]
}
```

## ListK8SResources

获取 k8s 集群资源列表

### 请求方法

POST

### 请求 url

rest/v2/k8s/resources/list_resources/

### 请求参数


| 字段               | 类型       | 必选    | 描述                                                                   |
| ---------------- | -------- | ----- | -------------------------------------------------------------------- |
| bk_biz_id        | id       | 是     | 业务 id                                                                |
| bcs_cluster_id   | string   | 是     | 集群 id                                                                |
| resource_type    | string   | 是     | 资源类型, 可选值为 "pod", "workload", "namespace", "container"               |
| query_string     | string   | 否     | 名字过滤                                                                 |
| filter_dict      | dict     | 否     | 精确过滤                                                                 |
| start_time       | int      | 是     | 开始时间                                                                 |
| end_time         | int      | 是     | 结束时间                                                                 |
| sernario         | str      | 是     | 场景，可选值为 "performance"                                                |
| with_history     | bool     | 否     | 历史出现过的资源, 默认为                                                        |
| page_size        | int      | 否     | 分页数量, 默认为 5, 且 with_history=false 可用                                 |
| page             | int      | 否     | 页数，默认为 1，且 with_history=false 可用                                     |
| page_type        | str      | 否     | 分页类型, 可选值为: "scrolling"(滚动分页), "traditional"(传统分页), 默认为"traditional" |

### 示例

#### 1.1. 获取所有 pod 的资源列表

##### 请求示例

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

##### 响应示例

默认返回 5 条内容
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

#### 1.2. Pod 列表中 “点击加载更多”

实际采用滚动分页的方式对剩下的数据进行请求，比如每次都刷新 20 条数据，则每次滚动只需 page + 1 即可

##### 请求示例

```json
{
  "bk_biz_id": 2,
  "bcs_cluster_id": "BCS-K8S-00000",
  "resource_type": "pod",
  "start_time": 1732240257,
  "end_time": 1732243857,
  "sernario": "performance",
  "page_size": 20,
  "page": 2,
  "page_type": "scrolling"
}
```

##### 响应示例

返回从第一页的第一条到第二页的 20 条，共 40 条数据
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
      // 省略 38 条
      {
        "pod": "pod-5",
        "namespace": "default",
        "workload": "Deployment:workload-3"
      }
    ]
  }
}
```

#### 1.3. 查询包含历史数据的 pod 列表

设置 `with_history` 为 `true` 时将返回所有的 pod 资源， 此时，`page_size`,`page`,`page_type` 将不可用

##### 请求示例

```json
{
  "bk_biz_id": 2,
  "bcs_cluster_id": "BCS-K8S-00000",
  "resource_type": "pod",
  "start_time": 1732240257,
  "end_time": 1732243857,
  "sernario": "performance",
  "with_history": true
}
```

##### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": 188,
    "items": [
      {
        "pod": "pod-1",
        "namespace": "default",
        "workload": "Deployment:workload-1"
      },
      // 省略 186 条
      {
        "pod": "pod-5",
        "namespace": "default",
        "workload": "Deployment:workload-3"
      }
    ]
  }
}
```

#### 2.1. 获取所有 workload 的资源列表

##### 请求示例

```json
{
  "bk_biz_id": 2,
  "bcs_cluster_id": "BCS-K8S-00000",
  "resource_type": "workload",
  "start_time": 1732240257,
  "end_time": 1732243857,
  "sernario": "performance"
}
```

##### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": 30,
    "items": [
      {
        "namespace": "default",
        "workload": "Deployment:workload-1"
      },
      {
        "namespace": "demo",
        "workload": "Deployment:workload-1"
      },
      {
        "namespace": "demo",
        "workload": "Deployment:workload-2"
      }
      // ...
    ]
  }
}
```

#### 2.2. 获取指定 namespace 下的 workload 资源列表

##### 请求示例

```json
{
  "bk_biz_id": 2,
  "bcs_cluster_id": "BCS-K8S-00000",
  "resource_type": "workload",
  "start_time": 1732240257,
  "end_time": 1732243857,
  "sernario": "performance",
  "filter_dict": {
    "namespace": "default"
  }
}
```

##### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": 2,
    "items": [
      {
        "namespace": "default",
        "workload": "Deployment:workload-1"
      },
      {
        "namespace": "default",
        "workload": "Deployment:workload-2"
      }
    ]
  }
}
```

#### 2.3. 获取 workload 指定某一个类型的的列表

##### 请求示例

在 `filter_dict["workload"]` 中采用 `<type>:` 可以查询指定类型的列表
```json
{
  "bk_biz_id": 2,
  "bcs_cluster_id": "BCS-K8S-00000",
  "resource_type": "workload",
  "start_time": 1733894974,
  "end_time": 1733898574,
  "scenario": "performance",
  "filter_dict": {
    "workload": "Deployment:"
  }
}

```

##### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": 554,
    "items": [
      {
        "namespace": "bkbase",
        "workload": "Deployment:bkbase-flinksql-batch"
      },
      {
        "namespace": "bkapp-qywx-open-plugin-stag",
        "workload": "Deployment:bkapp-qywx-open-plugin-stag--web"
      },
      {
        "namespace": "bkbase",
        "workload": "Deployment:bkbase-authapi-celeryworker"
      },
      {
        "namespace": "blueking",
        "workload": "Deployment:bk-dbm-hadb-api"
      },
      {
        "namespace": "blueking",
        "workload": "Deployment:bk-cmdb-toposerver"
      }
    ]
  }
}

```

#### 2.4. 通过指定 wrokload_type 和 query_string 获取 workload 资源

##### 请求示例

```json
{
  "bk_biz_id": 2,
  "bcs_cluster_id": "BCS-K8S-00000",
  "resource_type": "workload",
  "start_time": 1733894974,
  "end_time": 1733898574,
  "scenario": "performance",
  "query_string": "monitor",
  "filter_dict": {
    "workload": "Deployment:"
  }
}

```

##### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": 50,
    "items": [
      {
        "namespace": "blueking",
        "workload": "Deployment:bk-monitor-alarm-webhook-action-worker"
      },
      {
        "namespace": "blueking",
        "workload": "Deployment:bk-monitor-web-worker-resource"
      },
      {
        "namespace": "blueking",
        "workload": "Deployment:bk-monitor-grafana"
      },
      {
        "namespace": "blueking",
        "workload": "Deployment:bk-monitor-web-query-api"
      },
      {
        "namespace": "blueking",
        "workload": "Deployment:bk-monitor-ingester"
      }
    ]
  }
}

```

#### 2.5. 通过指定 workload_type 和 workload_name 获取 workload 资源

##### 请求示例

```json
{
  "bk_biz_id": 2,
  "bcs_cluster_id": "BCS-K8S-00000",
  "resource_type": "workload",
  "start_time": 1733894974,
  "end_time": 1733898574,
  "scenario": "performance",
  "filter_dict": { "workload": "Deployment:bk-monitor-grafana" }
}
```

##### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": 1,
    "items": [
      {
        "namespace": "blueking",
        "workload": "Deployment:bk-monitor-grafana"
      }
    ]
  }
}

```

#### 3.1. 获取所有 namespace 的资源列表

##### 请求示例

```json
{
  "bk_biz_id": 2,
  "bcs_cluster_id": "BCS-K8S-00000",
  "resource_type": "namespace",
  "start_time": 1732240257,
  "end_time": 1732243857,
  "sernario": "performance"
}
```

##### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": 18,
    "items": [
      {
        "bk_biz_id": 2,
        "bcs_cluster_id": "BCS-K8S-00000",
        "namespace": "default"
      },
      {
        "bk_biz_id": 2,
        "bcs_cluster_id": "BCS-K8S-00000",
        "namespace": "demo"
      }
      // ...
    ]
  }
}
```

#### 4.1. 获取所有 container 的资源列表

##### 请求示例

```json
{
  "bk_biz_id": 2,
  "bcs_cluster_id": "BCS-K8S-00000",
  "resource_type": "container",
  "start_time": 1732240257,
  "end_time": 1732243857,
  "sernario": "performance"
}
```

##### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": 23,
    "items": [
      {
        "pod": "pod-1",
        "container": "container-1",
        "namespace": "default",
        "workload": "Deployment:workload-1"
      },
      {
        "pod": "pod-2",
        "container": "container-2",
        "namespace": "demo",
        "workload": "Deployment:wrokload-2"
      } // ...
    ]
  }
}
```

#### 4.2. 获取指定 namespace 下的 container 资源列表

##### 请求示例

```json
{
  "bk_biz_id": 2,
  "bcs_cluster_id": "BCS-K8S-00000",
  "resource_type": "container",
  "start_time": 1732240257,
  "end_time": 1732243857,
  "sernario": "performance",
  "filter_dict": {
    "namespace": "default"
  }
}
```

##### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": 2,
    "items": [
      {
        "pod": "pod-1",
        "container": "container-1",
        "namespace": "default",
        "workload": "Deployment:workload-1"
      },
      {
        "pod": "pod-2",
        "container": "container-2",
        "namespace": "default",
        "workload": "Deployment:wrokload-2"
      } // ...
    ]
  }
}
```

#### 5.1. （暂未实现，文档需更改）获取资源类型为 node 的列表

##### 请求示例

```json
{
  "bk_biz_id": 2,
  "bcs_cluster_id": "BCS-K8S-00000",
  "resource_type": "node",
  "start_time": 1732240257,
  "end_time": 1732243857,
  "sernario": "performance"
}
```

##### 返回示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": 14,
    "items": [
      {
        "pod": "pod-1",
        "container": "container-1",
        "namespace": "default",
        "workload": "Deployment:workload-1"
      } // ...
    ]
  }
}
```

## GetResourceDetail

获取资源详情

### 请求方法

GET

### 请求 url

rest/v2/k8s/resources/get_resource_detail

### 请求参数

| 字段              | 类型   | 必填   | 描述                                                 |
| --------------- | ---- | ---- | -------------------------------------------------- |
| bcs_cluster_id  | str  | 是    | 集群 id                                              |
| bk_biz_id       | int  | 是    | 业务 id                                              |
| namespace       | str  | 是    | 命名空间                                               |
| resource_type   | str  | 是    | 资源类型，可选值为 "pod","workload","container"             |
| pod_name        | str  | 否    | pod 名称，当 resource_type 为 "pod" \| "container" 时必填  |
| container_name  | str  | 否    | 容器名称，当 resource_type 为 "container" 时必填             |
| workload_name   | str  | 否    | 工作负载名称， 当 resource_type 为 "workload" 时必填           |
| workload_type   | str  | 否    | 工作负载类型， 当 resource_type 为 "workload" 时必填           |

### 请求示例

```json
{
  "bk_biz_id": 2,
  "bcs_cluster_id": "BCS-K8S-00000",
  "namespace": "bkmonitor",
  "resource_type": "pod",
  "pod_name": "工作负载名称"
}
```

### 响应示例

和 `rest/v2/scene_view/get_kubernetes_workload/`, `rest/v2/scene_view/get_kubernetes_pod`, `rest/v2/scene_view/get_kubernetes_container` 接口返回数据格式一致

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "key": "name",
      "name": "工作负载名称",
      "type": "string",
      "value": "pf-f991b578413c4ce48d7d92d53f2021f9"
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
      "value": ""
    },
    {
      "key": "namespace",
      "name": "NameSpace",
      "type": "string",
      "value": "bkmonitor"
    }
  ]
}
```
