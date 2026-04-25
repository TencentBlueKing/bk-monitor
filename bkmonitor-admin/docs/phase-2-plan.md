# 第二期规划：列表页检索增强、视觉优化与新资源接入

本文档跟踪 `bkmonitor-admin` 第二期改造任务。核心目标：
1. 增强 DataSource / ResultTable 列表页的检索能力和视觉体验
2. 接入 ClusterInfo 和 BCSClusterInfo 资源展示
3. DataSource 详情页增加 Kafka 拉取最新数据操作

## 状态约定

| 状态 | 说明 |
| --- | --- |
| Todo | 尚未开始 |
| In Progress | 正在实现 |
| Blocked | 被依赖、环境或方案问题阻塞 |
| Review | 已完成实现，等待 review |
| Done | 已完成并验证 |

## 总体里程碑

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| M1 | 后端新增 ClusterInfo / BCSClusterInfo / kafka_sample RPC | Todo |
| M2 | 前端搜索/过滤 UI 重构 | Todo |
| M3 | 前端新资源页面（ClusterInfo / BCSClusterInfo） | Todo |
| M4 | DataSource 详情页 Kafka 取样 | Todo |
| M5 | 前端视觉与交互优化 | Todo |
| M6 | 联调、测试、文档收口 | Todo |

---

## 一、现状分析

### 1.1 后端 API 现状

**DataSource List** (`admin.datasource.list`) 完整支持的过滤参数：

| 参数 | 类型 | 匹配方式 | 前端 UI 是否已用 |
| --- | --- | --- | :---: |
| `bk_data_id` | integer | 精确 | 是 |
| `data_name` | string | `__contains` | 是 |
| `table_id` | string | 跨表精确 | 是 |
| `created_from` | string | 精确 | **否** |
| `source_label` | string | 精确 | **否** |
| `type_label` | string | 精确 | **否** |
| `is_enable` | boolean | 精确 | **否** |
| `is_custom_source` | boolean | 精确 | **否** |
| `is_platform_data_id` | boolean | 精确 | **否** |
| `space_uid` | string | 精确 | **否** |
| `ordering` | string | 排序白名单 | **否** |
| `page` / `page_size` | int | 分页 | 是 |

**ResultTable List** (`admin.result_table.list`) 完整支持的过滤参数：

| 参数 | 类型 | 匹配方式 | 前端 UI 是否已用 |
| --- | --- | --- | :---: |
| `table_id` | string | 精确/前缀/子串 (三重 OR) | 是 |
| `bk_data_id` | integer | 跨表精确 | 是 |
| `data_label` | string | 精确 | 是 |
| `table_name_zh` | string | `__contains` | **否** |
| `bk_biz_id` | integer | 精确 | **否** |
| `label` | string | 精确 | **否** |
| `schema_type` | string | 精确 | **否** |
| `default_storage` | string | 精确 | **否** |
| `is_enable` | boolean | 精确 | **否** |
| `is_deleted` | boolean | 精确 | **否** |
| `is_builtin` | boolean | 精确 | **否** |
| `ordering` | string | 排序白名单 | **否** |
| `page` / `page_size` | int | 分页 | 是 |

**当前缺失的后端 RPC**：

| 缺失能力 | 说明 |
| --- | --- |
| ClusterInfo 查询 | 无 `admin.cluster_info.list` / `admin.cluster_info.detail` |
| BCSClusterInfo 查询 | 无 `admin.bcs_cluster.list` / `admin.bcs_cluster.detail` |
| Kafka 取样 | 无 `admin.datasource.kafka_sample`，但已有 `KafkaTailResource` DRF Resource 可复用 |

### 1.2 前端 UI 现状

**DataSourceListPage**（3 个输入 → 需扩展到 10 个）:
- 搜索：`bk_data_id`、`data_name`、`table_id` + 搜索按钮
- 表格 10 列：`bk_data_id`、`data_name`、`bk_tenant_id`、type/source Badge、`created_from`、Kafka cluster、`is_enable`、`space_uid`、`result_table_count`、`last_modify_time`
- 分页：上一页/下一页 + "第 X 页 / 共 Y 条"

**ResultTableListPage**（3 个输入 → 需扩展到 11 个）:
- 搜索：`table_id`、`bk_data_id`、`data_label` + 搜索按钮
- 表格 11 列：`table_id`、`table_name_zh`、`bk_tenant_id`、`bk_biz_id`、`label`、`data_label`、`default_storage`、`is_enable`、`is_deleted`、`field_count`、`last_modify_time`
- 分页：同上

**关键问题**：
1. 搜索输入太少，仅 3 个文本框，各有 7-8 个后端过滤参数未暴露
2. 枚举字段（`source_label`、`type_label`、`schema_type` 等）只能用文本盲输
3. 布尔字段（`is_enable`、`is_deleted` 等）无控件
4. 分页器过于简陋（无 page size 选择、无跳页）
5. 表格无 hover 高亮、列宽不均衡、搜索区样式平庸

### 1.3 枚举值来源

以下枚举字段在后端有固化的常量定义，**无需新增后端接口**，直接以前端常量形式维护：

#### DataSource 枚举值

**`source_label`**（来源标签）— 来源 `bkmonitor/constants/data_source.py:DataSourceLabel`：

| db value | 显示名 |
| --- | --- |
| `bk_monitor` | 监控采集指标 |
| `bk_data` | 计算平台指标 |
| `custom` | 自定义指标 |
| `bk_log_search` | 日志平台指标 |
| `bk_fta` | 关联告警 |
| `bk_apm` | Trace明细指标 |
| `prometheus` | Prometheus |
| `dashboard` | DASHBOARD |

**`type_label`**（数据类型）— 来源 `bkmonitor/constants/data_source.py:DataTypeLabel`：

| db value | 显示名 |
| --- | --- |
| `time_series` | 时序数据 |
| `event` | 事件数据 |
| `log` | 日志数据 |
| `alert` | 关联告警 |
| `trace` | Trace数据 |

**`created_from`**（创建来源/数据链路）— 来源 `bkmonitor/metadata/models/constants.py:DataIdCreatedFromSystem`：

| db value | 显示名 |
| --- | --- |
| `bkgse` | V3 (GSE) |
| `bkdata` | V4 (计算平台) |

#### ResultTable 枚举值

**`schema_type`**（Schema 类型）— 来源 `result_table.py:SCHEMA_TYPE_CHOICES`：

| db value | 显示名 |
| --- | --- |
| `free` | 无固定字段 |
| `dynamic` | 动态字段 |
| `fixed` | 固定字段 |

**`default_storage`**（默认存储）— 来源 `storage.py:ClusterInfo.CLUSTER_TYPE_CHOICES`：

| db value | 显示名 |
| --- | --- |
| `influxdb` | influxDB |
| `kafka` | kafka |
| `redis` | redis |
| `elasticsearch` | elasticsearch |
| `argus` | argus |
| `victoria_metrics` | victoria_metrics |
| `doris` | doris |
| `bkdata` | bkdata |

**`label`**（结果表标签）— 来源 `metadata/migrations/*_init_label_info.py` 等迁移文件中的 `Label` 记录：

| db value | 显示名 | 层级 |
| --- | --- | --- |
| `applications` | 用户体验 | 一级 |
| `uptimecheck` | 服务拨测 | 二级(applications) |
| `application_check` | 业务应用 | 二级(applications) |
| `apm` | APM | 二级(applications) |
| `services` | 服务 | 一级 |
| `service_module` | 服务模块 | 二级(services) |
| `component` | 组件 | 二级(services) |
| `hosts` | 主机&云平台 | 一级 |
| `host_process` | 进程 | 二级(hosts) |
| `os` | 操作系统 | 二级(hosts) |
| `host_device` | 主机设备 | 二级(hosts) |
| `kubernetes` | kubernetes | 二级(hosts) |
| `data_center` | 数据中心 | 一级 |
| `hardware_device` | 硬件设备 | 二级(data_center) |
| `others` | 其他 | 一级 |
| `other_rt` | 其他 | 二级(others) |

> **注意**：`data_label` 无固化的枚举值，为自由文本字段。前端作为文本输入处理。可参考 `DATA_CATEGORY` 中常见模式（如 `bk_monitor_time_series`、`custom_event` 等）提供输入建议，但不强制约束。

---

## 二、后端新增 RPC

> **实现性能要求**：所有列表接口不做逐行关联查询（N+1），关联数据通过 `values_list` + `in` 批量聚合或放到详情接口处理。详情接口中关联数据用一次 `filter(__in=[])` 批量查询，不使用循环内单条 `get()`。

### P2-001 `admin.cluster_info.list` — 存储集群列表

状态：Todo  
建议负责人：Backend Agent

目标：

- 提供 `ClusterInfo` 模型的只读列表查询

入参：

```json
{
  "bk_tenant_id": "system",
  "cluster_type": "kafka",
  "cluster_name": "default",
  "is_default_cluster": true,
  "registered_system": "_default",
  "page": 1,
  "page_size": 20,
  "ordering": "cluster_id"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `bk_tenant_id` | string | 否 | 租户 ID |
| `cluster_type` | string | 否 | influxdb / kafka / redis / elasticsearch / argus / victoria_metrics / doris / bkdata |
| `cluster_name` | string | 否 | 集群名，`__contains` 子串匹配 |
| `is_default_cluster` | boolean | 否 | 是否默认集群 |
| `registered_system` | string | 否 | 注册系统，精确匹配 |
| `page` / `page_size` | int | 否 | 分页 |
| `ordering` | string | 否 | 排序字段 |

出参（列表项，敏感字段已脱敏）：

```json
{
  "cluster_id": 1,
  "cluster_name": "default-kafka",
  "display_name": "默认 Kafka 集群",
  "cluster_type": "kafka",
  "domain_name": "kafka.example.com",
  "port": 9092,
  "extranet_domain_name": "",
  "extranet_port": 0,
  "description": "",
  "is_default_cluster": true,
  "version": "3.5.1",
  "schema": "https",
  "is_ssl_verify": true,
  "ssl_verification_mode": "none",
  "is_auth": true,
  "sasl_mechanisms": "SCRAM-SHA-512",
  "security_protocol": "SASL_SSL",
  "registered_system": "_default",
  "registered_to_bkbase": false,
  "is_register_to_gse": true,
  "gse_stream_to_id": 100,
  "label": "",
  "default_settings": {},
  "has_username": true,
  "has_password": true,
  "has_ssl_certificate_authorities": false,
  "has_ssl_certificate": false,
  "has_ssl_certificate_key": false,
  "associated_datasources": 15,
  "associated_storages": 42,
  "creator": "admin",
  "create_time": "2026-04-24 10:00:00",
  "last_modify_user": "admin",
  "last_modify_time": "2026-04-24 10:00:00"
}
```

`associated_datasources` 和 `associated_storages` 通过一次 `COUNT` + `GROUP BY` 聚合查询批量获取，不逐行查询。

脱敏规则：
- `username`、`password` 替换为 `has_username: bool`、`has_password: bool`
- `ssl_certificate_authorities`、`ssl_certificate`、`ssl_certificate_key` 替换为 `has_ssl_*: bool`
- `custom_option` 不返回

实现要点：
- 查询 `ClusterInfo` 模型，支持按 `cluster_type`、`cluster_name`（`__contains`）、`is_default_cluster`、`registered_system` 过滤
- `ordering` 白名单：`cluster_id`、`cluster_name`、`cluster_type`、`is_default_cluster`、`registered_system`、`create_time`、`last_modify_time`
- 默认排序 `cluster_id`
- **性能**：需要关联统计时使用 `values_list` + `COUNT`/`GROUP BY` 或 `annotate` 批量聚合，禁止逐行查询

### P2-002 `admin.cluster_info.detail` — 存储集群详情

状态：Todo  
建议负责人：Backend Agent

目标：

- 提供 `ClusterInfo` 模型的单条详情查询，**包含关联的 `ClusterConfig` 及其 `component_config`**

#### ClusterInfo 与 ClusterConfig 的关系

`ClusterConfig`（位于 `metadata/models/data_link/data_link_configs.py`）通过软关联（`bk_tenant_id` + `cluster_type→kind` + `cluster_name→name`）与 `ClusterInfo` 连接。**同一 ClusterInfo 可能关联 1 个或 2 个 ClusterConfig**（取决于集群类型对应的 namespace 数量）：

| 集群类型 | kind | 对应 namespace | ClusterConfig 数 |
| --- | --- | --- | :---: |
| elasticsearch | ElasticSearch | `bklog` | 1 |
| victoria_metrics | VmStorage | `bkmonitor` | 1 |
| doris | Doris | `bklog` | 1 |
| kafka | KafkaChannel | `bklog` + `bkmonitor` | **2** |

`ClusterConfig.component_config` 是一个 `@property`，实时调用 bkbase API `get_data_link()` 获取组件的完整 Kubernetes-style 配置，返回结构包含 `kind`、`metadata`（namespace、name、labels、annotations）、`spec`（sources、sinks、transforms）和 `status`（phase、message）。

#### 入参

```json
{
  "bk_tenant_id": "system",
  "cluster_id": 1,
  "include": ["component_config"]
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `bk_tenant_id` | string | 否 | 租户 ID |
| `cluster_id` | integer | 是 | 集群 ID |
| `include` | string / list | 否 | 展开范围。`"component_config"` 默认包含；传空列表可跳过实时查询 |

注意：`include` 保留选项但不使用时 `component_config` 默认即返回。单个 namespace 调用失败以 `null` + warning 兼容，不阻塞整体响应。

#### 出参

```json
{
  "data": {
    "cluster_info": { /* 同列表项字段 */ },
    "cluster_configs": [
      {
        "namespace": "bkmonitor",
        "kind": "KafkaChannel",
        "name": "default-kafka",
        "origin_config": {
          "kind": "KafkaChannel",
          "metadata": {
            "namespace": "bkmonitor",
            "name": "default-kafka",
            "labels": { "bk_biz_id": "0" }
          },
          "spec": {
            "sources": [],
            "sinks": [],
            "transforms": []
          }
        },
        "component_config": {
          "kind": "KafkaChannel",
          "metadata": {
            "namespace": "bkmonitor",
            "name": "default-kafka",
            "labels": { "bk_biz_id": "2" },
            "annotations": { "kafka_cluster_name": "default-kafka" }
          },
          "spec": {
            "sources": [
              { "kind": "DataId", "namespace": "bkmonitor", "name": "demo" }
            ],
            "sinks": [
              { "kind": "VmStorageBinding", "namespace": "bkmonitor", "name": "vm_001" }
            ],
            "transforms": [
              { "kind": "PreDefinedLogic", "namespace": "bkmonitor", "name": "bk_standard_v2" }
            ]
          },
          "status": {
            "phase": "Ok",
            "message": "",
            "start_time": "2026-04-24 10:00:00",
            "update_time": "2026-04-24 12:00:00"
          }
        },
        "created_at": "2026-04-24 10:00:00",
        "updated_at": "2026-04-24 12:00:00"
      },
      {
        "namespace": "bklog",
        "kind": "KafkaChannel",
        "name": "default-kafka",
        "origin_config": { /* ... */ },
        "component_config": null,
        "created_at": "2026-04-24 10:00:00",
        "updated_at": "2026-04-24 12:00:00"
      }
    ],
    "related_result_tables": 42,
    "related_datasources": 15
  },
  "warnings": [
    {
      "code": "COMPONENT_CONFIG_UNAVAILABLE",
      "message": "namespace bklog 下组件配置获取失败，可能尚未注册到 bkbase"
    }
  ]
}
```

**字段说明**：
- `origin_config`：存储在 `ClusterConfig` 数据库中的静态配置（由 `compose_config()` 组装后保存），始终返回
- `component_config`：默认即从 bkbase API 拉取。如果某个 namespace 的 API 调用失败，对应项为 `null` 并附加 warning（不阻塞整体响应）
- `cluster_configs`：数组，长度为 1 或 2（取决于集群类型），每个元素对应一个 namespace 下的配置
- `created_at` / `updated_at` 来自 `ClusterConfig.create_time` / `update_time`

实现要点：
- 先查 `ClusterInfo`（1 次查询）获取 `bk_tenant_id`、`cluster_type`、`cluster_name`
- 通过 `CLUSTER_TYPE_TO_KIND_MAP` 和 `KIND_TO_NAMESPACES_MAP` 确定该集群对应的 (namespace, kind) 组合
- 一次 `filter` 查询所有 `ClusterConfig` 记录（1 次查询，1～2 条结果）
- 默认调用 `component_config` 实时查询 bkbase API（1～2 次外部调用），单个失败不影响其他
- 关联统计用 `COUNT` 聚合查询：`StorageResultTable` 子类按 `storage_cluster_id` 统计（1 次查询）、`DataSource` 按 `mq_cluster_id` 统计（1 次查询时仅 Kafka 类型需要）
- **总开销**：3 次 DB 查询 + 1～2 次 bkbase API 调用，无 N+1

### P2-003 `admin.bcs_cluster.list` — BCS 集群列表

状态：Todo  
建议负责人：Backend Agent

目标：

- 提供 `BCSClusterInfo` 模型的只读列表查询

入参：

```json
{
  "bk_tenant_id": "system",
  "bk_biz_id": 2,
  "cluster_id": "BCS-K8S-",
  "status": "running",
  "page": 1,
  "page_size": 20,
  "ordering": "cluster_id"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `bk_tenant_id` | string | 否 | 租户 ID |
| `bk_biz_id` | integer | 否 | 业务 ID，精确匹配 |
| `cluster_id` | string | 否 | BCS 集群 ID，`__contains` 子串匹配 |
| `status` | string | 否 | running / deleted / init_failed |
| `page` / `page_size` | int | 否 | 分页 |
| `ordering` | string | 否 | 排序字段 |

出参（列表项，密钥字段已脱敏）：

```json
{
  "cluster_id": "BCS-K8S-12345",
  "bcs_api_cluster_id": "BCS-API-K8S-12345",
  "bk_biz_id": 2,
  "bk_tenant_id": "system",
  "bk_cloud_id": 0,
  "project_id": "my-project",
  "status": "running",
  "domain_name": "https://k8s.example.com",
  "port": 443,
  "server_address_path": "/clusters/BCS-K8S-12345",
  "api_key_type": "authorization",
  "api_key_prefix": "Bearer",
  "is_skip_ssl_verify": true,
  "K8sMetricDataID": 50010,
  "CustomMetricDataID": 50011,
  "K8sEventDataID": 0,
  "CustomEventDataID": 0,
  "SystemLogDataID": 0,
  "CustomLogDataID": 0,
  "bk_env": "prod",
  "operator_ns": "bkmonitor-operator",
  "is_deleted_allow_view": false,
  "has_api_key": true,
  "has_cert": false,
  "creator": "admin",
  "create_time": "2026-04-24 10:00:00",
  "last_modify_user": "admin",
  "last_modify_time": "2026-04-24 10:00:00"
}
```

脱敏规则：
- `api_key_content` 替换为 `has_api_key: bool`
- `cert_content` 替换为 `has_cert: bool`

实现要点：
- 查询 `BCSClusterInfo` 模型，支持按 `bk_biz_id`（精确）、`cluster_id`（`__contains`）、`status`（精确）过滤
- `ordering` 白名单：`cluster_id`、`bcs_api_cluster_id`、`bk_biz_id`、`status`、`create_time`、`last_modify_time`
- 默认排序 `cluster_id`
- 默认排除状态为 `deleted` / `DELETED` / `init_failed` 的集群（除非 `status` 参数显式指定）
- **性能**：列表仅返回模型字段，不做关联查询；DataID 跳转逻辑由前端处理

### P2-004 `admin.bcs_cluster.detail` — BCS 集群详情

状态：Todo  
建议负责人：Backend Agent

目标：

- 提供 `BCSClusterInfo` 模型单条详情

入参：

```json
{
  "bk_tenant_id": "system",
  "cluster_id": "BCS-K8S-12345"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `bk_tenant_id` | string | 否 | 租户 ID |
| `cluster_id` | string | 是 | BCS 集群 ID |

出参：同列表项字段，增加关联 DataSource 摘要列表（通过 `K8sMetricDataID` 等关联，一次 `DataSource.objects.filter(bk_data_id__in=[...])` 批量查询）。

### P2-005 `admin.datasource.kafka_sample` — Kafka 取样

状态：Todo  
建议负责人：Backend Agent

目标：

- 从 DataSource 关联的 Kafka topic 拉取最新的 N 条原始数据
- 安全级别 `inspect`（读取实时数据，非纯元数据）

入参：

```json
{
  "bk_tenant_id": "system",
  "bk_data_id": 50010,
  "size": 10
}
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `bk_tenant_id` | string | 否 | 租户 ID | |
| `bk_data_id` | integer | 是 | | 数据源 ID |
| `size` | integer | 否 | 10 | 拉取条数，最大 50 |

出参：

```json
{
  "data": {
    "bk_data_id": 50010,
    "topic": "bkmonitor_50010",
    "items": [
      { "cpu": 0.85, "mem": 0.72, "host": "127.0.0.1" }
    ],
    "count": 10,
    "note": "返回最新的 10 条 record value（已解码为 JSON）"
  },
  "warnings": [],
  "meta": {
    "operation": "datasource.kafka_sample",
    "func_name": "admin.datasource.kafka_sample",
    "safety_level": "inspect",
    "effective_bk_tenant_id": "system"
  }
}
```

实现要点：
- 复用现有 `KafkaTailResource` 的核心消费逻辑（`_consume_with_confluent_kafka` / `_consume_with_kafka_python` / `_consume_with_gse_config` 三个消费路径）
- 内部从 Django 模型直接读取 `DataSource.mq_cluster`（含 `domain_name`、`port`、鉴权信息），不走 RPC 摘要输出
- 消费 `size` 条最新消息后立即断开，每条消息尝试 JSON 解码
- 超时保护：默认 10 秒，超过后返回已消费到的数据
- 安全级别标注为 `inspect`（区别于 `read` 级纯元数据查询）
- **性能**：单次 Kafka consumer 连接 + 消费，pull 到消息后立即关闭，无持续连接

### P2-006 后端测试

状态：Todo  
建议负责人：Backend Agent / QA Agent

目标：

- 为 P2-001 ~ P2-005 新增的 RPC 函数编写单元测试

---

## 三、前端搜索/过滤 UI 重构

### P2-101 `FilterToolbar` 通用过滤工具栏组件

状态：Todo  
建议负责人：Frontend Agent

目标：

- 创建可复用的过滤工具栏组件，替代当前页面内联的 `filter-grid` 表单

**支持的能力**：
- 文本输入型（`Input`）：`bk_data_id`、`data_name`、`table_id`、`table_name_zh`、`bk_biz_id`、`space_uid`
- 下拉选择型（`Select`）：`source_label`、`type_label`、`created_from`、`label`、`schema_type`、`default_storage`、`cluster_type`、`status`
- 布尔切换型（三元 Select: 全部/是/否）：`is_enable`、`is_custom_source`、`is_platform_data_id`、`is_deleted`、`is_builtin`
- 高级过滤折叠：默认显示 3-4 个常用过滤器，通过"高级筛选"展开更多
- 重置按钮：清空所有过滤并自动搜索
- 活动过滤标签行（`FilterTags`）：以 Badge/Chip 形式展示当前生效的过滤条件，可单独移除

**props 设计**：
```typescript
interface FilterField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'boolean';
  options?: Array<{ label: string; value: string }>;
  placeholder?: string;
  advanced?: boolean;
}

interface FilterToolbarProps {
  fields: FilterField[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  onSearch: () => void;
  onReset: () => void;
  loading?: boolean;
}
```

**`FilterTags` 子组件**：显示当前所有非空过滤条件的标签，每个 tag 可点击 × 清除。

### P2-102 枚举常量文件

状态：Todo  
建议负责人：Frontend Agent

目标：

- 将后端枚举值以前端常量形式维护，供 `FilterToolbar` 下拉选择使用

主要产出：
- `src/features/datasource/constants.ts`：导出 `SOURCE_LABEL_OPTIONS`、`TYPE_LABEL_OPTIONS`、`CREATED_FROM_OPTIONS`
- `src/features/result-table/constants.ts`：导出 `SCHEMA_TYPE_OPTIONS`、`DEFAULT_STORAGE_OPTIONS`、`LABEL_OPTIONS`
- `src/features/cluster-info/constants.ts`：导出 `CLUSTER_TYPE_OPTIONS`
- `src/features/bcs-cluster/constants.ts`：导出 `BCS_STATUS_OPTIONS`

所有选项格式：`Array<{ label: string; value: string }>`。

### P2-103 DataSource 列表页过滤重构

状态：Todo  
建议负责人：Frontend Agent

目标：

- 将 DataSourceListPage 搜索区替换为 `FilterToolbar`，暴露所有后端支持的过滤字段

过滤配置：

```typescript
const datasourceFilterFields: FilterField[] = [
  { key: 'bkDataId',     label: 'bk_data_id',   type: 'number',  placeholder: '精确匹配' },
  { key: 'dataName',     label: 'data_name',     type: 'text',    placeholder: '子串匹配' },
  { key: 'tableId',      label: '关联 table_id',  type: 'text' },
  { key: 'sourceLabel',  label: '来源标签',       type: 'select',  options: SOURCE_LABEL_OPTIONS,  advanced: true },
  { key: 'typeLabel',    label: '数据类型',       type: 'select',  options: TYPE_LABEL_OPTIONS,    advanced: true },
  { key: 'createdFrom',  label: '来源系统',       type: 'select',  options: CREATED_FROM_OPTIONS,  advanced: true },
  { key: 'spaceUid',     label: '空间 UID',       type: 'text',    advanced: true },
  { key: 'isEnable',          label: '启用',           type: 'boolean', advanced: true },
  { key: 'isCustomSource',    label: '自定义来源',      type: 'boolean', advanced: true },
  { key: 'isPlatformDataId',  label: '平台级 ID',      type: 'boolean', advanced: true },
];
```

### P2-104 ResultTable 列表页过滤重构

状态：Todo  
建议负责人：Frontend Agent

目标：

- 将 ResultTableListPage 搜索区替换为 `FilterToolbar`

过滤配置：

```typescript
const resultTableFilterFields: FilterField[] = [
  { key: 'tableId',       label: 'table_id',       type: 'text',   placeholder: '精确/前缀/子串' },
  { key: 'tableNameZh',   label: '中文名',          type: 'text',  placeholder: '子串匹配' },
  { key: 'bkDataId',      label: 'bk_data_id',     type: 'number', placeholder: '精确匹配' },
  { key: 'dataLabel',     label: 'data_label',      type: 'text',  placeholder: '精确匹配' },
  { key: 'bkBizId',       label: '业务 ID',         type: 'number', advanced: true },
  { key: 'label',         label: '标签',            type: 'select', options: LABEL_OPTIONS,           advanced: true },
  { key: 'schemaType',    label: 'Schema 类型',     type: 'select', options: SCHEMA_TYPE_OPTIONS,     advanced: true },
  { key: 'defaultStorage',label: '默认存储',        type: 'select', options: DEFAULT_STORAGE_OPTIONS, advanced: true },
  { key: 'isEnable',      label: '启用',            type: 'boolean', advanced: true },
  { key: 'isDeleted',     label: '已删除',          type: 'boolean', advanced: true },
  { key: 'isBuiltin',     label: '内置',            type: 'boolean', advanced: true },
];
```

> **`dataLabel` 说明**：该字段无固化的枚举值约束，二期作为自由文本输入处理。后期如需要可加 autocomplete 建议（参考 `DATA_CATEGORY` 常见模式如 `bk_monitor_time_series`）。

---

## 四、新资源 ClusterInfo 前端页面

### P2-201 ClusterInfo 列表页

状态：Todo  
建议负责人：Frontend Agent

目标：

- 实现 ClusterInfo 资源列表页

主要产出：

- `src/features/cluster-info/ClusterInfoListPage.tsx`
- `src/features/cluster-info/api.ts`：`listClusterInfos`、`getClusterInfoDetail`
- `src/features/cluster-info/queries.ts`：`useClusterInfoList`、`useClusterInfoDetail`
- `src/features/cluster-info/schemas.ts`：`clusterInfoListQuerySchema`、`clusterInfoSummarySchema`、`clusterInfoDetailResponseSchema`

过滤参数（通过 `FilterToolbar`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `cluster_name` | text | 子串匹配 |
| `cluster_type` | select | influxdb / kafka / redis / elasticsearch / argus / victoria_metrics / doris / bkdata |
| `is_default_cluster` | boolean | 是否默认集群 |
| `registered_system` | text | 精确匹配 |

表格列：

| 列 | 内容 |
| --- | --- |
| `cluster_id` | 数字，可点击跳转详情 |
| `cluster_name` | 集群名 |
| `display_name` | 显示名 |
| `cluster_type` | Badge，按类型染色（kafka=蓝、es=绿、influxdb=紫 ...） |
| `domain` | `domain_name:port` |
| `version` | 版本号 |
| `is_default` | Badge：是（绿色）/ 否（muted） |
| `registered_system` | 注册系统 |
| `associated_datasources` | 关联 DataSource 数（Kafka 类型时通过 `mq_cluster_id` 聚合统计） |
| `associated_storages` | 关联存储数（通过 `storage_cluster_id` 聚合统计） |
| `last_modify_time` | 格式化时间 |

### P2-202 ClusterInfo 详情页

状态：Todo  
建议负责人：Frontend Agent

目标：

- 实现 ClusterInfo 资源详情页，**重点展示关联 ClusterConfig 的组件配置（component_config）**

#### ClusterConfig 与 component_config 说明

每个 `ClusterInfo` 通过软关联对应 1 个或 2 个 `ClusterConfig`（取决于集群类型映射的 namespace 数量）。`ClusterConfig` 包含：

- **`origin_config`**（静态，已落库）：由 `compose_config()` 组装并保存到数据库的配置快照
- **`component_config`**（实时，从 bkbase API 拉取）：Kubernetes-style 的完整组件配置，包含 `spec.sources`（上游数据源）、`spec.sinks`（下游存储）、`spec.transforms`（数据转换逻辑）和 `status`（运行状态）

详情页默认展示 `origin_config`，并提供"加载组件配置"按钮按需拉取 `component_config`。

#### 主要产出

- `src/features/cluster-info/ClusterInfoDetailPage.tsx`
- `src/features/cluster-info/schemas.ts` 扩展：`clusterConfigSchema`、`componentConfigSchema`

#### 页面内容

**顶部 — 基本信息卡片**：
- `cluster_name`、`display_name`、`cluster_type`（Badge 染色）、`version`、`description`

**第二行 — 连接信息 + 安全配置（两列布局）**：
- 左列 连接信息：`domain_name:port`、`extranet_domain_name:port`、`schema`
- 右列 安全配置：SSL 验证模式、是否开启鉴权、SASL 机制、安全协议

**第三行 — 属性卡片**：
- 是否默认集群、注册系统、label、`registered_to_bkbase`、`is_register_to_gse`、`default_settings`（JsonBlock）

**核心区域 — ClusterConfig 列表（tab / accordion）**：

由于一个集群可能关联 1～2 个 namespace，按 `namespace` 分 tab 或 accordion 展示每个 `ClusterConfig`：

```
┌─────────────────────────────────────────────────────┐
│ ClusterConfig                                      │
│ ┌─ namespace: bkmonitor ──────────────────────────┐ │
│ │ kind: KafkaChannel  ·  name: default-kafka      │ │
│ │ 创建: 2026-04-24  ·  更新: 2026-04-24            │ │
│ │                                                  │ │
│ │ ┌─ origin_config (JsonBlock) ──────────────────┐ │ │
│ │ │ { "kind": "KafkaChannel",                    │ │ │
│ │ │   "metadata": { "namespace": "bkmonitor" },  │ │ │
│ │ │   "spec": { "sources": [], ... } }           │ │ │
│ │ └──────────────────────────────────────────────┘ │ │
│ │                                                  │ │
│ │ ┌─ component_config ───────────────────────────┐ │ │
│ │ │ ┌─ Sources (上游) ─────────────────--------┐ │ │ │
│ │ │ │ DataId: demo → 跳转详情                  │ │ │ │
│ │ │ ├─ Sinks (下游) ─────────────────----------┤ │ │ │
│ │ │ │ VmStorageBinding: vm_001                 │ │ │ │
│ │ │ ├─ Transforms (转换) ─────────────────------┤ │ │ │
│ │ │ │ PreDefinedLogic: bk_standard_v2          │ │ │ │
│ │ │ └─ Status ───────────────────────────────--┘ │ │ │
│ │ │   Phase: Ok · start: 2026-04-24             │ │ │
│ │ └──────────────────────────────────────────────┘ │ │
│ └──────────────────────────────────────────────────┘ │
│ ┌─ namespace: bklog (component_config 获取失败) ────┐ │
│ │ ... origin_config 仍正常展示                       │ │
│ └──────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

**`component_config` 展示**：
- 详情页加载时默认一并拉取（`include: ["component_config"]`）
- 按 namespace 分 accordion，每个展示：
  - **Sources**：列表，每项显示 `kind`、`namespace`、`name`，如为 DataId 可点击跳转 DataSource 详情
  - **Sinks**：列表，每项显示 `kind`、`namespace`、`name`
  - **Transforms**：列表
  - **Status**：phase (Ok/Error/Pending) + message + 起止时间
- 某个 namespace 的 `component_config` 为 `null` 时显示"获取失败"占位，不阻塞其他 namespace 的展示
- `origin_config` 以 JsonBlock 并列展示，供对比参考

**底部 — 关联统计 + 快捷导航**：
- 关联 ResultTable 数、关联 DataSource 数
- 点击可跳转对应列表页（URL 参数预填 `cluster_id` 过滤）

#### 数据结构设计

```typescript
// schemas.ts

const componentConfigSchema = z.object({
  kind: z.string(),
  metadata: z.object({
    namespace: z.string(),
    name: z.string(),
    labels: z.record(z.string(), z.string()).optional(),
    annotations: z.record(z.string(), z.string()).optional(),
  }),
  spec: z.object({
    sources: z.array(z.object({
      kind: z.string(),
      namespace: z.string(),
      name: z.string(),
    })).optional(),
    sinks: z.array(z.object({
      kind: z.string(),
      namespace: z.string(),
      name: z.string(),
    })).optional(),
    transforms: z.array(z.object({
      kind: z.string(),
      namespace: z.string(),
      name: z.string(),
    })).optional(),
  }).optional(),
  status: z.object({
    phase: z.string().optional(),
    message: z.string().optional(),
    start_time: z.string().optional(),
    update_time: z.string().optional(),
  }).optional(),
});

const clusterConfigSchema = z.object({
  namespace: z.string(),
  kind: z.string(),
  name: z.string(),
  origin_config: z.record(z.string(), z.any()),
  component_config: componentConfigSchema.nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
});

const clusterInfoDetailResponseSchema = z.object({
  cluster_info: clusterInfoSummarySchema,
  cluster_configs: z.array(clusterConfigSchema),
  related_result_tables: z.number(),
  related_datasources: z.number(),
});
```

### P2-203 添加左侧导航入口

状态：Todo  
建议负责人：Frontend Agent

目标：

- 在左侧导航栏"资源管理"下新增"存储集群"、"K8s 集群"两个菜单项

路由设计：
- `/clusters` → `ClusterInfoListPage`
- `/clusters/$clusterId` → `ClusterInfoDetailPage`
- `/bcs-clusters` → `BCSClusterInfoListPage`
- `/bcs-clusters/$clusterId` → `BCSClusterInfoDetailPage`

---

## 五、新资源 BCSClusterInfo 前端页面

### P2-301 BCSClusterInfo 列表页

状态：Todo  
建议负责人：Frontend Agent

目标：

- 实现 BCSClusterInfo 资源列表页

主要产出：

- `src/features/bcs-cluster/BCSClusterInfoListPage.tsx`
- `src/features/bcs-cluster/api.ts`：`listBcsClusters`、`getBcsClusterDetail`
- `src/features/bcs-cluster/queries.ts`：`useBcsClusterList`、`useBcsClusterDetail`
- `src/features/bcs-cluster/schemas.ts`：`bcsClusterListQuerySchema`、`bcsClusterSummarySchema`、`bcsClusterDetailResponseSchema`

过滤参数（通过 `FilterToolbar`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `cluster_id` | text | 子串匹配 |
| `bk_biz_id` | number | 精确匹配 |
| `status` | select | running / deleted / init_failed |

表格列：

| 列 | 内容 |
| --- | --- |
| `cluster_id` | 文本，可点击跳转详情 |
| `bcs_api_cluster_id` | API 集群 ID |
| `bk_biz_id` | 业务 ID |
| `project_id` | BCS 项目 ID |
| `status` | Badge：running=绿色、deleted=红色、init_failed=橙色 |
| `bk_env` | 环境标识 |
| `data_ids` | Badge 行：K8s指标/自定义指标/K8s事件/...，显示各 DataID 是否配置 |
| `operator_ns` | 命名空间 |
| `last_modify_time` | 格式化时间 |

### P2-302 BCSClusterInfo 详情页

状态：Todo  
建议负责人：Frontend Agent

目标：

- 实现 BCSClusterInfo 资源详情页

主要产出：

- `src/features/bcs-cluster/BCSClusterInfoDetailPage.tsx`

页面内容：
- **基本信息卡片**：`cluster_id`、`bcs_api_cluster_id`、`bk_biz_id`、`project_id`、`status`、`bk_env`
- **连接信息卡片**（脱敏后展示）：`domain_name:port`、`server_address_path`、`api_key_type` + 是否已配置 `api_key`、是否跳过 SSL 校验
- **Data IDs 卡片**：以网格展示 `K8sMetricDataID`、`CustomMetricDataID`、`K8sEventDataID`、`CustomEventDataID`、`SystemLogDataID`、`CustomLogDataID`，已配置的显示为可点击 Link（跳转到对应的 DataSource 详情），未配置的显示为 `–`
- **操作员命名空间**：`operator_ns`
- **data_ids 为空时的提示**：灰色文本说明尚未配置对应 DataSource

---

## 六、DataSource 详情页 Kafka 取样

### P2-401 Kafka 取样按钮与结果展示

状态：Todo  
建议负责人：Frontend Agent

目标：

- 在 DataSource 详情页的 Kafka 配置区域增加"拉取最新数据"操作按钮

主要改动：

**`DataSourceDetailPage.tsx`**：

在 KafkaTopic 配置区（`kafka_topic_config` 区域）新增一个操作用组件 `KafkaSampleButton`：

- 按钮文案："拉取最新数据"
- 点击后调用 `admin.datasource.kafka_sample` RPC，传递 `bk_tenant_id` + `bk_data_id` + `size`
- 加载态显示 spinner
- 成功后将返回的 `items` 以格式化 JSON 展示（复用 `JsonBlock` 组件）
- 错误时显示错误提示
- 结果以 `Card` 包裹展示在按钮下方，支持折叠/展开
- 显示取样元信息：topic 名、拉取条数、拉取时间

**`src/features/datasource/api.ts`**：新增 `sampleKafkaData(environment, params)`，operation: `admin.datasource.kafka_sample`

**`src/features/datasource/queries.ts`**：新增 `useKafkaSample(environment, bkTenantId, bkDataId, size)` — 注意这不是自动查询 hook，而是 `useMutation` 或手动触发

**安全级别提示**：safety_level 为 `inspect` 时在按钮附近显示灰色提示文字 "此操作读取实时 Kafka 数据" 或 guard icon。

**Mock 退路**：如果后端 kafka_sample 接口未就绪，前端 mock 数据包含 `note: "后端接口尚未实现，此处为 mock 数据"`。

---

## 七、前端视觉与交互优化

### P2-501 分页器增强

状态：Todo  
建议负责人：Frontend Agent

目标：

- 将简陋的"上一页/下一页"替换为功能完整的分页器

产物：

- 新建 `src/shared/components/Pagination.tsx`
- 支持：首页、上一页、页码按钮（ellipsis 省略号）、下一页、末页
- 显示 `page_size` 选择器：20 / 50 / 100
- 显示总数和当前范围
- 基于 shadcn/ui 风格

### P2-502 表格视觉优化

状态：Todo  
建议负责人：Frontend Agent

目标：

- 提升表格视觉质量和可读性

改动点：

- 表头行 `bg-muted/50` 浅色背景，与数据行区分
- 数据行 `hover:bg-muted/30` hover 高亮
- 表格容器 `max-h-[calc(100vh-280px)]` + sticky thead（粘性表头）
- 空值统一显示为 `–` (en dash)
- 链接列颜色统一使用 `text-primary`
- 列宽优化：ID/状态等窄列设最小宽度，描述类列自适应

### P2-503 搜索区样式重构

状态：Todo  
建议负责人：Frontend Agent

目标：

- 替代现有的 `.filter-grid`，使用更现代的分层过滤 UI

设计方案：

```text
┌─────────────────────────────────────────────────────┐
│  ┌────────────┐ ┌────────────┐ ┌────────────┐      │
│  │ bk_data_id │ │ data_name  │ │   table_id  │ 🔍  │
│  └────────────┘ └────────────┘ └────────────┘ 重置 │
│  [+ 高级筛选]                             统计栏   │
├─────────────────────────────────────────────────────┤
│  已选过滤: [source_label=bk_monitor ✕] [启用 ✕]    │
└─────────────────────────────────────────────────────┘
```

- 顶部工具栏：一行主过滤输入 + 搜索/重置按钮
- 高级筛选展开区：下拉选择和布尔开关（`Collapsible`，默认折叠）
- 活动过滤标签行（`FilterTags`）：Badge/Chip 形式，可单独移除

### P2-504 响应式适配

状态：Todo  
建议负责人：Frontend Agent

目标：

- 确保搜索区和表格在不同宽度下可正常使用

策略：

- 表格容器 `overflow-x: auto`，小屏可横向滚动
- 搜索区 grid 在小屏时单列布局
- 关键列（ID、名称）设置 `minWidth`

---

## 八、任务依赖与分工

### 依赖图

```text
后端:
P2-001 ──┐
P2-002 ──┤
P2-003 ──┼──> P2-005 (kafka_sample 可并行)
P2-004 ──┤
P2-006 ──┘  (测试可随各模块并行)

前端:
P2-101 (FilterToolbar) ──> P2-103, P2-104 (页面过滤重构)
                          ──> P2-201, P2-301 (新列表页也使用 FilterToolbar)

P2-102 (枚举常量) ──> P2-103, P2-104

P2-201 ──> P2-202 (ClusterInfo 列表 → 详情)
P2-301 ──> P2-302 (BCSClusterInfo 列表 → 详情)
P2-203 (导航) ──> P2-201, P2-301

P2-401 (Kafka 取样) —— 独立，依赖 P2-005

P2-501, P2-502, P2-503, P2-504 —— 视觉优化，独立于后端
```

### 推荐并行方式

**第一轮（可并行）**：
- Backend Agent：P2-001、P2-002、P2-003、P2-004（四个列表+详情 RPC）
- Backend Agent：P2-005（kafka_sample，可复用 KafkaTailResource 逻辑）
- Frontend Agent：P2-101 `FilterToolbar` + P2-102 枚举常量
- Frontend Agent：P2-501 分页器 + P2-502 表格视觉

**第二轮**：
- Frontend Agent：P2-103、P2-104（DataSource / ResultTable 过滤重构，依赖 FilterToolbar + 枚举常量）
- Frontend Agent：P2-201、P2-202、P2-301、P2-302 + P2-203（新资源页面 + 导航，依赖后端 RPC 就绪或 mock）

**第三轮**：
- Frontend Agent：P2-401（Kafka 取样按钮，依赖 P2-005 或 mock）
- Frontend Agent：P2-503、P2-504（视觉收尾）
- Backend Agent：P2-006（测试）
- Coordinator：文档收口

---

## 九、验收标准

### 搜索/过滤

- [ ] 两个列表页各暴露 ≥ 8 个过滤字段（含下拉选择和布尔开关）
- [ ] 下拉选择器选项值与后端枚举常量一致（无需调用后端 API 获取）
- [ ] 高级过滤默认折叠，展开后可查看所有后端参数
- [ ] 重置按钮清空所有过滤并恢复到第一页
- [ ] 活动过滤以 tag/chip 形式展示，可单独移除
- [ ] `data_label` 作为自由文本输入处理

### 新资源 (ClusterInfo)

- [ ] ClusterInfo 列表页可按 `cluster_type`、`cluster_name` 过滤
- [ ] ClusterInfo 详情页展示连接信息、安全配置、关联统计
- [ ] 详情页各信息区分卡片展示，结构清晰

### 新资源 (BCSClusterInfo)

- [ ] BCSClusterInfo 列表页可按 `bk_biz_id`、`status`、`cluster_id` 过滤
- [ ] BCSClusterInfo 详情页展示 Data IDs 网格，已配置的为可点击 Link
- [ ] 详情页连接信息已脱敏（api_key 不显示明文）

### Kafka 取样

- [ ] DataSource 详情页 Kafka 配置区有"拉取最新数据"按钮
- [ ] 点击后展示加载态、错误态、成功态
- [ ] 成功后以 JsonBlock 展示解码后的数据
- [ ] 安全级别 `inspect` 时有明确标识

### 视觉

- [ ] 表格表头有浅色背景，数据行有 hover 高亮
- [ ] 粘性表头在数据多时保持可见
- [ ] 空值统一 `–` 显示
- [ ] 搜索区样式统一美观，高级筛选有展开/折叠动画
- [ ] 分页器支持 page_size 选择、页码按钮

### 技术质量

- [ ] `pnpm typecheck` 通过
- [ ] `pnpm lint` 通过
- [ ] `pnpm test` 通过
- [ ] Playwright 冒烟测试覆盖新增页面
- [ ] 后端 RPC 单元测试通过

---

## 十、风险与阻塞

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 后端 env 依赖缺失 | 无法运行 Django 测试 | 用 `py_compile` 语法检查 + ruff 静态检查作为最小验证；记录阻塞原因 |
| labels 枚举值后续新增 | 前端下拉选项不完整 | 枚举常量文件集中维护，有新增时仅需更新 `constants.ts` |
| Kafka 取样超时 | 用户长时间等待 | 后端设置 10s 超时保护，返回已消费到的部分数据 |
| `admin.datasource.kafka_sample` 复用 `KafkaTailResource` | 两种框架（Resource vs RPC）生命周期不一致 | 将核心消费逻辑提取为共享工具函数，两边各自调用 |
| BCS Cluster `data_ids` 为空时的展示 | 详情页 Data IDs 网格大量 `–` | 以 compact 布局展示，明确给"未配置"提示 |
| 粘性表头在 overflow-x 容器中异常 | Tailwind sticky 失效 | 回退为非粘性，或在 `<thead>` 上使用 CSS `position: sticky` |

---

## 十一、已知不纳入二期的需求

| 需求 | 原因 |
| --- | --- |
| 表格列排序 | 用户明确指示暂缓 |
| 多值过滤（`source_label: ["a","b"]`） | 需后端支持数组入参 |
| 全文搜索（跨字段关键词） | 需后端支持或引入 ES |
| 时间范围过滤（`create_time__gte`/`__lte`） | 需后端支持范围查询 |
| 表格列显隐 | 前端状态复杂度较高 |
| 列表导出（CSV/Excel） | 需额外实现 |
| 实时刷新（轮询/WebSocket） | 需求待确认 |
| 聚合统计卡片（按 schema_type 分布图等） | 二期聚焦搜索和表格视图 |

---

## 十二、文档维护

二期实施过程中需更新以下文档：

- `docs/backend-admin-rpc.md`：新增 `admin.cluster_info.list` / `.detail`、`admin.bcs_cluster.list` / `.detail`、`admin.datasource.kafka_sample` 函数文档
- `docs/resources/`：如需要，新增 `cluster-info.md`、`bcs-cluster.md` 资源文档
- `docs/agent-friendly.md`：新增 RPC 函数的 AI Agent 调用示例
- 本 `docs/phase-2-plan.md`：持续更新各任务状态
