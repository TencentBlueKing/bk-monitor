### 功能描述

查询已注册的存储集群列表

### 请求参数

| 字段           | 类型  | 必选 | 描述                                                             |
|--------------|-----|----|----------------------------------------------------------------|
| cluster_type | str | 否  | 集群类型，可选值：`influxdb`、`elasticsearch`、`kafka`，默认为 `all` 表示查询所有类型 |
| page_size    | int | 否  | 每页条数，默认为 10                                                    |
| page         | int | 否  | 页码，最小值为 1，默认为 1                                                |

### 请求参数示例

```json
{
    "cluster_type": "elasticsearch",
    "page": 1,
    "page_size": 10
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 返回数据   |

#### data 字段说明

| 字段    | 类型         | 描述     |
|-------|------------|--------|
| total | int        | 集群总数   |
| data  | list[dict] | 集群信息列表 |

#### data.data 元素字段说明

| 字段                          | 类型   | 描述                                        |
|-----------------------------|------|-------------------------------------------|
| bk_tenant_id                | str  | 租户 ID                                     |
| cluster_id                  | int  | 集群 ID                                     |
| cluster_name                | str  | 集群英文名称                                    |
| display_name                | str  | 集群显示名称                                    |
| cluster_type                | str  | 集群类型，如 `influxdb`、`elasticsearch`、`kafka` |
| domain_name                 | str  | 集群域名                                      |
| port                        | int  | 集群端口                                      |
| extranet_domain_name        | str  | 集群外网域名                                    |
| extranet_port               | int  | 集群外网端口                                    |
| description                 | str  | 集群描述                                      |
| is_default_cluster          | bool | 是否为默认集群                                   |
| username                    | str  | 访问集群的用户名                                  |
| password                    | str  | 访问集群的密码（加密存储）                             |
| version                     | str  | 集群版本                                      |
| custom_option               | str  | 自定义标签                                     |
| schema                      | str  | 访问协议                                      |
| is_ssl_verify               | bool | 是否开启 SSL 强验证                              |
| ssl_verification_mode       | str  | CA 校验模式                                   |
| ssl_certificate_authorities | str  | CA 证书内容                                   |
| ssl_certificate             | str  | SSL/TLS 证书内容                              |
| ssl_certificate_key         | str  | SSL/TLS 证书私钥内容                            |
| ssl_insecure_skip_verify    | bool | 是否跳过服务器校验                                 |
| is_auth                     | bool | 是否开启鉴权                                    |
| sasl_mechanisms             | str  | SASL 认证机制                                 |
| security_protocol           | str  | 安全协议                                      |
| registered_system           | str  | 注册来源系统                                    |
| registered_to_bkbase        | bool | 是否已注册到计算平台                                |
| is_register_to_gse          | bool | 是否需要往 GSE 注册                              |
| gse_stream_to_id            | int  | GSE 接收端配置 ID                              |
| label                       | str  | 用途标签                                      |
| default_settings            | dict | 集群的默认配置                                   |
| creator                     | str  | 创建者                                       |
| create_time                 | str  | 创建时间，格式为 `YYYY-MM-DD HH:MM:SS`            |
| last_modify_user            | str  | 最后更新者                                     |
| last_modify_time            | str  | 最后更新时间，格式为 `YYYY-MM-DD HH:MM:SS`          |
| pipeline_name               | str  | 管道名称（固定为空字符串）                             |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "total": 2,
        "data": [
            {
                "bk_tenant_id": "system",
                "cluster_id": 1,
                "cluster_name": "es_cluster_01",
                "display_name": "ES 集群 01",
                "cluster_type": "elasticsearch",
                "domain_name": "es.example.com",
                "port": 9200,
                "extranet_domain_name": "",
                "extranet_port": 0,
                "description": "ES 集群",
                "is_default_cluster": true,
                "username": "elastic",
                "password": "******",
                "version": "7.10.0",
                "custom_option": "",
                "schema": "http",
                "is_ssl_verify": false,
                "ssl_verification_mode": "none",
                "ssl_certificate_authorities": "",
                "ssl_certificate": "",
                "ssl_certificate_key": "",
                "ssl_insecure_skip_verify": false,
                "is_auth": false,
                "sasl_mechanisms": null,
                "security_protocol": null,
                "registered_system": "_default",
                "registered_to_bkbase": false,
                "is_register_to_gse": false,
                "gse_stream_to_id": -1,
                "label": "",
                "default_settings": {},
                "creator": "admin",
                "create_time": "2023-01-01 00:00:00",
                "last_modify_user": "admin",
                "last_modify_time": "2023-06-01 12:00:00",
                "pipeline_name": ""
            }
        ]
    }
}
```
