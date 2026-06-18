# data_migrate 迁移后状态检查方案

## 背景

`data_migrate` 后需要同时确认新老环境在配置、数据链路、下发状态、数据状态上的差异。目标是先在 `packages/monitor_web/data_migrate/` 内实现独立 helper，后续再按需要暴露 API 或比对脚本，避免 API 层和脚本各自维护一套检查逻辑。

## 目标

1. 提供一个检查入口，返回单个业务在当前环境下的迁移状态快照。
2. 返回结构尽量稳定，方便后续 API 透传、脚本落盘、自动化比对。
3. 优先复用已有模型、resource、helper，不重复实现 data_id 发现和数据链路探测逻辑。
4. 采集入口只返回对象级明细，不在接口层预先统计数量、成功率、异常比例等汇总值；这类聚合由后续比对脚本基于明细计算。

## 建议文件

核心文件：

```text
packages/monitor_web/data_migrate/migration_status_check.py
```

规划文档：

```text
packages/monitor_web/data_migrate/migration_status_check_plan.md
```

API 暴露时只做薄封装，例如新增 resource 调用 `collect_migration_status`，不要把检查逻辑写进 view/resource。

## 总体入口设计

### 采集当前环境状态

```python
def collect_migration_status(
    *,
    bk_tenant_id: str,
    bk_biz_id: int,
    start_time: int | None = None,
    end_time: int | None = None,
    with_detail: bool = False,
) -> dict:
    ...
```

参数说明：

| 参数 | 说明 |
| --- | --- |
| `bk_tenant_id` | 租户 ID |
| `bk_biz_id` | 业务 ID，先按单业务实现，脚本层可循环多个业务 |
| `start_time` / `end_time` | 数据检查窗口，秒级时间戳；不传则默认最近 1 小时 |
| `with_detail` | 是否返回底层配置详情，例如 bkbase config、组件配置 |

## 总体返回结构

```json
{
  "bk_tenant_id": "system",
  "bk_biz_id": 2,
  "time_range": {
    "start_time": 1710000000,
    "end_time": 1710003600
  },
  "checks": {
    "host": {},
    "k8s": {},
    "uptime_check": {},
    "custom_report": {},
    "plugin_collect": {},
    "apm": {},
    "strategy": {}
  },
  "errors": []
}
```

每个检查项内部都建议包含：

| 字段 | 说明 |
| --- | --- |
| `items` | 具体对象列表，或按对象类型命名的列表，例如 `tasks` / `clusters` / `applications` |
| `data_links` | data_id / kafka / bkbase / 查询路由状态。该字段只在对应场景确实需要时返回 |
| `rt_statuses` | result table 是否存在、是否有近窗口数据 |
| `errors` | 单检查项失败信息 |

统计类字段不放在采集返回中，例如 `task_count`、`running_count`、`avg_available`、`no_data_count`。
后续比对脚本需要时从对象明细中即时计算，避免采集 API 和比对逻辑重复维护口径。

### 并发执行

检查过程包含 Kafka tail、BKAPI、PromQL、日志查询和节点管理接口调用，整体耗时会随对象数量线性增长。实现上需要两层并发：

| 层级 | 并发上限 | 说明 |
| --- | --- | --- |
| 顶层检查项 | `DEFAULT_CHECK_WORKERS = 4` | 并发执行 host / k8s / uptime / custom_report / plugin_collect / apm / strategy 等检查 |
| 对象级检查 | `DEFAULT_ITEM_CHECK_WORKERS = 8` | 同类检查内按集群、采集配置、自定义上报、APM 应用等对象并发 |

并发实现使用仓内 `bkmonitor.utils.thread_backend.ThreadPool`，由线程池继承当前租户、时区、语言和 trace 上下文，并在线程结束后关闭 DB 连接。并发结果按输入顺序回收，避免返回明细顺序随机抖动。

## 公共能力

### 对象发现

优先复用：

```python
from monitor_web.data_migrate.biz_matadata import find_biz_table_and_data_id
```

用途：

- 汇总业务关联的 result table 和 data_id。
- 避免每个检查项重复维护 data_id 收集规则。
- 当前已覆盖自定义上报、普通插件、事件插件、K8S、进程插件、日志、拨测、APM。

### 数据链路检查

注意：

- data_id Kafka 状态直接走 `api.metadata.kafka_tail(..., use_gse_config=True)` 的 GSE 配置查询模式。
- 单租户场景下，尤其是主机基础数据、进程性能、进程端口，应优先对业务发起 PromQL 数据查询，确认是否真实有数据和上报对象数量。
- 多租户场景下，再额外检查业务对应 data_id 是否创建、Kafka 是否有数据、查询路由是否可用。

已有能力：

| 函数 | 用途 |
| --- | --- |
| `api.metadata.kafka_tail(..., use_gse_config=True)` | 按 data_id 通过 GSE 路由配置探测 Kafka 是否有数据 |

### RT 数据检查

新增 helper：

```python
def query_result_table_recent_data_status(
    *,
    bk_tenant_id: str,
    bk_biz_id: int,
    table_id: str,
    data_source_label: str,
    data_type_label: str,
    start_time: int,
    end_time: int,
) -> dict:
    ...
```

建议返回：

| 字段 | 说明 |
| --- | --- |
| `table_id` | 结果表 ID |
| `exists` | metadata ResultTable 是否存在 |
| `has_data` | 查询窗口内是否有数据 |
| `latest_time` | 能取到最新时间时返回 |
| `sample` | 必要时返回一条轻量样本，避免大字段 |
| `message` | 查询失败原因 |

实现策略：

- 时序数据优先用 `UnifyQuerySet` / `QueryConfigBuilder` 做有无数据或最新一条查询。
- 事件 / 日志可参考 `CustomEventGroup.query_event_detail` 使用 `UnifyQuerySet`。
- 若某类 RT 查询参数无法稳定组装，第一阶段可以返回 `exists=True`、`has_data=None`、`message="unsupported"`，同时依赖 Kafka tail 判断 data_id 是否有数据。

### 异常隔离

每个检查项用 `safe_call` 包一层，单项失败不影响整体：

```python
def safe_check(check_name: str, func: Callable[[], dict]) -> dict:
    try:
        return func()
    except Exception as error:
        return {"items": [], "errors": [{"check": check_name, "message": str(error)}]}
```

## 检查项 1：主机数据

主机数据以 PromQL 查询为主，直接对特定业务的主机基础数据、进程性能数据、进程端口数据做有无数据和上报主机数量检查。
该检查项不返回 data_id / bkdata / Kafka 链路状态。

### 需要返回的字段

```json
{
  "promql_checks": {
    "host_metric": {
      "promql": "",
      "has_data": false,
      "host_count": 0,
      "message": ""
    },
    "process_perf": {
      "promql": "",
      "has_data": false,
      "host_count": 0,
      "message": ""
    },
    "process_port": {
      "promql": "",
      "has_data": false,
      "host_count": 0,
      "message": ""
    }
  }
}
```

`host_count` 只按 `bk_target_ip + bk_target_cloud_id` 去重计数，不返回具体 IP / 进程名明细。

### PromQL 检查项

建议封装一个公共函数：

```python
def query_promql_host_count(
    *,
    bk_biz_id: int,
    promql: str,
    start_time: int,
    end_time: int,
    interval: int = 60,
) -> dict:
    ...
```

查询实现优先复用现有 Prometheus 数据源：

```python
data_source_class = load_data_source(DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES)
data_source = data_source_class(bk_biz_id=bk_biz_id, promql=promql, interval=interval)
query = UnifyQuery(bk_biz_id=bk_biz_id, data_sources=[data_source], expression="")
records = query.query_data(start_time=start_time * 1000, end_time=end_time * 1000)
```

PromQL 示例：

| 检查 | RT / 指标 | PromQL 示例 | group by |
| --- | --- | --- | --- |
| 主机基础数据 | `system.cpu_summary` / `usage` | `sum by (bk_target_ip, bk_target_cloud_id) (count_over_time(system:cpu_summary:usage[5m]))` | `bk_target_ip`, `bk_target_cloud_id` |
| 进程性能数据 | `system.proc` / `cpu_usage_pct` | `sum by (bk_target_ip, bk_target_cloud_id, display_name) (count_over_time(system:proc:cpu_usage_pct[5m]))` | `bk_target_ip`, `bk_target_cloud_id`, `display_name` |
| 进程端口数据 | `system.proc_port` / `proc_exists` | `sum by (bk_target_ip, bk_target_cloud_id, display_name) (count_over_time(system:proc_port:proc_exists[5m]))` | `bk_target_ip`, `bk_target_cloud_id`, `display_name` |

说明：

- 具体窗口长度用接口参数控制，示例里的 `[5m]` 可按 `start_time/end_time` 推导。
- `bk_biz_id` 不建议直接拼入 PromQL label，优先通过 `data_source_class(bk_biz_id=...)` 和 `UnifyQuery(bk_biz_id=...)` 进行业务范围约束。
- 进程端口已有类似用法可参考 `TopoNodeProcessStatusResource` 中 `system:proc_port:proc_exists{...}`。
- 如某环境 PromQL metric name 需要 `bkmonitor:` 前缀，应在 helper 内统一兼容，不要散落到各检查项。

### 数据来源

| 数据 | 来源 |
| --- | --- |
| CMDB 主机数 | `api.cmdb.get_host_by_topo_node(bk_biz_id=bk_biz_id)`，只做参考 |
| 主机基础数据 | PromQL 查询 `system.cpu_summary`，按 `bk_target_ip` / `bk_target_cloud_id` 聚合 |
| 进程性能数据 | PromQL 查询 `system.proc`，按 `bk_target_ip` / `bk_target_cloud_id` / `display_name` 聚合 |
| 进程端口数据 | PromQL 查询 `system.proc_port`，按 `bk_target_ip` / `bk_target_cloud_id` / `display_name` 聚合 |

按固定系统表发起数据查询：

```text
system.cpu_summary
system.proc
system.proc_port
```

不要直接套多租户 data_name 规则判断单租户主机数据。

### 比对规则

涉及上报主机数量差异的规则，由比对脚本基于 `host_count` 计算。

| 规则 | 级别 |
| --- | --- |
| 老环境 `host_metric.host_count > 0`，新环境为 0 | fatal |
| 新环境主机基础数据上报数量明显少于老环境 | warning / fatal，按阈值 |
| 老环境进程性能有数据，新环境无数据 | warning / fatal |
| 老环境进程端口有数据，新环境无数据 | warning / fatal |

## 检查项 2：容器集群数据状态

容器集群先按 `BCSClusterInfo` 做必查，核心只关注 `K8sMetricDataID`、`CustomMetricDataID`、`K8sEventDataID`。
重点回答四个问题：

1. 集群记录和状态是否存在、是否正常。
2. 三类核心 data_id 是否创建，非 0 的 data_id 是否有 Kafka 数据。
3. 集群本身是否能联通，是否能读到 DataID 资源。
4. k8s 指标、自定义指标、事件数据是否已经最终落地到查询侧。

### 需要返回的字段

```json
{
  "clusters": [
    {
      "cluster_id": "",
      "bcs_api_cluster_id": "",
      "bk_biz_id": 0,
      "bk_tenant_id": "",
      "project_id": "",
      "status": "",
      "bk_env": "",
      "operator_ns": "",
      "data_ids": {
        "k8s_metric": {
          "field": "K8sMetricDataID",
          "data_id": 0,
          "exists": false,
          "has_kafka_data": false,
          "latest_time": null,
          "message": ""
        },
        "custom_metric": {
          "field": "CustomMetricDataID",
          "data_id": 0,
          "exists": false,
          "has_kafka_data": false,
          "latest_time": null,
          "sample_metric": "",
          "sample_bcs_cluster_id": "",
          "message": ""
        },
        "k8s_event": {
          "field": "K8sEventDataID",
          "data_id": 0,
          "exists": false,
          "has_kafka_data": false,
          "latest_time": null,
          "message": ""
        }
      },
      "extra_data_ids": {
        "custom_event_data_id": 0,
        "system_log_data_id": 0,
        "custom_log_data_id": 0
      },
      "cluster_connectivity": {
        "api_versions_ok": false,
        "dataid_resource_query_ok": false,
        "expected_resource_names": [],
        "existing_resource_names": [],
        "missing_resource_names": [],
        "error": ""
      },
      "k8s_metric_landing": {
        "promql": "avg(bkmonitor:container_cpu_usage_seconds_total) by (bcs_cluster_id)",
        "has_data": false,
        "value": null,
        "message": ""
      },
      "custom_metric_landing": {
        "sample_metric": "",
        "sample_bcs_cluster_id": "",
        "promql": "",
        "has_data": false,
        "value": null,
        "message": ""
      },
      "event_landing": {
        "has_kafka_event": false,
        "has_query_event": null,
        "latest_time": null,
        "sample": {},
        "message": ""
      }
    }
  ]
}
```

每个集群的 `data_ids` 只放需要真正检查的三类核心 data_id：

| 字段 | 来源 |
| --- | --- |
| `k8s_metric_data_id` | `BCSClusterInfo.K8sMetricDataID` |
| `custom_metric_data_id` | `BCSClusterInfo.CustomMetricDataID` |
| `k8s_event_data_id` | `BCSClusterInfo.K8sEventDataID` |

其余历史字段只放在 `extra_data_ids` 中展示原始值，不做数据检查和比对判断：

| 字段 | 来源 |
| --- | --- |
| `custom_event_data_id` | `BCSClusterInfo.CustomEventDataID` |
| `system_log_data_id` | `BCSClusterInfo.SystemLogDataID` |
| `custom_log_data_id` | `BCSClusterInfo.CustomLogDataID` |

### 数据来源

| 数据 | 来源 |
| --- | --- |
| 集群基础信息 | `metadata.models.BCSClusterInfo` |
| data_id 是否存在 | `metadata.models.DataSource` |
| Kafka 是否有数据 / 样本 | `api.metadata.kafka_tail(bk_tenant_id=..., bk_data_id=..., size=3, use_gse_config=True)` |
| 集群 API 连通性 | `BCSClusterInfo.api_client` / `BCSClusterInfo.get_api_class()` |
| 集群 DataID 资源 | `kubernetes.client.CustomObjectsApi(cluster.api_client).list_cluster_custom_object(...)` |
| DataID 资源配置常量 | `metadata.config.BCS_RESOURCE_GROUP_NAME` / `BCS_RESOURCE_VERSION` / `BCS_RESOURCE_DATA_ID_RESOURCE_PLURAL` |
| DataID 资源名称 | `BCSClusterInfo.compose_dataid_resource_name(...)` |
| 代表性 k8s 指标落地 | PromQL：`avg(bkmonitor:container_cpu_usage_seconds_total) by (bcs_cluster_id)` |
| 自定义指标落地 | 从 `CustomMetricDataID` Kafka 样本解析 metric 名，再发 PromQL 抽查 |
| 事件结果表 | `metadata.models.DataSourceResultTable` 或 `metadata.models.custom_report.EventGroup` |
| 事件落地 | `DataTypeLabel.EVENT + DataSourceLabel.CUSTOM` 的事件检索逻辑 |

### 可复用函数

```python
from kubernetes import client as k8s_client

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api, resource
from metadata import config
from metadata.models import BCSClusterInfo, DataSourceResultTable
from metadata.models.custom_report import EventGroup
```

本检查对单个 data_id 只直接使用 GSE Kafka tail 判断是否有 Kafka 数据。

### 获取逻辑

#### 1. 读取集群和核心 data_id

按业务过滤：

```python
clusters = BCSClusterInfo.objects.filter(bk_biz_id=bk_biz_id)
```

每个集群读取：

```python
data_id_fields = {
    "k8s_metric": "K8sMetricDataID",
    "custom_metric": "CustomMetricDataID",
    "k8s_event": "K8sEventDataID",
}

extra_data_id_fields = {
    "custom_event_data_id": "CustomEventDataID",
    "system_log_data_id": "SystemLogDataID",
    "custom_log_data_id": "CustomLogDataID",
}
```

对每个非 0 的核心 data_id 调用：

```python
sample_data = api.metadata.kafka_tail(
    bk_tenant_id=cluster.bk_tenant_id,
    bk_data_id=data_id,
    size=3,
    use_gse_config=True,
)
```

记录 `exists`、`has_kafka_data`、`message`。Kafka 样本只允许内部临时用于抽取 `sample_metric`，不返回原始 Kafka 消息。
`extra_data_id_fields` 只读取数值展示，不调用 Kafka tail。

#### 2. 检查集群状态和连通性

集群状态直接返回 `BCSClusterInfo.status`，重点标出：

| 状态 | 判断 |
| --- | --- |
| `RUNNING` / `running` | 正常 |
| `DELETED` / `deleted` | 已删除，默认 warning |
| `init_failed` | 初始化失败，默认 fatal |
| 其他状态 | warning，需要人工确认 |

连通性参考 `BCSClusterInfo.init_resource()` 的资源访问方式，但检查逻辑必须只读，不做 `ensure_data_id_resource(...)` 写入。

建议实现 `check_cluster_dataid_resources(cluster)`：

```python
# 先探测 API version，失败时 api_versions_ok=false。
cluster.get_api_class()

# 再只读查询 DataIDResource，失败时 dataid_resource_query_ok=false。
custom_client = k8s_client.CustomObjectsApi(cluster.api_client)
resource_list = custom_client.list_cluster_custom_object(
    group=config.BCS_RESOURCE_GROUP_NAME,
    version=config.BCS_RESOURCE_VERSION,
    plural=config.BCS_RESOURCE_DATA_ID_RESOURCE_PLURAL,
)
```

如果这个调用报错，说明集群 API 或 DataID CRD 资源不可访问，返回 `dataid_resource_query_ok=false` 和异常信息。

预期资源名称从 `BCSClusterInfo.DATASOURCE_REGISTER_INFO` 生成：

```python
expected_resource_names = [
    cluster.compose_dataid_resource_name(item["datasource_name"].lower())
    for item in cluster.DATASOURCE_REGISTER_INFO.values()
    if getattr(cluster, item["datasource_name"], 0)
]
```

当前 `DATASOURCE_REGISTER_INFO` 覆盖：

| usage | data_id 字段 | 资源名来源 |
| --- | --- | --- |
| `k8s_metric` | `K8sMetricDataID` | `k8smetricdataid` |
| `custom_metric` | `CustomMetricDataID` | `custommetricdataid` |
| `k8s_event` | `K8sEventDataID` | `k8seventdataid` |

`extra_data_ids` 中展示的字段不参与 DataIDResource 缺失判断。

#### 3. 检查 k8s_metric 最终落地

用一条代表性 PromQL 覆盖所有集群：

```promql
avg(bkmonitor:container_cpu_usage_seconds_total) by (bcs_cluster_id)
```

查询时可在 helper 内按 `bcs_cluster_id` 建索引，但采集结果只写回每个集群明细，不额外返回集群数量统计。

```json
{
  "cluster_id": "BCS-K8S-000000",
  "has_data": true,
  "value": 0.12,
  "message": ""
}
```

如果 `K8sMetricDataID` 有 Kafka 数据，但这条 PromQL 查不到对应 `bcs_cluster_id`，说明数据可能未最终落地到 VM / 查询侧，需要标为 fatal 或 warning。

#### 4. 检查 custom_metric 最终落地

先从 `CustomMetricDataID` 的 Kafka 样本里抽一个 metric：

```json
{
  "dimension": {
    "bcs_cluster_id": "BCS-K8S-100018"
  },
  "metrics": {
    "bcs_api_session_server_total_add_connections": 25061
  }
}
```

抽样规则：

1. 只取 `data[]` 中 `dimension.bcs_cluster_id` 等于当前集群的记录。
2. 从 `metrics` 字典中选择第一个数值型 metric。
3. 组装 PromQL 抽查最终落地：

```promql
topk(1, bkmonitor:bcs_api_session_server_total_add_connections{bcs_cluster_id="BCS-K8S-100018"})
```

返回：

```json
{
  "sample_metric": "bcs_api_session_server_total_add_connections",
  "sample_bcs_cluster_id": "BCS-K8S-100018",
  "promql": "topk(1, bkmonitor:bcs_api_session_server_total_add_connections{bcs_cluster_id=\"BCS-K8S-100018\"})",
  "has_data": true,
  "value": 25061,
  "message": ""
}
```

如果 Kafka 有样本但无法解析 metric，返回 `has_data=null` 和原因；如果 PromQL 查询无结果，标记为最终落地异常。

#### 5. 检查事件数据

事件第一阶段只判断“有没有事件数据”，不强制抽查具体事件类型。

优先检查：

| data_id | 判断 |
| --- | --- |
| `K8sEventDataID` | 非 0 且 Kafka 有数据，则 `has_kafka_event=true` |

如果能拿到事件结果表，再参考自定义事件页面的检索逻辑补充最终查询侧检查：

```python
event_table_ids = set(
    DataSourceResultTable.objects.filter(
        bk_tenant_id=cluster.bk_tenant_id,
        bk_data_id=cluster.K8sEventDataID,
    ).values_list("table_id", flat=True)
)
event_table_ids.update(
    EventGroup.objects.filter(
        bk_tenant_id=cluster.bk_tenant_id,
        bk_data_id=cluster.K8sEventDataID,
        is_delete=False,
        is_enable=True,
    ).values_list("table_id", flat=True)
)
```

```python
qs = (
    UnifyQuerySet()
    .scope(cluster.bk_biz_id)
    .time_align(False)
    .start_time(start_time * 1000)
    .end_time(end_time * 1000)
    .limit(1)
)
q = QueryConfigBuilder((DataTypeLabel.EVENT, DataSourceLabel.CUSTOM)).table(table_id)
records = qs.add_query(q.distinct("event_name").order_by("-time"))
```

`records` 非空则 `has_query_event=true`，并保留 1 条轻量样本。如果暂时无法可靠定位事件 `table_id`，先只返回 Kafka 有数状态和原因，不阻塞整体检查。

### 比对规则

涉及集群数量、上报集群数量、缺失资源数量的规则，由比对脚本基于 `clusters` 明细计算，采集接口不提前返回统计字段。

| 规则 | 级别 |
| --- | --- |
| 老环境存在 cluster，新环境缺失同 `cluster_id` | fatal |
| `cluster_id` 存在但 `K8sMetricDataID` / `CustomMetricDataID` / `K8sEventDataID` 缺失或为 0 | fatal |
| 老环境核心 data_id 非 0 且有 Kafka 数据，新环境对应核心 data_id 无 Kafka 数据 | fatal |
| 新环境集群 DataID 资源查询报错 | fatal |
| 新环境缺少 `DATASOURCE_REGISTER_INFO` 中非 0 data_id 对应的 DataIDResource | fatal |
| 老环境 `k8s_metric_landing.has_data=true`，新环境对应集群查不到 `container_cpu_usage_seconds_total` | fatal |
| 老环境 custom_metric Kafka 有样本，新环境样本 metric PromQL 查不到 | warning / fatal，按是否依赖该指标 |
| 老环境 `K8sEventDataID` 有事件数据，新环境事件 Kafka 和查询侧都无数据 | warning / fatal |
| 集群状态从 running 变为 deleted / init_failed | warning / fatal |

## 检查项 3：拨测任务、下发状态、数据状态

拨测新老环境可能同时存在公共 data_id 和业务分离 data_id 两种上报方式，不建议把“具体使用哪个 data_id”作为核心检查项。
本项重点只看：

1. 任务是否迁移完整。
2. 任务状态和下发状态是否正常。
3. 通过 PromQL 能否查到任务最终数据。
4. 列表页口径的成功率 / 可用率、响应时间是否存在明显异常。

### 需要返回的字段

```json
{
  "tasks": [
    {
      "id": 0,
      "name": "",
      "protocol": "HTTP",
      "status": "",
      "period": 60,
      "subscription_ids": [],
      "independent_dataid": null,
      "deploy_status": "",
      "deploy_message": "",
      "promql_data": {
        "available": {
          "promql": "",
          "has_data": null,
          "value": null,
          "time": null
        },
        "task_duration": {
          "promql": "",
          "has_data": null,
          "value": null,
          "time": null
        }
      },
      "available": null,
      "task_duration": null,
      "error_log": []
    }
  ]
}
```

### 数据来源

| 数据 | 来源 |
| --- | --- |
| 拨测任务 | `bk_monitor_base.uptime_check.list_tasks` |
| 订阅 ID | `bk_monitor_base.uptime_check.UptimeCheckTaskSubscription` |
| 下发状态 | `bk_monitor_base.uptime_check.refresh_task_status` |
| 失败日志 | `bk_monitor_base.uptime_check.list_collector_logs` |
| 列表页成功率 / 响应时间 | `resource.uptime_check.uptime_check_task_list(..., get_available=True, get_task_duration=True)` |
| 最终数据状态 | PromQL 查询 `available` / `task_duration` |

### 获取逻辑

#### 1. 获取任务和状态

任务列表：

```python
tasks = list_tasks(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
```

每个任务返回：

| 字段 | 说明 |
| --- | --- |
| `id` / `name` / `protocol` | 后续新老环境比对主键和辅助信息 |
| `status` | 任务状态，关注 `RUNNING`、`STOPED`、`START_FAILED`、`STOP_FAILED` |
| `period` | `task.config.get("period", 60)`，用于 PromQL range |
| `independent_dataid` | 仅展示，不作为比对规则 |
| `subscription_ids` | 从 `UptimeCheckTaskSubscription` 获取 |

下发状态：

```python
deploy_result = refresh_task_status(
    bk_tenant_id=bk_tenant_id,
    bk_biz_id=bk_biz_id,
    task_ids=[task.id for task in tasks],
)
```

如果任务为 `START_FAILED` 或下发状态异常，再调用：

```python
error_log = list_collector_logs(task.id)
```

#### 2. 获取列表页口径的成功率和响应时间

复用列表页逻辑：

```python
task_data = resource.uptime_check.uptime_check_task_list(
    task_data=[task.model_dump(exclude={"bk_tenant_id"}) for task in tasks],
    bk_biz_id=bk_biz_id,
    get_available=True,
    get_task_duration=True,
)
```

内部查询口径参考 `UptimeCheckTaskListResource.query_available_or_duration(...)`：

| 指标 | 口径 |
| --- | --- |
| `available` | 最近 5 个周期内按 `task_id` 聚合的平均可用率，返回时乘以 100 |
| `task_duration` | 最近 5 个周期内按 `task_id` 聚合的平均响应时间，单位 ms |

采集接口只把 `available`、`task_duration` 写回每个任务。
如需 `avg_available`、`min_available`、`zero_available_task_count`、`avg_task_duration`、`max_task_duration` 等统计，由比对脚本从 `tasks` 明细计算。

#### 3. PromQL 检查最终数据

最终有数判断以 PromQL 为准，不依赖具体 data_id。

按任务协议和周期分组后批量查询，同一 `protocol + period` 下每个指标只发起一次 PromQL，再按 `task_id` 回填到任务明细：

```text
protocol = task.protocol.lower()
period = task.config.get("period", 60)
metric_prefix = f"bkmonitor:uptimecheck_{protocol}"
```

成功率 / 可用率：

```promql
bottomk by (task_id) (1, min_over_time(bkmonitor:uptimecheck_{protocol}:available[{period}s]))
```

响应时间：

```promql
topk by (task_id) (1, max_over_time(bkmonitor:uptimecheck_{protocol}:task_duration[{period}s]))
```

不要按任务循环拼 `filter_dict={"task_id": task_id}`；批量结果中保留 `task_id` 维度即可定位每个任务。

返回时每个任务记录：

| 字段 | 说明 |
| --- | --- |
| `promql_data.available.has_data` | 是否查到可用率数据 |
| `promql_data.available.value` | 最新可用率值 |
| `promql_data.task_duration.has_data` | 是否查到响应时间数据 |
| `promql_data.task_duration.value` | 最新响应时间值 |

### 比对规则

涉及数量、比例、平均值、最大值的规则均由比对脚本基于 `tasks` 明细计算，采集接口不提前返回这些统计字段。

| 规则 | 级别 |
| --- | --- |
| 老环境任务数量大于 0，新环境为 0 | fatal |
| 同名任务缺失 | fatal |
| 老环境任务为 running，新环境同名任务为 start_failed / stop_failed | fatal |
| 老环境 running 且 PromQL 有数据，新环境 running 但 PromQL 无数据 | fatal |
| 新环境任务下发失败或存在失败日志 | warning / fatal |
| 老环境可用率明显正常，新环境可用率为 0 | fatal |
| 老环境可用率较高，新环境明显下降，例如 90% -> 0% | fatal |
| 新环境响应时间相比老环境明显升高 | warning / fatal，按阈值 |
| 新环境无 PromQL 数据的任务明显多于老环境 | fatal |
| token 不涉及拨测，不做 token 比对 | info |
| 具体使用公共 data_id 还是业务分离 data_id | info，仅展示，不作为异常判断 |

## 检查项 4：自定义指标 / 自定义事件数据状态

### 自定义指标返回字段

```json
{
  "custom_metrics": [
    {
      "time_series_group_id": 0,
      "name": "",
      "bk_data_id": 0,
      "table_id": "",
      "scenario": "",
      "data_label": "",
      "protocol": "json",
      "is_platform": false,
      "auto_discover": true,
      "access_token": "",
      "metric_fields": [],
      "kafka_status": {
        "has_data": false,
        "latest_time": null,
        "message": ""
      },
      "table_sample": {
        "metric": "",
        "has_data": null,
        "latest_time": null,
        "sample": {},
        "message": ""
      }
    }
  ]
}
```

### 自定义事件返回字段

```json
{
  "custom_events": [
    {
      "bk_event_group_id": 0,
      "name": "",
      "bk_data_id": 0,
      "table_id": "",
      "scenario": "",
      "data_label": "",
      "type": "custom_event",
      "is_enable": true,
      "is_platform": false,
      "access_token": "",
      "event_names": [],
      "dimensions": [],
      "kafka_status": {
        "has_data": false,
        "latest_time": null,
        "message": ""
      },
      "table_sample": {
        "has_data": null,
        "latest_time": null,
        "sample": {},
        "message": ""
      }
    }
  ]
}
```

### 数据来源

| 数据 | 来源 |
| --- | --- |
| 自定义指标配置 | `monitor_web.models.custom_report.CustomTSTable` |
| 自定义指标 token | `api.metadata.get_time_series_group(bk_tenant_id=..., time_series_group_id=...)` 优先，否则 prometheus token 或 `api.metadata.get_data_id(bk_tenant_id=..., bk_data_id=...)` |
| 指标字段 | `api.metadata.query_time_series_scope(bk_tenant_id=..., group_id=..., include_metrics=True)` |
| 自定义事件配置 | `monitor_web.models.custom_report.CustomEventGroup` |
| 自定义事件 token | `api.metadata.get_event_group(bk_tenant_id=..., event_group_id=...)` 优先，否则 `api.metadata.get_data_id(bk_tenant_id=..., bk_data_id=...)` |
| 事件列表 | `CustomEventGroup.event_info_list` 或 `api.metadata.get_event_group` |
| Kafka 状态 | `api.metadata.kafka_tail(..., use_gse_config=True)` |
| 自定义指标表抽查 | `QueryConfigBuilder((DataTypeLabel.TIME_SERIES, DataSourceLabel.CUSTOM)).table(table_id)` |
| 自定义事件表抽查 | `QueryConfigBuilder((DataTypeLabel.EVENT, DataSourceLabel.CUSTOM)).table(table_id)` |

页面 token 逻辑参考：

| 场景 | 页面逻辑 |
| --- | --- |
| 自定义指标 | `CustomTimeSeriesDetail` 中 `data["access_token"] = config.token` |
| 自定义事件 | `GetCustomEventGroup.get_token(...)` |

### 获取逻辑

#### 1. 自定义指标配置和 Kafka 状态

按业务读取配置：

```python
custom_metrics = CustomTSTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
```

每个配置返回 `time_series_group_id`、`name`、`bk_data_id`、`table_id`、`data_label`、`protocol`、`access_token`。
`metric_fields` 从 `CustomTSTable.get_metrics()` 中筛选 `monitor_type == "metric"` 的字段名，作为后续表抽查候选。

Kafka 检查：

```python
sample_data = api.metadata.kafka_tail(
    bk_tenant_id=bk_tenant_id,
    bk_data_id=config.bk_data_id,
    size=3,
    use_gse_config=True,
)
```

返回 `kafka_status.has_kafka_data`、`kafka_status.message`。
不返回 `kafka_latest_data` 或原始样本内容；该检查只需要判断是否有 Kafka 数据。

#### 2. 自定义指标表数据抽查

表数据抽查只需要证明该配置对应结果表在查询侧有数据，不做接口级统计。

优先从 `metric_fields` 里选第一个指标字段，按页面图表同款查询配置传入 `table` 和 `data_label`。`data_label` 取逗号前第一个值，例如 `process.perf,process` 使用 `process.perf`，对应页面指标名 `custom:process.perf:io_read_speed`。抽查按时间窗口查任意一条数据，不使用 instant 查询：

```python
qs = (
    UnifyQuerySet()
    .scope(bk_biz_id)
    .time_align(False)
    .start_time(start_time * 1000)
    .end_time(end_time * 1000)
    .limit(1)
)
q = (
    QueryConfigBuilder((DataTypeLabel.TIME_SERIES, DataSourceLabel.CUSTOM))
    .table(config.table_id)
    .data_label(config.data_label.split(",")[0])
    .metric(field=metric_name, method="AVG", alias="a")
)
records = qs.add_query(q)
```

如果没有任何指标字段，`table_sample.has_data=false`，`message` 说明 `empty metric field`。
如果 `table_id` 为空导致无法组装查询，`table_sample.has_data=null`，`message` 说明原因。
如果 Kafka 有数据但表抽查无数据，后续比对脚本标记为查询侧落地异常。

#### 3. 自定义事件配置和 Kafka 状态

按业务读取配置：

```python
custom_events = CustomEventGroup.objects.filter(
    bk_tenant_id=bk_tenant_id,
    bk_biz_id=bk_biz_id,
    type="custom_event",
)
```

每个配置返回 `bk_event_group_id`、`name`、`bk_data_id`、`table_id`、`data_label`、`is_enable`、`access_token`。
`event_names` 和 `dimensions` 从 `event_info_list` 读取，只作为明细展示，不做接口级统计。

Kafka 检查同样使用 `api.metadata.kafka_tail(..., use_gse_config=True)`，结果写入 `kafka_status`。

#### 4. 自定义事件表数据抽查

参考 `GetCustomEventGroup.query_event_detail(...)`，优先查最近一条事件：

```python
qs = (
    UnifyQuerySet()
    .scope(bk_biz_id)
    .time_align(False)
    .start_time(start_time * 1000)
    .end_time(end_time * 1000)
    .limit(1)
)
q = QueryConfigBuilder((DataTypeLabel.EVENT, DataSourceLabel.CUSTOM)).table(event_group.table_id)
records = qs.add_query(q.distinct("event_name").order_by("-time"))
```

`records` 非空则 `table_sample.has_data=true`，并把最近一条事件放入 `sample`。
如果事件结果表暂时无法查询，返回 `has_data=null` 和错误信息，不影响其他配置项检查。

### 比对规则

涉及指标数、事件数、维度数变化的规则，由比对脚本基于 `metric_fields`、`event_names`、`dimensions` 明细计算，采集接口不提前返回统计字段。

| 规则 | 级别 |
| --- | --- |
| 同名自定义指标/事件缺失 | fatal |
| `bk_data_id` 不一致 | warning，迁移重建可能变化，但需展示 |
| `access_token` 不一致 | fatal |
| 老环境有 Kafka 数据，新环境无 Kafka 数据 | fatal |
| 老环境表抽查有数据，新环境表抽查无数据 | fatal |
| 新环境 Kafka 有数据但表抽查无数据 | warning / fatal |
| 指标数 / 事件数减少 | warning |

## 检查项 5：插件采集任务下发状态及数据状态

插件采集重点关注两个结果：

1. 采集配置整体是否启用、下发是否成功。
2. 采集目标是否有数据。

下发状态不返回完整实例状态树，数据量太大。采集接口只按每个采集配置返回实例状态聚合和少量异常样例，完整状态详情保留给页面或人工二次查询。

### 需要返回的字段

```json
{
  "configs": [
    {
      "id": 0,
      "name": "",
      "bk_biz_id": 0,
      "collect_type": "",
      "plugin_id": "",
      "plugin_type": "",
      "target_object_type": "",
      "target_node_type": "",
      "last_operation": "",
      "operation_result": "",
      "config_status": "",
      "task_status": "",
      "subscription_id": 0,
      "task_ids": [],
      "data_ids": [],
      "result_table_ids": [],
      "deploy_status": {
        "status": "",
        "message": "",
        "instance_status_counts": {},
        "abnormal_instance_samples": []
      },
      "data_status": {
        "has_data": null,
        "no_data_instance_count": null,
        "checked_instance_count": null,
        "no_data_instance_samples": [],
        "message": ""
      }
    }
  ]
}
```

### 数据来源

| 数据 | 来源 |
| --- | --- |
| 采集配置 | `monitor_web.models.collecting.CollectConfigMeta` |
| 当前部署版本 | `DeploymentConfigVersion` |
| 插件类型 | `CollectorPluginMeta` |
| 配置状态 | `CollectConfigMeta.config_status` |
| 任务状态 | `CollectConfigMeta.task_status` |
| data_id | `CollectConfigMeta.data_id`，进程插件单独处理 |
| 下发状态聚合 | `monitor_web.collecting.deploy.get_collect_installer(config).status(diff=False)`，只聚合实例状态 |
| 采集项数据状态 | `CollectTargetStatusTopoResource.nodata_test(...)` |

### 获取逻辑

#### 1. 配置基础信息

按业务读取启用/未删除的采集配置：

```python
configs = CollectConfigMeta.objects.select_related(
    "deployment_config",
    "deployment_config__plugin_version",
    "deployment_config__plugin_version__plugin",
).filter(bk_biz_id=bk_biz_id)
```

每个配置返回 `id`、`name`、`collect_type`、`plugin_id`、`plugin_type`、`target_object_type`、`target_node_type`、`config_status`、`task_status`、`subscription_id`。

#### 2. 下发状态聚合

按插件类型复用现有能力：

```python
installer = get_collect_installer(collect_config)
if is_nodeman_installer:
    # 先切换本地租户，再静默调用 batch_task_result，避免节点管理使用错误的当前请求租户。
    collect_status = query_nodeman_task_result_silently(subscription_id)
else:
    collect_status = installer.status(diff=False)
```

NodeMan 订阅查询会使用检查入口的 `bk_tenant_id` 设置本地租户上下文；查询失败时不抛出，也不打印公共 installer warning，错误信息写入 `deploy_status.message`，实例状态聚合为空。

不返回 `collect_status` 原始树，只遍历其中的实例，按 `instance["status"]` 聚合：

```json
{
  "SUCCESS": 10,
  "FAILED": 2,
  "WARNING": 1,
  "PENDING": 0,
  "NODATA": 3
}
```

建议字段：

| 字段 | 说明 |
| --- | --- |
| `deploy_status.status` | 配置级状态，优先用 `CollectConfigMeta.task_status` |
| `deploy_status.instance_status_counts` | 实例状态聚合，不返回完整实例列表 |
| `deploy_status.abnormal_instance_samples` | 仅保留少量异常实例，例如 failed / warning / nodata |
| `deploy_status.message` | installer 查询失败或不支持时的错误信息 |

异常实例样例最多保留少量定位字段：

```json
{
  "instance_id": "",
  "ip": "",
  "bk_cloud_id": 0,
  "service_instance_id": null,
  "status": "",
  "message": ""
}
```

#### 3. 数据状态

数据状态复用现有无数据检测逻辑：

```python
no_data_info = CollectTargetStatusTopoResource.nodata_test(collect_config, targets)
```

`targets` 从 installer 状态中的实例生成，和现有 `CollectTargetStatusTopoResource.perform_request(...)` 保持一致：

| 实例类型 | target |
| --- | --- |
| 服务实例 | `{"bk_target_service_instance_id": service_instance_id}` |
| 主机实例 | `{"bk_target_ip": ip, "bk_target_cloud_id": bk_cloud_id}` |

返回：

| 字段 | 说明 |
| --- | --- |
| `data_status.has_data` | 只要有一个目标有数据则为 `true` |
| `data_status.checked_instance_count` | 实际参与无数据检测的实例数 |
| `data_status.no_data_instance_count` | 无数据实例数，配置级聚合 |
| `data_status.no_data_instance_samples` | 少量无数据实例样例 |
| `data_status.message` | 无法检测数据时的错误信息 |

如果配置已停用、没有目标、或插件类型暂不支持无数据检测，`has_data` 可以返回 `null` 并写明原因。

### 特殊插件处理

| 插件类型 | 说明 |
| --- | --- |
| 普通 exporter / script / datadog | 使用 `nodata_test(...)` 检测目标是否有时序数据 |
| process | 重点检查 perf 数据，port 数据可作为后续扩展，不在第一阶段展开完整 data_id 逻辑 |
| log / snmp_trap | 使用 `nodata_test(...)` 内部的事件表查询逻辑判断是否有数据 |
| k8s | `get_collect_installer` 返回 `K8sInstaller`，没有 NodeMan subscription 时仍返回配置级状态；如无法展开实例，`data_status.has_data=null` 并说明原因 |

### 比对规则

涉及数量减少、实例减少等规则均由比对脚本基于 `configs` 明细计算，采集接口不提前返回统计字段。

| 规则 | 级别 |
| --- | --- |
| 同名采集配置缺失 | fatal |
| 老环境启用，新环境停用 | fatal |
| 新环境 `deploy_status.instance_status_counts` 中 failed / warning 明显增加 | warning / fatal |
| 老环境有成功实例，新环境成功实例明显减少 | warning / fatal |
| 老环境 `data_status.has_data=true`，新环境为 `false` | fatal |
| 新环境下发成功但 `data_status.has_data=false` | fatal |
| 插件版本不一致 | warning |

## 检查项 6：APM 相关数据状态

APM 按应用维度返回明细，不在采集接口里提前计算总数、异常数、成功率。核心检查三类问题：

1. 应用配置、功能开关、token 是否一致。
2. 已开启的数据类型对应 datasource 是否存在，data_id 是否有 Kafka 数据。
3. trace / metric / log / profiling 是否能按各自真实查询链路查到最终落地数据。

APM 四类数据的查询方式不能混用：

| 返回键 | datasource model | 内部 datasource type | 最终查询方式 |
| --- | --- | --- | --- |
| `trace` | `apm.models.TraceDataSource` | `trace` | `TraceQueryGuard` + `DataTypeLabel.LOG / DataSourceLabel.BK_APM` |
| `metric` | `apm.models.MetricDataSource` | `metric` | `QueryConfigBuilder((DataTypeLabel.TIME_SERIES, DataSourceLabel.CUSTOM))` |
| `log` | `apm.models.LogDataSource` | `log` | 日志平台索引集，`DataTypeLabel.LOG / DataSourceLabel.BK_LOG_SEARCH` 或 `api.log_search.es_query_search` |
| `profiling` | `apm.models.ProfileDataSource` | `profile` | `packages.apm_web.profile.doris.querier.QueryTemplate` |

注意：`ProfileDataSource.DATASOURCE_TYPE` 是 `profile`，但对外返回仍使用页面语义 `profiling`。

### 需要返回的字段

```json
{
  "applications": [
    {
      "application_id": 0,
      "bk_biz_id": 0,
      "app_name": "",
      "app_alias": "",
      "is_enabled": true,
      "enabled": {
        "trace": true,
        "metric": true,
        "log": false,
        "profiling": false
      },
      "token": "",
      "datasources": {
        "trace": {
          "enabled": true,
          "exists": false,
          "bk_data_id": 0,
          "result_table_id": "",
          "table_id": "",
          "data_name": "",
          "index_set_id": null,
          "data_id_status": {
            "exists": false,
            "has_kafka_data": null,
            "latest_time": null,
            "message": ""
          },
          "data_status": {
            "method": "trace_query_guard",
            "has_data": null,
            "latest_time": null,
            "message": ""
          }
        },
        "metric": {
          "enabled": true,
          "exists": false,
          "bk_data_id": 0,
          "result_table_id": "",
          "table_id": "",
          "data_name": "",
          "time_series_group_id": 0,
          "sample_metric": "",
          "data_id_status": {
            "exists": false,
            "has_kafka_data": null,
            "latest_time": null,
            "message": ""
          },
          "data_status": {
            "method": "unify_query_time_series",
            "has_data": null,
            "latest_time": null,
            "value": null,
            "message": ""
          }
        },
        "log": {
          "enabled": false,
          "exists": false,
          "bk_data_id": 0,
          "result_table_id": "",
          "table_id": "",
          "data_name": "",
          "index_set_id": null,
          "data_id_status": {
            "exists": false,
            "has_kafka_data": null,
            "latest_time": null,
            "message": ""
          },
          "data_status": {
            "method": "bk_log_search",
            "has_data": null,
            "latest_time": null,
            "message": ""
          }
        },
        "profiling": {
          "enabled": false,
          "exists": false,
          "bk_data_id": 0,
          "result_table_id": "",
          "table_id": "",
          "data_name": "",
          "data_id_status": {
            "exists": false,
            "has_kafka_data": null,
            "latest_time": null,
            "message": ""
          },
          "data_status": {
            "method": "profile_query_template",
            "has_data": null,
            "latest_time": null,
            "message": ""
          }
        }
      }
    }
  ]
}
```

每种 datasource 的 `data_status.has_data` 表示最终查询侧是否查到数据：

| 值 | 说明 |
| --- | --- |
| `true` | 查询成功且有数据 |
| `false` | 查询成功但无数据 |
| `null` | 未开启、datasource 缺失、配置不足或查询异常，原因写入 `message` |

### 数据来源

| 数据 | 来源 |
| --- | --- |
| APM 应用 | `apm.models.ApmApplication` |
| APM token | `ApmApplication.get_bk_data_token()` |
| Trace datasource | `apm.models.TraceDataSource` |
| Metric datasource | `apm.models.MetricDataSource` |
| Log datasource | `apm.models.LogDataSource` |
| Profiling datasource | `apm.models.ProfileDataSource` |
| data_id / Kafka 状态 | 封装后的 `check_data_id_status(data_id)`，内部使用 `api.metadata.kafka_tail(..., use_gse_config=True)` |
| Trace 查询 | `bkmonitor.data_source.utils.apm.TraceDatasourceTarget` / `TraceQueryGuard` |
| Metric 查询 | `bkmonitor.data_source.unify_query.query.QueryConfigBuilder` / `UnifyQuerySet` |
| Log 查询 | `api.log_search.es_query_search` 或 `QueryConfigBuilder((DataTypeLabel.LOG, DataSourceLabel.BK_LOG_SEARCH))` |
| Profiling 查询 | `packages.apm_web.profile.doris.querier.QueryTemplate` |

### 应用和 datasource 获取

应用按业务和租户过滤：

```python
applications = ApmApplication.objects.filter(
    bk_tenant_id=bk_tenant_id,
    bk_biz_id=bk_biz_id,
)
```

每个应用分别读取四类 datasource：

```python
datasource_map = {
    "trace": application.trace_datasource,
    "metric": application.metric_datasource,
    "log": application.log_datasource,
    "profiling": application.profile_datasource,
}
```

`enabled` 从应用开关读取：

```python
enabled = {
    "trace": application.is_enabled_trace,
    "metric": application.is_enabled_metric,
    "log": application.is_enabled_log,
    "profiling": application.is_enabled_profiling,
}
```

data_id 状态只在 `enabled=true` 且 datasource 存在且 `bk_data_id > 0` 时检查。未开启的数据类型保留返回结构，但 `data_id_status` 和 `data_status` 置为 `null` 并写明 `disabled`。

### Trace 数据检查

Trace datasource 字段：

| 返回字段 | 来源 |
| --- | --- |
| `bk_data_id` | `TraceDataSource.bk_data_id` |
| `result_table_id` | `TraceDataSource.result_table_id` |
| `table_id` | `TraceDataSource.table_id` |
| `data_name` | `TraceDataSource.data_name` |
| `index_set_id` | `TraceDataSource.index_set_id` |

Trace 最终数据查询必须通过 `TraceQueryGuard`，共享 Trace 结果表场景下它会自动追加 `bk_biz_id/app_name` 隔离条件：

```python
target = TraceDatasourceTarget.build(
    application.bk_biz_id,
    application.app_name,
    trace_datasource.result_table_id or trace_datasource.table_id,
)
q = (
    TraceQueryGuard.get_q([target])
    .time_field(OtlpKey.END_TIME)
    .values(OtlpKey.TRACE_ID, OtlpKey.SPAN_ID, OtlpKey.SERVICE_NAME)
)
records = list(
    UnifyQuerySet()
    .add_query(q)
    .time_align(False)
    .start_time(start_time_ms)
    .end_time(end_time_ms)
    .limit(1)
)
```

返回规则：

| 字段 | 说明 |
| --- | --- |
| `data_status.has_data` | `records` 是否非空 |
| `data_status.latest_time` | 优先取 `end_time` / `dtEventTimeStamp` / `time` |
| `data_status.message` | 查询异常、配置不足或未开启时的原因 |

### Metric 数据检查

Metric datasource 字段：

| 返回字段 | 来源 |
| --- | --- |
| `bk_data_id` | `MetricDataSource.bk_data_id` |
| `result_table_id` | `MetricDataSource.result_table_id` |
| `table_id` | `MetricDataSource.table_id` |
| `data_name` | `MetricDataSource.data_name` |
| `time_series_group_id` | `MetricDataSource.time_series_group_id` |

Metric 最终数据走自定义时序查询。优先从结果表字段中挑一个数值型指标；如果暂时无法拿字段列表，可按 APM 常见指标兜底抽查 `request_count`、`error_count`、`avg_duration`：

```python
table_id = metric_datasource.result_table_id or metric_datasource.table_id
metric_name = pick_metric_field(table_id) or pick_first_existing(
    ["request_count", "error_count", "avg_duration"]
)
q = (
    QueryConfigBuilder((DataTypeLabel.TIME_SERIES, DataSourceLabel.CUSTOM))
    .table(table_id)
    .metric(field=metric_name, method="avg", alias="a")
)
records = list(
    UnifyQuerySet()
    .add_query(q)
    .scope(application.bk_biz_id)
    .start_time(start_time)
    .end_time(end_time)
    .time_agg(False)
    .time_align(False)
    .instant()
)
```

返回规则：

| 字段 | 说明 |
| --- | --- |
| `sample_metric` | 实际用于抽查的指标名 |
| `data_status.has_data` | `records` 是否非空 |
| `data_status.value` | 抽查指标的第一条值 |

### Log 数据检查

Log datasource 字段：

| 返回字段 | 来源 |
| --- | --- |
| `bk_data_id` | `LogDataSource.bk_data_id` |
| `result_table_id` | `LogDataSource.result_table_id` |
| `table_id` | `LogDataSource.table_id` |
| `data_name` | `LogDataSource.data_name` |
| `index_set_id` | `LogDataSource.index_set_id` |

Log 最终数据优先通过日志平台索引集抽查。`index_set_id` 为空时不做查询，返回 `has_data=null`。
调用日志平台前需要使用检查入口的 `bk_tenant_id` 设置本地租户上下文，避免 `bk_log esquery_search` 从 request/local 中取不到租户：

```python
time_field = get_index_time_field(application.bk_biz_id, log_datasource.index_set_id)
records = api.log_search.es_query_search(
    index_set_id=log_datasource.index_set_id,
    start_time=start_time,
    end_time=end_time,
    size=1,
    start=0,
    sort_list=[[time_field, "desc"]],
)
```

也可以沿用日志策略模板的 UnifyQuery 方式：

```python
q = (
    QueryConfigBuilder((DataTypeLabel.LOG, DataSourceLabel.BK_LOG_SEARCH))
    .table(str(log_datasource.index_set_id))
    .index_set_id(log_datasource.index_set_id)
    .metric(field="_index", method="COUNT", alias="a")
)
```

返回规则：

| 字段 | 说明 |
| --- | --- |
| `data_status.has_data` | 搜索结果是否有命中，或 count 是否大于 0 |
| `data_status.latest_time` | 日志记录时间字段 |
| `data_status.message` | 查询异常、配置不足或未开启时的原因 |

### Profiling 数据检查

Profiling datasource 字段：

| 返回字段 | 来源 |
| --- | --- |
| `bk_data_id` | `ProfileDataSource.bk_data_id` |
| `result_table_id` | `ProfileDataSource.result_table_id` |
| `table_id` | `ProfileDataSource.table_id` |
| `data_name` | `ProfileDataSource.data_name` |

Profiling 最终数据不走普通日志或时序查询，使用 profile Doris 查询模板：

```python
template = QueryTemplate(application.bk_biz_id, application.app_name)
has_data = template.exist_data(start_time_ms, end_time_ms)
```

返回规则：

| 字段 | 说明 |
| --- | --- |
| `data_status.has_data` | `QueryTemplate.exist_data(...)` 返回值 |
| `data_status.latest_time` | 目前不额外抽取样本时间，固定为空 |
| `data_status.message` | 查询异常、配置不足或未开启时的原因 |

### 需要特别校验 token

APM 新旧环境 token 必须按 `bk_biz_id + app_name` 比对：

| 规则 | 级别 |
| --- | --- |
| 老环境 app 存在，新环境缺失 | fatal |
| `token` 不一致 | fatal |
| 老环境开启某类数据，新环境关闭 | fatal |
| 开启状态下 datasource 缺失 | fatal |
| 老环境 `data_id_status.has_kafka_data=true`，新环境为 `false` | fatal |
| 老环境 `data_status.has_data=true`，新环境为 `false` | fatal |
| 老环境 datasource 存在，新环境 `bk_data_id <= 0` | fatal |
| `result_table_id` 不一致 | warning，迁移重建可能变化，但需展示 |

涉及应用数量、各类型 datasource 数量、最终有数据比例等规则，均由比对脚本基于 `applications` 明细计算，采集接口不提前返回统计字段。

## 检查项 7：策略 id/name

### 需要返回的字段

```json
{
  "strategies": [
    {
      "id": 0,
      "name": "",
      "bk_biz_id": 0,
      "is_enabled": true,
      "is_invalid": false,
      "invalid_type": ""
    }
  ]
}
```

策略检查只保留后续比对需要的最小字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 策略 ID |
| `name` | 策略名称 |
| `bk_biz_id` | 业务 ID |
| `is_enabled` | 策略是否启用 |
| `is_invalid` | 策略是否失效 |
| `invalid_type` | 失效类型 |

### 数据来源

| 数据 | 来源 |
| --- | --- |
| 策略 | `bkmonitor.models.strategy.StrategyModel` |

### 比对规则

涉及策略总数减少等规则均由比对脚本基于 `strategies` 明细计算，采集接口不提前返回统计字段。

| 规则 | 级别 |
| --- | --- |
| 策略总数减少 | warning / fatal |
| 按 ID 缺失 | fatal |
| 按 name 缺失 | warning / fatal |
| 同名策略状态由启用变关闭 | warning |
| `is_invalid=True` | warning |

## API 暴露建议

第一阶段先不新增 API，也不接入 `data_migrate` command，只实现独立 helper，供 ipython、临时脚本或后续 API 薄封装调用。

后续 API 可设计为：

```http
POST /api/v4/data_migrate/status_check/
```

请求：

```json
{
  "bk_tenant_id": "system",
  "bk_biz_id": 2,
  "start_time": 1710000000,
  "end_time": 1710003600,
  "with_detail": false
}
```

响应直接透传 `collect_migration_status` 的返回。

## 后续封装建议

`data_migrate` 内只保留独立 helper；API 或比对脚本都作为后续薄封装接入，避免在第一版把入口形态提前固定。

比对脚本暂不在第一版实现，后续基于 `collect_migration_status` 生成的快照另行补充。

## 稳定匹配键

| 对象 | 主匹配键 | 辅助匹配键 |
| --- | --- | --- |
| 主机 | `bk_host_id` | `bk_cloud_id + ip` |
| 容器集群 | `cluster_id` | `bcs_api_cluster_id` |
| 拨测任务 | `id` | `name + protocol` |
| 自定义指标 | `time_series_group_id` | `name + table_id` |
| 自定义事件 | `bk_event_group_id` | `name + table_id` |
| 采集配置 | `id` | `name + plugin_id` |
| APM 应用 | `app_name` | `application_id` |
| 策略 | `id` | `name` |

## 实现步骤

1. 新增 `migration_status_check.py`，实现公共 `safe_check`、时间窗口、data_id/RT 状态 helper。
2. 实现 7 个检查函数：`check_host`、`check_k8s`、`check_uptime_check`、`check_custom_report`、`check_plugin_collect`、`check_apm`、`check_strategy`。
3. 实现 `collect_migration_status` 聚合 7 个检查项。
4. 确认返回结构后，再做 API resource 或比对脚本薄封装。

## 待确认问题

1. RT 数据状态是否必须查询真实存储，还是第一阶段 Kafka tail + 查询路由即可。
2. 主机列表是否需要全量返回，还是只返回数量和样例。
3. 下发详情是否需要返回完整日志。完整日志可能很大，建议默认只返回失败摘要。
4. `bk_data_id` 是否要求新旧一致。部分重建场景 data_id 可能变化，建议先展示差异，不作为默认 fatal。
5. 是否需要支持多业务一次性检查。建议 helper 单业务，调用层循环。
