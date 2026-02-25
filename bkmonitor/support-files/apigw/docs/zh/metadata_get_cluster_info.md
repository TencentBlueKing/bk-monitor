### 功能描述

查询指定存储集群信息

### 请求参数

| 字段            | 类型     | 必选 | 描述                    |
|---------------|--------|----|-----------------------|
| bk_tenant_id  | string | 是  | 租户ID                  |
| cluster_id    | int    | 否  | 存储集群ID                |
| cluster_name  | string | 否  | 存储集群名                 |
| cluster_type  | string | 否  | 存储集群类型                |
| is_plain_text | bool   | 否  | 是否需要明文显示登陆信息（默认false） |

> 注意：cluster_id 和 cluster_name 至少提供一个

### 请求参数示例

```json
{
    "bk_tenant_id": "system",
    "cluster_id": 1,
    "is_plain_text": false
}
```

或

```json
{
    "bk_tenant_id": "system",
    "cluster_name": "es_cluster_01",
    "cluster_type": "elasticsearch",
    "is_plain_text": true
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | list   | 数据     |

#### data 元素字段说明

| 字段             | 类型          | 描述                                       |
|----------------|-------------|------------------------------------------|
| cluster_config | dict        | 集群配置信息（包含集群基本信息）                         |
| cluster_type   | string      | 集群类型                                     |
| auth_info      | dict/string | 身份认证信息（is_plain_text为false时为base64编码字符串） |

#### data[].cluster_config字段说明

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

#### data[].auth_info字段说明

当 `is_plain_text` 为 `true` 时，返回字典格式：

| 字段                | 类型     | 描述                   |
|-------------------|--------|----------------------|
| username          | string | 用户名                  |
| password          | string | 密码                   |
| sasl_mechanisms   | string | SASL认证机制（仅kafka类型集群） |
| security_protocol | string | 安全协议（仅kafka类型集群）     |

当 `is_plain_text` 为 `false` 时，返回 base64 编码的字符串，编码内容为上述字典的 JSON 字符串。

### 响应参数示例

#### Elasticsearch集群示例

```json
{
    "message": "OK",
    "code": 200,
    "data": [
        {
            "cluster_config": {
                "domain_name": "es.domain.cluster",
                "port": 9200,
                "extranet_domain_name": "es.extranet.domain.cluster",
                "extranet_port": 9200,
                "schema": "http",
                "is_ssl_verify": false,
                "ssl_verification_mode": "none",
                "ssl_insecure_skip_verify": false,
                "ssl_certificate_authorities": "base64://...",
                "ssl_certificate": "base64://...",
                "ssl_certificate_key": "base64://...",
                "raw_ssl_certificate_authorities": "",
                "raw_ssl_certificate": "",
                "raw_ssl_certificate_key": "",
                "cluster_id": 1,
                "cluster_name": "es_cluster_01",
                "display_name": "ES集群01",
                "version": "7.10.0",
                "custom_option": "",
                "registered_system": "_default",
                "creator": "admin",
                "create_time": 1700000000,
                "last_modify_user": "admin",
                "last_modify_time": 1700000000,
                "is_default_cluster": true
            },
            "cluster_type": "elasticsearch",
            "auth_info": "eyJ1c2VybmFtZSI6ICJhZG1pbiIsICJwYXNzd29yZCI6ICJwYXNzd29yZCJ9"
        }
    ],
    "result": true
}
```

#### Kafka集群示例（带SASL认证）

```json
{
    "message": "OK",
    "code": 200,
    "data": [
        {
            "cluster_config": {
                "domain_name": "kafka.domain.cluster",
                "port": 9092,
                "extranet_domain_name": "kafka.extranet.domain.cluster",
                "extranet_port": 9092,
                "schema": "",
                "is_ssl_verify": true,
                "ssl_verification_mode": "full",
                "ssl_insecure_skip_verify": false,
                "ssl_certificate_authorities": "base64://...",
                "ssl_certificate": "base64://...",
                "ssl_certificate_key": "base64://...",
                "raw_ssl_certificate_authorities": "",
                "raw_ssl_certificate": "",
                "raw_ssl_certificate_key": "",
                "cluster_id": 2,
                "cluster_name": "kafka_cluster_01",
                "display_name": "Kafka集群01",
                "version": "2.8.0",
                "custom_option": "",
                "registered_system": "_default",
                "creator": "admin",
                "create_time": 1700000000,
                "last_modify_user": "admin",
                "last_modify_time": 1700000000,
                "is_default_cluster": false
            },
            "cluster_type": "kafka",
            "auth_info": {
                "username": "admin",
                "password": "password",
                "sasl_mechanisms": "PLAIN",
                "security_protocol": "SASL_SSL"
            }
        }
    ],
    "result": true
}
```

#### InfluxDB集群示例（明文显示）

```json
{
    "message": "OK",
    "code": 200,
    "data": [
        {
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
        }
    ],
    "result": true
}
```

#### Redis集群示例

```json
{
    "message": "OK",
    "code": 200,
    "data": [
        {
            "cluster_config": {
                "domain_name": "redis.domain.cluster",
                "port": 6379,
                "extranet_domain_name": "",
                "extranet_port": 0,
                "schema": "",
                "is_ssl_verify": false,
                "ssl_verification_mode": "none",
                "ssl_insecure_skip_verify": false,
                "ssl_certificate_authorities": "",
                "ssl_certificate": "",
                "ssl_certificate_key": "",
                "raw_ssl_certificate_authorities": "",
                "raw_ssl_certificate": "",
                "raw_ssl_certificate_key": "",
                "cluster_id": 4,
                "cluster_name": "redis_cluster_01",
                "display_name": "Redis集群01",
                "version": "6.0.0",
                "custom_option": "",
                "registered_system": "_default",
                "creator": "admin",
                "create_time": 1700000000,
                "last_modify_user": "admin",
                "last_modify_time": 1700000000,
                "is_default_cluster": false
            },
            "cluster_type": "redis",
            "auth_info": "eyJ1c2VybmFtZSI6ICJhZG1pbiIsICJwYXNzd29yZCI6ICJwYXNzd29yZCJ9"
        }
    ],
    "result": true
}
```

#### VictoriaMetrics集群示例

```json
{
    "message": "OK",
    "code": 200,
    "data": [
        {
            "cluster_config": {
                "domain_name": "vm.domain.cluster",
                "port": 8428,
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
                "cluster_id": 5,
                "cluster_name": "vm_cluster_01",
                "display_name": "VM集群01",
                "version": "1.87.0",
                "custom_option": "",
                "registered_system": "_default",
                "creator": "admin",
                "create_time": 1700000000,
                "last_modify_user": "admin",
                "last_modify_time": 1700000000,
                "is_default_cluster": false
            },
            "cluster_type": "victoria_metrics",
            "auth_info": "eyJ1c2VybmFtZSI6ICIiLCAicGFzc3dvcmQiOiAiIn0="
        }
    ],
    "result": true
}
```

#### Doris集群示例

```json
{
    "message": "OK",
    "code": 200,
    "data": [
        {
            "cluster_config": {
                "domain_name": "doris.domain.cluster",
                "port": 9030,
                "extranet_domain_name": "",
                "extranet_port": 0,
                "schema": "mysql",
                "is_ssl_verify": false,
                "ssl_verification_mode": "none",
                "ssl_insecure_skip_verify": false,
                "ssl_certificate_authorities": "",
                "ssl_certificate": "",
                "ssl_certificate_key": "",
                "raw_ssl_certificate_authorities": "",
                "raw_ssl_certificate": "",
                "raw_ssl_certificate_key": "",
                "cluster_id": 6,
                "cluster_name": "doris_cluster_01",
                "display_name": "Doris集群01",
                "version": "1.2.0",
                "custom_option": "",
                "registered_system": "_default",
                "creator": "admin",
                "create_time": 1700000000,
                "last_modify_user": "admin",
                "last_modify_time": 1700000000,
                "is_default_cluster": false
            },
            "cluster_type": "doris",
            "auth_info": "eyJ1c2VybmFtZSI6ICJhZG1pbiIsICJwYXNzd29yZCI6ICJwYXNzd29yZCJ9"
        }
    ],
    "result": true
}
```

#### Argus集群示例

```json
{
    "message": "OK",
    "code": 200,
    "data": [
        {
            "cluster_config": {
                "domain_name": "argus.domain.cluster",
                "port": 8080,
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
                "cluster_id": 7,
                "cluster_name": "argus_cluster_01",
                "display_name": "Argus集群01",
                "version": "1.0.0",
                "custom_option": "",
                "registered_system": "_default",
                "creator": "admin",
                "create_time": 1700000000,
                "last_modify_user": "admin",
                "last_modify_time": 1700000000,
                "is_default_cluster": false
            },
            "cluster_type": "argus",
            "auth_info": "eyJ1c2VybmFtZSI6ICJhZG1pbiIsICJwYXNzd29yZCI6ICJwYXNzd29yZCJ9"
        }
    ],
    "result": true
}
```

#### BkData集群示例

```json
{
    "message": "OK",
    "code": 200,
    "data": [
        {
            "cluster_config": {
                "domain_name": "bkdata.domain.cluster",
                "port": 8080,
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
                "cluster_id": 8,
                "cluster_name": "bkdata_cluster_01",
                "display_name": "BkData集群01",
                "version": "1.0.0",
                "custom_option": "",
                "registered_system": "bkdata",
                "creator": "admin",
                "create_time": 1700000000,
                "last_modify_user": "admin",
                "last_modify_time": 1700000000,
                "is_default_cluster": false
            },
            "cluster_type": "bkdata",
            "auth_info": "eyJ1c2VybmFtZSI6ICJhZG1pbiIsICJwYXNzd29yZCI6ICJwYXNzd29yZCJ9"
        }
    ],
    "result": true
}
```
