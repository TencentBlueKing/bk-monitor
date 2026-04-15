# Capability: DataLink 组件复用

## MODIFIED Requirements

### Requirement: apply_data_link 必须先校验组件数量是否超限

`DataLink.apply_data_link` 在执行组件复用、写库和下发 BKBase 配置前，必须先根据当前策略和上下文推导本次理论组件槽位，并提供统一的辅助能力给当前 datalink 进行组件数量校验。最终是否允许继续执行，由当前 datalink 的校验逻辑决定。

#### Scenario: 单实例链路出现多余组件

- Given 某类普通 datalink 在本次 apply 中理论上某个 kind 只应生成 1 个组件
- And 当前 `data_link_name` 下该 kind 已存在 2 个组件
- When 执行 `apply_data_link`
- Then 系统应直接报错并终止
- And 不得继续执行组件复用
- And 不得继续新建更多组件

#### Scenario: 特殊链路出现超出理论槽位的组件

- Given 某类特殊 datalink 在本次 apply 中理论上某个 kind 应生成 N 个组件
- And 当前 datalink 的校验逻辑将该 kind 视为严格数量校验
- And 当前 `data_link_name` 下该 kind 已存在大于 N 个组件
- When 执行 `apply_data_link`
- Then 系统应直接报错并终止
- And 不得以“尽量复用”方式继续覆盖

#### Scenario: 允许保留历史 binding 的场景

- Given 某类 datalink 的校验逻辑将某个 binding kind 视为允许保留历史组件
- And 当前 `data_link_name` 下该 kind 的历史组件数量大于本次 compose 理论数量
- When 执行 `apply_data_link`
- Then 系统不得因为这些历史组件直接报错
- And 超出的历史组件应保持不变
- And 超出的历史组件不得在本次 apply 中被删除
- And 超出的历史组件不得强行参与本次逻辑槽位复用

### Requirement: apply_data_link 必须优先复用当前 datalink 已关联组件

`DataLink.apply_data_link` 在准备下发 BKBase 配置前，必须查询当前 `data_link_name` 已关联的组件配置，并在新生成组件与既有组件属于同一逻辑槽位时优先复用既有组件的 `name`。

#### Scenario: 迁移后已有单组件链路

- Given 当前 datalink 已存在一组 `ResultTableConfig`、`VMStorageBindingConfig`、`DataBusConfig`
- And 这些组件的 `name` 与当前 compose 规则生成值不同
- And 这些组件数量未超出本次理论槽位数量
- When 再次执行 `apply_data_link`
- Then compose 阶段应使用既有组件的 `name`
- And 不应额外创建第二组同类型组件
- And 最终下发到 BKBase 的配置 `metadata.name` 应与本地复用后的 name 一致

#### Scenario: 仅部分组件可复用

- Given 当前 datalink 下只有部分同类型组件已存在
- And 当前已有组件数量未超出本次理论槽位数量
- When 执行 `apply_data_link`
- Then 可唯一匹配的组件应复用原 name
- And 缺失组件应按当前命名规则新建

### Requirement: 组件匹配必须稳定且与数据库返回顺序无关

当一个 datalink 下存在多个同类型组件时，复用逻辑必须依赖稳定的语义键，而不是 queryset 默认顺序、插入顺序或临时排序副作用。

#### Scenario: basereport 多结果表重复 apply

- Given basereport datalink 下存在多组 `ResultTableConfig` 与 `VMStorageBindingConfig`
- And 每组组件都带有稳定的 `table_id`
- When 连续两次执行 `apply_data_link`
- Then 同一个 `table_id` 对应的逻辑槽位应始终映射到同一个既有组件 name
- And 第二次执行不应因为顺序变化导致 name 重新覆盖

#### Scenario: 歧义候选存在

- Given 某个逻辑槽位对应多个无法唯一判定的既有候选
- And 当前该 kind 已通过当前 datalink 的数量校验逻辑
- When 执行 `apply_data_link`
- Then 系统不得随机选择其中一个复用
- And 该槽位应回退为按当前规则新建

### Requirement: 本地元数据与下发配置必须使用同一组 resolved name

一旦某个组件槽位决定复用既有组件 name，本地 ORM 更新和 BKBase 下发配置都必须使用同一个 resolved name。

#### Scenario: compose 后不可再做盲目 name 重写

- Given 组件 name 的复用计划已经生成
- When compose 分支写入本地组件记录并渲染 BKBase 配置
- Then `update_or_create` 应直接使用 resolved name
- And 不允许仅在最终 payload 上补丁式重写 name
- Because 这会导致本地记录与 BKBase 实际组件名称不一致
