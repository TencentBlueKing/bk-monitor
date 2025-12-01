### 功能描述

应用详情

### 请求参数

| 字段名            | 类型  | 是否必选 | 描述     |
|----------------|-----|------|--------|
| application_id | int | 否    | 应用ID   |
| bk_biz_id      | int | 否    | 业务ID   |
| app_name       | str | 否    | 应用名称   |
| space_uid      | str | 否    | 空间唯一标识 |

请求参数这3种情况一定要传参一种情况：application_id, or bk_biz_id + app_name, or space_uid + app_name

### 请求参数示例

```json
{
  "application_id": 88
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 应用详情信息 |

#### data

| 字段                   | 类型   | 描述                |
|----------------------|------|-------------------|
| id                   | int  | 应用ID              |
| create_user          |      | 创建人               |
| create_time          |      | 创建时间              |
| update_user          |      | 最后修改人             |
| update_time          |      | 最后修改时间            |
| bk_biz_id            | int  | 业务ID              |
| app_name             | str  | 应用名称              |
| app_alias            | str  | 应用别名              |
| description          | str  | 应用描述              |
| token                | str  | 应用 Token          |
| is_enabled_log       | bool | 是否开启 Logs 功能      |
| is_enabled_trace     | bool | 是否开启 Traces 功能    |
| is_enabled_metric    | bool | 是否开启 Metrics 功能   |
| is_enabled_profiling | bool | 是否开启 Profiling 功能 |
| bk_tenant_id         | str  | 租户ID              |
| metric_config        | dict | 指标数据源配置           |
| trace_config         | dict | 调用链数据源配置          |
| profiling_config     | dict | 性能分析数据源配置         |
| log_config           | dict | 日志数据源配置           |

#### data.metric_config

| 字段                   | 类型  | 描述     |
|----------------------|-----|--------|
| bk_data_id           | int | 数据源ID  |
| result_table_id      | str | 结果表ID  |
| time_series_group_id | int | 时序分组ID |

#### data.trace_config

| 字段              | 类型  | 描述    |
|-----------------|-----|-------|
| bk_data_id      | int | 数据源ID |
| result_table_id | str | 结果表ID |
| index_set_id    | int | 索引集ID |

#### data.profiling_config

| 字段              | 类型  | 描述    |
|-----------------|-----|-------|
| bk_data_id      | int | 数据源ID |
| result_table_id | str | 结果表ID |

#### data.log_config

| 字段                  | 类型  | 描述     |
|---------------------|-----|--------|
| bk_data_id          | int | 数据源ID  |
| result_table_id     | str | 结果表ID  |
| collector_config_id | int | 采集配置ID |
| index_set_id        | int | 索引集ID  |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "id": 88,
        "create_user": "admin",
        "create_time": "2025-02-26 11:32:40+0800",
        "update_user": "admin",
        "update_time": "2025-02-26 11:32:40+0800",
        "bk_biz_id": 2,
        "app_name": "my_app",
        "app_alias": "my_app",
        "description": "my_app",
        "token": "f9d9746xxxef401xxxxdd4c12150xxxx",
        "is_enabled_log": true,
        "is_enabled_trace": true,
        "is_enabled_metric": true,
        "is_enabled_profiling": true,
        "bk_tenant_id": "system",
        "metric_config": {
            "bk_data_id": 666,
            "result_table_id": "2_xxx_metric_my_app.__default__",
            "time_series_group_id": 665
        },
        "trace_config": {
            "bk_data_id": 887,
            "result_table_id": "2_bkapm.trace_my_app",
            "index_set_id": 888
        },
        "profiling_config": {
            "bk_data_id": 524948,
            "result_table_id": "2_profile_my_app2"
        },
        "log_config": {
            "bk_data_id": 998,
            "result_table_id": "2_xxx.my_app",
            "collector_config_id": 674,
            "index_set_id": 999
        }
    }
}
```
