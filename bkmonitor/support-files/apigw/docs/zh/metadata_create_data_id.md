### 功能描述

创建监控数据ID

### 请求参数

| 字段                  | 类型        | 必选 | 描述                                                                    |
|---------------------|-----------|----|-----------------------------------------------------------------------|
| data_name           | string    | 是  | 数据源名称                                                                 |
| etl_config          | string    | 是  | 清洗模板配置，prometheus exportor对应"prometheus"                              |
| operator            | string    | 是  | 操作者                                                                   |
| source_label        | string    | 是  | 数据来源标签，例如：数据平台(bk_data)，监控采集器(bk_monitor_collector)。**必须使用系统预定义的标签值** |
| type_label          | string    | 是  | 数据类型标签，例如：时序数据(time_series)，事件数据(event)，日志数据(log)。**必须使用系统预定义的标签值**   |
| bk_biz_id           | int       | 否  | 业务ID                                                                  |
| bk_data_id          | int       | 否  | 数据源ID                                                                 |
| mq_cluster          | int       | 否  | 数据源使用的消息集群                                                            |
| mq_config           | dict      | 否  | 数据源消息队列配置                                                             |
| data_description    | string    | 否  | 数据源的具体描述                                                              |
| is_custom_source    | bool      | 否  | 是否用户自定义数据源，默认为是                                                       |
| option              | dict      | 否  | 数据源配置选项内容，格式为{`option_name`: `option_value`}                          |
| custom_label        | string    | 否  | 自定义标签配置信息                                                             |
| transfer_cluster_id | string    | 否  | transfer集群ID                                                          |
| space_uid           | string    | 否  | 空间唯一标识                                                                |
| authorized_spaces   | list[str] | 否  | 授权使用的空间ID列表                                                           |
| is_platform_data_id | bool      | 否  | 是否为平台级ID，默认为False                                                     |
| space_type_id       | string    | 否  | 数据源所属类型，默认为all（SpaceTypes.ALL.value）                                  |

**重要提示**：

- `source_label` 和 `type_label` **必须**通过 `metadata_list_label` 接口获取系统中已存在的标签值
- **不能自行创建**标签值，否则会导致接口调用失败，返回错误："标签[xxx | xxx]不存在，请确认后重试"
- 获取可用标签的方法：
    - 获取数据来源标签：调用 `metadata_list_label` 接口，参数 `label_type=source_label`
    - 获取数据类型标签：调用 `metadata_list_label` 接口，参数 `label_type=type_label`

#### option参数的可选项说明

以下是 `option` 参数中可以配置的选项：

| 选项名                      | 类型     | 描述             |
|--------------------------|--------|----------------|
| use_source_time          | bool   | 使用本地时间替换数据时间   |
| disable_metric_cutter    | bool   | 禁用指标切分         |
| allow_metrics_missing    | bool   | 允许指标字段缺失       |
| allow_dimensions_missing | bool   | 允许维度字段缺失       |
| time_precision           | string | 记录时间精度         |
| inject_local_time        | bool   | 增加入库时间指标       |
| allow_use_alias_name     | bool   | 入库字段映射改名       |
| group_info_alias         | string | GROUP_INFO别名配置 |
| timestamp_precision      | string | 时间单位的配置选项      |
| is_split_measurement     | bool   | 是否基于指标名切分      |
| align_time_unit          | string | 时间单位统一到选项      |
| drop_metrics_etl_configs | bool   | 允许指标为空时，丢弃记录选项 |

### 请求参数示例

```json
{
    "data_name": "basereport",
    "etl_config": "basereport",
    "operator": "username",
    "data_description": "basereport data source",
    "type_label": "time_series",
    "source_label": "bk_monitor_collector",
    "bk_biz_id": 2,
    "mq_cluster": 1,
    "mq_config": {
        "topic": "custom_topic"
    },
    "option": {
        "use_source_time": true,
        "disable_metric_cutter": false,
        "allow_metrics_missing": true,
        "timestamp_precision": "ms",
        "group_info_alias": "custom_group_info"
    },
    "transfer_cluster_id": "default",
    "space_uid": "bkcc__2",
    "authorized_spaces": ["bkcc__2", "bkcc__3"],
    "is_platform_data_id": false,
    "space_type_id": "bkcc"
}
```

### 响应参数

| 字段         | 类型     | 描述     |
|------------|--------|--------|
| result     | bool   | 请求是否成功 |
| code       | int    | 返回的状态码 |
| message    | string | 描述信息   |
| data       | dict   | 数据     |
| request_id | string | 请求id   |

#### data字段说明

| 字段         | 类型  | 描述    |
|------------|-----|-------|
| bk_data_id | int | 结果表ID |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "bk_data_id": 1001
    },
    "result": true,
    "request_id": "408233306947415bb1772a86b9536867"
}
```
