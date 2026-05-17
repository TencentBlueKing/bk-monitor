## ADDED Requirements

### Requirement: NodemanInstaller status 接口必须与旧版 collecting 对齐
`bk-monitor-base` 的 `NodemanInstaller` MUST 提供与旧版 collecting `NodeManInstaller` 对齐的 `status(diff=False)` 方法签名。该接口 MUST 接受布尔参数 `diff`，默认值 MUST 为 `False`，并返回旧版 collecting 兼容的状态分组结构，而不是当前 base 的 `node_name/node_type/node_id` 结构。

#### Scenario: 调用方未传 diff 参数
- **WHEN** 调用方直接调用 `NodemanInstaller.status()`
- **THEN** 实现 MUST 按 `diff=False` 处理并返回旧版全量状态结构

#### Scenario: 调用方显式请求 diff 模式
- **WHEN** 调用方调用 `NodemanInstaller.status(diff=True)`
- **THEN** 实现 MUST 执行旧版差异比对逻辑，并返回带有 `label_name` 和 `is_label` 的旧版分组结果

### Requirement: diff 分类必须复刻旧版 DeploymentConfigVersion.show_diff 行为
当 `diff=True` 时，系统 MUST 使用旧版 `DeploymentConfigVersion.show_diff()` 的运行时行为来生成节点分类结果，而不是采用新的近似算法。该分类结果 MUST 支持 `ADD`、`REMOVE`、`UPDATE`、`RETRY` 四种内部类别，并满足旧版行为约束。

#### Scenario: 首次部署没有上一版本
- **WHEN** 当前部署版本不存在上一版本且调用 `status(diff=True)`
- **THEN** 当前版本的全部目标节点 MUST 被分类为 `ADD`

#### Scenario: 插件版本发生变化
- **WHEN** 上一版本与当前版本的插件版本不同且调用 `status(diff=True)`
- **THEN** 实现 MUST 按旧版行为将上一版本的全部目标节点分类为 `UPDATE`，且 MUST 不再继续执行节点级增删匹配

#### Scenario: 参数或远程采集范围变化但目标节点相同
- **WHEN** 当前节点与上一版本节点完全相等，但参数或远程采集范围发生变化
- **THEN** 这些匹配到的节点 MUST 被分类为 `UPDATE`

#### Scenario: 参数和远程采集范围都未变化
- **WHEN** 当前节点与上一版本节点完全相等，且参数与远程采集范围都未变化
- **THEN** 这些匹配到的节点 MUST 被分类为 `RETRY`

#### Scenario: 目标节点有新增或删除
- **WHEN** 当前版本与上一版本存在未匹配的新节点或旧节点
- **THEN** 未匹配的新节点 MUST 被分类为 `ADD`，未匹配的旧节点 MUST 被分类为 `REMOVE`

#### Scenario: 构造最终返回结果
- **WHEN** `status(diff=True)` 根据节点分类构造最终输出
- **THEN** 实现 MUST 保持与旧版一致，不在最终返回中输出 `REMOVE` 节点分组

### Requirement: status 结果中的实例字段必须与旧版 collecting 完全兼容
无论 `diff` 是否开启，`status()` 返回的每个实例对象 MUST 使用旧版 collecting 的字段集合和字段语义。实现 MUST 从节点管理任务结果、当前部署版本和部署状态中补齐旧版所需字段，不得直接暴露 base 当前的原始实例结构。

#### Scenario: 主机实例字段转换
- **WHEN** 节点管理结果中的实例是主机实例
- **THEN** 返回结果 MUST 包含 `instance_id`、`ip`、`bk_cloud_id`、`bk_host_id`、`bk_host_name`、`bk_supplier_id`、`task_id`、`status`、`plugin_version`、`log`、`action`、`steps`、`scope_ids`、`instance_name`、`bk_module_ids`

#### Scenario: 服务实例字段转换
- **WHEN** 节点管理结果中的实例是服务实例
- **THEN** 返回结果 MUST 包含主机公共字段以及 `instance_name`、`service_instance_id`、`bk_module_id`

#### Scenario: 运行中状态转换
- **WHEN** 节点管理返回实例状态为旧版定义的运行中间态，且部署动作是启动或停止
- **THEN** 返回结果 MUST 按旧版规则将状态转换为 `STARTING` 或 `STOPPING` 等兼容展示状态

#### Scenario: 日志字段转换
- **WHEN** 节点管理返回某个步骤或子步骤失败
- **THEN** 返回实例的 `log` 字段 MUST 使用旧版的 `"步骤名-子步骤名"` 形式，而不是原始错误日志文本

### Requirement: status 分组结果必须按旧版 target_node_type 语义组织
`status()` 的最终分组 MUST 以当前部署版本的 `target_node_type/target_nodes` 为基准，而不是以 `remote_scope` 为展示目标。返回的每个分组对象 MUST 使用旧版字段 `node_path`、`label_name`、`is_label` 和 `child`。

#### Scenario: HOST 目标且 diff=False
- **WHEN** 当前部署目标是主机实例且调用 `status(diff=False)`
- **THEN** 实现 MUST 返回单个 `node_path` 为 `"主机"` 的分组，且 `label_name` MUST 为空字符串、`is_label` MUST 为 `False`

#### Scenario: HOST 目标且 diff=True
- **WHEN** 当前部署目标是主机实例且调用 `status(diff=True)`
- **THEN** 实现 MUST 按 diff 类型拆分多个 `"主机"` 分组，并在每个分组上填充对应的 `label_name`

#### Scenario: TOPO 目标
- **WHEN** 当前部署目标是拓扑节点且调用 `status()`
- **THEN** 每个结果分组 MUST 使用旧版拓扑路径字符串作为 `node_path`

#### Scenario: DYNAMIC_GROUP 目标
- **WHEN** 当前部署目标是动态分组且调用 `status()`
- **THEN** 每个结果分组 MUST 使用旧版 `"动态分组"` 作为 `node_path`，并保留 `dynamic_group_name` 与 `dynamic_group_id`

#### Scenario: SERVICE_TEMPLATE 或 SET_TEMPLATE 目标
- **WHEN** 当前部署目标是服务模板或集群模板且调用 `status()`
- **THEN** 实现 MUST 先按旧版规则将模板展开为对应拓扑节点，再基于展开后的节点构造分组结果

### Requirement: status 必须保留旧版历史兼容规则
为了保证与旧版 collecting 完全兼容，`status()` MUST 保留旧版中的历史兼容处理，不得因为 base 当前已有更规整的数据模型而省略这些逻辑。

#### Scenario: 主机目标使用旧格式节点
- **WHEN** 当前或上一版本的主机目标节点使用 `ip/bk_cloud_id` 而不是 `bk_host_id`
- **THEN** 实现 MUST 在做 diff 之前先按旧版逻辑将其归一化为 `bk_host_id`，并过滤无法映射的节点

#### Scenario: 动态分组状态回填
- **WHEN** 当前部署目标是动态分组
- **THEN** 实现 MUST 先查询动态分组成员，再基于实例的 `bk_host_id` 将实例挂载回对应分组

#### Scenario: 临时关联字段清理
- **WHEN** 实例已经完成节点关联和结果分组
- **THEN** 最终返回结果 MUST 不包含仅用于内部关联的临时字段
