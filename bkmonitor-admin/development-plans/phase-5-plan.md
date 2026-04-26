# 第 5 期开发计划：DataLink 集中查询入口

## 概述

第 5 期实现 metadata/models/DataLink 相关资源的集中查询与展示。以 **DataLink（数据链路）** 为统一导航入口，通过 **Kind 作为 Tab** 切换不同组件类型的资源列表。DataLink 本身作为一个特殊的 Kind，其详情页会展示该链路关联的全部组件配置信息。

核心设计原则：

- **Kind 即 Tab**：选择 Tab 后展示对应组件类型的资源列表
- **DataLink 为特殊 Kind**：作为顶层视图，详情展示其关联的全部组件配置
- **默认取 DB，详情才加载 component_config**：列表仅展示 DB 字段；进入详情后同时查询 DB 和 component_config（通过 BKBase API）

## 1. 资源模型调研

### 1.1 DataLinkKind 枚举（12 种组件类型）

| Kind                 | Enum 值                  | 数据库模型                  | 模型类型                          |
| -------------------- | ------------------------ | --------------------------- | --------------------------------- |
| **DataLink**         | _(特殊，不在枚举中)_     | `DataLink`                  | 链路编排器                        |
| DataId               | `"DataId"`               | `DataIdConfig`              | `DataLinkResourceConfigBase` 子类 |
| ResultTable          | `"ResultTable"`          | `ResultTableConfig`         | `DataLinkResourceConfigBase` 子类 |
| VmStorageBinding     | `"VmStorageBinding"`     | `VMStorageBindingConfig`    | `DataLinkResourceConfigBase` 子类 |
| ElasticSearchBinding | `"ElasticSearchBinding"` | `ESStorageBindingConfig`    | `DataLinkResourceConfigBase` 子类 |
| DorisBinding         | `"DorisBinding"`         | `DorisStorageBindingConfig` | `DataLinkResourceConfigBase` 子类 |
| Databus              | `"Databus"`              | `DataBusConfig`             | `DataLinkResourceConfigBase` 子类 |
| ConditionalSink      | `"ConditionalSink"`      | `ConditionalSinkConfig`     | `DataLinkResourceConfigBase` 子类 |
| KafkaChannel         | `"KafkaChannel"`         | `ClusterConfig`             | 独立模型（非 DRLRB）              |
| VmStorage            | `"VmStorage"`            | `ClusterConfig`             | 独立模型（非 DRLRB）              |
| ElasticSearch        | `"ElasticSearch"`        | `ClusterConfig`             | 独立模型（非 DRLRB）              |
| Doris                | `"Doris"`                | `ClusterConfig`             | 独立模型（非 DRLRB）              |
| Sink                 | `"Sink"`                 | _(暂无独立模型)_            | 枚举值但无对应表                  |

### 1.2 DataLink（链路编排器）

**表：** `metadata.models.data_link.data_link.DataLink`

| 字段                 | 类型                 | 说明                      |
| -------------------- | -------------------- | ------------------------- |
| `data_link_name`     | `CharField(255, PK)` | 链路名称（主键）          |
| `bk_tenant_id`       | `CharField(256)`     | 租户 ID                   |
| `namespace`          | `CharField(255)`     | 命名空间                  |
| `data_link_strategy` | `CharField(255)`     | 链路组装策略（11 种策略） |
| `bk_data_id`         | `IntegerField`       | 关联数据源 ID             |
| `table_ids`          | `JSONField`          | 关联结果表 ID 列表        |
| `create_time`        | `DateTimeField`      | 创建时间                  |
| `last_modify_time`   | `DateTimeField`      | 修改时间                  |

**关键方法：**

- `compose_configs()` — 按策略生成组件配置
- `apply_data_link()` — 完整生命周期：创建 RT → compose → apply
- `delete_data_link()` — 反向清理

### 1.3 DataLinkResourceConfigBase（组件配置基类）

所有组件配置（DataIdConfig 到 ConditionalSinkConfig）继承自此类。

| 通用字段           | 类型                                         |
| ------------------ | -------------------------------------------- |
| `kind`             | `CharField(64)` — 固定为 DataLinkKind 枚举值 |
| `name`             | `CharField(64)` — 组件实例名称               |
| `namespace`        | `CharField(64)` — 命名空间                   |
| `create_time`      | `DateTimeField`                              |
| `last_modify_time` | `DateTimeField`                              |
| `status`           | `CharField(64)` — 资源状态                   |
| `data_link_name`   | `CharField(64)` — 所属链路名称               |
| `bk_biz_id`        | `BigIntegerField`                            |
| `bk_tenant_id`     | `CharField(256)`                             |

**关键属性：**

- `component_config` — 通过 `service.get_data_link_component_config()` 调用 BKBase API 获取运行时配置
- `component_status` — 调用 BKBase API 获取组件状态

### 1.4 各组件类型的特有字段

| Kind                 | 特有字段                                                                      |
| -------------------- | ----------------------------------------------------------------------------- |
| DataId               | `name`, `bk_data_id`                                                          |
| ResultTable          | `name`, `table_id`, `data_type`, `bkbase_table_id`                            |
| VmStorageBinding     | `name`, `vm_cluster_name`, `bkbase_result_table_name`, `table_id`             |
| ElasticSearchBinding | `name`, `es_cluster_name`, `table_id`, `bkbase_result_table_name`, `timezone` |
| DorisBinding         | `name`, `table_id`, `bkbase_result_table_name`, `doris_cluster_name`          |
| Databus              | `name`, `data_id_name`, `bk_data_id`, `sink_names` (JSON)                     |
| ConditionalSink      | `name`                                                                        |

> **DataIdConfig 特殊性：** 虽然 DataIdConfig 继承自 `DataLinkResourceConfigBase`，它实际**不直接隶属于 DataLink**。DataIdConfig 通过 `bk_data_id` 与 DataSource 关联，而非通过 `data_link_name` 绑定到某个 DataLink。因此 DataIdConfig 的 `data_link_name` 始终为空，DataLink 详情页的关联子组件列表中**不包含 DataId**。
> | ClusterConfig 系列 | `name` (CharField 255), `origin_config` (JSON), `create_time`, `update_time` |

### 1.5 ClusterConfig（非 DRLRB 模型）

独立的集群配置表。通过 `kind` 字段区分 KafkaChannel/VmStorage/ElasticSearch/Doris。

| 字段            | 类型               |
| --------------- | ------------------ |
| `bk_tenant_id`  | CharField(255)     |
| `namespace`     | CharField(255)     |
| `name`          | CharField(255)     |
| `kind`          | CharField(255)     |
| `origin_config` | SymmetricJsonField |
| `create_time`   | DateTimeField      |
| `update_time`   | DateTimeField      |

同样有 `component_config` 属性，调用 BKBase API。

---

## 2. 后端 RPC 设计

### 2.1 操作列表

基于现有 RPC 模式（`kernel_api/rpc/functions/admin/`），新增 `datalink.py`，RPC 按三组独立设计：

**组件（DRLRB 子类）—— `admin.datalink.component_*`：**

| 操作名                            | 函数名                 | 说明                                             |
| --------------------------------- | ---------------------- | ------------------------------------------------ |
| `admin.datalink.component_list`   | `list_components`      | 按 Kind 查询 DRLRB 组件列表（含分页）            |
| `admin.datalink.component_detail` | `get_component_detail` | 查询单个 DRLRB 组件详情（可选 component_config） |
| `admin.datalink.component_config` | `get_component_config` | 懒加载某个 DRLRB 组件的 component_config         |

**集群配置（ClusterConfig）—— `admin.datalink.cluster_config_*`：**

| 操作名                                           | 函数名                                | 说明                                                 |
| ------------------------------------------------ | ------------------------------------- | ---------------------------------------------------- |
| `admin.datalink.cluster_config_list`             | `list_cluster_configs`                | 查询 ClusterConfig 列表（`kind` 作为过滤条件）       |
| `admin.datalink.cluster_config_detail`           | `get_cluster_config_detail`           | 查询单个 ClusterConfig 详情（可选 component_config） |
| `admin.datalink.cluster_config_component_config` | `get_cluster_config_component_config` | 懒加载 ClusterConfig 的 component_config             |

**DataLink 链路—— `admin.datalink.datalink_*`：**

| 操作名                                     | 函数名                          | 说明                                            |
| ------------------------------------------ | ------------------------------- | ----------------------------------------------- |
| `admin.datalink.datalink_list`             | `list_datalinks`                | 查询 DataLink 链路列表（含分页）                |
| `admin.datalink.datalink_detail`           | `get_datalink_detail`           | 查询 DataLink 链路详情 + 关联的全部子组件       |
| `admin.datalink.datalink_component_config` | `get_datalink_component_config` | 链路详情页中懒加载某个子组件的 component_config |

> **设计要点：** 三组 RPC 对应三种数据库模型（DRLRB 子类 / ClusterConfig / DataLink），字段结构与接口语义各不相同。`datalink_component_config` 可复用 `component_config` 内部实现。

---

### 2.2 `admin.datalink.component_list`

**参数：**

```json
{
  "bk_tenant_id": "可选，租户 ID",
  "kind": "必填，组件类型（DataId | ResultTable | VmStorageBinding | ...）",
  "namespace": "可选，命名空间过滤",
  "search": "可选，按名称模糊搜索",
  // kind-specific 过滤（见下方各 Kind 过滤条件表）
  "bk_data_id": "可选，按数据源 ID 过滤（DataId / Databus）",
  "data_type": "可选，按数据类型过滤（ResultTable）",
  "vm_cluster_name": "可选，按 VM 集群名过滤（VmStorageBinding）",
  "es_cluster_name": "可选，按 ES 集群名过滤（ElasticSearchBinding）",
  "doris_cluster_name": "可选，按 Doris 集群名过滤（DorisBinding）",
  "status": "可选，按状态过滤（DRLRB 子类）",
  "has_data_link": "可选，是否关联 DataLink（DRLRB 子类，不含 DataId 与存储组件）",
  "page": 1,
  "page_size": 20
}
```

**后端逻辑：**

1. 根据 `kind` 选择查询模型：
   - `kind` 为 DRLRB 子类 → `COMPONENT_CLASS_MAP[kind]`
   - `kind` 为 ClusterConfig 类型 → `models.ClusterConfig.objects.filter(kind=kind)`
2. 按通用过滤条件：`namespace`、`search`
3. 按 Kind 特有过滤条件（见下表）
4. 按高级过滤条件（见 2.2.1）
5. 分页

#### 2.2.1 过滤条件定义

**基础过滤（所有 Kind 通用）：**

| 参数        | 类型     | 说明                                |
| ----------- | -------- | ----------------------------------- |
| `namespace` | `string` | 命名空间精确匹配                    |
| `search`    | `string` | 按 `name`/`data_link_name` 模糊搜索 |

**Kind 特有基础过滤：**

| Kind                 | 过滤参数             | 后端字段             | 前端控件                                                   |
| -------------------- | -------------------- | -------------------- | ---------------------------------------------------------- |
| DataLink             | `data_link_strategy` | `data_link_strategy` | select（策略枚举）                                         |
| DataId               | `bk_data_id`         | `bk_data_id`         | number input                                               |
| DataId               | `status`             | `status`             | select（状态枚举）                                         |
| ResultTable          | `data_type`          | `data_type`          | select（metric/log/event 等）                              |
| ResultTable          | `status`             | `status`             | select                                                     |
| VmStorageBinding     | `vm_cluster_name`    | `vm_cluster_name`    | text input                                                 |
| VmStorageBinding     | `status`             | `status`             | select                                                     |
| ElasticSearchBinding | `es_cluster_name`    | `es_cluster_name`    | text input                                                 |
| ElasticSearchBinding | `status`             | `status`             | select                                                     |
| DorisBinding         | `doris_cluster_name` | `doris_cluster_name` | text input                                                 |
| DorisBinding         | `status`             | `status`             | select                                                     |
| Databus              | `bk_data_id`         | `bk_data_id`         | number input                                               |
| Databus              | `status`             | `status`             | select                                                     |
| ConditionalSink      | `status`             | `status`             | select                                                     |
| ClusterConfig        | `kind`               | `kind`               | select（KafkaChannel / VmStorage / ElasticSearch / Doris） |

> **重要：`kind` 字段的差异** — 在 DRLRB 子类（DataId / ResultTable / VmStorageBinding / ...）中，`kind` 是**类属性常量**（如 `kind = DataLinkKind.DATAID.value`），**不是**数据库列，后端通过调用方传入的 `kind` 参数选择 `COMPONENT_CLASS_MAP[kind]` 对应的模型类进行查询。而 `ClusterConfig` 中的 `kind` 是真正的 `CharField` 数据库列，可以作为过滤条件。

**高级过滤（仅部分 Kind 支持，放在 `FilterToolbar` 的"高级筛选"区域）：**

| Kind                 | 过滤参数        | 后端实现                                                 | 说明                       |
| -------------------- | --------------- | -------------------------------------------------------- | -------------------------- |
| ResultTable          | `has_data_link` | `Q(data_link_name="") \| Q(data_link_name__isnull=True)` | 筛选未关联 DataLink 的组件 |
| VmStorageBinding     | `has_data_link` | 同上                                                     | 同上                       |
| ElasticSearchBinding | `has_data_link` | 同上                                                     | 同上                       |
| DorisBinding         | `has_data_link` | 同上                                                     | 同上                       |
| Databus              | `has_data_link` | 同上                                                     | 同上                       |
| ConditionalSink      | `has_data_link` | 同上                                                     | 同上                       |

> **排除规则：** `DataId` 和 ClusterConfig、`DataLink` 链路自身不支持 `has_data_link` 过滤。`DataId` 不直接绑定 DataLink（由 DataSource 间接关联）。ClusterConfig 无 `data_link_name` 字段。`DataLink` 链路自身自然不需此过滤。

前端 `has_data_link` 实现为 boolean 选择器（三态）：

- `undefined` → 不筛选（所有记录）
- `true` → `data_link_name` 为空（未关联）
- `false` → `data_link_name` 非空（已关联）

**各 Kind 的列表 item 字段：**

| Kind                 | item 字段                                                                                                                                                                       |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| DataId               | `name`, `bk_data_id`, `namespace`, `status`, `data_link_name`, `bk_tenant_id`, `bk_biz_id`, `created_at`, `updated_at`                                                          |
| ResultTable          | `name`, `table_id`, `data_type`, `bkbase_table_id`, `namespace`, `status`, `data_link_name`, `bk_tenant_id`, `bk_biz_id`, `created_at`, `updated_at`                            |
| VmStorageBinding     | `name`, `vm_cluster_name`, `bkbase_result_table_name`, `table_id`, `namespace`, `status`, `data_link_name`, `bk_tenant_id`, `bk_biz_id`, `created_at`, `updated_at`             |
| ElasticSearchBinding | `name`, `es_cluster_name`, `table_id`, `bkbase_result_table_name`, `timezone`, `namespace`, `status`, `data_link_name`, `bk_tenant_id`, `bk_biz_id`, `created_at`, `updated_at` |
| DorisBinding         | `name`, `table_id`, `bkbase_result_table_name`, `doris_cluster_name`, `namespace`, `status`, `data_link_name`, `bk_tenant_id`, `bk_biz_id`, `created_at`, `updated_at`          |
| Databus              | `name`, `data_id_name`, `bk_data_id`, `sink_names`, `namespace`, `status`, `data_link_name`, `bk_tenant_id`, `bk_biz_id`, `created_at`, `updated_at`                            |
| ConditionalSink      | `name`, `namespace`, `status`, `data_link_name`, `bk_tenant_id`, `bk_biz_id`, `created_at`, `updated_at`                                                                        |
| ClusterConfig        | `name`, `kind`, `namespace`, `bk_tenant_id`, `origin_config`, `created_at`, `updated_at`                                                                                        |

> **注：** DataLink 链路列表使用独立的 `admin.datalink.datalink_list` 操作。

---

### 2.3 `admin.datalink.component_detail`

**参数：**

```json
{
  "bk_tenant_id": "可选，租户 ID",
  "kind": "必填，组件类型",
  "namespace": "必填，命名空间",
  "name": "必填，组件名称",
  "include": ["可选，component_config"]
}
```

**后端逻辑（DRLRB 子类）：**

1. 查询对应模型的唯一记录：`Model.objects.get(bk_tenant_id, namespace, name)`
2. 返回完整字段
3. 如果 `include` 包含 `"component_config"`：调用 `.component_config` 并返回

**后端逻辑（ClusterConfig 类型）：**

1. 查询 `ClusterConfig.objects.get(bk_tenant_id, namespace, kind, name)`
2. 返回完整字段（含 `origin_config`）
3. 如果 `include` 包含 `"component_config"`：调用 `.component_config` 并返回

**响应：**

```json
{
  "data": {
    "kind": "DataId",
    "name": "...",
    "namespace": "...",
    "status": "Ok",
    "data_link_name": "...",
    "bk_tenant_id": "...",
    "bk_biz_id": 100,
    "created_at": "...",
    "updated_at": "...",
    "bk_data_id": 1001,
    "component_config": { ... },
    "warnings": []
  },
  "trace_id": "...",
  "warnings": []
}
```

---

### 2.4 `admin.datalink.component_config`（懒加载专用）

**参数：**

```json
{
  "bk_tenant_id": "可选，租户 ID",
  "kind": "必填，组件类型",
  "namespace": "必填，命名空间",
  "name": "必填，组件名称"
}
```

**响应：**

```json
{
  "data": {
    "kind": "DataId",
    "namespace": "bkmonitor",
    "name": "test-data-source",
    "component_config": { ... }
  },
  "trace_id": "...",
  "warnings": []
}
```

**后端逻辑：**

1. 查找对应模型记录（by tenant + kind + namespace + name）
2. 调用 `component_config` 属性获取 BKBase 运行时配置
3. 对包含密码/密钥的 Config 调用 `_mask_sensitive_fields()`
4. 返回

---

### 2.5 `admin.datalink.cluster_config_list`

**参数：**

```json
{
  "bk_tenant_id": "可选，租户 ID",
  "kind": "可选，集群类型（KafkaChannel | VmStorage | ElasticSearch | Doris）",
  "namespace": "可选，命名空间过滤",
  "search": "可选，按 name 模糊搜索",
  "page": 1,
  "page_size": 20
}
```

**后端逻辑：**

1. 查询 `models.ClusterConfig.objects.filter(bk_tenant_id=bk_tenant_id)`
2. 按 `kind` 过滤（可选 — 不传则返回全部类型）
3. 按 `namespace` 过滤（可选）
4. 按 `search` 模糊匹配 `name`（可选）
5. 分页

**响应 item 字段：**

`name`, `kind`, `namespace`, `bk_tenant_id`, `origin_config`, `created_at`, `updated_at`

> **与 DRLRB 组件的区别：** ClusterConfig 的 `kind` 是真正的数据库列，因此可作为过滤条件。而 DRLRB 子类的 `kind` 是类属性常量，通过 `COMPONENT_CLASS_MAP` 映射到具体模型类。

---

### 2.6 `admin.datalink.cluster_config_detail`

**参数：**

```json
{
  "bk_tenant_id": "可选，租户 ID",
  "kind": "必填，集群类型",
  "namespace": "必填，命名空间",
  "name": "必填，集群配置名称",
  "include": ["可选，component_config"]
}
```

**后端逻辑：**

1. 查询 `ClusterConfig.objects.get(bk_tenant_id, kind, namespace, name)`
2. 返回完整字段（含 `origin_config`）
3. 如果 `include` 包含 `"component_config"`：调用 `.component_config` 脱敏后返回

---

### 2.7 `admin.datalink.cluster_config_component_config`（懒加载专用）

**参数：**

```json
{
  "bk_tenant_id": "可选，租户 ID",
  "kind": "必填，集群类型",
  "namespace": "必填，命名空间",
  "name": "必填，集群配置名称"
}
```

**响应：** 与 `admin.datalink.component_config` 格式相同。

**后端逻辑：** 查找 `ClusterConfig` 记录，调用 `.component_config`，脱敏，返回。

---

### 2.8 `admin.datalink.datalink_list`

**参数：**

```json
{
  "bk_tenant_id": "可选，租户 ID",
  "namespace": "可选，命名空间过滤",
  "search": "可选，按 data_link_name 模糊搜索",
  "data_link_strategy": "可选，按链路策略过滤",
  "bk_data_id": "可选，按关联数据源 ID 过滤",
  "page": 1,
  "page_size": 20
}
```

**后端逻辑：**

1. 查询 `models.DataLink.objects.filter(bk_tenant_id=bk_tenant_id)`
2. 按 `namespace` 过滤（可选）
3. 按 `search` 模糊匹配 `data_link_name`（可选）
4. 按 `data_link_strategy` 精确过滤（可选）
5. 按 `bk_data_id` 精确过滤（可选）
6. 分页

**响应 item 字段：**

`data_link_name`, `namespace`, `data_link_strategy`, `bk_data_id`, `table_ids`（数量）, `created_at`, `updated_at`

**前端过滤表：**

| 参数                 | 控件            | 位置     |
| -------------------- | --------------- | -------- |
| `namespace`          | select/combobox | 基础筛选 |
| `search`             | text input      | 基础筛选 |
| `data_link_strategy` | select          | 基础筛选 |
| `bk_data_id`         | number input    | 高级筛选 |

---

### 2.9 `admin.datalink.datalink_detail`

**参数：**

```json
{
  "bk_tenant_id": "可选，租户 ID",
  "data_link_name": "必填，链路名称",
  "include": ["可选，component_config"]
}
```

**后端逻辑：**

1. 查询 `DataLink.objects.get(bk_tenant_id, data_link_name=data_link_name)`
2. 返回 DataLink 基本信息
3. 查询所有 `data_link_name` 匹配的子组件（遍历 `COMPONENT_CLASS_MAP` 中每种模型，**跳过 DataIdConfig**）：
   - 对每种模型执行 `.filter(bk_tenant_id, data_link_name=data_link_name)`
   - 将匹配的组件列表返回，按 Kind 分组
4. 如果 `include` 包含 `"component_config"`：为每个子组件调用 `.component_config` 并返回（脱敏后）

> **为何跳过 DataIdConfig：** DataIdConfig 虽然继承自 `DataLinkResourceConfigBase`，但它通过 `bk_data_id` 与 DataSource 关联，其 `data_link_name` 始终为空。DataLink 自身已通过 `bk_data_id` 字段持有数据源引用，无需在子组件中重复展示。

**响应：**

```json
{
  "data": {
    "kind": "DataLink",
    "data_link_name": "...",
    "bk_tenant_id": "...",
    "namespace": "...",
    "data_link_strategy": "...",
    "bk_data_id": 1001,
    "table_ids": ["..."],
    "created_at": "...",
    "updated_at": "...",
    "components": {
      "ResultTable": [{ "name": "...", "table_id": "...", "component_config": {} }],
      "VmStorageBinding": [{ ... }],
      "ElasticSearchBinding": [{ ... }],
      "DorisBinding": [{ ... }],
      "Databus": [{ ... }],
      "ConditionalSink": [{ ... }]
    }
  },
  "trace_id": "...",
  "warnings": []
}
```

---

### 2.7 `admin.datalink.datalink_component_config`（懒加载专用）

**参数：**

```json
{
  "bk_tenant_id": "可选，租户 ID",
  "kind": "必填，子组件类型",
  "namespace": "必填，命名空间",
  "name": "必填，子组件名称"
}
```

**响应：** 与 `admin.datalink.component_config` 相同。

**后端逻辑：** 与 `admin.datalink.component_config` 相同 —— 查找对应模型记录，调用 `.component_config`，脱敏，返回。

> **设计说明：** `datalink_component_config` 与 `component_config` 功能等价，但作为独立操作以便在 DataLink 详情页中按清晰的操作语义调用。实现可复用同一内部函数。

---

### 2.8 实现文件

**新建：** `bkmonitor/kernel_api/rpc/functions/admin/datalink.py`

**修改：** `bkmonitor/kernel_api/rpc/functions/admin/__init__.py`（注册新模块）

---

## 3. 前端设计

### 3.1 路由与导航

**路由定义（`router.tsx`）：**

```ts
// 列表页
const dataLinkListRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'data-links',
  component: GuardedDataLinkListPage
});

// 详情页
const dataLinkDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'data-links/detail',
  component: GuardedDataLinkDetailPage
});
```

**侧边栏导航：**

在"资源管理"分组下新增：

```tsx
<Link to="/data-links" search={createEnvironmentSearch(...)}>
  <Network aria-hidden="true" size={18} />
  DataLink
</Link>
```

### 3.2 目录结构

```
src/features/datalink/
├── schemas.ts          # Zod schema + TypeScript 类型
├── api.ts              # RPC 调用函数
├── queries.ts          # TanStack Query hooks
├── constants.ts        # Kind 标签、状态颜色映射
├── DataLinkListPage.tsx  # 列表页（Kind Tab 切换）
└── DataLinkDetailPage.tsx # 详情页
```

### 3.3 列表页设计（DataLinkListPage）

**URL 参数：**

- `kind` — 当前选中的 Tab
- `namespace` — 命名空间过滤（可选）
- `search` — 搜索关键词（可选）

**页面结构：**

```
┌─────────────────────────────────────────────┐
│  eyebrow: DataLink                           │
│  h2: 数据链路管理                             │
│                                              │
│  [DataLink] [DataId] [ResultTable] [Vm...]  │  ← Kind Tabs
│                                              │
│  ┌─ FilterToolbar ────────────────────────┐ │
│  │ [namespace ▼] [search 🔍] [搜索按钮]   │ │
│  └───────────────────────────────────────┘ │
│                                              │
│  ┌─ DataTable ────────────────────────────┐ │
│  │ 列: (按 Kind 动态)                     │ │
│  │ ■ name  ■ status  ■ namespace          │ │
│  │ ■ created_at  ■ updated_at              │ │
│  │ ...(kind-specific fields)              │ │
│  │ 操作: [查看详情]                        │ │
│  └───────────────────────────────────────┘ │
│                                              │
│  <Pagination page={} pageSize={} total={} />│
└─────────────────────────────────────────────┘
```

**Tab 定义（constants.ts）：**

```ts
export const DATA_LINK_KIND_TABS = [
  { kind: 'DataLink', label: '链路', icon: Network },
  { kind: 'DataId', label: '数据源', icon: Database },
  { kind: 'ResultTable', label: '结果表', icon: Table },
  { kind: 'VmStorageBinding', label: 'VM 绑定', icon: HardDrive },
  { kind: 'ElasticSearchBinding', label: 'ES 绑定', icon: HardDrive },
  { kind: 'DorisBinding', label: 'Doris 绑定', icon: HardDrive },
  { kind: 'Databus', label: '数据总线', icon: ArrowLeftRight },
  { kind: 'ConditionalSink', label: '条件路由', icon: GitFork },
  { kind: 'ClusterConfig', label: '集群配置', icon: Server }
] as const;
```

**各 Tab 的表格列定义：**

| Tab                  | 列表列                                                                                              |
| -------------------- | --------------------------------------------------------------------------------------------------- |
| DataLink             | `data_link_name`, `namespace`, `data_link_strategy`, `bk_data_id`, `table_ids`(count), `created_at` |
| DataId               | `name`, `bk_data_id`, `namespace`, `status`, `data_link_name`, `created_at`                         |
| ResultTable          | `name`, `table_id`, `data_type`, `namespace`, `status`, `data_link_name`, `created_at`              |
| VmStorageBinding     | `name`, `vm_cluster_name`, `bkbase_result_table_name`, `namespace`, `status`, `data_link_name`      |
| ElasticSearchBinding | `name`, `es_cluster_name`, `bkbase_result_table_name`, `namespace`, `status`, `data_link_name`      |
| DorisBinding         | `name`, `doris_cluster_name`, `bkbase_result_table_name`, `namespace`, `status`, `data_link_name`   |
| Databus              | `name`, `data_id_name`, `bk_data_id`, `namespace`, `status`, `data_link_name`                       |
| ConditionalSink      | `name`, `namespace`, `status`, `data_link_name`                                                     |
| ClusterConfig        | `name`, `kind`, `namespace`, `created_at`, `updated_at`                                             |

### 3.4 详情页设计（DataLinkDetailPage）

**URL 参数：**

- `kind` — 组件类型
- `namespace` — 命名空间
- `name` — 组件名称
- `scope` — （仅 DataLink 时）是否为链路视图

**页面结构（DataLink 链路视图）：**

```
┌─────────────────────────────────────────────┐
│  eyebrow: DataLink Detail                   │
│  h2: {data_link_name}                       │
│                      [返回 DataLink 列表]    │
│                                              │
│  ┌─ DataLink 基本信息 ────────────────────┐ │
│  │ namespace  ●  data_link_strategy        │ │
│  │ bk_data_id ●  table_ids                 │ │
│  │ created_at ●  updated_at                │ │
│  └───────────────────────────────────────┘ │
│                                              │
│  ┌─ 关联组件 ─────────────────────────────┐ │
│  │                                        │ │
│  │  ■ DataId (1 个)                       │ │
│  │    ┌─ DataTable ──────────────────┐    │ │
│  │    │ name  bk_data_id  status     │    │ │
│  │    │      [获取配置]              │    │ │
│  │    └────────────────────────────┘    │ │
│  │                                        │ │
│  │  ■ ResultTable (2 个)                 │ │
│  │    ┌─ DataTable ──────────────────┐    │ │
│  │    │ name  table_id  data_type...  │    │ │
│  │    │      [获取配置]              │    │ │
│  │    └────────────────────────────┘    │ │
│  │                                        │ │
│  │  ■ VmStorageBinding (1 个)            │ │
│  │  ■ ElasticSearchBinding (1 个)        │ │
│  │  ■ Databus (1 个)                    │ │
│  │  ■ ConditionalSink (1 个)            │ │
│  └──────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

每个子组件组的 DataTable 包含各 Kind 的特有列 + "获取配置"按钮（lazy fetch component_config）。

**页面结构（组件视图 — 非 DataLink）：**

```
┌─────────────────────────────────────────────┐
│  eyebrow: DataLink Detail                   │
│  h2: {name}                                 │
│                      [返回 DataLink 列表]    │
│                                              │
│  ┌─ 基本信息 ─────────────────────────────┐ │
│  │ kind  ●  name  ●  namespace            │ │
│  │ status  ●  data_link_name             │ │
│  │ bk_biz_id  ●  bk_tenant_id            │ │
│  │ ...(kind-specific fields)             │ │
│  │ created_at  ●  updated_at              │ │
│  └───────────────────────────────────────┘ │
│                                              │
│  ┌─ component_config ─────────────────────┐ │
│  │ [获取 component_config] 按钮           │ │
│  │ JSON 文本框（展示/折叠）                │ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### 3.5 Schema 设计（schemas.ts）

**核心类型：**

```ts
// DataLinkKind 枚举映射
const dataLinkKindSchema = z.enum([
  'DataLink',
  'DataId',
  'ResultTable',
  'VmStorageBinding',
  'ElasticSearchBinding',
  'DorisBinding',
  'Databus',
  'ConditionalSink',
  'KafkaChannel',
  'VmStorage',
  'ElasticSearch',
  'Doris'
]);

// 列表查询参数
const dataLinkListQuerySchema = paginationQuerySchema.extend({
  bkTenantId: z.string().default('system'),
  kind: dataLinkKindSchema,
  namespace: z.string().optional(),
  search: z.string().optional()
});

// 每个 Kind 的列表 item schema（零散判别联合）
// ... 前端通过 kind 字段 + per-kind column 定义决定显示内容

// 列表响应
const dataLinkListResponseSchema = paginationResponseSchema.extend({
  items: z.array(
    z.object({
      kind: dataLinkKindSchema
      // ... common fields, kind-specific fields optional
    })
  )
});
```

**详情响应类型（分情况）：**

```ts
// DataLink 链路详情
const dataLinkDetailResponseSchema = z.object({
  kind: z.literal('DataLink'),
  data_link_name: z.string(),
  namespace: z.string(),
  data_link_strategy: z.string(),
  bk_data_id: z.number(),
  table_ids: z.array(z.string()),
  created_at: z.string(),
  updated_at: z.string(),
  components: z.object({
    DataId: z.array(dataIdComponentSchema).default([]),
    ResultTable: z.array(resultTableComponentSchema).default([]),
    VmStorageBinding: z.array(vmBindingComponentSchema).default([]),
    ElasticSearchBinding: z.array(esBindingComponentSchema).default([]),
    DorisBinding: z.array(dorisBindingComponentSchema).default([]),
    Databus: z.array(databusComponentSchema).default([]),
    ConditionalSink: z.array(conditionalSinkComponentSchema).default([])
  })
});

// 组件配置详情（非 DataLink）
const dataLinkComponentDetailResponseSchema = z.object({
  // kind 特有字段
  component_config: z.unknown().optional(),
  warnings: z.array(z.string()).default([])
});
```

**component_config 懒加载：**

```ts
// 请求
const dataLinkComponentConfigRequestSchema = z.object({
  bkTenantId: z.string().default('system'),
  kind: dataLinkKindSchema,
  namespace: z.string(),
  name: z.string()
});

// 响应
const dataLinkComponentConfigResponseSchema = z.object({
  kind: z.string(),
  namespace: z.string(),
  name: z.string(),
  component_config: z.unknown()
});
```

### 3.6 API 与查询设计

**api.ts：**

```ts
// ========== 组件（Component）API ==========

// 组件列表
export async function listComponents(
  environment: AdminEnvironment,
  query: ComponentListQuery
): Promise<ComponentListResponse>;

// 组件详情
export async function getComponentDetail(
  environment: AdminEnvironment,
  bkTenantId: string,
  kind: DataLinkKind,
  namespace: string,
  name: string,
  includeComponentConfig?: boolean
): Promise<ComponentDetailResponse>;

// 组件懒加载 component_config
export async function getComponentConfig(
  environment: AdminEnvironment,
  params: ComponentConfigRequest
): Promise<ComponentConfigResponse>;

// ========== DataLink 链路 API ==========

// DataLink 链路列表
export async function listDataLinks(
  environment: AdminEnvironment,
  query: DataLinkListQuery
): Promise<DataLinkListResponse>;

// DataLink 链路详情（含全部子组件）
export async function getDataLinkDetail(
  environment: AdminEnvironment,
  bkTenantId: string,
  dataLinkName: string,
  includeComponentConfig?: boolean
): Promise<DataLinkDetailResponse>;

// DataLink 详情页中懒加载子组件 component_config
export async function getDataLinkComponentConfig(
  environment: AdminEnvironment,
  params: ComponentConfigRequest
): Promise<ComponentConfigResponse>;
```

**queries.ts：**

```ts
export function useComponentList(environment: AdminEnvironment, query: ComponentListQuery);
export function useComponentDetail(
  environment: AdminEnvironment,
  bkTenantId: string,
  kind: string,
  namespace: string,
  name: string,
  includeComponentConfig?: boolean
);
export function useComponentConfig(environment: AdminEnvironment); // mutation

export function useDataLinkList(environment: AdminEnvironment, query: DataLinkListQuery);
export function useDataLinkDetail(
  environment: AdminEnvironment,
  bkTenantId: string,
  dataLinkName: string,
  includeComponentConfig?: boolean
);
export function useDataLinkComponentConfig(environment: AdminEnvironment); // mutation
```

### 3.7 前端注册

**operations.ts：** 新增 6 个 operation：

```ts
'datalink.component_list'; // => FUNC_DATALINK_COMPONENT_LIST
'datalink.component_detail'; // => FUNC_DATALINK_COMPONENT_DETAIL
'datalink.component_config'; // => FUNC_DATALINK_COMPONENT_CONFIG
'datalink.datalink_list'; // => FUNC_DATALINK_LIST
'datalink.datalink_detail'; // => FUNC_DATALINK_DETAIL
'datalink.datalink_component_config'; // => FUNC_DATALINK_COMPONENT_CONFIG
```

**mock.ts：** 新增 3 个 mock 处理器，返回示例数据。

**mockData.ts：** 新增各 Kind 的示例数据。

**router.tsx：** 新增 2 条路由 + 1 个 sidebar 导航链接。

---

## 4. 实施步骤

### 第 1 步：后端 RPC 实现

- [ ] 新建 `bkmonitor/kernel_api/rpc/functions/admin/datalink.py`
  - [ ] 实现 `list_components`（`admin.datalink.component_list`，按 Kind 分发查询）
  - [ ] 实现 `get_component_detail`（`admin.datalink.component_detail`，按 Kind 分发详情）
  - [ ] 实现 `get_component_config`（`admin.datalink.component_config`，懒加载 component_config）
  - [ ] 实现 `list_datalinks`（`admin.datalink.datalink_list`，DataLink 链路列表）
  - [ ] 实现 `get_datalink_detail`（`admin.datalink.datalink_detail`，链路 + 全部子组件）
  - [ ] 实现 `get_datalink_component_config`（可复用 `get_component_config` 内部逻辑）
  - [ ] 编写 per-kind 的序列化函数
  - [ ] 添加 safety_level = read
  - [ ] 添加 params_schema、example_params
- [ ] 修改 `bkmonitor/kernel_api/rpc/functions/admin/__init__.py`，注册 `datalink` 模块

### 第 2 步：前端 Schema 与类型

- [ ] 新建 `src/features/datalink/schemas.ts`
  - [ ] 定义 `DataLinkKindSchema` 枚举
  - [ ] 定义列表查询/响应 schema
  - [ ] 定义每种 Kind 的 detail schema
  - [ ] 定义 component_config 请求/响应 schema
  - [ ] 导出 TypeScript 类型
- [ ] 新建 `src/features/datalink/constants.ts`
  - [ ] Kind 标签/图标映射
  - [ ] 状态颜色映射
  - [ ] 每种 Kind 的列表列定义
  - [ ] 每种 Kind 的 detail Info 字段定义

### 第 3 步：前端 API & Queries

- [ ] 新建 `src/features/datalink/api.ts`
  - [ ] `listDataLinkResources()`
  - [ ] `getDataLinkDetail()`
  - [ ] `getDataLinkComponentConfig()`
- [ ] 新建 `src/features/datalink/queries.ts`
  - [ ] `useDataLinkList()`
  - [ ] `useDataLinkDetail()`
  - [ ] `useDataLinkComponentConfig()` (mutation)

### 第 4 步：前端页面

- [ ] 新建 `src/features/datalink/DataLinkListPage.tsx`
  - [ ] Kind 切换 Tab 栏
  - [ ] FilterToolbar（namespace 选择、搜索关键词）
  - [ ] 动态表格列定义（基于选中 Kind）
  - [ ] 链接到详情页
  - [ ] 分页
- [ ] 新建 `src/features/datalink/DataLinkDetailPage.tsx`
  - [ ] 根据 kind 渲染不同结构
  - [ ] DataLink 链路视图：基本信息 + 按 Kind 分组的组件表格
  - [ ] 组件视图：基本信息 + 懒加载 component_config
  - [ ] "获取配置" 按钮（expand/collapse JSON 文本框）
  - [ ] 返回目标管理

### 第 5 步：路由与注册

- [ ] 修改 `src/app/router.tsx`
  - [ ] 导入 DataLink 页面组件
  - [ ] 创建 `dataLinkListRoute`、`dataLinkDetailRoute`
  - [ ] 注入侧边栏 DataLink 链接
  - [ ] 修改 `src/features/kernel-rpc/operations.ts`
  - [ ] 注册 6 个新 operation
- [ ] 修改 `src/features/kernel-rpc/mock.ts`
  - [ ] 添加 6 个 mock 处理器
- [ ] 修改 `src/features/kernel-rpc/mockData.ts`
  - [ ] 添加各 Kind 的 mock 列表数据
  - [ ] 添加组件详情/component_config mock 数据

### 第 6 步：验证

- [ ] `pnpm format:check` 通过
- [ ] `pnpm lint` 通过（无新增错误）
- [ ] `pnpm typecheck` 通过
- [ ] `pnpm test` 通过
- [ ] 手动验证：Tab 切换正常、列表加载、详情加载、component_config 懒加载

---

## 5. 关键技术要点

### 5.1 Kind 切换时保留分页/筛选

每个 Kind 独立维护其分页和筛选状态。切换 Kind 时不应共用 page/pageSize/search，而应为每个 Kind 独立存储（或 reset 到初始值）。

**实现：** 使用 `useRef<Record<string, KindState>>` 或 `useSearch` 将 kind 写入 URL。

### 5.2 DataLink 详情中按 Kind 分组的组件表

DataLink detail 接口返回 `components: { [kind]: [...] }`。前端遍历 Object.entries 渲染多个 `<section>` + `<DataTable>`。

### 5.3 ClusterConfig 的识别

对于 KafkaChannel/VmStorage/ElasticSearch/Doris，`name` 字段较长（255）。列表和详情默认不展示 `origin_config` JSON（该字段较大），仅在详情中作为独立 section 展示。

### 5.4 component_config 敏感字段

对于包含 password/secret 字段的 component_config（如 KafkaChannelConfig），调用 `_mask_sensitive_fields()` 进行脱敏。该函数已在 `common.py` 中实现，支持 `ClusterConfig` 和 `DataIdConfig` 的配置脱敏。

---

## 6. 验证要求

1. `pnpm format:check` — 格式检查
2. `pnpm lint` — 代码规范检查
3. `pnpm typecheck` — TypeScript 类型检查
4. `pnpm test` — 单元测试
5. 关键页面手动验证：
   - DataLink 列表页 Tab 切换、各 Kind 表格正确展示
   - 各 Kind 列表的筛选、搜索、分页独立工作
   - DataLink 详情页（链路视图）展示所有子组件
   - 组件详情页 component_config 懒加载正常
   - 租户切换时页面行为正确
