### 功能描述

容器资源过滤候选值检索（级联过滤）

基于监控平台的容器资源缓存（集群下的 Workload/Pod/Container 快照，分钟级同步），返回指定维度的候选值列表，
用于容器场景检索类 UI 的过滤字段联想。已选条件与目标维度可任意组合级联：例如已选 namespace 后检索
workload_name 候选，仅返回该 namespace 下的负载名（含副本数为 0 的负载与完成态 Job/CronJob）。

注意：

- 缓存为当前态快照，已删除 Pod 的名字不会出现在候选中
- 目标维度自身的已选条件不参与过滤（多选场景下取候选时忽略本维度已选值）
- 请求的集群不属于该业务时返回空列表而非报错；BCS 空间（负数业务 ID）下共享集群仅返回授权命名空间的数据

### 请求参数

| 字段             | 类型        | 必选 | 描述                                                                                              |
|----------------|-----------|----|-------------------------------------------------------------------------------------------------|
| bk_biz_id      | int       | 是  | 业务ID（BCS 空间传对应负数 ID）                                                                            |
| bcs_cluster_ids | list[str] | 是  | 集群ID列表，多选                                                                                        |
| resource_type  | str       | 是  | 目标维度：namespace / workload_type / workload_name / pod_name / container_name / node_ip            |
| conditions     | list      | 否  | 已选过滤条件列表，元素为 {key, method, value}；key 取值同 resource_type，method 为 eq（精确多选）或 include（多值"包含"匹配，OR 语义），value 为字符串列表 |
| query_string   | str       | 否  | 对目标维度候选值做"包含"匹配的检索词                                                                              |
| page           | int       | 否  | 页码，默认 1                                                                                          |
| page_size      | int       | 否  | 分页大小，默认 500，最大 1000                                                                              |

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "bcs_cluster_ids": ["BCS-K8S-00000", "BCS-K8S-00001"],
    "resource_type": "workload_name",
    "conditions": [
        {"key": "namespace", "method": "eq", "value": ["ns1", "ns2"]},
        {"key": "workload_type", "method": "eq", "value": ["Deployment"]}
    ],
    "query_string": "gamesvr",
    "page": 1,
    "page_size": 500
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

| 字段    | 类型        | 描述                  |
|-------|-----------|---------------------|
| count | int       | 去重后的候选值总数           |
| items | list[str] | 当前页的候选值列表（跨集群去重、有序） |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "count": 2,
        "items": ["gamesvr-lobby", "gamesvr-match"]
    }
}
```
