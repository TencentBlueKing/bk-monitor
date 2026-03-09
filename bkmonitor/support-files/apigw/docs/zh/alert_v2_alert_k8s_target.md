### 功能描述

【告警V2】K8S目标查询

### 请求参数

| 字段       | 类型  | 必选 | 描述   |
|----------|-----|----|------|
| alert_id | str | 是  | 告警ID |

### 请求参数示例

```json
{
    "alert_id": "f1c6877ba046e2d32bfd8393b4dd26f7.1763554080.2860.2978.2"
}
```

### 响应参数

| 字段      | 类型     | 描述      |
|---------|--------|---------|
| result  | bool   | 请求是否成功  |
| code    | int    | 返回的状态码  |
| message | string | 描述信息    |
| data    | dict   | K8S目标信息 |

#### data 字段说明

| 字段            | 类型     | 描述                              |
|---------------|--------|---------------------------------|
| resource_type | string | 资源类型（pod/workload/node/service） |
| target_list   | list   | 目标对象列表                          |

#### target_list 元素字段说明

**通用字段（所有类型都包含）：**

| 字段             | 类型     | 描述                                                                                 |
|----------------|--------|------------------------------------------------------------------------------------|
| bcs_cluster_id | string | 集群ID                                                                               |
| namespace      | string | 命名空间（可选，当告警维度中存在namespace时才有此字段）                                                   |
| workload       | string | 工作负载（可选，格式：kind:name，如：Deployment:nginx，当告警维度中存在workload_kind和workload_name时才有此字段） |

**资源类型特定字段（根据resource_type不同，会额外包含对应的资源字段）：**

| resource_type | 额外字段     | 类型     | 描述                   |
|---------------|----------|--------|----------------------|
| pod           | pod      | string | Pod名称（值为告警目标target）  |
| workload      | workload | string | 工作负载名称（值为告警目标target） |
| node          | node     | string | 节点名称（值为告警目标target）   |
| service       | service  | string | 服务名称（值为告警目标target）   |

### 响应参数示例

**Pod类型示例：**

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "resource_type": "pod",
        "target_list": [
            {
                "bcs_cluster_id": "BCS-K8S-00000",
                "namespace": "default",
                "workload": "Deployment:nginx-deployment",
                "pod": "nginx-deployment-7d64c8f5d9-abc12"
            }
        ]
    }
}
```

**Workload类型示例：**

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "resource_type": "workload",
        "target_list": [
            {
                "bcs_cluster_id": "BCS-K8S-00000",
                "namespace": "default",
                "workload": "Deployment:nginx-deployment"
            }
        ]
    }
}
```

**Node类型示例：**

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "resource_type": "node",
        "target_list": [
            {
                "bcs_cluster_id": "BCS-K8S-00000",
                "node": "node-192-168-1-10"
            }
        ]
    }
}
```

**Service类型示例：**

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "resource_type": "service",
        "target_list": [
            {
                "bcs_cluster_id": "BCS-K8S-00000",
                "namespace": "default",
                "service": "nginx-service"
            }
        ]
    }
}
```
