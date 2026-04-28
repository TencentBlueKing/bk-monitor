import logging
import time
from typing import Any, Literal

from bk_monitor_base.uptime_check import control_task, refresh_task_status
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from pydantic import BaseModel, Field

from apm.models.datasource import LogDataSource, MetricDataSource, ProfileDataSource, TraceDataSource
from bk_dataview.api import DashboardPermissionActions, get_or_create_user, sync_user_role
from bk_dataview.models import BuiltinRole, Dashboard, Org, Permission, Role
from bk_dataview.permissions import GrafanaPermission
from bk_dataview.utils import generate_uid
from bkmonitor.utils.tenant import set_local_tenant_id
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from core.errors.api import BKAPIError
from metadata import config
from metadata.models import (
    BCSClusterInfo,
    ClusterInfo,
    DataSource,
    DataSourceResultTable,
    ESStorage,
    EventGroup,
    LogGroup,
    ResultTable,
    ResultTableOption,
    StorageClusterRecord,
    TimeSeriesGroup,
)
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link.constants import BKBASE_NAMESPACE_BK_LOG, BKBASE_NAMESPACE_BK_MONITOR
from metadata.models.data_link.data_link_configs import ClusterConfig
from metadata.models.space.constants import EtlConfigs
from metadata.utils.gse import KafkaGseSyncer
from monitor.models import ApplicationConfig
from monitor_web.collecting.constant import OperationType
from monitor_web.collecting.deploy import get_collect_installer
from monitor_web.commons.data_access import PluginDataAccessor
from monitor_web.data_migrate.constants import DATA_MIGRATE_CLOSED_RECORDS_APPLICATION_CONFIG_KEY
from monitor_web.models.collecting import CollectConfigMeta
from monitor_web.models.custom_report import CustomEventGroup, CustomTSTable
from monitor_web.models.plugin import (
    CollectorPluginConfig,
    CollectorPluginInfo,
    CollectorPluginMeta,
    PluginVersionHistory,
)
from monitor_web.models.uptime_check import UptimeCheckTask
from monitor_web.plugin.manager.process import ProcessPluginManager

logger = logging.getLogger(__name__)

UPTIME_CHECK_CLOSE_RECORDS_MODEL_LABEL = "monitor.uptimechecktask"
COLLECT_CONFIG_CLOSE_RECORDS_MODEL_LABEL = "monitor_web.collectconfigmeta"


DEFAULT_KAFKA_CLUSTER_NAMES = {
    "log": "log-kafka-public-1",
    "event": "log-kafka-public-1",
    "metric": "metric-kafka-public-1",
}

DEFAULT_ES_CLUSTER_NAMES = {"log": "log-es-public-1", "event": "event-es-public-1"}


def _get_plugin_data_label(plugin: CollectorPluginMeta) -> str | None:
    qcloud_exporter_plugin_id = getattr(settings, "TENCENT_CLOUD_METRIC_PLUGIN_ID", "")
    if not qcloud_exporter_plugin_id:
        return None

    if plugin.plugin_type != CollectorPluginMeta.PluginType.K8S:
        return None

    if plugin.plugin_id in [qcloud_exporter_plugin_id, f"{qcloud_exporter_plugin_id}_{plugin.bk_biz_id}"]:
        return qcloud_exporter_plugin_id

    return None


def rebuild_system_data(bk_tenant_id: str, bk_biz_id: int):
    """重建内置系统数据

    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
    """
    from metadata.task.tasks import check_bkcc_space_builtin_datalink

    # 检查并重新接入系统数据
    check_bkcc_space_builtin_datalink([(bk_tenant_id, bk_biz_id)])


def _register_data_source(bk_biz_id: int, data_source: DataSource, need_register_to_bkbase: bool = True):
    """注册数据源到gse和bkbase"""

    # 查询当前存量的路由
    query_params = {
        "condition": {"channel_id": data_source.bk_data_id, "plat_name": "tgdp"},
        "operation": {"operator_name": "admin"},
    }
    try:
        result: list[dict[str, Any]] = api.gse.query_route(**query_params)
    except BKAPIError as e:
        if "not found" not in e.message:
            raise e
        print(f"query gse route not found, data_id: {data_source.bk_data_id}")
        result = []

    if not result:
        exists_route_names = []
    else:
        exists_route_names: list[str] = [route["name"] for route in result[0]["route"]]

    # 准备注册到gse的路由配置
    gse_route_config = data_source.gse_route_config
    route_name = gse_route_config["name"]

    # 注册到gse和bkbase
    data_source.register_to_gse()
    data_source.refresh_gse_config_to_gse()
    if need_register_to_bkbase:
        data_source.register_to_bkbase(
            bk_biz_id=bk_biz_id,
            namespace=BKBASE_NAMESPACE_BK_LOG
            if data_source.etl_config in [EtlConfigs.BK_FLAT_BATCH.value, EtlConfigs.BK_STANDARD_V2_EVENT.value]
            else BKBASE_NAMESPACE_BK_MONITOR,
        )

    # 清理多余的路由
    need_delete_route_names = list(set(exists_route_names) - set([route_name]))
    if need_delete_route_names:
        print(f"delete extra route for data_id: {data_source.bk_data_id}, route names: {need_delete_route_names}")
        delete_params = {
            "condition": {"channel_id": data_source.bk_data_id, "plat_name": "tgdp"},
            "operation": {"operator_name": "admin", "method": "specification"},
            "specification": {"route": need_delete_route_names},
        }
        api.gse.delete_route(**delete_params)


def init_global_plugin(bk_tenant_id: str):
    """初始化全局插件
    Args:
        bk_tenant_id (str): 租户ID
    """
    # 全局进程插件
    with transaction.atomic():
        plugin, _ = CollectorPluginMeta.objects.update_or_create(
            bk_tenant_id=bk_tenant_id,
            plugin_id="bkprocessbeat",
            plugin_type=CollectorPluginMeta.PluginType.PROCESS,
            defaults={
                "is_internal": True,
                "bk_biz_id": 0,
                "label": "host_process",
            },
        )
        plugin_version = PluginVersionHistory.objects.filter(
            bk_tenant_id=bk_tenant_id, plugin_id=plugin.plugin_id
        ).last()
        if not plugin_version:
            plugin_config = CollectorPluginConfig.objects.create()
            plugin_info = CollectorPluginInfo.objects.create(
                plugin_display_name="进程采集", enable_field_blacklist=False
            )
            PluginVersionHistory.objects.create(
                bk_tenant_id=bk_tenant_id,
                plugin_id="bkprocessbeat",
                config=plugin_config,
                info=plugin_info,
                config_version=1,
                info_version=1,
                stage=PluginVersionHistory.Stage.RELEASE,
                signature="{'default': {}}",
                is_packaged=True,
            )


def _get_closed_record_ids_from_application_config(bk_biz_id: int, model_label: str) -> set[int]:
    """从 ``ApplicationConfig`` 中获取导入阶段记录的关闭对象 ID。"""
    config = ApplicationConfig.objects.filter(
        cc_biz_id=bk_biz_id,
        key=DATA_MIGRATE_CLOSED_RECORDS_APPLICATION_CONFIG_KEY,
    ).first()
    if not config or not isinstance(config.value, dict):
        return set()

    raw_record_ids = config.value.get(model_label, [])
    if not isinstance(raw_record_ids, list):
        return set()

    closed_record_ids: set[int] = set()
    for record_id in raw_record_ids:
        try:
            closed_record_ids.add(int(record_id))
        except (TypeError, ValueError):
            logger.warning(
                "skip invalid close record id: bk_biz_id=%s model_label=%s record_id=%s",
                bk_biz_id,
                model_label,
                record_id,
            )
    return closed_record_ids


def rebuild_collect_plugins(
    bk_tenant_id: str,
    bk_biz_id: int,
    collect_config_ids: list[int] | None = None,
    kafka_cluster_names: dict[str, str] | None = None,
    es_cluster_names: dict[str, str] | None = None,
):
    """重建采集插件

    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
        collect_config_ids (list[int]): 采集配置ID列表
        kafka_cluster_names (dict[str, str]): 集群名称映射 metric/log/event 对应 kafka 集群名称
        es_cluster_names (dict[str, str]): 集群名称映射 metric/log/event 对应 es 集群名称
    """
    collect_configs = CollectConfigMeta.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
    if collect_config_ids:
        collect_configs = collect_configs.filter(id__in=collect_config_ids)
    closed_collect_config_ids = _get_closed_record_ids_from_application_config(
        bk_biz_id=bk_biz_id,
        model_label=COLLECT_CONFIG_CLOSE_RECORDS_MODEL_LABEL,
    )
    plugin_ids = list(set(collect_configs.values_list("plugin_id", flat=True)))

    # 获取插件，顺便检查插件是否存在
    plugins = CollectorPluginMeta.objects.filter(
        Q(bk_biz_id=bk_biz_id, plugin_id__in=plugin_ids) | Q(bk_biz_id=0, plugin_id="bkprocessbeat"),
        bk_tenant_id=bk_tenant_id,
    )
    exists_plugin_ids = plugins.values_list("plugin_id", flat=True)
    if not set(exists_plugin_ids).issuperset(set(plugin_ids)):
        missing_plugin_ids = set(plugin_ids) - set(exists_plugin_ids)
        raise ValueError(f"插件不存在: {missing_plugin_ids}")

    # 如果进程插件不需要，则不需要在本轮进行重建
    if "bkprocessbeat" not in plugin_ids:
        plugins = CollectorPluginMeta.objects.filter(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, plugin_id__in=plugin_ids
        )

    set_local_tenant_id(bk_tenant_id)

    es_cluster = ClusterInfo.objects.get(
        bk_tenant_id=bk_tenant_id,
        cluster_name=es_cluster_names["event"] if es_cluster_names else DEFAULT_ES_CLUSTER_NAMES["event"],
    )
    event_kafka_cluster = ClusterInfo.objects.get(
        bk_tenant_id=bk_tenant_id,
        cluster_name=kafka_cluster_names["event"] if kafka_cluster_names else DEFAULT_KAFKA_CLUSTER_NAMES["event"],
    )
    metric_kafka_cluster = ClusterInfo.objects.get(
        bk_tenant_id=bk_tenant_id,
        cluster_name=kafka_cluster_names["metric"] if kafka_cluster_names else DEFAULT_KAFKA_CLUSTER_NAMES["metric"],
    )

    # 获取插件对应的数据源/结果表/自定义上报
    for plugin in plugins:
        if plugin.plugin_type in [CollectorPluginMeta.PluginType.SNMP_TRAP, CollectorPluginMeta.PluginType.LOG]:
            event_group = EventGroup.objects.get(event_group_name=f"{plugin.plugin_type}_{plugin.plugin_id}")
            rebuild_event_group(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                kafka_cluster_name=event_kafka_cluster.cluster_name,
                es_cluster_name=es_cluster.cluster_name,
                event_group_ids=[event_group.event_group_id],
            )
        elif plugin.plugin_type == CollectorPluginMeta.PluginType.PROCESS:
            group_ids = list(
                TimeSeriesGroup.objects.filter(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    time_series_group_name__in=["process_perf", "process_port"],
                ).values_list("time_series_group_id", flat=True)
            )
            if group_ids:
                rebuild_time_series_group(bk_tenant_id, bk_biz_id, metric_kafka_cluster.cluster_name, group_ids)
            else:
                ProcessPluginManager(plugin, operator="system").touch(bk_biz_id)
        else:
            data_source = DataSource.objects.get(
                bk_tenant_id=bk_tenant_id, data_name=f"{plugin.plugin_type}_{plugin.plugin_id}".lower()
            )
            data_source.mq_cluster_id = metric_kafka_cluster.cluster_id
            data_source.save()
            _register_data_source(bk_biz_id=bk_biz_id, data_source=data_source, need_register_to_bkbase=True)
            dsrts = DataSourceResultTable.objects.filter(
                bk_tenant_id=bk_tenant_id, bk_data_id=data_source.bk_data_id, table_id__endswith=".__default__"
            )

            if dsrts.exists():
                result_table = ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=dsrts.get().table_id)
                result_table.modify(operator="system", is_enable=True)
            else:
                accessor = PluginDataAccessor(
                    plugin.current_version, operator="system", data_label=_get_plugin_data_label(plugin)
                )
                accessor.access(force_split_measurement=True)

    # 启用采集配置
    for collect_config in collect_configs:
        collect_config.deployment_config.subscription_id = 0
        collect_config.deployment_config.save()
        collect_config_pk = int(collect_config.pk)
        if collect_config_pk not in closed_collect_config_ids:
            logger.info(
                "skip install collect config not found in close_records: bk_biz_id=%s collect_config_id=%s",
                bk_biz_id,
                collect_config_pk,
            )
            continue
        installer = get_collect_installer(collect_config)
        installer.install(
            install_config={
                "target_node_type": collect_config.deployment_config.target_node_type,
                "target_nodes": collect_config.deployment_config.target_nodes,
                "params": collect_config.deployment_config.params,
            },
            operation=OperationType.CREATE,
        )


def rebuild_uptime_check(bk_tenant_id: str, bk_biz_id: int, task_ids: list[int] | None = None):
    """重建拨测数据
    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
    """

    tasks = UptimeCheckTask.objects.filter(bk_biz_id=bk_biz_id, is_deleted=False)
    if task_ids:
        tasks = tasks.filter(task_id__in=task_ids)
    if not tasks.exists():
        return

    closed_task_ids = _get_closed_record_ids_from_application_config(
        bk_biz_id=bk_biz_id,
        model_label=UPTIME_CHECK_CLOSE_RECORDS_MODEL_LABEL,
    )

    # 启用独立数据源模式
    tasks.update(indepentent_dataid=True)

    deployed_task_ids: list[int] = []
    for task in tasks:
        if task.pk not in closed_task_ids:
            logger.info(
                "skip deploy uptime check task not found in close_records: bk_biz_id=%s task_id=%s",
                bk_biz_id,
                task.pk,
            )
            continue
        print("deploy uptime check task: ", task.pk, task.name)
        result = control_task(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, task_id=task.pk, action="deploy")
        print(f"deploy uptime check task {task.pk} {task.name} result: {result}")
        deployed_task_ids.append(task.pk)

    if not deployed_task_ids:
        return

    time.sleep(10)

    # 刷新任务状态
    refresh_task_status(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, task_ids=deployed_task_ids)


def rebuild_time_series_group(
    bk_tenant_id: str, bk_biz_id: int, kafka_cluster_name: str, time_series_group_ids: list[int]
):
    """重建时序分组

    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
        time_series_group_ids (list[int]): 时序分组ID列表
        kafka_cluster_name (str): kafka 集群名称
    """
    kafka_cluster = ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=kafka_cluster_name)

    time_series_groups = TimeSeriesGroup.objects.filter(
        bk_tenant_id=bk_tenant_id, time_series_group_id__in=time_series_group_ids, is_delete=False
    )

    data_ids = list(time_series_groups.values_list("bk_data_id", flat=True))
    table_ids = list(time_series_groups.values_list("table_id", flat=True))

    # 排除已经创建过DataIdConfig的数据源
    data_sources = DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=data_ids)
    data_sources.update(mq_cluster_id=kafka_cluster.cluster_id)

    for data_source in data_sources:
        _register_data_source(bk_biz_id=bk_biz_id, data_source=data_source, need_register_to_bkbase=True)

    time_series_groups.update(is_enable=True)
    result_tables = ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids)
    for result_table in result_tables:
        result_table.modify(operator="system", is_enable=True)


def rebuild_event_group(
    bk_tenant_id: str,
    bk_biz_id: int,
    kafka_cluster_name: str,
    es_cluster_name: str,
    event_group_ids: list[int],
):
    """重建事件分组

    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
        event_group_ids (list[int]): 事件分组ID列表
    """
    kafka_cluster = ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=kafka_cluster_name)
    es_cluster = ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=es_cluster_name)
    event_groups = EventGroup.objects.filter(
        bk_tenant_id=bk_tenant_id, event_group_id__in=event_group_ids, is_delete=False
    )

    data_ids = list(event_groups.values_list("bk_data_id", flat=True))
    table_ids = list(event_groups.values_list("table_id", flat=True))

    # 数据源路由重建
    data_sources = DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=data_ids)
    data_sources.update(mq_cluster_id=kafka_cluster.cluster_id)
    for data_source in data_sources:
        _register_data_source(bk_biz_id=bk_biz_id, data_source=data_source, need_register_to_bkbase=True)

    # 替换ESStorage/StorageClusterRecord的集群信息
    ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids).update(
        storage_cluster_id=es_cluster.cluster_id
    )
    StorageClusterRecord.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids).update(
        cluster_id=es_cluster.cluster_id
    )

    EventGroup.objects.filter(bk_tenant_id=bk_tenant_id, event_group_id__in=event_group_ids).update(is_enable=True)
    result_tables = ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids)
    for result_table in result_tables:
        # 默认启用V4事件组数据链路
        v4_option = ResultTableOption.objects.filter(
            table_id=result_table.table_id,
            bk_tenant_id=bk_tenant_id,
            name=ResultTableOption.OPTION_ENABLE_V4_EVENT_GROUP_DATA_LINK,
        ).first()
        if not v4_option:
            ResultTableOption.create_option(
                table_id=result_table.table_id,
                bk_tenant_id=bk_tenant_id,
                name=ResultTableOption.OPTION_ENABLE_V4_EVENT_GROUP_DATA_LINK,
                value=True,
                creator="system",
            )
        es_document_id_option = ResultTableOption.objects.filter(
            table_id=result_table.table_id,
            bk_tenant_id=bk_tenant_id,
            name=ResultTableOption.OPTION_ES_DOCUMENT_ID,
        ).first()
        if not es_document_id_option:
            fields = EventGroup.STORAGE_FIELD_LIST
            option_value = [field["field_name"] for field in fields]
            option_value.append("time")
            ResultTableOption.create_option(
                table_id=result_table.table_id,
                bk_tenant_id=bk_tenant_id,
                name=ResultTableOption.OPTION_ES_DOCUMENT_ID,
                value=option_value,
                creator="system",
            )

        result_table.modify(operator="system", is_enable=True)


def rebuild_bklog_data_source_route(bk_tenant_id: str, bk_biz_id: int, kafka_cluster_name: str, es_cluster_name: str):
    """重建bklog数据源路由
    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
        cluster_name (str): 集群名称

    1. 替换ESStorage/StorageClusterRecord的集群信息
    2. 替换数据源的集群信息
    3. 注册数据源到gse和bkbase
    4. 结果表和虚拟结果表全部为停用状态，后续由日志/APM方便自行开启
    """
    kafka_cluster = ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=kafka_cluster_name)
    es_cluster = ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=es_cluster_name)
    biz_result_tables = ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)

    # 排除trace
    log_data_sources = DataSource.objects.filter(bk_tenant_id=bk_tenant_id, etl_config=EtlConfigs.BK_FLAT_BATCH.value)
    dsrt = DataSourceResultTable.objects.filter(
        table_id__in=biz_result_tables.values_list("table_id", flat=True),
        bk_data_id__in=log_data_sources.values_list("bk_data_id", flat=True),
    )
    bk_data_ids: list[int] = [dsrt.bk_data_id for dsrt in dsrt]
    real_table_ids: list[str] = [dsrt.table_id for dsrt in dsrt]
    virtual_table_ids = list(
        ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, origin_table_id__in=real_table_ids).values_list(
            "table_id", flat=True
        )
    )

    data_sources = DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=bk_data_ids)

    # real_result_tables = ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=real_table_ids)
    # virtual_result_tables = ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=virtual_table_ids)
    real_ess = ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=real_table_ids)
    virtual_ess = ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=virtual_table_ids)
    storage_cluster_records = StorageClusterRecord.objects.filter(
        bk_tenant_id=bk_tenant_id, table_id__in=real_table_ids + virtual_table_ids
    )

    # 替换ess的集群信息
    real_ess.update(storage_cluster_id=es_cluster.cluster_id)
    virtual_ess.update(need_create_index=False, storage_cluster_id=es_cluster.cluster_id)
    storage_cluster_records.update(cluster_id=es_cluster.cluster_id)

    # 替换数据源的集群信息
    data_sources.update(mq_cluster_id=kafka_cluster.cluster_id)

    # 替换数据源kafka并注册到gse和bkbase
    for data_source in data_sources:
        if not data_source.is_enable:
            continue
        _register_data_source(
            bk_biz_id=bk_biz_id,
            data_source=data_source,
            need_register_to_bkbase=data_source.created_from == DataIdCreatedFromSystem.BKDATA.value,
        )

    # 重建trace数据
    trace_tables = ResultTable.objects.filter(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, table_id__startswith=f"{bk_biz_id}_bkapm.trace_"
    )
    for trace_table in trace_tables:
        trace_table.modify(operator="system", is_enable=True)


def _ensure_builtin_role(org_id: int, role_name: str, managed_role_name: str) -> Role:
    """确保 org 下存在指定的内置角色，不存在则创建。

    Args:
        org_id: Grafana 组织 ID
        role_name: BuiltinRole 的角色名（如 "Editor"、"Viewer"）
        managed_role_name: Role 的 managed 名称（如 "managed:builtins:editor:permissions"）

    Returns:
        对应的 Role 实例
    """
    builtin_role = BuiltinRole.objects.filter(org_id=org_id, role=role_name).first()
    if builtin_role:
        return Role.objects.get(id=builtin_role.role_id)

    try:
        role = Role.objects.create(
            org_id=org_id,
            name=managed_role_name,
            uid=generate_uid(exclude_model=Role),
        )
        BuiltinRole.objects.create(org_id=org_id, role=role_name, role_id=role.id)
    except IntegrityError:
        role = Role.objects.get(org_id=org_id, name=managed_role_name)
    return role


def rebuild_dashboard(bk_biz_id: int):
    """重建仪表盘权限配置。

    将 admin 用户加入业务对应的 Grafana Org 并赋予 Admin 角色，
    然后为 Org 下所有仪表盘重建基于内置角色的权限：
    - Admin 角色：拥有全部管理权限（通过 OrgUser.role=Admin 隐式生效）
    - Editor 角色：可读、可写、可删除
    - Viewer 角色：只读

    Args:
        bk_biz_id: 业务 ID（对应 Grafana Org.name）
    """
    org = Org.objects.filter(name=str(bk_biz_id)).first()
    if not org:
        logger.warning("rebuild_dashboard: bk_biz_id=%s 对应的 Grafana Org 不存在，跳过", bk_biz_id)
        return

    org_id = org.id

    # 确保 admin 用户存在并赋予 Admin 角色
    admin_user = get_or_create_user("admin")
    sync_user_role(org_id, admin_user["id"], "Admin")

    # 确保 Editor / Viewer 内置角色存在
    editor_role = _ensure_builtin_role(org_id, "Editor", "managed:builtins:editor:permissions")
    viewer_role = _ensure_builtin_role(org_id, "Viewer", "managed:builtins:viewer:permissions")

    # 获取 Org 下所有仪表盘 UID（排除 folder）
    dashboard_uids = list(Dashboard.objects.filter(org_id=org_id, is_folder=0).values_list("uid", flat=True))
    if not dashboard_uids:
        logger.info("rebuild_dashboard: bk_biz_id=%s org_id=%s 下无仪表盘，跳过权限重建", bk_biz_id, org_id)
        return

    # 构建每个角色对应的权限 scope 集合
    role_permission_map: dict[int, list[str]] = {
        editor_role.id: DashboardPermissionActions[GrafanaPermission.Edit],
        viewer_role.id: DashboardPermissionActions[GrafanaPermission.View],
    }

    # 清理 editor/viewer 角色的旧仪表盘权限
    role_ids = [editor_role.id, viewer_role.id]
    Permission.objects.filter(
        role_id__in=role_ids,
        scope__startswith="dashboards:uid:",
    ).delete()

    # 批量创建新权限
    permission_objs: list[Permission] = []
    for role_id, actions in role_permission_map.items():
        for uid in dashboard_uids:
            for action in actions:
                permission_objs.append(
                    Permission(
                        role_id=role_id,
                        action=action,
                        scope=f"dashboards:uid:{uid}",
                    )
                )

    if permission_objs:
        Permission.objects.bulk_create(permission_objs, batch_size=500, ignore_conflicts=True)
        logger.info(
            "rebuild_dashboard: bk_biz_id=%s org_id=%s 重建权限完成，共 %d 条 Permission",
            bk_biz_id,
            org_id,
            len(permission_objs),
        )


def rebuild_custom_report(
    bk_tenant_id: str,
    bk_biz_id: int,
    metric_kafka_cluster_name: str,
    event_kafka_cluster_name: str,
    es_cluster_name: str,
):
    """重建自定义报告权限配置。

    Args:
        bk_biz_id: 业务 ID（对应 Grafana Org.name）
    """

    metric_kafka_cluster = ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=metric_kafka_cluster_name)
    event_kafka_cluster = ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=event_kafka_cluster_name)
    es_cluster = ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=es_cluster_name)

    ts_tables = CustomTSTable.objects.filter(bk_biz_id=bk_biz_id)
    rebuild_time_series_group(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        kafka_cluster_name=metric_kafka_cluster.cluster_name,
        time_series_group_ids=list(ts_tables.values_list("time_series_group_id", flat=True)),
    )

    event_groups = CustomEventGroup.objects.filter(bk_biz_id=bk_biz_id, type="custom_event")
    rebuild_event_group(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        kafka_cluster_name=event_kafka_cluster.cluster_name,
        es_cluster_name=es_cluster.cluster_name,
        event_group_ids=list(event_groups.values_list("bk_event_group_id", flat=True)),
    )

    # APM的指标数据
    apm_metric_data_ids = MetricDataSource.objects.filter(bk_biz_id=bk_biz_id).values_list("bk_data_id", flat=True)
    time_series_groups = TimeSeriesGroup.objects.filter(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, bk_data_id__in=apm_metric_data_ids
    )
    rebuild_time_series_group(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        kafka_cluster_name=metric_kafka_cluster.cluster_name,
        time_series_group_ids=list(time_series_groups.values_list("time_series_group_id", flat=True)),
    )


def rebuild_k8s_data(
    bk_tenant_id: str,
    bk_biz_id: int,
    metric_kafka_cluster_name: str,
    event_kafka_cluster_name: str,
    es_cluster_name: str,
):
    metric_kafka_cluster = ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=metric_kafka_cluster_name)
    event_kafka_cluster = ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=event_kafka_cluster_name)
    es_cluster = ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=es_cluster_name)

    clusters = BCSClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id).exclude(
        status__in=[
            BCSClusterInfo.CLUSTER_STATUS_DELETED,
            BCSClusterInfo.CLUSTER_RAW_STATUS_DELETED,
            BCSClusterInfo.CLUSTER_STATUS_INIT_FAILED,
        ]
    )

    metric_data_ids = [cluster.K8sMetricDataID for cluster in clusters if cluster.K8sMetricDataID] + [
        cluster.CustomMetricDataID for cluster in clusters if cluster.CustomMetricDataID
    ]
    event_data_ids = [cluster.K8sEventDataID for cluster in clusters if cluster.K8sEventDataID]

    if metric_data_ids:
        time_series_groups = TimeSeriesGroup.objects.filter(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, bk_data_id__in=metric_data_ids
        )
        rebuild_time_series_group(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            kafka_cluster_name=metric_kafka_cluster.cluster_name,
            time_series_group_ids=list(time_series_groups.values_list("time_series_group_id", flat=True)),
        )

    if event_data_ids:
        event_groups = EventGroup.objects.filter(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, bk_data_id__in=event_data_ids
        )
        rebuild_event_group(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            kafka_cluster_name=event_kafka_cluster.cluster_name,
            es_cluster_name=es_cluster.cluster_name,
            event_group_ids=list(event_groups.values_list("event_group_id", flat=True)),
        )


def find_biz_custom_report_data_ids(bk_tenant_id: str, bk_biz_ids: list[int]) -> dict[str, dict[int, dict[str, Any]]]:
    """查询业务下需要执行双写迁移的自定义上报数据ID。

    覆盖范围：页面创建的自定义指标/事件、K8S 内置指标、APM 以及自定义日志上报。

    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_ids (list[int]): 业务ID列表

    Returns:
        dict[str, dict[int, dict[str, Any]]]: 按类别分组的数据ID到topic名称的映射，包含以下 key：
            - custom_metric: 自定义指标上报
            - custom_event: 自定义事件上报
            - k8s: K8S 内置指标/事件上报
            - apm: APM 上报
            - log: 日志自定义上报（与 APM 有重叠）
    """
    # 页面创建的自定义指标/事件上报
    custom_metric_ids = (
        CustomTSTable.objects.filter(bk_biz_id__in=bk_biz_ids)
        .exclude(name__in=["process_perf", "process_port"])
        .values_list("bk_data_id", flat=True)
    )

    custom_event_ids = CustomEventGroup.objects.filter(bk_biz_id__in=bk_biz_ids, type="custom_event").values_list(
        "bk_data_id", flat=True
    )

    # K8S内置的指标上报
    k8s_ids: set[int] = set()
    for dataids in (
        BCSClusterInfo.objects.filter(bk_biz_id__in=bk_biz_ids)
        .exclude(
            status__in=[
                BCSClusterInfo.CLUSTER_STATUS_DELETED,
                BCSClusterInfo.CLUSTER_RAW_STATUS_DELETED,
                BCSClusterInfo.CLUSTER_STATUS_INIT_FAILED,
            ]
        )
        .values_list("K8sMetricDataID", "CustomMetricDataID", "K8sEventDataID", "CustomEventDataID")
    ):
        k8s_ids.update(dataid for dataid in dataids if dataid)

    # APM 上报
    apm_ids: set[int] = set()
    for model in (MetricDataSource, TraceDataSource, LogDataSource, ProfileDataSource):
        apm_ids.update(model.objects.filter(bk_biz_id__in=bk_biz_ids).values_list("bk_data_id", flat=True))

    # 日志自定义上报(与APM有重叠)
    log_ids = set(LogGroup.objects.filter(bk_biz_id__in=bk_biz_ids).values_list("bk_data_id", flat=True))

    # 数据ID到topic名称的映射
    data_id_to_topic_name = {
        data_source.bk_data_id: data_source.mq_config.topic
        for data_source in DataSource.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_data_id__in=[*custom_metric_ids, *custom_event_ids, *k8s_ids, *apm_ids, *log_ids],
        )
    }

    # 数据ID到kafka集群的名称的映射
    data_id_to_kafka_cluster_name = get_data_id_to_cluster_name(
        bk_tenant_id=bk_tenant_id, bk_data_ids=list(data_id_to_topic_name.keys())
    )

    return {
        "custom_metric": {
            data_id: {
                "data_id": data_id,
                "topic_name": data_id_to_topic_name[data_id],
                "kafka_cluster_name": data_id_to_kafka_cluster_name[data_id],
            }
            for data_id in custom_metric_ids
            if data_id in data_id_to_topic_name
        },
        "custom_event": {
            data_id: {
                "data_id": data_id,
                "topic_name": data_id_to_topic_name[data_id],
                "kafka_cluster_name": data_id_to_kafka_cluster_name[data_id],
            }
            for data_id in custom_event_ids
            if data_id in data_id_to_topic_name
        },
        "k8s": {
            data_id: {
                "data_id": data_id,
                "topic_name": data_id_to_topic_name[data_id],
                "kafka_cluster_name": data_id_to_kafka_cluster_name[data_id],
            }
            for data_id in k8s_ids
            if data_id in data_id_to_topic_name
        },
        "apm": {
            data_id: {
                "data_id": data_id,
                "topic_name": data_id_to_topic_name[data_id],
                "kafka_cluster_name": data_id_to_kafka_cluster_name[data_id],
            }
            for data_id in apm_ids
            if data_id in data_id_to_topic_name
        },
        "log": {
            data_id: {
                "data_id": data_id,
                "topic_name": data_id_to_topic_name[data_id],
                "kafka_cluster_name": data_id_to_kafka_cluster_name[data_id],
            }
            for data_id in log_ids
            if data_id in data_id_to_topic_name
        },
    }


class KafkaCluster(BaseModel):
    cluster_name: str
    domain_name: str
    port: int
    version: str
    username: str
    password: str


def add_new_migrate_kafka_and_registe_to_gse(kafka_cluster_configs: list[dict[str, Any]]) -> None:
    """添加新的迁移kafka并注册到gse

    Args:
        kafka_clusters: Kafka集群列表
    """
    kafka_clusters = [KafkaCluster(**kafka_cluster_config) for kafka_cluster_config in kafka_cluster_configs]

    for kafka_cluster in kafka_clusters:
        cluster_name = f"migrate_{kafka_cluster.cluster_name}"
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
                "version": kafka_cluster.version,
                "security_protocol": config.KAFKA_SASL_PROTOCOL,
                "sasl_mechanisms": config.KAFKA_SASL_MECHANISM,
                "is_register_to_gse": True,
            },
        )

        # 注册到gse
        KafkaGseSyncer.register_to_gse(cluster)


def get_data_id_to_cluster_name(bk_tenant_id: str, bk_data_ids: list[int]) -> dict[int, str]:
    """获取数据ID到新kafka集群的名称的映射

    Args:
        bk_tenant_id: 租户ID
        bk_data_ids: 数据ID列表

    Returns:
        dict[int, str]: 数据ID到新kafka集群的名称的映射
    """
    data_sources = DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=bk_data_ids)
    if len(data_sources) != len(bk_data_ids):
        raise ValueError(f"data_sources({len(data_sources)}) != bk_data_ids({len(bk_data_ids)})")

    cluster_id_to_names = {
        cluster.cluster_id: cluster.cluster_name
        for cluster in ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, cluster_type=ClusterInfo.TYPE_KAFKA)
    }

    return {data_source.bk_data_id: cluster_id_to_names[data_source.mq_cluster_id] for data_source in data_sources}


def add_new_migrate_data_id_routes(data_id_infos: dict[int, dict[str, Any]]):
    """为迁移的上报dataid添加双写路由

    Args:
        data_id_infos: 数据ID信息列表，包含以下 key：
            - data_id: 数据ID
            - topic_name: 主题名称
            - kafka_cluster_name: kafka集群名称
    """

    # 获取迁移的kafka集群
    migrate_kafka_clusters = {
        c.cluster_name: c
        for c in ClusterInfo.objects.filter(cluster_type=ClusterInfo.TYPE_KAFKA, cluster_name__startswith="migrate_")
    }

    for data_id_info in data_id_infos.values():
        data_id = data_id_info["data_id"]
        topic_name = data_id_info["topic_name"]
        kafka_cluster_name = data_id_info["kafka_cluster_name"]

        cluster_name = f"migrate_{kafka_cluster_name}"
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

        for route_config in exist_route_config:
            if route_config["name"] == f"migrate_kafka_data_id_{data_id}":
                print(f"data_id({data_id}) migrate failed, gse router config already has this route")
                continue

        # 追加新的route
        new_route = {
            "name": f"migrate_kafka_data_id_{data_id}",
            "stream_to": {
                "stream_to_id": cluster.gse_stream_to_id,
                ClusterInfo.TYPE_KAFKA: {"topic_name": topic_name},
            },
        }

        # 更新gse路由配置
        params = {
            "condition": {"channel_id": data_id, "plat_name": config.DEFAULT_GSE_API_PLAT_NAME},
            "operation": {"operator_name": data_source.creator},
            "specification": {"route": [*exist_route_config, new_route]},
        }
        try:
            api.gse.update_route(**params)
        except BKAPIError as e:
            print(f"data_id({data_id}) migrate failed, update gse router failed, error:({e})")
            continue


class ClusterData(BaseModel):
    bk_tenant_id: str
    namespaces: list[Literal["bkmonitor", "bklog"]]
    cluster_name: str
    cluster_type: str
    display_name: str
    domain_name: str
    port: int
    version: str = Field(default="")
    username: str
    password: str


def create_tenant_new_clusters(bk_tenant_id: str, cluster_configs: list[dict[str, Any]]) -> None:
    """创建租户的新集群

    Args:
        bk_tenant_id: 租户ID
        cluster_configs: 集群配置列表
    """

    for cluster_config in cluster_configs:
        cluster_data = ClusterData(bk_tenant_id=bk_tenant_id, **cluster_config)

        cluster = ClusterInfo.objects.create(
            bk_tenant_id=cluster_data.bk_tenant_id,
            cluster_type=cluster_data.cluster_type,
            cluster_name=cluster_data.cluster_name,
            display_name=cluster_data.display_name,
            domain_name=cluster_data.domain_name,
            port=cluster_data.port,
            version=cluster_data.version,
            username=cluster_data.username,
            password=cluster_data.password,
            is_default_cluster=False,
            is_auth=bool(cluster_data.username or cluster_data.password),
            security_protocol=config.KAFKA_SASL_PROTOCOL
            if cluster_data.cluster_type == ClusterInfo.TYPE_KAFKA
            else None,
            sasl_mechanisms=config.KAFKA_SASL_MECHANISM
            if cluster_data.cluster_type == ClusterInfo.TYPE_KAFKA
            else None,
        )

        if cluster_data.cluster_type == ClusterInfo.TYPE_KAFKA:
            cluster.is_register_to_gse = True
            KafkaGseSyncer.register_to_gse(cluster)
            cluster.is_register_to_gse = True

        ClusterConfig.sync_cluster_config(cluster, sync_namespaces=list(cluster_data.namespaces))
