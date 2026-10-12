"""alarmd v2 Python Writer primitives and process-local bounded queue.

The wire contract is frozen by bkmonitor-datalink M0.  This module only owns
the Python writer side: canonical identities, self-contained message planning
and fail-open asynchronous admission.
"""

import copy
import hashlib
import json
import queue
import struct
import sys
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


REASON_RECORD_TOO_LARGE = "RECORD_TOO_LARGE"
_STOP = object()


class AccessV2WriterError(ValueError):
    pass


class PlanSetTooLarge(AccessV2WriterError):
    pass


def canonical_json_v2(value: Any) -> bytes:
    """Match M0 CanonicalJSONV2 for Python-produced JSON values."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _length_prefixed_sha256(domain: str, *values: bytes) -> str:
    digest = hashlib.sha256()
    for value in (domain.encode("utf-8"), *values):
        digest.update(struct.pack(">I", len(value)))
        digest.update(value)
    return digest.hexdigest()


def derive_canonical_digest_v2(domain: str, value: Any) -> str:
    return _length_prefixed_sha256(domain, canonical_json_v2(value))


def derive_dimension_identity_digest_v2(tenant_id: str, business_id: str, fields: Sequence[Mapping]) -> str:
    return _length_prefixed_sha256(
        "dimension-identity-v1",
        tenant_id.encode("utf-8"),
        business_id.encode("utf-8"),
        canonical_json_v2(list(fields)),
    )


def derive_record_id_v2(dimension_identity_digest: str, source_time: int) -> str:
    return _length_prefixed_sha256(
        "record-id-v2",
        dimension_identity_digest.encode("ascii"),
        str(source_time).encode("ascii"),
    )


def derive_query_group_kafka_key_v2(tenant_id: str, query_group_key: str) -> bytes:
    return bytes.fromhex(
        _length_prefixed_sha256(
            "query-group-kafka-key-v1",
            tenant_id.encode("utf-8"),
            query_group_key.encode("utf-8"),
        )
    )


def derive_plan_set_digest_v2(plan_set: Mapping) -> str:
    unsigned = copy.deepcopy(dict(plan_set))
    unsigned.pop("plan_set_digest", None)
    return derive_canonical_digest_v2("plan-set-v2", unsigned)


def derive_execution_payload_digest_v2(envelope: Mapping) -> str:
    unsigned = copy.deepcopy(dict(envelope))
    unsigned.pop("payload_digest", None)
    return derive_canonical_digest_v2("execution-envelope-payload-v2", unsigned)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(child) for key, child in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(child) for child in value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise AccessV2WriterError(f"unsupported snapshot value type: {type(value).__name__}")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw(child) for child in value]
    return value


def _retained_size(value: Any) -> int:
    """Conservative retained-memory accounting for one unshared snapshot."""

    if isinstance(value, Mapping):
        return sys.getsizeof(value) + sum(sys.getsizeof(key) + _retained_size(child) for key, child in value.items())
    if isinstance(value, (list, tuple)):
        return sys.getsizeof(value) + sum(_retained_size(child) for child in value)
    return sys.getsizeof(value)


@dataclass(frozen=True)
class AccessPublishJob:
    snapshot: Mapping
    records: tuple[Mapping, ...]
    selections: tuple[tuple[bool, ...], ...]
    record_count: int
    retained_bytes: int

    @classmethod
    def create(
        cls,
        *,
        execution_id: str,
        tenant_id: str,
        query_group: Mapping,
        source_window: Mapping,
        query_result: Mapping,
        dataset_contract: Mapping,
        plan_set: Mapping,
        records: Sequence[Mapping],
        selections: Sequence[Sequence[bool]],
    ) -> "AccessPublishJob":
        record_count = len(records)
        if len(selections) != int(plan_set["plan_count"]):
            raise AccessV2WriterError("selection count must match plan_count")
        normalized_selections = tuple(tuple(bool(selected) for selected in plan) for plan in selections)
        if any(len(plan) != record_count for plan in normalized_selections):
            raise AccessV2WriterError("every selection must cover the shared RecordBatch")
        snapshot_source = {
            "execution_id": execution_id,
            "tenant_id": tenant_id,
            "query_group": query_group,
            "source_window": source_window,
            "query_result": query_result,
            "dataset_contract": dataset_contract,
            "plan_set": plan_set,
        }
        frozen_records = _freeze(list(records))
        retained_bytes = (
            _retained_size(snapshot_source) + _retained_size(records) + _retained_size(normalized_selections)
        )
        snapshot = _freeze(snapshot_source)
        return cls(
            snapshot=snapshot,
            records=frozen_records,
            selections=normalized_selections,
            record_count=record_count,
            retained_bytes=retained_bytes,
        )


@dataclass(frozen=True)
class AccessPublishMessage:
    key: bytes
    payload: bytes
    record_count: int
    message_id: str


@dataclass(frozen=True)
class AccessRecordDrop:
    record_ordinal: int
    reason_code: str


def _selector_ranges(selection: Sequence[bool]) -> dict:
    ranges = []
    start = None
    for index, selected in enumerate((*selection, False)):
        if selected and start is None:
            start = index
        elif not selected and start is not None:
            ranges.append({"start": start, "end": index})
            start = None
    return {"kind": "RANGES", "ranges": ranges}


def _build_envelope(job: AccessPublishJob, start: int, end: int, message_id: str) -> dict:
    source = _thaw(job.snapshot)
    records = _thaw(job.records[start:end])
    envelope = {
        "schema": {"name": "execution-envelope", "major": 2, "minor": 0},
        "required_features": [],
        "message_id": message_id,
        **source,
        "selectors": [
            {
                "plan_ordinal": ordinal,
                "selector": _selector_ranges(selection[start:end]),
            }
            for ordinal, selection in enumerate(job.selections)
        ],
        "records": records,
    }
    envelope["payload_digest"] = derive_execution_payload_digest_v2(envelope)
    return envelope


def build_execution_messages(
    job: AccessPublishJob,
    *,
    max_records: int,
    max_envelope_bytes: int,
    message_id_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
) -> tuple[list[AccessPublishMessage], list[AccessRecordDrop]]:
    if max_records <= 0 or max_envelope_bytes <= 0:
        raise AccessV2WriterError("message budgets must be positive")

    snapshot = _thaw(job.snapshot)
    key = derive_query_group_kafka_key_v2(snapshot["tenant_id"], snapshot["query_group"]["key"])
    # Production IDs are 32-byte hexadecimal UUIDs. A wider placeholder keeps
    # planning conservative while still allowing a bounded opaque ID domain.
    placeholder_id = "0" * 64
    empty_payload = canonical_json_v2(_build_envelope(job, 0, 0, placeholder_id))
    if len(empty_payload) > max_envelope_bytes:
        raise PlanSetTooLarge("complete Plan Set exceeds one message")

    def finalize(start: int, end: int) -> AccessPublishMessage:
        message_id = message_id_factory()
        if len(message_id.encode("utf-8")) > len(placeholder_id):
            raise AccessV2WriterError("message_id exceeds the planned byte budget")
        envelope = _build_envelope(job, start, end, message_id)
        payload = canonical_json_v2(envelope)
        if len(payload) > max_envelope_bytes:
            raise AccessV2WriterError("message_id length changed an admitted message budget")
        return AccessPublishMessage(key=key, payload=payload, record_count=end - start, message_id=message_id)

    if job.record_count == 0:
        return [finalize(0, 0)], []

    messages = []
    drops = []
    start = 0
    index = 0
    record_delta = 0
    # Per Plan: range count, whether the last local index was selected,
    # current range start/end, and the exact byte delta from `ranges:[]`.
    selector_states = [(0, False, 0, 0, 0) for _selection in job.selections]

    def reset_chunk(next_start: int) -> None:
        nonlocal start, record_delta, selector_states
        start = next_start
        record_delta = 0
        selector_states = [(0, False, 0, 0, 0) for _selection in job.selections]

    def range_size(range_start: int, range_end: int) -> int:
        return len(canonical_json_v2({"start": range_start, "end": range_end}))

    while index < job.record_count:
        local_index = index - start
        record_size = len(canonical_json_v2(_thaw(job.records[index])))
        prospective_record_delta = record_delta + record_size + (1 if local_index else 0)
        prospective_states = []
        for selection, state in zip(job.selections, selector_states, strict=True):
            ranges, previous_selected, range_start, range_end, delta = state
            selected = selection[index]
            if selected and previous_selected:
                new_end = local_index + 1
                delta += range_size(range_start, new_end) - range_size(range_start, range_end)
                range_end = new_end
            elif selected:
                range_start = local_index
                range_end = local_index + 1
                delta += range_size(range_start, range_end) + (1 if ranges else 0)
                ranges += 1
            prospective_states.append((ranges, selected, range_start, range_end, delta))
        prospective_size = len(empty_payload) + prospective_record_delta + sum(state[4] for state in prospective_states)
        if prospective_size > max_envelope_bytes:
            if index > start:
                messages.append(finalize(start, index))
                reset_chunk(index)
                continue
            drops.append(AccessRecordDrop(record_ordinal=index, reason_code=REASON_RECORD_TOO_LARGE))
            index += 1
            reset_chunk(index)
            continue

        record_delta = prospective_record_delta
        selector_states = prospective_states
        index += 1
        if index - start >= max_records:
            messages.append(finalize(start, index))
            reset_chunk(index)
    if index > start:
        messages.append(finalize(start, index))
    return messages, drops


class BoundedAccessShadowPublisher:
    """One process-local worker with jobs/records/retained-bytes admission."""

    def __init__(
        self,
        *,
        max_jobs: int,
        max_records: int,
        max_bytes: int,
        run_job: Callable[[Any], None],
    ):
        if min(max_jobs, max_records, max_bytes) <= 0:
            raise ValueError("all async publisher budgets must be positive")
        self._max_jobs = max_jobs
        self._max_records = max_records
        self._max_bytes = max_bytes
        self._run_job = run_job
        self._queue = queue.Queue(maxsize=max_jobs)
        self._condition = threading.Condition()
        self._jobs = 0
        self._records = 0
        self._bytes = 0
        self._accepting = True
        self._thread = threading.Thread(target=self._worker, name="alarmd-v2-access-publisher", daemon=True)
        self._thread.start()

    def submit(self, job: Any, *, record_count: int, retained_bytes: int) -> bool:
        with self._condition:
            if (
                not self._accepting
                or self._jobs >= self._max_jobs
                or self._records + record_count > self._max_records
                or self._bytes + retained_bytes > self._max_bytes
            ):
                return False
            self._jobs += 1
            self._records += record_count
            self._bytes += retained_bytes
            try:
                self._queue.put_nowait((job, record_count, retained_bytes))
            except queue.Full:
                self._release(record_count, retained_bytes)
                return False
        return True

    def usage(self) -> tuple[int, int, int]:
        with self._condition:
            return self._jobs, self._records, self._bytes

    def wait_empty(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self._condition:
            while self._jobs:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True

    def close(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self._condition:
            self._accepting = False
        drained = self.wait_empty(timeout)
        try:
            self._queue.put_nowait(_STOP)
        except queue.Full:
            return False
        self._thread.join(timeout=max(0.0, deadline - time.monotonic()))
        return drained and not self._thread.is_alive()

    def _release(self, record_count: int, retained_bytes: int) -> None:
        self._jobs -= 1
        self._records -= record_count
        self._bytes -= retained_bytes
        self._condition.notify_all()

    def _worker(self) -> None:
        while True:
            queued = self._queue.get()
            if queued is _STOP:
                return
            job, record_count, retained_bytes = queued
            try:
                self._run_job(job)
            except Exception:
                # Shadow is fail-open. M8 observes the failure at the caller.
                pass
            finally:
                with self._condition:
                    self._release(record_count, retained_bytes)
