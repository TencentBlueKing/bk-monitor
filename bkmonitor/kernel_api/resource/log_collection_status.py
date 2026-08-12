"""日志采集任务与订阅状态 MCP 资源。"""

import re
from collections import Counter
from typing import Any

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from core.drf_resource import Resource, api

MAX_TASK_IDS = 100
MAX_TASK_ID_LENGTH = 20
MAX_STATUS_DETAILS = 100
DEFAULT_STATUS_DETAILS = 20
POLL_RETRY_AFTER_SECONDS = 5
MAX_STATUS_MESSAGE_LENGTH = 2000
TERMINAL_STATUSES = {"success", "partial_failed", "failed", "terminated"}

RUNNING_STATUSES = {"PENDING", "RUNNING", "STARTING", "DEPLOYING", "PREPARING"}
SUCCESS_STATUSES = {"SUCCESS", "FINISHED"}
FAILED_STATUSES = {"FAILED", "ERROR"}
TERMINATED_STATUSES = {"TERMINATED", "STOPPED"}
SENSITIVE_MESSAGE_PATTERN = re.compile(
    r"(?i)(password|secret|token|authorization|api[_-]?key|access[_-]?key)"
    r"([\"']?\s*[:=]\s*[\"']?)([^,\n;}]+)"
)


def normalize_task_ids(value: Any) -> list[str]:
    """把模型/API 中可能出现的列表或逗号字符串统一为字符串列表。"""
    if value in (None, ""):
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = [value]

    normalized: list[str] = []
    seen = set()
    for item in values:
        for task_id in str(item).split(","):
            task_id = task_id.strip()
            if task_id and task_id not in seen:
                normalized.append(task_id)
                seen.add(task_id)
    return normalized


def normalize_raw_status(value: Any, phase: str) -> str:
    raw_status = str(value or "").strip().upper()
    if raw_status in RUNNING_STATUSES:
        return "running"
    if raw_status in SUCCESS_STATUSES:
        return "success"
    if raw_status in FAILED_STATUSES:
        return "failed"
    if raw_status in TERMINATED_STATUSES:
        return "terminated"
    if "PART" in raw_status and "FAIL" in raw_status:
        return "partial_failed"
    return "unknown"


def sanitize_status_message(value: Any) -> tuple[str, bool]:
    message = SENSITIVE_MESSAGE_PATTERN.sub(r"\1\2******", str(value or ""))
    if len(message) <= MAX_STATUS_MESSAGE_LENGTH:
        return message, False
    return message[:MAX_STATUS_MESSAGE_LENGTH], True


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
            message, message_truncated = sanitize_status_message(
                child.get("message") or child.get("log") or ""
            )
            detail = {
                "phase": phase,
                "status": normalize_raw_status(child.get("status"), phase),
                "raw_status": str(child.get("status") or ""),
                "instance_id": child.get("instance_id"),
                "task_id": child.get("task_id"),
                "container_collector_config_id": child.get("container_collector_config_id"),
                "name": child.get("instance_name") or child.get("name") or "",
                "ip": child.get("ip") or "",
                "bk_cloud_id": child.get("bk_cloud_id", child.get("cloud_id")),
                "message": message,
                "message_truncated": message_truncated,
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
    has_terminated = "terminated" in statuses
    has_unknown = "unknown" in statuses
    if has_unknown:
        return "unknown"
    if has_failed and (has_success or has_terminated):
        return "partial_failed"
    if has_failed:
        return "failed"
    if has_terminated and has_success:
        return "partial_failed"
    if has_terminated:
        return "terminated"
    if has_success:
        return "success"
    return "unknown"


def combine_phase_status(task_status: str, subscription_status: str) -> str:
    """任务尚未成功时优先反映本次下发；成功后再用订阅状态确认运行结果。"""
    if task_status in {"running", "partial_failed", "failed", "terminated", "unknown"}:
        return task_status
    if subscription_status in {"running", "partial_failed", "failed", "terminated"}:
        return subscription_status
    if "unknown" in {task_status, subscription_status}:
        return "unknown"
    if task_status == "success" and subscription_status == "success":
        return "success"
    return "unknown"


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
            "terminated": counts["terminated"],
            "unknown": counts["unknown"],
        },
        "details": details[:detail_limit],
        "truncated": len(details) > detail_limit,
    }


class GetLogCollectorStatusResource(Resource):
    """查询单个日志采集项的统一任务与订阅状态。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collector_config_id = serializers.IntegerField(required=True, min_value=1, label="采集项ID")
        task_ids = serializers.ListField(
            child=serializers.CharField(max_length=MAX_TASK_ID_LENGTH),
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
            label="最多返回的实例明细总数",
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
        if len(task_ids) > MAX_TASK_IDS:
            raise serializers.ValidationError(
                {"task_ids": [f"Ensure this field has no more than {MAX_TASK_IDS} elements."]}
            )
        if any(not re.fullmatch(r"[1-9]\d{0,19}", task_id) for task_id in task_ids):
            raise serializers.ValidationError({"task_ids": ["Task IDs must contain only positive integers."]})

        if task_ids:
            task_payload = api.log_search.log_collector_task_status(
                collector_config_id=collector_config_id,
                task_id_list=",".join(task_ids),
                read_only=True,
            )
        else:
            task_payload = {"task_ready": False, "contents": []}
        task_details = flatten_status_details(task_payload, "task")
        task_result = build_phase_result(task_details, detail_limit)
        should_query_subscription = not task_ids or task_result["status"] == "success"
        subscription_payload = (
            api.log_search.log_collector_subscription_status(
                collector_config_id=collector_config_id,
                include_plugin_status=False,
            )
            if should_query_subscription
            else None
        )
        subscription_details = flatten_status_details(subscription_payload, "subscription")
        remaining_detail_limit = max(detail_limit - len(task_result["details"]), 0)
        subscription_result = build_phase_result(subscription_details, remaining_detail_limit)
        status = (
            combine_phase_status(task_result["status"], subscription_result["status"])
            if task_ids
            else subscription_result["status"]
        )

        errors = [
            {
                "phase": detail["phase"],
                "instance_id": detail["instance_id"],
                "task_id": detail["task_id"],
                "container_collector_config_id": detail["container_collector_config_id"],
                "message": detail["message"],
                "message_truncated": detail["message_truncated"],
            }
            for detail in task_details + subscription_details
            if detail["status"] in {"partial_failed", "failed"} and detail["message"]
        ][:detail_limit]

        return {
            "collector_config_id": collector_config_id,
            "subscription_id": collector.get("subscription_id"),
            "task_ids": task_ids,
            "environment": str(collector.get("environment") or ""),
            "status": status,
            "is_terminal": status in TERMINAL_STATUSES,
            "retry_after_seconds": 0 if status in TERMINAL_STATUSES else POLL_RETRY_AFTER_SECONDS,
            "task": task_result,
            "subscription": subscription_result,
            "errors": errors,
        }
