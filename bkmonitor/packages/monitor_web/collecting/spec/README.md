# Collecting 模块 bk-monitor-base 适配规划

## 1. 背景

plugin 模块已完成 bk-monitor-base 适配，采用环境变量开关 `ENABLE_BK_MONITOR_BASE_PLUGIN` 实现新老逻辑二选一。
现在需要对 collecting（采集配置）模块进行同样的适配，保证新老 Resource 完全兼容，实现平滑迁移。

## 2. 适配策略（参考 plugin 模块）

### 2.1 开关机制

- 使用环境变量 `ENABLE_BK_MONITOR_BASE_COLLECTING` 控制新老逻辑切换
- `resources/__init__.py` 中根据开关 import `resources/old.py`（当前逻辑）或 `resources/new.py`（base 适配）
- 同理 `views/__init__.py` 也需支持新老两套 ViewSet

### 2.2 分层架构

```
collecting/
├── resources/
│   ├── __init__.py          # 环境变量开关
│   ├── old/                 # 当前所有 Resource（重命名迁移）
│   │   ├── backend.py
│   │   ├── frontend.py
│   │   ├── status.py
│   │   ├── toolkit.py
│   │   └── snmp_trap.py
│   └── new/                 # 适配 bk-monitor-base 的新 Resource
│       ├── backend.py
│       ├── frontend.py
│       ├── status.py
│       ├── toolkit.py
│       └── snmp_trap.py
├── compat.py                # 新老数据结构转换层
├── deploy/                  # 部署安装器（可能需要双轨）
└── spec/                    # 本规划目录
```

### 2.3 兼容层（compat）

参考 `plugin/compat.py`，需要建立 collecting 的兼容转换层：
- `CollectConfigMeta` ORM ↔ `bk_monitor_base.collector.CollectConfig` 声明式模型
- `DeploymentConfigVersion` ORM ↔ `CollectSetConfig` / `CollectSpec`
- 旧枚举常量 ↔ base 枚举常量（`OperationType`、`TaskStatus` 等）

## 3. bk-monitor-base 现有能力分析

> **关键发现：`metric_plugin` 域已包含完整的「采集部署」管理能力。**
> 详见 [base_capability_mapping.md](./base_capability_mapping.md)

### 3.1 已有能力（metric_plugin 域）

| 能力 | 位置 | 对应旧模块 |
|------|------|-----------|
| **插件部署项 CRUD** | `operation.py` | `SaveCollectConfig` / `CollectConfigList` / `CollectConfigDetail` / `Delete` |
| **部署项启停** | `start/stop_metric_plugin_deployment()` | `ToggleCollectConfigStatus` |
| **部署项重试** | `retry_metric_plugin_deployment()` | `RetryTargetNodes` / `BatchRetryConfig` |
| **部署项状态查询** | `get_metric_plugin_deployment_status()` | `CollectTargetStatus` |
| **采集日志详情** | `get_nodeman_collect_log_detail()` | `GetCollectLogDetail` |
| **安装器体系** | `installer/` (Nodeman/K8s/Job/SQL) | `deploy/` (NodeMan/K8s) |
| **版本差异比对** | `BaseInstaller.get_version_diff()` | `DeploymentConfigVersion.show_diff()` |
| **插件 CRUD** | `create/get/list/delete_metric_plugin()` | `CollectorPluginMeta` ORM 操作 |
| **虚拟插件** | `SNMPTrapPluginManager` 等 | `PluginManagerFactory` |
| **节点管理 API 封装** | `infras.third_party_api.nodeman` | `core.drf_resource.api.node_man` |

### 3.2 需在 SaaS 层补充的能力

| 能力 | 说明 | 风险等级 |
|------|------|---------|
| **cache_data 缓存机制** | Base 无此概念，旧版用 JSON 字段缓存状态/实例统计 | 🟡 中 |
| **Rollback 回滚** | Base 无 rollback 方法，需 SaaS 层模拟（取上一版本重新 install） | 🟡 中 |
| **空间/业务权限过滤** | 旧版列表接口复杂的 Space + DataSource 过滤逻辑 | 🟡 中 |
| **告警策略清理** | `DatalinkDefaultAlarmStrategyLoader` 集成 | 🟡 中（保留 SaaS 层） |
| **NoData 检测** | 数据查询层耦合 | 🟡 中（保留 SaaS 层） |
| **指标缓存刷新** | `append_metric_list_cache` 异步任务 | 🟢 低（保留 SaaS 层） |
| **密码加解密** | RSA 加解密 | 🟢 低（保留 SaaS 层） |
| **遗留订阅管理** | 直连节点管理 DB | 🟢 低（保留 SaaS 层） |

## 4. Resource 全景清单

### 4.1 backend.py（核心 CRUD + 部署操作）

> 暴露渠道标记：🌐 ViewSet前端 | 🔗 kernel_api v4 | 📡 kernel_api v3 | 🔧 内部调用 | 详见 [resource_exposure.md](./resource_exposure.md)

| # | Resource | HTTP 端点 | 暴露渠道 | 适配复杂度 | Base 对应 |
|---|---------|----------|---------|-----------|----------|
| 1 | CollectConfigListResource | POST config_list | 🌐🔗🔧 | 🟡 中 | `list_metric_plugin_deployments()` + SaaS 过滤/缓存 |
| 2 | CollectConfigDetailResource | GET config_detail | 🌐🔗🔧 | 🟢 低 | `get_metric_plugin_deployment()` + 出参转换 |
| 3 | RenameCollectConfigResource | POST rename | 🌐🔗 | 🟢 低 | 直接更新 `MetricPluginDeploymentModel.name` |
| 4 | ToggleCollectConfigStatusResource | POST toggle | 🌐🔗 | 🟢 低 | `start/stop_metric_plugin_deployment()` |
| 5 | DeleteCollectConfigResource | POST delete | 🌐🔗 | 🟢 低 | `delete_metric_plugin_deployment()` + SaaS 告警清理 |
| 6 | CloneCollectConfigResource | POST clone | 🌐🔗 | 🟡 中 | `get` → `save_and_install` 组合 |
| 7 | RetryTargetNodesResource | POST retry | 🌐🔗 | 🟢 低 | `retry_metric_plugin_deployment()` |
| 8 | RevokeTargetNodesResource | POST revoke | 🌐🔗 | 🟢 低 | `installer.revoke(scope)` |
| 9 | RunCollectConfigResource | POST run | 🌐🔗 | 🟢 低 | `installer.run(action, scope)` |
| 10 | BatchRevokeTargetNodesResource | POST batch_revoke | 🌐🔗 | 🟢 低 | `installer.revoke()` |
| 11 | GetCollectLogDetailResource | GET get_collect_log_detail | 🌐🔗 | 🟢 低 | `get_nodeman_collect_log_detail()` |
| 12 | BatchRetryConfigResource | POST batch_retry | 🌐🔗 | 🟢 低 | `retry_metric_plugin_deployment(scope=None)` |
| 13 | SaveCollectConfigResource | POST save | 🌐🔗🔧 | 🟡 中 | `save_and_install_metric_plugin_deployment()` + compat |
| 14 | UpgradeCollectPluginResource | POST upgrade | 🌐🔗 | 🟢 低 | `save_and_install` 用新版本重新安装 |
| 15 | RollbackDeploymentConfigResource | POST rollback | 🌐🔗 | 🟡 中 | Base 无 rollback，SaaS 模拟 |
| 16 | GetMetricsResource | GET metrics | 🌐🔗 | 🟢 低 | `get_metric_plugin()` → `plugin.metrics` |
| 17 | CollectConfigInfoResource | - | 📡🔗 | 🟢 低 | kernel API v3 专用 + v4 继承 |
| 18 | BatchRetryResource | POST batch_retry_detailed | 🌐🔗 | 🟢 低 | 继承 BatchRetryConfigResource |

### 4.2 frontend.py（前端展示专用）

| # | Resource | HTTP 端点 | 暴露渠道 | 适配复杂度 | 说明 |
|---|---------|----------|---------|-----------|------|
| 19 | FrontendCollectConfigDetailResource | GET frontend_config_detail | 🌐🔗 | 🟡 中 | 组合查询，依赖 `collect_config_detail` |
| 20 | FrontendCollectConfigTargetInfoResource | GET frontend_target_info | 🌐🔗 | 🟡 中 | 依赖 `collect_config_detail` |
| 21 | FrontendTargetStatusTopoResource | POST target_status_topo | 🌐🔗 | 🟡 中 | 依赖 `collect_target_status_topo` |
| 22 | DeploymentConfigDiffResource | GET deployment_diff | 🌐🔗 | 🟢 低 | 配置差异 |
| 23 | GetCollectVariablesResource | GET get_collect_variables | 🌐🔗 | 🟢 低 | 纯静态数据 |

### 4.3 status.py（状态查询）

> ✅ Base `NodemanInstaller.status(diff)` 已完整实现旧版兼容格式，status 类 Resource 适配复杂度已降至 🟢 低。
> 详见 [base_capability_mapping.md § 4.5](./base_capability_mapping.md)

| # | Resource | HTTP 端点 | 暴露渠道 | 适配复杂度 | Base 对应 |
|---|---------|----------|---------|-----------|----------|
| 24 | CollectTargetStatusResource | GET status | 🌐🔗 | 🟢 低 | ✅ `installer.status(diff=True)` 直接可用 |
| 25 | CollectRunningStatusResource | GET running_status | 🌐🔗 | 🟢 低 | ✅ `installer.status(diff=False)` 直接可用 |
| 26 | CollectInstanceStatusResource | GET collect_instance_status | 🌐🔗🔧 | 🟢 低 | ✅ `installer.status(diff=False)` + 被 `datalink` 模块内部调用 |
| 27 | CollectTargetStatusTopoResource | - | 🔧 | 🟢 低 | ✅ 消费 status(diff=False) 结果 + SaaS NoData 检测 |
| 28 | UpdateConfigInstanceCountResource | - | ⚠️ | 🟢 低 | 未找到调用者，疑似废弃 |

### 4.4 toolkit.py（运维工具）

| # | Resource | HTTP 端点 | 暴露渠道 | 适配复杂度 | 说明 |
|---|---------|----------|---------|-----------|------|
| 29 | ListLegacySubscription | GET list_legacy_subscription | 🌐🔗🔧 | 🟡 中 | 被 `statistics` 模块调用 |
| 30 | CleanLegacySubscription | GET clean_legacy_subscription | 🌐🔗 | 🟡 中 | 清理订阅 |
| 31 | ListLegacyStrategy | GET list_legacy_strategy | 🌐🔗🔧 | 🟢 低 | 被 `strategies` 模块调用 |
| 32 | ListRelatedStrategy | POST list_related_strategy | 🌐🔗 | 🟢 低 | 关联策略 |
| 33 | IsTaskReady | POST is_task_ready | 🌐🔗🔧 | 🟢 低 | 被 `models/collecting.py` 调用 |
| 34 | EncryptPasswordResource | - | 🔧 | 🟢 低 | 仅被 `plugin/manager/exporter.py` 调用 |
| 35 | DecryptPasswordResource | - | ⚠️ | 🟢 低 | 未找到调用者，疑似预留 |
| 36 | CheckAdjectiveCollect | GET check_adjective_collect | 🌐🔗 | 🟡 中 | 游离态检查 |
| 37 | FetchCollectConfigStat | GET fetch_collect_config_stat | 🌐🔗 | 🟢 低 | 统计信息 |
| 38 | CheckPluginVersionResource | POST check_plugin_version | 🌐🔗 | 🟡 中 | 版本校验 |

### 4.5 snmp_trap.py

| # | Resource | HTTP 端点 | 暴露渠道 | 适配复杂度 | 说明 |
|---|---------|----------|---------|-----------|------|
| 39 | GetTrapCollectorPluginResource | - | 🔧 | 🟡 中 | 仅被 `SaveCollectConfigResource` 内部调用 |

## 5. 可提取的公共函数/逻辑

详见 [common_functions.md](./common_functions.md)

## 6. 实施优先级建议

> 核心策略：Base 已有完整的部署管理能力，适配工作的核心是 **compat 层**（入参/出参转换），
> 而非补齐 base 功能。详见 [base_capability_mapping.md](./base_capability_mapping.md)

### Phase 0：compat 层基础
1. 建立 `resources/new.py`、`resources/old.py`、`resources/__init__.py` 结构
2. 建立 `compat.py`：核心转换函数
   - `convert_save_params_to_base()` 入参转换
   - `convert_deployment_to_legacy()` 出参转换
   - 状态枚举双向映射
   - 版本号转换
   - `remote_collecting_host` ↔ `remote_scope` 互转
3. 特性开关：`ENABLE_BK_MONITOR_BASE_COLLECTING`

### Phase 1：高频 CRUD（直接映射 base operation）
4. `SaveCollectConfigResource` → `save_and_install_metric_plugin_deployment()`
5. `CollectConfigListResource` → `list_metric_plugin_deployments()`
6. `CollectConfigDetailResource` → `get_metric_plugin_deployment()`
7. `ToggleCollectConfigStatusResource` → `start/stop_metric_plugin_deployment()`
8. `DeleteCollectConfigResource` → `delete_metric_plugin_deployment()`

### Phase 2：部署操作
9. `UpgradeCollectPluginResource` → `save_and_install`（新版本）
10. `RollbackDeploymentConfigResource` → SaaS 模拟（获取上一版本重新 install）
11. `CloneCollectConfigResource` → `get` + `save_and_install` 组合
12. 批量操作 → `retry/revoke/run` 直接映射

### Phase 3：状态查询（高兼容度）
13. `CollectTargetStatusResource` → `get_metric_plugin_deployment_status()`
14. `CollectRunningStatusResource` / `CollectInstanceStatusResource` → 同上
15. `GetCollectLogDetailResource` → `get_nodeman_collect_log_detail()`
16. `CollectTargetStatusTopoResource` → status() + SaaS NoData 检测
17. frontend.py 全部 Resource

### Phase 4：工具与边缘
18. toolkit.py 全部 Resource（大部分保留 SaaS 层）
19. snmp_trap.py

## 7. 文档索引

### 全局文档

- [base_capability_mapping.md](./base_capability_mapping.md)：bk-monitor-base 能力映射
- [common_functions.md](./common_functions.md)：公共函数/逻辑提取规划
- [resource_exposure.md](./resource_exposure.md)：**Resource 暴露渠道与调用分析**（ViewSet / kernel_api / 内部调用）

### Resource 详细分析

每个 Resource 的详细分析见 `resources/` 子目录，按源文件分组：

- **backend/**：核心 CRUD 和部署操作
- **frontend/**：前端展示专用接口
- **status/**：状态查询接口
- **toolkit/**：运维工具接口
- **snmp_trap/**：SNMP Trap 专用接口
