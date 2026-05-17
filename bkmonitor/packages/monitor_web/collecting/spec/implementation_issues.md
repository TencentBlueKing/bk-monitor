# collecting 模块适配 bk-monitor-base 实现问题记录

> 本文档记录在将 collecting 模块的 backend / frontend / snmp_trap resource 适配到
> `bk-monitor-base` 过程中发现的问题。每个问题附带影响的 Resource、当前临时处理方式及建议的后续改进方向。

---

## 一、列表查询能力不足

### 1.1 list_metric_plugin_deployments 过滤能力有限（已部分缓解）

- **影响 Resource**: `CollectConfigListResource`
- **问题描述**: 旧版列表筛选同时混合了运行态、任务态、升级态和模糊搜索语义，而
  base 领域模型只具备部署原子状态。若不做分层，容易把旧版兼容枚举直接固化到 base。
- **当前处理**:
  - base 层 `list_metric_plugin_deployments` 已支持 `deployment_statuses`、`fuzzy`、
    排序白名单与分页下推。
  - SaaS 层 `CollectConfigListResource` 负责把旧版 `status/task_status` 翻译为
    base 原子状态；其中 `SUCCESS/WARNING/FAILED` 和 `need_upgrade` 仍在 SaaS 层补充过滤。
- **剩余风险**: `task_status=SUCCESS/WARNING/FAILED` 与 `need_upgrade` 仍需要补充实例统计 /
  版本比较，因此在这些场景下无法完全避免 SaaS 层后置过滤。
- **后续建议**: 如果后面要继续下推 `SUCCESS/WARNING/FAILED`、`need_upgrade`，应补齐
  base 的实例统计快照或版本比较原语，而不是继续扩展旧版兼容枚举入参。

### 1.2 缺少 config_version / info_version 字段

- **影响 Resource**: `CollectConfigListResource`、`CollectConfigDetailResource`
- **问题描述**: base 返回的 `MetricPluginDeployment` 和 `MetricPluginDeploymentVersion`
  不包含 `config_version` / `info_version` 字段，旧版 API 需要返回这些字段。
- **当前处理**: 在 `compat.py` 中从 `plugin_version` 字段推导（格式如 `"1.2"` → config=1, info=2）。
- **建议**: 如果 `config_version` / `info_version` 是必要的业务概念，base 可在
  `MetricPluginDeploymentVersion` 中直接提供，避免 SaaS 层猜测解析。

---

## 二、缺少操作 API

### 2.1 缺少 rename / partial update API

- **影响 Resource**: `RenameCollectConfigResource`
- **问题描述**: base 没有专门的重命名或部分更新 API，`save_and_install_metric_plugin_deployment`
  会触发完整的重新安装流程，仅为修改名称而重新安装不合理。
- **当前处理**: 直接更新旧 ORM 表 `CollectConfigMeta.name`。
- **建议**: base 提供 `update_metric_plugin_deployment_name()` 或通用的
  `partial_update_metric_plugin_deployment()` API。

### 2.2 缺少 revoke operation

- **影响 Resource**: `RevokeTargetNodesResource`、`StopAndRunResource`
- **问题描述**: base 的 `operation` 层没有直接的 `revoke`（撤销正在执行的任务）操作。
- **当前处理**: 通过 `get_installer(deployment, operator)` 获取安装器实例后直接调用
  `installer.revoke()`。
- **建议**: base 在 `operation` 层提供 `revoke_metric_plugin_deployment()` 封装。

### 2.3 installer.revoke() 不支持按 instance_ids 撤销

- **影响 Resource**: `RevokeTargetNodesResource`
- **问题描述**: 原版 API 支持传入 `instance_ids` 进行部分实例撤销，但 base 的
  `installer.revoke()` 只接受 `scope` 参数（`MetricPluginDeploymentScope | None`）。
- **当前处理**: 忽略 `instance_ids` 参数，执行全量撤销。
- **风险**: 行为语义与旧版不一致，用户选择部分实例撤销时实际会撤销全部。
- **建议**: base `installer.revoke()` 增加 `instance_ids` 参数支持。

### 2.4 缺少 run operation

- **影响 Resource**: `RunCollectConfigResource`
- **问题描述**: base 的 `operation` 层没有直接的 `run`（手动触发执行）操作。
- **当前处理**: 通过 `get_installer(deployment, operator)` 获取安装器实例后直接调用
  `installer.run(action, scope)`。
- **建议**: base 在 `operation` 层提供 `run_metric_plugin_deployment()` 封装。

### 2.5 缺少 rollback operation 及历史版本查询

- **影响 Resource**: `RollbackDeploymentConfigResource`
- **问题描述**:
  1. base 没有 `rollback` operation。
  2. base 不提供历史版本列表查询 API（`list_metric_plugin_deployment_versions`），
     无法获取「上一版本」的完整参数用于回滚。
- **当前处理**: 完全回退到旧 ORM 实现（通过 `CollectConfigMeta` + `get_collect_installer`）。
- **建议**: base 提供 `list_metric_plugin_deployment_versions()` 查询能力，
  以及 `rollback_metric_plugin_deployment()` 操作。

---

## 三、~~缺少差异比对能力~~（已解决）

### 3.1 ~~无版本差异比对（show_diff）~~（已解决）

- **影响 Resource**: `DeploymentConfigDiffResource`
- **问题描述**: 前端详情页展示「升级 diff」时，需要对比当前版本与上次部署版本的参数差异。
- **解决状态**: ✅ **已解决**。base 的 `NodemanInstaller.status(diff=True)` 已实现完整的
  旧版兼容 diff 逻辑，包括：
  1. `_get_previous_deployment_version()` 查询上一部署版本
  2. `_get_legacy_node_diff()` 按旧版 `show_diff` 规则计算 ADD/REMOVE/UPDATE/RETRY 差异
  3. `_build_legacy_status_groups()` 构造旧版格式的分组返回值（含 `node_path`/`label_name`/`is_label`）
  4. `_process_instance_result()` 实例级状态转换（含 `task_id`/`plugin_version`/`log`/`scope_ids`）
- **遗留事项**: `DeploymentConfigDiffResource` 需要的是「配置参数差异」而非「节点部署状态差异」，
  仍需 base 提供版本参数 diff API 或在 SaaS 层实现。`status(diff=True)` 解决的是节点
  部署状态页面的差异展示。

---

## 四、数据格式兼容问题

### 4.1 CollectConfigInfoResource 返回格式不兼容

- **影响 Resource**: `CollectConfigInfoResource`
- **问题描述**: 该接口供 `kernel_api` 调用，旧版直接返回
  `CollectConfigMeta.objects.all().values()` 的原始 dict 列表。
  base 返回的 `MetricPluginDeployment` 格式与 ORM `values()` 完全不同，字段名、结构
  均有差异。如果直接替换，所有下游调用方都会出错。
- **当前处理**: 保留旧 ORM 查询，不走 base。
- **建议**: 需要清点所有 `kernel_api` 调用方对该接口返回值的使用方式，
  确认是否可以统一到 base 格式，或在 `compat.py` 中提供完整的字段映射转换。

---

## 五、跨模块依赖问题

### 5.1 虚拟插件创建依赖 PluginManagerFactory

- **影响 Resource**: `SaveCollectConfigResource`、`GetTrapCollectorPluginResource`
- **问题描述**: LOG、PROCESS、K8S、SNMP_TRAP 等虚拟插件的创建和版本管理依赖
  `PluginManagerFactory` 和 `resource.plugin.create_plugin` 调用链。
  如果 `plugin` 模块也切换到了 base 模式（`ENABLE_BK_MONITOR_BASE_PLUGIN=true`），
  `PluginManagerFactory` 的行为可能发生变化。
- **当前处理**: 使用旧版 `PluginManagerFactory` 路径创建虚拟插件。
- **风险**: 两个模块开关同时打开时，虚拟插件创建路径可能出现不一致。
- **建议**: 确认 `plugin` 模块适配 base 后虚拟插件创建的统一入口，
  或在 base 层提供虚拟插件创建的原生支持。

### 5.2 DatalinkDefaultAlarmStrategyLoader 依赖旧 ORM

- **影响 Resource**: `DeleteCollectConfigResource`、`SaveCollectConfigResource`
- **问题描述**: 删除/保存采集配置后需要清理/创建关联的默认告警策略。
  `DatalinkDefaultAlarmStrategyLoader` 内部依赖 `CollectConfigMeta` ORM 对象。
  当 base 删除了对应部署记录后，`CollectConfigMeta` 中可能已无对应记录，
  导致策略清理逻辑异常。
- **当前处理**: try-except 包裹调用，失败不影响主流程。
- **建议**: `DatalinkDefaultAlarmStrategyLoader` 应适配 base 数据源，
  或 base 提供关联策略清理的 hook 机制。

### 5.3 ~~FrontendTargetStatusTopoResource 依赖未适配的 status 模块~~（进行中）

- **影响 Resource**: `FrontendTargetStatusTopoResource`
- **问题描述**: 该 Resource 内部调用 `resource.collecting.collect_target_status_topo`，
  而 `status` 模块暂未适配 base（始终使用旧实现）。
- **解决状态**: 🔧 **进行中**。base 的 `NodemanInstaller.status(diff)` 已完整实现
  旧版兼容的 status 返回格式，现在可以着手改造 `status` 模块的 Resource 层。

---

## 六、类型检查器限制（非功能性问题）

### 6.1 PluginManager 动态属性无法被 basedpyright 识别

- **影响位置**: `SaveCollectConfigResource`（`backend.py`）、
  `GetTrapCollectorPluginResource`（`snmp_trap.py`）
- **问题描述**: `PluginManagerFactory` 通过工厂模式动态创建 `PluginManager` 子类，
  其 `get_params`、`touch` 等方法在静态类型层面不可见。basedpyright 报告
  `无法访问 "PluginManager" 类的 "get_params" 属性` 等错误（共 5 处）。
- **性质**: 预存问题，非本次适配引入。
- **建议**: 后续可为 `PluginManagerFactory` 添加 `Protocol` 类型注解或
  `TYPE_CHECKING` 分支来消除类型检查警告。

---

## 总结

| 分类 | 问题数 | 严重程度 | 状态 |
|------|--------|---------|------|
| 列表查询能力不足 | 2 | 中（性能风险） | 待处理 |
| 缺少操作 API | 5 | 高（部分功能降级或回退旧实现） | 待处理 |
| ~~缺少差异比对能力~~ | ~~1~~ | ~~中~~ | ✅ 已解决（Base installer.status(diff) 已实现） |
| 数据格式兼容 | 1 | 中（保留旧实现） | 待处理 |
| 跨模块依赖 | 3→2 | 中（需协调多模块适配节奏） | 5.3 进行中 |
| 类型检查器限制 | 1 | 低（不影响运行） | 待处理 |

**优先建议 base 补齐的能力（按优先级排序）**：

1. `list_metric_plugin_deployments` 增加过滤/搜索参数
2. `list_metric_plugin_deployment_versions()` 历史版本查询
3. `rollback_metric_plugin_deployment()` 回滚操作
4. `revoke_metric_plugin_deployment()` 撤销操作（含 instance_ids 支持）
5. `run_metric_plugin_deployment()` 手动触发执行
6. `update_metric_plugin_deployment_name()` 部分更新
7. ~~版本差异比对能力~~（✅ installer.status(diff) 已实现节点状态 diff）
