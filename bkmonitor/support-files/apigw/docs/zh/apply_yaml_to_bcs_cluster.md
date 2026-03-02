### 功能描述

应用YAML配置到指定BCS集群

### 请求参数

| 字段           | 类型  | 必选 | 描述                 |
|--------------|-----|----|--------------------|
| cluster_id   | str | 是  | BCS集群ID            |
| yaml_content | str | 是  | YAML文本内容           |
| namespace    | str | 否  | 命名空间，默认为 `default` |

### 请求参数示例

```json
{
    "cluster_id": "BCS-K8S-00001",
    "namespace": "default",
    "yaml_content": "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: my-config\ndata:\n  key: value"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | bool   | 是否应用成功 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": true
}
```
