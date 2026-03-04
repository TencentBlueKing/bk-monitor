### 功能描述

创建 VM 存储集群

### 请求参数

| 字段                 | 类型   | 必选 | 描述                    |
|--------------------|------|----|-----------------------|
| cluster_name       | str  | 是  | 集群名称                  |
| domain_name        | str  | 是  | 集群域名                  |
| port               | int  | 否  | 集群端口，默认为 80           |
| description        | str  | 否  | 集群描述，默认为 `vm 集群`      |
| is_default_cluster | bool | 否  | 是否设置为默认集群，默认为 `false` |

> 注意：当 `is_default_cluster=true` 时，系统会将原有默认集群取消默认状态，并将所有未指定特定集群的空间更新为使用新集群

### 请求参数示例

```json
{
    "cluster_name": "vm_cluster_01",
    "domain_name": "vm.example.com",
    "port": 8480,
    "description": "VM 集群",
    "is_default_cluster": false
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 返回数据   |

#### data 字段说明

| 字段         | 类型  | 描述        |
|------------|-----|-----------|
| cluster_id | int | 新创建的集群 ID |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "cluster_id": 5
    }
}
```
