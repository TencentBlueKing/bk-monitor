import logging
import threading
from unittest import mock

from alarm_backends.core.alarmd import async_publish
from alarm_backends.core.alarmd.encoder import encode_json_document


def test_shadow_job_size_from_payload_sizes_is_exact():
    payload = ({"batch_id": "one"}, {"batch_id": "two", "value": "三"})
    payload_sizes = tuple(len(encode_json_document(item)) for item in payload)

    assert async_publish.shadow_job_encoded_size_from_payload_sizes("reference", payload_sizes) == (
        async_publish.shadow_job_encoded_size("reference", payload)
    )


def test_async_publisher_is_bounded_and_fail_open():
    started = threading.Event()
    release = threading.Event()

    def run_job(job):
        started.set()
        release.wait(1)

    publisher = async_publish.AsyncShadowPublisher(max_jobs=1, run_job=run_job)
    with mock.patch.object(async_publish, "record_shadow_async_job"):
        try:
            assert publisher.submit("reference", ({"batch_id": "first"},))
            assert started.wait(1)
            assert publisher.submit("reference", ({"batch_id": "second"},))
            assert not publisher.submit("reference", ({"batch_id": "dropped"},))
        finally:
            release.set()
            publisher.close()


def test_async_publisher_accepts_numeric_string_queue_size():
    publisher = async_publish.AsyncShadowPublisher(max_jobs="16")

    assert publisher._queue.maxsize == 16


def test_async_publisher_rejects_unknown_operation():
    publisher = async_publish.AsyncShadowPublisher(max_jobs=1, run_job=mock.Mock())

    assert not publisher.submit("unknown", ({"batch_id": "one"},))


def test_async_publisher_continues_after_one_job_fails():
    completed = threading.Event()
    attempts = []

    def run_job(job):
        attempts.append(job.payload[0]["batch_id"])
        if len(attempts) == 1:
            raise RuntimeError("broker unavailable")
        completed.set()

    publisher = async_publish.AsyncShadowPublisher(max_jobs=2, run_job=run_job)
    with mock.patch.object(async_publish, "record_shadow_async_job") as record:
        try:
            assert publisher.submit("reference", ({"batch_id": "failed"},))
            assert publisher.submit("reference", ({"batch_id": "continued"},))
            assert completed.wait(1)
        finally:
            publisher.close()

    assert attempts == ["failed", "continued"]
    record.assert_any_call("reference", async_publish.ASYNC_STATUS_WORKER_FAILED)


def test_async_publisher_logs_terminal_ack(caplog):
    caplog.set_level(logging.INFO, logger="alarmd.shadow")
    completed = threading.Event()

    def run_job(_job):
        completed.set()
        return 3

    publisher = async_publish.AsyncShadowPublisher(max_jobs=1, run_job=run_job)
    try:
        assert publisher.submit("reference", ({"batch_id": "one"},))
        assert completed.wait(1)
    finally:
        publisher.close()

    assert "stage=reference result=broker_ack operation=async_worker records=3" in caplog.text


def test_async_publisher_rejects_a_job_over_the_full_payload_limit():
    run_job = mock.Mock()
    publisher = async_publish.AsyncShadowPublisher(max_jobs=1, run_job=run_job)
    with mock.patch.object(async_publish, "record_shadow_async_job") as record:
        assert not publisher.submit(
            "reference",
            ({"payload": "x" * async_publish.MAX_ASYNC_JOB_BYTES},),
        )

    run_job.assert_not_called()
    record.assert_called_once_with("reference", async_publish.ASYNC_STATUS_DROPPED)


def test_async_publisher_fails_open_when_payload_cannot_be_encoded():
    run_job = mock.Mock()
    publisher = async_publish.AsyncShadowPublisher(max_jobs=1, run_job=run_job)
    with mock.patch.object(async_publish, "record_shadow_async_job") as record:
        assert not publisher.submit("reference", ({"payload": object()},))

    run_job.assert_not_called()
    record.assert_called_once_with("reference", async_publish.ASYNC_STATUS_DROPPED)


def test_celery_process_shutdown_reports_pending_jobs(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="alarmd.shadow")
    publisher = mock.Mock()
    publisher.pending_jobs.return_value = 2
    monkeypatch.setattr(async_publish, "_publisher", publisher)
    monkeypatch.setattr(async_publish, "_publisher_pid", 100)
    monkeypatch.setattr(async_publish.os, "getpid", mock.Mock(return_value=100))

    async_publish._report_current_process_pending_jobs()

    assert "operation=process_exit pending_jobs=2" in caplog.text


def test_global_publisher_is_recreated_after_fork(monkeypatch):
    created = []

    class StubPublisher:
        def __init__(self, max_jobs):
            created.append(max_jobs)

        def submit(self, operation, payload):
            return True

    monkeypatch.setattr(async_publish, "AsyncShadowPublisher", StubPublisher)
    monkeypatch.setattr(async_publish, "_publisher", None)
    monkeypatch.setattr(async_publish, "_publisher_pid", None)
    monkeypatch.setattr(async_publish.os, "getpid", mock.Mock(side_effect=[100, 101]))
    assert async_publish.submit_shadow_job("reference", ({"batch_id": "one"},), max_jobs=3)
    assert async_publish.submit_shadow_job("reference", ({"batch_id": "two"},), max_jobs=3)
    assert created == [3, 3]


def test_submit_shadow_job_rate_limits_repeated_initialize_failure(monkeypatch, caplog):
    caplog.set_level(logging.ERROR, logger="alarmd.shadow")
    monkeypatch.setattr(async_publish, "_publisher", None)
    monkeypatch.setattr(async_publish, "_publisher_pid", None)
    monkeypatch.setattr(async_publish, "_last_initialize_failure_log", 0.0, raising=False)

    with mock.patch.object(async_publish.time, "monotonic", side_effect=[100.0, 101.0]):
        assert not async_publish.submit_shadow_job("reference", ({"batch_id": "one"},), max_jobs="invalid")
        assert not async_publish.submit_shadow_job("reference", ({"batch_id": "two"},), max_jobs="invalid")

    assert caplog.text.count("operation=async_initialize") == 1
