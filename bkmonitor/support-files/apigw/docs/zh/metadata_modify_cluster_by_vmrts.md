### 功能描述

根据VMRT列表修改VM集群

### 请求参数

| 字段           | 类型        | 必选 | 描述        |
|--------------|-----------|----|-----------|
| vmrts        | list[str] | 是  | VM结果表ID列表 |
| cluster_name | str       | 是  | 目标集群名称    |

### 请求参数示例

```json
{
    "vmrts": ["2_bkmonitor_time_series_1001.__default__", "2_bkmonitor_time_series_1002.__default__"],
    "cluster_name": "vm-cluster-01"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | bool   | 操作是否成功 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": true
}
```
