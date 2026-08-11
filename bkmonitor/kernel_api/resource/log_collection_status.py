"""日志采集任务与订阅状态 MCP 资源。"""

from collections import Counter
from typing import Any

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from core.drf_resource import Resource, api

MAX_TASK_IDS = 100
MAX_STATUS_DETAILS = 100
DEFAULT_STATUS_DETAILS = 20
POLL_RETRY_AFTER_SECONDS = 5
TERMINAL_STATUSES = {"success", "partial_failed", "failed"}

RUNNING_STATUSES = {"PENDING", "RUNNING", "STARTING", "DEPLOYING", "PREPARING"}
SUCCESS_STATUSES = {"SUCCESS", "FINISHED"}
FAILED_STATUSES = {"FAILED", "ERROR", "TERMINATED", "STOPPED"}


def normalize_task_ids(value: Any) -> list[str]:
    """把模型/API 中可能出现的列表或逗号字符串统一为字符串列表。"""
    if value in (None, ""):
        return []
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = [value]
    return [str(item).strip() for item in values if str(item).strip()]


def normalize_raw_status(value: Any) -> str:
    raw_status = str(value or "").strip().upper()
    if raw_status in RUNNING_STATUSES:
        return "running"
    if raw_status in SUCCESS_STATUSES:
        return "success"
    if raw_status in FAILED_STATUSES:
        return "failed"
    if "PART" in raw_status and "FAIL" in raw_status:
        return "partial_failed"
    return "unknown"


def flatten_status_details(payload: Any, phase: str) -> list[dict[str, Any]]:
    """扁平化 Host 拓扑分组和容器配置分组，保留 MCP 需要的稳定字段。"""
    if not isinstance(payload, dict):
        return []

    details: list[dict[str, Any]] = []
    for content in payload.get("contents") or []:
        if not isinstance(content, dict):
            continue
        for child in content.get("child") or []:
            if not isinstance(child, dict):
                continue
            message = child.get("message") or child.get("log") or ""
            detail = {
                "phase": phase,
                "status": normalize_raw_status(child.get("status")),
                "raw_status": str(child.get("status") or ""),
                "instance_id": child.get("instance_id"),
                "task_id": child.get("task_id"),
                "container_collector_config_id": child.get("container_collector_config_id"),
                "name": child.get("instance_name") or child.get("name") or "",
                "ip": child.get("ip") or "",
                "bk_cloud_id": child.get("bk_cloud_id", child.get("cloud_id")),
                "message": str(message),
            }
            details.append(detail)
    return details


def aggregate_status(details: list[dict[str, Any]]) -> str:
    statuses = [detail["status"] for detail in details]
    if not statuses or all(status == "unknown" for status in statuses):
        return "unknown"
    if "running" in statuses:
        return "running"
    if "partial_failed" in statuses:
        return "partial_failed"

    has_failed = "failed" in statuses
    has_success = "success" in statuses
    if has_failed and has_success:
        return "partial_failed"
    if has_failed:
        return "failed"
    if has_success:
        return "success"
    return "unknown"


def combine_phase_status(task_status: str, subscription_status: str) -> str:
    """任务尚未成功时优先反映本次下发；成功后再用订阅状态确认运行结果。"""
    if task_status in {"running", "partial_failed", "failed"}:
        return task_status
    if task_status == "success":
        return subscription_status if subscription_status != "unknown" else "success"
    return subscription_status


def build_phase_result(details: list[dict[str, Any]], detail_limit: int) -> dict[str, Any]:
    counts = Counter(detail["status"] for detail in details)
    return {
        "status": aggregate_status(details),
        "counts": {
            "total": len(details),
            "running": counts["running"],
            "success": counts["success"],
            "partial_failed": counts["partial_failed"],
            "failed": counts["failed"],
            "unknown": counts["unknown"],
        },
        "details": details[:detail_limit],
        "truncated": len(details) > detail_limit,
    }


class GetLogCollectorStatusResource(Resource):
    """查询单个日志采集项的统一任务与订阅状态。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collector_config_id = serializers.IntegerField(required=True, label="采集项ID")
        task_ids = serializers.ListField(
            child=serializers.CharField(),
            required=False,
            allow_empty=False,
            max_length=MAX_TASK_IDS,
            label="Fast Create/Fast Update 返回的任务ID",
        )
        detail_limit = serializers.IntegerField(
            required=False,
            default=DEFAULT_STATUS_DETAILS,
            min_value=1,
            max_value=MAX_STATUS_DETAILS,
            label="每个阶段最多返回的实例明细数",
        )

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        collector_config_id = validated_request_data["collector_config_id"]
        detail_limit = validated_request_data["detail_limit"]

        collector = api.log_search.data_bus_collectors(collector_config_id=collector_config_id)
        if str(collector.get("bk_biz_id")) != str(bk_biz_id):
            raise PermissionDenied("Collector config does not belong to the requested business.")

        task_ids = normalize_task_ids(
            validated_request_data.get("task_ids", collector.get("task_id_list"))
        )
        task_payload = api.log_search.log_collector_task_status(
            collector_config_id=collector_config_id,
            task_id_list=",".join(task_ids),
        )
        subscription_payload = api.log_search.log_collector_subscription_status(
            collector_config_id=collector_config_id
        )

        task_details = flatten_status_details(task_payload, "task")
        subscription_details = flatten_status_details(subscription_payload, "subscription")
        task_result = build_phase_result(task_details, detail_limit)
        subscription_result = build_phase_result(subscription_details, detail_limit)
        status = combine_phase_status(task_result["status"], subscription_result["status"])

        errors = [
            detail
            for detail in task_details + subscription_details
            if detail["status"] in {"partial_failed", "failed"} and detail["message"]
        ][:detail_limit]

        return {
            "collector_config_id": collector_config_id,
            "subscription_id": collector.get("subscription_id"),
            "task_ids": task_ids,
            "environment": collector.get("environment", ""),
            "status": status,
            "is_terminal": status in TERMINAL_STATUSES,
            "retry_after_seconds": 0 if status in TERMINAL_STATUSES else POLL_RETRY_AFTER_SECONDS,
            "task": task_result,
            "subscription": subscription_result,
            "errors": errors,
        }
