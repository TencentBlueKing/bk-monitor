import logging
import threading
from unittest import mock

from alarm_backends.core.alarmd import async_publish


def test_async_publisher_is_bounded_and_fail_open():
    started = threading.Event()
    release = threading.Event()

    def run_job(job):
        started.set()
        release.wait(1)

    publisher = async_publish.AsyncShadowPublisher(max_jobs=1, run_job=run_job)
    with mock.patch.object(async_publish, "record_shadow_async_job"):
        try:
            assert publisher.submit("detect_input", ({"batch_id": "first"},))
            assert started.wait(1)
            assert publisher.submit("detect_input", ({"batch_id": "second"},))
            assert not publisher.submit("detect_input", ({"batch_id": "dropped"},))
        finally:
            release.set()
            publisher.close()


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
        assert publisher.submit("detect_input", ({"batch_id": "one"},))
        assert completed.wait(1)
    finally:
        publisher.close()

    assert "stage=detect_input result=broker_ack operation=async_worker records=3" in caplog.text


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
    monkeypatch.setattr(async_publish.atexit, "register", mock.Mock())

    assert async_publish.submit_shadow_job("detect_input", ({"batch_id": "one"},), max_jobs=3)
    assert async_publish.submit_shadow_job("detect_input", ({"batch_id": "two"},), max_jobs=3)
    assert created == [3, 3]
