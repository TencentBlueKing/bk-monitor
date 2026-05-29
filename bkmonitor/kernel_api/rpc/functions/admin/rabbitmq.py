"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests
from django.conf import settings

from config.tools.rabbitmq import get_rabbitmq_settings
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    SAFETY_LEVEL_DESTRUCTIVE,
    SAFETY_LEVEL_READ,
    build_response,
    get_bk_tenant_id,
)

FUNC_RABBITMQ_OVERVIEW = "admin.rabbitmq.overview"
FUNC_RABBITMQ_PURGE_QUEUE = "admin.rabbitmq.purge_queue"

TARGET_FRONTEND = "frontend"
TARGET_BACKEND = "backend"
TARGET_LABELS = {
    TARGET_FRONTEND: "前台 RabbitMQ",
    TARGET_BACKEND: "后台 RabbitMQ",
}
TARGETS = (TARGET_FRONTEND, TARGET_BACKEND)
DEFAULT_MANAGEMENT_PORT = 15672
REQUEST_TIMEOUT_SECONDS = 10
QUEUE_LIST_COLUMNS = [
    "name",
    "vhost",
    "node",
    "state",
    "durable",
    "auto_delete",
    "exclusive",
    "consumers",
    "consumer_utilisation",
    "memory",
    "messages",
    "messages_ready",
    "messages_unacknowledged",
    "messages_details",
    "messages_ready_details",
    "messages_unacknowledged_details",
    "message_stats",
    "idle_since",
    "arguments",
]


@dataclass(frozen=True)
class RabbitMqTargetConfig:
    target: str
    label: str
    host: str
    amqp_port: int | None
    management_port: int
    vhost: str
    username: str
    password: str


def _parse_int(value: Any, field_name: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数") from error


def _parse_optional_targets(raw_targets: Any) -> list[str]:
    if raw_targets in (None, ""):
        return list(TARGETS)
    if isinstance(raw_targets, str):
        targets = [item.strip() for item in raw_targets.split(",") if item.strip()]
    elif isinstance(raw_targets, list | tuple | set):
        targets = [str(item).strip() for item in raw_targets if str(item).strip()]
    else:
        raise CustomException(message="target 必须是字符串或列表")

    unsupported_targets = sorted(set(targets) - set(TARGETS))
    if unsupported_targets:
        raise CustomException(message=f"不支持的 RabbitMQ target: {', '.join(unsupported_targets)}")
    return targets or list(TARGETS)


def _compile_queue_exclude_regex(raw_regex: Any) -> re.Pattern[str] | None:
    if raw_regex in (None, ""):
        return None
    if not isinstance(raw_regex, str):
        raise CustomException(message="queue_exclude_regex 必须是字符串")

    normalized_regex = raw_regex.strip()
    if not normalized_regex:
        return None
    try:
        return re.compile(normalized_regex)
    except re.error as error:
        raise CustomException(message=f"queue_exclude_regex 不是合法正则: {error}") from error


def _require_target(raw_target: Any) -> str:
    target = str(raw_target or "").strip()
    if target not in TARGETS:
        raise CustomException(message=f"target 为必填项，可选值: {', '.join(TARGETS)}")
    return target


def _require_queue_name(raw_queue_name: Any) -> str:
    queue_name = str(raw_queue_name or "").strip()
    if not queue_name:
        raise CustomException(message="queue_name 为必填项")
    return queue_name


def _get_management_port(target: str, amqp_port: int | None) -> int:
    env_names = (
        ["RABBITMQ_MANAGEMENT_PORT", "RABBITMQ_HTTP_PORT"]
        if target == TARGET_FRONTEND
        else ["BK_MONITOR_RABBITMQ_MANAGEMENT_PORT", "BK_MONITOR_RABBITMQ_HTTP_PORT"]
    )
    for env_name in env_names:
        env_value = os.environ.get(env_name)
        if env_value in (None, ""):
            continue
        parsed_value = _parse_int(env_value, env_name)
        if parsed_value:
            return parsed_value

    if amqp_port == 5672:
        return DEFAULT_MANAGEMENT_PORT
    return DEFAULT_MANAGEMENT_PORT


def _get_target_config(target: str) -> RabbitMqTargetConfig:
    app_code = getattr(settings, "APP_CODE", "bk_monitor")
    host, port, vhost, user, password, _ = get_rabbitmq_settings(
        app_code=app_code,
        backend=(target == TARGET_BACKEND),
    )
    normalized_vhost = vhost or "/"
    return RabbitMqTargetConfig(
        target=target,
        label=TARGET_LABELS[target],
        host=str(host or "").strip(),
        amqp_port=port,
        management_port=_get_management_port(target, port),
        vhost=str(normalized_vhost).strip() or "/",
        username=str(user or ""),
        password=str(password or ""),
    )


def _encoded_vhost(config: RabbitMqTargetConfig) -> str:
    return quote(config.vhost, safe="")


def _encoded_queue_name(queue_name: str) -> str:
    return quote(queue_name, safe="")


def _build_url(config: RabbitMqTargetConfig, path: str) -> str:
    return f"http://{config.host}:{config.management_port}{path}"


def _request_rabbitmq(
    config: RabbitMqTargetConfig,
    method: str,
    path: str,
    *,
    expected_statuses: set[int],
    parse_json: bool = True,
    params: dict[str, Any] | None = None,
) -> Any:
    if not config.host:
        raise CustomException(message=f"{config.label} 未配置 host，无法调用 RabbitMQ HTTP API")

    url = _build_url(config, path)
    try:
        response = requests.request(
            method,
            url,
            auth=(config.username, config.password),
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        raise CustomException(message=f"{config.label} RabbitMQ HTTP API 调用失败: {error}") from error

    if response.status_code not in expected_statuses:
        error_text = response.text[:500] if response.text else response.reason
        raise CustomException(
            message=(
                f"{config.label} RabbitMQ HTTP API 返回异常: "
                f"status={response.status_code}, path={path}, body={error_text}"
            )
        )

    if not parse_json:
        return None

    try:
        payload = response.json()
    except ValueError as error:
        raise CustomException(message=f"{config.label} RabbitMQ HTTP API 返回不是合法 JSON: path={path}") from error
    if isinstance(payload, dict) and payload.get("error"):
        raise CustomException(message=f"{config.label} RabbitMQ HTTP API 返回错误: {payload.get('error')}")
    return payload


def _rate(value: Any) -> float | None:
    if not isinstance(value, dict):
        return None
    raw_rate = value.get("rate")
    if raw_rate in (None, ""):
        return None
    try:
        return float(raw_rate)
    except (TypeError, ValueError):
        return None


def _int_value(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_value(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sum_numbers(values: list[int | float | None]) -> int | float | None:
    normalized_values = [value for value in values if value is not None]
    return sum(normalized_values) if normalized_values else None


def _serialize_queue(queue: dict[str, Any]) -> dict[str, Any]:
    message_stats = queue.get("message_stats") if isinstance(queue.get("message_stats"), dict) else {}
    return {
        "name": queue.get("name"),
        "vhost": queue.get("vhost"),
        "node": queue.get("node"),
        "state": queue.get("state"),
        "durable": queue.get("durable"),
        "auto_delete": queue.get("auto_delete"),
        "exclusive": queue.get("exclusive"),
        "consumers": _int_value(queue.get("consumers")),
        "consumer_utilisation": _float_value(queue.get("consumer_utilisation")),
        "memory": _int_value(queue.get("memory")),
        "messages": _int_value(queue.get("messages")),
        "messages_ready": _int_value(queue.get("messages_ready")),
        "messages_unacknowledged": _int_value(queue.get("messages_unacknowledged")),
        "messages_rate": _rate(queue.get("messages_details")),
        "messages_ready_rate": _rate(queue.get("messages_ready_details")),
        "messages_unacknowledged_rate": _rate(queue.get("messages_unacknowledged_details")),
        "publish_rate": _rate(message_stats.get("publish_details")),
        "deliver_get_rate": _rate(message_stats.get("deliver_get_details")),
        "ack_rate": _rate(message_stats.get("ack_details")),
        "idle_since": queue.get("idle_since"),
        "arguments": queue.get("arguments") if isinstance(queue.get("arguments"), dict) else {},
    }


def _build_queue_totals(queues: list[dict[str, Any]]) -> dict[str, Any]:
    state_counts: dict[str, int] = {}
    for queue in queues:
        state = str(queue.get("state") or "unknown")
        state_counts[state] = state_counts.get(state, 0) + 1

    return {
        "queue_count": len(queues),
        "messages": _sum_numbers([_int_value(queue.get("messages")) for queue in queues]),
        "messages_ready": _sum_numbers([_int_value(queue.get("messages_ready")) for queue in queues]),
        "messages_unacknowledged": _sum_numbers([_int_value(queue.get("messages_unacknowledged")) for queue in queues]),
        "consumers": _sum_numbers([_int_value(queue.get("consumers")) for queue in queues]),
        "memory": _sum_numbers([_int_value(queue.get("memory")) for queue in queues]),
        "publish_rate": _sum_numbers(
            [_rate(_get_queue_message_stats(queue).get("publish_details")) for queue in queues]
        ),
        "deliver_get_rate": _sum_numbers(
            [_rate(_get_queue_message_stats(queue).get("deliver_get_details")) for queue in queues]
        ),
        "ack_rate": _sum_numbers([_rate(_get_queue_message_stats(queue).get("ack_details")) for queue in queues]),
        "state_counts": state_counts,
    }


def _get_queue_message_stats(queue: dict[str, Any]) -> dict[str, Any]:
    message_stats = queue.get("message_stats")
    return message_stats if isinstance(message_stats, dict) else {}


def _serialize_vhost(raw_vhost: dict[str, Any] | None, config: RabbitMqTargetConfig) -> dict[str, Any]:
    raw_vhost = raw_vhost or {}
    return {
        "name": raw_vhost.get("name") or config.vhost,
        "description": raw_vhost.get("description"),
        "tracing": raw_vhost.get("tracing"),
        "cluster_state": raw_vhost.get("cluster_state"),
        "recv_oct": _int_value(raw_vhost.get("recv_oct")),
        "send_oct": _int_value(raw_vhost.get("send_oct")),
        "messages": _int_value(raw_vhost.get("messages")),
        "messages_ready": _int_value(raw_vhost.get("messages_ready")),
        "messages_unacknowledged": _int_value(raw_vhost.get("messages_unacknowledged")),
    }


def _build_vhost_fallback_info(config: RabbitMqTargetConfig, queue_totals: dict[str, Any]) -> dict[str, Any]:
    vhost_info = _serialize_vhost(None, config)
    vhost_info.update(
        {
            "messages": queue_totals.get("messages"),
            "messages_ready": queue_totals.get("messages_ready"),
            "messages_unacknowledged": queue_totals.get("messages_unacknowledged"),
        }
    )
    return vhost_info


def _build_target_error_payload(config: RabbitMqTargetConfig, error: Exception) -> dict[str, Any]:
    return {
        "target": config.target,
        "label": config.label,
        "host": config.host,
        "amqp_port": config.amqp_port,
        "management_port": config.management_port,
        "vhost": config.vhost,
        "username": config.username,
        "status": "error",
        "error": str(error),
        "excluded_queue_count": 0,
        "vhost_info": _serialize_vhost(None, config),
        "queue_totals": {
            "queue_count": 0,
            "messages": None,
            "messages_ready": None,
            "messages_unacknowledged": None,
            "consumers": None,
            "memory": None,
            "publish_rate": None,
            "deliver_get_rate": None,
            "ack_rate": None,
            "state_counts": {},
        },
        "queues": [],
    }


def _queue_matches_exclude(queue: dict[str, Any], queue_exclude_regex: re.Pattern[str] | None) -> bool:
    if queue_exclude_regex is None:
        return False
    queue_name = str(queue.get("name") or "")
    return bool(queue_exclude_regex.search(queue_name))


def _fetch_target_overview(
    config: RabbitMqTargetConfig,
    queue_exclude_regex: re.Pattern[str] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    try:
        encoded_vhost = _encoded_vhost(config)
        vhost_info: dict[str, Any] | None = None
        try:
            raw_vhost_info = _request_rabbitmq(config, "GET", f"/api/vhosts/{encoded_vhost}", expected_statuses={200})
            vhost_info = raw_vhost_info if isinstance(raw_vhost_info, dict) else None
        except Exception as error:  # pylint: disable=broad-except
            warnings.append(
                {
                    "code": "RABBITMQ_VHOST_QUERY_SKIPPED",
                    "message": f"{config.label} vhost 详情查询失败，已继续使用 queue 接口汇总",
                    "details": {"target": config.target, "vhost": config.vhost, "error": str(error)},
                }
            )
        queues = _request_rabbitmq(
            config,
            "GET",
            f"/api/queues/{encoded_vhost}",
            expected_statuses={200},
            params={"columns": ",".join(QUEUE_LIST_COLUMNS)},
        )
        if not isinstance(queues, list):
            raise CustomException(message=f"{config.label} /api/queues 返回结构不是列表")

        filtered_queues = [
            queue
            for queue in queues
            if isinstance(queue, dict) and not _queue_matches_exclude(queue, queue_exclude_regex)
        ]
        queue_items = [_serialize_queue(queue) for queue in filtered_queues]
        queue_items.sort(key=lambda item: (-(item.get("messages") or 0), str(item.get("name") or "")))
        queue_totals = _build_queue_totals(filtered_queues)

        return {
            "target": config.target,
            "label": config.label,
            "host": config.host,
            "amqp_port": config.amqp_port,
            "management_port": config.management_port,
            "vhost": config.vhost,
            "username": config.username,
            "status": "ok",
            "error": None,
            "vhost_info": (
                _serialize_vhost(vhost_info, config) if vhost_info else _build_vhost_fallback_info(config, queue_totals)
            ),
            "queue_totals": queue_totals,
            "excluded_queue_count": len(queues) - len(filtered_queues),
            "queues": queue_items,
        }, warnings
    except Exception as error:  # pylint: disable=broad-except
        warnings.append(
            {
                "code": "RABBITMQ_TARGET_QUERY_FAILED",
                "message": f"{config.label} 查询失败",
                "details": {"target": config.target, "error": str(error)},
            }
        )
        return _build_target_error_payload(config, error), warnings


def _fetch_queue_detail(config: RabbitMqTargetConfig, queue_name: str) -> dict[str, Any] | None:
    encoded_vhost = _encoded_vhost(config)
    encoded_queue_name = _encoded_queue_name(queue_name)
    payload = _request_rabbitmq(
        config,
        "GET",
        f"/api/queues/{encoded_vhost}/{encoded_queue_name}",
        expected_statuses={200},
    )
    return _serialize_queue(payload) if isinstance(payload, dict) else None


@KernelRPCRegistry.register(
    FUNC_RABBITMQ_OVERVIEW,
    summary="Admin 查询 RabbitMQ 实时概览",
    description="通过 RabbitMQ HTTP API 查询前台和后台 RabbitMQ vhost 概览及队列实时指标。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID，仅用于统一 envelope；RabbitMQ 连接配置来自环境变量",
        "targets": "可选，frontend/backend 字符串列表或逗号分隔字符串，默认同时查询两者",
        "queue_exclude_regex": "可选，按 queue name 正则匹配排除干扰队列；例如 (^celeryev|\\.pidbox$)",
    },
    example_params={
        "bk_tenant_id": "system",
        "targets": ["frontend", "backend"],
        "queue_exclude_regex": "(^celeryev|\\.pidbox$)",
    },
)
def get_rabbitmq_overview(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    target_ids = _parse_optional_targets(params.get("targets") or params.get("target"))
    queue_exclude_regex = _compile_queue_exclude_regex(params.get("queue_exclude_regex") or params.get("exclude_regex"))
    warnings: list[dict[str, Any]] = []
    targets = []

    for target_id in target_ids:
        target_payload, target_warnings = _fetch_target_overview(
            _get_target_config(target_id),
            queue_exclude_regex,
        )
        targets.append(target_payload)
        warnings.extend(target_warnings)

    return build_response(
        operation="rabbitmq.overview",
        func_name=FUNC_RABBITMQ_OVERVIEW,
        bk_tenant_id=bk_tenant_id,
        data={
            "queue_exclude_regex": queue_exclude_regex.pattern if queue_exclude_regex else None,
            "targets": targets,
        },
        warnings=warnings,
        safety_level=SAFETY_LEVEL_READ,
    )


@KernelRPCRegistry.register(
    FUNC_RABBITMQ_PURGE_QUEUE,
    summary="Admin 清理 RabbitMQ 指定队列消息",
    description=(
        "通过 RabbitMQ HTTP API 删除指定 target/vhost/queue 的 ready 消息。该操作不可逆，必须由前端显式确认后调用。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID，仅用于统一 envelope；RabbitMQ 连接配置来自环境变量",
        "target": "必填，frontend 或 backend",
        "queue_name": "必填，待清理 queue 名称",
    },
    example_params={"bk_tenant_id": "system", "target": "backend", "queue_name": "celery_service"},
)
def purge_rabbitmq_queue(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    target = _require_target(params.get("target"))
    queue_name = _require_queue_name(params.get("queue_name"))
    config = _get_target_config(target)
    encoded_vhost = _encoded_vhost(config)
    encoded_queue_name = _encoded_queue_name(queue_name)
    warnings: list[dict[str, Any]] = []

    before = _fetch_queue_detail(config, queue_name)
    _request_rabbitmq(
        config,
        "DELETE",
        f"/api/queues/{encoded_vhost}/{encoded_queue_name}/contents",
        expected_statuses={204},
        parse_json=False,
    )
    try:
        after = _fetch_queue_detail(config, queue_name)
    except Exception as error:  # pylint: disable=broad-except
        after = None
        warnings.append(
            {
                "code": "RABBITMQ_QUEUE_AFTER_PURGE_QUERY_FAILED",
                "message": "队列清理完成，但清理后状态查询失败",
                "details": {"target": target, "queue_name": queue_name, "error": str(error)},
            }
        )

    return build_response(
        operation="rabbitmq.purge_queue",
        func_name=FUNC_RABBITMQ_PURGE_QUEUE,
        bk_tenant_id=bk_tenant_id,
        data={
            "target": target,
            "label": config.label,
            "vhost": config.vhost,
            "queue_name": queue_name,
            "purged": True,
            "before": before,
            "after": after,
        },
        warnings=warnings,
        safety_level=SAFETY_LEVEL_DESTRUCTIVE,
    )
