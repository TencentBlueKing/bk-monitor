### 功能描述

查询 APM 应用下的服务列表，返回每个服务的语言、系统信息、日志关联关系及 Kubernetes 平台信息。可选传入服务名列表进行过滤。

### 请求参数

| 字段            | 类型           | 必选 | 描述                             |
|---------------|--------------|----|--------------------------------|
| bk_biz_id     | int          | 是  | 业务 ID                          |
| app_name      | string       | 是  | 应用名称                           |
| service_names | List[string] | 否  | 服务名列表，为空时返回该应用下所有服务，传入时仅返回指定服务 |

### 请求参数示例

#### 查询所有服务

```json
{
    "bk_biz_id": 2,
    "app_name": "my-apm-app"
}
```

#### 查询指定服务

```json
{
    "bk_biz_id": 2,
    "app_name": "my-apm-app",
    "service_names": ["user-service", "order-service"]
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | list   | 服务列表   |

#### data 字段说明（每个元素为一个服务对象）

| 字段               | 类型     | 描述                                       |
|------------------|--------|------------------------------------------|
| service_name     | string | 服务名称                                     |
| service_language | string | 服务语言（如 `python`、`java`、`go` 等），未识别时为空字符串 |
| system           | dict   | 服务的系统信息（SDK、上报协议等），无 system 时为 `{}`      |
| log_relations    | list   | 服务关联的日志索引集列表                             |
| platform         | dict   | 平台信息（仅当服务关联了 Kubernetes 负载时返回此字段）        |

#### system 字段说明

当服务存在系统信息时，返回以下字段：

| 字段          | 类型     | 描述                                              |
|-------------|--------|-------------------------------------------------|
| name        | string | 系统名称（如 `opentelemetry`）                         |
| sdk         | string | SDK 名称                                          |
| temporality | string | 时间性（如 `cumulative`（累加）、`delta`（差值）），用于描述指标的聚合方式 |

#### log_relations 字段说明

| 字段           | 类型     | 描述           |
|--------------|--------|--------------|
| bk_biz_id    | int    | 业务 ID        |
| index_set_id | int    | 日志索引集 ID     |
| log_type     | string | 日志类型         |

#### platform 字段说明

仅当服务关联了 Kubernetes 工作负载时返回，结构如下：

| 字段        | 类型     | 描述                          |
|-----------|--------|-----------------------------|
| name      | string | 平台名称，固定为 `k8s`              |
| relations | list   | 工作负载列表                      |

**platform.relations 字段说明**

| 字段             | 类型     | 描述                                     |
|----------------|--------|----------------------------------------|
| bcs_cluster_id | string | BCS 集群 ID                              |
| namespace      | string | 命名空间                                   |
| workload_type  | string | 工作负载类型（如 `Deployment`、`StatefulSet` 等） |
| workload_name  | string | 工作负载名称                                 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "service_name": "user-service",
            "service_language": "java",
            "system": {
                "name": "opentelemetry",
                "sdk": "opentelemetry-java",
                "temporality": "cumulative"
            },
            "log_relations": [
                {
                    "bk_biz_id": 2,
                    "index_set_id": 12345,
                    "log_type": "custom"
                }
            ],
            "platform": {
                "name": "k8s",
                "relations": [
                    {
                        "bcs_cluster_id": "BCS-K8S-00001",
                        "namespace": "default",
                        "workload_type": "Deployment",
                        "workload_name": "user-service"
                    }
                ]
            }
        },
        {
            "service_name": "order-service",
            "service_language": "go",
            "system": {},
            "log_relations": []
        }
    ]
}
```

### 使用说明

1. **服务过滤**：`service_names` 参数为空列表或不传时，接口返回该应用下所有真实服务（排除虚拟节点）。传入指定服务名列表时，仅返回匹配的服务。

2. **系统信息**：`system` 描述了服务使用的可观测性系统（如 OpenTelemetry），包括 SDK 和指标时间性。若服务没有关联的系统，返回空字典 `{}`。

3. **日志关联**：`log_relations` 列出了服务关联的日志采集索引集，可用于在日志平台进行关联查询。

4. **Kubernetes 平台信息**：`platform` 字段仅在服务关联了 Kubernetes 工作负载时出现，描述了服务对应的集群、命名空间和工作负载信息。
