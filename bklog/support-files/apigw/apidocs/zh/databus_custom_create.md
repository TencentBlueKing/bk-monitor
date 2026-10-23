## 功能描述

创建自定义上报采集项，调用用户需具备业务下的「创建采集项」权限。

创建时会同时创建（或复用）该采集项的索引集记录；未传 `storage_cluster_id` 时索引集处于未激活状态，不含清洗与存储配置，返回值中的 `index_set_id` 仍然有值。

## 请求参数

### 鉴权头

| 参数名称    | 参数类型 | 必须 | 参数说明     |
| ----------- | -------- | ---- | ------------ |
| bk_app_code   | string | 是   | 蓝鲸应用ID   |
| bk_app_secret | string | 是   | 蓝鲸应用秘钥 |
| bk_username | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 参数列表

| 字段                       | 类型   | 必选     | 描述                                                                                                       |
| -------------------------- | ------ | -------- | ---------------------------------------------------------------------------------------------------------- |
| bk_biz_id                  | int    | 条件必选 | 业务 ID，与 `space_uid` 二选一                                                                             |
| space_uid                  | string | 条件必选 | 空间唯一标识，例如 `bkcc__2`，与 `bk_biz_id` 二选一；同时传入时以 `space_uid` 为准                          |
| collector_config_name      | string | 是       | 采集项名称，不超过 50 个字符                                                                                |
| collector_config_name_en   | string | 是       | 采集项英文名，5~50 个字符，仅支持字母、数字、下划线；业务内唯一，同时作为结果表名使用                        |
| custom_type                | string | 是       | 日志类型，可选 `log`、`otlp_trace`、`otlp_log`；一般自定义上报填 `log`                                      |
| category_id                | string | 否       | 数据分类，默认 `application_check`                                                                          |
| description                | string | 否       | 描述信息，不超过 64 个字符，默认取 `collector_config_name`                                                  |
| data_link_id               | int    | 否       | 数据链路 ID，不传时按「业务私有链路 → 公共链路 → 默认链路」自动选择                                          |
| storage_cluster_id         | int    | 否       | 存储集群 ID，传值时创建清洗规则与存储配置；不传时仅创建采集项、数据管道和未激活的索引集记录                  |
| retention                  | int    | 条件必选 | 数据保留天数，指定 ES 类型存储集群时必填                                                                    |
| allocation_min_days        | int    | 条件必选 | n 天后的数据转入冷节点，仅集群开启冷热时生效，指定 ES 类型存储集群时必填                                     |
| es_shards                  | int    | 否       | 索引分片数，最小 1，默认取部署配置 `BKAPP_ES_SHARDS`（默认 3）                                              |
| storage_replies            | int    | 否       | 索引副本数，最小 0，默认取部署配置 `BKAPP_ES_REPLICAS`（默认 1）                                            |
| etl_config                 | string | 否       | 清洗类型，可选 `bk_log_text`、`bk_log_json`、`bk_log_delimiter`、`bk_log_regexp`；未传时按 `bk_log_text` 处理 |
| etl_params                 | dict   | 否       | 清洗参数，见下表；传入该字段（即使为 `{}` 也会被补成默认清洗参数）、`fields` 为非空列表且传入 `storage_cluster_id` 时生效 |
| fields                     | list   | 否       | 清洗字段，见下表；传入非空列表且同时传入 `etl_params`、`storage_cluster_id` 时生效；传空列表视为不指定         |
| owners                     | list   | 否       | 授权用户列表，授予采集项、索引集及所属业务的访问权限                                                        |
| ignore_exists              | bool   | 否       | 同英文名采集项已存在时是否直接复用，默认 `false`（此时返回错误）；为 `true` 时复用并返回 `created=false`      |
| auto_select_storage_cluster | bool  | 否       | 未传 `storage_cluster_id` 时是否自动选择业务可用的公共存储集群，默认 `false`；无可用集群时报错               |
| parent_index_set_ids       | list   | 否       | 归属索引集 ID 列表，与 `parent_index_set_names` 二选一，创建后加入该索引集                                   |
| parent_index_set_names     | list   | 否       | 归属索引集名称列表，与 `parent_index_set_ids` 二选一                                                        |
| sort_fields                | list   | 否       | 上下文排序字段                                                                                              |
| target_fields              | list   | 否       | 上下文目标字段                                                                                              |
| is_platform_index          | bool   | 否       | 是否创建平台级索引集，为 `true` 时 `platform_index_visibility` 与 `platform_index_filter` 必填               |
| platform_index_visibility  | dict   | 否       | 平台索引可见范围，支持 `{"type": "multi_biz", "bk_biz_ids": [2]}` 或 `{"type": "biz_attr", "bk_biz_labels": {"label": ["value"]}}` |
| platform_index_filter      | dict   | 否       | 平台索引过滤条件，`{"field": "字段名", "value_ref": "space_id"}`，`value_ref` 支持 `space_id`、`bk_biz_id`   |


### etl_params 参数

| 字段                             | 类型   | 必选 | 描述                                                                 |
| -------------------------------- | ------ | ---- | -------------------------------------------------------------------- |
| retain_original_text             | bool   | 否   | 是否保留原始日志到 `log` 字段，默认 `true`                            |
| separator                        | string | 否   | 分隔符，`etl_config=bk_log_delimiter` 时配置                          |
| separator_regexp                 | string | 否   | 正则表达式，`etl_config=bk_log_regexp` 时配置                         |
| retain_extra_json                | bool   | 否   | 是否保留未定义的 JSON 字段（存入 `__ext_json`），默认 `false`，仅 JSON 清洗生效 |
| enable_retain_content            | bool   | 否   | 是否保留清洗失败的日志，默认 `true`                                   |
| original_text_is_case_sensitive  | bool   | 否   | 原文是否大小写敏感，默认 `false`                                      |
| original_text_tokenize_on_chars  | string | 否   | 原文自定义分词符，默认空                                              |
| is_grok                          | bool   | 否   | 是否使用 grok 解析                                                    |

### fields 参数

| 字段         | 类型   | 必选     | 描述                                                                                       |
| ------------ | ------ | -------- | ------------------------------------------------------------------------------------------ |
| field_index  | int    | 否       | 字段顺序                                                                                   |
| field_name   | string | 条件必选 | 字段名称，`is_delete=false` 时必填                                                          |
| field_type   | string | 条件必选 | 字段类型，常用 `int`、`long`、`double`、`string`、`object`、`nested`，`is_delete=false` 时必填 |
| alias_name   | string | 否       | 字段别名，清洗为 JSON 时可用于字段重命名，不能与内置保留字段冲突                            |
| description  | string | 否       | 字段描述                                                                                   |
| is_delete    | bool   | 是       | 字段是否被删除，新增字段保留 `false` 即可                                                   |
| is_dimension | bool   | 否       | 是否为维度字段，默认 `true`；`is_analyzed=true` 时会被强制置为 `false`                       |
| is_time      | bool   | 否       | 是否为时间字段，默认 `false`，为 `true` 时需通过 `option` 配置时区与格式                     |
| is_analyzed  | bool   | 否       | 是否为分词字段，默认 `false`，仅支持 `field_type=string`                                    |
| is_built_in  | bool   | 否       | 是否为内置字段，默认 `false`，一般无需设置                                                   |
| is_case_sensitive | bool | 否     | 是否大小写敏感，默认 `false`                                                                 |
| option       | dict   | 否       | 字段配置，时间字段必填 `time_zone`、`time_format`；`int`/`long` 类型需使用 `epoch_millis`、`epoch_second`、`epoch_minute`、`epoch_micros` |

## 请求参数示例

自定义日志（分隔符清洗）：

```json
{
  "bk_biz_id": 2,
  "collector_config_name": "test_custom_config_name",
  "collector_config_name_en": "test_custom_config_name_en",
  "custom_type": "log",
  "category_id": "application_check",
  "etl_config": "bk_log_delimiter",
  "etl_params": {
    "retain_original_text": true,
    "separator": " "
  },
  "fields": [
    {
      "field_index": 1,
      "field_name": "custom_1",
      "field_type": "int",
      "alias_name": "",
      "description": "自定义字段说明1",
      "is_delete": false,
      "is_analyzed": false,
      "is_built_in": false,
      "is_dimension": false
    }
  ],
  "storage_cluster_id": 15,
  "retention": 3,
  "es_shards": 1,
  "storage_replies": 0,
  "allocation_min_days": 0,
  "description": ""
}
```

OTLP 日志（使用内置清洗，不自定义字段）：

```json
{
  "bk_biz_id": 2,
  "collector_config_name": "otlp_log_demo",
  "collector_config_name_en": "otlp_log_demo",
  "custom_type": "otlp_log",
  "storage_cluster_id": 15,
  "retention": 7,
  "allocation_min_days": 0
}
```

## 返回结果示例

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": {
    "collector_config_id": 1026,
    "index_set_id": 481367,
    "bk_data_id": 1578495,
    "created": true
  }
}
```

### 返回结果说明

| 字段                | 类型      | 描述                                                              |
| ------------------- | --------- | ----------------------------------------------------------------- |
| result              | bool      | 请求是否成功                                                      |
| code                | int       | 返回状态码，`0` 表示成功                                          |
| message             | string    | 描述信息                                                          |
| data                | dict      | 创建结果                                                          |
| data.collector_config_id | int  | 采集项 ID                                                         |
| data.index_set_id   | int       | 索引集 ID，创建时即生成并返回；未传 `storage_cluster_id` 时为未激活状态，尚不可用于检索 |
| data.bk_data_id     | int       | 数据管道 ID                                                       |
| data.created        | bool      | 是否本次新建，`ignore_exists=true` 复用已有采集项时为 `false`      |
| data.bk_data_token  | string    | 上报 token，仅 `custom_type=otlp_log` 创建时返回                   |

## 注意事项

- `collector_config_name_en` 业务内唯一，重复创建会返回错误；需要幂等时传 `ignore_exists=true`，命中后仅向本次传入的 `owners` 授予采集项与索引集权限，不授予业务访问权限；未传 `owners` 时不会新增任何授权，调用方需确认自己已有访问权限。
- 传入 `storage_cluster_id`、`fields` 为非空列表，且 `etl_params` 已传入（即使为 `{}` 也会被补成默认清洗参数）时才会使用传入的清洗配置；`etl_config` 未传时按 `bk_log_text` 处理。未传 `etl_params` 或 `fields` 为空列表时按 `custom_type` 的默认清洗创建。
- `custom_type=log` 默认按 `bk_log_text` 直接入库；`otlp_trace`、`otlp_log` 默认按 `bk_log_json` 并使用内置字段。
- 指定 ES 类型存储集群时，`retention` 与 `allocation_min_days` 必填，缺失会返回参数校验错误。
