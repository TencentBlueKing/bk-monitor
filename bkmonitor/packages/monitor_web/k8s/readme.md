# 接口文档

## ListBCSCluster

获取集群列表

- 请求url: rest/v2/k8s/resources/list_bcs_cluster/
- 请求参数:

```python
{"bk_biz_id": 2}
```

- 返回示例:

```python
{
    "result": True,
    "code": 200,
    "message": "OK",
    "data": [{"id": "BCS-K8S-00000", "name": "蓝鲸7.0(BCS-K8S-00000)"}],
}
```

## ScenarioMetricList

获取指定场景的指标列表

- 请求url: rest/v2/k8s/resources/scenario_metric_list/
- 请求参数:

```python
# 可选值: 
# performance : 性能

{
  "scenario": "performance"
}
```

- 返回示例:

```python
{
    "result": True,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "id": "CPU",
            "name": "CPU",
            "children": [
                {"id": "container_cpu_usage_seconds_total", "name": "CPU使用量"},
                {"id": "kube_pod_cpu_requests_ratio", "name": "CPU request使用率"},
                {"id": "kube_pod_cpu_limits_ratio", "name": "CPU limit使用率"},
            ],
        },
        {
            "id": "memory",
            "name": "内存",
            "children": [
                {"id": "container_memory_rss", "name": "内存使用量(rss)"},
                {"id": "kube_pod_memory_requests_ratio", "name": "内存 request使用率"},
                {"id": "kube_pod_memory_limits_ratio", "name": "内存 limit使用率"},
            ],
        },
    ],
}

```

## ListK8SResources

### 请求url

rest/v2/k8s/resources/list_k8s_resources/
获取k8s集群资源列表

### 请求参数

| 字段             | 类型     | 必选  | 描述                                                            |     |
| -------------- | ------ | --- | ------------------------------------------------------------- | --- |
| bk_biz_id      | id     | 是   | 业务id                                                          |     |
| bcs_cluster_id | string | 是   | 集群id                                                          |     |
| resource_type  | string | 是   | 资源类型，可选值为 ”pod", "node“, "workload", "namespace", "container" |     |
| query_string   | string | 否   | 名字过滤                                                          |     |
| filter_dict    | dict   | 否   | 精确过滤                                                          |     |
| start_time     | int    | 是   | 开始时间                                                          |     |
| end_time       | int    | 是   | 结束时间                                                          |     |
| sernario       | str    | 是   | 场景，可选值为 ”performance“                                         |     |
| with_history   | bool   | 否   | 历史出现过的资源                                                      |     |

### 返回示例

#### 返回资源类型: pod

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
      {
        "pod": "pod-1",
        "namespace":"default",
        "workload":"Deployment:workload-1"
      }
    ]
}
```

#### 返回资源类型: workload

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
      {
        "namespace":"default",
        "workload":"Deployment:workload-1"
      }
    ]
}
```

#### 返回资源类型: namespace

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
      {
        "bk_biz_id": 2,
        "bcs_cluster_id":"BCS-K8S-00000",
        "namespace":"default",
      }
    ]
}
```

#### 返回资源类型: contaier

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
      {
        "pod": "pod-1",
        "namespace":"default",
        "workload":"Deployment:workload-1"
      }
    ]
}
```

#### 返回资源类型: node

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
      {
        "pod": "pod-1",
        "container":"container-1",
        "namespace":"default",
        "workload":"Deployment:workload-1"
      }
    ]
}
```
