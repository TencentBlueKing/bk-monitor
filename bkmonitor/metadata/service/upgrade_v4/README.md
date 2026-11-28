# 单租户 V4 升级散件

用于 3.9.x 单租户原地升级。只提供检查、注册、分场景建链、路由发布和显式收尾函数，**没有跨场景总流程、管理命令或定时执行入口**。数据迁移指链路及元数据接入，不搬迁历史样本，不转换 Grafana/策略，也不创建旧查询别名。

## 调用约定

在 Metadata Django 环境中导入 `metadata.service.upgrade_v4`。

- 批量场景的 ID 参数 `None` 表示该场景范围内全部对象，`[]` 表示不执行；传列表表示局部执行。平台内置指标、集群注册、Transfer 收尾和拨测部署要求显式列表。
- `migrate_*` 申请/更新 V4 组件，复用已保存身份，失败后可以用原参数重跑。不以本地已有记录作为远端申请成功的证明。
- 不修改旧 DataID 的 Kafka/Topic，不重置采集订阅，不启用停用数据源/结果表。拨测新独立 DataID 是例外：通过原有申请接口创建，并保留共享旧 DataID。
- 建链不会主动改变原数据源 `created_from`，也不会清理 Transfer；`finalize_transfer()` 是独立函数，必须由调用者在核查与消费交接后显式调用。已经是 BKDATA 的来源不会被改回 BKGSE。
- 建链会下发 Databus，**并非无副作用的 dry-run**。沿用 Transfer 消费组时会与运行中的 Transfer 分摊消费，消费交接必须由调用者安排。此模块不实现双写、停流或自动回滚。
- 批量返回 `results`（每项成功/失败/跳过）和 `routes`。一项失败继续处理其他项，失败项可能已有部分本地或远端变更；重跑原参数恢复。`success=True` 表示函数执行成功，不等于入库或连续性验收通过。
- 停用对象返回跳过或不纳入自动选择，不应将其纳入 `finalize_transfer` 清单。
- `bk_tenant_id` 默认 `system`，模块只用于单租户；系统内置和拨测入口固定使用 `system`。

## 前置检查与注册（各自独立）

| 函数 | 行为 |
|---|---|
| `check_settings()` | 只读返回单租户、V4 开关和默认计算平台业务 |
| `check_cluster_registration(cluster_ids=None)` | 从 BKBase 查询选中集群实际注册状态；Kafka 检查 `bkmonitor`、`bklog`，同 kind/namespace 只查询一次；不会读取或返回集群凭据 |
| `check_data_sources(data_ids=None)` | 只读列出 ETL、启用状态、归属、Kafka 和 Topic；缺失 Topic 等异常向调用者抛出 |
| `register_kafka_to_gse(cluster_ids)` | 显式注册选定 Kafka 到 GSE；不串联 BKBase 注册 |
| `register_clusters(cluster_ids, namespaces=None)` | 将选定集群重复 apply 到 BKBase；不改变默认集群；可选择 namespace，空列表不执行 |
| `check_data_link(data_id)` | 查询已登记 DataId 和该 DataID 下各链路组件的远端状态；不等待、不做数据验收或收尾 |

Kafka 必须先有有效 GSE streamToId，再向 BKBase 注册。VM/ES 也需事先部署并登记到监控元数据；此模块不创建物理存储集群，不代替存储连通性/容量检查。注册函数保留已有 `ClusterConfig` 行为和字段语义。

```python
from metadata.service import upgrade_v4 as upgrade

upgrade.check_settings()
upgrade.check_cluster_registration(cluster_ids=[1, 2])
# 下列均为独立操作，不要求连续调用；ID 替换为目标环境实际清单。
upgrade.register_kafka_to_gse(cluster_ids=[1])
upgrade.register_clusters(cluster_ids=[1], namespaces=["bkmonitor", "bklog"])
```

## 各场景入口

| 函数 | 范围与参数 |
|---|---|
| `migrate_host_metrics(vm_cluster_name=...)` | settings 指定的共享基础采集 DataID；保持 `system.*` 及单租户 VMRT 映射 |
| `migrate_system_processes(data_ids=None, vm_cluster_name=...)` | 全部或选定的性能/端口系统 DataID，保持原系统表 |
| `migrate_system_events()` | settings 指定的系统事件 DataID，使用原 ES 集群和表 |
| `migrate_plugins(data_ids=None, vm_cluster_name=...)` | `bk_exporter` / `bk_standard` 普通插件；支持默认表和旧多表字段准备；复用原命令字段整理，不执行其兼容别名、路由和清理流程 |
| `prepare_plugin(data_id, vm_cluster_name=...)` | 仅准备默认表/TimeSeriesGroup/指标维度，返回准备上下文；不申请 Databus |
| `migrate_metric(data_id, vm_cluster_name=...)` | 单个标准时序/插件 DataID 接入；不刷新路由，供调用者组合 |
| `migrate_custom_metrics(data_ids=None, bk_biz_ids=None, vm_cluster_name=...)` | 选中 TimeSeriesGroup 的标准时序接入；也可用于业务进程指标组；不支持的 ETL 逐项报错 |
| `migrate_builtin_metrics(data_ids, vm_cluster_name=...)` | 按明确的环境 DataID 清单接入平台自监控/统计指标 |
| `migrate_custom_formats(table_ids=None)` | 使用已配置的 `custom_format_v4_data_link`，只开启原有选项并应用；不推测清洗规则或目标存储 |
| `migrate_event(data_id)` | 单个标准事件组接入，不刷新路由，保留原存储 |
| `migrate_custom_events(data_ids=None, bk_biz_ids=None)` | 选中 EventGroup 接入，包含符合标准事件 ETL 的事件插件 |
| `migrate_containers(cluster_ids=None, bk_biz_ids=None, vm_cluster_name=..., metrics=True, events=True)` | 非删除集群的 K8s/Custom Metric 和 K8s/Custom Event；按 DataID 去重，可仅执行指标或事件 |
| `migrate_uptimechecks(task_ids=None, bk_biz_ids=None, vm_cluster_name=...)` | 按业务/协议去重准备独立数据链路，不修改任务标志或部署任务 |
| `switch_uptimecheck_tasks(task_ids, deploy=False)` | 验收后切换指定任务的独立 DataID 标志；`deploy=True` 仅请求重下发当前运行中的任务，返回 `deploy_requested` 和原始接口响应 |
| `deploy_uptimecheck_tasks(task_ids)` | 显式部署指定任务（可能启动停用任务），供选定对象下发或失败重试；不自动枚举其他任务 |
| `finalize_transfer(data_ids)` | 调用者确认后切为 BKDATA 并删 Transfer 配置；清理失败可重入，已为 BKDATA 时仍重试清理 |

主机、系统进程、系统事件可通过 `data_bk_biz_id` 指定计算平台业务，默认沿用配置。指标入口要求显式 `vm_cluster_name`，不隐式重选默认 VM。

插件准备对不支持的固定 schema 默认表等情况报错，不自动改写旧表结构。普通时序多结果表应先使用对应准备入口，不能用多个同组 Databus 各自写单表。本模块不删除旧表，不提供联邦拓扑升级编排；联邦资源需要按现有专用入口处理，不能将其当作普通采集链路强制重建。

拨测准备通过既有 DataID 申请接口创建缺失来源，结果表和组使用无异步建链/路由的准备路径。`switch_uptimecheck_tasks` 不确认远端入库成功；先核查链路与目标任务，再选择下发。下发异常时可使用 `deploy_uptimecheck_tasks` 显式重试，不能仅用当前任务状态推断之前是否已经下发。

## 路由刷新

批量入口接受 `route_refresh` 和 `is_publish`，每个批次在末尾合并成功对象的 RT/space；单 DataID 的 `migrate_metric`、`migrate_event` 和 `prepare_plugin` 不刷新。

| `route_refresh` | 行为 |
|---|---|
| `none` | 不刷新，返回待刷新的 RT/空间，供多批合并 |
| `rt` | 仅指定 RT 详情 |
| `data_label` | 仅指定 RT 对应的标签路由 |
| `rt_and_data_label`（默认） | 指定 RT 详情和标签，不刷新 space |
| `all` | RT/标签和本批关联空间；每个空间去重后只刷新一次，不表示全租户 |

`is_publish=True` 默认传给原路由接口。BMW 开关开启时仍遵循既有接口行为；这里不改写 worker 的发布语义。空 RT 列表不会传给底层“空列表即全量”的接口。RT 刷新不附带整个租户的预计算规则。

```python
from metadata.service import upgrade_v4 as upgrade

# 场景局部执行，只发布 RT 与标签。
report = upgrade.migrate_plugins(data_ids=[123], vm_cluster_name="vm_default")

# 同场景整体执行，暂不刷路由。注意 None 与 [] 的区别。
report = upgrade.migrate_custom_events(data_ids=None, bk_biz_ids=[2], route_refresh="none")

# 可跨批累计成功记录，由调用者在选定时点发布；空间在此统一去重。
successes = [item for item in report["results"] if item["success"] and not item.get("skipped")]
upgrade.refresh_routes(
    table_ids=[table for item in successes for table in item["table_ids"]],
    spaces=[space for item in successes for space in item["spaces"]],
    mode="all",
)

# 若已逐批发布 RT/标签，只补空间即可，不再次刷 RT。
upgrade.refresh_routes(spaces=[("bkcc", "2")], mode="all")
```

以上片段展示独立函数用法，不是建议直接串跑的整体升级脚本。`finalize_transfer` 不自动等待就绪或校验数据，需核对同 DataID 的全部目标；不能只迁完其中一个使用方便删除整条 Transfer 配置。路由刷新异常向调用者抛出，不代表之前的组件申请未执行；可单独重试 `refresh_routes`。

## 验证边界

定向测试覆盖副作用、失败重入、批次局部失败、路由模式、空列表、空间去重、显式收尾和拨测停用状态。使用隔离 Django 配置，BKBase、Redis、GSE、节点管理等外部接口被 mock；不代表真实环境入库、消费连续性或采集部署已验收。正常项目测试启动在当前环境有既有 `URLField` JSON 序列化错误，未通过修改业务配置绕开。
