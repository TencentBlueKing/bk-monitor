# bk-monitor-base metric_plugin 域能力映射分析

## 1. 核心发现

**bk-monitor-base 的 `metric_plugin` 域已经包含了完整的「采集部署」管理能力。**

在 base 的建模中，采集配置被抽象为「插件部署项」（MetricPluginDeployment），采集下发/启停/重试/终止等操作都已有对应的 operation 函数和 installer 实现。这意味着 collecting 模块的适配核心不在于「补齐能力」，而在于「建立旧模型到新模型的兼容映射」。

## 2. 概念映射

### 2.1 数据模型映射

| 旧模型（collecting/plugin） | Base 模型（metric_plugin） | 说明 |
|---|---|---|
| `CollectConfigMeta` | `MetricPluginDeployment` / `MetricPluginDeploymentModel` | 采集配置 ↔ 插件部署项 |
| `DeploymentConfigVersion` | `MetricPluginDeploymentVersion` / `MetricPluginDeploymentVersionModel` | 部署配置版本 ↔ 部署版本 |
| `CollectorPluginMeta` | `MetricPlugin` / `MetricPluginModel` | 采集插件 ↔ 指标插件 |
| `PluginVersionHistory` | `MetricPluginVersionModel` | 插件版本历史 ↔ 插件版本 |
| 旧 `BaseInstaller`（deploy/base.py） | Base `BaseInstaller`（installer/base.py） | 安装器基类 |
| 旧 `NodeManInstaller` | Base `NodemanInstaller` | 节点管理安装器 |
| 旧 `K8sInstaller` | Base `K8sInstaller` | K8s 安装器 |
| `get_collect_installer()` | `get_installer()` | 安装器工厂 |

### 2.2 字段级映射

#### CollectConfigMeta → MetricPluginDeployment

| 旧字段 | Base 字段 | 转换说明 |
|--------|----------|---------|
| `id` | `id` | 直接映射 |
| `name` | `name` | 直接映射 |
| `bk_biz_id` | `bk_biz_id` | 直接映射 |
| `bk_tenant_id` | `bk_tenant_id` | 直接映射 |
| `plugin_id` | `plugin_id` | 直接映射 |
| `collect_type` | 通过 `plugin_id` 关联 `MetricPlugin.type` | 间接获取 |
| `target_object_type` | 通过 `MetricPlugin.label` 推导 | HOST/SERVICE 来自插件标签 |
| `last_operation` | 无直接对应 | Base 只记录 `status`，不记录操作类型 |
| `operation_result` | `status` | 状态枚举需映射 |
| `cache_data` | 无直接对应 | 需在 SaaS 层维护或 base 扩展 |
| `label` / `label_info` | 无直接对应 | 可通过 `MetricPlugin.label` 获取 |
| `create_time` / `update_time` | `created_at` / `updated_at` | 字段名格式差异 |
| `create_user` / `update_user` | `created_by` / `updated_by` | 字段名格式差异 |

#### DeploymentConfigVersion → MetricPluginDeploymentVersion

| 旧字段 | Base 字段 | 转换说明 |
|--------|----------|---------|
| `config_meta_id` | `deployment_id` | 外键关联 |
| `plugin_version` | `plugin_version: VersionTuple` | 旧版是 FK，base 用 VersionTuple |
| `target_node_type` | `target_scope.node_type` | 嵌套在 scope 对象中 |
| `target_nodes` | `target_scope.nodes` | 嵌套在 scope 对象中 |
| `params` | `params` | 直接映射 |
| `remote_collecting_host` | `remote_scope` | 结构差异：旧版单主机，base 用 scope |
| `subscription_id` | `deployment.related_params["subscription_id"]` | 存储位置不同 |
| `task_ids` | `deployment.related_params["task_ids"]` | 存储位置不同 |
| `last_version` (FK) | 通过 version 排序获取上一版本 | 查询方式不同 |

### 2.3 状态枚举映射

| 旧枚举（collecting/constant.py） | Base 枚举（MetricPluginDeploymentStatusEnum） | 说明 |
|---|---|---|
| `OperationResult.PREPARING` | `INITIALIZING` | 初始化 |
| `OperationResult.DEPLOYING` | `DEPLOYING` | 部署中 |
| `OperationResult.SUCCESS` | `RUNNING` | 运行中 |
| `OperationResult.FAILED` | `FAILED` | 失败 |
| `TaskStatus.STOPPED` | `STOPPED` | 已停止 |
| `TaskStatus.STARTING` | `STARTING` | 启动中 |
| `TaskStatus.STOPPING` | `STOPPING` | 停止中 |
| `OperationResult.WARNING` | 无直接对应 | Base 无部分失败状态，需 SaaS 层计算 |
| `Status.AUTO_DEPLOYING` | 无直接对应 | 自动下发状态需 SaaS 层处理 |

## 3. Operation 函数映射

### 3.1 核心 CRUD

| 旧 Resource | Base Operation 函数 | 适配要点 |
|---|---|---|
| `SaveCollectConfigResource` | `save_and_install_metric_plugin_deployment()` | 入参转换：data → `CreateOrUpdateDeploymentParams` |
| `CollectConfigListResource` | `list_metric_plugin_deployments()` | 旧版有更复杂的过滤/排序/缓存逻辑，base 只提供基础列表 |
| `CollectConfigDetailResource` | `get_metric_plugin_deployment()` | 返回 `(deployment, version)`，需组装为旧格式 |
| `DeleteCollectConfigResource` | `delete_metric_plugin_deployment()` | Base 要求先 stop 再 delete |
| `RenameCollectConfigResource` | 直接更新 `MetricPluginDeploymentModel.name` | base 无专门 rename API |

### 3.2 启停操作

| 旧 Resource | Base Operation 函数 | 适配要点 |
|---|---|---|
| `ToggleCollectConfigStatusResource(enable)` | `start_metric_plugin_deployment()` | 状态校验不同：base 要求 STOPPED → STARTING |
| `ToggleCollectConfigStatusResource(disable)` | `stop_metric_plugin_deployment()` | 状态校验不同：base 要求 RUNNING → STOPPING |

### 3.3 部署操作

| 旧 Resource | Base Operation 函数 | 适配要点 |
|---|---|---|
| `RetryTargetNodesResource` | `retry_metric_plugin_deployment()` | 入参差异：旧版 `instance_id`，base 用 `RetryDeployPluginParams.instance_scope` |
| `BatchRetryConfigResource` | `retry_metric_plugin_deployment()` | scope=None 表示重试全部 |
| `RevokeTargetNodesResource` | Base `installer.revoke(scope)` | 需通过 installer 调用 |
| `BatchRevokeTargetNodesResource` | Base `installer.revoke()` | scope=None 终止全部 |
| `RunCollectConfigResource` | Base `installer.run(action, scope)` | 参数结构需适配 |
| `UpgradeCollectPluginResource` | `save_and_install_metric_plugin_deployment()` | 升级 = 用新版本重新安装 |
| `RollbackDeploymentConfigResource` | **无直接对应** | 需通过获取上一版本参数重新 install |

### 3.4 状态查询

| 旧 Resource | Base Operation 函数 | 适配要点 |
|---|---|---|
| `CollectTargetStatusResource` | `get_metric_plugin_deployment_status()` | 返回格式需兼容 |
| `CollectRunningStatusResource` | `get_metric_plugin_deployment_status()` | diff=False 场景 |
| `CollectInstanceStatusResource` | `get_metric_plugin_deployment_status()` | diff=False 场景 |
| `GetCollectLogDetailResource` | `get_nodeman_collect_log_detail()` | 已有直接对应 |
| `GetMetricsResource` | `get_metric_plugin()` → `plugin.metrics` | 通过插件获取指标 |

### 3.5 工具类

| 旧 Resource | Base Operation 函数 | 适配要点 |
|---|---|---|
| `GetTrapCollectorPluginResource` | `create_metric_plugin()` | 虚拟插件创建走 base |
| `IsTaskReady` | `check_subscription_task_ready()` | nodeman API 已封装 |
| `CheckPluginVersionResource` | 无直接对应 | 保留 SaaS 层 |
| `EncryptPasswordResource` | 无直接对应 | 保留 SaaS 层 |
| 遗留订阅类 | 无直接对应 | 保留 SaaS 层 |

## 4. 安装器映射

### Base `BaseInstaller` 抽象方法

| 方法 | 旧安装器对应 | 说明 |
|------|------------|------|
| `install(deployment_version)` | `install(data, operation)` | 参数结构不同 |
| `uninstall()` | `uninstall()` | 一致 |
| `stop()` | `stop()` | 一致 |
| `start()` | `start()` | 一致 |
| `run(action, scope)` | `run(action, scope)` | scope 类型不同 |
| `retry(scope)` | `retry(instance_ids)` | 参数类型不同 |
| `revoke(scope)` | `revoke(instance_ids)` | 参数类型不同 |
| `status(diff)` | `status(diff)` | ✅ Base 已支持 diff 参数，返回旧版兼容格式 |
| - | `rollback()` | **Base 无 rollback** |
| - | `upgrade(params)` | **Base 通过 install 实现升级** |
| - | `instance_status(instance_id)` | NodemanInstaller 上有 |

### 关键差异

1. **Base 统一了 install 和 upgrade**：旧版分两个方法，base 统一通过 `install(new_deployment_version)` 实现
2. **Base 无 rollback**：回滚需在 SaaS 层通过「获取上一版本 → 重新 install」实现
3. ~~**Base 无 diff 模式的 status**~~（✅ 已解决）：Base `NodemanInstaller.status(diff=True/False)` 已完整实现旧版 diff 语义，包括 ADD/REMOVE/UPDATE/RETRY 节点分类
4. **scope 替代 instance_ids**：Base 用 `MetricPluginDeploymentScope(node_type, nodes)` 替代 `list[str]`
5. **version_diff 内置**：Base `BaseInstaller.get_version_diff()` 提供了版本差异比对
6. **Base 新增 SQLInstaller / JobInstaller**：旧版没有 Job 类安装器，base 扩展了 SQL 类插件支持
7. **status() 返回值格式**：Base `NodemanInstaller.status(diff)` 返回旧版兼容的树状结构，包含 `node_path`/`label_name`/`is_label` 等旧版字段，支持拓扑/动态分组/模板/主机实例的分组
8. **instance_status() 在 NodemanInstaller 上**：Base 在 NodemanInstaller 上有 `instance_status(instance_id)` → 返回日志详情

## 4.5 status() 实现对比（✅ 已对齐）

> ✅ **Base `NodemanInstaller.status(diff)` 已完整实现旧版兼容的 status 语义，
> 包括 diff 模式、实例状态转换、节点分组等。SaaS 层 Resource 可直接调用。**

### 4.5.1 diff 模式（✅ 已支持）

Base `NodemanInstaller.status(diff=True/False)` 已实现完整的 diff 语义：

- **`diff=True`（默认）**：调用 `_get_previous_deployment_version()` 获取上一版本，
  通过 `_get_legacy_node_diff()` 按旧版 `show_diff` 规则将节点分为 ADD/REMOVE/UPDATE/RETRY 四类。
- **`diff=False`**：不做差异比对，展示当前全量节点状态。

### 4.5.2 返回结构（✅ 已兼容）

Base 的 `_build_legacy_status_groups()` 已按旧版格式构造返回值：

#### TOPO 场景

```python
[
    {
        "child": [...实例列表...],
        "node_path": "蓝鲸/公共组件/kafka",  # ✅ 使用 node_path 字段名
        "label_name": "ADD",                  # ✅ 差异类型
        "is_label": True,                     # ✅ 差异标签开关
    },
]
```

#### HOST 场景

```python
[
    {
        "child": [...所有 ADD 的主机实例...],
        "node_path": "主机",
        "label_name": "ADD",
        "is_label": True,
    },
]
```

#### DYNAMIC_GROUP 场景

```python
[
    {
        "child": [...实例列表...],
        "node_path": "动态分组",
        "label_name": "ADD",
        "is_label": True,
        "dynamic_group_name": "分组名称",     # ✅ 动态分组名
        "dynamic_group_id": "XXXXXXXX",       # ✅ 动态分组ID
    },
]
```

### 4.5.3 实例级（child[]）字段（✅ 已兼容）

Base `_process_instance_result()` 已返回旧版兼容的实例字段：

| 字段 | 旧版 | Base | 状态 |
|------|------|------|------|
| `instance_id` | ✅ | ✅ | ✅ 一致 |
| `ip` | ✅ | ✅ | ✅ 一致 |
| `bk_host_id` | ✅ | ✅ | ✅ 一致 |
| `bk_host_name` | ✅ | ✅ | ✅ 一致 |
| `bk_cloud_id` | ✅ | ✅ | ✅ 一致 |
| `bk_supplier_id` | ✅ | ✅ | ✅ 一致 |
| `task_id` | ✅ | ✅ | ✅ Base 已返回 |
| `plugin_version` | ✅ | ✅ | ✅ Base 已返回 |
| `status` | ✅ | ✅ | ✅ Base 已做 STARTING/STOPPING 转换 |
| `log` | ✅ 阶段名 | ✅ 阶段名 | ✅ `_get_instance_failed_stage_log()` 格式一致 |
| `action` | ✅ | ✅ | ✅ 一致 |
| `steps` | ✅ | ✅ | ✅ 一致 |
| `instance_name` | ✅ | ✅ | ✅ 一致 |
| `scope_ids` | ✅ | ✅ | ✅ Base 使用 `scope_ids`，`_build_status_output_instance()` 移除 |
| `service_instance_id` | ✅ | ✅ | ✅ 一致 |
| `bk_module_id` / `bk_module_ids` | ✅ | ✅ | ✅ 一致 |

### 4.5.4 状态转换逻辑（✅ 已兼容）

Base `_convert_legacy_instance_status()` 已实现旧版语义：

```python
def _convert_legacy_instance_status(status: str, deployment_status: str) -> str:
    if status in [CollectStatus.RUNNING.value, CollectStatus.PENDING.value]:
        if deployment_status == MetricPluginDeploymentStatusEnum.STARTING.value:
            return "STARTING"
        if deployment_status == MetricPluginDeploymentStatusEnum.STOPPING.value:
            return "STOPPING"
    return status
```

同时 `_update_deployment_status_from_task_results()` 在方法末尾根据所有实例状态
更新 deployment 整体状态（RUNNING/STOPPED/FAILED/DEPLOYING）。

### 4.5.5 diff 节点比对逻辑（✅ 已兼容）

Base `_get_legacy_node_diff()` 按旧版 `show_diff` 规则计算差异：

1. 无上一版本 → 所有节点为 ADD
2. 插件版本变化 → 所有旧节点为 UPDATE
3. 节点类型变化 → 当前为 ADD，旧版为 REMOVE
4. 节点类型相同 → 逐节点对比：
   - 新增节点 → ADD
   - 参数/远程范围变化 → UPDATE
   - 无变化 → RETRY
   - 剩余旧节点 → REMOVE

### 4.5.6 适配影响评估（更新后）

| 影响范围 | 严重程度 | 说明 |
|---------|---------|------|
| `CollectTargetStatusResource`（diff=True） | 🟢 低 | ✅ Base 已完整支持 diff，直接调用 |
| `CollectRunningStatusResource`（diff=False） | 🟢 低 | ✅ Base 返回格式已兼容 |
| `CollectInstanceStatusResource`（diff=False） | 🟢 低 | ✅ Base 返回格式已兼容 |
| `CollectTargetStatusTopoResource` | 🟢 低 | ✅ 消费 status(diff=False) 的结果，格式已兼容 |
| `UpdateConfigInstanceCountResource` | 🟢 低 | 仅统计 error/total，与分组结构无关 |
| 前端 `FrontendTargetStatusTopoResource` | 🟢 低 | ✅ 间接依赖的 status 格式已兼容 |

### 4.5.7 SaaS Resource 层改造方案

Base 已在 installer 层完成了所有兼容工作，SaaS 的 status Resource 改造非常简洁：

```python
class CollectTargetStatusResource(Resource):
    def perform_request(self, params):
        bk_tenant_id = get_request_tenant_id()
        deployment, version = get_metric_plugin_deployment(
            bk_tenant_id=bk_tenant_id,
            deployment_id=params["id"],
            bk_biz_id=params["bk_biz_id"],
        )
        installer = get_installer(deployment, operator="")
        return {
            "config_info": _build_config_info(deployment, version),
            "contents": installer.status(diff=params["diff"]),
        }
```

其中 `config_info` 需要从 deployment + version 构建旧版 `collect_config.get_info()` 格式。

`operation.py` 的 `get_metric_plugin_deployment_status()` 当前未传递 diff 参数，
新版 Resource 应直接使用 `get_installer()` + `installer.status(diff=...)` 调用链。

## 5. 入参转换设计（compat 层核心）

### 5.1 SaveCollectConfig → CreateOrUpdateDeploymentParams

```python
# 旧请求数据
old_data = {
    "id": 123,                          # → params.id
    "name": "my_collect",               # → params.name
    "bk_biz_id": 2,                     # → bk_biz_id
    "plugin_id": "my_plugin",           # → params.plugin_id
    "target_node_type": "TOPO",         # → params.target_scope.node_type
    "target_nodes": [...],              # → params.target_scope.nodes
    "params": {"collector": {}, "plugin": {}},  # → params.params
    "remote_collecting_host": {...},    # → params.remote_scope
}

# Base 参数
base_params = CreateOrUpdateDeploymentParams(
    id=old_data.get("id"),
    name=old_data["name"],
    plugin_id=old_data["plugin_id"],
    plugin_version=VersionTuple(major=..., minor=...),  # 需从插件当前版本获取
    target_scope=MetricPluginDeploymentScope(
        node_type=old_data["target_node_type"],
        nodes=old_data["target_nodes"],
    ),
    remote_scope=convert_remote_host_to_scope(old_data.get("remote_collecting_host")),
    params=old_data["params"],
)
```

### 5.2 出参转换：MetricPluginDeployment → 旧 CollectConfig 格式

```python
def convert_deployment_to_legacy(
    deployment: MetricPluginDeployment,
    version: MetricPluginDeploymentVersion,
    plugin: MetricPlugin,
) -> dict:
    return {
        "id": deployment.id,
        "deployment_id": deployment.id,   # 旧版有单独的 deployment_config_id
        "name": deployment.name,
        "bk_biz_id": deployment.bk_biz_id,
        "collect_type": plugin.type,
        "plugin_id": deployment.plugin_id,
        "target_object_type": label_to_object_type(plugin.label),
        "target_node_type": version.target_scope.node_type,
        "target_nodes": version.target_scope.nodes,
        "params": version.params,
        "remote_collecting_host": convert_scope_to_remote_host(version.remote_scope),
        "plugin_info": convert_plugin_to_legacy_info(plugin),
        "subscription_id": deployment.related_params.get("subscription_id", 0),
        "label": plugin.label,
        "label_info": {...},
        "create_time": deployment.created_at,
        "create_user": deployment.created_by,
        "update_time": deployment.updated_at,
        "update_user": deployment.updated_by,
    }
```

### 5.3 列表出参补充

旧版 `CollectConfigListResource` 返回的列表项包含一些 Base 不直接提供的字段，需在 SaaS 层补充：

| 字段 | 补充方式 |
|------|---------|
| `space_name` | 调 SpaceApi |
| `status` / `task_status` | 从 `deployment.status` 映射 |
| `need_upgrade` | 比较 deployment.plugin_version 与 plugin 最新 release_version |
| `config_version` / `info_version` | 从 plugin_version 拆解 |
| `error_instance_count` / `total_instance_count` | 调 `get_metric_plugin_deployment_status()` 或缓存 |
| `running_tasks` | 从 `related_params` 获取 |

## 6. 需在 SaaS 层补充的逻辑

### 6.1 无法由 Base 直接满足的能力

| 能力 | 原因 | 解决方案 |
|------|------|---------|
| `cache_data` 缓存机制 | Base 无此概念 | 在 SaaS 层维护缓存表或字段 |
| `allow_rollback` 计算 | Base 无回滚概念 | SaaS 层根据版本历史判断 |
| Rollback 操作 | Base 无 rollback 方法 | SaaS 层获取上一版本参数，调 `save_and_install` |
| 空间/业务权限过滤 | Base 未集成 Space | SaaS 层做过滤 |
| 告警策略清理 | monitoring 域耦合 | 保留 SaaS 层 |
| NoData 检测 | 数据查询层耦合 | 保留 SaaS 层 |
| 指标缓存刷新 | SaaS 异步任务 | 保留 SaaS 层 |
| 遗留订阅管理 | 运维工具 | 保留 SaaS 层 |

### 6.2 虚拟插件处理

旧版 `SaveCollectConfigResource.get_collector_plugin()` 针对 LOG/PROCESS/SNMP_TRAP/K8S 类型创建虚拟插件。适配时需要：

1. **LOG 类型**：使用 base `create_metric_plugin()` + 对应 manager
2. **PROCESS 类型**：使用 base `create_metric_plugin()` 替代 `PluginManagerFactory`
3. **SNMP_TRAP 类型**：base 已有 `SNMPTrapPluginManager`
4. **K8S 类型**：base 已有 `K8sInstaller`

## 7. 修订后的适配复杂度评估

Base 已有完整的部署管理能力，大部分 CRUD/操作类 Resource 复杂度大幅降低。
**status 类 Resource 已从高复杂度降为低复杂度**——Base `NodemanInstaller.status(diff)` 已完整实现
旧版兼容格式，SaaS 层只需简单调用转发。

| Resource | 原评估 | 修订评估 | 修订原因 |
|----------|--------|---------|---------|
| SaveCollectConfigResource | 🔴 高 | 🟡 中 | 核心是入参转换 + 虚拟插件处理 |
| CollectConfigListResource | 🔴 高 | 🟡 中 | 基础列表 base 已有，缓存/状态补充在 SaaS 层 |
| CollectConfigDetailResource | 🟡 中 | 🟢 低 | `get_metric_plugin_deployment()` 直接可用 |
| ToggleCollectConfigStatusResource | 🟡 中 | 🟢 低 | `start/stop_metric_plugin_deployment()` 直接可用 |
| DeleteCollectConfigResource | 🟡 中 | 🟢 低 | `delete_metric_plugin_deployment()` 直接可用 |
| RetryTargetNodesResource | 🟢 低 | 🟢 低 | `retry_metric_plugin_deployment()` 直接可用 |
| **CollectTargetStatusResource** | 🟡 中 | **🟢 低** | ✅ Base `installer.status(diff)` 已完整实现旧版兼容格式 |
| CollectRunningStatusResource | 🟢 低 | **🟢 低** | ✅ Base 返回格式已兼容 |
| CollectInstanceStatusResource | 🟢 低 | **🟢 低** | ✅ Base 返回格式已兼容 |
| GetCollectLogDetailResource | 🟢 低 | 🟢 低 | `get_nodeman_collect_log_detail()` 直接可用 |
| RollbackDeploymentConfigResource | 🟡 中 | 🟡 中 | 需 SaaS 层模拟（获取上一版本重新 install） |
| CollectTargetStatusTopoResource | 🔴 高 | **🟢 低** | ✅ 消费 status(diff=False) 结果，格式已兼容 + SaaS NoData 检测 |
| UpgradeCollectPluginResource | 🟡 中 | 🟢 低 | 通过 `save_and_install` 用新版本重新安装 |
