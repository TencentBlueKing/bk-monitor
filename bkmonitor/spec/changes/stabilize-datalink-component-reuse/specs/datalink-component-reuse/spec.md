# Capability: DataLink 组件复用

## ADDED Requirements

### Requirement: apply_data_link 必须在 compose 前加载当前 datalink 已有组件

`DataLink.apply_data_link` 在调用 `compose_configs` 之前，必须基于一个全局的"DataLink 组件模型列表"，按 `bk_tenant_id + namespace + data_link_name` 把当前 datalink 下所有相关 kind 的现有组件一次性装入一个 `ExistingComponentContext`，并把该上下文注入 `compose_configs`。

加载范围由统一的全局 kind 列表决定，不依赖 `data_link_strategy`。任何属于该全局列表、且 `data_link_name` 命中的组件都会被装入上下文，无论它当初是由哪种 strategy 创建。

#### Scenario: 加载范围使用统一 kind 列表而非 strategy 分类

- Given 系统维护一份"全部 DataLink 组件模型"的全局列表
- When 执行 `apply_data_link`
- Then 上下文加载阶段必须遍历该全局列表
- And 不得改用 `STRATEGY_RELATED_COMPONENTS[strategy]` 之类的按 strategy 过滤的子集
- And 加载条件必须是 `bk_tenant_id + namespace + data_link_name`，且仅作用于当前 datalink

#### Scenario: 历史上由其它 strategy 创建的同名组件也必须被纳入上下文

- Given 当前 datalink 的 `data_link_name` 下存在一条组件
- And 该组件所属 kind 不属于当前 strategy 在历史代码中默认创建的 kind 集合
- When 执行 `apply_data_link`
- Then 该组件仍必须被装入 `ExistingComponentContext`
- And 必须接受后续的 leftover 检查，避免脏数据被静默忽略

### Requirement: compose 分支必须通过 `ExistingComponentContext.claim` 复用既有组件

各 `compose_*_configs` 在生成每一个组件之前，必须先调用 `ExistingComponentContext.claim(kind, predicate)` 尝试从上下文中认领一条同语义的既有组件；命中时使用既有组件的 `name` 进入 `update_or_create`，未命中时按当前命名规则新建。

`claim` 必须满足：

- 恰好 1 条匹配 → 从上下文中移除并返回该组件；
- 0 条匹配 → 返回 `None`；
- ≥2 条匹配 → 返回 `None`，且不修改上下文，由 compose 走"新建"分支处理。

#### Scenario: 迁移后 name 不一致但语义键命中

- Given 当前 datalink 已存在一条同 kind 的既有组件
- And 该组件的 `name` 与本次 compose 规则生成的 `generated_name` 不同
- And compose 提供的 `predicate` 通过稳定语义键（如 `table_id`）唯一命中该既有组件
- When 执行 compose 分支
- Then compose 必须以 `claim` 返回组件的 `name` 作为 `update_or_create` 的查询条件
- And 不得新建一条使用 `generated_name` 的同类组件
- And 最终下发到 BKBase 的配置 `metadata.name` 必须与本地复用后的 `name` 一致

#### Scenario: 同一 predicate 命中多条既有组件时放弃复用

- Given 上下文中某个 kind 下有多条候选都能被 compose 提供的 `predicate` 命中
- When compose 调用 `claim(kind, predicate)`
- Then `claim` 必须返回 `None`
- And 上下文不得被修改
- And compose 必须按 `generated_name` 走新建分支
- And 多余候选必须保留在上下文中，进入后续 leftover 检查

#### Scenario: 部分命中加部分新建

- Given 当前 datalink 下某 kind 已有部分既有组件
- When compose 在循环中对每个 slot 调用 `claim`
- Then 命中的 slot 必须复用既有组件 `name`
- And 未命中的 slot 必须按 `generated_name` 新建
- And 命中与未命中之间不得相互影响（claim 一次只消费一条候选）

#### Scenario: 重复 apply 必须给出稳定的复用结果

- Given 一次 `apply_data_link` 已经基于稳定语义键完成了若干 `claim`
- When 立刻再次执行 `apply_data_link`，且 ORM 状态未被外部修改
- Then 第二次执行的 `claim` 结果必须与第一次完全一致
- And 不得因为 queryset 默认顺序、分页或临时排序差异导致不同 slot 命中不同既有组件

### Requirement: 本地 ORM 与下发配置必须共用同一个 name

一旦某个组件 slot 通过 `claim` 决定复用既有组件，本地 `update_or_create` 与最终发送给 BKBase 的配置 `metadata.name` 必须使用同一个 `name`。

#### Scenario: 禁止在 payload 阶段对 name 做补丁式重写

- Given compose 已经基于 `claim` 结果调用了 `update_or_create`
- When 生成最终的 BKBase 下发 payload
- Then payload 中该组件的 `metadata.name` 必须直接来自 ORM 实例
- And 不允许在 payload 上单独重写 `metadata.name`，否则会造成本地记录与 BKBase 实际组件名称不一致

### Requirement: apply_data_link 必须在 compose 之后、BKBase 下发之前执行 leftover 检查

`compose_configs` 执行完成后，`apply_data_link` 必须基于 `ExistingComponentContext.leftover()` 与该 datalink 声明的 `REUSE_LEFTOVER_POLICY` 做一次统一的"未消费组件"检查，再决定是否调用 BKBase 下发。

`REUSE_LEFTOVER_POLICY` 是 `(strategy, kind) -> Literal["strict", "keep"]` 的集中声明，未声明的 `(strategy, kind)` 默认为 `strict`。

- `strict`：该 kind 的 leftover 必须为空，否则视为脏数据，apply 必须直接报错；
- `keep`：允许 leftover 存在；既不报错，也不删除，也不参与本次下发；本地 ORM 记录保持不变。

无论哪种 policy，leftover 中的组件**都不得**被本次 apply 改名、改字段或删除。

#### Scenario: strict 策略下出现未消费组件必须直接报错

- Given 某个 kind 在该 strategy 下被声明为 `strict`（或未声明，按默认 `strict` 处理）
- And compose 完成后该 kind 的 `leftover()` 非空
- When 进入 leftover 检查
- Then `apply_data_link` 必须抛出包含 `data_link_name`、`strategy`、`kind`、leftover 组件标识的错误
- And 必须在调用 BKBase 下发接口之前抛出
- And 不得对 leftover 组件做任何修改或删除

#### Scenario: keep 策略下未消费组件必须保留

- Given 某个 kind 在该 strategy 下被声明为 `keep`
- And compose 完成后该 kind 的 `leftover()` 非空
- When 进入 leftover 检查
- Then 不得抛错
- And 不得删除 leftover 组件
- And 不得将 leftover 组件加入本次 BKBase 下发 payload
- And 不得修改 leftover 组件的本地 ORM 字段

#### Scenario: 多个 strict 违规必须一次性聚合上报

- Given 多个 kind 同时出现 `strict` 违规
- When 进入 leftover 检查
- Then `apply_data_link` 必须收集所有违规后再抛错，而不是遇到第一个就抛
- And 错误信息必须按 kind 列出对应的 leftover 组件，便于人工排查

### Requirement: `claim` 调用的 kind 必须属于上下文已加载的范围

`ExistingComponentContext.claim` 不允许接收一个未在 `from_datalink` 阶段加载过的 `kind`。

#### Scenario: 未加载的 kind 触发 claim 必须报错

- Given 上下文按"全局 DataLink 组件模型列表"加载完毕
- When compose 调用 `claim(kind, predicate)`，但该 `kind` 不在该全局列表中
- Then `claim` 必须直接抛错，而不是返回 `None`
- Because 这种情况意味着 compose 代码引用了未注册的组件 kind，应当作为编程错误尽早暴露
