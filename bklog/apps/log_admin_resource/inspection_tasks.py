"""Short-lived Redis records for Resource Call inspection tasks.

Celery is only the executor.  The public task identity, progress and result are
owned by Resource Call so callers never depend on a Celery result backend or
learn Celery/JOB identifiers.
"""

from __future__ import annotations

import hashlib
import json
import uuid
import zlib
from datetime import datetime, timedelta
from typing import Any

from django.core.cache import caches
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone


TASK_TYPE_HOST_INSPECTION = "collector_host_inspection"
TASK_TYPE_K8S_INSPECTION = "collector_k8s_inspection"
ACTIVE_STATUSES = {"pending", "running"}
TASK_DEADLINE_SECONDS = {
    TASK_TYPE_HOST_INSPECTION: 90,
    TASK_TYPE_K8S_INSPECTION: 120,
}


def request_fingerprint(*, task_type: str, target: dict[str, Any], request_options: dict[str, Any]) -> str:
    """Return a stable opaque identity for one normalized inspection request."""

    payload = {"task_type": task_type, "target": target, "request_options": request_options}
    encoded = json.dumps(payload, cls=DjangoJSONEncoder, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class ResourceInspectionTaskRecord:
    """Persist bounded task metadata, compressed evidence and an active key."""

    META_TTL_SECONDS = 24 * 60 * 60
    RESULT_TTL_SECONDS = 60 * 60
    ACTIVE_TTL_SECONDS = 120
    DEADLINE_SECONDS = 90
    MAX_RESULT_BYTES = 10 * 1024 * 1024

    META_KEY_PREFIX = "bklog:resource_inspection:task:"
    RESULT_KEY_PREFIX = "bklog:resource_inspection:result:"
    ACTIVE_KEY_PREFIX = "bklog:resource_inspection:active:"
    EXECUTION_KEY_PREFIX = "bklog:resource_inspection:execution:"

    @staticmethod
    def cache():
        return caches["redis"]

    @classmethod
    def create_or_reuse(
        cls,
        *,
        app_code: str,
        bk_tenant_id: str,
        target: dict[str, Any],
        request_options: dict[str, Any],
        task_type: str = TASK_TYPE_HOST_INSPECTION,
        fingerprint: str | None = None,
        deadline_seconds: int | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Atomically acquire one normalized request and create its public record.

        A stale active key is reclaimed once.  A valid pending/running task is
        returned as-is so the caller does not dispatch duplicate remote probes.
        """

        if task_type not in TASK_DEADLINE_SECONDS:
            raise ValueError(f"unsupported inspection task type: {task_type}")
        fingerprint = fingerprint or request_fingerprint(
            task_type=task_type, target=target, request_options=request_options
        )
        deadline_seconds = deadline_seconds or TASK_DEADLINE_SECONDS[task_type]
        active_ttl_seconds = max(cls.ACTIVE_TTL_SECONDS, deadline_seconds + 30)
        active_key = cls._active_key(task_type=task_type, fingerprint=fingerprint)
        for _attempt in range(2):
            task_id = str(uuid.uuid4())
            if cls.cache().add(active_key, task_id, timeout=active_ttl_seconds):
                record = cls._new_record(
                    task_id=task_id,
                    app_code=app_code,
                    bk_tenant_id=bk_tenant_id,
                    target=target,
                    request_options=request_options,
                    task_type=task_type,
                    fingerprint=fingerprint,
                    deadline_seconds=deadline_seconds,
                    active_ttl_seconds=active_ttl_seconds,
                )
                try:
                    cls.save(record)
                except Exception:
                    cls.release_active(record)
                    raise
                return record, False

            active_task_id = cls._cache_text(cls.cache().get(active_key))
            active_record = cls.get(active_task_id) if active_task_id else None
            if active_record and cls.is_active(active_record):
                if active_record.get("app_code") == app_code and active_record.get("bk_tenant_id") == bk_tenant_id:
                    return active_record, True
                raise RuntimeError("inspection target already has an active task")

            cls._delete_if_owner(active_key, active_task_id)

        raise RuntimeError("inspection target is busy")

    @classmethod
    def _new_record(
        cls,
        *,
        task_id: str,
        app_code: str,
        bk_tenant_id: str,
        target: dict[str, Any],
        request_options: dict[str, Any],
        task_type: str,
        fingerprint: str,
        deadline_seconds: int,
        active_ttl_seconds: int,
    ) -> dict[str, Any]:
        now = timezone.now()
        return {
            "task_id": task_id,
            "task_type": task_type,
            "request_fingerprint": fingerprint,
            "deadline_seconds": deadline_seconds,
            "active_ttl_seconds": active_ttl_seconds,
            "task_status": "pending",
            "phase": "queued",
            "app_code": app_code,
            "bk_tenant_id": bk_tenant_id,
            "target": target,
            "request_options": request_options,
            "created_at": now.isoformat(),
            "started_at": None,
            "updated_at": now.isoformat(),
            "finished_at": None,
            "heartbeat_at": now.isoformat(),
            "deadline_at": (now + timedelta(seconds=deadline_seconds)).isoformat(),
            "result_expires_at": (now + timedelta(seconds=cls.RESULT_TTL_SECONDS)).isoformat(),
            "celery_task_id": None,
            "job_instance_id": None,
            "job_step_instance_id": None,
            "probes": {},
            "error": None,
        }

    @classmethod
    def save(cls, record: dict[str, Any]) -> dict[str, Any]:
        record = dict(record)
        record["updated_at"] = timezone.now().isoformat()
        encoded = json.dumps(record, cls=DjangoJSONEncoder, ensure_ascii=False, separators=(",", ":"))
        cls.cache().set(cls._meta_key(record["task_id"]), encoded, timeout=cls.META_TTL_SECONDS)
        stored = cls.get(record["task_id"])
        if not stored:
            raise RuntimeError("inspection task record was not persisted")
        return stored

    @classmethod
    def get(cls, task_id: str | None) -> dict[str, Any] | None:
        if not task_id:
            return None
        raw = cls.cache().get(cls._meta_key(task_id))
        if raw is None:
            return None
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return json.loads(raw) if isinstance(raw, str) else dict(raw)
        except (TypeError, ValueError, UnicodeDecodeError):
            return None

    @classmethod
    def update(cls, task_id: str, *, heartbeat: bool = True, **fields: Any) -> dict[str, Any] | None:
        record = cls.get(task_id)
        if not record:
            return None
        record.update(fields)
        if heartbeat:
            record["heartbeat_at"] = timezone.now().isoformat()
        return cls.save(record)

    @classmethod
    def set_probe(cls, task_id: str, name: str, probe: dict[str, Any]) -> dict[str, Any] | None:
        record = cls.get(task_id)
        if not record:
            return None
        probes = dict(record.get("probes") or {})
        probes[name] = cls._probe_summary(probe)
        record["probes"] = probes
        record["heartbeat_at"] = timezone.now().isoformat()
        return cls.save(record)

    @classmethod
    def store_result(cls, task_id: str, result: dict[str, Any]) -> None:
        encoded = json.dumps(result, cls=DjangoJSONEncoder, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > cls.MAX_RESULT_BYTES:
            raise RuntimeError("inspection task result exceeds the 10 MiB response limit")
        compressed = zlib.compress(encoded)
        record = cls.get(task_id)
        expires_at = cls._parse_datetime(record.get("result_expires_at")) if record else None
        timeout = cls.RESULT_TTL_SECONDS
        if expires_at:
            timeout = max(1, int((expires_at - timezone.now()).total_seconds()))
        cls.cache().set(cls._result_key(task_id), compressed, timeout=timeout)
        if cls.cache().get(cls._result_key(task_id)) is None:
            raise RuntimeError("inspection task result was not persisted")

    @classmethod
    def load_result(cls, task_id: str) -> dict[str, Any] | None:
        raw = cls.cache().get(cls._result_key(task_id))
        if raw is None:
            return None
        try:
            if isinstance(raw, str):
                raw = raw.encode("latin1")
            return json.loads(zlib.decompress(raw).decode("utf-8"))
        except (TypeError, ValueError, UnicodeDecodeError, zlib.error):
            return None

    @classmethod
    def set_internal_execution_ids(
        cls,
        task_id: str,
        *,
        celery_task_id: str | None = None,
        job_instance_id: int | None = None,
        job_step_instance_id: int | None = None,
    ) -> dict[str, Any] | None:
        fields = {}
        if celery_task_id is not None:
            fields["celery_task_id"] = celery_task_id
        if job_instance_id is not None:
            fields["job_instance_id"] = job_instance_id
        if job_step_instance_id is not None:
            fields["job_step_instance_id"] = job_step_instance_id
        return cls.update(task_id, **fields)

    @classmethod
    def delete_pending(cls, record: dict[str, Any]) -> None:
        cls.cache().delete(cls._meta_key(record["task_id"]))
        cls.cache().delete(cls._result_key(record["task_id"]))
        cls.release_active(record)

    @classmethod
    def release_active(cls, record: dict[str, Any]) -> None:
        task_type = record.get("task_type") or TASK_TYPE_HOST_INSPECTION
        fingerprint = record.get("request_fingerprint") or request_fingerprint(
            task_type=task_type,
            target=record.get("target") or {},
            request_options=record.get("request_options") or {},
        )
        cls._delete_if_owner(cls._active_key(task_type=task_type, fingerprint=fingerprint), record.get("task_id"))

    @classmethod
    def claim_execution(cls, task_id: str) -> bool:
        record = cls.get(task_id) or {}
        timeout = int(record.get("active_ttl_seconds") or cls.ACTIVE_TTL_SECONDS)
        return bool(cls.cache().add(cls._execution_key(task_id), task_id, timeout=timeout))

    @classmethod
    def release_execution(cls, task_id: str) -> None:
        cls._delete_if_owner(cls._execution_key(task_id), task_id)

    @classmethod
    def is_active(cls, record: dict[str, Any]) -> bool:
        if record.get("task_status") not in ACTIVE_STATUSES:
            return False
        return not cls.is_deadline_exceeded(record)

    @classmethod
    def is_deadline_exceeded(cls, record: dict[str, Any]) -> bool:
        deadline = cls._parse_datetime(record.get("deadline_at"))
        return bool(deadline and timezone.now() > deadline)

    @classmethod
    def remaining_seconds(cls, record: dict[str, Any]) -> int:
        deadline = cls._parse_datetime(record.get("deadline_at"))
        if not deadline:
            return int(record.get("deadline_seconds") or cls.DEADLINE_SECONDS)
        return max(0, int((deadline - timezone.now()).total_seconds()))

    @classmethod
    def result_expired(cls, record: dict[str, Any]) -> bool:
        expires_at = cls._parse_datetime(record.get("result_expires_at"))
        return bool(expires_at and timezone.now() >= expires_at)

    @classmethod
    def normalize_timeout(cls, record: dict[str, Any]) -> dict[str, Any]:
        if (
            not cls.is_active(record)
            and record.get("task_status") in ACTIVE_STATUSES
            and cls.is_deadline_exceeded(record)
        ):
            now = timezone.now().isoformat()
            record.update(
                {
                    "task_status": "timed_out",
                    "phase": "timed_out",
                    "finished_at": now,
                    "heartbeat_at": now,
                    "error": {"code": "task_timed_out", "message": "inspection task exceeded its deadline"},
                }
            )
            record = cls.save(record)
            cls.release_active(record)
        return record

    @classmethod
    def _delete_if_owner(cls, key: str, expected_owner: str | None) -> None:
        if not expected_owner:
            return
        backend = cls.cache()
        client_adapter = getattr(backend, "client", None)
        if client_adapter is not None and hasattr(client_adapter, "get_client") and hasattr(client_adapter, "encode"):
            redis_client = client_adapter.get_client(write=True)
            redis_client.eval(
                "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
                1,
                backend.make_key(key),
                client_adapter.encode(str(expected_owner)),
            )
            return
        if cls._cache_text(backend.get(key)) == str(expected_owner):
            backend.delete(key)

    @classmethod
    def _probe_summary(cls, probe: dict[str, Any]) -> dict[str, Any]:
        return {
            key: probe.get(key)
            for key in ("status", "code", "summary", "started_at", "finished_at", "duration_ms")
            if key in probe
        }

    @classmethod
    def _meta_key(cls, task_id: str) -> str:
        return f"{cls.META_KEY_PREFIX}{task_id}"

    @classmethod
    def _result_key(cls, task_id: str) -> str:
        return f"{cls.RESULT_KEY_PREFIX}{task_id}"

    @classmethod
    def _active_key(cls, *, task_type: str, fingerprint: str) -> str:
        return f"{cls.ACTIVE_KEY_PREFIX}{task_type}:{fingerprint}"

    @classmethod
    def _execution_key(cls, task_id: str) -> str:
        return f"{cls.EXECUTION_KEY_PREFIX}{task_id}"

    @staticmethod
    def _cache_text(value: Any) -> str | None:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value) if value is not None else None

    @staticmethod
    def _parse_datetime(value: str | None):
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed


class K8sCollectorCandidateStore:
    """Short-lived opaque bindings for server-discovered collector candidates."""

    TTL_SECONDS = 5 * 60
    KEY_PREFIX = "bklog:resource_inspection:k8s_candidate:"

    @classmethod
    def create(cls, binding: dict[str, Any]) -> str:
        candidate_id = str(uuid.uuid4())
        encoded = json.dumps(binding, cls=DjangoJSONEncoder, ensure_ascii=False, separators=(",", ":"))
        ResourceInspectionTaskRecord.cache().set(cls._key(candidate_id), encoded, timeout=cls.TTL_SECONDS)
        if ResourceInspectionTaskRecord.cache().get(cls._key(candidate_id)) is None:
            raise RuntimeError("collector candidate binding was not persisted")
        return candidate_id

    @classmethod
    def get(cls, candidate_id: str) -> dict[str, Any] | None:
        raw = ResourceInspectionTaskRecord.cache().get(cls._key(candidate_id))
        if raw is None:
            return None
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return json.loads(raw) if isinstance(raw, str) else dict(raw)
        except (TypeError, ValueError, UnicodeDecodeError):
            return None

    @classmethod
    def _key(cls, candidate_id: str) -> str:
        return f"{cls.KEY_PREFIX}{candidate_id}"


class K8sDeepProbeSlots:
    """Bound deep exec concurrency to two probes per exact collector Pod UID."""

    MAX_SLOTS = 2
    # Keep the slot for the complete 120-second task window, including logs and pre/post identity checks.
    TTL_SECONDS = 130
    KEY_PREFIX = "bklog:resource_inspection:k8s_deep:"

    @classmethod
    def claim(cls, pod_uid: str, task_id: str) -> str | None:
        pod_key = hashlib.sha256(pod_uid.encode("utf-8")).hexdigest()
        for slot in range(cls.MAX_SLOTS):
            key = f"{cls.KEY_PREFIX}{pod_key}:{slot}"
            if ResourceInspectionTaskRecord.cache().add(key, task_id, timeout=cls.TTL_SECONDS):
                return key
        return None

    @classmethod
    def release(cls, key: str | None, task_id: str) -> None:
        if key:
            ResourceInspectionTaskRecord._delete_if_owner(key, task_id)
