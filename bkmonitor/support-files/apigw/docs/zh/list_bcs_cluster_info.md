### 功能描述

查询metadata中BCS集群信息

### 请求参数

| 字段          | 类型        | 必选 | 描述                  |
|-------------|-----------|----|---------------------|
| bk_biz_id   | int       | 否  | 业务ID，不传则查询所有业务的集群   |
| cluster_ids | list[str] | 否  | BCS集群ID列表，为空时查询所有集群 |

### 请求参数示例

```json
{
    "bk_biz_id": 2,
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

| 字段                  | 类型   | 描述          |
|---------------------|------|-------------|
| cluster_id          | str  | BCS集群ID     |
| bk_tenant_id        | str  | 租户ID        |
| bcs_api_cluster_id  | str  | BCS API集群ID |
| bk_biz_id           | int  | 业务ID        |
| project_id          | str  | BCS项目ID     |
| domain_name         | str  | BCS域名       |
| port                | int  | BCS端口       |
| server_address_path | str  | 服务地址路径      |
| api_key_type        | str  | API密钥类型     |
| api_key_content     | str  | API密钥内容     |
| api_key_prefix      | str  | API密钥前缀     |
| is_skip_ssl_verify  | bool | 是否跳过SSL认证   |
| cert_content        | str  | 证书内容        |
| k8s_event_data_id   | int  | K8s事件DataID |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "cluster_id": "BCS-K8S-00001",
            "bk_tenant_id": "default",
            "bcs_api_cluster_id": "BCS-K8S-00001",
            "bk_biz_id": 2,
            "project_id": "project123",
            "domain_name": "bcs.example.com",
            "port": 443,
            "server_address_path": "/clusters/BCS-K8S-00001",
            "api_key_type": "Bearer",
            "api_key_content": "***",
            "api_key_prefix": "Bearer",
            "is_skip_ssl_verify": false,
            "cert_content": "",
            "k8s_event_data_id": 1001
        }
    ]
}
```
