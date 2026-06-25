from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

from apm.core.application_config import ApplicationConfig
from apm.models import ApmApplication
from bkmonitor.utils.local import local
from bkmonitor.utils.tenant import set_local_tenant_id
from bkmonitor.utils.user import set_local_username
from bkmonitor.utils.bk_collector_config import BkCollectorConfig
from bkmonitor.utils.version import get_max_version
from core.drf_resource import api
from metadata.models import CustomReportSubscription, LogGroup, LogSubscriptionConfig

PLUGIN_NAME = "bk-collector"
APM_APPLICATION = "apm_application"
CUSTOM_REPORT = "custom_report"
LOG = "log"
INSTALL = "install"
STOP = "stop"

CONFIG_TYPES = (APM_APPLICATION, CUSTOM_REPORT, LOG)
VERSION_PATTERN = re.compile(r"[vV]?(\d+\.){1,5}\d+$")
SUCCEEDED_ACTIONS = {INSTALL, STOP, "refresh"}


def install_biz_bk_collector(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    operator: str = "system",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Install or upgrade bk-collector on proxy hosts used by the given businesses."""
    with _local_operator_context(bk_tenant_id=bk_tenant_id, operator=operator):
        try:
            plugin_version = _find_latest_plugin_version(bk_tenant_id=bk_tenant_id, plugin_name=PLUGIN_NAME)
            if not plugin_version or plugin_version == "0.0.0":
                raise ValueError(f"node_man has no ready {PLUGIN_NAME} version")
        except Exception as error:  # noqa: BLE001 - migration command reports per-business failures.
            return _build_biz_bk_collector_operation_error_report(
                bk_tenant_id=bk_tenant_id,
                bk_biz_ids=bk_biz_ids,
                operator=operator,
                dry_run=dry_run,
                category=INSTALL,
                operation_host_key="deploy_host_ids",
                message=str(error),
            )

    return _operate_biz_bk_collector_plugin(
        bk_tenant_id=bk_tenant_id,
        bk_biz_ids=bk_biz_ids,
        operator=operator,
        dry_run=dry_run,
        category=INSTALL,
        job_type="MAIN_INSTALL_PLUGIN",
        plugin_version=plugin_version,
        operation_host_key="deploy_host_ids",
        host_plan_loader=_get_deploy_host_ids,
        empty_operation_message="all proxy hosts already deployed",
        dry_run_message="would install bk-collector",
    )


def stop_biz_bk_collector(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    operator: str = "system",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Stop bk-collector on proxy hosts used by the given businesses."""
    return _operate_biz_bk_collector_plugin(
        bk_tenant_id=bk_tenant_id,
        bk_biz_ids=bk_biz_ids,
        operator=operator,
        dry_run=dry_run,
        category=STOP,
        job_type="MAIN_STOP_PLUGIN",
        plugin_version="",
        operation_host_key="stop_host_ids",
        host_plan_loader=_get_stop_host_ids,
        empty_operation_message="no proxy host has bk-collector installed",
        dry_run_message="would stop bk-collector",
    )


def refresh_biz_bk_collector_proxy_configs(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    config_types: list[str] | tuple[str, ...] | None = None,
    operator: str = "system",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Refresh bk-collector proxy configs for selected config families."""
    selected_config_types = _normalize_config_types(config_types)
    report = _init_report(
        bk_tenant_id=bk_tenant_id,
        bk_biz_ids=bk_biz_ids,
        operator=operator,
        dry_run=dry_run,
        categories=selected_config_types,
    )

    with _local_operator_context(bk_tenant_id=bk_tenant_id, operator=operator):
        for config_type in selected_config_types:
            if config_type == APM_APPLICATION:
                _refresh_apm_applications(report, bk_tenant_id=bk_tenant_id, bk_biz_ids=bk_biz_ids, dry_run=dry_run)
            elif config_type == CUSTOM_REPORT:
                _refresh_custom_report(report, bk_tenant_id=bk_tenant_id, bk_biz_ids=bk_biz_ids, dry_run=dry_run)
            elif config_type == LOG:
                _refresh_log(report, bk_tenant_id=bk_tenant_id, bk_biz_ids=bk_biz_ids, dry_run=dry_run)

    report["summary"] = _build_summary(report["details"], dry_run=dry_run)
    return report


def _operate_biz_bk_collector_plugin(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    operator: str,
    dry_run: bool,
    category: str,
    job_type: str,
    plugin_version: str,
    operation_host_key: str,
    host_plan_loader: Callable[..., tuple[list[int], list[int]]],
    empty_operation_message: str,
    dry_run_message: str,
) -> dict[str, Any]:
    report = _init_report(
        bk_tenant_id=bk_tenant_id,
        bk_biz_ids=bk_biz_ids,
        operator=operator,
        dry_run=dry_run,
        categories=(category,),
    )
    report["plugin_name"] = PLUGIN_NAME
    if plugin_version:
        report["plugin_version"] = plugin_version

    with _local_operator_context(bk_tenant_id=bk_tenant_id, operator=operator):
        for bk_biz_id in bk_biz_ids:
            record = {
                "bk_biz_id": bk_biz_id,
                "plugin_name": PLUGIN_NAME,
                "plugin_version": plugin_version,
                "target_host_ids": [],
                operation_host_key: [],
                "skipped_host_ids": [],
            }
            try:
                target_host_ids = _unique_ints(BkCollectorConfig.get_target_host_ids_by_biz_id(bk_tenant_id, bk_biz_id))
                record["target_host_ids"] = target_host_ids
                if not target_host_ids:
                    record.update({"action": "skip", "result": True, "message": "no proxy host found"})
                    report["details"][category].append(record)
                    continue

                operation_host_ids, skipped_host_ids = host_plan_loader(
                    bk_tenant_id=bk_tenant_id,
                    bk_host_ids=target_host_ids,
                    plugin_name=PLUGIN_NAME,
                    plugin_version=plugin_version,
                )
                record[operation_host_key] = operation_host_ids
                record["skipped_host_ids"] = skipped_host_ids
                if not operation_host_ids:
                    record.update({"action": "skip", "result": True, "message": empty_operation_message})
                    report["details"][category].append(record)
                    continue

                if dry_run:
                    record.update({"action": "dry_run", "result": None, "message": dry_run_message})
                    report["details"][category].append(record)
                    continue

                operate_result = api.node_man.plugin_operate(
                    bk_tenant_id=bk_tenant_id,
                    plugin_params=_build_plugin_params(plugin_version=plugin_version),
                    job_type=job_type,
                    bk_host_id=operation_host_ids,
                )
            except Exception as error:  # noqa: BLE001 - keep processing other businesses.
                record.update({"action": category, "result": False, "message": str(error)})
            else:
                record.update(
                    {
                        "action": category,
                        "result": True,
                        "message": "success",
                        "operate_result": operate_result,
                    }
                )
            report["details"][category].append(record)

    report["summary"] = _build_summary(report["details"], dry_run=dry_run)
    return report


def _build_biz_bk_collector_operation_error_report(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    operator: str,
    dry_run: bool,
    category: str,
    operation_host_key: str,
    message: str,
) -> dict[str, Any]:
    report = _init_report(
        bk_tenant_id=bk_tenant_id,
        bk_biz_ids=bk_biz_ids,
        operator=operator,
        dry_run=dry_run,
        categories=(category,),
    )
    for bk_biz_id in bk_biz_ids:
        report["details"][category].append(
            {
                "bk_biz_id": bk_biz_id,
                "plugin_name": PLUGIN_NAME,
                "plugin_version": "",
                "target_host_ids": [],
                operation_host_key: [],
                "skipped_host_ids": [],
                "action": category,
                "result": False,
                "message": message,
            }
        )
    report["summary"] = _build_summary(report["details"], dry_run=dry_run)
    return report


def _refresh_apm_applications(
    report: dict[str, Any],
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    dry_run: bool,
) -> None:
    for application in _list_apm_applications(bk_tenant_id=bk_tenant_id, bk_biz_ids=bk_biz_ids):
        record = {
            "bk_tenant_id": bk_tenant_id,
            "bk_biz_id": application.bk_biz_id,
            "app_name": application.app_name,
            "config_type": APM_APPLICATION,
        }
        if dry_run:
            record.update({"action": "dry_run", "result": None, "message": "would refresh apm application config"})
            report["details"][APM_APPLICATION].append(record)
            continue

        try:
            ApplicationConfig(application).refresh()
        except Exception as error:  # noqa: BLE001 - keep processing other applications.
            record.update({"action": "refresh", "result": False, "message": str(error)})
        else:
            record.update({"action": "refresh", "result": True, "message": "success"})
        report["details"][APM_APPLICATION].append(record)


def _refresh_custom_report(
    report: dict[str, Any],
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    dry_run: bool,
) -> None:
    for bk_biz_id in bk_biz_ids:
        record = {
            "bk_tenant_id": bk_tenant_id,
            "bk_biz_id": bk_biz_id,
            "config_type": CUSTOM_REPORT,
            "deploy_targets": ["node_man"],
        }
        try:
            refresh_result = CustomReportSubscription.refresh_collector_custom_conf(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                deploy_targets=("node_man",),
                dry_run=dry_run,
            )
        except Exception as error:  # noqa: BLE001 - keep processing other businesses.
            record.update(
                {
                    "action": "dry_run" if dry_run else "refresh",
                    "result": False,
                    "message": str(error),
                }
            )
        else:
            failed_count = (refresh_result or {}).get("summary", {}).get("failed_count", 0)
            if dry_run:
                record.update({"action": "dry_run", "result": None, "message": "would refresh custom report config"})
            elif failed_count:
                record.update(
                    {
                        "action": "refresh",
                        "result": False,
                        "message": f"failed targets: {failed_count}",
                    }
                )
            else:
                record.update({"action": "refresh", "result": True, "message": "success"})
            record["refresh_result"] = refresh_result
        report["details"][CUSTOM_REPORT].append(record)


def _refresh_log(
    report: dict[str, Any],
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    dry_run: bool,
) -> None:
    for log_group in _list_log_groups(bk_tenant_id=bk_tenant_id, bk_biz_ids=bk_biz_ids):
        record = {
            "bk_tenant_id": bk_tenant_id,
            "bk_biz_id": log_group.bk_biz_id,
            "log_group_id": log_group.log_group_id,
            "log_group_name": log_group.log_group_name,
            "config_type": LOG,
        }
        if dry_run:
            record.update({"action": "dry_run", "result": None, "message": "would refresh log config"})
            report["details"][LOG].append(record)
            continue

        try:
            LogSubscriptionConfig.refresh(log_group)
        except Exception as error:  # noqa: BLE001 - keep processing other log groups.
            record.update({"action": "refresh", "result": False, "message": str(error)})
        else:
            record.update({"action": "refresh", "result": True, "message": "success"})
        report["details"][LOG].append(record)


def _get_deploy_host_ids(
    *, bk_tenant_id: str, bk_host_ids: list[int], plugin_name: str, plugin_version: str
) -> tuple[list[int], list[int]]:
    plugin_info_list = _list_plugin_info_by_host_ids(bk_tenant_id=bk_tenant_id, bk_host_ids=bk_host_ids)
    returned_host_ids = {plugin_info["bk_host_id"] for plugin_info in plugin_info_list}
    skipped_host_ids = []
    deploy_host_ids = []

    for plugin_info in plugin_info_list:
        current_version = _get_current_plugin_version(plugin_info.get("plugin_status") or [], plugin_name)
        if current_version == plugin_version:
            skipped_host_ids.append(plugin_info["bk_host_id"])
        else:
            deploy_host_ids.append(plugin_info["bk_host_id"])

    deploy_host_ids.extend([bk_host_id for bk_host_id in bk_host_ids if bk_host_id not in returned_host_ids])
    return _unique_ints(deploy_host_ids), _unique_ints(skipped_host_ids)


def _get_stop_host_ids(
    *, bk_tenant_id: str, bk_host_ids: list[int], plugin_name: str, plugin_version: str = ""
) -> tuple[list[int], list[int]]:
    plugin_info_list = _list_plugin_info_by_host_ids(bk_tenant_id=bk_tenant_id, bk_host_ids=bk_host_ids)
    plugin_info_by_host_id = {plugin_info["bk_host_id"]: plugin_info for plugin_info in plugin_info_list}
    skipped_host_ids = []
    stop_host_ids = []

    for bk_host_id in bk_host_ids:
        plugin_info = plugin_info_by_host_id.get(bk_host_id)
        if plugin_info and _has_plugin(plugin_info.get("plugin_status") or [], plugin_name):
            stop_host_ids.append(bk_host_id)
        else:
            skipped_host_ids.append(bk_host_id)

    return _unique_ints(stop_host_ids), _unique_ints(skipped_host_ids)


def _list_plugin_info_by_host_ids(*, bk_tenant_id: str, bk_host_ids: list[int]) -> list[dict[str, Any]]:
    params = {"page": 1, "pagesize": len(bk_host_ids), "conditions": [], "bk_host_id": bk_host_ids}
    return api.node_man.plugin_search(bk_tenant_id=bk_tenant_id, **params).get("list", [])


def _get_current_plugin_version(plugin_status: list[dict[str, Any]], plugin_name: str) -> str:
    proc = next((item for item in plugin_status if item.get("name") == plugin_name), {})
    current_plugin_version = VERSION_PATTERN.search(proc.get("version", ""))
    return current_plugin_version.group() if current_plugin_version else ""


def _has_plugin(plugin_status: list[dict[str, Any]], plugin_name: str) -> bool:
    return any(item.get("name") == plugin_name for item in plugin_status)


def _build_plugin_params(*, plugin_version: str) -> dict[str, str]:
    plugin_params = {"name": PLUGIN_NAME}
    if plugin_version:
        plugin_params["version"] = plugin_version
    return plugin_params


def _find_latest_plugin_version(*, bk_tenant_id: str, plugin_name: str) -> str:
    default_version = "0.0.0"
    plugin_infos = api.node_man.plugin_info(name=plugin_name, bk_tenant_id=bk_tenant_id)
    version_str_list = [
        plugin_info.get("version", default_version) for plugin_info in plugin_infos if plugin_info.get("is_ready", True)
    ]
    return get_max_version(default_version, version_str_list)


def _list_apm_applications(*, bk_tenant_id: str, bk_biz_ids: list[int]) -> list[ApmApplication]:
    return list(
        ApmApplication.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id__in=bk_biz_ids, is_enabled=True).order_by(
            "bk_biz_id", "app_name"
        )
    )


def _list_log_groups(*, bk_tenant_id: str, bk_biz_ids: list[int]) -> list[LogGroup]:
    return list(
        LogGroup.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id__in=bk_biz_ids,
            is_enable=True,
            is_need_deploy_collector_config=True,
        ).order_by("bk_biz_id", "log_group_id")
    )


def _normalize_config_types(config_types: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if not config_types:
        return CONFIG_TYPES

    normalized_config_types = tuple(dict.fromkeys(str(config_type).strip() for config_type in config_types))
    invalid_config_types = sorted(set(normalized_config_types) - set(CONFIG_TYPES))
    if invalid_config_types:
        raise ValueError(f"unsupported config types: {invalid_config_types}")
    return normalized_config_types


def _build_summary(details: dict[str, list[dict[str, Any]]], *, dry_run: bool) -> dict[str, dict[str, int]]:
    summary = {}
    for category, records in details.items():
        summary[category] = {
            "matched_count": len(records),
            "planned_count": sum(1 for record in records if record["action"] == "dry_run") if dry_run else 0,
            "succeeded_count": sum(
                1 for record in records if record["action"] in SUCCEEDED_ACTIONS and record["result"] is True
            ),
            "skipped_count": sum(1 for record in records if record["action"] == "skip"),
            "failed_count": sum(1 for record in records if record["result"] is False),
        }
    summary["total"] = {
        key: sum(category_summary[key] for category_summary in summary.values())
        for key in ["matched_count", "planned_count", "succeeded_count", "skipped_count", "failed_count"]
    }
    return summary


def _init_report(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int] | None,
    operator: str,
    dry_run: bool,
    categories: tuple[str, ...],
) -> dict[str, Any]:
    report = {
        "dry_run": dry_run,
        "bk_tenant_id": bk_tenant_id,
        "operator": operator,
        "details": {category: [] for category in categories},
        "summary": {},
    }
    if bk_biz_ids is not None:
        report["bk_biz_ids"] = bk_biz_ids
    return report


def _unique_ints(values) -> list[int]:
    return list(dict.fromkeys(int(value) for value in values))


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
