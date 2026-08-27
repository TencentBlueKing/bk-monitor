"""Python Access adapter for the alarmd v2 Shadow writer."""

import copy
import logging
import math
import os
import sys
import threading
import time
from collections import Counter, defaultdict
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
    dropped_records: int


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
        dropped_records=record_count,
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


def _identity_fields(item, records: Sequence) -> list[str]:
    schemas = Counter()
    for record in records:
        try:
            schemas[tuple(sorted(record.clean_dimension_fields()))] += 1
        except Exception:
            continue
    if schemas:
        # One malformed or exceptional record must not choose the contract for
        # every sibling. Ties are deterministic.
        count = max(schemas.values())
        return list(min(schema for schema, frequency in schemas.items() if frequency == count))
    dimensions = getattr(getattr(item, "query", None), "dimensions", None)
    if dimensions is None:
        query_configs = getattr(item, "query_configs", None) or []
        dimensions = query_configs[0].get("agg_dimension", []) if query_configs else []
    return sorted(set(dimensions or []))


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


def _record_snapshot(
    record, *, tenant_id: str, business_id: str, identity_fields: list[str], received_time: int
) -> dict:
    if sorted(record.clean_dimension_fields()) != identity_fields:
        raise AccessV2BuildError("record identity schema conflicts with Dataset Contract")
    dimensions = dict(record.data.get("dimensions") or {})
    if any(isinstance(value, (dict, list, tuple)) for value in dimensions.values()):
        raise AccessV2BuildError("v2 dimensions must contain scalar JSON values")
    fields = []
    for name in identity_fields:
        value = dimensions.get(name)
        if value is None or isinstance(value, (dict, list, tuple)):
            raise AccessV2BuildError(f"identity dimension {name} is missing or non-scalar")
        fields.append({"name": name, "value": value})
    source_time = int(record.data["time"])
    digest = derive_dimension_identity_digest_v2(tenant_id, business_id, fields)
    value = record.data.get("value")
    if isinstance(value, float) and not math.isfinite(value):
        raise AccessV2BuildError("record value must be finite")
    try:
        canonical_json_v2({"dimensions": dimensions, "value": value})
    except (TypeError, ValueError) as error:
        raise AccessV2BuildError("record dimensions and value must be canonical JSON scalars") from error
    return {
        "record_id": derive_record_id_v2(digest, source_time),
        "source_time": source_time,
        "business_id": business_id,
        "dimension_identity": {"fields": fields, "digest": digest},
        "values": {"value": value},
        "dimensions": dimensions,
        "received_time": received_time,
    }


def build_access_publish_job(processor, records: Sequence, *, received_time: int | None = None) -> AccessPublishJob:
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
    identity_fields = _identity_fields(first_item, records)
    query_window = max(0, int(processor.until_timestamp) - int(processor.from_timestamp))
    plan_set, selection_item_ids, terminal_reasons = _build_plan_set(processor.items, identity_fields, query_window)
    if terminal_reasons:
        _record_stage("dropped")
        logger.warning(
            "[alarmd shadow] component=alarmd-python stage=access_v2 result=coverage_gap reason=%s plans=%s",
            terminal_reasons[0],
            len(terminal_reasons),
        )
    received_time = int(time.time()) if received_time is None else int(received_time)
    valid_records = []
    record_snapshots = []
    invalid_record_count = 0
    first_invalid_ordinal = None
    for ordinal, record in enumerate(records):
        try:
            snapshot = _record_snapshot(
                record,
                tenant_id=tenant_id,
                business_id=business_id,
                identity_fields=identity_fields,
                received_time=received_time,
            )
        except (AccessV2BuildError, KeyError, TypeError, ValueError):
            invalid_record_count += 1
            if first_invalid_ordinal is None:
                first_invalid_ordinal = ordinal
            continue
        valid_records.append(record)
        record_snapshots.append(snapshot)
    if invalid_record_count:
        _record_stage("dropped")
        logger.warning(
            "[alarmd shadow] component=alarmd-python stage=access_v2 result=coverage_gap "
            "reason=RECORD_IDENTITY_CONFLICT records=%s first_record_ordinal=%s",
            invalid_record_count,
            first_invalid_ordinal,
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

    def publish(self, job: AccessPublishJob) -> AccessPublishEvidence:
        try:
            messages, drops = build_execution_messages(
                job,
                max_records=self.max_records,
                max_envelope_bytes=self.max_envelope_bytes,
            )
        except PlanSetTooLarge as error:
            raise AccessV2PublishError(
                "alarmd v2 complete Plan Set exceeds one message",
                _fully_dropped_evidence(job.record_count),
                reason_code="MESSAGE_BUDGET_EXCEEDED",
            ) from error
        except AccessV2WriterError as error:
            raise AccessV2PublishError(
                "alarmd v2 message planning failed",
                _fully_dropped_evidence(job.record_count),
                reason_code="PLAN_INVALID",
            ) from error
        if drops:
            _record_stage("dropped")
            logger.warning(
                "[alarmd shadow] component=alarmd-python stage=access_v2 result=coverage_gap "
                "reason=%s records=%s first_record_ordinal=%s",
                drops[0].reason_code,
                len(drops),
                drops[0].record_ordinal,
            )
        receipt = KafkaPublishReceipt()
        lock = threading.Lock()
        published_messages = 0
        published_records = 0
        published_bytes = 0
        acked_messages = 0
        acked_records = 0
        acked_bytes = 0

        def evidence() -> AccessPublishEvidence:
            with lock:
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
                    dropped_records=len(drops),
                )

        def delivery_callback(current, downstream):
            delivered = False

            def on_delivery(error, broker_message):
                nonlocal delivered, acked_messages, acked_records, acked_bytes
                with lock:
                    if delivered:
                        return
                    delivered = True
                    if error is None:
                        acked_messages += 1
                        acked_records += current.record_count
                        acked_bytes += len(current.payload)
                downstream(error, broker_message)

            return on_delivery

        for message in messages:
            callback, cancel = receipt.reserve(message.record_count)
            try:
                self.producer.produce(
                    topic=self.topic,
                    key=message.key,
                    value=message.payload,
                    on_delivery=delivery_callback(message, callback),
                )
                with lock:
                    published_messages += 1
                    published_records += message.record_count
                    published_bytes += len(message.payload)
                if hasattr(self.producer, "poll"):
                    self.producer.poll(0)
            except Exception as error:
                cancel()
                receipt.fail_enqueue(error)
                break
        _record_stage("published")
        try:
            remaining = self.producer.flush(timeout=self.flush_timeout)
        except Exception as error:
            raise AccessV2PublishError("alarmd v2 Kafka flush failed", evidence()) from error
        if (
            receipt.enqueue_error
            or receipt.first_delivery_error
            or (remaining and receipt.pending_messages)
            or receipt.pending_messages
        ):
            raise AccessV2PublishError("alarmd v2 Kafka publish was not fully acknowledged", evidence())
        return evidence()


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
            job = build_access_publish_job(source, source.records)
            _record_stage("built")
        except Exception:
            _record_stage("dropped")
            logger.exception(
                "[alarmd shadow] component=alarmd-python stage=access_v2 result=coverage_gap "
                "reason=PLAN_INVALID duration_ms=%s",
                max(0, round((time.monotonic() - started) * 1000)),
            )
            return
        try:
            if kafka_publisher is None:
                kafka_publisher = KafkaExecutionEnvelopePublisher(
                    shadow_kafka_config(settings.ALARMD_V2_SHADOW_KAFKA_CONFIG),
                    shadow_topics(settings.ALARMD_V2_SHADOW_ALLOWED_TOPICS),
                )
            publish_evidence = kafka_publisher.publish(job)
        except AccessV2PublishError as error:
            if error.evidence.acked_messages:
                _record_stage("acked", error.evidence.acked_records)
            _record_stage("dropped")
            logger.exception(
                "[alarmd shadow] component=alarmd-python stage=access_v2 result=fail_open "
                "reason=%s planned_messages=%s planned_records=%s planned_bytes=%s "
                "published_messages=%s published_records=%s published_bytes=%s "
                "acked_messages=%s acked_records=%s acked_bytes=%s dropped_records=%s duration_ms=%s",
                error.reason_code,
                error.evidence.planned_messages,
                error.evidence.planned_records,
                error.evidence.planned_bytes,
                error.evidence.published_messages,
                error.evidence.published_records,
                error.evidence.published_bytes,
                error.evidence.acked_messages,
                error.evidence.acked_records,
                error.evidence.acked_bytes,
                error.evidence.dropped_records,
                max(0, round((time.monotonic() - started) * 1000)),
            )
            return
        except Exception:
            _record_stage("dropped")
            logger.exception(
                "[alarmd shadow] component=alarmd-python stage=access_v2 result=fail_open "
                "reason=KAFKA_UNAVAILABLE duration_ms=%s",
                max(0, round((time.monotonic() - started) * 1000)),
            )
        else:
            _record_stage("acked", publish_evidence.acked_records)
            logger.info(
                "[alarmd shadow] component=alarmd-python stage=access_v2 result=acked "
                "messages=%s records=%s bytes=%s dropped_records=%s duration_ms=%s",
                publish_evidence.acked_messages,
                publish_evidence.acked_records,
                publish_evidence.acked_bytes,
                publish_evidence.dropped_records,
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
