# 接口文档

## ListBCSCluster

获取集群列表

### 请求 url

rest/v2/k8s/resources/list_bcs_cluster/

### 请求参数

```json
{"bk_biz_id": 2}
```

### 返回示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [{ "id": "BCS-K8S-00000", "name": "蓝鲸7.0(BCS-K8S-00000)" }]
}
```

## WorkloadOverview

### 请求 url

rest/v2/k8s/resources/workload_overview/

### 请求参数

| 字段             | 类型  | 必选  | 描述               |
| -------------- | --- | --- | ---------------- |
| bk_biz_id      | int | 是   | 业务 ID            |
| bcs_cluster_id | str | 是   | 集群 ID            |
| namespace      | str | 否   | 命名空间             |
| query_string   | str | 否   | workload_name 过滤 |

### 返回示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    ["Deployments", 9],
    ["StatefulSets", 9],
    ["DaemonSets", 9],
    ["Jobs", 9],
    ["CronJobs", 9]
  ]
}
```

## ScenarioMetricList

获取指定场景的指标列表

### 请求 url

rest/v2/k8s/resources/scenario_metric_list/

### 请求参数

```python
# 可选值:
# performance : 性能
{
  "scenario": "performance"
}
```

### 返回示例

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

### 请求 url

rest/v2/k8s/resources/list_k8s_resources/

### 请求参数

| 字段               | 类型       | 必选    | 描述                                                               |
| ---------------- | -------- | ----- | ---------------------------------------------------------------- |
| bk_biz_id        | id       | 是     | 业务 id                                                            |
| bcs_cluster_id   | string   | 是     | 集群 id                                                            |
| resource_type    | string   | 是     | 资源类型，可选值为 ”pod", "node“, "workload", "namespace", "container"    |
| query_string     | string   | 否     | 名字过滤                                                             |
| filter_dict      | dict     | 否     | 精确过滤                                                             |
| start_time       | int      | 是     | 开始时间                                                             |
| end_time         | int      | 是     | 结束时间                                                             |
| sernario         | str      | 是     | 场景，可选值为 ”performance“                                            |
| with_history     | bool     | 否     | 历史出现过的资源                                                         |
| page_size        | int      | 否     | 分页数量                                                             |
| page             | int      | 否     | 页数                                                               |
| page_type        | str      | 否     | 分页类型，可选值为："scrolling"(滚动分页),"traditional"(传统分页)，默认为"traditional" |

### 返回示例

#### 返回资源类型: pod

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": 200,
    "items": [
      {
        "pod": "pod-1",
        "namespace": "default",
        "workload": "Deployment:workload-1"
      }
    ]
  }
}
```

#### 返回资源类型: workload

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": 200,
    "items": [
      {
        "namespace": "default",
        "workload": "Deployment:workload-1"
      }
    ]
  }
}
```

#### 返回资源类型: namespace

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": 200,
    "items": [
      {
        "bk_biz_id": 2,
        "bcs_cluster_id": "BCS-K8S-00000",
        "namespace": "default"
      }
    ]
  }
}
```

#### 返回资源类型: contaier

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": 200,
    "items": [
      {
        "pod": "pod-1",
        "namespace": "default",
        "workload": "Deployment:workload-1"
      }
    ]
  }
}
```

#### 返回资源类型: node

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": 200,
    "items": [
      {
        "pod": "pod-1",
        "container": "container-1",
        "namespace": "default",
        "workload": "Deployment:workload-1"
      }
    ]
  }
}
```

## GetResourceDetail

获取资源详情

### 请求 url

rest/v2/k8s/resources/get_resource_detail

### 请求参数

| 字段            | 类型  | 必填  | 描述                                                |
| -------------- | --- | --- | ------------------------------------------------- |
| bcs_cluster_id | str | 是   | 集群 id                                             |
| bk_biz_id      | int | 是   | 业务 id                                             |
| namespace      | str | 是   | 命名空间                                              |
| resource_type  | str | 是   | 资源类型，可选值为 “pod”,"workload","container"            |
| pod_name       | str | 否   | pod 名称，当 resource_type 为 "pod" \| "container" 时必填 |
| container_name | str | 否   | 容器名称，当 resource_type 为 “container" 时必填            |
| workload_name  | str | 否   | 工作负载名称， 当 resource_type 为 ”workload" 时必填          |
| workload_type  | str | 否   | 工作负载类型， 当 resource_type 为 ”workload" 时必填          |

### 返回示例

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
