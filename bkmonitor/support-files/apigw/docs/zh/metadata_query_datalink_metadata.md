### 功能描述

查询数据链路元信息

### 请求参数

| 字段           | 类型  | 必选 | 描述                |
|--------------|-----|----|-------------------|
| bk_data_id   | str | 是  | 数据源ID             |

### 请求参数示例

```json
{
    "bk_data_id": "1001"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | object | 返回数据   |

#### data 字段说明

| 字段            | 类型     | 描述          |
|---------------|--------|-------------|
| data_source   | object | 数据源基础信息     |
| kafka_config  | object | Kafka 配置信息  |
| result_tables | list   | 结果表信息列表     |

#### data.data_source 字段说明

| 字段                   | 类型   | 描述                              |
|----------------------|------|---------------------------------|
| bk_data_id           | int  | 数据源ID                           |
| data_name            | str  | 数据源名称                           |
| source_system        | str  | 来源系统                            |
| etl_config           | str  | 清洗配置                            |
| is_enabled           | bool | 是否启用                            |
| is_platform_data_id  | bool | 是否为平台级数据源                       |
| created_from         | str  | 数据源来源                           |
| transfer_cluster_id  | str  | Transfer 集群ID                   |
| data_link_version    | str  | 链路版本，`v4` 表示计算平台链路，`v3` 表示监控链路  |

#### data.kafka_config 字段说明

| 字段           | 类型  | 描述          |
|--------------|-----|-------------|
| cluster_id   | int | Kafka 集群ID  |
| cluster_name | str | Kafka 集群名称  |
| domain_name  | str | Kafka 集群域名  |
| topic        | str | Kafka Topic |
| partition    | int | 分区数量        |

#### data.result_tables 元素字段说明

| 字段              | 类型     | 描述                                    |
|-----------------|--------|---------------------------------------|
| table_id        | str    | 结果表ID                                 |
| storage_type    | str    | 存储类型                                  |
| bk_biz_id       | int    | 业务ID                                  |
| space_uid       | str    | 空间UID                                 |
| space_name      | str    | 空间名称                                  |
| is_enabled      | bool   | 是否启用                                  |
| data_label      | str    | 数据标签                                  |
| storage_details | object | 存储详情，根据存储类型不同内容不同（ES 或 VM 存储时存在）      |
| backend_kafka   | object | 后端 Kafka 配置，存在后端 Kafka 时返回（可能不存在）     |

#### data.result_tables[].storage_details 字段说明（ES 存储）

| 字段               | 类型  | 描述              |
|------------------|-----|-----------------|
| type             | str | 存储类型，固定为 `elasticsearch` |
| cluster_id       | int | ES 集群ID         |
| cluster_name     | str | ES 集群名称         |
| domain_name      | str | ES 集群域名         |
| index_set        | str | 索引集             |
| slice_size_gb    | int | 索引大小切分阈值（GB）    |
| slice_gap_minutes | int | 索引分片时间间隔（分钟）    |

#### data.result_tables[].storage_details 字段说明（VM 存储）

| 字段      | 类型         | 描述        |
|---------|------------|-----------|
| type    | str        | 存储类型，固定为 `vm` |
| records | list[dict] | VM 接入记录列表 |

#### data.result_tables[].storage_details.records 元素字段说明（VM 存储）

| 字段                  | 类型  | 描述          |
|---------------------|-----|-------------|
| vm_result_table_id  | str | VM 结果表ID    |
| vm_cluster_id       | int | VM 查询集群ID   |
| storage_cluster_id  | int | VM 接入集群ID   |
| bk_base_data_id     | int | 计算平台数据源ID   |
| domain_name         | str | VM 集群域名     |

#### data.result_tables[].backend_kafka 字段说明

| 字段           | 类型  | 描述              |
|--------------|-----|-----------------|
| cluster_id   | int | 后端 Kafka 集群ID   |
| cluster_name | str | 后端 Kafka 集群名称   |
| domain_name  | str | 后端 Kafka 集群域名   |
| topic        | str | 后端 Kafka Topic  |
| partition    | int | 分区数量            |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "data_source": {
            "bk_data_id": 1001,
            "data_name": "test_data_source",
            "source_system": "bk_monitor",
            "etl_config": "bk_standard_v2_time_series",
            "is_enabled": true,
            "is_platform_data_id": false,
            "created_from": "bk_monitor",
            "transfer_cluster_id": "default",
            "data_link_version": "v3"
        },
        "kafka_config": {
            "cluster_id": 1,
            "cluster_name": "kafka-default",
            "domain_name": "kafka.example.com:9092",
            "topic": "0bkmonitor_10010",
            "partition": 1
        },
        "result_tables": [
            {
                "table_id": "2_bkmonitor_time_series_1001.__default__",
                "storage_type": "influxdb",
                "bk_biz_id": 2,
                "space_uid": "bkcc__2",
                "space_name": "蓝鲸",
                "is_enabled": true,
                "data_label": "",
                "storage_details": {
                    "type": "vm",
                    "records": [
                        {
                            "vm_result_table_id": "2_bkmonitor_time_series_1001.__default__",
                            "vm_cluster_id": 1,
                            "storage_cluster_id": 1,
                            "bk_base_data_id": 30001,
                            "domain_name": "vm.example.com"
                        }
                    ]
                }
            }
        ]
    }
}
```
