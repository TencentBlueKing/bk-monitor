"""Process-local bounded publisher for fail-open alarmd Shadow jobs."""

import logging
import os
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger("alarmd.shadow")

MAX_ASYNC_JOB_BYTES = 512 * 1024

ASYNC_STATUS_ENQUEUED = "enqueued"
ASYNC_STATUS_DROPPED = "dropped"
ASYNC_STATUS_WORKER_FAILED = "worker_failed"
ASYNC_STATUS_ACKED = "acked"

_DROP_LOG_INTERVAL_SECONDS = 30
_INITIALIZE_FAILURE_LOG_INTERVAL_SECONDS = 30
_STOP = object()


@dataclass(frozen=True)
class ShadowPublishJob:
    operation: str
    payload: tuple[dict, ...]


def shadow_job_encoded_size(operation: str, payload: tuple[dict, ...]) -> int:
    from alarm_backends.core.alarmd.encoder import encode_json_document

    return len(encode_json_document({"operation": operation, "payload": list(payload)}))


def shadow_job_encoded_size_from_payload_sizes(operation: str, payload_sizes: tuple[int, ...]) -> int:
    from alarm_backends.core.alarmd.encoder import encode_json_document

    empty_job_size = len(encode_json_document({"operation": operation, "payload": []}))
    return empty_job_size + sum(payload_sizes) + max(0, len(payload_sizes) - 1)


def shadow_job_fits(operation: str, payload: tuple[dict, ...]) -> bool:
    return shadow_job_encoded_size(operation, payload) <= MAX_ASYNC_JOB_BYTES


def record_shadow_async_job(stage: str, status: str) -> None:
    try:
        from alarm_backends.core.alarmd.telemetry import record_shadow_async_job as record

        record(stage, status)
    except Exception:
        logger.exception(
            "[alarmd shadow] component=alarmd-python stage=%s result=fail_open operation=async_telemetry",
            stage,
        )


def _run_shadow_job(job: ShadowPublishJob) -> int:
    if job.operation == "detect_input":
        from alarm_backends.service.detect.process import publish_alarmd_detect_shadow_batches

        return publish_alarmd_detect_shadow_batches(job.payload)
    if job.operation == "reference":
        from alarm_backends.service.trigger.processor import publish_alarmd_reference_batches

        return publish_alarmd_reference_batches(job.payload)
    raise ValueError(f"unsupported alarmd Shadow publish operation: {job.operation}")


class AsyncShadowPublisher:
    def __init__(self, *, max_jobs: int | str, run_job: Callable[[ShadowPublishJob], int] = _run_shadow_job):
        try:
            max_jobs = int(max_jobs)
        except (TypeError, ValueError) as exc:
            raise ValueError("alarmd Shadow async queue size must be a positive integer") from exc
        if max_jobs <= 0:
            raise ValueError("alarmd Shadow async queue size must be positive")
        self._queue = queue.Queue(maxsize=max_jobs)
        self._run_job = run_job
        self._start_lock = threading.Lock()
        self._thread = None
        self._last_drop_log = 0.0

    def submit(self, operation: str, payload: tuple[dict, ...]) -> bool:
        if operation not in {"detect_input", "reference"} or not payload:
            return False
        try:
            fits = shadow_job_fits(operation, payload)
        except Exception:
            record_shadow_async_job(operation, ASYNC_STATUS_DROPPED)
            self._log_drop(operation, "payload_encode_failed")
            return False
        if not fits:
            record_shadow_async_job(operation, ASYNC_STATUS_DROPPED)
            self._log_drop(operation, "payload_too_large")
            return False
        self._ensure_started()
        job = ShadowPublishJob(operation=operation, payload=payload)
        try:
            self._queue.put_nowait(job)
        except queue.Full:
            record_shadow_async_job(operation, ASYNC_STATUS_DROPPED)
            self._log_drop(operation, "queue_full")
            return False
        record_shadow_async_job(operation, ASYNC_STATUS_ENQUEUED)
        return True

    def close(self) -> None:
        thread = self._thread
        if thread is None:
            return
        self._queue.join()
        self._queue.put(_STOP)
        thread.join(timeout=1)

    def pending_jobs(self) -> int:
        with self._queue.mutex:
            return self._queue.unfinished_tasks

    def _ensure_started(self) -> None:
        if self._thread is not None:
            return
        with self._start_lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._worker, name="alarmd-shadow-publisher", daemon=True)
                self._thread.start()

    def _worker(self) -> None:
        while True:
            job = self._queue.get()
            try:
                if job is _STOP:
                    return
                started_at = time.monotonic()
                try:
                    acknowledged = self._run_job(job)
                except Exception:
                    record_shadow_async_job(job.operation, ASYNC_STATUS_WORKER_FAILED)
                    logger.exception(
                        "[alarmd shadow] component=alarmd-python stage=%s result=fail_open "
                        "operation=async_worker duration_ms=%s",
                        job.operation,
                        max(0, round((time.monotonic() - started_at) * 1000)),
                    )
                else:
                    record_shadow_async_job(job.operation, ASYNC_STATUS_ACKED)
                    logger.info(
                        "[alarmd shadow] component=alarmd-python stage=%s result=broker_ack "
                        "operation=async_worker records=%s duration_ms=%s",
                        job.operation,
                        acknowledged,
                        max(0, round((time.monotonic() - started_at) * 1000)),
                    )
            finally:
                self._queue.task_done()

    def _log_drop(self, operation: str, reason: str) -> None:
        now = time.monotonic()
        if now - self._last_drop_log < _DROP_LOG_INTERVAL_SECONDS:
            return
        self._last_drop_log = now
        logger.warning(
            "[alarmd shadow] component=alarmd-python stage=%s result=fail_open operation=async_enqueue reason=%s",
            operation,
            reason,
        )


_publisher_lock = threading.Lock()
_publisher = None
_publisher_pid = None
_initialize_failure_log_pid = None
_last_initialize_failure_log = 0.0


def _log_initialize_failure(operation: str, process_id: int) -> None:
    global _initialize_failure_log_pid, _last_initialize_failure_log

    now = time.monotonic()
    if (
        _initialize_failure_log_pid == process_id
        and now - _last_initialize_failure_log < _INITIALIZE_FAILURE_LOG_INTERVAL_SECONDS
    ):
        return
    _initialize_failure_log_pid = process_id
    _last_initialize_failure_log = now
    logger.exception(
        "[alarmd shadow] component=alarmd-python stage=%s result=fail_open operation=async_initialize",
        operation,
    )


def _report_pending_jobs_on_shutdown(publisher: AsyncShadowPublisher, process_id: int) -> None:
    if os.getpid() != process_id:
        return
    pending = publisher.pending_jobs()
    if pending:
        logger.warning(
            "[alarmd shadow] component=alarmd-python stage=async_publish result=coverage_gap "
            "operation=process_exit pending_jobs=%s",
            pending,
        )


def _report_current_process_pending_jobs(**_kwargs) -> None:
    with _publisher_lock:
        publisher = _publisher
        process_id = _publisher_pid
    if publisher is not None and process_id is not None:
        _report_pending_jobs_on_shutdown(publisher, process_id)


def submit_shadow_job(operation: str, payload: tuple[dict, ...], *, max_jobs: int | str) -> bool:
    global _publisher, _publisher_pid

    process_id = os.getpid()
    with _publisher_lock:
        if _publisher is None or _publisher_pid != process_id:
            try:
                _publisher = AsyncShadowPublisher(max_jobs=max_jobs)
            except Exception:
                _log_initialize_failure(operation, process_id)
                return False
            _publisher_pid = process_id
        publisher = _publisher
    return publisher.submit(operation, payload)


try:
    from celery.signals import worker_process_shutdown

    worker_process_shutdown.connect(_report_current_process_pending_jobs, weak=False)
except ImportError:
    logger.warning(
        "[alarmd shadow] component=alarmd-python stage=async_publish result=coverage_gap "
        "operation=install_shutdown_signal reason=celery_unavailable"
    )
