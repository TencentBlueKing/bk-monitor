### 功能描述

查询metadata中BCS资源的DataID信息

### 请求参数

| 字段            | 类型        | 必选 | 描述                  |
|---------------|-----------|----|---------------------|
| resource_type | str       | 是  | 资源类型，支持多个类型用英文逗号分隔  |
| cluster_ids   | list[str] | 否  | BCS集群ID列表，为空时查询所有集群 |

### 请求参数示例

```json
{
    "resource_type": "servicemonitors,podmonitors",
    "cluster_ids": ["BCS-K8S-00001"]
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | list   | 返回数据   |

#### data 元素字段说明

| 字段                 | 类型   | 描述          |
|--------------------|------|-------------|
| cluster_id         | str  | BCS集群ID     |
| namespace          | str  | 命名空间        |
| name               | str  | 资源名称        |
| bk_data_id         | int  | 关联的DataID   |
| is_custom_resource | bool | 是否为自定义资源    |
| is_common_data_id  | bool | 是否为公共DataID |
| resource_type      | str  | 资源类型        |
| resource_usage     | str  | 资源用途        |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "cluster_id": "BCS-K8S-00001",
            "namespace": "default",
            "name": "my-service-monitor",
            "bk_data_id": 1001,
            "is_custom_resource": true,
            "is_common_data_id": false,
            "resource_type": "servicemonitors",
            "resource_usage": "metric"
        }
    ]
}
```
