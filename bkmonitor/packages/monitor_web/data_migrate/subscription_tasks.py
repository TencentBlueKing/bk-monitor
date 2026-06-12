from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from typing import Any

from bk_monitor_base.uptime_check import (
    UptimeCheckTaskSubscription,
    control_task,
    list_tasks,
)

from bkmonitor.utils.local import local
from bkmonitor.utils.tenant import set_local_tenant_id
from bkmonitor.utils.user import set_local_username
from monitor_web.collecting.constant import OperationType
from monitor_web.collecting.deploy import get_collect_installer
from monitor_web.models import CollectConfigMeta, CollectorPluginMeta
from monitor_web.plugin.constant import PluginType

UPTIME_CHECK = "uptime_check"
PLUGIN_COLLECT = "plugin_collect"
K8S_COLLECT = "k8s_collect"
TASK_CATEGORIES = (UPTIME_CHECK, PLUGIN_COLLECT, K8S_COLLECT)
NEGATIVE_BIZ_SKIP_REASON = "negative biz id has no subscription-backed collect tasks"


def stop_biz_subscription_tasks(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    operator: str = "system",
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Stop all subscription-backed tasks under businesses.

    The scope includes uptime-check tasks and plugin collect configs with NodeMan subscriptions.
    K8S collect configs are also stopped even though they are not backed by NodeMan subscriptions.
    """
    skipped_biz_ids = [
        {"bk_biz_id": bk_biz_id, "reason": NEGATIVE_BIZ_SKIP_REASON} for bk_biz_id in bk_biz_ids if bk_biz_id < 0
    ]
    target_bk_biz_ids = [bk_biz_id for bk_biz_id in bk_biz_ids if bk_biz_id >= 0]
    report = _init_report(
        bk_tenant_id=bk_tenant_id,
        bk_biz_ids=bk_biz_ids,
        operator=operator,
        dry_run=dry_run,
        skipped_biz_ids=skipped_biz_ids,
    )
    if not target_bk_biz_ids:
        report["summary"] = _build_summary(report["details"], dry_run=dry_run)
        return report

    with _local_operator_context(bk_tenant_id=bk_tenant_id, operator=operator):
        for task, subscription_ids in _list_uptime_tasks(bk_tenant_id=bk_tenant_id, bk_biz_ids=target_bk_biz_ids):
            record = {
                "bk_biz_id": task.bk_biz_id,
                "task_id": task.id,
                "name": task.name,
                "status": task.status.value,
                "subscription_ids": subscription_ids,
            }
            _stop_uptime_task(record, task, bk_tenant_id=bk_tenant_id, operator=operator, dry_run=dry_run)
            report["details"][UPTIME_CHECK].append(record)

        collect_configs = _list_collect_configs(bk_tenant_id=bk_tenant_id, bk_biz_ids=target_bk_biz_ids)
        plugin_type_map = _get_plugin_type_map(bk_tenant_id=bk_tenant_id, collect_configs=collect_configs)
        for collect_config in collect_configs:
            plugin_type = plugin_type_map.get(collect_config.plugin_id, "")
            category = _get_collect_category(collect_config, plugin_type)
            subscription_id = collect_config.deployment_config.subscription_id
            if category == PLUGIN_COLLECT and not subscription_id:
                continue

            record = {
                "bk_biz_id": collect_config.bk_biz_id,
                "collect_config_id": collect_config.pk,
                "name": collect_config.name,
                "collect_type": collect_config.collect_type,
                "plugin_id": collect_config.plugin_id,
                "plugin_type": plugin_type,
                "last_operation": collect_config.last_operation,
                "operation_result": collect_config.operation_result,
                "subscription_id": subscription_id,
            }
            _stop_collect_config(record, collect_config, category=category, dry_run=dry_run)
            report["details"][category].append(record)

    report["summary"] = _build_summary(report["details"], dry_run=dry_run)
    return report


def _stop_uptime_task(
    record: dict[str, Any],
    task,
    *,
    bk_tenant_id: str,
    operator: str,
    dry_run: bool,
) -> None:
    if dry_run:
        record.update({"action": "dry_run", "result": None, "message": "would stop uptime check task"})
        return

    try:
        control_task(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=task.bk_biz_id,
            task_id=task.id,
            action="stop",
            operator=operator,
        )
    except Exception as error:  # noqa: BLE001 - migration command should continue and report per-task failures.
        record.update({"action": "stop", "result": False, "message": str(error)})
    else:
        record.update({"action": "stop", "result": True, "message": "success"})


def _stop_collect_config(
    record: dict[str, Any],
    collect_config: CollectConfigMeta,
    *,
    category: str,
    dry_run: bool,
) -> None:
    if dry_run:
        record.update({"action": "dry_run", "result": None, "message": f"would stop {category}"})
        return

    if category == K8S_COLLECT and collect_config.last_operation == OperationType.STOP:
        record.update({"action": "skip", "result": True, "message": "k8s collect config already stopped"})
        return

    try:
        installer = get_collect_installer(collect_config)
        installer.stop()
    except Exception as error:  # noqa: BLE001 - migration command should continue and report per-task failures.
        record.update({"action": "stop", "result": False, "message": str(error)})
    else:
        record.update({"action": "stop", "result": True, "message": "success"})


def _list_uptime_tasks(*, bk_tenant_id: str, bk_biz_ids: list[int]) -> list[tuple[Any, list[int]]]:
    tasks = []
    for bk_biz_id in bk_biz_ids:
        tasks.extend(
            list_tasks(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                fields=["id", "bk_biz_id", "name", "protocol", "status"],
                order_by="id",
            )
        )

    task_ids = [task.id for task in tasks if task.id is not None]
    subscription_map = _get_uptime_subscription_map(task_ids=task_ids, bk_biz_ids=bk_biz_ids)
    return [(task, subscription_map[task.id]) for task in tasks if task.id in subscription_map]


def _get_uptime_subscription_map(*, task_ids: list[int], bk_biz_ids: list[int]) -> dict[int, list[int]]:
    if not task_ids:
        return {}

    subscription_map: dict[int, list[int]] = defaultdict(list)
    subscriptions = (
        UptimeCheckTaskSubscription.objects.filter(
            is_deleted=False,
            uptimecheck_id__in=task_ids,
            bk_biz_id__in=bk_biz_ids,
            subscription_id__gt=0,
        )
        .values_list("uptimecheck_id", "subscription_id")
        .order_by("uptimecheck_id", "subscription_id")
    )
    for task_id, subscription_id in subscriptions:
        subscription_map[int(task_id)].append(int(subscription_id))
    return dict(subscription_map)


def _list_collect_configs(*, bk_tenant_id: str, bk_biz_ids: list[int]) -> list[CollectConfigMeta]:
    return list(
        CollectConfigMeta.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id__in=bk_biz_ids)
        .select_related("deployment_config")
        .order_by("bk_biz_id", "id")
    )


def _get_plugin_type_map(*, bk_tenant_id: str, collect_configs: list[CollectConfigMeta]) -> dict[str, str]:
    plugin_ids = sorted({collect_config.plugin_id for collect_config in collect_configs})
    if not plugin_ids:
        return {}
    return dict(
        CollectorPluginMeta.objects.filter(bk_tenant_id=bk_tenant_id, plugin_id__in=plugin_ids).values_list(
            "plugin_id", "plugin_type"
        )
    )


def _get_collect_category(collect_config: CollectConfigMeta, plugin_type: str) -> str:
    if collect_config.collect_type == PluginType.K8S or plugin_type == PluginType.K8S:
        return K8S_COLLECT
    return PLUGIN_COLLECT


def _build_summary(details: dict[str, list[dict[str, Any]]], *, dry_run: bool) -> dict[str, dict[str, int]]:
    summary = {}
    for category in TASK_CATEGORIES:
        records = details[category]
        summary[category] = {
            "matched_count": len(records),
            "planned_count": len(records) if dry_run else 0,
            "stopped_count": sum(1 for record in records if record["action"] == "stop" and record["result"] is True),
            "skipped_count": sum(1 for record in records if record["action"] == "skip"),
            "failed_count": sum(1 for record in records if record["result"] is False),
        }
    summary["total"] = {
        key: sum(category_summary[key] for category_summary in summary.values())
        for key in ["matched_count", "planned_count", "stopped_count", "skipped_count", "failed_count"]
    }
    return summary


def _init_report(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    operator: str,
    dry_run: bool,
    skipped_biz_ids: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "dry_run": dry_run,
        "bk_tenant_id": bk_tenant_id,
        "bk_biz_ids": bk_biz_ids,
        "operator": operator,
        "skipped_biz_ids": skipped_biz_ids,
        "details": {category: [] for category in TASK_CATEGORIES},
        "summary": {},
    }


@contextmanager
def _local_operator_context(*, bk_tenant_id: str, operator: str):
    preserved_values = {}
    for key in ["bk_tenant_id", "username"]:
        if hasattr(local, key):
            preserved_values[key] = getattr(local, key)

    set_local_tenant_id(bk_tenant_id)
    set_local_username(operator)

    try:
        yield
    finally:
        for key in ["bk_tenant_id", "username"]:
            if key in preserved_values:
                setattr(local, key, preserved_values[key])
            elif hasattr(local, key):
                delattr(local, key)
