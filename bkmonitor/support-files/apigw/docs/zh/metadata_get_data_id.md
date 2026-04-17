### 功能描述

获取监控数据ID信息

### 请求参数

| 字段           | 类型     | 必选 | 描述                         |
|--------------|--------|----|----------------------------|
| bk_data_id   | int    | 否  | 数据源ID                      |
| data_name    | string | 否  | 数据源名称                      |
| with_rt_info | bool   | 否  | 是否需要ResultTable信息（默认是True） |

> 注意：
> 1. 上述两个必须提供一个，不可以两者同时为空;
> 2. 当bk_data_id提供时，data_name无效

### 请求参数示例

```json
{
	"bk_data_id": 1001,
    "with_rt_info": false
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

| 字段                  | 类型     | 描述                           |
|---------------------|--------|------------------------------|
| bk_data_id          | int    | 数据源ID                        |
| data_id             | int    | 数据源ID（与bk_data_id相同）         |
| bk_tenant_id        | string | 租户ID                         |
| data_name           | string | 数据源名称                        |
| mq_config           | dict   | 消息队列集群信息                     |
| etl_config          | string | 清洗配置名称                       |
| option              | dict   | 数据源配置选项                      |
| type_label          | string | 数据类型标签                       |
| source_label        | string | 数据源标签                        |
| token               | string | dataID的验证码                   |
| transfer_cluster_id | string | transfer集群ID                 |
| is_platform_data_id | bool   | 是否为平台级ID                     |
| space_type_id       | string | 空间类型ID                       |
| space_uid           | string | 空间UID                        |
| bk_biz_id           | int    | 业务ID                         |
| result_table_list   | list   | 结果表列表（当with_rt_info为true时返回） |

#### data.mq_config字段说明

| 字段             | 类型     | 描述     |
|----------------|--------|--------|
| storage_config | dict   | 存储配置信息 |
| batch_size     | int    | 批量大小   |
| flush_interval | string | 刷新间隔   |
| consume_rate   | int    | 消费速率   |
| cluster_config | dict   | 存储集群信息 |
| cluster_type   | string | 存储集群类型 |
| auth_info      | dict   | 身份认证信息 |

#### data.mq_config.storage_config字段说明

| 字段        | 类型     | 描述        |
|-----------|--------|-----------|
| topic     | string | Kafka主题名称 |
| partition | int    | 分区数       |

#### data.result_table_list元素字段说明

| 字段           | 类型     | 描述       |
|--------------|--------|----------|
| bk_biz_id    | int    | 业务ID     |
| bk_tenant_id | string | 租户ID     |
| result_table | string | 结果表ID    |
| shipper_list | list   | 存储列表     |
| field_list   | list   | 字段列表     |
| schema_type  | string | schema类型 |
| option       | dict   | 结果表选项    |

### 响应参数示例

```json
{
    "message":"OK",
    "code": 200,
    "data":{
        "bk_data_id": 1001,
        "data_id": 1001,
        "bk_tenant_id": "default",
        "data_name": "基础数据",
        "mq_config": {
            "storage_config": {
                "topic": "bk_monitor_1001",
                "partition": 1
            },
            "batch_size": 1000,
            "flush_interval": "1s",
            "consume_rate": 1000,
            "cluster_config": {
                "domain_name": "kafka.domain.cluster",
                "port": 9092
            },
            "cluster_type": "kafka",
            "auth_info": {
                "username": "",
                "password": ""
            }
        },
        "etl_config": "basereport",
        "option": {},
        "type_label": "time_series",
        "source_label": "bk_monitor_collector",
        "token": "5dc2353d913c45bea43dd8d931745a05",
        "transfer_cluster_id": "default",
        "is_platform_data_id": true,
        "space_type_id": "bkcc",
        "space_uid": "bkcc__2",
        "bk_biz_id": 2,
        "result_table_list": [
            {
                "bk_biz_id": 2,
                "bk_tenant_id": "default",
                "result_table": "system.cpu",
                "shipper_list": [],
                "field_list": [],
                "schema_type": "fixed",
                "option": {}
            }
        ]
    },
    "result":true
}
```
