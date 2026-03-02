### 功能描述

创建存储集群配置

### 请求参数

| 字段                          | 类型     | 必选 | 描述                                               |
|-----------------------------|--------|----|--------------------------------------------------|
| cluster_name                | string | 否  | 存储集群名，默认为空                                       |
| display_name                | string | 否  | 集群显示名称，若不提供则使用 cluster_name                      |
| cluster_type                | string | 是  | 存储集群类型，目前可以支持 influxDB、kafka、redis、elasticsearch |
| domain_name                 | string | 是  | 存储集群域名（可以填入IP）                                   |
| port                        | int    | 是  | 存储集群端口                                           |
| operator                    | string | 是  | 操作者                                              |
| description                 | string | 否  | 存储集群描述信息，默认为空                                    |
| auth_info                   | dict   | 否  | 集群身份认证信息，默认为空                                    |
| version                     | string | 否  | 集群版本信息，默认为空                                      |
| custom_option               | string | 否  | 自定义标签，默认为空                                       |
| schema                      | string | 否  | 链接协议，可用于配置 https 等情形，默认为空                        |
| is_ssl_verify               | bool   | 否  | 是否需要 SSL 验证，默认为 false                            |
| ssl_verification_mode       | string | 否  | SSL 校验模式，默认为空                                    |
| ssl_certificate_authorities | string | 否  | CA 证书内容，默认为空                                     |
| ssl_certificate             | string | 否  | SSL/TLS 证书内容，默认为空                                |
| ssl_certificate_key         | string | 否  | SSL/TLS 私钥内容，默认为空                                |
| ssl_insecure_skip_verify    | bool   | 否  | 是否跳过服务端校验，默认为 false                              |
| extranet_domain_name        | string | 否  | 外网集群域名，默认为空                                      |
| extranet_port               | int    | 否  | 外网集群端口，默认为 0                                     |

#### auth_info 字段说明

| 字段       | 类型     | 必选 | 描述    |
|----------|--------|----|-------|
| username | string | 否  | 访问用户名 |
| password | string | 否  | 访问密码  |

### 请求参数示例

```json
{
    "cluster_name": "first_influxdb",
    "cluster_type": "influxDB",
    "domain_name": "influxdb.service.consul",
    "port": 9052,
    "operator": "admin",
    "description": "描述信息",
    "auth_info": {
        "username": "username",
        "password": "password"
    }
}
```

### 响应参数

| 字段      | 类型     | 描述      |
|---------|--------|---------|
| result  | bool   | 请求是否成功  |
| code    | int    | 返回的状态码  |
| message | string | 描述信息    |
| data    | int    | 新建的集群ID |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": 1001,
    "result": true
}
```
