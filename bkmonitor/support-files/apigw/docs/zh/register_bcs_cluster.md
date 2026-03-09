### 功能描述

将BCS集群信息注册到metadata

### 请求参数

| 字段                  | 类型   | 必选 | 描述             |
|---------------------|------|----|----------------|
| bk_biz_id           | int  | 是  | 业务ID           |
| cluster_id          | str  | 是  | BCS集群ID        |
| project_id          | str  | 是  | BCS项目ID        |
| creator             | str  | 是  | 操作人            |
| domain_name         | str  | 否  | BCS域名          |
| port                | int  | 否  | BCS端口          |
| api_key_type        | str  | 否  | API密钥类型        |
| api_key_prefix      | str  | 否  | API密钥前缀        |
| is_skip_ssl_verify  | bool | 否  | 是否跳过SSL认证      |
| transfer_cluster_id | str  | 否  | Transfer集群ID   |
| bk_env              | str  | 否  | 配置来源标签，默认为空字符串 |

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "cluster_id": "BCS-K8S-00001",
    "project_id": "project123",
    "creator": "admin",
    "domain_name": "bcs.example.com",
    "port": 443,
    "api_key_type": "Bearer",
    "api_key_prefix": "Bearer",
    "is_skip_ssl_verify": false,
    "transfer_cluster_id": "default",
    "bk_env": ""
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
