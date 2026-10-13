# 指标插件模块 (metric_plugin)

## 概述

`metric_plugin` 模块是 BlueKing Monitor 中用于管理指标采集插件的核心模块。该模块提供了插件的全生命周期管理能力，包括插件的创建、版本管理、发布、部署等功能。

## 核心设计理念

### 插件管理器 (Manager)

插件管理器采用**策略模式**，负责处理插件在不同平台（如节点管理、作业平台）的具体实现逻辑。

**设计要点**：

1. **平台抽象**：通过 `BaseMetricPluginManager` 基类定义统一的接口，不同平台提供具体实现（如 `NodemanPluginManager`、`JobPluginManager`）
2. **自动选择**：根据插件类型自动选择对应的管理器实现，上层业务无需关心平台差异
3. **核心职责**：
   - `apply_data_link()`：申请数据链路，创建数据链路配置并获取数据ID（可重入）
   - `sync_metrics()`：同步指标配置，当开启指标自动发现时自动刷新插件的指标定义
4. **职责边界**：管理器专注于平台相关的业务逻辑（如插件注册、导出、调试），不涉及部署流程

### 插件安装器 (Installer)

插件安装器采用**模板方法模式**，负责将插件实际安装到目标节点并管理部署生命周期。

**设计要点**：

1. **统一流程**：通过 `BaseInstaller` 基类定义统一的安装流程模板，子类实现平台特定的安装逻辑
2. **版本管理**：支持部署版本差异比对，自动识别插件版本、部署参数、采集范围等变化，避免重复安装
3. **生命周期管理**：提供完整的部署操作接口：
   - `install()`：安装部署版本（比对差异，创建新版本记录）
   - `uninstall()`：卸载插件
   - `start()` / `stop()`：启动/停止采集
   - `run()`：主动执行操作（如调试）
   - `retry()`：重试失败操作
   - `revoke()`：终止进行中的操作
   - `status()`：查询部署状态
4. **协作关系**：安装器内部持有插件管理器实例，通过管理器处理平台相关的具体操作（如节点管理的订阅操作）

**设计优势**：

- **职责分离**：Manager 负责平台抽象，Installer 负责部署流程，各司其职
- **可扩展性**：新增平台只需实现对应的 Manager 和 Installer，无需修改核心逻辑
- **版本控制**：通过版本差异比对，确保部署的一致性和可追溯性

### 数据接入

插件的数据需要上报到指定的数据源上，不同的插件对应不同的数据源，在创建插件/插件部署项时，需要创建数据源。

目前有几种数据源模式:

1. 基于插件创建的数据源，所有的插件部署项都会上报到这个数据源上。
2. 基于插件+业务创建的数据源，该业务下的所有该插件部署项都会上报到这个数据源上。
3. 基于插件部署项创建的数据源，每个部署项都有独立的数据源。

根据数据源模式的不同

1. bk_data_id会记录在插件/插件部署项的related_params中。
2. 需要不同的时机进行数据源的创建。
   - 基于插件创建的数据源，在创建/发布插件时创建。
   - 基于插件+业务创建的数据源，在该业务下第一个插件部署项创建时创建。
   - 基于插件部署项创建的数据源，在创建插件部署项时创建。

## 插件管理流程

### 插件配置分类

插件的配置分为三类：
1. 基础配置：如插件名称、描述、标签等，这些字段发生变化时，不需要变更版本号，也不会产生新的版本。
2. 插件主要配置：如参数、定义、指标配置等，当这些字段发生变化时，需要变更主版本号。
3. 插件次要配置：如插件名称、描述、标签等，当这些字段发生变化时，需要变更次版本号。

### 插件管理流程

1. 创建插件时，生成初始版本，默认版本号为 1.0，默认状态为 DEBUG。
2. 创建插件版本时，基于最新的release版本生成新的版本，根据配置的变更情况，决定是否变更主版本号或次版本号，默认状态为 DEBUG，如果存在同版本号的 DEBUG 版本，则直接覆盖。禁止创建小于已发布版本的DEBUG版本。
3. 更新插件版本时，只能更新次要配置，不能更新主要配置，且不能覆盖已发布版本。
4. 当确认插件版本配置无误后，可以发布插件版本，此时插件版本状态变为 RELEASE。

### 核心方法

1. create_metric_plugin - 创建插件
2. TODO: import_plugin - 导入插件包
3. TODO: export_plugin - 导出插件包
4. create_metric_plugin_version - 创建插件版本(变更版本号)
5. update_metric_plugin_version - 更新插件版本(不变更版本号)
6. release_metric_plugin_version - 发布插件版本
7. get_metric_plugin - 获取插件信息(最新发布/调试版本或指定版本号)
8. get_metric_plugin_versions - 获取插件版本列表
9. delete_metric_plugin - 删除插件
10. list_metric_plugins - 获取插件列表（可以指定是否优先显示发布版本）

## 节点管理插件

节点管理插件就是通过节点管理进行插件管理和采集下发的插件类型，目前支持的节点管理插件类型有：

- exporter - exporter采集
- script - 脚本采集
- jmx - jmx采集
- datadog - datadog采集
- pushgateway - pushgateway采集
- snmp - snmp采集
- snmp_trap - snmp_trap采集
- process - 进程采集
- log - 日志关键字采集

其中主要分为两大类

一类是需要用户制作插件包后进行采集下发的插件类型。

- exporter
- script
- jmx
- datadog
- pushgateway
- snmp

一类是内置插件类型，租户下只有一个插件实例，需要在合适的时机进行内置。

- snmp_trap
- process
- log

### 节点管理数据接入

#### 数据链路（Metadata）实现说明

节点管理类插件的数据接入由 `CustomNodemanPluginDataLinker` 负责（位于 `domains/metric_plugin/manager/node_man/datalink.py`），主要完成两件事：

1. **申请/校准数据源（data_id）**：确保插件对应的数据源存在，并且 data_source 的关键属性与当前插件期望一致。
2. **申请/校准时序分组（time_series_group）**：确保时序分组存在，且指标字段/维度字段配置与插件定义一致。

> 设计目标：**可重入**（重复执行不会产生重复资源）、**可演进**（插件配置变化能自动校准）、**向前兼容**（历史遗留 data_name/data_id 可复用）。

##### 1) 数据源（data_id）申请与更新规则

**相关字段存储**：

- `plugin.related_params["bk_data_id"]`：数据源 ID
- `plugin.related_params["data_name"]`：数据源名称（也是后续查询/创建时序分组的 name）
- 同步写入 `MetricPluginModel.related_params`，确保持久化

**核心流程（apply_data_ids）**：

- **优先复用已有 `bk_data_id`**：
  - 通过 `metadata_api.get_data_source(bk_data_id=...)` 拉取现状
  - 如果本地 `data_name` 与远端 `data_name` 不一致，则**只同步 `data_name`**（避免由于历史变更导致后续查不到分组）
- **如果没有 `bk_data_id`，尝试兼容旧版本 data_name**：
  - 旧版本 data_name：`{plugin.type.lower()}_{plugin.id}`
  - 调用 `metadata_api.get_data_source(data_name=...)`：
    - 若返回“DataSource 不存在”（错误信息包含 `DataSource matching query does not exist`），视为不存在，继续创建
    - 其他错误直接抛出，避免在不确定状态下重复创建数据源
- **创建新数据源**：
  - 新版本 data_name：`{plugin.type.lower()}_{plugin.id}_{random8}`（增加随机后缀，降低同名冲突风险）
  - 创建成功后写回 `bk_data_id` 与 `data_name` 并返回（本次不会继续做 modify 校准）

**自动校准（modify_data_source）触发条件**：

对比远端 `data_source` 与期望配置，仅当以下关键字段有差异时才调用 `metadata_api.modify_data_source(...)`：

- `is_platform_data_id`：来自 `plugin.is_global`
- `data_description`：固定格式 `plugin_type: {type}, plugin_id: {id}`
- `option`：固定为
  - `inject_local_time=True`
  - `allow_dimensions_missing=True`
  - `is_split_measurement=True`

##### 2) 时序分组（time_series_group）申请与更新规则

时序分组使用 `data_name` 作为 `time_series_group_name` 做唯一定位：

- 查询：`metadata_api.query_time_series_group(time_series_group_name=data_name)`
- **不存在则创建**：`metadata_api.create_time_series_group(...)`
- **存在则更新**：`metadata_api.modify_time_series_group(...)`（更新 label、data_label、metric_info_list 等）

**开关映射**：

- `enable_field_black_list`（时序分组选项）使用 `plugin.enable_metric_discovery`：
  - `True`：开启字段黑名单能力（指标自动发现开启时需要）
  - `False`：关闭字段黑名单能力（未开启自动发现时走白名单/固定字段模式）

##### 3) 指标字段与维度字段拼装规则（metric_info_list）

时序分组的 `metric_info_list` 由插件定义的 `metrics` 转换而来，并会注入内置维度与 DMS 注入维度，生成规则如下：

- **插件定义维度**：
  - 只收集 `monitor_type == "dimension"` 且 `is_active == True` 的字段
- **内置维度**：
  - 默认注入一组通用内置维度（如 `bk_target_ip`、`bk_target_cloud_id`、`bk_collect_config_id` 等）
  - 当 `plugin.label in ["component", "service_module"]` 时，还会额外注入服务实例类内置维度（如 `bk_target_service_instance_id`）
  - 为避免“插件自定义维度”与“内置维度”同名导致重复，内置维度注入会跳过插件已定义的同名维度
- **DMS 注入维度**：
  - 收集 `plugin.params` 中 `mode == dms_insert` 的参数名作为维度字段注入
  - 同样会跳过插件已定义的同名维度
- **指标字段**：
  - `monitor_type == "metric"` 的字段会被展开成时序字段，每个指标字段共享同一份 `tag_list`（维度列表）

#### 历史遗留问题

1. 在最早的插件数据接入时，插件的指标信息是固定的，插件会根据 metrics 信息进行实际分表，每一个指标分组都是一个独立的 RT，当指标移动分组时，实际的存储会发生变化。

2. 后续支持指标自动发现，实际的存储变为一个RT，所有的指标都在这个RT上，但是指标信息的不固定的，随时会发生增减。

#### 最终状态

1. 无论是否开启自动发现，后续全部使用一个RT进行存储，指标的分组只是虚拟分组。

2. 当未开启自动发现时，将 resulttable 的 option 的 enable_field_black_list 设置为 false，最终清洗时会使用白名单模式进行清洗。

3. 指标的维度只能进行全局开关，无法在分组内单独关闭。

4. 需要使用data_label对新旧数据查询进行兼容。

## 作业平台插件
### SQL 采集插件

SQL 采集插件就是直接通过作业平台进行插件管理和采集下发的插件类型，目前支持的 SQL 采集插件类型有：
- job_mysql - MySQL采集
- job_oracle - Oracle采集
- job_db2 - DB2采集

#### SQL 采集插件数据接入
为兼容现有的数据查询，global_biz_id为指定的全局业务id,plugin_category固定为 "SQL"，plugin_id 固定为对应的插件类型，如 "mysql_sql_plugin_1"。
- metadata_timeseriesgroups: 自定义上报时序分组，暂不接入，没用上指标自动发现能力，可不接入。
- dataid: data_source name 固定为 {global_biz_id}_{plugin_category.lower()}_{plugin_id}
- result_table: 单指标单表，table_id 固定为 {plugin_category.lower()}_{plugin_id}_{sql_alias}，sql_alias 与 指标组id(table_name)一致。

##### 数据链路（Metadata）实现说明

SQL 采集插件的数据接入能力重写自自插件管理器 `BaseMetricPluginManager` 负责（位于 `domains/metric_plugin/manager/base.py`），主要包含2个方法：

1. **申请/创建数据源与rt（apply_data_link）**：确保插件对应的数据源存在，并且 data_source 的关键属性与当前插件期望一致。
2. **删除数据源与rt（delete_data_link）**：确保插件对应的数据源被删除。

> 设计目标：**可重入**（重复执行不会产生重复资源）、**可演进**（插件配置变化能自动校准）、**向前兼容**（历史遗留 data_name/data_id 可复用）。

###### 1) 数据源（data_id）申请与更新规则

**相关字段存储**：

- `plugin.related_params["bk_data_id"]`：数据源 ID
- `plugin.related_params["data_name"]`：数据源名称
- 同步写入 `MetricPluginModel.related_params`，确保持久化

**核心流程（apply_data_ids）**：

- **优先复用已有 `bk_data_id`**：
  - 通过 `metadata_api.get_data_source(bk_data_id=...)` 拉取现状
  - 如果本地 `data_name` 与远端 `data_name` 不一致，则**只同步 `data_name`**（避免由于历史变更导致后续查不到分组）
- **如果没有 `bk_data_id`，尝试兼容旧版本 data_name**：
  - 旧版本 data_name：`{global_biz_id}_{plugin_category.lower()}_{plugin_id}`
  - 调用 `metadata_api.get_data_source(data_name=...)`：
    - 若返回“DataSource 不存在”（错误信息包含 `DataSource matching query does not exist`），视为不存在，继续创建
    - 其他错误直接抛出，避免在不确定状态下重复创建数据源
- **创建新数据源**：
  - 新版本 data_name：`{global_biz_id}_{plugin_category.lower()}_{plugin_id}`（与旧版一致，该插件暂不做改造）
  - 创建成功后写回 `bk_data_id` 与 `data_name` 并返回（本次不会继续做 modify 校准）

**自动校准（modify_data_source）触发条件**：

对比远端 `data_source` 与期望配置，仅当以下关键字段有差异时才调用 `metadata_api.modify_data_source(...)`：

- `is_platform_data_id`：来自 `plugin.is_global`
- `data_description`：固定格式 `plugin_type: {type}, plugin_id: {id}`
- `option`：固定为
  - `inject_local_time=True`
  - `allow_dimensions_missing=True`
  - `is_split_measurement=True`
