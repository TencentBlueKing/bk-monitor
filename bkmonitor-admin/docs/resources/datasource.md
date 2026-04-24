# DataSource 资源设计

## 资源定位

DataSource 是数据接入侧的核心资源，以 `bk_data_id` 为主键。管理后台需要围绕它展示数据源基础信息、配置选项、空间授权、结果表关系，以及 bkdata 类型数据链路配置。

## 涉及模型

主模型：

- DataSource

关联模型：

- DataSourceOption
- SpaceDataSource
- DataSourceResultTable
- DataIdConfig
- ResultTable

## 关键字段

列表建议展示：

| 字段 | 说明 |
| --- | --- |
| bk_data_id | 数据源 ID |
| data_name | 数据源名称 |
| data_description | 数据源描述，列表中截断 |
| bk_tenant_id | 租户 ID |
| type_label | 数据类型标签 |
| source_label | 数据源标签 |
| created_from | 数据源来源 |
| is_enable | 是否启用 |
| is_custom_source | 是否自定义数据源 |
| is_platform_data_id | 是否平台级 ID |
| space_uid | 所属空间 UID |
| kafka_cluster | Kafka 集群摘要；列表展示集群名称，tooltip 展示集群 ID |
| mq_cluster_id | Kafka 集群 ID，作为兼容字段保留 |
| transfer_cluster_id | transfer 集群 ID |
| create_time | 创建时间 |
| last_modify_time | 更新时间 |

详情建议展示：

- 基础信息：列表字段 + token 是否存在、source_system、custom_label、space_type_id。
- MQ 信息：mq_cluster_id、mq_config_id、Kafka 集群 ID/名称、KafkaTopic 配置、etl_config、transfer_cluster_id。
- 标签与归属：type_label、source_label、created_from、space_uid、is_tenant_specific_global、is_platform_data_id。
- 操作信息：creator、last_modify_user、create_time、last_modify_time。

## 检索与过滤

一期支持：

| 过滤项 | 类型 | 匹配方式 | 备注 |
| --- | --- | --- | --- |
| bk_data_id | number | 精确 | 最高优先级 |
| data_name | string | 包含 / 前缀 | 建议后端控制模糊范围 |
| created_from | enum | 精确 | 如 bkgse / bkdata 等 |
| type_label | enum | 精确 | 时序 / 事件 / 日志等 |
| source_label | enum | 精确 | bk_monitor / bk_data / custom 等 |
| is_enable | boolean | 精确 | 默认不过滤 |
| is_custom_source | boolean | 精确 | 默认不过滤 |
| is_platform_data_id | boolean | 精确 | 默认不过滤 |
| space_uid | string | 精确 | 可从空间维度定位 |
| table_id | string | 关联过滤 | 通过 DataSourceResultTable 反查 |
| bk_tenant_id | string | 精确 | 必选或由环境上下文注入 |

## 列表行为

- 默认按 `bk_data_id desc` 或 `last_modify_time desc` 排序。
- 列表只返回轻量字段和关联计数，不展开 options 和所有 RT。
- `data_description`、`etl_config` 这类长文本不在列表完整展示。
- `token` 默认不展示明文，只展示是否存在。

## 详情页面

建议详情分 tab：

### 概览

展示 DataSource 基础字段和核心状态。

概览中需要直接展示 Kafka 集群 ID、Kafka 集群名称和 KafkaTopic 配置 ID，便于快速确认 DataSource 使用的消息队列链路。

### KafkaTopic 配置

展示 `KafkaTopicInfo`：

- id
- bk_data_id
- topic
- partition
- batch_size
- flush_interval
- consume_rate

### Options

展示 DataSourceOption：

- name
- value
- value_type
- creator
- create_time

值较长时使用 JSON 折叠展示。

### 空间关系

展示 SpaceDataSource：

- space_type_id
- space_id
- bk_tenant_id
- bk_data_id
- from_authorization

支持按 `space_uid` 复制和跳转。

### 结果表关系

展示 DataSourceResultTable 与 ResultTable 摘要：

- bk_data_id
- table_id
- ResultTable.table_name_zh
- ResultTable.bk_biz_id
- ResultTable.data_label
- ResultTable.default_storage
- ResultTable.is_enable
- ResultTable.is_deleted

`table_id` 可跳转到 ResultTable 详情。

### DataIdConfig

仅对 bkdata 类型或 V4 datalink 相关数据源展示：

- bk_tenant_id
- namespace
- name
- bk_data_id
- kind
- bk_biz_id 相关信息

一期只读展示，不提供重新下发或删除配置。

## 与 ResultTable 的关系

DataSource 到 ResultTable 的主路径是：

```text
DataSource.bk_data_id
  -> DataSourceResultTable.bk_data_id
  -> DataSourceResultTable.table_id
  -> ResultTable.table_id
```

在多租户环境下必须同时带上 `bk_tenant_id`。

## 后端接口需求

这些接口后续都应沉淀为 Agent-facing operation，并提供 input/output schema、examples 和 `safety_level=read`。

所有请求都必须携带 `environment_id`，或由已绑定环境的会话上下文注入。

### admin.datasource.list

Agent operation：`datasource.list`

Safety level：`read`

请求示例：

```json
{
  "environment_id": "prod-main",
  "bk_tenant_id": "system",
  "bk_data_id": 50010,
  "data_name": "demo",
  "created_from": "bkdata",
  "page": 1,
  "page_size": 20
}
```

响应建议：

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

每个 item 建议带：

- datasource 基础字段
- result_table_count
- space_count
- option_count
- has_data_id_config

### admin.datasource.detail

Agent operation：`datasource.detail`

Safety level：`read`

请求示例：

```json
{
  "environment_id": "prod-main",
  "bk_tenant_id": "system",
  "bk_data_id": 50010
}
```

响应建议：

```json
{
  "datasource": {},
  "options": [],
  "space_datasources": [],
  "data_source_result_tables": [],
  "result_tables": [],
  "data_id_config": null
}
```

## 一期验收标准

- 能按 `bk_data_id` 快速定位唯一 DataSource。
- 能按 `data_name`、`created_from`、`source_label`、`type_label` 做过滤。
- 能在详情中看到 DataSource 的 options、空间关系、结果表关系。
- 能从 DataSource 详情跳转到关联 ResultTable。
- bkdata 类型数据源能看到 DataIdConfig 是否存在及其核心字段。
