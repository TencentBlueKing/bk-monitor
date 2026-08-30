"""Short-lived Redis records for Resource Call inspection tasks.

Celery is only the executor.  The public task identity, progress and result are
owned by Resource Call so callers never depend on a Celery result backend or
learn Celery/JOB identifiers.
"""

from __future__ import annotations

import json
import uuid
import zlib
from datetime import datetime, timedelta
from typing import Any

from django.core.cache import caches
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone


TASK_TYPE_HOST_INSPECTION = "collector_host_inspection"
ACTIVE_STATUSES = {"pending", "running"}


class ResourceInspectionTaskRecord:
    """Persist bounded task metadata, compressed evidence and an active key."""

    META_TTL_SECONDS = 24 * 60 * 60
    RESULT_TTL_SECONDS = 60 * 60
    ACTIVE_TTL_SECONDS = 120
    DEADLINE_SECONDS = 90

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
    ) -> tuple[dict[str, Any], bool]:
        """Atomically acquire a target and create its public task record.

        A stale active key is reclaimed once.  A valid pending/running task is
        returned as-is so the caller does not dispatch a duplicate JOB probe.
        """

        active_key = cls._active_key(target)
        for _attempt in range(2):
            task_id = str(uuid.uuid4())
            if cls.cache().add(active_key, task_id, timeout=cls.ACTIVE_TTL_SECONDS):
                record = cls._new_record(
                    task_id=task_id,
                    app_code=app_code,
                    bk_tenant_id=bk_tenant_id,
                    target=target,
                    request_options=request_options,
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
    ) -> dict[str, Any]:
        now = timezone.now()
        return {
            "task_id": task_id,
            "task_type": TASK_TYPE_HOST_INSPECTION,
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
            "deadline_at": (now + timedelta(seconds=cls.DEADLINE_SECONDS)).isoformat(),
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
        cls._delete_if_owner(cls._active_key(record.get("target") or {}), record.get("task_id"))

    @classmethod
    def claim_execution(cls, task_id: str) -> bool:
        return bool(cls.cache().add(cls._execution_key(task_id), task_id, timeout=cls.ACTIVE_TTL_SECONDS))

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
            return cls.DEADLINE_SECONDS
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
    def _active_key(cls, target: dict[str, Any]) -> str:
        return (
            f"{cls.ACTIVE_KEY_PREFIX}{TASK_TYPE_HOST_INSPECTION}:"
            f"{target.get('collector_config_id')}:{target.get('bk_host_id')}"
        )

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
