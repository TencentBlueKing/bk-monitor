### 功能描述

修改metadata中BCS资源的DataID信息

### 请求参数

| 字段            | 类型  | 必选 | 描述                                                      |
|---------------|-----|----|---------------------------------------------------------|
| cluster_id    | str | 是  | BCS集群ID                                                 |
| resource_type | str | 是  | 资源类型，支持：`servicemonitors`、`podmonitors`、`logcollectors` |
| resource_name | str | 是  | 资源名称                                                    |
| data_id       | int | 是  | 修改后的目标DataID                                            |

### 请求参数示例

```json
{
    "cluster_id": "BCS-K8S-00001",
    "resource_type": "servicemonitors",
    "resource_name": "my-service-monitor",
    "data_id": 1001
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | null   | 返回数据   |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": null
}
```
