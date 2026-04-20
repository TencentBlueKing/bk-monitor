### 功能描述

更新已注册的存储集群资源信息

### 请求参数

| 字段               | 类型   | 必选 | 描述                         |
|------------------|------|----|----------------------------|
| cluster_id       | int  | 是  | 集群 ID                      |
| operator         | str  | 是  | 操作者                        |
| description      | str  | 否  | 集群描述，默认为空                  |
| username         | str  | 否  | 访问集群的用户名，默认为空              |
| password         | str  | 否  | 访问集群的密码，默认为空               |
| version          | str  | 否  | 集群版本，默认为空                  |
| schema           | str  | 否  | 访问协议，如 `http`、`https`，默认为空 |
| is_ssl_verify    | bool | 否  | 是否开启 SSL 验证，默认为 `false`    |
| label            | str  | 否  | 集群标签，默认为空                  |
| default_settings | dict | 否  | 默认集群配置，默认为空对象              |

### 请求参数示例

```json
{
    "cluster_id": 1,
    "operator": "admin",
    "description": "更新后的 ES 集群描述",
    "username": "elastic",
    "password": "new_password",
    "version": "7.17.0",
    "schema": "https",
    "is_ssl_verify": true
}
```

### 响应参数

| 字段      | 类型   | 描述            |
|---------|------|---------------|
| result  | bool | 请求是否成功        |
| code    | int  | 返回的状态码        |
| message | str  | 描述信息          |
| data    | bool | 更新成功返回 `true` |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": true
}
```
