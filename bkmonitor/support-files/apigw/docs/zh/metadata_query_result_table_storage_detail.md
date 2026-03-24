### 功能描述

查询结果表的存储详情

### 请求参数

| 字段             | 类型  | 必选 | 描述                                         |
|----------------|-----|----|--------------------------------------------|
| bk_data_id     | int | 否  | 数据源 ID，与 `table_id`、`bcs_cluster_id` 三选一   |
| table_id       | str | 否  | 结果表 ID，与 `bk_data_id`、`bcs_cluster_id` 三选一 |
| bcs_cluster_id | str | 否  | BCS 集群 ID，与 `bk_data_id`、`table_id` 三选一    |

> 注意：`bk_data_id`、`table_id`、`bcs_cluster_id` 不能同时为空

### 请求参数示例

```json
{
    "table_id": "2_bkmonitor_time_series_1001.__default__"
}
```

### 响应参数

| 字段      | 类型         | 描述                           |
|---------|------------|------------------------------|
| result  | bool       | 请求是否成功                       |
| code    | int        | 返回的状态码                       |
| message | str        | 描述信息                         |
| data    | list[dict] | 结果表存储详情列表，每个元素对应一个结果表的完整链路信息 |

#### data 元素字段说明

| 字段                        | 类型   | 描述                         |
|---------------------------|------|----------------------------|
| data_source               | dict | 数据源基本信息                    |
| transfer_cluster          | str  | Transfer 集群 ID             |
| kafka_config              | dict | Kafka 配置信息                 |
| result_table              | dict | 结果表信息                      |
| bk_biz_info               | dict | 业务信息                       |
| influxdb                  | dict | InfluxDB 存储配置（无则为空对象）      |
| elasticsearch             | dict | Elasticsearch 存储配置（无则为空对象） |
| kafka                     | dict | Kafka 存储配置（无则为空对象）         |
| redis                     | dict | Redis 存储配置（无则为空对象）         |
| bkdata                    | dict | 计算平台存储配置（无则为空对象）           |
| argus                     | dict | Argus 存储配置（无则为空对象）         |
| victoria_metrics          | dict | VM 存储配置（无则为空对象）            |
| influxdb_instance_cluster | list | InfluxDB 实例集群信息            |

#### data.data_source 字段说明

| 字段           | 类型    | 描述                |
|--------------|-------|-------------------|
| bk_data_id   | int   | 数据源 ID            |
| bk_data_name | str   | 数据源名称             |
| space_uid    | str   | 所属空间 UID          |
| etl_config   | str   | 清洗模板配置            |
| creator      | str   | 创建者               |
| updater      | str   | 最后修改者             |
| cluster_id   | str   | 关联的 BCS 集群 ID（如有） |
| is_enable    | bool  | 是否启用              |
| create_time  | float | 创建时间（Unix 时间戳）    |
| created_from | str   | 创建来源              |

#### data.kafka_config 字段说明

| 字段               | 类型  | 描述           |
|------------------|-----|--------------|
| topic            | str | Kafka Topic  |
| partition        | int | 分区数          |
| cluster_name     | str | 集群名称         |
| domain_name      | str | 集群域名         |
| port             | int | 集群端口         |
| username         | str | 用户名          |
| password         | str | 密码           |
| version          | str | 集群版本         |
| schema           | str | 访问协议         |
| gse_stream_to_id | int | GSE 接收端配置 ID |

#### data.result_table 字段说明

| 字段                | 类型   | 描述      |
|-------------------|------|---------|
| table_id          | str  | 结果表 ID  |
| result_table_name | str  | 结果表中文名称 |
| is_enable         | bool | 是否启用    |

#### data.bk_biz_info 字段说明

| 字段          | 类型  | 描述    |
|-------------|-----|-------|
| bk_biz_id   | int | 业务 ID |
| bk_biz_name | str | 业务名称  |

#### data.victoria_metrics 字段说明

| 字段                 | 类型  | 描述         |
|--------------------|-----|------------|
| vm_cluster_domain  | str | VM 集群域名    |
| vm_cluster_id      | int | VM 集群 ID   |
| bk_base_data_id    | int | 计算平台数据源 ID |
| vm_result_table_id | str | VM 结果表 ID  |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "data_source": {
                "bk_data_id": 1001,
                "bk_data_name": "my_data_source",
                "space_uid": "bkcc__2",
                "etl_config": "bk_standard_v2_time_series",
                "creator": "admin",
                "updater": "admin",
                "cluster_id": "",
                "is_enable": true,
                "create_time": 1704067200.0,
                "created_from": "bk_monitor"
            },
            "transfer_cluster": "default",
            "kafka_config": {
                "topic": "0bkmonitor_10010",
                "partition": 1,
                "cluster_name": "kafka_cluster_01",
                "domain_name": "kafka.example.com",
                "port": 9092,
                "username": "",
                "password": "",
                "version": "2.8.0",
                "schema": ""
            },
            "result_table": {
                "table_id": "2_bkmonitor_time_series_1001.__default__",
                "result_table_name": "默认结果表",
                "is_enable": true
            },
            "bk_biz_info": {
                "bk_biz_id": 2,
                "bk_biz_name": "蓝鲸"
            },
            "influxdb": {},
            "elasticsearch": {},
            "kafka": {},
            "redis": {},
            "bkdata": {},
            "argus": {},
            "victoria_metrics": {
                "vm_cluster_domain": "vm.example.com",
                "vm_cluster_id": 1,
                "bk_base_data_id": 12345,
                "vm_result_table_id": "vm_rt_1001"
            },
            "influxdb_instance_cluster": []
        }
    ]
}
```
