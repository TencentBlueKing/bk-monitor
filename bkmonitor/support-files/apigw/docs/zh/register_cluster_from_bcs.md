### 功能描述

BCS集群接入监控

### 请求参数

| 字段             | 类型  | 必选 | 描述                          |
|----------------|-----|----|-----------------------------|
| bcs_cluster_id | str | 是  | 集群ID                        |
| username       | str | 否  | 用户名，为空时默认使用请求用户名，默认为"admin" |

### 请求参数示例

```json
{
    "bcs_cluster_id": "BCS-K8S-00000",
    "username": "admin"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | str    | 返回数据   |

#### data 字段说明

返回字符串，表示集群注册结果：

- 成功注册：`[cluster]{cluster_id} success!`
- 集群已存在：`[cluster]{cluster_id} already registered. do nothing`

### 响应参数示例

#### 成功注册

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": "[cluster]BCS-K8S-00000 success!"
}
```

#### 集群已存在

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": "[cluster]BCS-K8S-00000 already registered. do nothing"
}
```

#### 集群不存在

```json
{
    "result": false,
    "code": 500,
    "message": "[cluster]BCS-K8S-00000 not in bcs",
    "data": null
}
```
