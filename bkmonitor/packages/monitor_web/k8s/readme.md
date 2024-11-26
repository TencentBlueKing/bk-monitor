### 接口文档

#### 

##### ListBCSCluster
获取集群列表
- 请求url: rest/v2/k8s/resources/list_bcs_cluster/
- 请求参数:
```
{'bk_biz_id': 2}
```
- 返回示例:
```
{'result': True,
 'code': 200,
 'message': 'OK',
 'data': [{'id': 'BCS-K8S-00000', 'name': '蓝鲸7.0(BCS-K8S-00000)'}]}
```


##### ScenarioMetricList
获取指定场景的指标列表
- 请求url: rest/v2/k8s/resources/scenario_metric_list/
- 请求参数:
```
# 可选值: 
# performance : 性能

{'scenario': 'performance'}
```
- 返回示例:
```
{'result': True,
 'code': 200,
 'message': 'OK',
 'data': [{'id': 'CPU',
   'name': 'CPU',
   'children': [{'id': 'container_cpu_usage_seconds_total', 'name': 'CPU使用量'},
    {'id': 'kube_pod_cpu_requests_ratio', 'name': 'CPU request使用率'},
    {'id': 'kube_pod_cpu_limits_ratio', 'name': 'CPU limit使用率'}]},
  {'id': 'memory',
   'name': '内存',
   'children': [{'id': 'container_memory_rss', 'name': '内存使用量(rss)'},
    {'id': 'kube_pod_memory_requests_ratio', 'name': '内存 request使用率'},
    {'id': 'kube_pod_memory_limits_ratio', 'name': '内存 limit使用率'}]}]}
```



##### ListK8SResources
- 请求url: rest/v2/k8s/resources/list_k8s_resources/
获取k8s集群资源列表