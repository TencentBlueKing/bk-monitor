## Why

`bk-monitor-base` 当前的 `NodemanInstaller.status()` 只能返回节点管理的最新全量状态，无法表达当前部署版本相对上一版本的目标差异，这使得上层无法复用 collecting 模块既有的 `diff` 语义。现在需要把 base 层的状态查询能力补齐到与 `bkmonitor` collecting 模块旧版 `NodeManInstaller.status(diff)` 完全兼容，避免同一类部署在不同实现间出现状态视图、字段结构和比对逻辑漂移。

## What Changes

- 为 `bk-monitor-base` 的 `NodemanInstaller.status` 增加 `diff` 模式，支持按当前版本与上一版本的目标范围差异输出旧版定义的 `ADD`、`REMOVE`、`UPDATE`、`RETRY` 语义分组。
- 调整 `NodemanInstaller.status` 的方法签名和返回契约，使其与 `bkmonitor/packages/monitor_web/collecting/deploy/node_man.py` 中旧版 `NodeManInstaller.status(diff=False)` 的参数、默认值、返回字段和分组方式完全对齐。
- 在 `diff=True` 场景补齐主机、拓扑、动态分组、服务模板、集群模板等目标类型的差异归类和节点聚合逻辑。
- 复用部署版本记录补齐“当前版本 / 上一版本”对比所需的上下文，并明确无上一版本时的首版部署行为。
- 将旧版代码中的兼容细节纳入契约，包括历史主机 `ip/bk_cloud_id -> bk_host_id` 归一化、模板节点展开、动态分组主机关联和 `removed` 节点在返回结果中的处理方式。
- **BREAKING**：`bk-monitor-base` 的 `NodemanInstaller.status` 调用方式与返回结构将从“仅返回当前全量状态”调整为支持 `diff` 参数的兼容旧版语义接口，不再维持当前签名。

## Capabilities

### New Capabilities
- `nodemaninstaller-status-diff`: 为 base 层 NodemanInstaller 提供与 collecting 旧版完全兼容的状态查询、diff 比对和分组输出能力。

### Modified Capabilities

## Impact

- 受影响代码主要位于 `bk-monitor-base/src/bk_monitor_base/domains/metric_plugin/installer/nodeman.py` 及其相关的部署版本查询、CMDB 节点聚合和节点管理状态转换逻辑。
- 该变更会影响调用 `NodemanInstaller.status` 的上层接口与测试用例，调用方需要按旧版 collecting 兼容语义使用 `diff` 参数并接受旧版结构化返回。
- 不引入新的外部依赖，但会增加对历史部署版本、目标范围差异计算和节点映射逻辑的依赖深度。
