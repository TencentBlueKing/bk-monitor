### 功能描述

修改存储集群配置

### 请求参数

| 字段                          | 类型     | 必选 | 描述                                |
|-----------------------------|--------|----|-----------------------------------|
| cluster_id                  | int    | 否  | 存储集群ID，与 cluster_name 至少提供一个      |
| cluster_name                | string | 否  | 存储集群名，与 cluster_id 至少提供一个         |
| cluster_type                | string | 否  | 存储集群类型，用于在 cluster_name 相同时辅助定位集群 |
| display_name                | string | 否  | 集群显示名称                            |
| operator                    | string | 是  | 操作者                               |
| description                 | string | 否  | 存储集群描述信息                          |
| auth_info                   | dict   | 否  | 集群身份认证信息，默认为空                     |
| custom_option               | string | 否  | 集群自定义标签                           |
| schema                      | string | 否  | 集群链接协议，可用于配置 https 等情形            |
| is_ssl_verify               | bool   | 否  | 是否需要强制 SSL/TLS 认证                 |
| ssl_verification_mode       | string | 否  | SSL 校验模式                          |
| ssl_certificate_authorities | string | 否  | CA 证书内容                           |
| ssl_certificate             | string | 否  | SSL/TLS 证书内容                      |
| ssl_certificate_key         | string | 否  | SSL/TLS 私钥内容                      |
| ssl_insecure_skip_verify    | bool   | 否  | 是否跳过服务端校验                         |
| extranet_domain_name        | string | 否  | 外网集群域名                            |
| extranet_port               | int    | 否  | 外网集群端口                            |

**注意**：`cluster_id` 与 `cluster_name` 至少提供一个

#### auth_info 字段说明

| 字段       | 类型     | 必选 | 描述    |
|----------|--------|----|-------|
| username | string | 否  | 访问用户名 |
| password | string | 否  | 访问密码  |

### 请求参数示例

```json
{
    "cluster_id": 1,
    "operator": "admin",
    "description": "更新后的描述信息",
    "auth_info": {
        "username": "username",
        "password": "password"
    }
}
```

### 响应参数

| 字段      | 类型     | 描述             |
|---------|--------|----------------|
| result  | bool   | 请求是否成功         |
| code    | int    | 返回的状态码         |
| message | string | 描述信息           |
| data    | dict   | 集群 consul 配置信息 |

#### data 字段说明

| 字段             | 类型     | 描述     |
|----------------|--------|--------|
| cluster_config | dict   | 集群配置信息 |
| cluster_type   | string | 集群类型   |
| auth_info      | dict   | 身份认证信息 |

#### data.cluster_config 字段说明

| 字段                              | 类型     | 描述                                         |
|---------------------------------|--------|--------------------------------------------|
| domain_name                     | string | 集群域名                                       |
| port                            | int    | 集群端口                                       |
| extranet_domain_name            | string | 集群外网域名                                     |
| extranet_port                   | int    | 集群外网端口                                     |
| schema                          | string | 访问协议                                       |
| is_ssl_verify                   | bool   | 是否SSL验证                                    |
| ssl_verification_mode           | string | CA校验模式                                     |
| ssl_insecure_skip_verify        | bool   | 是否跳过服务端校验                                  |
| ssl_certificate_authorities     | string | base64编码的CA证书内容（is_plain_text为false时）      |
| ssl_certificate                 | string | base64编码的SSL/TLS证书内容（is_plain_text为false时） |
| ssl_certificate_key             | string | base64编码的SSL/TLS私钥内容（is_plain_text为false时） |
| raw_ssl_certificate_authorities | string | 原始CA证书内容                                   |
| raw_ssl_certificate             | string | 原始SSL/TLS证书内容                              |
| raw_ssl_certificate_key         | string | 原始SSL/TLS私钥内容                              |
| cluster_id                      | int    | 集群ID                                       |
| cluster_name                    | string | 集群名称                                       |
| display_name                    | string | 集群显示名称                                     |
| version                         | string | 集群版本                                       |
| custom_option                   | string | 自定义标签                                      |
| registered_system               | string | 注册来源系统                                     |
| creator                         | string | 创建者                                        |
| create_time                     | int    | 创建时间（时间戳）                                  |
| last_modify_user                | string | 最后更新者                                      |
| last_modify_time                | int    | 最后更新时间（时间戳）                                |
| is_default_cluster              | bool   | 是否默认集群                                     |

#### data.auth_info字段说明

当 `is_plain_text` 为 `true` 时，返回字典格式：

| 字段                | 类型     | 描述                   |
|-------------------|--------|----------------------|
| username          | string | 用户名                  |
| password          | string | 密码                   |
| sasl_mechanisms   | string | SASL认证机制（仅kafka类型集群） |
| security_protocol | string | 安全协议（仅kafka类型集群）     |

当 `is_plain_text` 为 `false` 时，返回 base64 编码的字符串，编码内容为上述字典的 JSON 字符串。

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
            "cluster_config": {
                "domain_name": "influxdb.domain.cluster",
                "port": 8086,
                "extranet_domain_name": "",
                "extranet_port": 0,
                "schema": "http",
                "is_ssl_verify": false,
                "ssl_verification_mode": "none",
                "ssl_insecure_skip_verify": false,
                "ssl_certificate_authorities": "",
                "ssl_certificate": "",
                "ssl_certificate_key": "",
                "raw_ssl_certificate_authorities": "",
                "raw_ssl_certificate": "",
                "raw_ssl_certificate_key": "",
                "cluster_id": 3,
                "cluster_name": "influxdb_cluster_01",
                "display_name": "InfluxDB集群01",
                "version": "1.8.0",
                "custom_option": "",
                "registered_system": "_default",
                "creator": "admin",
                "create_time": 1700000000,
                "last_modify_user": "admin",
                "last_modify_time": 1700000000,
                "is_default_cluster": true
            },
            "cluster_type": "influxdb",
            "auth_info": {
                "username": "admin",
                "password": "password"
            }
        },
    "result": true
}
```