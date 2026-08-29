"""Python Access adapter for the alarmd v2 Shadow writer."""

import copy
import logging
import math
import os
import sys
import threading
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.conf import settings

from alarm_backends.core.alarmd.config import shadow_flag, shadow_kafka_config, shadow_topics
from alarm_backends.core.alarmd.publisher import KafkaPublishReceipt, _build_kafka_producer
from alarm_backends.core.alarmd.v2_writer import (
    AccessPublishJob,
    AccessV2WriterError,
    BoundedAccessShadowPublisher,
    PlanSetTooLarge,
    build_execution_messages,
    canonical_json_v2,
    derive_canonical_digest_v2,
    derive_dimension_identity_digest_v2,
    derive_plan_set_digest_v2,
    derive_record_id_v2,
)


logger = logging.getLogger("alarmd.shadow")
TELEMETRY_STAGE = "access_v2"

QUERY_FULL = "FULL"
QUERY_PARTIAL = "PARTIAL"
QUERY_UNAVAILABLE = "UNAVAILABLE"
REASON_QUERY_PARTIAL = "QUERY_PARTIAL"
REASON_QUERY_UNAVAILABLE = "QUERY_UNAVAILABLE"
REASON_CONFIG_DRIFT = "CONFIG_DRIFT"
REASON_RECORD_IDENTITY_INVALID = "RECORD_IDENTITY_INVALID"
REASON_RECORD_INVALID = "RECORD_INVALID"
REASON_RECORD_TOO_LARGE = "RECORD_TOO_LARGE"
QUERY_REASON_NONE = "NONE"

_OPERATOR = {
    "gt": "GT",
    "gte": "GTE",
    "lt": "LT",
    "lte": "LTE",
    "eq": "EQ",
    "neq": "NEQ",
}


class AccessV2BuildError(ValueError):
    pass


class AccessV2RecordBuildError(AccessV2BuildError):
    def __init__(self, detail_reason: str, message: str):
        super().__init__(message)
        self.detail_reason = detail_reason


@dataclass(frozen=True)
class AccessPublishSource:
    """O(1) capture of stable, already-prepared Access objects.

    The formal Access branches only read these objects after the M1 submit
    point. Jobs/records and shallow reference bytes are admitted synchronously;
    canonical copying and Plan/selector construction happen in the worker.
    """

    items: Sequence
    strategy_group_key: str
    from_timestamp: int
    until_timestamp: int
    alarmd_v2_execution_id: str
    alarmd_v2_evaluation_time: int
    alarmd_v2_query_result: Mapping
    alarmd_v2_source_config_digest: str | None
    records: Sequence

    @classmethod
    def capture(cls, processor, records: Sequence) -> "AccessPublishSource":
        return cls(
            items=processor.items,
            strategy_group_key=processor.strategy_group_key,
            from_timestamp=processor.from_timestamp,
            until_timestamp=processor.until_timestamp,
            alarmd_v2_execution_id=processor.alarmd_v2_execution_id,
            alarmd_v2_evaluation_time=processor.alarmd_v2_evaluation_time,
            alarmd_v2_query_result=processor.alarmd_v2_query_result,
            alarmd_v2_source_config_digest=getattr(processor, "alarmd_v2_source_config_digest", None),
            records=records,
        )

    @property
    def retained_reference_bytes(self) -> int:
        # No record/Plan body is copied here. The records budget bounds the
        # number of retained existing objects; this byte budget accounts for
        # the job and its retained reference containers without walking them.
        return (
            sys.getsizeof(self)
            + sys.getsizeof(self.items)
            + sys.getsizeof(self.records)
            + sys.getsizeof(self.alarmd_v2_query_result)
        )


@dataclass(frozen=True)
class AccessPublishEvidence:
    planned_messages: int
    planned_records: int
    planned_bytes: int
    published_messages: int
    published_records: int
    published_bytes: int
    acked_messages: int
    acked_records: int
    acked_bytes: int
    dropped_messages: int
    dropped_records: int
    dropped_bytes: int
    ack_unknown_messages: int
    ack_unknown_records: int
    ack_unknown_bytes: int
    planner_dropped_records: int

    def __post_init__(self):
        values = (
            self.planned_messages,
            self.planned_records,
            self.planned_bytes,
            self.published_messages,
            self.published_records,
            self.published_bytes,
            self.acked_messages,
            self.acked_records,
            self.acked_bytes,
            self.dropped_messages,
            self.dropped_records,
            self.dropped_bytes,
            self.ack_unknown_messages,
            self.ack_unknown_records,
            self.ack_unknown_bytes,
            self.planner_dropped_records,
        )
        if any(value < 0 for value in values):
            raise ValueError("alarmd Access v2 publish evidence must be non-negative")
        if (
            self.planned_messages != self.acked_messages + self.dropped_messages + self.ack_unknown_messages
            or self.planned_records != self.acked_records + self.dropped_records + self.ack_unknown_records
            or self.planned_bytes != self.acked_bytes + self.dropped_bytes + self.ack_unknown_bytes
        ):
            raise ValueError("alarmd Access v2 planned publish evidence does not conserve")


class AccessV2PublishError(RuntimeError):
    def __init__(self, message: str, evidence: AccessPublishEvidence, *, reason_code: str = "OUTPUT_ACK_UNKNOWN"):
        super().__init__(message)
        self.evidence = evidence
        self.reason_code = reason_code


def _fully_dropped_evidence(record_count: int) -> AccessPublishEvidence:
    return AccessPublishEvidence(
        planned_messages=0,
        planned_records=0,
        planned_bytes=0,
        published_messages=0,
        published_records=0,
        published_bytes=0,
        acked_messages=0,
        acked_records=0,
        acked_bytes=0,
        dropped_messages=0,
        dropped_records=0,
        dropped_bytes=0,
        ack_unknown_messages=0,
        ack_unknown_records=0,
        ack_unknown_bytes=0,
        planner_dropped_records=record_count,
    )


def _record_stage(status: str, acknowledged_records: int = 0) -> None:
    try:
        from alarm_backends.core.alarmd.telemetry import record_shadow_async_job, record_shadow_published_records

        record_shadow_async_job(TELEMETRY_STAGE, status)
        if acknowledged_records:
            record_shadow_published_records(TELEMETRY_STAGE, acknowledged_records)
    except Exception:
        logger.exception(
            "[alarmd shadow] component=alarmd-python stage=access_v2 "
            "result=fail_open reason=AUDIT_DROP operation=telemetry"
        )


def _record_acknowledged_records(acknowledged_records: int) -> None:
    if not acknowledged_records:
        return
    try:
        from alarm_backends.core.alarmd.telemetry import record_shadow_published_records

        record_shadow_published_records(TELEMETRY_STAGE, acknowledged_records)
    except Exception:
        logger.exception(
            "[alarmd shadow] component=alarmd-python stage=access_v2 "
            "result=fail_open reason=AUDIT_DROP operation=telemetry"
        )


def _record_access_exclusion(reason: str, count: int) -> None:
    if count <= 0:
        return
    try:
        from alarm_backends.core.alarmd.telemetry import record_shadow_access_record_exclusion

        record_shadow_access_record_exclusion(reason, count)
    except Exception:
        logger.exception(
            "[alarmd shadow] component=alarmd-python stage=access_v2 "
            "result=fail_open reason=AUDIT_DROP operation=record_exclusion"
        )


def _record_access_funnel(
    source_records: int,
    evidence: AccessPublishEvidence | None = None,
) -> None:
    try:
        from alarm_backends.core.alarmd.telemetry import record_shadow_access_funnel

        record_shadow_access_funnel(
            source_records=source_records,
            planned_records=evidence.planned_records if evidence else 0,
            planned_messages=evidence.planned_messages if evidence else 0,
            planned_bytes=evidence.planned_bytes if evidence else 0,
            acked_records=evidence.acked_records if evidence else 0,
            acked_messages=evidence.acked_messages if evidence else 0,
            acked_bytes=evidence.acked_bytes if evidence else 0,
            dropped_records=evidence.dropped_records if evidence else 0,
            dropped_messages=evidence.dropped_messages if evidence else 0,
            dropped_bytes=evidence.dropped_bytes if evidence else 0,
            ack_unknown_records=evidence.ack_unknown_records if evidence else 0,
            ack_unknown_messages=evidence.ack_unknown_messages if evidence else 0,
            ack_unknown_bytes=evidence.ack_unknown_bytes if evidence else 0,
        )
    except Exception:
        logger.exception(
            "[alarmd shadow] component=alarmd-python stage=access_v2 "
            "result=fail_open reason=AUDIT_DROP operation=access_funnel"
        )


def _query_outcome(jobs: Sequence[AccessPublishJob]) -> tuple[str, str]:
    query_result = jobs[0].snapshot["query_result"]
    completeness = str(query_result.get("completeness") or QUERY_UNAVAILABLE)
    if query_result.get("reason_code") == REASON_CONFIG_DRIFT:
        return completeness, REASON_CONFIG_DRIFT
    if completeness == QUERY_UNAVAILABLE:
        return completeness, REASON_QUERY_UNAVAILABLE
    if completeness == QUERY_PARTIAL:
        return completeness, REASON_QUERY_PARTIAL
    return completeness, QUERY_REASON_NONE


def _canonical_decimal(value) -> str:
    if isinstance(value, bool):
        raise AccessV2BuildError("boolean threshold is invalid")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise AccessV2BuildError("threshold must be decimal") from error
    if not number.is_finite():
        raise AccessV2BuildError("threshold must be finite")
    rendered = format(number, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"-0", ""} else rendered


def _threshold_groups(config) -> list[dict]:
    if not isinstance(config, list):
        raise AccessV2BuildError("Threshold config must be an array")
    groups = config if not config or isinstance(config[0], list) else [config]
    result = []
    for group in groups:
        if not isinstance(group, list):
            raise AccessV2BuildError("Threshold group must be an array")
        conditions = []
        for condition in group:
            if not isinstance(condition, Mapping):
                raise AccessV2BuildError("Threshold condition must be an object")
            operator = _OPERATOR.get(str(condition.get("method", "")).lower())
            if operator is None:
                raise AccessV2BuildError("unsupported Threshold operator")
            conditions.append(
                {
                    "operator": operator,
                    "threshold_decimal": _canonical_decimal(condition.get("threshold")),
                }
            )
        result.append({"conditions": conditions})
    return result


def _fallback_identity_fields(item) -> list[str]:
    dimensions = getattr(getattr(item, "query", None), "dimensions", None)
    if dimensions is None:
        query_configs = getattr(item, "query_configs", None) or []
        dimensions = query_configs[0].get("agg_dimension", []) if query_configs else []
    return sorted(set(dimensions or []))


def _record_identity_schema(record) -> tuple[str, ...]:
    fields = record.clean_dimension_fields()
    if not isinstance(fields, Sequence) or isinstance(fields, (str, bytes)):
        raise AccessV2BuildError("record identity fields must be an array")
    if any(not isinstance(field, str) or not field for field in fields):
        raise AccessV2BuildError("record identity fields must be non-empty strings")
    if len(set(fields)) != len(fields):
        raise AccessV2BuildError("record identity fields must be unique")
    return tuple(sorted(fields))


def _projection(item, identity_fields: list[str]) -> dict:
    return {
        "value_fields": ["value"],
        "dimension_fields": identity_fields,
        "business_identity_field": "bk_biz_id",
        "multi_value_alignment": "SINGLE_VALUE",
        "data_unit": getattr(item, "unit", "") or "",
        "missing_value_policy": "REQUIRED_VALUE",
    }


def _build_algorithm(algorithm: Mapping, item) -> dict:
    algorithm_type = str(algorithm.get("type") or "")
    if algorithm_type != "Threshold":
        return {
            "type": algorithm_type,
            "version": 1,
            "config": copy.deepcopy(algorithm.get("config") if isinstance(algorithm.get("config"), Mapping) else {}),
        }
    try:
        groups = _threshold_groups(algorithm.get("config"))
    except AccessV2BuildError:
        # Keep the Plan present and let M3 terminalize this Level. Dropping the
        # whole Query Group here would hide valid sibling Plans.
        groups = []
    return {
        "type": "Threshold",
        "version": 1,
        "config": {
            "value_field": "value",
            "data_unit": getattr(item, "unit", "") or "",
            "threshold_unit_prefix": algorithm.get("unit_prefix") or "",
            "precision": {"decimal_places": int(settings.POINT_PRECISION), "rounding": "HALF_EVEN"},
            "groups": groups,
        },
    }


def _is_always_active_uptime(uptime) -> bool:
    if not isinstance(uptime, Mapping):
        return False
    if uptime.get("calendars") or uptime.get("active_calendars"):
        return False
    time_ranges = uptime.get("time_ranges")
    return time_ranges in (
        [],
        [{"start": "00:00", "end": "23:59"}],
        [{"start": "00:00:00", "end": "23:59:59"}],
    )


def _build_plan(item, identity_fields: list[str], query_window: int) -> dict:
    strategy = item.strategy
    strategy_id = str(strategy.id)
    revision = str(
        strategy.config.get("update_time") or derive_canonical_digest_v2("python-strategy-revision-v1", strategy.config)
    )
    strategy_ref = {
        "tenant_id": strategy.bk_tenant_id,
        "strategy_id": strategy_id,
        "revision": revision,
    }
    projection = _projection(item, identity_fields)
    interval = min((int(config.get("agg_interval") or 60) for config in item.query_configs), default=60)
    detects = {int(detect["level"]): detect for detect in strategy.config.get("detects") or []}
    algorithms_by_level = defaultdict(list)
    for algorithm in item.algorithms:
        algorithms_by_level[int(algorithm["level"])].append(algorithm)
    levels = []
    for level_id in sorted(algorithms_by_level):
        detect = detects.get(level_id, {})
        priority = detect.get("priority")
        if priority is None:
            # Only the existing 1/2/3 compatibility domain has an implicit
            # source mapping. Unknown Levels remain in the Plan with priority
            # zero and are terminalized instead of being silently dropped.
            priority = level_id if level_id in {1, 2, 3} else 0
        trigger = detect.get("trigger_config") or {}
        recovery = detect.get("recovery_config") or {}
        trigger_config = {
            "required_anomalies": int(trigger.get("count") or 0),
            "step_seconds": interval,
            "window_size": int(trigger.get("check_window") or 0),
        }
        uptime = trigger.get("uptime")
        if uptime and not _is_always_active_uptime(uptime):
            trigger_config["uptime"] = copy.deepcopy(uptime)
            # Keep the Python hot path free of an additional BusinessManager
            # lookup. The Go EffectiveTimeProvider resolves this stable ref
            # with the envelope tenant/business identity at evaluation time.
            trigger_config["timezone_ref"] = "BUSINESS_LOCAL"
        levels.append(
            {
                "definition": {"level_id": level_id, "priority": int(priority)},
                "connector": "OR" if str(detect.get("connector") or "and").lower() == "or" else "AND",
                "detect_plan": {
                    "algorithms": [_build_algorithm(algorithm, item) for algorithm in algorithms_by_level[level_id]]
                },
                "trigger_plan": {"type": "N_OF_M", "version": 1, "config": trigger_config},
                "recovery_plan": {
                    "type": "CONTINUOUS_TRIGGER_MISS",
                    "version": 1,
                    "config": {
                        "consecutive_windows": int(recovery.get("check_window") or 0),
                        "enabled": bool(recovery),
                    },
                },
            }
        )
    strategy_ir = {
        "schema": {"name": "alarmd-strategy-ir", "major": 2, "minor": 0},
        "required_features": [],
        "strategy_ref": strategy_ref,
        "execution_semantics": {
            "evaluation_scope": "SERIES",
            "query_window": max(interval, int(query_window)),
            "aggregation_interval": interval,
            "evaluation_interval": interval,
            "lateness_tolerance": interval * 2,
        },
        "input_projection": projection,
        "levels": levels,
    }
    return {
        "plan_id": strategy_id,
        "strategy_ref": strategy_ref,
        "input_projection": projection,
        "source_compatibility": {"item_id": str(item.id)},
        "strategy_ir": strategy_ir,
    }


def _build_terminal_plan(item, reason_code: str) -> dict:
    strategy = item.strategy
    strategy_id = str(strategy.id)
    strategy_config = strategy.config if isinstance(strategy.config, Mapping) else {}
    revision = str(strategy_config.get("update_time") or "invalid")
    strategy_ref = {
        "tenant_id": str(strategy.bk_tenant_id),
        "strategy_id": strategy_id,
        "revision": revision,
    }
    return {
        "plan_id": strategy_id,
        "strategy_ref": strategy_ref,
        "terminal_reason_code": reason_code,
    }


def _build_plan_set(
    items: Sequence, identity_fields: list[str], query_window: int
) -> tuple[dict, list[tuple[int, ...]], list[str]]:
    grouped_items = defaultdict(list)
    for item in sorted(items, key=lambda value: (int(value.strategy.id), int(value.id))):
        grouped_items[int(item.strategy.id)].append(item)
    plans = []
    selection_item_ids = []
    terminal_reasons = []
    for strategy_id in sorted(grouped_items):
        source_items = grouped_items[strategy_id]
        source_item = source_items[0]
        if len(source_items) > 1:
            reason = "MULTIPLE_EVALUATION_UNITS_UNSUPPORTED"
            plans.append(_build_terminal_plan(source_item, reason))
            selection_item_ids.append(tuple(int(item.id) for item in source_items))
            terminal_reasons.append(reason)
            continue
        try:
            plans.append(_build_plan(source_item, identity_fields, query_window))
        except Exception:
            reason = "PLAN_INVALID"
            plans.append(_build_terminal_plan(source_item, reason))
            selection_item_ids.append((int(source_item.id),))
            terminal_reasons.append(reason)
            continue
        selection_item_ids.append((int(source_item.id),))
    plan_set = {"plan_set_digest": "", "plan_count": len(plans), "evaluation_plans": plans}
    plan_set["plan_set_digest"] = derive_plan_set_digest_v2(plan_set)
    return plan_set, selection_item_ids, terminal_reasons


def _query_revision(processor, first_item) -> str:
    return derive_canonical_digest_v2(
        "query-revision-v1",
        {
            "query_group_key": processor.strategy_group_key,
            "expression": first_item.expression,
            "functions": first_item.functions,
            "query_configs": first_item.query_configs,
            "time_delay": first_item.time_delay,
        },
    )


def access_source_config_digest(processor) -> str:
    """Digest the exact strategy/item revisions used for selector semantics."""

    sources = [
        {
            "strategy_id": str(item.strategy.id),
            "item_id": str(item.id),
            "strategy": item.strategy.config,
        }
        for item in sorted(processor.items, key=lambda value: (int(value.strategy.id), int(value.id)))
    ]
    return derive_canonical_digest_v2("access-selector-source-v1", sources)


def export_access_batch_context(processor) -> dict | None:
    if not getattr(processor, "alarmd_v2_execution_id", None):
        return None
    return {
        "execution_id": processor.alarmd_v2_execution_id,
        "evaluation_time": int(processor.alarmd_v2_evaluation_time),
        "query_result": copy.deepcopy(processor.alarmd_v2_query_result),
        "from_timestamp": int(processor.from_timestamp),
        "until_timestamp": int(processor.until_timestamp),
        "source_config_digest": access_source_config_digest(processor),
    }


def apply_access_batch_context(processor, context: Mapping | None) -> None:
    if not context:
        return
    processor.alarmd_v2_execution_id = context.get("execution_id")
    processor.alarmd_v2_evaluation_time = context.get("evaluation_time")
    processor.alarmd_v2_query_result = copy.deepcopy(context.get("query_result"))
    processor.from_timestamp = context.get("from_timestamp")
    processor.until_timestamp = context.get("until_timestamp")
    processor.alarmd_v2_source_config_digest = context.get("source_config_digest")


def _is_canonical_json_scalar(value) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _record_snapshot(
    record, *, tenant_id: str, business_id: str, identity_fields: list[str], received_time: int
) -> dict:
    if list(_record_identity_schema(record)) != identity_fields:
        raise AccessV2RecordBuildError(
            "IDENTITY_SCHEMA_CONFLICT", "record identity schema conflicts with Dataset Contract"
        )
    source_dimensions = dict(record.data.get("dimensions") or {})
    dimensions = {}
    fields = []
    for name in identity_fields:
        value = source_dimensions.get(name)
        if not _is_canonical_json_scalar(value):
            raise AccessV2RecordBuildError("IDENTITY_DIMENSION_INVALID", f"identity dimension {name} is invalid")
        dimensions[name] = value
        fields.append({"name": name, "value": value})
    # Python Access enriches records with Alert/CMDB-only structures such as
    # bk_topo_node. Evaluation v2 keeps scalar supplemental labels and leaves
    # nested enrichment to Alert.Builder instead of dropping the whole record.
    for name, value in source_dimensions.items():
        if name not in dimensions and _is_canonical_json_scalar(value):
            dimensions[name] = value
    try:
        source_time = int(record.data["time"])
    except (KeyError, TypeError, ValueError) as error:
        raise AccessV2RecordBuildError("RECORD_TIME_INVALID", "record time is invalid") from error
    try:
        digest = derive_dimension_identity_digest_v2(tenant_id, business_id, fields)
    except (TypeError, ValueError, UnicodeError) as error:
        raise AccessV2RecordBuildError("IDENTITY_DIMENSION_INVALID", "identity dimension is invalid") from error
    value = record.data.get("value")
    if not _is_canonical_json_scalar(value):
        raise AccessV2RecordBuildError("RECORD_VALUE_INVALID", "record value must be a canonical JSON scalar")
    try:
        canonical_json_v2({"dimensions": dimensions, "value": value})
    except (TypeError, ValueError, UnicodeError) as error:
        raise AccessV2RecordBuildError(
            "RECORD_CANONICALIZATION_INVALID", "record dimensions and value must be canonical JSON scalars"
        ) from error
    return {
        "record_id": derive_record_id_v2(digest, source_time),
        "source_time": source_time,
        "business_id": business_id,
        "dimension_identity": {"fields": fields, "digest": digest},
        "values": {"value": value},
        "dimensions": dimensions,
        "received_time": received_time,
    }


def build_access_publish_jobs(
    processor, records: Sequence, *, received_time: int | None = None
) -> tuple[AccessPublishJob, ...]:
    """Build self-contained Dataset jobs for contiguous exact-schema runs.

    All jobs retain the source QueryExecution identity and full Plan
    membership. Each Plan projection is compiled against its Dataset schema,
    so its Plan Set digest is intentionally Dataset-specific. Contiguous runs
    preserve source order when schemas are interleaved.
    """
    received_time = int(time.time()) if received_time is None else int(received_time)
    effective_records = records
    query_result = getattr(processor, "alarmd_v2_query_result", None) or {}
    first_item = processor.items[0] if processor.items else None
    parent_source_digest = getattr(processor, "alarmd_v2_source_config_digest", None)
    config_drift = bool(parent_source_digest and parent_source_digest != access_source_config_digest(processor))
    if query_result.get("completeness") == QUERY_UNAVAILABLE or config_drift:
        effective_records = []
        _record_access_exclusion(REASON_CONFIG_DRIFT if config_drift else REASON_QUERY_UNAVAILABLE, len(records))

    dataset_groups: list[tuple[tuple[str, ...], list]] = []
    invalid_record_count = 0
    first_invalid_ordinal = None
    for ordinal, record in enumerate(effective_records):
        try:
            identity_fields = _record_identity_schema(record)
        except Exception:
            invalid_record_count += 1
            if first_invalid_ordinal is None:
                first_invalid_ordinal = ordinal
            continue
        if not dataset_groups or dataset_groups[-1][0] != identity_fields:
            dataset_groups.append((identity_fields, []))
        dataset_groups[-1][1].append(record)
    if not dataset_groups:
        dataset_groups.append((tuple(_fallback_identity_fields(first_item)), []))

    identity_schema_count = len({identity_fields for identity_fields, _records in dataset_groups})

    if invalid_record_count:
        _record_stage("dropped")
        _record_access_exclusion(REASON_RECORD_IDENTITY_INVALID, invalid_record_count)
        logger.warning(
            "[alarmd shadow] component=alarmd-python stage=access_v2 result=coverage_gap "
            "reason=RECORD_IDENTITY_INVALID execution_id=%s query_group_key=%s "
            "identity_schemas=%s records=%s first_record_ordinal=%s",
            processor.alarmd_v2_execution_id,
            processor.strategy_group_key,
            identity_schema_count,
            invalid_record_count,
            first_invalid_ordinal,
        )

    if len(dataset_groups) > 1:
        logger.info(
            "[alarmd shadow] component=alarmd-python stage=access_v2 result=split "
            "execution_id=%s query_group_key=%s datasets=%s identity_schemas=%s records=%s",
            processor.alarmd_v2_execution_id,
            processor.strategy_group_key,
            len(dataset_groups),
            identity_schema_count,
            sum(len(group) for _identity_fields, group in dataset_groups),
        )

    return tuple(
        _build_access_publish_job(
            processor,
            group,
            received_time=received_time,
            identity_fields=list(identity_fields),
        )
        for identity_fields, group in dataset_groups
    )


def _build_access_publish_job(
    processor,
    records: Sequence,
    *,
    received_time: int,
    identity_fields: list[str],
) -> AccessPublishJob:
    if not processor.items:
        raise AccessV2BuildError("Query Group has no item")
    query_result = copy.deepcopy(getattr(processor, "alarmd_v2_query_result", None))
    if not query_result:
        raise AccessV2BuildError("Query Group has no executed query result")
    if query_result.get("completeness") == QUERY_UNAVAILABLE:
        records = []
    first_item = processor.items[0]
    parent_source_digest = getattr(processor, "alarmd_v2_source_config_digest", None)
    if parent_source_digest and parent_source_digest != access_source_config_digest(processor):
        query_result = {"completeness": QUERY_UNAVAILABLE, "reason_code": "CONFIG_DRIFT"}
        records = []
    tenant_id = first_item.strategy.bk_tenant_id
    business_id = str(first_item.strategy.bk_biz_id)
    if any(
        item.strategy.bk_tenant_id != tenant_id or str(item.strategy.bk_biz_id) != business_id
        for item in processor.items
    ):
        raise AccessV2BuildError("one Query Group must contain one tenant and business")
    query_window = max(0, int(processor.until_timestamp) - int(processor.from_timestamp))
    plan_set, selection_item_ids, terminal_reasons = _build_plan_set(processor.items, identity_fields, query_window)
    if terminal_reasons:
        _record_stage("dropped")
        logger.warning(
            "[alarmd shadow] component=alarmd-python stage=access_v2 result=coverage_gap "
            "reason=%s execution_id=%s query_group_key=%s plans=%s",
            terminal_reasons[0],
            processor.alarmd_v2_execution_id,
            processor.strategy_group_key,
            len(terminal_reasons),
        )
    valid_records = []
    record_snapshots = []
    invalid_record_count = 0
    first_invalid_ordinal = None
    invalid_detail_reasons = defaultdict(int)
    for ordinal, record in enumerate(records):
        try:
            snapshot = _record_snapshot(
                record,
                tenant_id=tenant_id,
                business_id=business_id,
                identity_fields=identity_fields,
                received_time=received_time,
            )
        except AccessV2RecordBuildError as error:
            invalid_record_count += 1
            invalid_detail_reasons[error.detail_reason] += 1
            if first_invalid_ordinal is None:
                first_invalid_ordinal = ordinal
            continue
        except (AccessV2BuildError, KeyError, TypeError, ValueError):
            invalid_record_count += 1
            invalid_detail_reasons["RECORD_BUILD_INVALID"] += 1
            if first_invalid_ordinal is None:
                first_invalid_ordinal = ordinal
            continue
        valid_records.append(record)
        record_snapshots.append(snapshot)
    if invalid_record_count:
        _record_stage("dropped")
        _record_access_exclusion(REASON_RECORD_INVALID, invalid_record_count)
        logger.warning(
            "[alarmd shadow] component=alarmd-python stage=access_v2 result=coverage_gap "
            "reason=RECORD_INVALID execution_id=%s query_group_key=%s "
            "records=%s first_record_ordinal=%s detail_reasons=%s",
            processor.alarmd_v2_execution_id,
            processor.strategy_group_key,
            invalid_record_count,
            first_invalid_ordinal,
            ",".join(f"{reason}:{invalid_detail_reasons[reason]}" for reason in sorted(invalid_detail_reasons)),
        )
    selections = [
        [
            any(record.is_retains[item_id] and not record.inhibitions[item_id] for item_id in source_item_ids)
            for record in valid_records
        ]
        for source_item_ids in selection_item_ids
    ]
    schema_input = {
        "identity_fields": identity_fields,
        "value_fields": ["value"],
        "source_time_field": "time",
        "received_time_field": "received_time",
    }
    dataset_contract = {
        "schema_digest": derive_canonical_digest_v2("dataset-schema-v1", schema_input),
        "normalization_digest": derive_canonical_digest_v2(
            "dataset-normalization-v1",
            {"point_precision": int(settings.POINT_PRECISION), "producer": "python-access-clean-v1"},
        ),
        "identity_fields": identity_fields,
        "source_time_field": "time",
        "received_time_field": "received_time",
    }
    return AccessPublishJob.create(
        execution_id=processor.alarmd_v2_execution_id,
        tenant_id=tenant_id,
        query_group={
            "key": processor.strategy_group_key,
            "query_md5": processor.strategy_group_key,
            "query_revision": _query_revision(processor, first_item),
            "evaluation_time": int(processor.alarmd_v2_evaluation_time),
        },
        source_window={"from_time": int(processor.from_timestamp), "until_time": int(processor.until_timestamp)},
        query_result=query_result,
        dataset_contract=dataset_contract,
        plan_set=plan_set,
        records=record_snapshots,
        selections=selections,
    )


class KafkaExecutionEnvelopePublisher:
    def __init__(self, config: Mapping, allowed_topics: Sequence[str], producer_factory=None):
        producer_config = dict(config)
        topic = producer_config.pop("topic", None)
        if not topic or topic not in set(allowed_topics):
            raise ValueError("alarmd v2 topic is not in the Shadow allowlist")
        timeout_ms = int(producer_config.get("message.timeout.ms", 3000))
        producer_config.setdefault("message.timeout.ms", timeout_ms)
        producer_config["enable.idempotence"] = False
        producer_config["acks"] = "all"
        self.flush_timeout = float(producer_config.pop("alarm.engine.flush.timeout.seconds", timeout_ms / 1000 + 1))
        self.max_records = int(producer_config.pop("alarm.engine.max.records.per.message", 0))
        self.max_envelope_bytes = int(producer_config.pop("alarm.engine.max.envelope.bytes", 0))
        if self.max_records <= 0 or self.max_envelope_bytes <= 0:
            raise ValueError("alarmd v2 record and envelope budgets must be configured")
        self.topic = topic
        self.producer = _build_kafka_producer(
            producer_config,
            producer_factory=producer_factory,
            producer_scope="access-v2",
        )

    def publish(self, jobs: Sequence[AccessPublishJob]) -> AccessPublishEvidence:
        jobs = tuple(jobs)
        if not jobs:
            raise AccessV2PublishError(
                "alarmd v2 publish requires at least one Dataset",
                _fully_dropped_evidence(0),
                reason_code="PLAN_INVALID",
            )
        messages = []
        drops = []
        first_drop_dataset = None
        total_records = sum(job.record_count for job in jobs)
        for dataset_ordinal, job in enumerate(jobs):
            try:
                job_messages, job_drops = build_execution_messages(
                    job,
                    max_records=self.max_records,
                    max_envelope_bytes=self.max_envelope_bytes,
                )
            except PlanSetTooLarge as error:
                raise AccessV2PublishError(
                    "alarmd v2 complete Plan Set exceeds one message",
                    _fully_dropped_evidence(total_records),
                    reason_code="MESSAGE_BUDGET_EXCEEDED",
                ) from error
            except AccessV2WriterError as error:
                raise AccessV2PublishError(
                    "alarmd v2 message planning failed",
                    _fully_dropped_evidence(total_records),
                    reason_code="PLAN_INVALID",
                ) from error
            messages.extend(job_messages)
            if job_drops and first_drop_dataset is None:
                first_drop_dataset = dataset_ordinal
            drops.extend(job_drops)
        if drops:
            _record_stage("dropped")
            oversized_record_count = sum(drop.reason_code == REASON_RECORD_TOO_LARGE for drop in drops)
            _record_access_exclusion(REASON_RECORD_TOO_LARGE, oversized_record_count)
            logger.warning(
                "[alarmd shadow] component=alarmd-python stage=access_v2 result=coverage_gap "
                "reason=%s records=%s first_dataset_ordinal=%s first_record_ordinal=%s",
                drops[0].reason_code,
                len(drops),
                first_drop_dataset,
                drops[0].record_ordinal,
            )
        receipt = KafkaPublishReceipt()
        lock = threading.Lock()
        message_states = [{"message": message, "status": "planned"} for message in messages]
        finalized = False
        published_messages = 0
        published_records = 0
        published_bytes = 0

        def evidence() -> AccessPublishEvidence:
            nonlocal finalized
            with lock:
                if not finalized:
                    for state in message_states:
                        if state["status"] == "pending":
                            state["status"] = "ack_unknown"
                        elif state["status"] == "planned":
                            state["status"] = "dropped"
                    finalized = True

                def terminal_totals(status):
                    terminal_messages = [state["message"] for state in message_states if state["status"] == status]
                    return (
                        len(terminal_messages),
                        sum(message.record_count for message in terminal_messages),
                        sum(len(message.payload) for message in terminal_messages),
                    )

                acked_messages, acked_records, acked_bytes = terminal_totals("acked")
                dropped_messages, dropped_records, dropped_bytes = terminal_totals("dropped")
                ack_unknown_messages, ack_unknown_records, ack_unknown_bytes = terminal_totals("ack_unknown")
                return AccessPublishEvidence(
                    planned_messages=len(messages),
                    planned_records=sum(message.record_count for message in messages),
                    planned_bytes=sum(len(message.payload) for message in messages),
                    published_messages=published_messages,
                    published_records=published_records,
                    published_bytes=published_bytes,
                    acked_messages=acked_messages,
                    acked_records=acked_records,
                    acked_bytes=acked_bytes,
                    dropped_messages=dropped_messages,
                    dropped_records=dropped_records,
                    dropped_bytes=dropped_bytes,
                    ack_unknown_messages=ack_unknown_messages,
                    ack_unknown_records=ack_unknown_records,
                    ack_unknown_bytes=ack_unknown_bytes,
                    planner_dropped_records=len(drops),
                )

        def delivery_callback(state, downstream):
            delivered = False

            def on_delivery(error, broker_message):
                nonlocal delivered
                with lock:
                    if delivered:
                        return
                    delivered = True
                    if not finalized:
                        state["status"] = "acked" if error is None else "dropped"
                downstream(error, broker_message)

            return on_delivery

        for state in message_states:
            message = state["message"]
            callback, cancel = receipt.reserve(message.record_count)
            try:
                self.producer.produce(
                    topic=self.topic,
                    key=message.key,
                    value=message.payload,
                    on_delivery=delivery_callback(state, callback),
                )
                with lock:
                    if state["status"] == "planned":
                        state["status"] = "pending"
                    published_messages += 1
                    published_records += message.record_count
                    published_bytes += len(message.payload)
                if hasattr(self.producer, "poll"):
                    self.producer.poll(0)
            except Exception as error:
                cancel()
                with lock:
                    if state["status"] == "planned":
                        state["status"] = "dropped"
                receipt.fail_enqueue(error)
                break
        _record_stage("published")
        flush_error = None
        try:
            self.producer.flush(timeout=self.flush_timeout)
        except Exception as error:
            flush_error = error
        publish_evidence = evidence()
        if receipt.enqueue_error:
            raise AccessV2PublishError(
                "alarmd v2 Kafka message enqueue failed",
                publish_evidence,
                reason_code="OUTPUT_ENQUEUE_FAILED",
            ) from receipt.enqueue_error
        if publish_evidence.dropped_messages:
            raise AccessV2PublishError(
                "alarmd v2 Kafka message delivery failed",
                publish_evidence,
                reason_code="OUTPUT_DELIVERY_FAILED",
            ) from receipt.first_delivery_error
        if flush_error is not None:
            raise AccessV2PublishError("alarmd v2 Kafka flush failed", publish_evidence) from flush_error
        if publish_evidence.ack_unknown_messages:
            raise AccessV2PublishError("alarmd v2 Kafka publish was not fully acknowledged", publish_evidence)
        return publish_evidence


_publisher_lock = threading.Lock()
_publisher = None
_publisher_pid = None
_publisher_initialize_log_pid = None
_publisher_initialize_log_at = 0.0
_PUBLISHER_INITIALIZE_LOG_INTERVAL_SECONDS = 30


def _log_publisher_initialize_failure(process_id: int) -> None:
    global _publisher_initialize_log_pid, _publisher_initialize_log_at

    now = time.monotonic()
    if (
        _publisher_initialize_log_pid == process_id
        and now - _publisher_initialize_log_at < _PUBLISHER_INITIALIZE_LOG_INTERVAL_SECONDS
    ):
        return
    _publisher_initialize_log_pid = process_id
    _publisher_initialize_log_at = now
    logger.exception(
        "[alarmd shadow] component=alarmd-python stage=access_v2 result=fail_open reason=KAFKA_UNAVAILABLE"
    )


def _new_async_publisher() -> BoundedAccessShadowPublisher:
    # Kafka construction is intentionally lazy and happens in the async
    # worker, never in the Python Access request path.
    kafka_publisher = None

    def run(source: AccessPublishSource):
        nonlocal kafka_publisher
        started = time.monotonic()
        try:
            jobs = build_access_publish_jobs(source, source.records)
            _record_stage("built")
        except Exception:
            _record_stage("dropped")
            _record_access_funnel(len(source.records))
            logger.exception(
                "[alarmd shadow] component=alarmd-python stage=access_v2 result=coverage_gap "
                "reason=PLAN_INVALID execution_id=%s query_group_key=%s duration_ms=%s",
                source.alarmd_v2_execution_id,
                source.strategy_group_key,
                max(0, round((time.monotonic() - started) * 1000)),
            )
            return
        try:
            if kafka_publisher is None:
                kafka_publisher = KafkaExecutionEnvelopePublisher(
                    shadow_kafka_config(settings.ALARMD_V2_SHADOW_KAFKA_CONFIG),
                    shadow_topics(settings.ALARMD_V2_SHADOW_ALLOWED_TOPICS),
                )
            from alarm_backends.core.alarmd.telemetry import observe_shadow_publish

            with observe_shadow_publish(TELEMETRY_STAGE):
                publish_evidence = kafka_publisher.publish(jobs)
        except AccessV2PublishError as error:
            if error.evidence.acked_messages:
                _record_acknowledged_records(error.evidence.acked_records)
            _record_stage("dropped")
            _record_access_funnel(len(source.records), error.evidence)
            logger.exception(
                "[alarmd shadow] component=alarmd-python stage=access_v2 result=fail_open "
                "reason=%s execution_id=%s query_group_key=%s datasets=%s "
                "planned_messages=%s planned_records=%s planned_bytes=%s "
                "published_messages=%s published_records=%s published_bytes=%s "
                "acked_messages=%s acked_records=%s acked_bytes=%s "
                "dropped_messages=%s dropped_records=%s dropped_bytes=%s "
                "ack_unknown_messages=%s ack_unknown_records=%s ack_unknown_bytes=%s "
                "planner_dropped_records=%s duration_ms=%s",
                error.reason_code,
                source.alarmd_v2_execution_id,
                source.strategy_group_key,
                len(jobs),
                error.evidence.planned_messages,
                error.evidence.planned_records,
                error.evidence.planned_bytes,
                error.evidence.published_messages,
                error.evidence.published_records,
                error.evidence.published_bytes,
                error.evidence.acked_messages,
                error.evidence.acked_records,
                error.evidence.acked_bytes,
                error.evidence.dropped_messages,
                error.evidence.dropped_records,
                error.evidence.dropped_bytes,
                error.evidence.ack_unknown_messages,
                error.evidence.ack_unknown_records,
                error.evidence.ack_unknown_bytes,
                error.evidence.planner_dropped_records,
                max(0, round((time.monotonic() - started) * 1000)),
            )
            return
        except Exception:
            _record_stage("dropped")
            _record_access_funnel(len(source.records))
            logger.exception(
                "[alarmd shadow] component=alarmd-python stage=access_v2 result=fail_open "
                "reason=KAFKA_UNAVAILABLE execution_id=%s query_group_key=%s datasets=%s duration_ms=%s",
                source.alarmd_v2_execution_id,
                source.strategy_group_key,
                len(jobs),
                max(0, round((time.monotonic() - started) * 1000)),
            )
        else:
            _record_stage("acked", publish_evidence.acked_records)
            _record_access_funnel(len(source.records), publish_evidence)
            query_completeness, query_reason = _query_outcome(jobs)
            logger.info(
                "[alarmd shadow] component=alarmd-python stage=access_v2 result=acked "
                "execution_id=%s query_group_key=%s datasets=%s "
                "messages=%s records=%s bytes=%s source_records=%s planned_records=%s "
                "prewire_excluded_records=%s query_completeness=%s query_reason=%s "
                "planner_dropped_records=%s duration_ms=%s",
                source.alarmd_v2_execution_id,
                source.strategy_group_key,
                len(jobs),
                publish_evidence.acked_messages,
                publish_evidence.acked_records,
                publish_evidence.acked_bytes,
                len(source.records),
                publish_evidence.planned_records,
                len(source.records) - publish_evidence.planned_records,
                query_completeness,
                query_reason,
                publish_evidence.planner_dropped_records,
                max(0, round((time.monotonic() - started) * 1000)),
            )

    return BoundedAccessShadowPublisher(
        max_jobs=int(settings.ALARMD_V2_SHADOW_ASYNC_MAX_JOBS),
        max_records=int(settings.ALARMD_V2_SHADOW_ASYNC_MAX_RECORDS),
        max_bytes=int(settings.ALARMD_V2_SHADOW_ASYNC_MAX_BYTES),
        run_job=run,
    )


def submit_access_shadow(processor, records: Sequence) -> bool:
    if not shadow_flag(settings.ALARMD_SHADOW_ENABLED):
        return False
    if getattr(processor, "alarmd_v2_query_result", None) is None:
        return False
    _record_stage("source")
    source = AccessPublishSource.capture(processor, records)
    global _publisher, _publisher_pid
    process_id = os.getpid()
    with _publisher_lock:
        if _publisher is None or _publisher_pid != process_id:
            try:
                _publisher = _new_async_publisher()
            except Exception:
                _record_stage("dropped")
                _record_access_funnel(len(records))
                _log_publisher_initialize_failure(process_id)
                return False
            _publisher_pid = process_id
        publisher = _publisher
    accepted = publisher.submit(
        source,
        record_count=len(records),
        retained_bytes=source.retained_reference_bytes,
    )
    if not accepted:
        _record_stage("dropped")
        _record_access_funnel(len(records))
        logger.warning(
            "[alarmd shadow] component=alarmd-python stage=access_v2 result=coverage_gap reason=RESOURCE_HARD_STOP records=%s",
            len(records),
        )
    elif accepted:
        _record_stage("enqueued")
    return accepted


def close_access_shadow_publisher(timeout: float | None = None) -> bool:
    with _publisher_lock:
        publisher = _publisher
    if publisher is None:
        return True
    timeout = float(settings.ALARMD_V2_SHADOW_DRAIN_TIMEOUT_SECONDS if timeout is None else timeout)
    return publisher.close(timeout)


def _close_access_shadow_on_worker_shutdown(**_kwargs) -> None:
    if not close_access_shadow_publisher():
        jobs, records, retained_bytes = _publisher.usage()
        logger.warning(
            "[alarmd shadow] component=alarmd-python stage=access_v2 result=coverage_gap "
            "reason=OUTPUT_ACK_UNKNOWN jobs=%s records=%s bytes=%s",
            jobs,
            records,
            retained_bytes,
        )


try:
    from celery.signals import worker_process_shutdown

    worker_process_shutdown.connect(_close_access_shadow_on_worker_shutdown, weak=False)
except ImportError:
    pass
