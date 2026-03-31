import logging

from django.db import IntegrityError

from bk_dataview.api import DashboardPermissionActions, get_or_create_user, sync_user_role
from bk_dataview.models import BuiltinRole, Dashboard, Org, Permission, Role
from bk_dataview.permissions import GrafanaPermission
from bk_dataview.utils import generate_uid
from core.drf_resource import resource
from metadata.models import (
    DataSource,
    DataSourceResultTable,
    EventGroup,
    ResultTable,
    ResultTableOption,
    TimeSeriesGroup,
)
from metadata.models.data_link.constants import BKBASE_NAMESPACE_BK_LOG, BKBASE_NAMESPACE_BK_MONITOR
from metadata.models.space.constants import EtlConfigs
from metadata.task.tasks import check_bkcc_space_builtin_datalink
from monitor_web.commons.data_access import PluginDataAccessor, UptimecheckDataAccessor
from monitor_web.models.collecting import CollectConfigMeta
from monitor_web.models.plugin import CollectorPluginMeta
from monitor_web.models.uptime_check import UptimeCheckTask
from monitor_web.plugin.manager.process import ProcessPluginManager

logger = logging.getLogger(__name__)


def rebuild_system_data(bk_tenant_id: str, bk_biz_id: int):
    """重建内置系统数据

    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
    """
    # 检查并重新接入系统数据
    check_bkcc_space_builtin_datalink([(bk_tenant_id, bk_biz_id)])


def rebuild_collect_plugins(bk_tenant_id: str, bk_biz_id: int, collect_config_ids: list[int]):
    """重建采集插件

    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
        collect_config_ids (list[int]): 采集配置ID列表
    """

    collect_configs = CollectConfigMeta.objects.filter(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, id__in=collect_config_ids
    )
    plugin_ids = list(set(collect_configs.values_list("plugin_id", flat=True)))

    # 获取插件，顺便检查插件是否存在
    plugins = CollectorPluginMeta.objects.filter(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, plugin_id__in=plugin_ids
    )
    exists_plugin_ids = plugins.values_list("id", flat=True)
    if len(exists_plugin_ids) != len(plugin_ids):
        missing_plugin_ids = set(plugin_ids) - set(exists_plugin_ids)
        raise ValueError(f"插件不存在: {missing_plugin_ids}")

    # 获取插件对应的数据源/结果表/自定义上报
    for plugin in plugins:
        if plugin.plugin_type in [CollectorPluginMeta.PluginType.SNMP_TRAP, CollectorPluginMeta.PluginType.LOG]:
            event_group = EventGroup.objects.get(event_group_name=f"{plugin.plugin_type}_{plugin.plugin_id}")
            rebuild_event_group(bk_tenant_id, bk_biz_id, [event_group.event_group_id])
        elif plugin.plugin_type == CollectorPluginMeta.PluginType.PROCESS:
            group_ids = list(
                TimeSeriesGroup.objects.filter(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    time_series_group_name__in=["process_perf", "process_port"],
                ).values_list("time_series_group_id", flat=True)
            )
            if group_ids:
                rebuild_time_series_group(bk_tenant_id, bk_biz_id, group_ids)
            else:
                ProcessPluginManager(plugin, operator="system").touch(bk_biz_id)
        else:
            accessor = PluginDataAccessor(plugin.current_version, operator="system")
            data_source = DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=accessor.get_data_id())

            time_series_group = TimeSeriesGroup.objects.filter(
                bk_tenant_id=bk_tenant_id, bk_data_id=data_source.bk_data_id
            ).first()
            if time_series_group:
                rebuild_time_series_group(bk_tenant_id, bk_biz_id, [time_series_group.time_series_group_id])
            else:
                accessor.access()

    # 启用采集配置
    for collect_config in collect_configs:
        resource.collecting.toggle_collect_config_status(bk_biz_id=bk_biz_id, id=collect_config.pk, action="enable")


def rebuild_uptime_check(bk_tenant_id: str, bk_biz_id: int, task_ids: list[int] | None = None):
    """重建拨测数据
    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
    """
    tasks = UptimeCheckTask.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, is_delete=False)
    if task_ids:
        tasks = tasks.filter(task_id__in=task_ids)
    if not tasks.exists():
        return

    # 启用独立数据源模式
    tasks.update(indepentent_dataid=True)

    # 启用或重建自定义上
    accessor = UptimecheckDataAccessor(tasks[0])
    accessor.access()

    # 部署任务
    for task in tasks:
        task.deploy()


def rebuild_time_series_group(bk_tenant_id: str, bk_biz_id: int, time_series_group_ids: list[int] | None = None):
    """重建时序分组

    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
        time_series_group_ids (list[int]): 时序分组ID列表
    """
    time_series_groups = TimeSeriesGroup.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, is_delete=False)
    if time_series_group_ids:
        time_series_groups = time_series_groups.filter(time_series_group_id__in=time_series_group_ids)

    data_ids = list(time_series_groups.values_list("bk_data_id", flat=True))
    table_ids = list(time_series_groups.values_list("table_id", flat=True))

    data_sources = DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=data_ids)
    for data_source in data_sources:
        if not data_source.register_to_gse():
            raise ValueError(f"数据源{data_source.bk_data_id}注册到gse失败")
        data_source.register_to_bkbase(bk_biz_id=bk_biz_id, namespace=BKBASE_NAMESPACE_BK_MONITOR)

    TimeSeriesGroup.objects.filter(bk_tenant_id=bk_tenant_id, time_series_group_id__in=time_series_group_ids).update(
        is_enable=True
    )
    result_tables = ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids)
    for result_table in result_tables:
        result_table.modify(operator="system", is_enable=True)


def rebuild_event_group(bk_tenant_id: str, bk_biz_id: int, event_group_ids: list[int] | None = None):
    """重建事件分组

    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
        event_group_ids (list[int]): 事件分组ID列表
    """
    event_groups = EventGroup.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, is_delete=False)
    if event_group_ids:
        event_groups = event_groups.filter(event_group_id__in=event_group_ids)

    data_ids = list(event_groups.values_list("bk_data_id", flat=True))
    table_ids = list(event_groups.values_list("table_id", flat=True))

    # 数据源路由重建
    data_sources = DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=data_ids)
    for data_source in data_sources:
        if not data_source.register_to_gse():
            raise ValueError(f"数据源{data_source.bk_data_id}注册到gse失败")
        data_source.register_to_bkbase(bk_biz_id=bk_biz_id, namespace=BKBASE_NAMESPACE_BK_LOG)

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
                value="true",
                creator="system",
            )
        result_table.modify(operator="system", is_enable=True)


def rebuild_bklog_data_source_route(bk_tenant_id: str, bk_biz_id: int):
    """重建bklog数据源路由
    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
    """
    result_tables = ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
    related_data_ids = list(
        DataSourceResultTable.objects.filter(table_id__in=result_tables.values_list("table_id", flat=True))
        .values_list("bk_data_id", flat=True)
        .distinct()
    )
    data_sources = DataSource.objects.filter(
        bk_tenant_id=bk_tenant_id, etl_config=EtlConfigs.BK_FLAT_BATCH.value, bk_data_id__in=related_data_ids
    )

    for data_source in data_sources:
        data_source.register_to_gse()


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
