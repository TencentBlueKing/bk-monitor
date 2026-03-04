### 功能描述

删除存储集群信息

### 请求参数

| 字段           | 类型  | 必选 | 描述                         |
|--------------|-----|----|----------------------------|
| cluster_id   | int | 否  | 存储集群 ID，与 cluster_name 二选一 |
| cluster_name | str | 否  | 存储集群名，与 cluster_id 二选一     |

> 注意：`cluster_id` 和 `cluster_name` 至少提供一个。

### 请求参数示例

```json
{
    "cluster_id": 1
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
