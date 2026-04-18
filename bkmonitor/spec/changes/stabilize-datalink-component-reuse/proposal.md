# Proposal: 稳定复用 DataLink 既有组件名称

## 背景

当前 `DataLink.apply_data_link` 的调用链里，`compose_*_configs` 会按固定命名规则创建本地组件配置，并据此渲染下发给 BKBase 的配置。

这在纯新建场景下可工作，但在迁移场景下会出现一个明显问题：

- 迁移导入后的 DataLink 组件，已经以旧环境或旧规则生成的 `name` 落库；
- 我们重新执行 `apply_data_link` 时，`compose_*` 仍按当前规则生成"固定 name"；
- `update_or_create` 以新 name 作为查询条件无法命中旧记录，从而走"创建"分支落地一份新组件；
- BKBase 侧也会收到新 name 的下发配置，最终出现同一条 DataLink 下重复组件并存的风险。

## 问题定义

我们需要让 `apply_data_link` 在"已有组件存在但 name 不对齐"的情况下，优先复用当前 DataLink 已关联的组件，而不是按新 name 盲目新建。

同时需要保证：

- 复用过程是稳定的，重复执行 `apply_data_link` 不会让 name 来回变化；
- 不依赖 queryset 默认顺序；
- 本地 ORM 记录和下发到 BKBase 的配置必须使用同一个 `name`；
- 当 datalink 下出现"超出预期"的脏数据时，能快速失败而不是继续在脏数据上叠加。

## 目标

1. 在 `apply_data_link` 入口一次性加载当前 datalink 已关联的所有组件，构造一个 `ExistingComponentContext`，作为 compose 阶段的复用候选池。
2. 各 `compose_*_configs` 在生成每个组件之前，先通过 `ctx.claim(kind, predicate)` 尝试复用既有组件；命中即用其 `name` 进入 `update_or_create`，否则按现有规则新建。
3. compose 完成后、调用 BKBase 下发之前，统一对 `ctx.leftover()` 做一次"未消费组件"检查；按 `(strategy, kind)` 声明的策略决定是直接报错还是允许保留。
4. 整个过程按 `data_link_strategy` 维度独立灰度，可按 strategy 逐步上线、独立回滚。

## 核心设计要点

- **加载范围统一**：使用一份"全部 DataLink 组件模型"的全局列表加载现有组件，过滤条件只有 `bk_tenant_id + namespace + data_link_name`，不按 strategy 划分子集。这样可以同时把"由历史 strategy 创建、当前 strategy 不该再生成"的组件也纳入检查范围，避免脏数据被静默忽略。
- **匹配策略下沉**：是否复用、按什么键复用，全部由 compose 自己写在 `claim` 的 `predicate` 里。外层框架不维护 `(kind, logical_key) -> name` 这样的全局映射，也不替 compose 决定语义键。
- **歧义即放弃**：`claim` 的 predicate 命中 0 条或 ≥2 条时统一返回 `None`，由 compose 走新建分支；上下文不被修改，多余候选自然进入 leftover 检查。
- **leftover 收尾**：整个 datalink 是否"健康"由 leftover 检查在 compose 完成后一次性判定，而不是在 compose 之前预先估算"理论组件数量"。
- **policy 仅两态**：`REUSE_LEFTOVER_POLICY[(strategy, kind)]` 只有 `strict`（默认，leftover 非空报错）与 `keep`（允许保留）两种取值；本次唯一需要声明 `keep` 的是 `BK_LOG` 的 `ESStorageBindingConfig` / `DorisStorageBindingConfig`（开关变化时允许旧 binding 保留）。
- **本地与下发一致**：复用的 `name` 必须先进入本地 `update_or_create`，再由 ORM 实例渲染下发 payload；不允许在 payload 阶段对 `metadata.name` 做补丁式重写。

## 非目标

- 本次不改变 `compose_bkdata_data_id_name` / `compose_bkdata_table_id` 的命名规则本身。
- 本次不做历史脏数据自动清理或孤儿组件回收。
- 本次不直接依赖 BKBase 实时扫描全部组件；复用候选只来自 Metadata 本地库。
- 本次不处理多进程/多节点并发执行同一 datalink `apply_data_link` 的并发问题，假设上层调度按 datalink 串行。

## 影响范围

- `metadata/models/data_link/data_link.py`
- 相关 `compose_*_configs` 分支（按 strategy 逐个接入）
- `metadata/tests/data_link/` 下的链路创建与重复 apply 测试
- `settings` 中新增 `DATA_LINK_COMPONENT_REUSE_STRATEGIES` 灰度开关

## 预期收益

- 兼容迁移后已存在的组件名称，避免重复创建同类组件；
- 提升重复执行 `apply_data_link` 的幂等性与稳定性；
- 在链路出现异常膨胀时通过 leftover 检查快速失败，阻止进一步污染；
- 允许日志链路等少量合法存量组件继续保留，避免把预期行为误判成异常；
- 为后续 DataLink 迁移、修复、对账能力提供统一的复用入口。
