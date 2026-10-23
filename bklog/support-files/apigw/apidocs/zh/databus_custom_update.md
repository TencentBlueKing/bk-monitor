## 功能描述

更新自定义上报采集项的基础信息，并在传入存储集群时同步更新清洗规则与存储配置。

后端路径：`POST /api/v1/databus/collectors/{collector_config_id}/custom_update/`，`Content-Type: application/json`。

调用用户需具备该采集项的「管理采集项」权限。

> 说明：不传 `storage_cluster_id` 时只更新采集项名称、分类、描述、展示状态、授权用户与归属索引集，不会改动清洗规则和存储配置。

## 请求参数

### 鉴权头

| 参数名称    | 参数类型 | 必须 | 参数说明     |
| ----------- | -------- | ---- | ------------ |
| bk_app_code   | string | 是   | 蓝鲸应用ID   |
| bk_app_secret | string | 是   | 蓝鲸应用秘钥 |
| bk_username | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 路径参数

| 字段                | 类型 | 必选 | 描述      |
| ------------------- | ---- | ---- | --------- |
| collector_config_id | int  | 是   | 采集项 ID |

### 参数列表

| 字段                       | 类型   | 必选     | 描述                                                                                                       |
| -------------------------- | ------ | -------- | ---------------------------------------------------------------------------------------------------------- |
| collector_config_name      | string | 是       | 采集项名称，不超过 50 个字符                                                                                |
| category_id                | string | 否       | 数据分类，默认 `application_check`                                                                          |
| description                | string | 否       | 描述信息，不超过 64 个字符，默认取 `collector_config_name`                                                  |
| is_display                 | bool   | 否       | 是否在采集列表展示，默认 `true`                                                                              |
| owners                     | list   | 否       | 授权用户列表，授予采集项、索引集及所属业务的访问权限，仅新增授权不回收历史权限                              |
| storage_cluster_id         | int    | 否       | 存储集群 ID，传值时更新清洗规则与存储配置；不传时跳过存储与清洗更新                                          |
| retention                  | int    | 条件必选 | 数据保留天数，指定 ES 类型存储集群时必填                                                                    |
| allocation_min_days        | int    | 条件必选 | n 天后的数据转入冷节点，仅集群开启冷热时生效，指定 ES 类型存储集群时必填                                     |
| es_shards                  | int    | 否       | 索引分片数，最小 1，默认取部署配置 `BKAPP_ES_SHARDS`（默认 3）                                              |
| storage_replies            | int    | 否       | 索引副本数，最小 0，默认取部署配置 `BKAPP_ES_REPLICAS`（默认 1）                                            |
| etl_config                 | string | 否       | 清洗类型，可选 `bk_log_text`、`bk_log_json`、`bk_log_delimiter`、`bk_log_regexp`；需与 `etl_params`、`fields` 同时传入才生效 |
| etl_params                 | dict   | 否       | 清洗参数，见下表；需与 `etl_config`、`fields` 同时传入才生效                                                |
| fields                     | list   | 否       | 清洗字段，见下表；需与 `etl_config`、`etl_params` 同时传入才生效                                            |
| parent_index_set_ids       | list   | 否       | 归属索引集 ID 列表，与 `parent_index_set_names` 二选一；传空列表表示清空，不传表示不变                       |
| parent_index_set_names     | list   | 否       | 归属索引集名称列表，与 `parent_index_set_ids` 二选一                                                        |
| sort_fields                | list   | 否       | 上下文排序字段                                                                                              |
| target_fields              | list   | 否       | 上下文目标字段                                                                                              |
| is_platform_index          | bool   | 否       | 是否设置为平台级索引集，为 `true` 时 `platform_index_visibility` 与 `platform_index_filter` 必填             |
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

```json
{
  "collector_config_name": "test_custom_config_name",
  "category_id": "application_check",
  "description": "更新后的描述",
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
  "owners": ["admin"]
}
```

## 返回结果示例

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": null
}
```

### 返回结果说明

| 字段    | 类型   | 描述                  |
| ------- | ------ | --------------------- |
| result  | bool   | 请求是否成功          |
| code    | int    | 返回状态码，`0` 表示成功 |
| message | string | 描述信息              |
| data    | null   | 更新成功时为空        |

## 注意事项

- `collector_config_name_en`、`custom_type` 不支持修改；该接口仅更新采集项名称、分类、描述、展示状态、授权用户、归属索引集，以及传入 `storage_cluster_id` 时的清洗与存储配置。
- 不传 `category_id` 时会被重置为 `application_check`；不传 `description` 时会被置为 `collector_config_name`；不传 `is_display` 时会被重置为 `true`。
- `etl_config`、`etl_params`、`fields` 需同时传入才会覆盖已有清洗配置；只传其中之一时会沿用该采集项已有的清洗配置。
- 指定 ES 类型存储集群时，`retention` 与 `allocation_min_days` 必填，缺失会返回参数校验错误。
- `owners` 仅新增授权，不回收历史授权。
