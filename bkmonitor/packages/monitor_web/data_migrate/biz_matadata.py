"""
查询业务下关联的结果表和数据ID

可以通过DataSourceResultTable对结果表和数据ID进行关联查询

1. 自定义指标 CustomTSTable，全局数据也能归属到业务下，不能归属到业务0
2. 自定义事件 CustomEventGroup, 全局数据也能归属到业务下，不能归属到业务0
3. 采集插件 需要分类讨论，全局插件属于业务0 可以参考 data_access.py
4. 日志平台数据，bk_flat_batch类的ResultTable(需要排查apm trace)，都可以归属到业务下
5. 容器采集 BCSClusterInfo，都可以归属的业务下
6. 服务拨测 uptimechecktask， 参考UptimecheckDataAccessor，部分业务存在业务独立的结果表和数据ID，内置的拨测结果表和数据ID不需要处理，不需要归入业务0
7. APM ApmApplication 根据apm的接入表查询，都能按业务区分，不存在业务0
"""

from collections.abc import Iterable

from django.conf import settings
from pydantic import BaseModel

from apm.models import LogDataSource, MetricDataSource, ProfileDataSource, TraceDataSource
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from core.errors.api import BKAPIError
from metadata import config
from metadata.migration_util import filter_apm_log_table_ids
from metadata.models import BCSClusterInfo, ClusterInfo, DataSource, DataSourceResultTable, LogGroup, ResultTable
from metadata.models.storage import ESStorage
from metadata.utils.gse import KafkaGseSyncer
from monitor.models import UptimeCheckTask
from monitor_web.constants import EVENT_TYPE
from monitor_web.models import CollectorPluginMeta, CustomEventGroup, CustomTSTable, PluginVersionHistory
from monitor_web.plugin.constant import PluginType

INVALID_DATA_ID_VALUES: tuple[None, int, int] = (None, 0, -1)
INVALID_TABLE_ID_VALUES: tuple[None, str] = (None, "")


def _add_data_ids(container: set[int], values: Iterable[int | None]) -> None:
    for value in values:
        if value not in INVALID_DATA_ID_VALUES:
            container.add(value)


def _add_table_ids(container: set[str], values: Iterable[str | None]) -> None:
    for value in values:
        if value not in INVALID_TABLE_ID_VALUES:
            container.add(value)


def _add_dsrt_table_ids(container: set[str], data_ids: Iterable[int]) -> None:
    _add_table_ids(
        container,
        DataSourceResultTable.objects.filter(bk_data_id__in=list(data_ids))
        .values_list("table_id", flat=True)
        .distinct(),
    )


def _collect_custom_report_data(bk_biz_id: int, table_ids: set[str], data_ids: set[int]) -> None:
    if bk_biz_id == 0:
        return

    _add_table_ids(
        container=table_ids, values=CustomTSTable.objects.filter(bk_biz_id=bk_biz_id).values_list("table_id", flat=True)
    )
    _add_data_ids(
        container=data_ids,
        values=CustomTSTable.objects.filter(bk_biz_id=bk_biz_id).values_list("bk_data_id", flat=True),
    )
    _add_table_ids(
        container=table_ids,
        values=CustomEventGroup.objects.filter(bk_biz_id=bk_biz_id).values_list("table_id", flat=True),
    )
    _add_data_ids(
        container=data_ids,
        values=CustomEventGroup.objects.filter(bk_biz_id=bk_biz_id).values_list("bk_data_id", flat=True),
    )


def _collect_normal_plugin_data(bk_biz_id: int, table_ids: set[str], data_ids: set[int]) -> None:
    virtual_plugin_types = [
        PluginType.K8S,
        PluginType.PROCESS,
        PluginType.LOG,
        PluginType.SNMP_TRAP,
    ]
    plugins = CollectorPluginMeta.objects.filter(bk_biz_id=bk_biz_id).exclude(plugin_type__in=virtual_plugin_types)
    plugin_data_name_map = {
        f"{plugin.plugin_type}_{plugin.plugin_id}".lower(): plugin
        for plugin in plugins.only("plugin_type", "plugin_id", "bk_biz_id", "bk_tenant_id")
    }
    if not plugin_data_name_map:
        return

    ds_records = list(
        DataSource.objects.filter(data_name__in=list(plugin_data_name_map.keys())).values_list(
            "data_name", "bk_data_id"
        )
    )
    for data_name, bk_data_id in ds_records:
        plugin = plugin_data_name_map.get(data_name)
        if plugin is None:
            continue
        _add_data_ids(data_ids, [bk_data_id])
        table_id = PluginVersionHistory.get_result_table_id(plugin, "__default__").lower()
        _add_table_ids(table_ids, [table_id])


def _collect_event_plugin_data(bk_biz_id: int, table_ids: set[str], data_ids: set[int]) -> None:
    event_group_qs = CustomEventGroup.objects.filter(
        bk_biz_id=bk_biz_id,
        type=EVENT_TYPE.KEYWORDS,
        name__in=[
            f"{PluginType.LOG}_{plugin_id}"
            for plugin_id in CollectorPluginMeta.objects.filter(
                bk_biz_id=bk_biz_id, plugin_type__in=[PluginType.LOG, PluginType.SNMP_TRAP]
            ).values_list("plugin_id", flat=True)
        ]
        + [
            f"{PluginType.SNMP_TRAP}_{plugin_id}"
            for plugin_id in CollectorPluginMeta.objects.filter(
                bk_biz_id=bk_biz_id, plugin_type__in=[PluginType.LOG, PluginType.SNMP_TRAP]
            ).values_list("plugin_id", flat=True)
        ],
    )
    _add_table_ids(table_ids, event_group_qs.values_list("table_id", flat=True))
    _add_data_ids(data_ids, event_group_qs.values_list("bk_data_id", flat=True))


def _collect_k8s_plugin_data(bk_biz_id: int, table_ids: set[str], data_ids: set[int]) -> None:
    cluster_values = BCSClusterInfo.objects.filter(bk_biz_id=bk_biz_id).values_list(
        "K8sMetricDataID",
        "CustomMetricDataID",
        "K8sEventDataID",
        "CustomEventDataID",
    )
    k8s_data_ids: set[int] = set()
    for k8s_metric_data_id, custom_metric_data_id, k8s_event_data_id, custom_event_data_id in cluster_values:
        _add_data_ids(k8s_data_ids, [k8s_metric_data_id, custom_metric_data_id])
        if k8s_event_data_id not in INVALID_DATA_ID_VALUES:
            k8s_data_ids.add(k8s_event_data_id)
        if custom_event_data_id not in INVALID_DATA_ID_VALUES:
            k8s_data_ids.add(custom_event_data_id)

    _add_data_ids(data_ids, k8s_data_ids)
    _add_dsrt_table_ids(table_ids, k8s_data_ids)


def _collect_process_plugin_data(bk_biz_id: int, table_ids: set[str], data_ids: set[int]) -> None:
    process_data_names = [
        f"{bk_biz_id}_custom_time_series_process_perf",
        f"{bk_biz_id}_custom_time_series_process_port",
    ]
    process_data_ids = set(
        DataSource.objects.filter(data_name__in=process_data_names).values_list("bk_data_id", flat=True).distinct()
    )
    _add_data_ids(data_ids, process_data_ids)
    _add_dsrt_table_ids(table_ids, process_data_ids)


def _collect_bk_flat_batch_log_data(bk_biz_id: int, table_ids: set[str], data_ids: set[int]) -> None:
    biz_table_ids = set(ResultTable.objects.filter(bk_biz_id=bk_biz_id).values_list("table_id", flat=True))
    if not biz_table_ids:
        return

    flat_batch_data_ids = DataSource.objects.filter(etl_config="bk_flat_batch").values_list("bk_data_id", flat=True)
    apm_log_tables = set(filter_apm_log_table_ids(DataSource, DataSourceResultTable)["apm"])
    dsrt_queryset = DataSourceResultTable.objects.filter(table_id__in=biz_table_ids, bk_data_id__in=flat_batch_data_ids)
    dsrt_queryset = dsrt_queryset.exclude(table_id__in=apm_log_tables)
    physical_table_ids = set(dsrt_queryset.values_list("table_id", flat=True).distinct())
    _add_table_ids(table_ids, physical_table_ids)
    _add_data_ids(data_ids, dsrt_queryset.values_list("bk_data_id", flat=True).distinct())

    # 通过 ESStorage.origin_table_id 查找关联的虚拟表，虚拟 RT 没有自己的
    # DataSourceResultTable 记录，只能通过 origin_table_id 反查
    if physical_table_ids:
        virtual_table_ids = set(
            ESStorage.objects.filter(origin_table_id__in=physical_table_ids)
            .exclude(table_id__in=physical_table_ids)
            .values_list("table_id", flat=True)
            .distinct()
        )
        _add_table_ids(table_ids, virtual_table_ids)


def _collect_uptimecheck_data(bk_biz_id: int, table_ids: set[str], data_ids: set[int]) -> None:
    protocols = (
        UptimeCheckTask.objects.filter(bk_biz_id=bk_biz_id, indepentent_dataid=True)
        .values_list("protocol", flat=True)
        .distinct()
    )
    data_names = [f"uptimecheck_{protocol.lower()}_{bk_biz_id}" for protocol in protocols]
    if not data_names:
        return

    uptimecheck_data_ids = set(DataSource.objects.filter(data_name__in=data_names).values_list("bk_data_id", flat=True))
    _add_data_ids(data_ids, uptimecheck_data_ids)
    _add_dsrt_table_ids(table_ids, uptimecheck_data_ids)


def _collect_apm_data(bk_biz_id: int, table_ids: set[str], data_ids: set[int]) -> None:
    for model in (MetricDataSource, TraceDataSource, LogDataSource, ProfileDataSource):
        queryset = model.objects.filter(bk_biz_id=bk_biz_id)
        _add_data_ids(data_ids, queryset.values_list("bk_data_id", flat=True))
        _add_table_ids(table_ids, queryset.values_list("result_table_id", flat=True))


def find_biz_table_and_data_id(bk_biz_id: int) -> tuple[list[str], list[int]]:
    """查询业务下关联的结果表和数据ID

    Args:
        bk_biz_id: 业务ID

    Returns:
        tuple[list[str], list[int]]: 结果表列表和数据ID列表
    """
    table_ids: set[str] = set()
    data_ids: set[int] = set()

    _collect_custom_report_data(bk_biz_id, table_ids, data_ids)
    _collect_normal_plugin_data(bk_biz_id, table_ids, data_ids)
    _collect_event_plugin_data(bk_biz_id, table_ids, data_ids)
    if bk_biz_id != 0:
        _collect_k8s_plugin_data(bk_biz_id, table_ids, data_ids)
        _collect_process_plugin_data(bk_biz_id, table_ids, data_ids)
        _collect_bk_flat_batch_log_data(bk_biz_id, table_ids, data_ids)
        _collect_uptimecheck_data(bk_biz_id, table_ids, data_ids)
        _collect_apm_data(bk_biz_id, table_ids, data_ids)

    return sorted(table_ids), sorted(data_ids)


def find_biz_custom_report_data_ids(bk_biz_id: int) -> dict[str, set[int]]:
    """查询业务下需要执行双写迁移的自定义上报数据ID。

    覆盖范围：页面创建的自定义指标/事件、K8S 内置指标、APM 以及自定义日志上报。

    Args:
        bk_biz_id: 业务ID

    Returns:
        dict[str, set[int]]: 按类别分组的数据ID集合，包含以下 key：
            - ``custom_metric``: 自定义指标上报
            - ``custom_event``: 自定义事件上报
            - ``k8s``: K8S 内置指标/事件上报
            - ``apm``: APM 上报
            - ``log``: 日志自定义上报（与 APM 有重叠）
    """
    # 页面创建的自定义指标/事件上报
    custom_metric_ids: set[int] = set()
    _add_data_ids(
        custom_metric_ids, CustomTSTable.objects.filter(bk_biz_id=bk_biz_id).values_list("bk_data_id", flat=True)
    )

    custom_event_ids: set[int] = set()
    _add_data_ids(
        custom_event_ids, CustomEventGroup.objects.filter(bk_biz_id=bk_biz_id).values_list("bk_data_id", flat=True)
    )

    # K8S内置的指标上报
    k8s_ids: set[int] = set()
    for k8s_metric, custom_metric, k8s_event, custom_event in BCSClusterInfo.objects.filter(
        bk_biz_id=bk_biz_id
    ).values_list("K8sMetricDataID", "CustomMetricDataID", "K8sEventDataID", "CustomEventDataID"):
        _add_data_ids(k8s_ids, [k8s_metric, custom_metric, k8s_event, custom_event])

    # APM 上报
    apm_ids: set[int] = set()
    for model in (MetricDataSource, TraceDataSource, LogDataSource, ProfileDataSource):
        _add_data_ids(apm_ids, model.objects.filter(bk_biz_id=bk_biz_id).values_list("bk_data_id", flat=True))

    # 日志自定义上报(与APM有重叠)
    log_ids: set[int] = set()
    _add_data_ids(log_ids, LogGroup.objects.filter(bk_biz_id=bk_biz_id).values_list("bk_data_id", flat=True))

    return {
        "custom_metric": custom_metric_ids,
        "custom_event": custom_event_ids,
        "k8s": k8s_ids,
        "apm": apm_ids,
        "log": log_ids,
    }


class KafkaCluster(BaseModel):
    cluster_name: str
    domain_name: str
    port: int
    version: str
    username: str
    password: str


def add_new_migrate_kafka_and_registe_to_gse(kafka_clusters: list[KafkaCluster]) -> None:
    """添加新的迁移kafka并注册到gse

    Args:
        kafka_clusters: Kafka集群列表
    """

    for kafka_cluster in kafka_clusters:
        cluster_name = f"migrate_kafka_{kafka_cluster.cluster_name}"
        is_auth = bool(kafka_cluster.username and kafka_cluster.password)

        cluster, _ = ClusterInfo.objects.update_or_create(
            bk_tenant_id=DEFAULT_TENANT_ID,
            cluster_type=ClusterInfo.TYPE_KAFKA,
            cluster_name=cluster_name,
            defaults={
                "is_default_cluster": False,
                "display_name": cluster_name,
                "domain_name": kafka_cluster.domain_name,
                "port": kafka_cluster.port,
                "username": kafka_cluster.username,
                "password": kafka_cluster.password,
                "is_auth": is_auth,
                "security_protocol": config.KAFKA_SASL_PROTOCOL,
                "sasl_mechanisms": config.KAFKA_SASL_MECHANISM,
                "is_register_to_gse": True,
            },
        )

        # 注册到gse
        KafkaGseSyncer.register_to_gse(cluster)


def add_new_migrate_data_id_routes(data_id_to_cluster_name: dict[int, str]):
    """为迁移的上报dataid添加双写路由

    Args:
        data_id_to_cluster_name: 数据ID到新kafka集群的名称的映射
    """

    # 获取迁移的kafka集群
    migrate_kafka_clusters = {
        c.cluster_name: c
        for c in ClusterInfo.objects.filter(
            cluster_type=ClusterInfo.TYPE_KAFKA, cluster_name__startswith="migrate_kafka_"
        )
    }

    for data_id, cluster_name in data_id_to_cluster_name.items():
        cluster_name = f"migrate_kafka_{cluster_name}"
        cluster = migrate_kafka_clusters.get(cluster_name)
        if cluster is None:
            print(f"data_id({data_id}) migrate failed, kafka cluster({cluster_name}) not found")
            continue

        data_source = DataSource.objects.filter(bk_data_id=data_id).first()
        if data_source is None:
            print(f"data_id({data_id}) migrate failed, data source not found")
            continue

        # 查询是否存在gse路由配置
        try:
            exist_gse_router_config = api.gse.query_route(
                condition={"plat_name": config.DEFAULT_GSE_API_PLAT_NAME, "channel_id": data_id},
                operation={"operator_name": settings.COMMON_USERNAME},
            )
        except BKAPIError as e:
            print(f"data_id({data_id}) migrate failed, query gse router failed, error:({e})")
            continue

        # 如果gse路由配置为空，则跳过
        if not exist_gse_router_config:
            print(f"data_id({data_id}) migrate failed, gse router config is empty")
            continue

        # 获取存量gse路由配置并检查
        exist_route_config = exist_gse_router_config[0]["route"]
        if not exist_route_config:
            print(f"data_id({data_id}) migrate failed, gse router config is empty")
            continue

        if len(exist_route_config) > 1:
            print(f"data_id({data_id}) migrate failed, gse router config has multiple routes")
            continue

        # 追加新的route
        new_route = {
            "name": f"migrate_kafka_data_id_{data_id}",
            "stream_to": {
                "stream_to_id": cluster.gse_stream_to_id,
                ClusterInfo.TYPE_KAFKA: {"topic_name": data_source.mq_config.topic},
            },
        }

        # 更新gse路由配置
        params = {
            "condition": {"channel_id": data_id, "plat_name": config.DEFAULT_GSE_API_PLAT_NAME},
            "operation": {"operator_name": data_source.creator},
            "specification": {"route": [exist_route_config[0], new_route]},
        }
        try:
            api.gse.update_route(**params)
        except BKAPIError as e:
            print(f"data_id({data_id}) migrate failed, update gse router failed, error:({e})")
            continue
