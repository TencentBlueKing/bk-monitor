### 功能描述

创建监控结果表

### 请求参数

| 字段                     | 类型     | 是否必选 | 描述                                                                                                                   |
|------------------------|--------|------|----------------------------------------------------------------------------------------------------------------------|
| bk_data_id             | int    | 是    | 数据源ID                                                                                                                |
| table_id               | string | 是    | 结果表ID，格式应该为 库.表(例如，system.cpu)                                                                                       |
| table_name_zh          | string | 是    | 结果表中文名                                                                                                               |
| is_custom_table        | bool   | 是    | 是否用户自定义结果表                                                                                                           |
| schema_type            | string | 是    | 结果表字段配置方案, free(无schema配置), fixed(固定schema)                                                                          |
| operator               | string | 是    | 操作者                                                                                                                  |
| default_storage        | string | 是    | 默认存储类型，目前支持influxdb、elasticsearch、kafka、redis等                                                                       |
| bk_biz_id              | int    | 否    | 业务ID，默认为0（全业务）结果表；如果非零时，将会校验结果表命名规范                                                                                  |
| label                  | string | 否    | 结果表标签，此处记录的是二级标签，对应一级标签将由二级标签推导得到。应该通过`metadata_list_label`接口获取                                                      |
| default_storage_config | dict   | 否    | 默认的存储信息，根据每种不同的存储，会有不同的配置内容，如果不提供则会使用默认值；具体内容请参考下面的具体说明                                                              |
| field_list             | list   | 否    | 字段信息列表，数组元素为object，具体字段说明见下方field_list参数说明                                                                           |
| query_alias_settings   | list   | 否    | 查询别名设置列表，用于配置字段的查询别名，具体字段说明见下方query_alias_settings参数说明                                                               |
| bk_biz_id_alias        | string | 否    | 过滤条件业务ID别名                                                                                                           |
| external_storage       | dict   | 否    | 额外存储配置，格式为{storage_type: storage_config}，storage_type可为kafka、influxdb、redis等；storage_config与default_storage_config一致 |
| is_time_field_only     | bool   | 否    | 是否仅需要提供时间默认字段                                                                                                        |
| option                 | dict   | 否    | 结果表级别的额外配置信息，格式为{option_name: option_value}，具体选项见下方说明                                                                |
| time_alias_name        | string | 否    | 时间字段别名，用于指定上报数据时使用的时间字段名                                                                                             |
| time_option            | dict   | 否    | 时间字段的选项配置                                                                                                            |
| is_sync_db             | bool   | 否    | 是否需要同步创建真实表                                                                                                          |
| data_label             | string | 否    | 数据标签                                                                                                                 |

#### 参数: option 结果表级别可选配置项

| 选项名                    | 类型     | 描述              |
|------------------------|--------|-----------------|
| cmdb_level_config      | list   | CMDB层级拆分配置      |
| group_info_alias       | string | 分组标识字段别名        |
| es_unique_field_list   | list   | ES生成doc_id的字段列表 |
| segmented_query_enable | bool   | 分段查询开关          |

#### 参数: field_list 字段列表的具体参数说明

| 字段                | 类型     | 是否必选 | 默认值  | 描述                                                        |
|-------------------|--------|------|------|-----------------------------------------------------------|
| field_name        | string | 是    | -    | 字段名                                                       |
| field_type        | string | 是    | -    | 字段类型，可以为float、string、boolean和timestamp                    |
| tag               | string | 是    | -    | 字段标签，可以为metric（指标）、dimension（维度）、timestamp（时间戳）、group（分组） |
| unit              | string | 否    | ""   | 字段单位                                                      |
| description       | string | 否    | ""   | 字段描述信息                                                    |
| alias_name        | string | 否    | ""   | 入库别名                                                      |
| option            | dict   | 否    | {}   | 字段选项配置，键为选项名，值为选项配置，具体选项见下方说明                             |
| is_reserved_check | bool   | 否    | True | 是否进行保留字检查                                                 |

##### field_list.option 字段级别可选配置项

| 选项名               | 类型     | 描述                                      |
|-------------------|--------|-----------------------------------------|
| es_type           | string | ES配置：映射实际字段类型                           |
| es_include_in_all | bool   | ES配置：是否包含到_all字段中                       |
| es_format         | string | ES配置：时间格式                               |
| es_doc_values     | bool   | ES配置：是否维度                               |
| es_index          | string | ES配置：是否分词，值可以为true或false                |
| time_format       | string | 数据源时间格式，供Transfer解析上报时间                 |
| time_zone         | int    | 时区配置，供Transfer解析上报时间为UTC，取值范围[-12, +12] |

#### 参数: query_alias_settings 查询别名设置的具体参数说明

| 字段          | 类型     | 是否必选 | 描述           |
|-------------|--------|------|--------------|
| field_name  | string | 是    | 需要设置查询别名的字段名 |
| query_alias | string | 是    | 字段的查询别名      |

#### 参数: default_storage_config 及 external_storage 中的存储配置说明

##### InfluxDB 存储配置参数

| 键值                   | 类型     | 是否必选 | 默认值             | 描述                    |
|----------------------|--------|------|-----------------|-----------------------|
| storage_cluster_id   | int    | 否    | 使用该存储类型的默认存储集群  | 指定存储集群ID              |
| database             | string | 否    | table_id的点分第一部分 | 存储的数据库名               |
| real_table_name      | string | 否    | table_id的点分第二部分 | 实际存储表名                |
| source_duration_time | string | 否    | 30d             | 数据保存时间，需要符合InfluxDB格式 |

##### Kafka 存储配置参数

| 键值                 | 类型     | 是否必选 | 默认值                            | 描述                                                             |
|--------------------|--------|------|--------------------------------|----------------------------------------------------------------| 
| storage_cluster_id | int    | 否    | 使用该存储类型的默认存储集群                 | 指定存储集群ID                                                       |
| topic              | string | 否    | 0bkmonitor_storage_${table_id} | 存储的topic名称                                                     |
| partition          | int    | 否    | 1                              | 存储partition数量。注意：此处只是记录，如果需要超过1个partition，需要手动通过kafka命令行工具进行扩容 |
| retention          | int    | 否    | 1800000                        | Kafka数据保存时长，默认是半小时，单位为毫秒(ms)                                   |

##### Redis 存储配置参数

| 键值                 | 类型     | 是否必选 | 默认值            | 描述             |
|--------------------|--------|------|----------------|----------------|
| storage_cluster_id | int    | 否    | 使用该存储类型的默认存储集群 | 指定存储集群ID       |
| key                | string | 否    | table_id名字     | 存储键值           |
| db                 | int    | 否    | 0              | 使用的Redis数据库编号  |
| command            | string | 否    | PUBLISH        | 存储命令           |
| is_sentinel        | bool   | 否    | False          | 是否使用哨兵模式       |
| master_name        | string | 否    | ""             | 哨兵模式下的master名称 |

**注意**: 由于Redis默认使用队列方式，消费后就丢弃，因此没有时长配置

##### Elasticsearch 存储配置参数

| 键值                 | 类型     | 是否必选 | 默认值      | 描述                          |
|--------------------|--------|------|----------|-----------------------------|
| storage_cluster_id | int    | 否    | -        | 指定存储集群ID，不指定则使用该存储类型的默认存储集群 |
| retention          | int    | 否    | 30       | 保留index时间，单位为天，默认保留30天      |
| date_format        | string | 否    | %Y%m%d%H | 时间格式，默认精确到小时                |
| slice_size         | int    | 否    | 500      | 需要切分的大小阈值，单位为GB，默认为500GB    |
| slice_gap          | int    | 否    | 120      | index分片时间间隔，单位为分钟，默认2小时     |
| index_settings     | dict   | 否    | -        | 索引创建配置，JSON格式               |
| mapping_settings   | dict   | 否    | -        | 索引mapping配置（不包含字段定义），JSON格式 |

**注意**: 实际index构造方式为 `${table_id}_${date_format}_${current_index}`

### 请求参数示例

```json
{
    "bk_data_id": 1001,
    "table_id": "system.cpu_detail",
    "table_name_zh": "CPU记录",
    "is_custom_table": true,
    "schema_type": "fixed",
    "operator": "username",
    "default_storage": "influxdb",
    "default_storage_config": {
        "storage_cluster_id": 1,
        "source_duration_time": "30d"
    },
    "field_list": [{
        "field_name": "usage",
        "field_type": "double",
        "description": "CPU使用率",
        "tag": "metric",
        "unit": "percent",
        "alias_name": "usage_alias",
        "option": {
            "es_type": "double"
        },
        "is_reserved_check": true
    }],
    "label": "os",
    "external_storage": {
        "kafka": {
            "retention": 1800000
        }
    },
    "option": {
        "group_info_alias": "target"
    },
    "bk_biz_id": 2
}
```

### 响应参数

| 字段         | 类型     | 描述     |
|------------|--------|--------|
| result     | bool   | 请求是否成功 |
| code       | int    | 返回的状态码 |
| message    | string | 描述信息   |
| data       | dict   | 数据     |
| request_id | string | 请求ID   |

#### data字段说明

| 字段       | 类型     | 描述    |
|----------|--------|-------|
| table_id | string | 结果表ID |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
    	"table_id": "system.cpu_detail"
    },
    "result": true,
    "request_id": "408233306947415bb1772a86b9536867"
}
```
