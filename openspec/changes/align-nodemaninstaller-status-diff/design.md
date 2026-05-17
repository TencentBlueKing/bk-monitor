## Context

`bk-monitor-base` 当前 `NodemanInstaller.status()` 的实现偏向 base 域模型：它直接返回当前订阅的全量实例状态，并按 `remote_scope or target_scope` 聚合为 `node_name/node_type/node_id/child` 结构。旧版 collecting 的 `NodeManInstaller.status(diff=False)` 则是一个面向上层展示的兼容接口，既负责把节点管理任务结果转换为旧版实例字段，也负责基于“当前版本/上一版本”的差异把节点分为 `ADD`、`UPDATE`、`RETRY`，并最终输出 `node_path/label_name/is_label/child` 结构。

用户要求这次改造必须以旧版 collecting 代码为兼容基线，避免后续实现与旧逻辑发生漂移。兼容基线不仅包括方法签名，还包括以下运行时行为：

- `status(diff=False)` 默认返回旧版结构化的全量状态。
- `status(diff=True)` 的分组和分类来自旧版 `DeploymentConfigVersion.show_diff()` 的行为，而不是一个“语义上接近”的新算法。
- 节点聚合以当前部署版本的 `target_node_type/target_nodes` 为基准，远程采集范围只参与差异判定，不改变 status 的目标节点分组方式。
- 返回值保留旧版字段名、日志表达方式和若干历史兼容逻辑，例如 IP 主机配置归一化、模板节点展开和动态分组聚合。

这次变更横跨 base installer 状态查询、部署版本对比、CMDB 节点映射和测试基线，属于适合先写清设计再落实现的跨模块行为改造。

## Goals / Non-Goals

**Goals:**

- 让 `bk-monitor-base` 的 `NodemanInstaller.status` 方法签名与旧版 `NodeManInstaller.status(diff=False)` 对齐。
- 让 `status(diff=False)` 和 `status(diff=True)` 的输出结构、字段名和分组方式与旧版 collecting 保持完全兼容。
- 用旧版代码行为定义 diff 规则，包括首版部署、插件版本变化、参数变化、远程采集目标变化、目标节点增删改等场景。
- 明确并固化旧版中的特殊行为，避免后续实现“看起来合理但不兼容”。
- 为后续实现提供可直接转成单测/集成测试的规范基线。

**Non-Goals:**

- 不在本次设计中扩展 `status()` 到旧版未支持的新字段或新分组维度。
- 不借机统一 `NodemanInstaller`、`K8sInstaller`、`JobInstaller` 的状态返回模型。
- 不修复与旧版兼容语义无关的历史问题，也不尝试重构所有节点管理状态处理流程。
- 不要求对当前 base `status()` 的现有调用方做向前兼容适配；本次以旧版 collecting 兼容为唯一接口目标。

## Decisions

### 决策 1：以旧版 `NodeManInstaller.status(diff)` 的运行时行为作为唯一兼容基线

`status` 的兼容目标不只来源于文档说明，还要直接锚定旧版代码中的实际行为，包括：

- `_process_nodeman_task_result()` 产出的实例字段集与状态转换。
- `DeploymentConfigVersion.show_diff()` 产出的节点差异分类。
- `status(diff)` 对模板、动态分组、主机和拓扑目标的聚合输出。

这样做的原因是旧版 spec 文档里保留了高层意图，但像 “removed 节点不出现在最终结果中” 这类行为只有读代码才能稳定识别。如果只按高层描述实现，最容易在边界场景偏离。

备选方案：

- 直接扩展现有 base `status()` 返回结构，再由调用方转换。放弃，因为这会把兼容责任继续推给上层，无法从 base 层提供稳定契约。
- 参考旧版文档重写一套“等价但更简洁”的逻辑。放弃，因为用户明确要求完全兼容，简化实现会放大漂移风险。

### 决策 2：新增一个面向兼容语义的状态构建流程，而不是在现有 base 返回值上做浅层补丁

现有 base `status()` 在以下方面与旧版天然不兼容：

- 分组基准是 `remote_scope or target_scope`，旧版按 `target_node_type/target_nodes` 聚合。
- 实例字段使用 `related_node_ids`、原始错误日志等 base 语义，旧版需要 `scope_ids`、阶段日志、`task_id`、`plugin_version` 等字段。
- 主机与模板目标的历史兼容逻辑不在现有返回结构中。

因此设计上需要拆成两段：

1. 复用节点管理查询和实例解析能力，得到标准化的“原始实例状态”。
2. 基于旧版规则做字段补齐、diff 分类、目标节点映射和最终分组输出。

这样能最大限度复用现有底层能力，同时保证最终接口由兼容层统一收口。

备选方案：

- 在现有 `status()` 最后一步直接改字段名。放弃，因为仅改字段名无法解决 diff 分类、分组基准和历史兼容节点映射问题。

### 决策 3：diff 分类复刻旧版 `show_diff()` 的行为，而不是复用 base `get_version_diff()`

旧版 `show_diff()` 的核心兼容语义是：

- 无上一版本时，所有当前节点都视为 `ADD`。
- 插件版本变化时，上一版本全部目标节点视为 `UPDATE`。
- `target_node_type` 变化时，当前节点视为 `ADD`，旧节点视为 `REMOVE`。
- 节点相等且参数或远程采集目标变化时，节点视为 `UPDATE`。
- 节点相等且参数未变时，节点视为 `RETRY`。
- 未匹配到的当前节点视为 `ADD`，未匹配到的旧节点视为 `REMOVE`。
- 最终 `status(diff=True)` 会丢弃 `REMOVE` 节点，不参与返回结果构建。

base `get_version_diff()` 只返回字段级差异摘要，不提供旧版所需的 `added/updated/removed/unchanged` 节点列表，因此不能直接作为兼容实现的依据。设计上应新增一个专门的旧版兼容 diff 计算器，输入当前/上一部署版本，输出旧版节点分类结果。

备选方案：

- 复用 `get_version_diff()` 后再推导节点分类。放弃，因为它丢失了节点级别的旧版语义，尤其是 `RETRY`、`REMOVE` 过滤和“插件版本变化即全部 UPDATE”的行为。

### 决策 4：status 聚合一律以当前部署版本的 target scope 为准

旧版 `status(diff)` 使用 `current_version.target_node_type` 与 `current_version.target_nodes` 驱动节点组织方式：

- `INSTANCE + HOST` 聚合到单一“主机”节点，并按 diff 标签拆组。
- `DYNAMIC_GROUP + HOST` 按动态分组构造节点。
- `TOPO`/`SERVICE_TEMPLATE`/`SET_TEMPLATE` 按拓扑路径或模板展开后的拓扑节点构造 `node_path`。

远程采集目标只影响 `show_diff()` 中“是否更新配置”的判断，不改变展示侧的目标节点语义。因此新实现必须显式避免使用 `remote_scope or target_scope` 作为 status 聚合基准。

备选方案：

- 延续现有 base 的 `remote_scope or target_scope` 逻辑。放弃，因为远程采集配置会直接改变分组结果，与旧版展示完全不一致。

### 决策 5：实例字段按旧版格式重建，必要时主动降级现有 base 信息

新实现的实例对象应恢复为旧版字段集，包括：

- `instance_id`、`ip`、`bk_cloud_id`、`bk_host_id`、`bk_host_name`、`bk_supplier_id`
- `task_id`、`status`、`plugin_version`、`log`、`action`、`steps`、`scope_ids`
- 服务实例字段：`instance_name`、`service_instance_id`、`bk_module_id`
- 主机实例字段：`instance_name`、`bk_module_ids`

其中有两个兼容点必须显式处理：

- `log` 必须保持旧版“步骤名-子步骤名”表达，而不是 base 当前返回的子步骤原始日志文本。
- `RUNNING/PENDING` 状态必须按旧版规则结合部署动作映射到 `STARTING/STOPPING` 等展示状态，而不是保留 base 当前的中间态表达。

备选方案：

- 保留 base 更详细的错误日志文本。放弃，因为旧版前端与调用方依赖的是阶段名而不是原始日志。

### 决策 6：历史兼容规则进入规范并要求测试覆盖

以下规则虽然看似“边角”，但一旦遗漏就会与旧版行为漂移，因此设计上直接将其视为主流程的一部分：

- 主机目标允许旧格式 `ip/bk_cloud_id`，在 diff 前需归一化为 `bk_host_id`。
- 模板目标需先展开为对应的拓扑节点，再和实例 `scope_ids` 对齐。
- 动态分组需先查询组成员，再将实例按 `bk_host_id` 关联到分组。
- 结果构建后需要移除实例内部的临时关联字段，保持旧版输出纯净。

备选方案：

- 将这些逻辑留到实现时“按需补”。放弃，因为这正是最容易引发兼容性遗漏的来源。

## Risks / Trade-offs

- [兼容基线依赖旧代码细节，逻辑较繁琐] → 通过在 spec 中写清旧版行为，并要求测试按旧版场景覆盖首版、参数更新、模板、动态分组和历史主机配置。
- [现有 base `status()` 使用 remote scope 聚合，改造后可能影响当前调用方预期] → 明确将旧版 collecting 兼容语义作为新的接口契约，并在实现时同步修正相关调用测试。
- [CMDB 查询链路较多，模板/动态分组/主机归一化都依赖外部数据] → 优先复用现有 base/旧版 helper 的查询模式，测试中对外部调用做稳定 mock。
- [旧版行为本身存在非直觉细节，如 `REMOVE` 不出现在最终返回中] → 在 spec 中把这些细节写成强约束，避免实现者按“常识”修正。

## Migration Plan

1. 先在 `openspec` 中固化兼容要求，作为实现与测试的唯一验收基线。
2. 实现 `NodemanInstaller.status(diff=False)` 新签名，并新增旧版兼容 diff/分组辅助逻辑。
3. 将现有状态查询相关测试替换或补充为旧版兼容场景测试。
4. 发布时不做数据迁移；如需回滚，可恢复 `status()` 到当前 base 版本，但会失去旧版兼容能力。

## Open Questions

- 无。当前兼容目标已由旧版 collecting 代码和用户要求明确限定。
