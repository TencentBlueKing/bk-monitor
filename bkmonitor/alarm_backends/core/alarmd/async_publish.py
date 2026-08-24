"""Process-local bounded publisher for fail-open alarmd Shadow jobs."""

import atexit
import logging
import os
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger("alarmd.shadow")

ASYNC_STATUS_ENQUEUED = "enqueued"
ASYNC_STATUS_DROPPED = "dropped"
ASYNC_STATUS_WORKER_FAILED = "worker_failed"
ASYNC_STATUS_ACKED = "acked"

_DROP_LOG_INTERVAL_SECONDS = 30
_STOP = object()


@dataclass(frozen=True)
class ShadowPublishJob:
    operation: str
    payload: tuple[dict, ...]


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
    def __init__(self, *, max_jobs: int, run_job: Callable[[ShadowPublishJob], int] = _run_shadow_job):
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
        self._ensure_started()
        job = ShadowPublishJob(operation=operation, payload=payload)
        try:
            self._queue.put_nowait(job)
        except queue.Full:
            record_shadow_async_job(operation, ASYNC_STATUS_DROPPED)
            self._log_drop(operation)
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

    def _log_drop(self, operation: str) -> None:
        now = time.monotonic()
        if now - self._last_drop_log < _DROP_LOG_INTERVAL_SECONDS:
            return
        self._last_drop_log = now
        logger.warning(
            "[alarmd shadow] component=alarmd-python stage=%s result=fail_open "
            "operation=async_enqueue reason=queue_full",
            operation,
        )


_publisher_lock = threading.Lock()
_publisher = None
_publisher_pid = None


def _report_pending_jobs_at_exit(publisher: AsyncShadowPublisher, process_id: int) -> None:
    if os.getpid() != process_id:
        return
    pending = publisher.pending_jobs()
    if pending:
        logger.warning(
            "[alarmd shadow] component=alarmd-python stage=async_publish result=coverage_gap "
            "operation=process_exit pending_jobs=%s",
            pending,
        )


def submit_shadow_job(operation: str, payload: tuple[dict, ...], *, max_jobs: int) -> bool:
    global _publisher, _publisher_pid

    process_id = os.getpid()
    with _publisher_lock:
        if _publisher is None or _publisher_pid != process_id:
            try:
                _publisher = AsyncShadowPublisher(max_jobs=max_jobs)
            except Exception:
                logger.exception(
                    "[alarmd shadow] component=alarmd-python stage=%s result=fail_open operation=async_initialize",
                    operation,
                )
                return False
            _publisher_pid = process_id
            atexit.register(_report_pending_jobs_at_exit, _publisher, process_id)
        publisher = _publisher
    return publisher.submit(operation, payload)
