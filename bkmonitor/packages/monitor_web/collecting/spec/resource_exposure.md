# Collecting Resource 暴露渠道与调用分析

## 概述

本文档分析每个 Resource 的暴露渠道，分三类：
1. **ViewSet HTTP API**（前端直接调用）
2. **kernel_api**（对外/跨系统暴露的接口）
3. **内部调用**（`resource.collecting.xxx()` 或直接类引用）

## 1. 暴露渠道总览

### 1.1 前端 HTTP API — `CollectingConfigViewSet`

通过 `monitor_web/collecting/views.py` 的 `CollectingConfigViewSet` 注册，路由前缀由
`monitor_web/collecting/urls.py` 的 `ResourceRouter` 决定。所有接口都受 IAM 权限管控
（读操作 = `VIEW_COLLECTION`，写操作 = `MANAGE_COLLECTION`）。

### 1.2 kernel_api — 对外接口

存在两个版本的暴露通道：

| 版本 | 文件 | 暴露方式 | 说明 |
|------|------|---------|------|
| **v3** | `kernel_api/views/v3/models.py` | 仅注册 `CollectConfigInfoResource` | 路径: `api/v3/models/collect_config/` |
| **v4** | `kernel_api/views/v4/collect.py` | 继承 `CollectingConfigViewSet` **全部路由** | 路径: `api/v4/collecting_config/*` |

- `kernel_api/resource/collecting.py` 通过 `from monitor_web.collecting.resources import *` 导出所有 Resource 类。
- v4 的 `CollectViewSet(CollectingConfigViewSet)` 直接继承前端 ViewSet，意味着前端所有接口在 v4 都有对外暴露。

### 1.3 内部调用

主要通过 `resource.collecting.<method_name>()` 调用链：
- 模块自身内部互调
- 跨模块调用（`plugin`、`export_import`、`datalink`、`strategies`、`statistics`、`models`、`commons`）

---

## 2. 每个 Resource 的完整渠道分析

### 2.1 backend.py

| # | Resource | ViewSet 端点 | kernel_api | 内部调用 |
|---|---------|-------------|------------|---------|
| 1 | `CollectConfigListResource` | ✅ POST `config_list` | ✅ v4（继承） | ✅ 被以下调用：<br>• `UpgradeCollectPluginResource`：刷新缓存<br>• `commons/biz/func_control.py`：`.exists_by_biz()` 检查业务是否有采集配置 |
| 2 | `CollectConfigDetailResource` | ✅ GET `config_detail` | ✅ v4（继承） | ✅ 被以下调用：<br>• `CloneCollectConfigResource`：克隆前获取详情<br>• `FrontendCollectConfigDetailResource`：底层详情<br>• `FrontendCollectConfigTargetInfoResource`：底层详情<br>• `plugin/resources/old.py`：`PluginCollectorSeparateResource` 获取采集配置<br>• `plugin/resources/new.py`：同上 |
| 3 | `RenameCollectConfigResource` | ✅ POST `rename` | ✅ v4（继承） | ❌ 无内部调用 |
| 4 | `ToggleCollectConfigStatusResource` | ✅ POST `toggle` | ✅ v4（继承） | ❌ 无内部调用 |
| 5 | `DeleteCollectConfigResource` | ✅ POST `delete` | ✅ v4（继承） | ❌ 无内部调用 |
| 6 | `CloneCollectConfigResource` | ✅ POST `clone` | ✅ v4（继承） | ❌ 无内部调用 |
| 7 | `RetryTargetNodesResource` | ✅ POST `retry` | ✅ v4（继承） | ❌ 无内部调用 |
| 8 | `RevokeTargetNodesResource` | ✅ POST `revoke` | ✅ v4（继承） | ❌ 无内部调用 |
| 9 | `RunCollectConfigResource` | ✅ POST `run` | ✅ v4（继承） | ❌ 无内部调用 |
| 10 | `BatchRevokeTargetNodesResource` | ✅ POST `batch_revoke` | ✅ v4（继承） | ❌ 无内部调用 |
| 11 | `GetCollectLogDetailResource` | ✅ GET `get_collect_log_detail` | ✅ v4（继承） | ❌ 无内部调用 |
| 12 | `BatchRetryConfigResource` | ✅ POST `batch_retry` | ✅ v4（继承） | ❌ 无内部调用 |
| 13 | `SaveCollectConfigResource` | ✅ POST `save` | ✅ v4（继承） | ✅ 被以下调用：<br>• `CloneCollectConfigResource`：日志/SNMP Trap 类型克隆<br>• `export_import/resources.py`：导入配置批量调用<br>• `export_import/import_config.py`：导入采集配置 |
| 14 | `UpgradeCollectPluginResource` | ✅ POST `upgrade` | ✅ v4（继承） | ❌ 无内部调用 |
| 15 | `RollbackDeploymentConfigResource` | ✅ POST `rollback` | ✅ v4（继承） | ❌ 无内部调用 |
| 16 | `GetMetricsResource` | ✅ GET `metrics` | ✅ v4（继承） | ❌ 无内部调用 |
| 17 | `CollectConfigInfoResource` | ❌ 无前端端点 | ✅ **v3** 专用端点 + v4（继承） | ❌ 无内部调用 |
| 18 | `BatchRetryResource` | ✅ POST `batch_retry_detailed` | ✅ v4（继承） | ❌ 无内部调用 |

### 2.2 frontend.py

| # | Resource | ViewSet 端点 | kernel_api | 内部调用 |
|---|---------|-------------|------------|---------|
| 19 | `FrontendCollectConfigDetailResource` | ✅ GET `frontend_config_detail` | ✅ v4（继承） | ❌ 无跨模块调用<br>**模块内依赖**：`collect_config_detail`、`frontend_collect_config_target_info` |
| 20 | `FrontendCollectConfigTargetInfoResource` | ✅ GET `frontend_target_info` | ✅ v4（继承） | ❌ 无跨模块调用<br>**模块内依赖**：`collect_config_detail` |
| 21 | `FrontendTargetStatusTopoResource` | ✅ POST `target_status_topo` | ✅ v4（继承） | ❌ 无跨模块调用<br>**模块内依赖**：`collect_target_status_topo` |
| 22 | `DeploymentConfigDiffResource` | ✅ GET `deployment_diff` | ✅ v4（继承） | ❌ 无内部调用 |
| 23 | `GetCollectVariablesResource` | ✅ GET `get_collect_variables` | ✅ v4（继承） | ❌ 无内部调用 |

### 2.3 status.py

| # | Resource | ViewSet 端点 | kernel_api | 内部调用 |
|---|---------|-------------|------------|---------|
| 24 | `CollectTargetStatusResource` | ✅ GET `status` | ✅ v4（继承） | ❌ 无跨模块调用 |
| 25 | `CollectRunningStatusResource` | ✅ GET `running_status` | ✅ v4（继承） | ❌ 无跨模块调用 |
| 26 | `CollectInstanceStatusResource` | ✅ GET `collect_instance_status` | ✅ v4（继承） | ✅ 被 `datalink/resources.py` 调用：<br>获取采集实例状态用于 datalink 策略详情展示 |
| 27 | `CollectTargetStatusTopoResource` | ❌ 无直接端点 | ❌ | ✅ 仅被 `FrontendTargetStatusTopoResource` 内部调用 |
| 28 | `UpdateConfigInstanceCountResource` | ❌ 无直接端点 | ❌ | ⚠️ 已注册为 Resource 但**未找到实际调用者**<br>可能由 Celery 定时任务通过 `resource.collecting.update_config_instance_count()` 调用（需确认） |

### 2.4 toolkit.py

| # | Resource | ViewSet 端点 | kernel_api | 内部调用 |
|---|---------|-------------|------------|---------|
| 29 | `ListLegacySubscriptionResource` | ✅ GET `list_legacy_subscription` | ✅ v4（继承） | ✅ 被 `statistics/v2/collect_config.py` 调用：<br>遗留订阅统计 |
| 30 | `CleanLegacySubscriptionResource` | ✅ GET `clean_legacy_subscription` | ✅ v4（继承） | ❌ 无内部调用 |
| 31 | `ListLegacyStrategyResource` | ✅ GET `list_legacy_strategy` | ✅ v4（继承） | ✅ 被 `strategies/resources/v1.py` 调用：<br>获取失效策略列表 |
| 32 | `ListRelatedStrategyResource` | ✅ POST `list_related_strategy` | ✅ v4（继承） | ❌ 无内部调用 |
| 33 | `IsTaskReadyResource` | ✅ POST `is_task_ready` | ✅ v4（继承） | ✅ 被 `models/collecting.py` 调用：<br>`CollectConfigMeta.check_task_is_ready()` |
| 34 | `EncryptPasswordResource` | ❌ 无前端端点 | ❌ | ✅ 被 `plugin/manager/exporter.py` 调用（2处）：<br>插件参数加密 |
| 35 | `DecryptPasswordResource` | ❌ 无前端端点 | ❌ | ❌ 已定义但**未找到实际调用者** |
| 36 | `CheckAdjectiveCollectResource` | ✅ GET `check_adjective_collect` | ✅ v4（继承） | ❌ 无内部调用 |
| 37 | `FetchCollectConfigStatResource` | ✅ GET `fetch_collect_config_stat` | ✅ v4（继承） | ❌ 无内部调用 |
| 38 | `CheckPluginVersionResource` | ✅ POST `check_plugin_version` | ✅ v4（继承） | ❌ 无内部调用 |

### 2.5 snmp_trap.py

| # | Resource | ViewSet 端点 | kernel_api | 内部调用 |
|---|---------|-------------|------------|---------|
| 39 | `GetTrapCollectorPluginResource` | ❌ 无前端端点 | ❌ | ✅ 仅被 `SaveCollectConfigResource` 调用：<br>SNMP Trap 类型时获取/创建虚拟插件 |

---

## 3. 按渠道分类汇总

### 3.1 仅内部使用（无 HTTP 端点）

以下 Resource 未注册到任何 ViewSet，仅通过 `resource.collecting.xxx()` 在代码内部使用：

| Resource | 实际调用者 | 适配影响 |
|----------|-----------|---------|
| `CollectTargetStatusTopoResource` | `FrontendTargetStatusTopoResource` | 随 frontend 一起迁移 |
| `UpdateConfigInstanceCountResource` | ⚠️ 未找到调用者（可能是定时任务） | 需确认是否仍在使用 |
| `EncryptPasswordResource` | `plugin/manager/exporter.py` | 跨模块依赖，需保持接口稳定 |
| `DecryptPasswordResource` | ⚠️ 未找到调用者 | 可能是预留接口 |
| `GetTrapCollectorPluginResource` | `SaveCollectConfigResource` | 随 Save 一起迁移 |
| `CollectConfigInfoResource` | 无内部代码调用，仅 kernel_api v3 注册 | 见 kernel_api 部分 |

### 3.2 kernel_api v3 专用

| Resource | 路径 | 说明 |
|----------|------|------|
| `CollectConfigInfoResource` | `api/v3/models/collect_config/` | 唯一一个 v3 专用接口，提供采集配置原始数据 |

### 3.3 kernel_api v4（全量继承）

`kernel_api/views/v4/collect.py` 的 `CollectViewSet` 直接继承 `CollectingConfigViewSet`，
因此 ViewSet 中注册的**全部 33 个端点**均在 v4 对外暴露。

⚠️ **适配注意事项**：v4 的对外接口和前端接口共享同一个 ViewSet 类，适配时需确保新老 Resource 的
入参/出参完全兼容，否则会同时影响前端和对外 API。

### 3.4 跨模块依赖汇总

被其他模块通过 `resource.collecting.xxx()` 调用的 Resource：

| Resource | 调用方模块 | 调用场景 |
|----------|-----------|---------|
| `collect_config_detail` | `plugin` (old.py + new.py) | 获取采集配置详情 |
| `collect_config_list` | `commons/biz/func_control.py` | `.exists_by_biz()` 判断业务有无采集配置 |
| `save_collect_config` | `export_import` (resources.py + import_config.py) | 配置导入 |
| `collect_instance_status` | `datalink/resources.py` | 获取实例状态用于策略详情 |
| `encrypt_password` | `plugin/manager/exporter.py` | 插件参数加密（2处） |
| `list_legacy_subscription` | `statistics/v2/collect_config.py` | 遗留订阅统计 |
| `list_legacy_strategy` | `strategies/resources/v1.py` | 获取失效策略 |
| `is_task_ready` | `models/collecting.py` | 检查任务就绪状态 |

---

## 4. 适配策略建议

### 4.1 对外接口兼容性（最高优先级）

由于 kernel_api v4 完整继承了 `CollectingConfigViewSet`，**新老 Resource 的出参格式必须完全一致**，
不能因切换到 base 而改变返回结构。这是 compat 层设计的核心约束。

### 4.2 跨模块调用兼容性

上述 8 个跨模块依赖点，在适配时需要特别注意：
- **入参格式不变**：调用方不需要修改任何代码
- **出参格式不变**：返回值结构必须兼容
- `save_collect_config` 被 `export_import` 调用时传入的参数格式需要在 compat 层正确转换

### 4.3 纯内部 Resource

`CollectTargetStatusTopoResource`、`GetTrapCollectorPluginResource` 等纯内部 Resource，
可以在适配时调整内部数据流，只要上层消费者（如 `FrontendTargetStatusTopoResource`、
`SaveCollectConfigResource`）的行为不变即可。

### 4.4 需确认的 Resource

- `UpdateConfigInstanceCountResource`：需确认是否有 Celery 定时任务调用
- `DecryptPasswordResource`：未找到调用者，可能是预留接口或已废弃
