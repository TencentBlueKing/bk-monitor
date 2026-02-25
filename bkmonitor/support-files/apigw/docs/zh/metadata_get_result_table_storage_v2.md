### 功能描述

查询指定结果表的指定存储信息

### 请求参数

| 字段                | 类型     | 必选 | 描述                              |
|-------------------|--------|----|---------------------------------|
| bk_tenant_id      | string | 是  | 租户ID                            |
| result_table_list | string | 是  | 结果表列表，多个结果表用英文逗号分隔              |
| storage_type      | string | 是  | 存储类型（如：influxdb、elasticsearch等） |
| is_plain_text     | bool   | 否  | 是否明文显示链接信息（默认false）             |

### 请求参数示例

```json
{
    "bk_tenant_id": "system",
    "result_table_list": "system.cpu,system.mem",
    "storage_type": "influxdb",
    "is_plain_text": false
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 数据     |

#### data字段说明

data为字典类型，key为结果表ID，value为该结果表的存储配置信息

#### data[table_id]字段说明

| 字段             | 类型          | 描述                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
|----------------|-------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| storage_config | dict        | 存储集群特性，不同存储类型字段不同：<br/>- **elasticsearch**: index_datetime_format, index_datetime_timezone, date_format, slice_size, slice_gap, retention, warm_phase_days, warm_phase_settings, base_index, index_settings, mapping_settings, bk_tenant_id<br/>- **influxdb**: real_table_name, database, retention_policy_name<br/>- **redis**: db, key, command, is_sentinel, master_name<br/>- **kafka**: topic, partition<br/>- **argus**: tenant_id<br/>- **bkdata**: 返回空字典 |
| cluster_config | dict        | 存储集群信息                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| cluster_type   | string      | 存储集群类型                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| auth_info      | dict/string | 身份认证信息（is_plain_text为false时对auth_info字典进行base64编码）                                                                                                                                                                                                                                                                                                                                                                                                                |

### 响应参数示例

#### InfluxDB存储示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "system.cpu": {
            "storage_config": {
                "real_table_name": "cpu",
                "database": "system",
                "retention_policy_name": "autogen"
            },
            "cluster_config": {
                "domain_name": "influxdb.domain.cluster",
                "port": 8086,
                "instance_cluster_name": "default"
            },
            "cluster_type": "influxDB",
            "auth_info": "eyJ1c2VybmFtZSI6ICJhZG1pbiIsICJwYXNzd29yZCI6ICJwYXNzd29yZCJ9"
        }
    },
    "result": true
}
```

#### Elasticsearch存储示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "system.disk": {
            "storage_config": {
                "index_datetime_format": "write_200601021504",
                "index_datetime_timezone": "Asia/Shanghai",
                "date_format": "%Y%m%d%H%M",
                "slice_size": 1000,
                "slice_gap": 100,
                "retention": "30d",
                "warm_phase_days": 7,
                "warm_phase_settings": {},
                "base_index": "system_disk",
                "index_settings": {},
                "mapping_settings": {},
                "bk_tenant_id": "system"
            },
            "cluster_config": {
                "domain_name": "es.domain.cluster",
                "port": 9200
            },
            "cluster_type": "elasticsearch",
            "auth_info": "eyJ1c2VybmFtZSI6ICJhZG1pbiIsICJwYXNzd29yZCI6ICJwYXNzd29yZCJ9"
        }
    },
    "result": true
}
```

#### Kafka存储示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "system.network": {
            "storage_config": {
                "topic": "bkmonitorv3_system_network",
                "partition": 1
            },
            "cluster_config": {
                "domain_name": "kafka.domain.cluster",
                "port": 9092
            },
            "cluster_type": "kafka",
            "auth_info": "eyJ1c2VybmFtZSI6ICJhZG1pbiIsICJwYXNzd29yZCI6ICJwYXNzd29yZCJ9"
        }
    },
    "result": true
}
```

#### Redis存储示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "system.alert": {
            "storage_config": {
                "db": 0,
                "key": "bkmonitorv3_system_alert",
                "command": "PUBLISH",
                "is_sentinel": false,
                "master_name": ""
            },
            "cluster_config": {
                "domain_name": "redis.domain.cluster",
                "port": 6379
            },
            "cluster_type": "redis",
            "auth_info": "eyJ1c2VybmFtZSI6ICJhZG1pbiIsICJwYXNzd29yZCI6ICJwYXNzd29yZCJ9"
        }
    },
    "result": true
}
```

#### Argus存储示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "system.backup": {
            "storage_config": {
                "tenant_id": "tenant_001"
            },
            "cluster_config": {
                "domain_name": "argus.domain.cluster",
                "port": 8080
            },
            "cluster_type": "argus",
            "auth_info": "eyJ1c2VybmFtZSI6ICJhZG1pbiIsICJwYXNzd29yZCI6ICJwYXNzd29yZCJ9"
        }
    },
    "result": true
}
```

#### BkData存储示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "system.bkdata": {
            "storage_config": {},
            "cluster_config": {
                "domain_name": "bkdata.domain.cluster",
                "port": 8080
            },
            "cluster_type": "bkdata",
            "auth_info": "eyJ1c2VybmFtZSI6ICJhZG1pbiIsICJwYXNzd29yZCI6ICJwYXNzd29yZCJ9"
        }
    },
    "result": true
}
```
