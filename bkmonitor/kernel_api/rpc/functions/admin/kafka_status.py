"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any

import arrow
from django.db import close_old_connections

from core.drf_resource import resource
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response, require_bk_tenant_id

logger = logging.getLogger("kernel_api")

FUNC_DATASOURCE_KAFKA_STATUS_BATCH = "admin.datasource.kafka_status_batch"
KAFKA_STATUS_BATCH_SIZE = 20
KAFKA_STATUS_WORKERS = 4
KAFKA_FRESHNESS_THRESHOLD_SECONDS = 180
TIMESTAMP_FIELDS = ("time", "timestamp", "dtEventTimeStamp", "_time_", "utctime", "@timestamp")


def _normalize_bk_data_ids(value: Any) -> list[int]:
    if not isinstance(value, list) or not value:
        raise CustomException(message="bk_data_ids 为必填非空数组")
    if len(value) > KAFKA_STATUS_BATCH_SIZE:
        raise CustomException(message=f"bk_data_ids 最多支持 {KAFKA_STATUS_BATCH_SIZE} 个")

    result: list[int] = []
    seen: set[int] = set()
    for item in value:
        try:
            bk_data_id = int(item)
        except (TypeError, ValueError) as error:
            raise CustomException(message="bk_data_ids 必须全部为正整数") from error
        if isinstance(item, bool) or bk_data_id <= 0:
            raise CustomException(message="bk_data_ids 必须全部为正整数")
        if bk_data_id not in seen:
            seen.add(bk_data_id)
            result.append(bk_data_id)
    return result


def _parse_timestamp_value(value: Any) -> datetime | None:
    if value is None or isinstance(value, bool):
        return None

    try:
        if isinstance(value, int | float):
            numeric_value = float(value)
        elif isinstance(value, str):
            normalized_value = value.strip()
            if not normalized_value:
                return None
            try:
                numeric_value = float(normalized_value)
            except ValueError:
                parsed = arrow.get(normalized_value).datetime
                return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        else:
            return None

        if not math.isfinite(numeric_value):
            return None
        absolute_value = abs(numeric_value)
        if absolute_value >= 1e18:
            numeric_value /= 1e9
        elif absolute_value >= 1e15:
            numeric_value /= 1e6
        elif absolute_value >= 1e12:
            numeric_value /= 1e3
        return datetime.fromtimestamp(numeric_value, tz=UTC)
    except (OverflowError, OSError, TypeError, ValueError, arrow.parser.ParserError):
        return None


def _extract_payload_timestamp(payload: Any, *, depth: int = 0) -> tuple[datetime, str] | None:
    if depth > 5:
        return None

    candidates: list[tuple[datetime, str]] = []
    if isinstance(payload, list):
        for item in payload:
            candidate = _extract_payload_timestamp(item, depth=depth + 1)
            if candidate:
                candidates.append(candidate)
    elif isinstance(payload, dict):
        for field in TIMESTAMP_FIELDS:
            if field not in payload:
                continue
            timestamp = _parse_timestamp_value(payload[field])
            if timestamp:
                candidates.append((timestamp, field))
                break

        nested_data = payload.get("data")
        if isinstance(nested_data, dict | list):
            candidate = _extract_payload_timestamp(nested_data, depth=depth + 1)
            if candidate:
                candidates.append(candidate)

    return max(candidates, key=lambda item: item[0]) if candidates else None


def _summarize_payload_timestamps(payloads: list[Any], checked_at: datetime) -> dict[str, Any]:
    timestamps = [candidate for payload in payloads if (candidate := _extract_payload_timestamp(payload))]
    latest_timestamp, timestamp_field = max(timestamps, key=lambda item: item[0]) if timestamps else (None, None)
    if not payloads:
        status = "no_data"
        age_seconds = None
    elif latest_timestamp is None:
        status = "unknown_time"
        age_seconds = None
    else:
        age_seconds = round((checked_at - latest_timestamp).total_seconds())
        status = "fresh" if age_seconds <= KAFKA_FRESHNESS_THRESHOLD_SECONDS else "stale"

    return {
        "status": status,
        "has_data": bool(payloads),
        "latest_timestamp": (
            latest_timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z") if latest_timestamp else None
        ),
        "timestamp_field": timestamp_field,
        "age_seconds": age_seconds,
    }


def _error_item(bk_data_id: int, started_at: float, message: str):
    return {
        "bk_data_id": bk_data_id,
        "status": "error",
        "has_data": None,
        "latest_timestamp": None,
        "timestamp_field": None,
        "age_seconds": None,
        "route_count": 0,
        "partitions_checked": 0,
        "topics": [],
        "duration_ms": round((time.monotonic() - started_at) * 1000),
        "warnings": [],
        "error": message,
    }


def _check_datasource(
    bk_tenant_id: str,
    bk_data_id: int,
    checked_at: datetime,
) -> dict[str, Any]:
    started_at = time.monotonic()
    try:
        payloads = resource.metadata.kafka_tail(
            bk_tenant_id=bk_tenant_id,
            bk_data_id=bk_data_id,
            size=1,
            use_gse_config=True,
        )
    except Exception as error:
        logger.exception("Kafka status: metadata.kafka_tail failed, bk_data_id=%s", bk_data_id)
        return _error_item(bk_data_id, started_at, f"Kafka Tail 检查失败: {error}")

    if not isinstance(payloads, list):
        return _error_item(bk_data_id, started_at, "Kafka Tail 返回结构不是数组")

    return {
        "bk_data_id": bk_data_id,
        **_summarize_payload_timestamps(payloads, checked_at),
        "route_count": 0,
        "partitions_checked": 0,
        "topics": [],
        "duration_ms": round((time.monotonic() - started_at) * 1000),
        "warnings": [],
        "error": None,
    }


@KernelRPCRegistry.register(
    FUNC_DATASOURCE_KAFKA_STATUS_BATCH,
    summary="Admin 批量检查 DataSource Kafka 数据新鲜度",
    description="inspect：通过 resource.metadata.kafka_tail 拉取尾部消息，并从消息体提取最近业务时间。",
    params_schema={
        "bk_tenant_id": "必填，租户 ID",
        "bk_data_ids": f"必填，DataSource ID 数组，最多 {KAFKA_STATUS_BATCH_SIZE} 个",
    },
    example_params={"bk_tenant_id": "system", "bk_data_ids": [50010, 50011]},
)
def kafka_status_batch(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = require_bk_tenant_id(params)
    bk_data_ids = _normalize_bk_data_ids(params.get("bk_data_ids"))
    checked_at = datetime.now(tz=UTC)
    items_by_id: dict[int, dict[str, Any]] = {}

    def check_item(bk_data_id: int):
        close_old_connections()
        try:
            return _check_datasource(bk_tenant_id, bk_data_id, checked_at)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=min(KAFKA_STATUS_WORKERS, len(bk_data_ids))) as executor:
        futures = {executor.submit(check_item, bk_data_id): bk_data_id for bk_data_id in bk_data_ids}
        for future in as_completed(futures):
            bk_data_id = futures[future]
            try:
                items_by_id[bk_data_id] = future.result()
            except Exception as error:
                logger.exception("Kafka status: unexpected check failure, bk_data_id=%s", bk_data_id)
                items_by_id[bk_data_id] = _error_item(bk_data_id, time.monotonic(), str(error))

    items = [items_by_id[bk_data_id] for bk_data_id in bk_data_ids]
    summary = {status: 0 for status in ("fresh", "stale", "unknown_time", "no_data", "error")}
    for item in items:
        summary[item["status"]] += 1

    return build_response(
        operation="datasource.kafka_status_batch",
        func_name=FUNC_DATASOURCE_KAFKA_STATUS_BATCH,
        bk_tenant_id=bk_tenant_id,
        safety_level="inspect",
        data={
            "checked_at": checked_at.isoformat().replace("+00:00", "Z"),
            "freshness_threshold_seconds": KAFKA_FRESHNESS_THRESHOLD_SECONDS,
            "summary": summary,
            "items": items,
        },
    )
