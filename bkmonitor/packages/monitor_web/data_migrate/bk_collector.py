from __future__ import annotations

import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from typing import Any

from django.conf import settings

from apm.core.application_config import ApplicationConfig
from apm.models import ApmApplication, SubscriptionConfig
from bkmonitor.models import GlobalConfig
from bkmonitor.utils.bk_collector_config import BkCollectorConfig
from bkmonitor.utils.local import local
from bkmonitor.utils.tenant import set_local_tenant_id
from bkmonitor.utils.user import set_local_username
from bkmonitor.utils.version import get_max_version
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from metadata.models import CustomReportSubscription, LogGroup, LogSubscriptionConfig

logger = logging.getLogger(__name__)

PLUGIN_NAME = "bk-collector"
APM_APPLICATION = "apm_application"
CUSTOM_REPORT = "custom_report"
LOG = "log"
INSTALL = "install"
STOP = "stop"
DISABLE_AUTO_INSPECTION = "disable_auto_inspection"
UPDATE = "update"
RETRY = "retry"
NEW_ENV_BLACK_LIST = "new_env_black_list"
NEW_ENV_BIZ_BLACK_LIST_CONFIG_KEY = "NEW_ENV_BIZ_BLACK_LIST"
NEW_ENV_BIZ_WHITE_LIST_CONFIG_KEY = "NEW_ENV_BIZ_WHITE_LIST"

CONFIG_TYPES = (APM_APPLICATION, CUSTOM_REPORT, LOG)
SUCCEEDED_ACTIONS = {INSTALL, STOP, "refresh", DISABLE_AUTO_INSPECTION, UPDATE, RETRY}
CONFIG_DELIVERY_SUCCESS_STATUS = "SUCCESS"
CONFIG_DELIVERY_TIMEOUT_STATUS = "TIMEOUT"
PROXY_CONFIG_RENDER_STEP_CODE = "render_and_push_config"
PENDING_CONFIG_DELIVERY_STATUSES = {"PENDING", "RUNNING", "DEPLOYING"}
PLUGIN_JOB_SUCCESS_STATUS = "SUCCESS"
PLUGIN_JOB_PENDING_STATUSES = {"PENDING", "RUNNING", "DEPLOYING"}
PLUGIN_JOB_TIMEOUT_STATUS = "TIMEOUT"
# 安装场景仅跳过 Agent 未安装的主机；停止场景仅对 Agent RUNNING 的主机执行。
AGENT_NOT_INSTALLED_STATUS = "NOT_INSTALLED"
AGENT_RUNNING_STATUS = "RUNNING"
SKIP_REASON_AGENT_NOT_INSTALLED = "agent not installed"
SKIP_REASON_AGENT_NOT_RUNNING = "agent not running"
SKIP_REASON_BK_COLLECTOR_NOT_INSTALLED = "bk-collector not installed"
DEFAULT_PLUGIN_JOB_WAIT_TIMEOUT = 90
DEFAULT_PLUGIN_JOB_POLL_INTERVAL = 10
DEFAULT_CONFIG_DELIVERY_WAIT_TIMEOUT = 90
DEFAULT_CONFIG_DELIVERY_POLL_INTERVAL = 10


def _set_nodeman_api() -> str | None:
    """
    单租户情况下，如果使用的是esb，有些API调用会有问题，需要临时切换到apigw
    """
    original_api_base_url = getattr(settings, "BKNODEMAN_API_BASE_URL", None)
    if not settings.ENABLE_MULTI_TENANT_MODE:
        settings.BKNODEMAN_API_BASE_URL = f"{settings.BK_COMPONENT_API_URL}/api/bk-nodeman/prod/"
    return original_api_base_url


def _restore_nodeman_api(original_api_base_url: str | None) -> None:
    settings.BKNODEMAN_API_BASE_URL = original_api_base_url


def _with_nodeman_api_context(func: Callable[..., dict[str, Any]]):
    @wraps(func)
    def wrapped(*args, **kwargs):
        original_api_base_url = _set_nodeman_api()
        try:
            return func(*args, **kwargs)
        finally:
            _restore_nodeman_api(original_api_base_url)

    return wrapped


@_with_nodeman_api_context
def install_biz_bk_collector(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    operator: str = "system",
    dry_run: bool = False,
    job_wait_timeout: int = DEFAULT_PLUGIN_JOB_WAIT_TIMEOUT,
    job_poll_interval: int = DEFAULT_PLUGIN_JOB_POLL_INTERVAL,
    skip_hosts_without_agent: bool = False,
) -> dict[str, Any]:
    """Install or upgrade bk-collector on proxy hosts used by the given businesses.

    默认不跳过 Agent 未安装的主机（``skip_hosts_without_agent=False``），保持全量安装；
    如需跳过，可显式传入 ``skip_hosts_without_agent=True``。
    """
    logger.info(
        "install_biz_bk_collector: start bk_tenant_id=%s bk_biz_ids=%s operator=%s dry_run=%s "
        "job_wait_timeout=%s job_poll_interval=%s skip_hosts_without_agent=%s",
        bk_tenant_id,
        bk_biz_ids,
        operator,
        dry_run,
        job_wait_timeout,
        job_poll_interval,
        skip_hosts_without_agent,
    )
    with _local_operator_context(bk_tenant_id=bk_tenant_id, operator=operator):
        try:
            plugin_version = _find_latest_plugin_version(bk_tenant_id=bk_tenant_id, plugin_name=PLUGIN_NAME)
            logger.info(
                "install_biz_bk_collector: latest plugin version loaded bk_tenant_id=%s plugin_name=%s "
                "plugin_version=%s",
                bk_tenant_id,
                PLUGIN_NAME,
                plugin_version,
            )
            if not plugin_version or plugin_version == "0.0.0":
                raise ValueError(f"node_man has no ready {PLUGIN_NAME} version")
        except Exception as error:  # noqa: BLE001 - migration command reports per-business failures.
            logger.exception(
                "install_biz_bk_collector: load latest plugin version failed bk_tenant_id=%s plugin_name=%s",
                bk_tenant_id,
                PLUGIN_NAME,
            )
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
        empty_operation_message="no proxy host available to install bk-collector",
        dry_run_message="would install bk-collector",
        job_wait_timeout=job_wait_timeout,
        job_poll_interval=job_poll_interval,
        skip_hosts_without_agent=skip_hosts_without_agent,
    )


@_with_nodeman_api_context
def stop_biz_bk_collector(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    operator: str = "system",
    dry_run: bool = False,
    job_wait_timeout: int = DEFAULT_PLUGIN_JOB_WAIT_TIMEOUT,
    job_poll_interval: int = DEFAULT_PLUGIN_JOB_POLL_INTERVAL,
    skip_hosts_without_agent: bool = True,
) -> dict[str, Any]:
    """Stop bk-collector on proxy hosts used by the given businesses.

    默认跳过 Agent 状态非 RUNNING 的主机（``skip_hosts_without_agent=True``）；
    如需对这些主机也执行停止，可显式传入 ``skip_hosts_without_agent=False``。
    """
    logger.info(
        "stop_biz_bk_collector: start bk_tenant_id=%s bk_biz_ids=%s operator=%s dry_run=%s "
        "job_wait_timeout=%s job_poll_interval=%s skip_hosts_without_agent=%s",
        bk_tenant_id,
        bk_biz_ids,
        operator,
        dry_run,
        job_wait_timeout,
        job_poll_interval,
        skip_hosts_without_agent,
    )
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
        job_wait_timeout=job_wait_timeout,
        job_poll_interval=job_poll_interval,
        skip_hosts_without_agent=skip_hosts_without_agent,
    )


def refresh_biz_bk_collector_proxy_configs(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    config_types: list[str] | tuple[str, ...] | None = None,
    operator: str = "system",
    dry_run: bool = False,
    check_delivery: bool = True,
    delivery_wait_timeout: int = DEFAULT_CONFIG_DELIVERY_WAIT_TIMEOUT,
    delivery_poll_interval: int = DEFAULT_CONFIG_DELIVERY_POLL_INTERVAL,
    retry_render_failures: bool = True,
    include_details: bool = False,
) -> dict[str, Any]:
    """Refresh bk-collector proxy configs for selected config families.

    非 dry-run 且开启下发检查时，会在检查后复用检查结果，对 render 失败的订阅调用
    retry_subscription 补一轮执行，用于解决节点管理对多次失败订阅不再自动重试的问题。
    """
    selected_config_types = _normalize_config_types(config_types)
    logger.info(
        "refresh_biz_bk_collector_proxy_configs: start bk_tenant_id=%s bk_biz_ids=%s config_types=%s "
        "operator=%s dry_run=%s check_delivery=%s delivery_wait_timeout=%s delivery_poll_interval=%s "
        "retry_render_failures=%s include_details=%s",
        bk_tenant_id,
        bk_biz_ids,
        selected_config_types,
        operator,
        dry_run,
        check_delivery,
        delivery_wait_timeout,
        delivery_poll_interval,
        retry_render_failures,
        include_details,
    )
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
    if check_delivery and not dry_run:
        logger.info(
            "refresh_biz_bk_collector_proxy_configs: start delivery check bk_tenant_id=%s bk_biz_ids=%s "
            "config_types=%s",
            bk_tenant_id,
            bk_biz_ids,
            selected_config_types,
        )
        report["delivery_check"] = check_biz_bk_collector_proxy_config_delivery(
            bk_tenant_id=bk_tenant_id,
            bk_biz_ids=bk_biz_ids,
            config_types=selected_config_types,
            operator=operator,
            wait_timeout=delivery_wait_timeout,
            poll_interval=delivery_poll_interval,
            subscription_scope=_build_proxy_config_delivery_subscription_scope(report["details"]),
        )

        # 复用上面的下发检查结果，对 render 失败的订阅补一轮执行，不重复检查。
        final_delivery_check = report["delivery_check"]
        if retry_render_failures and report["delivery_check"].get("result") is False:
            logger.info(
                "refresh_biz_bk_collector_proxy_configs: delivery check has failures, retry render failures "
                "bk_tenant_id=%s bk_biz_ids=%s config_types=%s",
                bk_tenant_id,
                bk_biz_ids,
                selected_config_types,
            )
            retry_report = _retry_render_failed_proxy_config_subscriptions(
                bk_tenant_id=bk_tenant_id,
                bk_biz_ids=bk_biz_ids,
                operator=operator,
                dry_run=dry_run,
                categories=selected_config_types,
                delivery_details=report["delivery_check"].get("details"),
            )
            report["retry"] = retry_report
            if _count_triggered_render_failure_retry(retry_report["details"]):
                # 仅在确有 render 失败被重试后，才复检一次以反映最终下发状态。
                retry_report["delivery_check"] = check_biz_bk_collector_proxy_config_delivery(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_ids=bk_biz_ids,
                    config_types=selected_config_types,
                    operator=operator,
                    wait_timeout=delivery_wait_timeout,
                    poll_interval=delivery_poll_interval,
                )
                final_delivery_check = retry_report["delivery_check"]
            if not include_details:
                _drop_report_details(retry_report)

        report["delivery_check"] = final_delivery_check
        report["result"] = (
            report["summary"]["total"]["failed_count"] == 0 and final_delivery_check.get("result") is True
        )
        report["message"] = (
            "refresh completed and all proxy configs rendered and pushed successfully"
            if report["result"]
            else "refresh completed but some proxy configs were not rendered and pushed successfully"
        )
    else:
        report["result"] = report["summary"]["total"]["failed_count"] == 0
        if check_delivery and dry_run:
            report["message"] = "dry run completed, proxy config delivery check skipped"
        else:
            report["message"] = "refresh completed, proxy config delivery check skipped"
    logger.info(
        "refresh_biz_bk_collector_proxy_configs: completed bk_tenant_id=%s bk_biz_ids=%s result=%s "
        "summary=%s message=%s",
        bk_tenant_id,
        bk_biz_ids,
        report["result"],
        report["summary"],
        report["message"],
    )
    if not include_details:
        _drop_report_details(report)
    return report


def disable_biz_bk_collector_subscription_auto_inspection(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    operator: str = "system",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Disable NodeMan auto-inspection for migrated bk-collector config subscriptions and blacklist businesses."""
    normalized_bk_biz_ids = _unique_ints(bk_biz_ids)
    logger.info(
        "disable_biz_bk_collector_subscription_auto_inspection: start bk_tenant_id=%s bk_biz_ids=%s "
        "operator=%s dry_run=%s",
        bk_tenant_id,
        normalized_bk_biz_ids,
        operator,
        dry_run,
    )
    report = _init_report(
        bk_tenant_id=bk_tenant_id,
        bk_biz_ids=normalized_bk_biz_ids,
        operator=operator,
        dry_run=dry_run,
        categories=(*CONFIG_TYPES, NEW_ENV_BLACK_LIST),
    )
    subscriptions = _list_proxy_config_delivery_subscriptions(
        bk_tenant_id=bk_tenant_id,
        bk_biz_ids=normalized_bk_biz_ids,
        config_types=CONFIG_TYPES,
    )

    with _local_operator_context(bk_tenant_id=bk_tenant_id, operator=operator):
        for subscription in subscriptions:
            record = _disable_bk_collector_subscription_auto_inspection(subscription, dry_run=dry_run)
            report["details"][subscription["config_type"]].append(record)

    _append_new_env_scope_update_record(
        report,
        category=NEW_ENV_BLACK_LIST,
        config_key=NEW_ENV_BIZ_BLACK_LIST_CONFIG_KEY,
        bk_biz_ids=normalized_bk_biz_ids,
        dry_run=dry_run,
        remove_config_keys=(NEW_ENV_BIZ_WHITE_LIST_CONFIG_KEY,),
        empty_message="no biz to add into new env black list",
    )
    logger.info(
        "disable_biz_bk_collector_subscription_auto_inspection: completed bk_tenant_id=%s bk_biz_ids=%s summary=%s",
        bk_tenant_id,
        normalized_bk_biz_ids,
        report["summary"],
    )
    return report


def check_biz_bk_collector_proxy_config_delivery(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    config_types: list[str] | tuple[str, ...] | None = None,
    operator: str = "system",
    wait_timeout: int = 0,
    poll_interval: int = DEFAULT_CONFIG_DELIVERY_POLL_INTERVAL,
    subscription_scope: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    only_current_bk_biz_id: bool = True,
) -> dict[str, Any]:
    """Check whether bk-collector proxy configs have been rendered and pushed successfully.

    Args:
        only_current_bk_biz_id: 为 True（默认）时，仅统计订阅中属于本业务的 Proxy 主机
            （业务自有 Proxy 及默认直连区域全局主机）的下发状态，忽略从其他业务借用的
            Proxy 主机的下发异常，避免因借用主机失败误判本业务下发结果；为 False 时
            统计订阅下的全部主机，保持原有全量检查行为。
    """
    selected_config_types = _normalize_config_types(config_types)
    normalized_bk_biz_ids = _unique_ints(bk_biz_ids)
    logger.info(
        "check_biz_bk_collector_proxy_config_delivery: start bk_tenant_id=%s bk_biz_ids=%s "
        "config_types=%s operator=%s wait_timeout=%s poll_interval=%s subscription_scope_count=%s",
        bk_tenant_id,
        normalized_bk_biz_ids,
        selected_config_types,
        operator,
        wait_timeout,
        poll_interval,
        len(subscription_scope) if subscription_scope is not None else None,
    )
    normalized_wait_timeout = max(_read_int(wait_timeout), 0)
    normalized_poll_interval = max(_read_int(poll_interval), 0)
    deadline = time.monotonic() + normalized_wait_timeout
    poll_attempts = 0

    while True:
        poll_attempts += 1
        report = _check_biz_bk_collector_proxy_config_delivery_once(
            bk_tenant_id=bk_tenant_id,
            bk_biz_ids=normalized_bk_biz_ids,
            config_types=selected_config_types,
            operator=operator,
            subscription_scope=subscription_scope,
            only_current_bk_biz_id=only_current_bk_biz_id,
        )
        report["poll_attempts"] = poll_attempts
        report["timed_out"] = False
        logger.info(
            "check_biz_bk_collector_proxy_config_delivery: poll result bk_tenant_id=%s bk_biz_ids=%s "
            "poll_attempts=%s result=%s summary=%s message=%s",
            bk_tenant_id,
            normalized_bk_biz_ids,
            poll_attempts,
            report["result"],
            report["summary"],
            report["message"],
        )
        if _is_proxy_config_delivery_terminal(report):
            return report

        if normalized_wait_timeout <= 0:
            return report

        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            report.update(
                {
                    "status": CONFIG_DELIVERY_TIMEOUT_STATUS,
                    "result": False,
                    "timed_out": True,
                    "message": f"proxy config delivery wait timeout, last message: {report['message']}",
                }
            )
            logger.warning(
                "check_biz_bk_collector_proxy_config_delivery: polling timeout bk_tenant_id=%s bk_biz_ids=%s "
                "poll_attempts=%s summary=%s",
                bk_tenant_id,
                normalized_bk_biz_ids,
                poll_attempts,
                report["summary"],
            )
            return report

        sleep_seconds = min(normalized_poll_interval or 1, remaining_seconds)
        if sleep_seconds > 0:
            logger.info(
                "check_biz_bk_collector_proxy_config_delivery: wait next poll bk_tenant_id=%s bk_biz_ids=%s "
                "poll_attempts=%s sleep_seconds=%.2f",
                bk_tenant_id,
                normalized_bk_biz_ids,
                poll_attempts,
                sleep_seconds,
            )
            time.sleep(sleep_seconds)


@_with_nodeman_api_context
def retry_biz_bk_collector_proxy_config_delivery(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    config_types: list[str] | tuple[str, ...] | None = None,
    operator: str = "system",
    dry_run: bool = False,
    recheck_delivery: bool = True,
    delivery_wait_timeout: int = DEFAULT_CONFIG_DELIVERY_WAIT_TIMEOUT,
    delivery_poll_interval: int = DEFAULT_CONFIG_DELIVERY_POLL_INTERVAL,
    include_details: bool = False,
) -> dict[str, Any]:
    """Retry bk-collector proxy config delivery for subscriptions with render-failed proxies.

    节点管理对多次失败的订阅不会再自动重试，导致 refresh 在配置未变化时无法触发下发。
    此命令会先检查配置下发状态，对存在 render 失败实例的订阅调用 retry_subscription 补一轮执行。
    """
    selected_config_types = _normalize_config_types(config_types)
    normalized_bk_biz_ids = _unique_ints(bk_biz_ids)
    logger.info(
        "retry_biz_bk_collector_proxy_config_delivery: start bk_tenant_id=%s bk_biz_ids=%s config_types=%s "
        "operator=%s dry_run=%s recheck_delivery=%s delivery_wait_timeout=%s delivery_poll_interval=%s "
        "include_details=%s",
        bk_tenant_id,
        normalized_bk_biz_ids,
        selected_config_types,
        operator,
        dry_run,
        recheck_delivery,
        delivery_wait_timeout,
        delivery_poll_interval,
        include_details,
    )

    # 先做一次即时检查（不等待），拿到每个订阅下 render 失败的实例明细。
    initial_check = check_biz_bk_collector_proxy_config_delivery(
        bk_tenant_id=bk_tenant_id,
        bk_biz_ids=normalized_bk_biz_ids,
        config_types=selected_config_types,
        operator=operator,
        wait_timeout=0,
    )
    report = _retry_render_failed_proxy_config_subscriptions(
        bk_tenant_id=bk_tenant_id,
        bk_biz_ids=normalized_bk_biz_ids,
        operator=operator,
        dry_run=dry_run,
        categories=selected_config_types,
        delivery_details=initial_check.get("details"),
    )
    report["initial_delivery_check"] = {
        "summary": initial_check.get("summary", {}),
        "message": initial_check.get("message", ""),
    }
    if include_details:
        report["initial_delivery_check"]["failure_summary"] = initial_check.get("failure_summary", {})

    triggered_count = _count_triggered_render_failure_retry(report["details"])

    if recheck_delivery and not dry_run and triggered_count:
        logger.info(
            "retry_biz_bk_collector_proxy_config_delivery: start recheck bk_tenant_id=%s bk_biz_ids=%s "
            "config_types=%s triggered_count=%s",
            bk_tenant_id,
            normalized_bk_biz_ids,
            selected_config_types,
            triggered_count,
        )
        report["delivery_check"] = check_biz_bk_collector_proxy_config_delivery(
            bk_tenant_id=bk_tenant_id,
            bk_biz_ids=normalized_bk_biz_ids,
            config_types=selected_config_types,
            operator=operator,
            wait_timeout=delivery_wait_timeout,
            poll_interval=delivery_poll_interval,
        )
        report["result"] = (
            report["summary"]["total"]["failed_count"] == 0 and report["delivery_check"]["result"] is True
        )
        report["message"] = (
            "retry completed and all proxy configs rendered and pushed successfully"
            if report["result"]
            else "retry completed but some proxy configs were still not rendered and pushed successfully"
        )
    else:
        report["result"] = report["summary"]["total"]["failed_count"] == 0
        if dry_run:
            report["message"] = "dry run completed, proxy config delivery recheck skipped"
        elif not triggered_count:
            report["message"] = "no render-failed proxy config subscription to retry"
        else:
            report["message"] = "retry completed, proxy config delivery recheck skipped"

    logger.info(
        "retry_biz_bk_collector_proxy_config_delivery: completed bk_tenant_id=%s bk_biz_ids=%s result=%s "
        "summary=%s message=%s",
        bk_tenant_id,
        normalized_bk_biz_ids,
        report["result"],
        report["summary"],
        report["message"],
    )
    if not include_details:
        _drop_report_details(report)
    return report


def _retry_render_failed_proxy_config_subscriptions(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    operator: str,
    dry_run: bool,
    categories: tuple[str, ...],
    delivery_details: dict[str, list[dict[str, Any]]] | None,
) -> dict[str, Any]:
    """基于已有的配置下发检查结果，对 render 失败的订阅补一轮执行，避免重复检查。"""
    report = _init_report(
        bk_tenant_id=bk_tenant_id,
        bk_biz_ids=bk_biz_ids,
        operator=operator,
        dry_run=dry_run,
        categories=categories,
    )
    delivery_details = delivery_details or {}
    with _local_operator_context(bk_tenant_id=bk_tenant_id, operator=operator):
        for config_type in categories:
            for detail in delivery_details.get(config_type, []):
                report["details"][config_type].append(
                    _retry_proxy_config_delivery_subscription(detail, dry_run=dry_run)
                )
    report["summary"] = _build_summary(report["details"], dry_run=dry_run)
    return report


def _count_triggered_render_failure_retry(report_details: dict[str, list[dict[str, Any]]]) -> int:
    return sum(1 for records in report_details.values() for record in records if record["action"] in {RETRY, "dry_run"})


def _is_retryable_proxy_config_delivery_instance(instance: dict[str, Any]) -> bool:
    """render 失败（非 pending、非 unknown 且未成功）的实例才需要补一轮执行。

    被标记为 ``ignored`` 的实例（借用的其他业务 Proxy）不属于本业务，不参与补执行，
    避免重试触碰其他业务的 Proxy 主机。
    """
    return (
        not instance.get("ignored")
        and instance.get("result") is not True
        and instance.get("status") not in PENDING_CONFIG_DELIVERY_STATUSES
        and instance.get("status") != "UNKNOWN"
    )


def _retry_proxy_config_delivery_subscription(detail: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    retry_instances = [
        instance for instance in detail.get("instances", []) if _is_retryable_proxy_config_delivery_instance(instance)
    ]
    instance_id_list = [instance["instance_id"] for instance in retry_instances if instance.get("instance_id")]

    record: dict[str, Any] = {
        "config_type": detail.get("config_type"),
        "bk_tenant_id": detail.get("bk_tenant_id"),
        "bk_biz_id": detail.get("bk_biz_id"),
        "subscription_id": detail.get("subscription_id"),
        "target_instance_count": len(instance_id_list),
        "instance_id_list": instance_id_list,
    }
    for optional_key in ("name", "bk_data_id"):
        if optional_key in detail:
            record[optional_key] = detail[optional_key]

    if not instance_id_list:
        record.update({"action": "skip", "result": True, "message": "no render-failed proxy to retry"})
        return record

    logger.info(
        "retry bk-collector proxy config subscription: start config_type=%s bk_tenant_id=%s bk_biz_id=%s "
        "subscription_id=%s target_instance_count=%s dry_run=%s",
        record["config_type"],
        record["bk_tenant_id"],
        record["bk_biz_id"],
        record["subscription_id"],
        record["target_instance_count"],
        dry_run,
    )

    if dry_run:
        record.update(
            {
                "action": "dry_run",
                "result": None,
                "message": f"would retry {len(instance_id_list)} render-failed proxies",
            }
        )
        return record

    try:
        retry_result = api.node_man.retry_subscription(
            bk_tenant_id=record["bk_tenant_id"],
            subscription_id=record["subscription_id"],
            instance_id_list=instance_id_list,
        )
    except Exception as error:  # noqa: BLE001 - migration command reports per-subscription failures.
        logger.exception(
            "retry bk-collector proxy config subscription: failed config_type=%s bk_tenant_id=%s bk_biz_id=%s "
            "subscription_id=%s",
            record["config_type"],
            record["bk_tenant_id"],
            record["bk_biz_id"],
            record["subscription_id"],
        )
        record.update({"action": RETRY, "result": False, "message": str(error)})
    else:
        logger.info(
            "retry bk-collector proxy config subscription: completed config_type=%s bk_tenant_id=%s bk_biz_id=%s "
            "subscription_id=%s retry_result=%s",
            record["config_type"],
            record["bk_tenant_id"],
            record["bk_biz_id"],
            record["subscription_id"],
            retry_result,
        )
        record.update({"action": RETRY, "result": True, "message": "success", "retry_result": retry_result})
    return record


def _load_biz_owned_proxy_host_ids(*, bk_tenant_id: str, bk_biz_id: int) -> set[int] | None:
    """加载指定业务视角下应纳入下发检查的 Proxy 主机 host id 集合。

    集合包含两部分：

    - 业务自有的 Proxy 主机（``only_current_bk_biz_id=True``），即 bk_biz_id 归属当前业务的 Proxy；
    - 默认租户直连区域下的全局配置主机。

    订阅实际会下发到业务所在管控区域下的全部 Proxy（可能包含从其他业务借用的 Proxy），
    这些借用主机不在本集合内，其下发异常在检查时应被忽略，避免因借用 Proxy 的失败
    误判本业务的下发结果。

    Args:
        bk_tenant_id: 租户 ID。
        bk_biz_id: 业务 ID，非正数（如 0 号直连业务）时跳过业务自有 Proxy 查询。

    Returns:
        本业务视角下需要关注的 Proxy 主机 host id 集合。查询成功但没有应统计主机时
        返回空集合；查询失败时返回 ``None``，调用方应降级为不过滤，避免用不完整集合误判。
    """
    owned_host_ids: set[int] = set()
    if bk_biz_id and bk_biz_id > 0:
        try:
            owned_host_ids.update(
                _unique_ints(
                    BkCollectorConfig.get_target_host_ids_by_biz_id(
                        bk_tenant_id, bk_biz_id, only_current_bk_biz_id=True
                    )
                )
            )
        except Exception:  # noqa: BLE001 - 查询失败时退化为不过滤，避免用不完整集合误判
            logger.exception(
                "load_biz_owned_proxy_host_ids: load current biz proxy hosts failed bk_tenant_id=%s bk_biz_id=%s",
                bk_tenant_id,
                bk_biz_id,
            )
            return None
    try:
        owned_host_ids.update(_unique_ints(BkCollectorConfig.get_target_host_in_default_cloud_area()))
    except Exception:  # noqa: BLE001 - 查询失败时退化为不过滤，避免用不完整集合误判
        logger.exception(
            "load_biz_owned_proxy_host_ids: load default cloud area hosts failed bk_tenant_id=%s bk_biz_id=%s",
            bk_tenant_id,
            bk_biz_id,
        )
        return None
    return owned_host_ids


def _check_biz_bk_collector_proxy_config_delivery_once(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    config_types: tuple[str, ...],
    operator: str,
    subscription_scope: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    only_current_bk_biz_id: bool = True,
) -> dict[str, Any]:
    report = _init_report(
        bk_tenant_id=bk_tenant_id,
        bk_biz_ids=bk_biz_ids,
        operator=operator,
        dry_run=False,
        categories=config_types,
    )

    subscriptions = _list_proxy_config_delivery_subscriptions(
        bk_tenant_id=bk_tenant_id,
        bk_biz_ids=bk_biz_ids,
        config_types=config_types,
    )
    listed_subscription_count = len(subscriptions)
    subscriptions = _filter_proxy_config_delivery_subscriptions_by_scope(
        subscriptions,
        subscription_scope=subscription_scope,
    )
    logger.info(
        "check_biz_bk_collector_proxy_config_delivery: matched subscriptions bk_tenant_id=%s "
        "bk_biz_ids=%s listed_subscription_count=%s subscription_count=%s subscription_scope_count=%s "
        "only_current_bk_biz_id=%s",
        bk_tenant_id,
        bk_biz_ids,
        listed_subscription_count,
        len(subscriptions),
        len(subscription_scope) if subscription_scope is not None else None,
        only_current_bk_biz_id,
    )

    # 缓存按 (租户, 业务) 计算的本业务 Proxy host 集合，避免同一业务重复请求节点管理/CMDB
    owned_host_ids_cache: dict[tuple[str, int], set[int] | None] = {}
    with _local_operator_context(bk_tenant_id=bk_tenant_id, operator=operator):
        for subscription in subscriptions:
            owned_host_ids: set[int] | None = None
            if only_current_bk_biz_id:
                cache_key = (subscription["bk_tenant_id"], _read_int(subscription.get("bk_biz_id")))
                if cache_key not in owned_host_ids_cache:
                    owned_host_ids_cache[cache_key] = _load_biz_owned_proxy_host_ids(
                        bk_tenant_id=cache_key[0], bk_biz_id=cache_key[1]
                    )
                # None 表示 owner 查询失败，降级不过滤；空集合表示查询成功但本业务没有应统计主机
                owned_host_ids = owned_host_ids_cache[cache_key]
            report["details"][subscription["config_type"]].append(
                _check_proxy_config_delivery_subscription(subscription, owned_host_ids=owned_host_ids)
            )

    report["summary"] = _build_config_delivery_summary(report["details"])
    report["failure_summary"] = _build_config_delivery_failure_summary(report["details"])
    total_summary = report["summary"]["total"]
    report["result"] = (
        total_summary["failed_count"] == 0
        and total_summary["pending_count"] == 0
        and total_summary["unknown_count"] == 0
    )
    if total_summary["subscription_count"] == 0:
        report["message"] = "no matched bk-collector proxy config subscription"
    elif report["result"]:
        report["message"] = "all proxy configs rendered and pushed successfully"
    else:
        report["message"] = "some proxy configs were not rendered and pushed successfully"
    logger.info(
        "check_biz_bk_collector_proxy_config_delivery: completed bk_tenant_id=%s bk_biz_ids=%s "
        "result=%s summary=%s message=%s",
        bk_tenant_id,
        bk_biz_ids,
        report["result"],
        report["summary"],
        report["message"],
    )
    return report


def _is_proxy_config_delivery_terminal(report: dict[str, Any]) -> bool:
    total_summary = report["summary"]["total"]
    if total_summary["subscription_count"] == 0 or report["result"] is True:
        return True
    return (
        total_summary["failed_count"] > 0
        and total_summary.get("pending_count", 0) == 0
        and total_summary.get("unknown_count", 0) == 0
    )


def _drop_report_details(report: dict[str, Any]) -> None:
    report.pop("details", None)
    delivery_check = report.get("delivery_check")
    if isinstance(delivery_check, dict):
        delivery_check.pop("details", None)


def _disable_bk_collector_subscription_auto_inspection(
    subscription: dict[str, Any], *, dry_run: bool
) -> dict[str, Any]:
    record = {
        **subscription,
        "action": "dry_run" if dry_run else DISABLE_AUTO_INSPECTION,
        "result": None if dry_run else True,
        "message": "would disable subscription auto inspection" if dry_run else "success",
    }
    logger.info(
        "disable bk-collector subscription auto inspection: start config_type=%s bk_tenant_id=%s "
        "bk_biz_id=%s subscription_id=%s dry_run=%s",
        subscription.get("config_type"),
        subscription.get("bk_tenant_id"),
        subscription.get("bk_biz_id"),
        subscription.get("subscription_id"),
        dry_run,
    )
    if dry_run:
        return record

    try:
        result = api.node_man.switch_subscription(
            bk_tenant_id=subscription["bk_tenant_id"],
            subscription_id=subscription["subscription_id"],
            action="disable",
        )
    except Exception as error:  # noqa: BLE001 - migration command reports per-subscription failures.
        logger.exception(
            "disable bk-collector subscription auto inspection: failed config_type=%s bk_tenant_id=%s "
            "bk_biz_id=%s subscription_id=%s",
            subscription.get("config_type"),
            subscription.get("bk_tenant_id"),
            subscription.get("bk_biz_id"),
            subscription.get("subscription_id"),
        )
        record.update({"result": False, "message": str(error)})
    else:
        logger.info(
            "disable bk-collector subscription auto inspection: completed config_type=%s bk_tenant_id=%s "
            "bk_biz_id=%s subscription_id=%s result=%s",
            subscription.get("config_type"),
            subscription.get("bk_tenant_id"),
            subscription.get("bk_biz_id"),
            subscription.get("subscription_id"),
            result,
        )
        record["switch_result"] = result
    return record


def _append_new_env_scope_update_record(
    report: dict[str, Any],
    *,
    category: str,
    config_key: str,
    bk_biz_ids: list[int],
    dry_run: bool,
    remove_config_keys: tuple[str, ...] = (),
    empty_message: str,
) -> None:
    report["details"].setdefault(category, [])
    try:
        record = _sync_new_env_biz_scope_config(
            config_key=config_key,
            bk_biz_ids=bk_biz_ids,
            dry_run=dry_run,
            remove_config_keys=remove_config_keys,
            empty_message=empty_message,
        )
    except Exception as error:  # noqa: BLE001 - keep a structured failure in command output.
        logger.exception(
            "sync new env biz scope config failed config_key=%s bk_biz_ids=%s dry_run=%s remove_config_keys=%s",
            config_key,
            bk_biz_ids,
            dry_run,
            remove_config_keys,
        )
        record = {
            "config_key": config_key,
            "bk_biz_ids": _unique_ints(bk_biz_ids),
            "remove_config_keys": list(remove_config_keys),
            "action": "dry_run" if dry_run else UPDATE,
            "result": False,
            "message": str(error),
        }
    report["details"][category].append(record)
    report["summary"] = _build_summary(report["details"], dry_run=report["dry_run"])


def _sync_new_env_biz_scope_config(
    *,
    config_key: str,
    bk_biz_ids: list[int],
    dry_run: bool,
    remove_config_keys: tuple[str, ...],
    empty_message: str,
) -> dict[str, Any]:
    normalized_bk_biz_ids = _unique_ints(bk_biz_ids)
    current_value = _get_global_config_biz_id_list(config_key)
    next_value = _merge_biz_id_list(current_value, normalized_bk_biz_ids)
    removed_before_values = {
        remove_config_key: _get_global_config_biz_id_list(remove_config_key) for remove_config_key in remove_config_keys
    }
    removed_values = {
        remove_config_key: _remove_biz_ids_from_list(remove_config_value, normalized_bk_biz_ids)
        for remove_config_key, remove_config_value in removed_before_values.items()
    }
    record = {
        "config_key": config_key,
        "bk_biz_ids": normalized_bk_biz_ids,
        "before": current_value,
        "after": next_value,
        "remove_config_keys": list(remove_config_keys),
        "removed_configs": {
            remove_config_key: {
                "before": removed_before_values[remove_config_key],
                "after": removed_value,
            }
            for remove_config_key, removed_value in removed_values.items()
        },
    }
    if not normalized_bk_biz_ids:
        record.update({"action": "skip", "result": True, "message": empty_message})
        return record
    if dry_run:
        record.update({"action": "dry_run", "result": None, "message": f"would update {config_key}"})
        return record

    GlobalConfig.set(config_key, next_value)
    setattr(settings, config_key, next_value)
    for remove_config_key, removed_value in removed_values.items():
        GlobalConfig.set(remove_config_key, removed_value)
        setattr(settings, remove_config_key, removed_value)
    record.update({"action": UPDATE, "result": True, "message": "success"})
    return record


def _get_global_config_biz_id_list(config_key: str) -> list[int]:
    value = GlobalConfig.get(config_key, getattr(settings, config_key, []))
    return _unique_ints(value or [])


def _merge_biz_id_list(current_value: list[int], added_biz_ids: list[int]) -> list[int]:
    return _unique_ints([*current_value, *added_biz_ids])


def _remove_biz_ids_from_list(current_value: list[int], removed_biz_ids: list[int]) -> list[int]:
    removed = set(_unique_ints(removed_biz_ids))
    return [bk_biz_id for bk_biz_id in _unique_ints(current_value) if bk_biz_id not in removed]


def _list_proxy_config_delivery_subscriptions(
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    config_types: tuple[str, ...],
) -> list[dict[str, Any]]:
    query_bk_biz_ids = _unique_ints(bk_biz_ids)
    subscriptions: list[dict[str, Any]] = []

    if APM_APPLICATION in config_types:
        for record in (
            SubscriptionConfig.objects.filter(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id__in=query_bk_biz_ids,
                subscription_id__gt=0,
            )
            .values("bk_tenant_id", "bk_biz_id", "app_name", "subscription_id")
            .order_by("bk_biz_id", "app_name", "subscription_id")
        ):
            subscriptions.append(
                {
                    "config_type": APM_APPLICATION,
                    "bk_tenant_id": record["bk_tenant_id"],
                    "bk_biz_id": record["bk_biz_id"],
                    "subscription_id": record["subscription_id"],
                    "name": record["app_name"],
                }
            )

    if CUSTOM_REPORT in config_types:
        for record in (
            CustomReportSubscription.objects.filter(bk_biz_id__in=query_bk_biz_ids, subscription_id__gt=0)
            .values("bk_biz_id", "bk_data_id", "subscription_id")
            .order_by("bk_biz_id", "bk_data_id", "subscription_id")
        ):
            subscriptions.append(
                {
                    "config_type": CUSTOM_REPORT,
                    "bk_tenant_id": DEFAULT_TENANT_ID if record["bk_biz_id"] == 0 else bk_tenant_id,
                    "bk_biz_id": record["bk_biz_id"],
                    "subscription_id": record["subscription_id"],
                    "bk_data_id": record["bk_data_id"],
                }
            )

    if LOG in config_types:
        for record in (
            LogSubscriptionConfig.objects.filter(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id__in=query_bk_biz_ids,
                subscription_id__gt=0,
            )
            .values("bk_tenant_id", "bk_biz_id", "log_name", "subscription_id")
            .order_by("bk_biz_id", "log_name", "subscription_id")
        ):
            subscriptions.append(
                {
                    "config_type": LOG,
                    "bk_tenant_id": record["bk_tenant_id"],
                    "bk_biz_id": record["bk_biz_id"],
                    "subscription_id": record["subscription_id"],
                    "name": record["log_name"],
                }
            )

    subscription_counts = {
        config_type: sum(1 for subscription in subscriptions if subscription["config_type"] == config_type)
        for config_type in config_types
    }
    logger.info(
        "list_proxy_config_delivery_subscriptions: completed bk_tenant_id=%s bk_biz_ids=%s "
        "subscription_count=%s subscription_counts=%s",
        bk_tenant_id,
        bk_biz_ids,
        len(subscriptions),
        subscription_counts,
    )
    return subscriptions


def _build_proxy_config_delivery_subscription_scope(details: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    subscription_scope: list[dict[str, Any]] = []

    for record in details.get(APM_APPLICATION, []):
        if record.get("result") is True:
            subscription_scope.append(
                {
                    "config_type": APM_APPLICATION,
                    "bk_tenant_id": record.get("bk_tenant_id"),
                    "bk_biz_id": record.get("bk_biz_id"),
                    "name": record.get("app_name"),
                    "subscription_id": record.get("subscription_id"),
                }
            )

    for record in details.get(CUSTOM_REPORT, []):
        if record.get("result") is not True:
            continue
        refresh_result = record.get("refresh_result") or {}
        for detail in refresh_result.get("details") or []:
            node_man_target = (detail.get("targets") or {}).get("node_man") or {}
            if node_man_target.get("action") != "refresh" or node_man_target.get("result") is not True:
                continue
            for bk_data_id in _read_ints(detail.get("data_ids") or []):
                subscription_scope.append(
                    {
                        "config_type": CUSTOM_REPORT,
                        "bk_tenant_id": detail.get("bk_tenant_id") or record.get("bk_tenant_id"),
                        "bk_biz_id": detail.get("bk_biz_id", record.get("bk_biz_id")),
                        "bk_data_id": bk_data_id,
                    }
                )

    for record in details.get(LOG, []):
        if record.get("result") is True:
            subscription_scope.append(
                {
                    "config_type": LOG,
                    "bk_tenant_id": record.get("bk_tenant_id"),
                    "bk_biz_id": record.get("bk_biz_id"),
                    "name": record.get("log_group_name"),
                    "subscription_id": record.get("subscription_id"),
                }
            )

    return _dedupe_proxy_config_delivery_subscription_scope(subscription_scope)


def _dedupe_proxy_config_delivery_subscription_scope(
    subscription_scope: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    deduped_scope = []
    seen_keys = set()
    for scope in subscription_scope:
        match_keys = _proxy_config_delivery_subscription_match_keys(scope)
        if not match_keys:
            continue
        dedupe_key = tuple(match_keys)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        deduped_scope.append(scope)
    return deduped_scope


def _filter_proxy_config_delivery_subscriptions_by_scope(
    subscriptions: list[dict[str, Any]],
    *,
    subscription_scope: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> list[dict[str, Any]]:
    if subscription_scope is None:
        return subscriptions

    scope_keys = {
        match_key for scope in subscription_scope for match_key in _proxy_config_delivery_subscription_match_keys(scope)
    }
    if not scope_keys:
        return []

    return [
        subscription
        for subscription in subscriptions
        if any(match_key in scope_keys for match_key in _proxy_config_delivery_subscription_match_keys(subscription))
    ]


def _proxy_config_delivery_subscription_match_keys(subscription: dict[str, Any]) -> list[tuple[Any, ...]]:
    config_type = subscription.get("config_type")
    bk_tenant_id = subscription.get("bk_tenant_id")
    bk_biz_id = subscription.get("bk_biz_id")
    match_keys: list[tuple[Any, ...]] = []

    subscription_id = _read_int(subscription.get("subscription_id"))
    if subscription_id > 0:
        match_keys.append((config_type, bk_tenant_id, "subscription_id", subscription_id))

    if config_type == CUSTOM_REPORT:
        bk_data_id = _read_int(subscription.get("bk_data_id"))
        if bk_data_id > 0:
            match_keys.append((config_type, bk_tenant_id, bk_biz_id, "bk_data_id", bk_data_id))
    else:
        name = subscription.get("name") or subscription.get("app_name") or subscription.get("log_name")
        if name:
            match_keys.append((config_type, bk_tenant_id, bk_biz_id, "name", str(name)))

    return match_keys


def _check_proxy_config_delivery_subscription(
    subscription: dict[str, Any], *, owned_host_ids: set[int] | None = None
) -> dict[str, Any]:
    """检查单个订阅的 Proxy 配置下发状态。

    Args:
        subscription: 订阅元信息（config_type / bk_tenant_id / bk_biz_id / subscription_id 等）。
        owned_host_ids: 本业务视角下需要关注的 Proxy 主机 host id 集合。为 ``None`` 时统计
            订阅下的全部主机；非空时，host id 不在该集合内的实例（借用的其他业务 Proxy）
            会被标记为 ``ignored`` 并从各项计数与结果判定中排除。
    """
    logger.info(
        "check bk-collector proxy config subscription: start config_type=%s bk_tenant_id=%s bk_biz_id=%s "
        "subscription_id=%s owned_host_count=%s",
        subscription.get("config_type"),
        subscription.get("bk_tenant_id"),
        subscription.get("bk_biz_id"),
        subscription.get("subscription_id"),
        len(owned_host_ids) if owned_host_ids is not None else None,
    )
    detail = {
        **subscription,
        "action": "check",
        "result": False,
        "message": "",
        "proxy_count": 0,
        "succeeded_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "unknown_count": 0,
        "ignored_count": 0,
        "instances": [],
    }
    try:
        task_results = api.node_man.batch_task_result(
            bk_tenant_id=subscription["bk_tenant_id"],
            subscription_id=subscription["subscription_id"],
            need_detail=True,
        )
    except Exception as error:  # noqa: BLE001 - migration checker should summarize query failures.
        logger.exception(
            "check bk-collector proxy config subscription: query nodeman task result failed "
            "config_type=%s bk_tenant_id=%s bk_biz_id=%s subscription_id=%s",
            subscription.get("config_type"),
            subscription.get("bk_tenant_id"),
            subscription.get("bk_biz_id"),
            subscription.get("subscription_id"),
        )
        detail.update(
            {"status": "UNKNOWN", "unknown_count": 1, "message": f"query nodeman task result failed: {error}"}
        )
        return detail

    if not task_results:
        logger.warning(
            "check bk-collector proxy config subscription: no nodeman task result found "
            "config_type=%s bk_tenant_id=%s bk_biz_id=%s subscription_id=%s",
            subscription.get("config_type"),
            subscription.get("bk_tenant_id"),
            subscription.get("bk_biz_id"),
            subscription.get("subscription_id"),
        )
        detail.update({"status": "UNKNOWN", "unknown_count": 1, "message": "no nodeman task result found"})
        return detail

    instances = [_get_proxy_config_delivery_status(task_result) for task_result in task_results]
    detail["instances"] = instances

    # 标记不属于本业务的实例（借用的其他业务 Proxy），其下发异常不纳入统计与结果判定
    ignored_count = 0
    if owned_host_ids is not None:
        for instance in instances:
            if _read_int(instance.get("bk_host_id")) not in owned_host_ids:
                instance["ignored"] = True
                ignored_count += 1

    considered_instances = [instance for instance in instances if not instance.get("ignored")]
    detail["ignored_count"] = ignored_count
    detail["proxy_count"] = len(considered_instances)
    detail["succeeded_count"] = sum(1 for instance in considered_instances if instance["result"] is True)
    detail["pending_count"] = sum(
        1 for instance in considered_instances if instance["status"] in PENDING_CONFIG_DELIVERY_STATUSES
    )
    detail["unknown_count"] = sum(1 for instance in considered_instances if instance["status"] == "UNKNOWN")
    detail["failed_count"] = sum(
        1
        for instance in considered_instances
        if instance["result"] is False
        and instance["status"] not in PENDING_CONFIG_DELIVERY_STATUSES
        and instance["status"] != "UNKNOWN"
    )
    detail["result"] = detail["failed_count"] == 0 and detail["pending_count"] == 0 and detail["unknown_count"] == 0
    detail["status"] = CONFIG_DELIVERY_SUCCESS_STATUS if detail["result"] else "FAILED"
    if not considered_instances and ignored_count:
        detail["message"] = "no proxy host belongs to this business, skipped"
    else:
        detail["message"] = "success" if detail["result"] else "not all proxy configs were rendered and pushed"
    logger.info(
        "check bk-collector proxy config subscription: completed config_type=%s bk_tenant_id=%s bk_biz_id=%s "
        "subscription_id=%s result=%s proxy_count=%s succeeded_count=%s failed_count=%s pending_count=%s "
        "unknown_count=%s ignored_count=%s",
        subscription.get("config_type"),
        subscription.get("bk_tenant_id"),
        subscription.get("bk_biz_id"),
        subscription.get("subscription_id"),
        detail["result"],
        detail["proxy_count"],
        detail["succeeded_count"],
        detail["failed_count"],
        detail["pending_count"],
        detail["unknown_count"],
        detail["ignored_count"],
    )
    return detail


def _parse_bk_host_id_from_instance_id(instance_id: Any) -> int:
    """从节点管理订阅实例 ID 中解析 bk_host_id。

    实例 ID 形如 ``"host|instance|host|30313642"``，末尾的数字段即为 bk_host_id，
    在 ``instance_info.host`` 缺失 bk_host_id 时作为兜底来源。
    """
    if not instance_id:
        return 0
    for segment in reversed(str(instance_id).split("|")):
        if segment.isdigit():
            return int(segment)
    return 0


def _get_proxy_config_delivery_status(task_result: dict[str, Any]) -> dict[str, Any]:
    render_steps = list(_iter_proxy_config_render_steps(task_result))
    host = (task_result.get("instance_info") or {}).get("host") or {}
    # host 信息缺失 bk_host_id 时，从实例 ID 末段兜底解析
    bk_host_id = _read_int(host.get("bk_host_id")) or _parse_bk_host_id_from_instance_id(task_result.get("instance_id"))
    detail = {
        "instance_id": task_result.get("instance_id"),
        "bk_host_id": bk_host_id or None,
        "bk_cloud_id": host.get("bk_cloud_id"),
        "ip": host.get("bk_host_innerip") or host.get("bk_host_innerip_v6") or host.get("inner_ip"),
        "render_steps": [
            {
                "status": step.get("status"),
                "start_time": step.get("start_time"),
                "finish_time": step.get("finish_time"),
                "pipeline_id": step.get("pipeline_id"),
            }
            for step in render_steps
        ],
    }
    if not render_steps:
        detail.update({"result": False, "status": "UNKNOWN", "message": "render_and_push_config step not found"})
        logger.warning(
            "get_proxy_config_delivery_status: render step not found instance_id=%s bk_host_id=%s bk_cloud_id=%s ip=%s",
            detail["instance_id"],
            detail["bk_host_id"],
            detail["bk_cloud_id"],
            detail["ip"],
        )
        return detail

    pending_steps = [step for step in render_steps if step.get("status") in PENDING_CONFIG_DELIVERY_STATUSES]
    if pending_steps:
        detail.update(
            {
                "result": False,
                "status": pending_steps[0].get("status") or "UNKNOWN",
                "message": "render_and_push_config is pending",
            }
        )
        logger.info(
            "get_proxy_config_delivery_status: render step pending instance_id=%s bk_host_id=%s bk_cloud_id=%s "
            "ip=%s status=%s render_step_count=%s",
            detail["instance_id"],
            detail["bk_host_id"],
            detail["bk_cloud_id"],
            detail["ip"],
            detail["status"],
            len(render_steps),
        )
        return detail

    failed_steps = [step for step in render_steps if step.get("status") != CONFIG_DELIVERY_SUCCESS_STATUS]
    if failed_steps:
        detail.update(
            {
                "result": False,
                "status": failed_steps[0].get("status") or "UNKNOWN",
                "message": "render_and_push_config failed",
            }
        )
        logger.warning(
            "get_proxy_config_delivery_status: render step failed instance_id=%s bk_host_id=%s bk_cloud_id=%s "
            "ip=%s status=%s render_step_count=%s",
            detail["instance_id"],
            detail["bk_host_id"],
            detail["bk_cloud_id"],
            detail["ip"],
            detail["status"],
            len(render_steps),
        )
        return detail

    detail.update({"result": True, "status": CONFIG_DELIVERY_SUCCESS_STATUS, "message": "success"})
    logger.info(
        "get_proxy_config_delivery_status: render step succeeded instance_id=%s bk_host_id=%s bk_cloud_id=%s "
        "ip=%s render_step_count=%s",
        detail["instance_id"],
        detail["bk_host_id"],
        detail["bk_cloud_id"],
        detail["ip"],
        len(render_steps),
    )
    return detail


def _iter_proxy_config_render_steps(task_result: dict[str, Any]):
    task_payloads = [task_result]
    last_task = task_result.get("last_task")
    if isinstance(last_task, dict):
        task_payloads.append(last_task)

    for task_payload in task_payloads:
        for step in task_payload.get("steps") or []:
            for sub_step in step.get("sub_steps") or []:
                if sub_step.get("step_code") == PROXY_CONFIG_RENDER_STEP_CODE:
                    yield sub_step
            for target_host in step.get("target_hosts") or []:
                for sub_step in target_host.get("sub_steps") or []:
                    if sub_step.get("step_code") == PROXY_CONFIG_RENDER_STEP_CODE:
                        yield sub_step


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
    host_plan_loader: Callable[..., tuple[list[int], list[dict[str, Any]]]],
    empty_operation_message: str,
    dry_run_message: str,
    job_wait_timeout: int,
    job_poll_interval: int,
    skip_hosts_without_agent: bool,
) -> dict[str, Any]:
    logger.info(
        "operate_biz_bk_collector_plugin: start category=%s job_type=%s bk_tenant_id=%s bk_biz_ids=%s "
        "operator=%s dry_run=%s plugin_version=%s job_wait_timeout=%s job_poll_interval=%s "
        "skip_hosts_without_agent=%s",
        category,
        job_type,
        bk_tenant_id,
        bk_biz_ids,
        operator,
        dry_run,
        plugin_version,
        job_wait_timeout,
        job_poll_interval,
        skip_hosts_without_agent,
    )
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
            logger.info(
                "operate_biz_bk_collector_plugin: biz started category=%s bk_tenant_id=%s bk_biz_id=%s",
                category,
                bk_tenant_id,
                bk_biz_id,
            )
            record = {
                "bk_biz_id": bk_biz_id,
                "plugin_name": PLUGIN_NAME,
                "plugin_version": plugin_version,
                "target_host_ids": [],
                operation_host_key: [],
                "skipped_host_ids": [],
                "skipped_hosts": [],
            }
            try:
                target_host_ids = _unique_ints(
                    BkCollectorConfig.get_target_host_ids_by_biz_id(
                        bk_tenant_id, bk_biz_id, only_current_bk_biz_id=True
                    )
                )
                record["target_host_ids"] = target_host_ids
                logger.info(
                    "operate_biz_bk_collector_plugin: target proxy hosts loaded category=%s bk_tenant_id=%s "
                    "bk_biz_id=%s target_host_count=%s target_host_ids=%s",
                    category,
                    bk_tenant_id,
                    bk_biz_id,
                    len(target_host_ids),
                    target_host_ids,
                )
                if not target_host_ids:
                    record.update({"action": "skip", "result": True, "message": "no proxy host found"})
                    logger.info(
                        "operate_biz_bk_collector_plugin: skip biz category=%s bk_tenant_id=%s bk_biz_id=%s "
                        "reason=no proxy host found",
                        category,
                        bk_tenant_id,
                        bk_biz_id,
                    )
                    report["details"][category].append(record)
                    continue

                operation_host_ids, skipped_hosts = host_plan_loader(
                    bk_tenant_id=bk_tenant_id,
                    bk_host_ids=target_host_ids,
                    plugin_name=PLUGIN_NAME,
                    plugin_version=plugin_version,
                    skip_hosts_without_agent=skip_hosts_without_agent,
                )
                skipped_host_ids = [skipped_host["bk_host_id"] for skipped_host in skipped_hosts]
                record[operation_host_key] = operation_host_ids
                record["skipped_hosts"] = skipped_hosts
                record["skipped_host_ids"] = skipped_host_ids
                logger.info(
                    "operate_biz_bk_collector_plugin: operation plan ready category=%s bk_tenant_id=%s "
                    "bk_biz_id=%s operation_host_count=%s skipped_host_count=%s operation_host_ids=%s "
                    "skipped_hosts=%s",
                    category,
                    bk_tenant_id,
                    bk_biz_id,
                    len(operation_host_ids),
                    len(skipped_hosts),
                    operation_host_ids,
                    skipped_hosts,
                )
                if not operation_host_ids:
                    record.update({"action": "skip", "result": True, "message": empty_operation_message})
                    logger.info(
                        "operate_biz_bk_collector_plugin: skip biz category=%s bk_tenant_id=%s bk_biz_id=%s reason=%s",
                        category,
                        bk_tenant_id,
                        bk_biz_id,
                        empty_operation_message,
                    )
                    report["details"][category].append(record)
                    continue

                if dry_run:
                    record.update({"action": "dry_run", "result": None, "message": dry_run_message})
                    logger.info(
                        "operate_biz_bk_collector_plugin: dry run planned category=%s bk_tenant_id=%s "
                        "bk_biz_id=%s operation_host_ids=%s",
                        category,
                        bk_tenant_id,
                        bk_biz_id,
                        operation_host_ids,
                    )
                    report["details"][category].append(record)
                    continue

                logger.info(
                    "operate_biz_bk_collector_plugin: submit nodeman plugin job category=%s job_type=%s "
                    "bk_tenant_id=%s bk_biz_id=%s operation_host_ids=%s plugin_version=%s",
                    category,
                    job_type,
                    bk_tenant_id,
                    bk_biz_id,
                    operation_host_ids,
                    plugin_version,
                )
                operate_result = api.node_man.plugin_operate(
                    bk_tenant_id=bk_tenant_id,
                    plugin_params=_build_plugin_params(plugin_version=plugin_version),
                    job_type=job_type,
                    bk_host_id=operation_host_ids,
                )
                logger.info(
                    "operate_biz_bk_collector_plugin: nodeman plugin job submitted category=%s job_type=%s "
                    "bk_tenant_id=%s bk_biz_id=%s operate_result=%s",
                    category,
                    job_type,
                    bk_tenant_id,
                    bk_biz_id,
                    operate_result,
                )
                job_status = _get_plugin_operate_job_status(
                    bk_tenant_id=bk_tenant_id,
                    operate_result=operate_result,
                    target_host_ids=operation_host_ids,
                    wait_timeout=job_wait_timeout,
                    poll_interval=job_poll_interval,
                )
            except Exception as error:  # noqa: BLE001 - keep processing other businesses.
                logger.exception(
                    "operate_biz_bk_collector_plugin: biz failed category=%s bk_tenant_id=%s bk_biz_id=%s",
                    category,
                    bk_tenant_id,
                    bk_biz_id,
                )
                record.update({"action": category, "result": False, "message": str(error)})
            else:
                logger.info(
                    "operate_biz_bk_collector_plugin: biz completed category=%s bk_tenant_id=%s bk_biz_id=%s "
                    "result=%s status=%s timed_out=%s poll_attempts=%s message=%s",
                    category,
                    bk_tenant_id,
                    bk_biz_id,
                    job_status["result"],
                    job_status.get("status"),
                    job_status.get("timed_out"),
                    job_status.get("poll_attempts"),
                    job_status["message"],
                )
                record.update(
                    {
                        "action": category,
                        "result": job_status["result"],
                        "message": job_status["message"],
                        "operate_result": operate_result,
                        "job_status": job_status,
                    }
                )
            report["details"][category].append(record)

    report["summary"] = _build_summary(report["details"], dry_run=dry_run)
    report["failure_summary"] = _build_plugin_operation_failure_summary(report["details"])
    report["skip_summary"] = _build_plugin_operation_skip_summary(report["details"])
    logger.info(
        "operate_biz_bk_collector_plugin: completed category=%s bk_tenant_id=%s bk_biz_ids=%s summary=%s "
        "skip_summary=%s",
        category,
        bk_tenant_id,
        bk_biz_ids,
        report["summary"],
        report["skip_summary"],
    )
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
                "skipped_hosts": [],
                "action": category,
                "result": False,
                "message": message,
            }
        )
    report["summary"] = _build_summary(report["details"], dry_run=dry_run)
    report["failure_summary"] = _build_plugin_operation_failure_summary(report["details"])
    report["skip_summary"] = _build_plugin_operation_skip_summary(report["details"])
    return report


def _build_plugin_operation_failure_summary(details: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    records = []
    abnormal_host_count = 0

    for category, category_records in details.items():
        for record in category_records:
            if record.get("action") in {"skip", "dry_run"} or record.get("result") is True:
                continue

            job_status = record.get("job_status") or {}
            abnormal_hosts = [
                _serialize_plugin_abnormal_instance(instance)
                for instance in job_status.get("instances", [])
                if instance.get("status") != PLUGIN_JOB_SUCCESS_STATUS
            ]
            abnormal_host_count += len(abnormal_hosts)

            failure_record = {
                "category": category,
                "bk_biz_id": record.get("bk_biz_id"),
                "action": record.get("action"),
                "message": record.get("message"),
                "target_host_ids": record.get("target_host_ids", []),
                "operation_host_ids": _get_plugin_operation_host_ids(record),
                "skipped_host_ids": record.get("skipped_host_ids", []),
            }
            if job_status:
                failure_record.update(
                    {
                        "job_id": job_status.get("job_id"),
                        "job_status": job_status.get("status"),
                        "timed_out": job_status.get("timed_out"),
                        "poll_attempts": job_status.get("poll_attempts"),
                    }
                )
            if abnormal_hosts:
                failure_record["hosts"] = abnormal_hosts
            records.append(failure_record)

    return {
        "record_count": len(records),
        "host_count": abnormal_host_count,
        "records": records,
    }


def _build_plugin_operation_skip_summary(details: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """汇总因 Agent 状态或插件未安装等原因被跳过的主机，方便命令层集中打印。"""
    records = []
    host_count = 0

    for category, category_records in details.items():
        for record in category_records:
            skipped_hosts = record.get("skipped_hosts") or []
            if not skipped_hosts:
                continue
            host_count += len(skipped_hosts)
            records.append(
                {
                    "category": category,
                    "bk_biz_id": record.get("bk_biz_id"),
                    "skipped_host_count": len(skipped_hosts),
                    "hosts": skipped_hosts,
                }
            )

    return {
        "record_count": len(records),
        "host_count": host_count,
        "records": records,
    }


def _get_plugin_operation_host_ids(record: dict[str, Any]) -> list[int]:
    for host_key in ["deploy_host_ids", "stop_host_ids"]:
        if host_key in record:
            return record[host_key]
    return []


def _serialize_plugin_abnormal_instance(instance: dict[str, Any]) -> dict[str, Any]:
    return {
        "instance_id": instance.get("instance_id"),
        "bk_host_id": instance.get("bk_host_id"),
        "bk_biz_id": instance.get("bk_biz_id"),
        "bk_cloud_id": instance.get("bk_cloud_id"),
        "ip": instance.get("ip"),
        "status": instance.get("status"),
        "status_display": instance.get("status_display"),
        "op_type": instance.get("op_type"),
        "step": instance.get("step"),
    }


def _get_plugin_operate_job_status(
    *,
    bk_tenant_id: str,
    operate_result: dict[str, Any] | None,
    target_host_ids: list[int],
    wait_timeout: int,
    poll_interval: int,
) -> dict[str, Any]:
    job_id = _extract_job_id(operate_result)
    job_status = {
        "job_id": job_id,
        "status": "UNKNOWN",
        "result": False,
        "message": "job_id not found in plugin_operate result",
        "statistics": {},
        "instances": [],
    }
    if not job_id:
        logger.warning(
            "get_plugin_operate_job_status: job_id not found operate_result=%s target_host_ids=%s",
            operate_result,
            target_host_ids,
        )
        return job_status

    normalized_wait_timeout = max(_read_int(wait_timeout), 0)
    normalized_poll_interval = max(_read_int(poll_interval), 0)
    deadline = time.monotonic() + normalized_wait_timeout
    poll_attempts = 0
    logger.info(
        "get_plugin_operate_job_status: start polling bk_tenant_id=%s job_id=%s target_host_ids=%s "
        "wait_timeout=%s poll_interval=%s",
        bk_tenant_id,
        job_id,
        target_host_ids,
        normalized_wait_timeout,
        normalized_poll_interval,
    )

    while True:
        poll_attempts += 1
        try:
            job_detail = api.node_man.job_detail(
                bk_tenant_id=bk_tenant_id,
                id=job_id,
                page=1,
                pagesize=max(len(target_host_ids), 100),
            )
        except Exception as error:  # noqa: BLE001 - migration command reports this in structured output.
            logger.exception(
                "get_plugin_operate_job_status: query nodeman job detail failed bk_tenant_id=%s job_id=%s "
                "poll_attempts=%s",
                bk_tenant_id,
                job_id,
                poll_attempts,
            )
            job_status.update(
                {
                    "poll_attempts": poll_attempts,
                    "timed_out": False,
                    "message": f"query nodeman job detail failed: {error}",
                }
            )
            return job_status

        job_status = _build_plugin_job_status(job_id=job_id, job_detail=job_detail)
        job_status["poll_attempts"] = poll_attempts
        job_status["timed_out"] = False
        logger.info(
            "get_plugin_operate_job_status: poll result bk_tenant_id=%s job_id=%s poll_attempts=%s "
            "status=%s result=%s statistics=%s message=%s",
            bk_tenant_id,
            job_id,
            poll_attempts,
            job_status.get("status"),
            job_status.get("result"),
            job_status.get("statistics"),
            job_status.get("message"),
        )
        if job_status["result"] is not None:
            return job_status

        remaining_seconds = deadline - time.monotonic()
        if normalized_wait_timeout <= 0 or remaining_seconds <= 0:
            job_status.update(
                {
                    "status": PLUGIN_JOB_TIMEOUT_STATUS,
                    "last_status": job_status.get("status"),
                    "result": False,
                    "timed_out": True,
                    "message": f"nodeman job wait timeout, last status: {job_status.get('status')}",
                }
            )
            logger.warning(
                "get_plugin_operate_job_status: polling timeout bk_tenant_id=%s job_id=%s poll_attempts=%s "
                "last_status=%s statistics=%s",
                bk_tenant_id,
                job_id,
                poll_attempts,
                job_status.get("last_status"),
                job_status.get("statistics"),
            )
            return job_status

        sleep_seconds = min(normalized_poll_interval or 1, remaining_seconds)
        if sleep_seconds > 0:
            logger.info(
                "get_plugin_operate_job_status: wait next poll bk_tenant_id=%s job_id=%s poll_attempts=%s "
                "sleep_seconds=%.2f",
                bk_tenant_id,
                job_id,
                poll_attempts,
                sleep_seconds,
            )
            time.sleep(sleep_seconds)


def _build_plugin_job_status(*, job_id: int, job_detail: dict[str, Any]) -> dict[str, Any]:
    instances = _serialize_plugin_job_instances(job_detail.get("list") or [])
    statistics = _normalize_plugin_job_statistics(job_detail.get("statistics") or {}, instances)
    status = str(job_detail.get("status") or "UNKNOWN")
    if status == PLUGIN_JOB_SUCCESS_STATUS and statistics["failed_count"] == 0 and statistics["pending_count"] == 0:
        result = True
        message = "success"
    elif status in PLUGIN_JOB_PENDING_STATUSES or statistics["pending_count"]:
        result = None
        message = f"nodeman job is {status}"
    else:
        result = False
        message = f"nodeman job is {status}"
    return {
        "job_id": job_id,
        "job_type": job_detail.get("job_type"),
        "status": status,
        "result": result,
        "message": message,
        "statistics": statistics,
        "start_time": job_detail.get("start_time"),
        "end_time": job_detail.get("end_time"),
        "cost_time": job_detail.get("cost_time"),
        "instances": instances,
    }


def _extract_job_id(operate_result: dict[str, Any] | None) -> int | None:
    if not isinstance(operate_result, dict):
        return None
    raw_job_id = operate_result.get("job_id")
    if raw_job_id in (None, ""):
        return None
    try:
        return int(raw_job_id)
    except (TypeError, ValueError):
        return None


def _serialize_plugin_job_instances(instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "instance_id": instance.get("instance_id"),
            "bk_host_id": instance.get("bk_host_id"),
            "bk_biz_id": instance.get("bk_biz_id"),
            "bk_cloud_id": instance.get("bk_cloud_id"),
            "ip": instance.get("inner_ip") or instance.get("ip") or instance.get("inner_ipv6"),
            "status": instance.get("status") or "UNKNOWN",
            "status_display": instance.get("status_display"),
            "op_type": instance.get("op_type"),
            "step": instance.get("step"),
            "start_time": instance.get("start_time"),
            "end_time": instance.get("end_time"),
            "cost_time": instance.get("cost_time"),
        }
        for instance in instances
    ]


def _normalize_plugin_job_statistics(statistics: dict[str, Any], instances: list[dict[str, Any]]) -> dict[str, int]:
    success_count = _read_int(statistics.get("success_count"))
    failed_count = _read_int(statistics.get("failed_count"))
    pending_count = _read_int(statistics.get("pending_count")) + _read_int(statistics.get("running_count"))
    ignored_count = _read_int(statistics.get("ignored_count"))
    if not statistics:
        success_count = sum(1 for instance in instances if instance["status"] == PLUGIN_JOB_SUCCESS_STATUS)
        failed_count = sum(
            1
            for instance in instances
            if instance["status"] not in {PLUGIN_JOB_SUCCESS_STATUS, *PLUGIN_JOB_PENDING_STATUSES}
        )
        pending_count = sum(1 for instance in instances if instance["status"] in PLUGIN_JOB_PENDING_STATUSES)
        ignored_count = 0

    return {
        "total_count": _read_int(statistics.get("total_count")) or len(instances),
        "success_count": success_count,
        "failed_count": failed_count,
        "pending_count": pending_count,
        "ignored_count": ignored_count,
    }


def _read_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _read_ints(values: list[Any] | tuple[Any, ...]) -> list[int]:
    return [int_value for value in values if (int_value := _read_int(value)) > 0]


def _refresh_apm_applications(
    report: dict[str, Any],
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    dry_run: bool,
) -> None:
    applications = _list_apm_applications(bk_tenant_id=bk_tenant_id, bk_biz_ids=bk_biz_ids)
    logger.info(
        "refresh_apm_applications: matched bk_tenant_id=%s bk_biz_ids=%s application_count=%s dry_run=%s",
        bk_tenant_id,
        bk_biz_ids,
        len(applications),
        dry_run,
    )
    for application in applications:
        logger.info(
            "refresh_apm_applications: application started bk_tenant_id=%s bk_biz_id=%s app_name=%s dry_run=%s",
            bk_tenant_id,
            application.bk_biz_id,
            application.app_name,
            dry_run,
        )
        record = {
            "bk_tenant_id": bk_tenant_id,
            "bk_biz_id": application.bk_biz_id,
            "app_name": application.app_name,
            "config_type": APM_APPLICATION,
        }
        if dry_run:
            record.update({"action": "dry_run", "result": None, "message": "would refresh apm application config"})
            logger.info(
                "refresh_apm_applications: application dry run planned bk_tenant_id=%s bk_biz_id=%s app_name=%s",
                bk_tenant_id,
                application.bk_biz_id,
                application.app_name,
            )
            report["details"][APM_APPLICATION].append(record)
            continue

        try:
            ApplicationConfig(application).refresh()
        except Exception as error:  # noqa: BLE001 - keep processing other applications.
            logger.exception(
                "refresh_apm_applications: application failed bk_tenant_id=%s bk_biz_id=%s app_name=%s",
                bk_tenant_id,
                application.bk_biz_id,
                application.app_name,
            )
            record.update({"action": "refresh", "result": False, "message": str(error)})
        else:
            logger.info(
                "refresh_apm_applications: application completed bk_tenant_id=%s bk_biz_id=%s app_name=%s",
                bk_tenant_id,
                application.bk_biz_id,
                application.app_name,
            )
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
        logger.info(
            "refresh_custom_report: biz started bk_tenant_id=%s bk_biz_id=%s dry_run=%s",
            bk_tenant_id,
            bk_biz_id,
            dry_run,
        )
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
            logger.exception(
                "refresh_custom_report: biz failed bk_tenant_id=%s bk_biz_id=%s dry_run=%s",
                bk_tenant_id,
                bk_biz_id,
                dry_run,
            )
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
                logger.info(
                    "refresh_custom_report: biz dry run planned bk_tenant_id=%s bk_biz_id=%s refresh_result=%s",
                    bk_tenant_id,
                    bk_biz_id,
                    refresh_result,
                )
            elif failed_count:
                record.update(
                    {
                        "action": "refresh",
                        "result": False,
                        "message": f"failed targets: {failed_count}",
                    }
                )
                logger.warning(
                    "refresh_custom_report: biz completed with failures bk_tenant_id=%s bk_biz_id=%s "
                    "failed_count=%s refresh_result=%s",
                    bk_tenant_id,
                    bk_biz_id,
                    failed_count,
                    refresh_result,
                )
            else:
                record.update({"action": "refresh", "result": True, "message": "success"})
                logger.info(
                    "refresh_custom_report: biz completed bk_tenant_id=%s bk_biz_id=%s refresh_result=%s",
                    bk_tenant_id,
                    bk_biz_id,
                    refresh_result,
                )
            record["refresh_result"] = refresh_result
        report["details"][CUSTOM_REPORT].append(record)


def _refresh_log(
    report: dict[str, Any],
    *,
    bk_tenant_id: str,
    bk_biz_ids: list[int],
    dry_run: bool,
) -> None:
    log_groups = _list_log_groups(bk_tenant_id=bk_tenant_id, bk_biz_ids=bk_biz_ids)
    logger.info(
        "refresh_log: matched bk_tenant_id=%s bk_biz_ids=%s log_group_count=%s dry_run=%s",
        bk_tenant_id,
        bk_biz_ids,
        len(log_groups),
        dry_run,
    )
    for log_group in log_groups:
        logger.info(
            "refresh_log: log group started bk_tenant_id=%s bk_biz_id=%s log_group_id=%s log_group_name=%s dry_run=%s",
            bk_tenant_id,
            log_group.bk_biz_id,
            log_group.log_group_id,
            log_group.log_group_name,
            dry_run,
        )
        record = {
            "bk_tenant_id": bk_tenant_id,
            "bk_biz_id": log_group.bk_biz_id,
            "log_group_id": log_group.log_group_id,
            "log_group_name": log_group.log_group_name,
            "config_type": LOG,
        }
        if dry_run:
            record.update({"action": "dry_run", "result": None, "message": "would refresh log config"})
            logger.info(
                "refresh_log: log group dry run planned bk_tenant_id=%s bk_biz_id=%s log_group_id=%s",
                bk_tenant_id,
                log_group.bk_biz_id,
                log_group.log_group_id,
            )
            report["details"][LOG].append(record)
            continue

        try:
            LogSubscriptionConfig.refresh(log_group)
        except Exception as error:  # noqa: BLE001 - keep processing other log groups.
            logger.exception(
                "refresh_log: log group failed bk_tenant_id=%s bk_biz_id=%s log_group_id=%s",
                bk_tenant_id,
                log_group.bk_biz_id,
                log_group.log_group_id,
            )
            record.update({"action": "refresh", "result": False, "message": str(error)})
        else:
            logger.info(
                "refresh_log: log group completed bk_tenant_id=%s bk_biz_id=%s log_group_id=%s",
                bk_tenant_id,
                log_group.bk_biz_id,
                log_group.log_group_id,
            )
            record.update({"action": "refresh", "result": True, "message": "success"})
        report["details"][LOG].append(record)


def _get_deploy_host_ids(
    *,
    bk_tenant_id: str,
    bk_host_ids: list[int],
    plugin_name: str,
    plugin_version: str,
    skip_hosts_without_agent: bool = False,
) -> tuple[list[int], list[dict[str, Any]]]:
    """安装场景默认全量安装；仅当 ``skip_hosts_without_agent`` 为真时才检查 Agent 状态并跳过未安装主机。"""
    if not skip_hosts_without_agent:
        return _unique_ints(bk_host_ids), []

    plugin_info_by_host_id = _get_plugin_info_by_host_id(bk_tenant_id=bk_tenant_id, bk_host_ids=bk_host_ids)
    deploy_host_ids: list[int] = []
    skipped_hosts: list[dict[str, Any]] = []

    for bk_host_id in bk_host_ids:
        plugin_info = plugin_info_by_host_id.get(bk_host_id)
        if _is_agent_not_installed((plugin_info or {}).get("status")):
            skipped_hosts.append(_build_skipped_host_record(plugin_info, bk_host_id, SKIP_REASON_AGENT_NOT_INSTALLED))
            continue
        deploy_host_ids.append(bk_host_id)

    return _unique_ints(deploy_host_ids), skipped_hosts


def _get_stop_host_ids(
    *,
    bk_tenant_id: str,
    bk_host_ids: list[int],
    plugin_name: str,
    plugin_version: str = "",
    skip_hosts_without_agent: bool = True,
) -> tuple[list[int], list[dict[str, Any]]]:
    """停止场景默认跳过 Agent 状态非 RUNNING 的主机；同时跳过未安装 bk-collector 的主机。"""
    plugin_info_by_host_id = _get_plugin_info_by_host_id(bk_tenant_id=bk_tenant_id, bk_host_ids=bk_host_ids)
    stop_host_ids: list[int] = []
    skipped_hosts: list[dict[str, Any]] = []

    for bk_host_id in bk_host_ids:
        plugin_info = plugin_info_by_host_id.get(bk_host_id)
        if skip_hosts_without_agent and not _is_agent_running((plugin_info or {}).get("status")):
            skipped_hosts.append(_build_skipped_host_record(plugin_info, bk_host_id, SKIP_REASON_AGENT_NOT_RUNNING))
        elif plugin_info and _has_plugin(plugin_info.get("plugin_status") or [], plugin_name):
            stop_host_ids.append(bk_host_id)
        else:
            skipped_hosts.append(
                _build_skipped_host_record(plugin_info, bk_host_id, SKIP_REASON_BK_COLLECTOR_NOT_INSTALLED)
            )

    return _unique_ints(stop_host_ids), skipped_hosts


def _get_plugin_info_by_host_id(*, bk_tenant_id: str, bk_host_ids: list[int]) -> dict[int, dict[str, Any]]:
    plugin_info_list = _list_plugin_info_by_host_ids(bk_tenant_id=bk_tenant_id, bk_host_ids=bk_host_ids)
    return {plugin_info["bk_host_id"]: plugin_info for plugin_info in plugin_info_list}


def _is_agent_not_installed(agent_status: str | None) -> bool:
    """Agent 状态为 NOT_INSTALLED，或节点管理未返回该主机（状态缺失/为空）时，视为 Agent 未安装。"""
    return str(agent_status or "").strip().upper() in {"", AGENT_NOT_INSTALLED_STATUS}


def _is_agent_running(agent_status: str | None) -> bool:
    """仅节点管理返回 RUNNING 时视为 Agent 可执行插件停止操作。"""
    return str(agent_status or "").strip().upper() == AGENT_RUNNING_STATUS


def _build_skipped_host_record(plugin_info: dict[str, Any] | None, bk_host_id: int, reason: str) -> dict[str, Any]:
    plugin_info = plugin_info or {}
    return {
        "bk_host_id": bk_host_id,
        "ip": plugin_info.get("inner_ip") or plugin_info.get("inner_ipv6") or plugin_info.get("ip"),
        "bk_cloud_id": plugin_info.get("bk_cloud_id"),
        "agent_status": plugin_info.get("status"),
        "reason": reason,
    }


def _list_plugin_info_by_host_ids(*, bk_tenant_id: str, bk_host_ids: list[int]) -> list[dict[str, Any]]:
    params = {"page": 1, "pagesize": len(bk_host_ids), "conditions": [], "bk_host_id": bk_host_ids}
    return api.node_man.plugin_search(bk_tenant_id=bk_tenant_id, **params).get("list", [])


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
            "pending_count": sum(
                1 for record in records if record["action"] in SUCCEEDED_ACTIONS and record["result"] is None
            ),
            "timeout_count": sum(1 for record in records if record.get("job_status", {}).get("timed_out") is True),
            "skipped_count": sum(1 for record in records if record["action"] == "skip"),
            "failed_count": sum(1 for record in records if record["result"] is False),
        }
    summary["total"] = {
        key: sum(category_summary[key] for category_summary in summary.values())
        for key in [
            "matched_count",
            "planned_count",
            "succeeded_count",
            "pending_count",
            "timeout_count",
            "skipped_count",
            "failed_count",
        ]
    }
    return summary


def _build_config_delivery_summary(details: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, int]]:
    summary = {}
    for category, records in details.items():
        summary[category] = {
            "subscription_count": len(records),
            "proxy_count": sum(record["proxy_count"] for record in records),
            "succeeded_count": sum(record["succeeded_count"] for record in records),
            "failed_count": sum(record["failed_count"] for record in records),
            "pending_count": sum(record["pending_count"] for record in records),
            "unknown_count": sum(record["unknown_count"] for record in records),
            "ignored_count": sum(record.get("ignored_count", 0) for record in records),
        }
    summary["total"] = {
        key: sum(category_summary[key] for category_summary in summary.values())
        for key in [
            "subscription_count",
            "proxy_count",
            "succeeded_count",
            "failed_count",
            "pending_count",
            "unknown_count",
            "ignored_count",
        ]
    }
    return summary


def _build_config_delivery_failure_summary(details: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    subscriptions = []
    abnormal_proxy_count = 0

    for config_type, records in details.items():
        for record in records:
            abnormal_instances = [
                _serialize_config_delivery_abnormal_instance(instance)
                for instance in record.get("instances", [])
                if instance.get("result") is not True and not instance.get("ignored")
            ]
            if record.get("result") is True and not abnormal_instances:
                continue

            abnormal_proxy_count += len(abnormal_instances)
            subscription = {
                "config_type": config_type,
                "bk_tenant_id": record.get("bk_tenant_id"),
                "bk_biz_id": record.get("bk_biz_id"),
                "subscription_id": record.get("subscription_id"),
                "status": record.get("status"),
                "message": record.get("message"),
                "proxy_count": record.get("proxy_count", 0),
                "failed_count": record.get("failed_count", 0),
                "pending_count": record.get("pending_count", 0),
                "unknown_count": record.get("unknown_count", 0),
            }
            for optional_key in ["name", "bk_data_id"]:
                if optional_key in record:
                    subscription[optional_key] = record[optional_key]
            if abnormal_instances:
                subscription["hosts"] = abnormal_instances
            subscriptions.append(subscription)

    return {
        "subscription_count": len(subscriptions),
        "proxy_count": abnormal_proxy_count,
        "subscriptions": subscriptions,
    }


def _serialize_config_delivery_abnormal_instance(instance: dict[str, Any]) -> dict[str, Any]:
    render_step_statuses = [
        step.get("status") for step in instance.get("render_steps", []) if step.get("status") is not None
    ]
    return {
        "instance_id": instance.get("instance_id"),
        "bk_host_id": instance.get("bk_host_id"),
        "bk_cloud_id": instance.get("bk_cloud_id"),
        "ip": instance.get("ip"),
        "status": instance.get("status"),
        "message": instance.get("message"),
        "render_step_statuses": render_step_statuses,
    }


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
