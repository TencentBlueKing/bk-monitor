### 功能描述

注册存储集群资源

### 请求参数

| 字段                | 类型   | 必选 | 描述                                          |
|-------------------|------|----|---------------------------------------------|
| cluster_name      | str  | 否  | 集群名称，需符合正则规范，默认为空（系统自动生成）                   |
| cluster_type      | str  | 是  | 集群类型，可选值：`influxdb`、`elasticsearch`、`kafka` |
| display_name      | str  | 否  | 集群显示名称                                      |
| domain            | str  | 是  | 集群域名                                        |
| port              | int  | 是  | 集群端口                                        |
| registered_system | str  | 是  | 注册来源系统                                      |
| operator          | str  | 是  | 创建者                                         |
| description       | str  | 否  | 集群描述，默认为空                                   |
| username          | str  | 否  | 访问集群的用户名，默认为空                               |
| password          | str  | 否  | 访问集群的密码，默认为空                                |
| version           | str  | 否  | 集群版本，默认为空                                   |
| schema            | str  | 否  | 访问协议，如 `http`、`https`，默认为空                  |
| is_ssl_verify     | bool | 否  | 是否开启 SSL 验证，默认为 `false`                     |
| label             | str  | 否  | 集群标签，默认为空                                   |
| default_settings  | dict | 否  | 默认集群配置，默认为空对象                               |

### 请求参数示例

```json
{
    "cluster_name": "es_cluster_01",
    "cluster_type": "elasticsearch",
    "domain": "es.example.com",
    "port": 9200,
    "registered_system": "bk_monitor",
    "operator": "admin",
    "description": "ES 集群",
    "username": "elastic",
    "password": "password123",
    "version": "7.10.0",
    "schema": "http",
    "is_ssl_verify": false
}
```

### 响应参数

| 字段      | 类型   | 描述       |
|---------|------|----------|
| result  | bool | 请求是否成功   |
| code    | int  | 返回的状态码   |
| message | str  | 描述信息     |
| data    | dict | 注册后的集群详情 |

#### data 字段说明

| 字段                              | 类型    | 描述                        |
|---------------------------------|-------|---------------------------|
| cluster_id                      | int   | 集群 ID                     |
| cluster_name                    | str   | 集群名称                      |
| cluster_type                    | str   | 集群类型                      |
| display_name                    | str   | 集群显示名称                    |
| domain_name                     | str   | 集群域名                      |
| port                            | int   | 集群端口                      |
| extranet_domain_name            | str   | 外网集群域名                    |
| extranet_port                   | int   | 外网集群端口                    |
| schema                          | str   | 访问协议                      |
| is_ssl_verify                   | bool  | 是否开启 SSL 验证               |
| ssl_verification_mode           | str   | CA 校验模式                   |
| ssl_insecure_skip_verify        | bool  | 是否跳过服务端校验                 |
| ssl_certificate_authorities     | str   | CA 证书内容（Base64 编码）        |
| ssl_certificate                 | str   | SSL/TLS 证书内容（Base64 编码）   |
| ssl_certificate_key             | str   | SSL/TLS 证书私钥内容（Base64 编码） |
| raw_ssl_certificate_authorities | str   | CA 证书原始内容                 |
| raw_ssl_certificate             | str   | SSL/TLS 证书原始内容            |
| raw_ssl_certificate_key         | str   | SSL/TLS 证书私钥原始内容          |
| version                         | str   | 集群版本                      |
| custom_option                   | str   | 自定义标签                     |
| registered_system               | str   | 注册来源系统                    |
| creator                         | str   | 创建者                       |
| create_time                     | float | 创建时间（Unix 时间戳）            |
| last_modify_user                | str   | 最后修改者                     |
| last_modify_time                | float | 最后修改时间（Unix 时间戳）          |
| is_default_cluster              | bool  | 是否为默认集群                   |
| auth_info                       | dict  | 认证信息                      |
| label                           | str   | 集群标签                      |
| default_settings                | dict  | 默认集群配置                    |

#### data.auth_info 字段说明

| 字段       | 类型  | 描述  |
|----------|-----|-----|
| username | str | 用户名 |
| password | str | 密码  |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "cluster_id": 1,
        "cluster_name": "es_cluster_01",
        "cluster_type": "elasticsearch",
        "display_name": "es_cluster_01",
        "domain_name": "es.example.com",
        "port": 9200,
        "extranet_domain_name": "",
        "extranet_port": 0,
        "schema": "http",
        "is_ssl_verify": false,
        "ssl_verification_mode": "",
        "ssl_insecure_skip_verify": false,
        "ssl_certificate_authorities": "",
        "ssl_certificate": "",
        "ssl_certificate_key": "",
        "raw_ssl_certificate_authorities": "",
        "raw_ssl_certificate": "",
        "raw_ssl_certificate_key": "",
        "version": "7.10.0",
        "custom_option": "",
        "registered_system": "bk_monitor",
        "creator": "admin",
        "create_time": 1704067200.0,
        "last_modify_user": "admin",
        "last_modify_time": 1704067200.0,
        "is_default_cluster": false,
        "auth_info": {
            "username": "elastic",
            "password": "password123"
        },
        "label": "",
        "default_settings": {}
    }
}
```
