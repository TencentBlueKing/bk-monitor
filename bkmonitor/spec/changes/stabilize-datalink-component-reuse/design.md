# Design: DataLink 组件名称复用与稳定映射

## 现状

`DataLink.apply_data_link` 当前流程是：

1. 创建/获取 `BkBaseResultTable`
2. 调用 `compose_configs`
3. `compose_*_configs` 内部按固定 name 执行 `update_or_create`
4. 生成配置并调用 `apply_data_link_with_retry`

核心问题不在 BKBase API，而在 compose 阶段已经把“固定 name”固化到了本地 ORM 和下发配置里。

如果只在 compose 完成后再重写配置里的 `metadata.name`，会留下两个问题：

- 本地组件表中已经提前创建了新 name 记录；
- 本地记录与 BKBase 实际配置 name 不一致，后续状态刷新、删除、排障都会偏移。

因此，复用决策必须先于 `update_or_create` 生效，而不是在最终 payload 上做补丁。

## 设计目标

- 复用前先做组件基数校验，但外层只提供通用辅助能力；
- 最终校验逻辑由各类 datalink 自行决定，而不是固化为一张全局策略表；
- 默认发现多余组件立即失败，少量显式放宽的场景由对应 datalink 自己负责定义；
- 复用决策发生在 `apply_data_link` 编排层；
- compose 分支在写库前就拿到 resolved name；
- 复用规则可解释、可测试、可重复；
- 对歧义场景宁可不复用，也不做不稳定的猜测性覆盖。

## 新的执行顺序

`apply_data_link` 后续应按如下顺序组织：

1. 预计算本次理论组件槽位
2. 查询当前 datalink 现有组件
3. 做组件基数校验
4. 校验通过后再生成 name 复用计划
5. 执行 compose + `update_or_create`
6. 调用 BKBase apply

这里“基数校验”必须前置于复用和写库，否则在已有脏数据的情况下继续 apply，仍可能制造更多重复组件。
但“校验是否失败”不能是全局一刀切，而应由当前 datalink 自己决定。

## 数据来源

复用候选来自 Metadata 本地库中当前 DataLink 已关联组件：

- 查询条件：`bk_tenant_id + namespace + data_link_name`
- 查询范围：`DataLink.STRATEGY_RELATED_COMPONENTS[self.data_link_strategy]`

原因：

- 这是“当前 datalink 关联的所有组件配置”的直接来源；
- 迁移导入后，组件间的归属关系已经通过 `data_link_name` 固化；
- 本地记录已经包含 `table_id`、`bkbase_result_table_name`、`sink_names` 等可用于稳定匹配的语义字段。

## 核心抽象

### 1. 组件逻辑槽位

在 compose 阶段不要只关心“生成什么 name”，还要显式表达“这是哪一个逻辑组件”。

建议抽象出逻辑槽位，至少包含：

- `kind`
- `generated_name`
- `logical_key`
- `table_id`
- `related_result_table_key`
- `data_id_name`

其中 `logical_key` 用来描述“该组件在链路中的稳定身份”，而不是最终 name。

这些逻辑槽位也会作为“理论组件数量”的直接来源。

### 2. 复用计划

`apply_data_link` 在 compose 前生成一个 `component_name_plan`，形式可为：

```python
{
    (kind, logical_key): resolved_name,
}
```

compose 分支通过统一 helper 获取最终 name：

```python
resolved_name = self.resolve_component_name(kind=..., logical_key=..., generated_name=...)
```

### 3. 组件基数校验

在生成复用计划前，需要先比对：

- `expected_slots_by_kind`
- `existing_components_by_kind`

外层辅助层负责：

- 统一收集理论槽位；
- 统一查询现有组件；
- 提供按 kind 分组、计数、筛选候选、构造错误信息等通用 helper；
- 将整理好的上下文交给当前 datalink 的校验方法。

当前 datalink 的校验方法负责：

- 决定哪些 kind 必须严格等于理论数量；
- 决定哪些 kind 允许“现有大于理论数量但保留旧组件”；
- 决定哪些超出组件可以忽略、哪些必须报错；
- 决定通过校验后哪些组件允许参与当前复用映射。

建议的默认语义仍然是：

- `exact_match`
  现有数量不能超过理论数量；适用于大多数固定组件。
- `allow_partial`
  现有数量可小于理论数量，允许后续补建；这是默认补齐行为的一部分，不是豁免超量。
- `allow_existing_superset`
  允许现有数量大于本次理论数量，但超出的既有组件仅保留、不参与本次 compose 复用，也不在本次 apply 中删除。

其中 `allow_existing_superset` 只应用于少量明确声明的场景，不能作为默认兜底。

例如：

- 标准时序链路：`ResultTable=1`、`StorageBinding=1`、`DataBus=1`
- 基础采集链路：数量虽多，但可由 `BASEREPORT_USAGES` 稳定推导
- 日志链路：ES/Doris Binding 数量由当前存储配置推导，但在一次 apply 中仍然是确定值
- 日志链路中的 `ESStorageBinding` / `DorisStorageBinding` 可采用 `allow_existing_superset`
  - 若本次 compose 因开关关闭不再生成某类 binding，允许旧 binding 继续留在当前 datalink 下
  - 这些旧 binding 不应在本次 apply 中被删除
  - 这些旧 binding 也不应强行参与本次生成配置的复用映射

### 4. datalink 自定义校验入口

建议不要把最终规则固化在全局注册表里，而是提供 datalink 级别的自定义校验入口。

例如：

```python
def validate_existing_components(self, validation_context) -> ValidationDecision:
    ...
```

其中外层负责准备 `validation_context`，而 `ValidationDecision` 至少应包含：

- 是否允许继续执行；
- 哪些 kind/组件应参与本次复用映射；
- 哪些现有组件需要被视为“保留但不参与本次复用”；
- 失败时的错误信息。

这样做的好处是：

- 规则与具体 datalink 语义更贴近；
- 后续新增特殊场景时不必修改全局表；
- 日志链路这类“数量变化是预期行为”的场景可以就地表达；
- 外层仍保留统一的辅助能力与错误格式。

## 匹配规则

### 优先级

对每个逻辑槽位，按以下顺序匹配既有组件：

1. 精确同名命中：`generated_name == existing.name`
2. 语义键精确匹配
3. 单候选回退复用
4. 否则新建

前提是：该 kind 已通过当前 datalink 的校验逻辑，并被允许参与本次复用。

### 语义键建议

不同组件类型使用不同的稳定键：

- `ResultTableConfig`
  - 首选：`table_id`
  - 次选：`generated_name`
- `VMStorageBindingConfig` / `ESStorageBindingConfig` / `DorisStorageBindingConfig`
  - 首选：`table_id`
  - 次选：`bkbase_result_table_name`
  - 再次选：`generated_name`
- `DataBusConfig`
  - 首选：`data_id_name + sink kind 集合`
  - 次选：当当前 datalink 下该类型仅存在一个候选且本次仅生成一个槽位时，直接复用
- `ConditionalSinkConfig`
  - 首选：当当前 datalink 下该类型仅存在一个候选且本次仅生成一个槽位时，直接复用
  - 次选：`generated_name`

### 歧义处理

若某个语义键对应多个候选，必须视为歧义，不可随机选取。

处理原则：

- 不做模糊匹配；
- 不按数据库自然顺序选第一个；
- 不按临时排序结果“赌”一个；
- 直接放弃复用该槽位，回退为新建。

这样虽然可能保守，但不会引入重复 apply 抖动。

若歧义本身来自“现有组件数量已经超过理论数量”，则是否允许继续执行取决于当前 datalink 的校验逻辑：

- 对默认严格策略，直接报错退出；
- 对 `allow_existing_superset`，超出部分仅保留，不进入当前逻辑槽位匹配。

## 稳定性约束

即使在多组件场景下，映射也必须可重复。

为此需要满足两点：

1. 候选集合排序稳定
2. 匹配键稳定

建议所有候选在参与匹配前统一按以下字段排序：

`table_id`, `bkbase_result_table_name`, `data_id_name`, `name`, `pk`

但排序只用于“确定遍历顺序”，不能代替语义匹配本身。

对于基础采集等多组件场景，真正的稳定性应来自 `table_id` 这类语义键，而不是 BASEREPORT usage 的循环顺序或 queryset 顺序。

但在进入稳定映射之前，仍必须先满足“当前 kind 已通过当前 datalink 校验并被允许参与复用”的前置条件。

## 对 compose 分支的改造要求

### 原则

compose 分支不能再把“固定 name”写死进 `update_or_create` 的查询条件。

应改为：

1. 先计算每个逻辑槽位的 `generated_name`
2. 再通过 resolver 得到 `resolved_name`
3. 最后以 `resolved_name` 执行 `update_or_create`

### 影响

以下分支都要接入统一 resolver：

- `compose_standard_time_series_configs`
- `compose_bk_plugin_time_series_config`
- `compose_bcs_federal_proxy_time_series_configs`
- `compose_bcs_federal_subset_time_series_configs`
- `compose_basereport_time_series_configs`
- `compose_base_event_configs`
- `compose_system_proc_configs`
- `compose_log_configs`
- `compose_custom_event_configs`

## 推荐落地方式

### 方案 A：在 `apply_data_link` 生成 name plan，并传入 compose

优点：

- 入口集中；
- 符合“在 apply_data_link 时做查询和规划”的需求；
- 易于单测。

建议新增 helper：

- `_plan_expected_components(...)`
- `_list_existing_components()`
- `_build_validation_context(...)`
- `_raise_component_validation_error(...)`
- `_validate_component_cardinality(...)`
- `_build_component_name_plan(...)`
- `_resolve_component_name(...)`

### 方案 B：先生成“组件草稿”，再统一落库

优点：

- 模型更干净，compose 与写库彻底分离。

缺点：

- 重构量更大；
- 不适合作为第一步改造。

本次建议优先采用方案 A。

## 测试策略

至少补充以下测试：

1. 单实例链路的多余组件场景
   - 当前 datalink 下某 kind 理论上只应有 1 个组件，但实际已有 2 个及以上
   - `apply_data_link` 应直接失败，不进入覆盖或补建

2. 单 RT 单 Binding 单 DataBus 的迁移复用场景
   - 当前 datalink 已有关联组件，但 name 与当前 compose 规则不同
   - 且现有数量未超限
   - `apply_data_link` 后应更新既有记录，不新增第二套组件

3. basereport 多 RT/多 Binding 的稳定复用场景
   - 既有组件通过 `table_id` 与新生成槽位对齐
   - 重复执行两次 `apply_data_link`，name 映射结果不变化

4. 允许保留历史组件的场景
   - 如日志链路中，某类 binding 因开关关闭，本次 compose 数量少于历史已有数量
   - 历史 binding 应允许保留
   - 本次 apply 不应删除这些旧组件
   - 本次 apply 也不应把这些旧组件强行纳入当前复用映射

5. 特殊链路中的严格组件超限场景
   - 即使在日志等特殊链路中，若某个 kind 仍被声明为严格校验
   - 一旦现有数量超过理论槽位数，仍应直接失败

6. 部分命中场景
   - 已有 1 个组件可复用，另 1 个不存在
   - 应只复用命中部分，缺失部分新建

7. 歧义场景
   - 同类型候选无法唯一匹配
   - 应放弃复用该槽位，避免错误覆盖

8. 日志链路双 sink 场景
   - ES 与 Doris 绑定分别按各自 kind 独立匹配

## 非本次处理

- 清理历史重复组件
- 自动修复跨 datalink 误关联
- DataId 侧的迁移命名兼容
- 直接对 BKBase 现网组件做全量扫描比对
