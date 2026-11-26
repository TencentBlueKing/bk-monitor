# 用两个结果表配置指标入库和 Doris 窗口汇总

在 Metadata Django shell 使用下面两个示例。每个示例可以独立复制。首次接入传入所在业务的 `biz_id`（非 BKCC 空间传对应的负业务 ID）和同租户 Doris `cluster_id`。示例用的 `data_id` 必须已经配置原 Kafka 通道。先运行明细示例，再运行引用它的汇总示例。

明细输入采用标准指标上报结构，每个 `data[]` 项含毫秒级 `timestamp`、`metrics` 键值对象，以及可选的 `dimension` 和 `target`。一条上报中命中白名单的每个指标各写一行。

## 明细 RT

```python
from core.drf_resource import resource

def configure_raw(tenant, data_id, biz_id, cluster_id, operator, *, create=False, tasks=4, days=7):
    table_id = f"timeseries_raw_apm_rpc_{data_id}.__default__"
    identity = dict(bk_tenant_id=tenant, table_id=table_id, operator=operator)
    storage = dict(storage_cluster_id=cluster_id, expire_days=days, doris_storage_config={"flush_timeout": 30})
    if create:
        resource.metadata.create_result_table(
            **identity, bk_data_id=data_id, bk_biz_id=biz_id, table_name_zh="APM RPC 明细",
            schema_type="free", is_custom_table=True, is_time_field_only=True,
            default_storage="doris", default_storage_config=storage, data_label="apm_rpc", is_sync_db=False,
        )
    labels = """
        app_name scope_name service_name city region canary version sdk_name env_name namespace
        user_ext1 user_ext2 user_ext3 code code_type instance container_name caller_server caller_service
        caller_method caller_ip caller_container caller_con_setid caller_group callee_server callee_service
        callee_method callee_ip callee_container callee_con_setid le monitor_name node max_field _group
    """.split()
    dimensions = {name: name for name in labels}
    dimensions.update({"target": "dimension_target", "11": "dimension_11"})
    option = {
        "metric_ingest": {
            "metrics": [
                "rpc_server_handled_total", "rpc_server_handled_seconds_bucket",
                "rpc_server_handled_seconds_sum", "rpc_server_handled_seconds_count",
                "rpc_client_handled_total", "rpc_client_handled_seconds_bucket",
                "rpc_client_handled_seconds_sum", "rpc_client_handled_seconds_count",
            ],
            "dimensions": dimensions, "task_num": tasks,
            # 共享 DataID 时可按已展开的列筛选，例如 {"app_name": "my-app"}。
            "dimension_filters": {},
        },
        "time_field": {"name": "dtEventTimeStamp", "type": "date", "unit": "millisecond"},
        "need_add_time": False,
    }
    resource.metadata.modify_result_table(**identity, option=option, external_storage={"doris": storage})
    return table_id

# 首次配置，替换为实际值。重复修改时省略 create=True。
# raw = configure_raw("system", 1605502, biz_id, cluster_id, operator, create=True)
# configure_raw("system", 1605502, biz_id, cluster_id, operator, tasks=8)
# resource.metadata.modify_result_table(bk_tenant_id="system", table_id=raw, operator=operator, is_enable=False)
# resource.metadata.modify_result_table(bk_tenant_id="system", table_id=raw, operator=operator, is_enable=True)
```

## 汇总 RT

```python
from core.drf_resource import resource

def configure_aggregate(tenant, data_id, biz_id, cluster_id, operator, source_table_id, *,
                        create=False, lookback=10, days=30, normalize_callee_method=False):
    table_id = f"timeseries_agg_apm_rpc_{data_id}_swip1m.__default__"
    identity = dict(bk_tenant_id=tenant, table_id=table_id, operator=operator)
    storage = dict(storage_cluster_id=cluster_id, expire_days=days, doris_storage_config={"buckets": 16})
    if create:
        resource.metadata.create_result_table(
            **identity, bk_data_id=data_id, bk_biz_id=biz_id, table_name_zh="APM RPC 分钟汇总",
            schema_type="free", is_custom_table=True, is_time_field_only=True,
            default_storage="doris", default_storage_config=storage, data_label="apm_rpc_swip1m", is_sync_db=False,
        )
    option = {
        "metric_aggregate": {
            "source_table_id": source_table_id, "template_key": "sum_without",
            "without": ["callee_ip", "caller_ip", "instance"],
            "window_minutes": 1, "interval_minutes": 1, "lookback_minutes": lookback,
            "output_prefix": "sum_without_ip_", "normalize_callee_method": normalize_callee_method,
        },
        "time_field": {"name": "dtEventTimeStamp", "type": "date", "unit": "millisecond"},
        "need_add_time": False,
    }
    resource.metadata.modify_result_table(**identity, option=option, external_storage={"doris": storage})
    return table_id

# raw 是前一示例返回的完整逻辑 table_id。
# agg = configure_aggregate("system", 1605502, biz_id, cluster_id, operator, raw, create=True)
# configure_aggregate("system", 1605502, biz_id, cluster_id, operator, raw, lookback=20)
# resource.metadata.modify_result_table(bk_tenant_id="system", table_id=agg, operator=operator, is_enable=False)
# resource.metadata.modify_result_table(bk_tenant_id="system", table_id=agg, operator=operator, is_enable=True)
```

`without` 使用明细的输出列名。每个窗口按 `(T-window, T]` 对区间值求和，空维度按空字符串分组。`le` 是字符串，可保留 `+Inf`。启用 `normalize_callee_method` 会将完整匹配 `/idx_schedule/_doc/<id>` 的方法归入 `/idx_schedule/_doc/:id`。汇总表默认 16 桶，副本沿用 Doris 默认值；单副本测试集群可在汇总表的 `doris_storage_config` 显式传 `replication_num=1`。

`table_id` 和 `data_label` 由调用方选择。传入 `option` 时按 RT 的完整清洗配置提交。省略 `option` 可以只调整保留期或启停；传入空对象会停止该 RT 的任务。已配置的源 RT 和汇总 RT 各自维护启用状态。

## 查看执行和换表情况

```python
from metadata.models.data_link import MetricDorisPipeline

p = MetricDorisPipeline.objects.get(result_table__bk_tenant_id=tenant, result_table__table_id=agg)
print(p.phase, p.status_reason, p.output.name)
print(list(p.data_link.doris_jobs.values("name", "remote_id", "reconcile_status", "status_reason")))
```

`phase` 为空表示本次配置动作已收敛。用实际集群的 `tasks("type"="insert")` 按已登记的 `JobId` 查看执行结果。查询物理表时使用 `DorisStorage.physical_tables["main"]`。按相同事件窗口、输出维度比对明细的 `SUM(metric_value)`、`COUNT(*)` 与汇总的 `metric_value`、`source_sample_count`。

调整回看或周期会自动替换同名 Job。调整分组、归一化或窗口粒度会准备新的物理表和 Job。成功任务覆盖切换窗口后发布历史路由，旧表按原保留期提供原口径的数据。使用逻辑 RT 跨切点查询时只选取各自生效的时间段。
