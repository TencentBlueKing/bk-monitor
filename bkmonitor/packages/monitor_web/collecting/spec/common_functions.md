# 公共函数/逻辑提取规划

## 0. compat 层核心转换函数

> 适配的核心是新旧数据模型之间的兼容转换。
> bk-monitor-base 中已有完整的部署管理能力（详见 `base_capability_mapping.md`），
> 因此公共函数中最重要的是 **compat 层转换函数**。

### 0.1 入参转换函数

#### `convert_save_params_to_base(data: dict, bk_tenant_id: str) -> CreateOrUpdateDeploymentParams`

**描述**：将旧版 `SaveCollectConfigResource` 的请求参数转换为 base 的 `CreateOrUpdateDeploymentParams`。

**映射逻辑**：
```python
# 旧版入参
data = {
    "id": 123,
    "name": "采集配置名称",
    "bk_biz_id": 2,
    "plugin_id": "my_plugin",
    "target_node_type": "TOPO",
    "target_nodes": [{"bk_inst_id": 1, "bk_obj_id": "module"}],
    "params": {"collector": {...}, "plugin": {...}},
    "remote_collecting_host": {"bk_host_id": 100, ...},
}

# 转换为 base 入参
CreateOrUpdateDeploymentParams(
    id=data.get("id"),
    name=data["name"],
    plugin_id=data["plugin_id"],
    plugin_version=_resolve_plugin_version(bk_tenant_id, data["plugin_id"]),
    target_scope=MetricPluginDeploymentScope(
        node_type=data["target_node_type"],
        nodes=data["target_nodes"],
    ),
    remote_scope=_convert_remote_host_to_scope(data.get("remote_collecting_host")),
    params=data.get("params", {}),
)
```

#### `_resolve_plugin_version(bk_tenant_id, plugin_id) -> VersionTuple`

**描述**：获取插件的最新已发布版本。如果旧版请求未显式传 plugin_version，需通过 base API 获取。

#### `_convert_remote_host_to_scope(remote_host: dict | None) -> MetricPluginDeploymentScope | None`

**描述**：将旧版的 `remote_collecting_host`（单主机 dict）转换为 base 的 `MetricPluginDeploymentScope`。

### 0.2 出参转换函数

#### `convert_deployment_to_legacy(deployment, version, plugin) -> dict`

**描述**：将 base 的 `MetricPluginDeployment` + `MetricPluginDeploymentVersion` + `MetricPlugin` 转换为旧版 API 的响应格式。

**映射逻辑**：
```python
def convert_deployment_to_legacy(
    deployment: MetricPluginDeployment,
    version: MetricPluginDeploymentVersion | None,
    plugin: MetricPlugin,
) -> dict:
    return {
        "id": deployment.id,
        "name": deployment.name,
        "bk_biz_id": deployment.bk_biz_id,
        "collect_type": plugin.type,
        "plugin_id": deployment.plugin_id,
        "target_object_type": _label_to_object_type(plugin.label),
        "target_node_type": version.target_scope.node_type if version else "",
        "target_nodes": version.target_scope.nodes if version else [],
        "params": version.params if version else {},
        "remote_collecting_host": _convert_scope_to_remote_host(version.remote_scope) if version else None,
        "plugin_info": convert_plugin_to_legacy_info(plugin),
        "subscription_id": deployment.related_params.get("subscription_id", 0),
        "label": plugin.label,
        "status": _convert_deployment_status_to_legacy(deployment.status),
        "task_status": _convert_deployment_status_to_task_status(deployment.status),
        "create_time": deployment.created_at.isoformat(),
        "create_user": deployment.created_by,
        "update_time": deployment.updated_at.isoformat(),
        "update_user": deployment.updated_by,
    }
```

#### `convert_deployment_list_to_legacy(deployments, ...) -> list[dict]`

**描述**：批量转换部署项列表，包括补充 `need_upgrade`、`error_instance_count` 等旧版额外字段。

### 0.3 状态枚举转换

#### `_convert_deployment_status_to_legacy(status: str) -> str`

**描述**：将 base 的 `MetricPluginDeploymentStatusEnum` 转换为旧版 `OperationResult` 枚举。

| Base 状态 | 旧版 status | 旧版 task_status |
|-----------|-------------|-----------------|
| `INITIALIZING` | `PREPARING` | `PREPARING` |
| `DEPLOYING` | `DEPLOYING` | `DEPLOYING` |
| `RUNNING` | `SUCCESS` | `STARTED` |
| `STOPPED` | `SUCCESS` | `STOPPED` |
| `STOPPING` | `DEPLOYING` | `STOPPING` |
| `STARTING` | `DEPLOYING` | `STARTING` |
| `FAILED` | `FAILED` | `FAILED` |

### 0.4 插件信息转换

#### `convert_plugin_to_legacy_info(plugin: MetricPlugin) -> dict`

**描述**：将 base 的 `MetricPlugin` 转换为旧版 `plugin_info` 字典（CollectConfigDetail 中嵌套的插件信息）。

#### `_label_to_object_type(label: str) -> str`

**描述**：根据插件的 `label` 推导旧版的 `target_object_type`（HOST / SERVICE）。

#### `_convert_scope_to_remote_host(scope: MetricPluginDeploymentScope | None) -> dict | None`

**描述**：将 base 的远程 scope 转换回旧版的 `remote_collecting_host` 单主机格式。

### 0.5 版本号转换

#### `convert_version_to_legacy(version: VersionTuple) -> str`

**描述**：`VersionTuple(1, 10)` → `"1.10"`

#### `convert_legacy_version_to_tuple(version_str: str) -> VersionTuple`

**描述**：`"1.10"` → `VersionTuple(1, 10)`

### 0.6 ~~status() 结果转换~~（✅ 已由 Base 完成，无需 compat 层转换）

> ~~**这是 compat 层最复杂的部分。**~~ ✅ Base 的 `NodemanInstaller.status(diff)` 已直接返回
> 旧版兼容格式（含 `node_path`/`label_name`/`is_label`/`task_id`/`plugin_version` 等所有旧版字段），
> SaaS 层 **不需要做任何格式转换**，直接使用 `installer.status(diff=...)` 的返回值即可。
>
> Base 内部已实现以下旧版逻辑：
> - `_get_legacy_node_diff()` → 节点差异计算（ADD/REMOVE/UPDATE/RETRY）
> - `_build_legacy_status_groups()` → 按节点类型分组（TOPO/HOST/DYNAMIC_GROUP/TEMPLATE）
> - `_process_instance_result()` → 实例字段转换（task_id, plugin_version, log, status, scope_ids）
> - `_convert_legacy_instance_status()` → 实例状态转换（STARTING/STOPPING）
> - `_build_status_output_instance()` → 移除内部字段后输出
>
> 因此以下函数 **不再需要在 SaaS compat 层实现**：
> - ~~`convert_base_status_to_legacy()`~~
> - ~~`_compute_node_diff()`~~
> - ~~`_convert_instance_status()`~~
> - ~~`_regroup_by_node_type()`~~

---

## 1. 总览

分析 collecting 模块所有 39 个 Resource，提取出可在多个 Resource 间复用的公共逻辑，
按功能域分为以下几类。

## 2. 公共函数清单

### 2.1 采集配置获取与校验

#### `get_collect_config_or_raise(bk_biz_id, config_id) -> CollectConfigMeta`

**描述**：获取采集配置（含关联的 deployment_config），不存在时抛出 `CollectConfigNotExist` 异常。

**当前状态**：每个 Resource 都在 `perform_request` 中重复实现如下模式：
```python
try:
    collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(
        id=config_id, bk_biz_id=bk_biz_id
    )
except CollectConfigMeta.DoesNotExist:
    raise CollectConfigNotExist({"msg": config_id})
```

**使用的 Resource**：
- `CollectConfigDetailResource`
- `ToggleCollectConfigStatusResource`
- `DeleteCollectConfigResource`
- `CloneCollectConfigResource`
- `RetryTargetNodesResource`
- `RevokeTargetNodesResource`
- `RunCollectConfigResource`
- `BatchRevokeTargetNodesResource`
- `GetCollectLogDetailResource`
- `BatchRetryConfigResource`
- `SaveCollectConfigResource`（编辑时）
- `UpgradeCollectPluginResource`
- `RollbackDeploymentConfigResource`
- `GetMetricsResource`
- `DeploymentConfigDiffResource`
- `FrontendTargetStatusTopoResource`

**提取建议**：
- 提取为模块级别公共函数
- 支持可选的 `select_related` 参数
- base 适配时，新版实现替换为 base API 调用

---

### 2.2 安装器获取

#### `get_collect_installer(collect_config, *args, **kwargs) -> BaseInstaller`

**描述**：根据插件类型获取对应的安装器实例（NodeMan / K8s）。

**当前状态**：已是独立函数，位于 `deploy/__init__.py`。

**使用的 Resource**：
- `ToggleCollectConfigStatusResource`
- `DeleteCollectConfigResource`
- `RetryTargetNodesResource`
- `RevokeTargetNodesResource`
- `RunCollectConfigResource`
- `BatchRevokeTargetNodesResource`
- `GetCollectLogDetailResource`
- `BatchRetryConfigResource`
- `SaveCollectConfigResource`
- `UpgradeCollectPluginResource`
- `RollbackDeploymentConfigResource`
- `CollectTargetStatusResource`（及其子类）
- `CollectTargetStatusTopoResource`
- `UpdateConfigInstanceCountResource`
- `CheckAdjectiveCollect`

**适配建议**：
- 新版需 base 侧提供等价的安装器获取机制
- 或在 SaaS 层包装 base 安装器为 `BaseInstaller` 接口

---

### 2.3 节点管理订阅统计

#### `fetch_sub_statistics(config_data_list) -> tuple[dict, list]`

**描述**：批量获取节点管理订阅统计数据，包含分组请求（每组 20 个）逻辑。

**当前状态**：已是独立函数，位于 `utils.py`。

**使用的 Resource**：
- `CollectConfigListResource.get_realtime_data()`
- `UpdateConfigInstanceCountResource`

**适配建议**：
- 新版可由 base 封装节点管理 API 调用
- 或保留在 SaaS 层作为 thin wrapper

---

### 2.4 密码处理

#### `update_password_inplace(data, config_meta) -> None`

**描述**：将密码类型参数的 bool/None 值替换为实际密码值。编辑采集配置时，前端传入 `True`（已设置）或 `None`（未更改），需替换为数据库中的实际密码。

**当前状态**：定义为 `SaveCollectConfigResource` 的静态方法。

**使用的 Resource**：
- `SaveCollectConfigResource`
- `UpgradeCollectPluginResource`

**提取建议**：
- 提取为模块级别公共函数
- 与 `password_convert`（详情返回时转为 bool）配对

#### `password_convert(collect_config_meta) -> None`

**描述**：将密码类型参数转为 bool 值，用于前端展示（避免 F12 看到明文）。

**当前状态**：定义为 `CollectConfigDetailResource` 的静态方法。

**使用的 Resource**：
- `CollectConfigDetailResource`

**提取建议**：提取为公共函数，与 `update_password_inplace` 归为一组。

---

### 2.5 虚拟插件管理

#### `get_collector_plugin(data) -> CollectorPluginMeta`

**描述**：根据 `collect_type` 获取或创建对应的虚拟插件（LOG/PROCESS/SNMP_TRAP/K8S/普通插件）。

**当前状态**：定义为 `SaveCollectConfigResource` 的静态方法。

**使用的 Resource**：
- `SaveCollectConfigResource`

**提取建议**：
- 提取为独立函数
- 新版需根据 plugin 适配状态（`ENABLE_BK_MONITOR_BASE_PLUGIN`）走不同路径
- 如果 plugin 已适配 base，则虚拟插件创建需走 base 的 `metric_plugin` 域

---

### 2.6 目标节点解析

#### `resolve_target_nodes(collect_config) -> list`

**描述**：根据 `target_node_type` 和 `target_object_type` 解析目标节点详情（调用 CMDB API）。

**当前状态**：内联在 `CollectConfigDetailResource.perform_request()` 中，有 5+ 种类型分支。

**使用的 Resource**：
- `CollectConfigDetailResource`

**提取建议**：
- 提取为公共函数
- 不同类型使用策略模式或映射表分发

#### `resolve_host_ids_by_target(target_nodes, target_node_type, bk_biz_id) -> list[int]`

**描述**：按目标类型解析主机 ID 列表。

**当前状态**：内联在 `CheckPluginVersionResource.get_host_ids()` 中。

**使用的 Resource**：
- `CheckPluginVersionResource`

**提取建议**：
- 提取为公共函数
- 与 `resolve_target_nodes` 有部分重叠，可统一

---

### 2.7 目标节点校验与格式化

#### `validate_and_normalize_target_nodes(attrs) -> list`

**描述**：校验 `target_object_type` + `target_node_type` 组合的合法性，并统一 `target_nodes` 格式。

**当前状态**：内联在 `SaveCollectConfigResource.RequestSerializer.validate()` 中。

**使用的 Resource**：
- `SaveCollectConfigResource`

**提取建议**：
- 提取为独立校验函数，可被多个 Serializer 复用

---

### 2.8 状态计算与缓存更新

#### `calculate_operation_result(error_count, total_count, pending_count, running_count) -> str`

**描述**：根据实例统计计算操作结果状态（SUCCESS/WARNING/FAILED/DEPLOYING）。

**当前状态**：内联在 `CollectConfigListResource.get_realtime_data()` 中（两处几乎相同的逻辑）。

**使用的 Resource**：
- `CollectConfigListResource`

**提取建议**：
- 提取为公共函数
- 列表 Resource 中有两处使用（NodeMan 和 K8s 分别计算）

#### `update_cache_data(config, cache_data) -> None`

**描述**：更新采集配置的缓存数据（总数、异常数），与数据库不一致时保存。

**当前状态**：内联在 `CollectConfigListResource.update_cache_data()` 和 `UpdateConfigInstanceCountResource` 中。

---

### 2.9 指标缓存更新

#### `update_metric_cache(collector_plugin) -> None`

**描述**：采集配置保存/升级后，主动更新指标缓存表。

**当前状态**：定义为 `SaveCollectConfigResource` 的静态方法。

**使用的 Resource**：
- `SaveCollectConfigResource`
- `UpgradeCollectPluginResource`

**提取建议**：
- 提取为模块级别公共函数

---

### 2.10 生成不重名名称

#### `generate_unique_name(base_name, bk_biz_id) -> str`

**描述**：生成不重名的采集配置名称（追加 `_copy`、`_copy(1)` 等）。

**当前状态**：内联在 `CloneCollectConfigResource.perform_request()` 中（两处）。

**使用的 Resource**：
- `CloneCollectConfigResource`

**提取建议**：
- 提取为公共函数

---

### 2.11 告警策略清理

#### `cleanup_alarm_strategy(collect_config, username) -> None`

**描述**：删除采集配置时清理关联的内置链路健康策略。

**当前状态**：内联在 `DeleteCollectConfigResource.perform_request()` 中。

**使用的 Resource**：
- `DeleteCollectConfigResource`

**提取建议**：
- 提取为公共函数（或保留在 SaaS 层）

---

### 2.12 无数据检测

#### `nodata_test(collect_config, target_list) -> dict[str, bool]`

**描述**：检测目标实例是否在最近 3 个采集周期内有数据上报。

**当前状态**：定义为 `CollectTargetStatusTopoResource` 的类方法。

**使用的 Resource**：
- `CollectTargetStatusTopoResource`

**提取建议**：
- 提取为独立函数
- 逻辑较复杂（日志/Trap vs 时序两条路径），可能需保留在 SaaS 层

---

## 3. 新版文件组织建议

```python
# collecting/common.py（或 collecting/helpers.py）

# 2.1 采集配置获取
def get_collect_config_or_raise(bk_biz_id, config_id, select_related=None): ...

# 2.4 密码处理
def update_password_inplace(data, config_meta): ...
def password_convert(collect_config_meta): ...

# 2.5 虚拟插件管理
def get_collector_plugin(data): ...

# 2.6 目标节点解析
def resolve_target_nodes(collect_config): ...
def resolve_host_ids_by_target(target_nodes, target_node_type, bk_biz_id): ...

# 2.7 目标节点校验
def validate_and_normalize_target_nodes(attrs): ...

# 2.8 状态计算
def calculate_operation_result(error_count, total_count, pending_count, running_count): ...

# 2.9 指标缓存
def update_metric_cache(collector_plugin): ...

# 2.10 名称生成
def generate_unique_name(base_name, bk_biz_id): ...

# 2.11 告警策略
def cleanup_alarm_strategy(collect_config, username): ...
```

## 4. 适配层分类

### 需要在 compat.py 中处理的转换

| 转换方向 | 说明 |
|---------|------|
| `CollectConfigMeta` ORM → base `CollectConfig` | 列表/详情查询时的模型映射 |
| 前端请求 dict → base `CollectSpec` / `CollectSetSpec` | 保存/编辑时的参数转换 |
| base 状态枚举 → 旧状态枚举 | `TaskStatus`、`OperationResult` 等 |
| base `MetricPlugin` → `CollectorPluginMeta` | 插件信息转换 |
| `DeploymentConfigVersion` → base `CollectSetConfig` | 部署配置转换 |

### 可直接保留在 SaaS 层的逻辑

| 逻辑 | 原因 |
|------|------|
| `ListLegacySubscription` / `CleanLegacySubscription` | 直连节点管理 DB |
| `ListLegacyStrategy` / `ListRelatedStrategy` | 策略域逻辑 |
| `EncryptPasswordResource` / `DecryptPasswordResource` | 通用工具，无需 base |
| `GetCollectVariablesResource` | 纯静态数据 |
| `DatalinkDefaultAlarmStrategyLoader` 调用 | 告警域逻辑 |
| `append_metric_list_cache` 调用 | SaaS 层缓存逻辑 |
| NoData 检测（`nodata_test`） | 依赖数据查询层 |
