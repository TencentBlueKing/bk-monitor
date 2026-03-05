### 功能描述

查询数据源信息

### 请求参数

| 字段           | 类型   | 必选 | 描述                                     |
|--------------|------|----|----------------------------------------|
| bk_data_id   | int  | 否  | 数据源 ID，与 `data_name` 二选一，指定此参数时不使用租户过滤 |
| data_name    | str  | 否  | 数据源名称，与 `bk_data_id` 二选一               |
| with_rt_info | bool | 否  | 是否返回关联的结果表信息，默认为 `true`                |

> 注意：`bk_data_id` 和 `data_name` 不能同时为空，`bk_data_id` 优先级高于 `data_name`

### 请求参数示例

```json
{
    "bk_data_id": 1001,
    "with_rt_info": true
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 数据源详情  |

#### data 字段说明

| 字段                  | 类型         | 描述                                  |
|---------------------|------------|-------------------------------------|
| bk_data_id          | int        | 数据源 ID                              |
| data_id             | int        | 数据源 ID（同 bk_data_id）                |
| bk_tenant_id        | str        | 租户 ID                               |
| data_name           | str        | 数据源名称                               |
| etl_config          | str        | 清洗模板配置                              |
| option              | dict       | 数据源配置项                              |
| type_label          | str        | 数据类型标签                              |
| source_label        | str        | 数据来源标签                              |
| token               | str        | 数据源 Token                           |
| transfer_cluster_id | str        | Transfer 集群 ID                      |
| is_platform_data_id | bool       | 是否为平台级 ID                           |
| space_type_id       | str        | 数据源所属空间类型                           |
| space_uid           | str        | 数据源所属空间 UID                         |
| bk_biz_id           | int        | 业务 ID                               |
| mq_config           | dict       | 消息队列配置                              |
| result_table_list   | list[dict] | 关联的结果表列表（当 `with_rt_info=true` 时返回） |

#### data.mq_config 字段说明

| 字段             | 类型   | 描述                        |
|----------------|------|---------------------------|
| storage_config | dict | 存储配置，包含 topic 和 partition |
| batch_size     | int  | 批量大小                      |
| flush_interval | int  | 刷新间隔                      |
| consume_rate   | int  | 消费速率                      |
| cluster_config | dict | 集群配置                      |
| cluster_type   | str  | 集群类型                      |
| auth_info      | dict | 认证信息                      |

#### data.mq_config.cluster_config 字段说明

| 字段                              | 类型    | 描述                        |
|---------------------------------|-------|---------------------------|
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
| cluster_id                      | int   | 集群 ID                     |
| cluster_name                    | str   | 集群名称                      |
| display_name                    | str   | 集群显示名称                    |
| version                         | str   | 集群版本                      |
| custom_option                   | str   | 自定义标签                     |
| registered_system               | str   | 注册来源系统                    |
| creator                         | str   | 创建者                       |
| create_time                     | float | 创建时间（Unix 时间戳）            |
| last_modify_user                | str   | 最后修改者                     |
| is_default_cluster              | bool  | 是否为默认集群                   |

#### data.result_table_list 元素字段说明

| 字段           | 类型         | 描述        |
|--------------|------------|-----------|
| bk_biz_id    | int        | 业务 ID     |
| bk_tenant_id | str        | 租户 ID     |
| result_table | str        | 结果表 ID    |
| shipper_list | list[dict] | 存储配置列表    |
| field_list   | list[dict] | 字段列表      |
| schema_type  | str        | Schema 类型 |
| option       | dict       | 结果表配置项    |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "bk_data_id": 1001,
        "data_id": 1001,
        "bk_tenant_id": "system",
        "data_name": "my_data_source",
        "etl_config": "bk_standard_v2_time_series",
        "option": {},
        "type_label": "time_series",
        "source_label": "bk_monitor",
        "token": "abc123",
        "transfer_cluster_id": "default",
        "is_platform_data_id": false,
        "space_type_id": "bkcc",
        "space_uid": "bkcc__2",
        "bk_biz_id": 2,
        "mq_config": {
            "storage_config": {
                "topic": "0bkmonitor_10010",
                "partition": 1
            },
            "batch_size": 0,
            "flush_interval": 0,
            "consume_rate": 0,
            "cluster_config": {
                "domain_name": "kafka.example.com",
                "port": 9092
            },
            "cluster_type": "kafka",
            "auth_info": {
                "username": "",
                "password": ""
            }
        },
        "result_table_list": [
            {
                "bk_biz_id": 2,
                "bk_tenant_id": "system",
                "result_table": "2_bkmonitor_time_series_1001.__default__",
                "shipper_list": [],
                "field_list": [],
                "schema_type": "free",
                "option": {}
            }
        ]
    }
}
```
