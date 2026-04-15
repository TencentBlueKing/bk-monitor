# Proposal: 稳定复用 DataLink 既有组件名称

## 背景

当前 `DataLink.apply_data_link` 的调用链里，`compose_*_configs` 会按固定命名规则创建本地组件配置，并据此渲染 BKBase 下发配置。

这在纯新建场景下可工作，但在迁移场景下会出现一个明显问题：

- 迁移导入后的 DataLink 组件，已经以旧环境或旧规则生成的 `name` 落库；
- 我们重新执行 `apply_data_link` 时，`compose_*` 仍会生成“当前规则下的固定 name”；
- 由于新旧 `name` 不一致，`update_or_create` 会命中新 name，从而额外创建一组组件；
- BKBase 侧也会收到新 name 的配置，最终出现同一条 DataLink 下重复组件并存的风险。

## 问题定义

我们需要让 `apply_data_link` 在“已有组件存在但 name 不对齐”的情况下，优先复用当前 DataLink 已关联组件，而不是盲目按固定 name 新建。

同时需要保证：

- 整个映射过程是稳定的；
- 不能依赖 queryset 默认顺序；
- 不能因为排序变化导致每次 apply 都把 name 来回覆盖；
- 本地 Metadata 记录与 BKBase 下发配置中的 name 必须保持一致。

## 目标

1. 在 `apply_data_link` 入口识别当前 DataLink 已有关联组件。
2. 在真正复用前，先校验各组件类型的现有数量是否超出本次理论范围。
3. 为 `compose_*_configs` 生成的组件建立“逻辑槽位 -> 既有组件 name”的映射。
4. 在可安全复用时，优先覆盖既有组件；仅在没有可复用候选时才创建新组件。
5. 对多组件场景建立确定性的匹配规则，保证重复执行结果稳定。

## 核心约束

除少量特殊链路外，大部分 `data_link_strategy` 的组件数量都是稳定不变的。

因此本次变更采用“外层提供通用校验辅助，最终规则由各类 datalink 自行决定”的保守策略：

- 默认情况下，一旦发现当前 datalink 下某类组件数量多于本次理论应生成数量，直接报错并中止；
- 但少量允许保留历史组件的场景，需要由对应 datalink 明确声明放宽逻辑；
- 不在脏数据基础上继续覆盖或补建；
- 不尝试自动吞掉“多余组件”，避免一次 apply 让链路状态进一步失控。

例如日志链路中，ES/Doris 存储绑定可能因开关变化导致本次 compose 产出的 binding 数量变少；这类场景下允许保留旧 binding，而不是在 apply 时删除或报错。

## 非目标

- 本次不改变 `compose_bkdata_data_id_name` / `compose_bkdata_table_id` 的命名规则本身。
- 本次不做历史脏数据自动清理或孤儿组件回收。
- 本次不直接依赖 BKBase 实时扫描全部组件；优先使用 Metadata 中当前 DataLink 的关联记录作为复用依据。

## 方案概览

在 `DataLink.apply_data_link` 中新增“组件复用规划”阶段：

1. 先根据当前上下文推导“本次理论组件槽位”。
2. 查询当前 `data_link_name` 关联的所有组件配置，按类型分组。
3. 外层收集理论槽位与现有组件，交由对应 datalink 的校验逻辑决定是否允许继续执行。
4. 仅在该 datalink 校验通过后，基于 compose 阶段将要产出的“逻辑组件槽位”计算复用计划。
5. 将复用后的 name 传入各 `compose_*_configs`，让本地 `update_or_create` 和最终下发配置都使用同一个 resolved name。
6. 对无法唯一匹配的候选不做模糊复用，回退为新建，避免错误覆盖。

## 影响范围

- `metadata/models/data_link/data_link.py`
- 相关 `compose_*_configs` 分支
- `metadata/tests/data_link/` 下的链路创建与重复 apply 测试

## 预期收益

- 在发现链路已出现异常膨胀时快速失败，阻止进一步污染；
- 允许日志等少量合法存量组件继续保留，避免把预期行为误判成异常；
- 兼容迁移后已存在的组件名称；
- 避免重复创建同类组件；
- 提升重复执行 `apply_data_link` 的幂等性与稳定性；
- 为后续 DataLink 迁移、修复和对账能力提供统一的复用入口。
