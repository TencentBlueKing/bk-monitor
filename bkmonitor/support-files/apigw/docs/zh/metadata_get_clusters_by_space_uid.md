### 功能描述

查询空间（bkci 类型）下关联的 BCS 集群信息

### 请求参数

| 字段            | 类型  | 必选 | 描述                                       |
|---------------|-----|----|------------------------------------------|
| space_uid     | str | 否  | 空间唯一标识，格式为 `{space_type_id}__{space_id}` |
| space_type_id | str | 否  | 空间类型 ID，与 space_id 配合使用                  |
| space_id      | str | 否  | 空间 ID，与 space_type_id 配合使用               |

> 注意：`space_uid` 和 `(space_type_id, space_id)` 至少提供一个，且空间类型必须为 `bkci`。

### 请求参数示例

```json
{
    "space_uid": "bkci__myproject"
}
```

### 响应参数

| 字段      | 类型         | 描述     |
|---------|------------|--------|
| result  | bool       | 请求是否成功 |
| code    | int        | 返回的状态码 |
| message | string     | 描述信息   |
| data    | list[dict] | 集群信息列表 |

#### data 元素字段说明

| 字段             | 类型        | 描述        |
|----------------|-----------|-----------|
| cluster_id     | str       | BCS 集群 ID |
| namespace_list | list[str] | 命名空间列表    |
| cluster_type   | str       | 集群类型      |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "cluster_id": "BCS-K8S-00001",
            "namespace_list": ["default", "kube-system"],
            "cluster_type": "k8s"
        }
    ]
}
```
