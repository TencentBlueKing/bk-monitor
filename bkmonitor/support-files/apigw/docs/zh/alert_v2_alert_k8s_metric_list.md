### 功能描述

【告警V2】K8S指标列表查询

### 请求参数

| 字段        | 类型  | 必选 | 描述                                                  |
|-----------|-----|----|-----------------------------------------------------|
| bk_biz_id | int | 是  | 业务ID                                                |
| scenario  | str | 是  | 观测场景名称，可选值：performance（性能）、network（网络）、capacity（容量） |

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "scenario": "performance"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | list   | 指标分类列表 |

#### data 元素字段说明（指标分类）

| 字段       | 类型         | 描述                 |
|----------|------------|--------------------|
| id       | string     | 分类ID（如：CPU、memory） |
| name     | string     | 分类名称               |
| children | list[dict] | 该分类下的指标列表          |

#### children 元素字段说明（指标详情）

| 字段                   | 类型        | 描述                                 |
|----------------------|-----------|------------------------------------|
| id                   | string    | 指标ID                               |
| name                 | string    | 指标名称                               |
| unit                 | string    | 指标单位（如：core、bytes、percentunit、Bps） |
| unsupported_resource | list[str] | 不支持该指标的资源类型列表（如：["namespace"]）     |
| show_chart           | bool      | 是否在图表中展示                           |

### 响应参数示例

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
                {
                    "id": "container_cpu_usage_seconds_total",
                    "name": "CPU使用量",
                    "unit": "core",
                    "unsupported_resource": [],
                    "show_chart": true
                },
                {
                    "id": "kube_pod_cpu_requests_ratio",
                    "name": "CPU request使用率",
                    "unit": "percentunit",
                    "unsupported_resource": ["namespace"],
                    "show_chart": true
                },
                {
                    "id": "kube_pod_cpu_limits_ratio",
                    "name": "CPU limit使用率",
                    "unit": "percentunit",
                    "unsupported_resource": ["namespace"],
                    "show_chart": true
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
                    "unsupported_resource": [],
                    "show_chart": true
                },
                {
                    "id": "kube_pod_memory_requests_ratio",
                    "name": "内存 request使用率",
                    "unit": "percentunit",
                    "unsupported_resource": ["namespace"],
                    "show_chart": true
                },
                {
                    "id": "kube_pod_memory_limits_ratio",
                    "name": "内存 limit使用率",
                    "unit": "percentunit",
                    "unsupported_resource": ["namespace"],
                    "show_chart": true
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
                    "unsupported_resource": ["container"],
                    "show_chart": true
                },
                {
                    "id": "container_network_transmit_bytes_total",
                    "name": "网络出带宽",
                    "unit": "Bps",
                    "unsupported_resource": ["container"],
                    "show_chart": true
                }
            ]
        }
    ]
}
```
