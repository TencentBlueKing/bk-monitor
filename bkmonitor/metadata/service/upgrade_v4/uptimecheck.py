"""拨测分业务/协议准备链路，任务切换与部署另行显式调用。"""

from copy import deepcopy

from django.db import transaction

from metadata import config, models
from metadata.service.upgrade_v4.common import require_single_tenant, run_batch, set_source_options
from metadata.service.upgrade_v4.metrics import migrate_metric


def _tasks(task_ids, bk_biz_ids):
    from monitor_web.models.uptime_check import UptimeCheckTask

    tasks = UptimeCheckTask.objects.filter(bk_tenant_id="system", is_deleted=False)
    if task_ids is not None:
        tasks = tasks.filter(task_id__in=task_ids)
    if bk_biz_ids is not None:
        tasks = tasks.filter(bk_biz_id__in=bk_biz_ids)
    return tasks.order_by("task_id")


def migrate_uptimechecks(task_ids=None, *, vm_cluster_name, bk_biz_ids=None, **route_options):
    """仅准备数据链路，不切换任务标志或重新部署；同业务同协议仅处理一次。"""
    from monitor_web.commons.data_access import UptimecheckDataAccessor

    tasks = {}
    for task in _tasks(task_ids, bk_biz_ids):
        tasks.setdefault((task.bk_biz_id, task.protocol), task)

    def migrate(key):
        task = tasks[key]
        accessor = UptimecheckDataAccessor(task)
        source = models.DataSource.objects.filter(bk_tenant_id="system", data_name=accessor.data_name).first()
        data_id = source.bk_data_id if source else accessor.create_data_id()
        group = models.TimeSeriesGroup.objects.filter(bk_tenant_id="system", bk_data_id=data_id).first()
        # 不调用 access()/create_time_series_group()，避免内置异步下发/路由刷新。
        with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
            if group is None:
                table_id, group = models.TimeSeriesGroup._create(
                    table_id=None,
                    bk_biz_id=task.bk_biz_id,
                    bk_data_id=data_id,
                    custom_group_name=accessor.data_name,
                    time_series_group_name=accessor.data_name,
                    label="uptimecheck",
                    operator="system",
                    is_split_measurement=True,
                    bk_tenant_id="system",
                    is_need_deploy_collector_config=False,
                )
                models.TimeSeriesGroup._post_process_create(group, {})
            if not models.ResultTable.objects.filter(bk_tenant_id="system", table_id=group.table_id).exists():
                models.ResultTable.create_result_table(
                    bk_tenant_id="system",
                    bk_data_id=data_id,
                    bk_biz_id=task.bk_biz_id,
                    table_id=group.table_id,
                    table_name_zh=accessor.data_name,
                    is_custom_table=True,
                    schema_type=models.ResultTable.SCHEMA_TYPE_FREE,
                    operator="system",
                    default_storage=models.ClusterInfo.TYPE_INFLUXDB,
                    label="uptimecheck",
                    data_label=accessor.data_label,
                    create_storage=False,
                    is_sync_db=False,
                    is_time_field_only=True,
                    field_list=deepcopy(models.TimeSeriesGroup.STORAGE_FIELD_LIST),
                    option={
                        "is_split_measurement": True,
                        "enable_field_black_list": True,
                        "enable_default_value": False,
                    },
                )
        if not group.is_enable or group.is_delete:
            return {"skipped": "拨测指标组已停用或删除", "table_ids": [], "spaces": []}
        source = models.DataSource.objects.get(bk_tenant_id="system", bk_data_id=data_id)
        set_source_options(source, group.get_datasource_options())
        result = migrate_metric(data_id, vm_cluster_name=vm_cluster_name)
        result["task_ids"] = [
            item.pk for item in _tasks(task_ids, bk_biz_ids) if (item.bk_biz_id, item.protocol) == key
        ]
        return result

    return run_batch(tasks, migrate, **route_options)


def switch_uptimecheck_tasks(task_ids, *, deploy=False):
    """链路验收后显式切换选定任务；deploy=True 仅重下发原来运行中的任务，可重复调用。"""
    from bk_monitor_base.uptime_check import control_task
    from monitor.models import ApplicationConfig
    from monitor_web.commons.data_access import UptimecheckDataAccessor

    require_single_tenant()
    result = []
    for task in _tasks(task_ids, None):
        accessor = UptimecheckDataAccessor(task)
        source = models.DataSource.objects.get(bk_tenant_id="system", data_name=accessor.data_name)
        models.TimeSeriesGroup.objects.get(
            bk_tenant_id="system", bk_data_id=source.bk_data_id, is_delete=False, is_enable=True
        )
        ApplicationConfig.objects.update_or_create(
            cc_biz_id=task.bk_biz_id,
            key=f"access_uptime_check_{task.protocol.lower()}_biz_dataid",
            defaults={"value": accessor.version},
        )
        task.indepentent_dataid = True
        task.save(update_fields=["indepentent_dataid"])
        deployed = deploy and task.status == task.Status.RUNNING
        response = None
        if deployed:
            response = control_task(bk_tenant_id="system", bk_biz_id=task.bk_biz_id, task_id=task.pk, action="deploy")
        result.append({"task_id": task.pk, "deploy_requested": deployed, "response": response})
    return result


def deploy_uptimecheck_tasks(task_ids):
    """显式下发选定任务，可用于失败重试；不会自动筛选或枚举其他任务。"""
    from bk_monitor_base.uptime_check import control_task

    require_single_tenant()
    return [
        {
            "task_id": task.pk,
            "response": control_task(bk_tenant_id="system", bk_biz_id=task.bk_biz_id, task_id=task.pk, action="deploy"),
        }
        for task in _tasks(task_ids, None)
    ]
