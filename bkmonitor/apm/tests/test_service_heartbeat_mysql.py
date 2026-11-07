import logging
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from typing import Any
from unittest import mock

import pytest
from django.db import connections, router, transaction

from apm.models import TopoNode
from apm.tests.test_service_heartbeat import make_node


pytestmark = pytest.mark.django_db(databases="__all__", transaction=True)


def test_mysql_concurrent_heartbeat_merges_preserve_both_data_types() -> None:
    database = router.db_for_write(TopoNode)
    assert connections[database].vendor == "mysql", "并发与锁超时测试必须使用 MySQL"
    node = make_node(source=["log"])
    initial_updated_at = node.updated_at
    locked = Event()
    release = Event()
    writer_connections: list[int] = []

    def first_writer() -> None:
        try:
            with transaction.atomic(using=database):
                TopoNode.touch_heartbeat(2, "app", "trace", {"demo": 100}, 110)
                locked.set()
                assert release.wait(10)
        finally:
            connections[database].close()

    def second_writer() -> bool:
        try:
            assert locked.wait(5)
            with connections[database].cursor() as cursor:
                cursor.execute("SELECT CONNECTION_ID()")
                writer_connections.append(cursor.fetchone()[0])
            return TopoNode.touch_heartbeat(2, "app", "metric", {"demo": 120}, 130)
        finally:
            connections[database].close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_writer)
        second = pool.submit(second_writer)
        try:
            assert locked.wait(5)
            deadline = time.monotonic() + 5
            waiting = False
            while time.monotonic() < deadline:
                with connections[database].cursor() as cursor:
                    cursor.execute(
                        "SELECT COUNT(*) FROM performance_schema.data_lock_waits w "
                        "JOIN performance_schema.threads t ON t.THREAD_ID = w.REQUESTING_THREAD_ID "
                        "WHERE t.PROCESSLIST_ID = %s",
                        [writer_connections[0] if writer_connections else 0],
                    )
                    waiting = cursor.fetchone()[0] > 0
                if waiting:
                    break
                time.sleep(0.02)
            assert waiting, "第二个写入者必须实际等待 MySQL 行锁"
            assert not second.done()
        finally:
            release.set()
        first.result(timeout=5)
        assert second.result(timeout=5)
    node.refresh_from_db()
    assert node.heartbeat == {
        "trace": {"last_data_at": 100, "checked_at": 110},
        "metric": {"last_data_at": 120, "checked_at": 130},
    }
    assert node.source == ["log", "trace", "metric"]
    assert node.updated_at == initial_updated_at


def test_mysql_lock_timeout_keeps_previous_heartbeat() -> None:
    database = router.db_for_write(TopoNode)
    assert connections[database].vendor == "mysql", "并发与锁超时测试必须使用 MySQL"
    previous: dict[str, Any] = {"trace": {"last_data_at": 100, "checked_at": 110}}
    node = make_node(source=["trace"], heartbeat=previous)

    def blocked_writer() -> bool:
        try:
            with connections[database].cursor() as cursor:
                cursor.execute("SET SESSION innodb_lock_wait_timeout = 1")
            return TopoNode.touch_heartbeat(2, "app", "log", {"demo": 200}, 210)
        finally:
            connections[database].close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic(using=database):
            TopoNode.objects.using(database).select_for_update().get(id=node.id)
            assert pool.submit(blocked_writer).result(timeout=5) is False
    node.refresh_from_db()
    assert node.heartbeat == previous
    assert node.source == ["trace"]
    assert TopoNode.touch_heartbeat(2, "app", "log", {"demo": 200}, 210)
    node.refresh_from_db()
    assert node.heartbeat["log"] == {"last_data_at": 200, "checked_at": 210}
    assert node.source == ["trace", "log"]


def test_mysql_lock_timeout_retries_original_observation_after_lock_release() -> None:
    database = router.db_for_write(TopoNode)
    assert connections[database].vendor == "mysql", "锁冲突重试测试必须使用 MySQL"
    node = make_node("service-a", source=["trace"], heartbeat={"trace": {"last_data_at": 100, "checked_at": 110}})
    updated_at = node.updated_at
    retry_ready = Event()
    lock_released = Event()
    session_timeouts: list[int] = []

    def wait_for_lock_release(delay: float) -> None:
        assert not connections[database].in_atomic_block
        with connections[database].cursor() as cursor:
            cursor.execute("SELECT @@SESSION.innodb_lock_wait_timeout")
            assert cursor.fetchone()[0] == 2
        retry_ready.set()
        assert lock_released.wait(5)

    def blocked_writer() -> bool:
        try:
            with connections[database].cursor() as cursor:
                cursor.execute("SET SESSION innodb_lock_wait_timeout = 2")
                cursor.execute("SELECT @@SESSION.innodb_lock_wait_timeout")
                session_timeouts.append(cursor.fetchone()[0])
            succeeded = TopoNode.touch_heartbeat(2, "app", "log", {"service-a": 200}, 210)
            with connections[database].cursor() as cursor:
                cursor.execute("SELECT @@SESSION.innodb_lock_wait_timeout")
                session_timeouts.append(cursor.fetchone()[0])
            return succeeded
        finally:
            connections[database].close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with mock.patch("apm.models.topo.time.sleep", side_effect=wait_for_lock_release) as sleep:
            try:
                with transaction.atomic(using=database):
                    TopoNode.objects.using(database).select_for_update().get(id=node.id)
                    writer = pool.submit(blocked_writer)
                    assert retry_ready.wait(8), "第一次真实锁超时后必须进入事务外重试"
                    TopoNode.objects.using(database).filter(id=node.id).update(
                        heartbeat={"trace": {"last_data_at": 150, "checked_at": 160}}
                    )
            finally:
                lock_released.set()
            assert writer.result(timeout=5)
            sleep.assert_called_once()
    node.refresh_from_db()
    assert node.heartbeat == {
        "trace": {"last_data_at": 150, "checked_at": 160},
        "log": {"last_data_at": 200, "checked_at": 210},
    }
    assert node.source == ["trace", "log"]
    assert node.updated_at == updated_at
    assert session_timeouts == [2, 2]


def test_mysql_exhausted_lock_retries_keep_session_timeout_unchanged() -> None:
    database = router.db_for_write(TopoNode)
    assert connections[database].vendor == "mysql", "锁冲突重试测试必须使用 MySQL"
    previous = {"metric": {"last_data_at": 100, "checked_at": 110}}
    node = make_node("service-a", source=["metric"], heartbeat=previous)
    session_timeouts: list[int] = []

    def blocked_writer() -> bool:
        try:
            with connections[database].cursor() as cursor:
                cursor.execute("SET SESSION innodb_lock_wait_timeout = 2")
                cursor.execute("SELECT @@SESSION.innodb_lock_wait_timeout")
                session_timeouts.append(cursor.fetchone()[0])
            succeeded = TopoNode.touch_heartbeat(2, "app", "log", {"service-a": 200}, 210)
            with connections[database].cursor() as cursor:
                cursor.execute("SELECT @@SESSION.innodb_lock_wait_timeout")
                session_timeouts.append(cursor.fetchone()[0])
            return succeeded
        finally:
            connections[database].close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic(using=database):
            TopoNode.objects.using(database).select_for_update().get(id=node.id)
            assert pool.submit(blocked_writer).result(timeout=10) is False
    node.refresh_from_db()
    assert node.heartbeat == previous
    assert node.source == ["metric"]
    assert session_timeouts == [2, 2]


def test_mysql_deadlock_keeps_victims_previous_heartbeat(caplog: pytest.LogCaptureFixture) -> None:
    database = router.db_for_write(TopoNode)
    assert connections[database].vendor == "mysql", "死锁测试必须使用 MySQL"
    previous = {"log": {"last_data_at": 80, "checked_at": 90}}
    first = make_node("first", source=["log"], heartbeat=previous)
    second = make_node("second", source=["log"], heartbeat=previous)
    both_locked = Barrier(2, timeout=5)
    caplog.set_level(logging.WARNING, logger="apm")

    def update_other(locked_id: int, target_name: str) -> bool:
        try:
            with connections[database].cursor() as cursor:
                cursor.execute("SET SESSION innodb_lock_wait_timeout = 3")
            with transaction.atomic(using=database):
                TopoNode.objects.using(database).select_for_update().get(id=locked_id)
                both_locked.wait()
                return TopoNode.touch_heartbeat(2, "app", "trace", {target_name: 100}, 110)
        finally:
            connections[database].close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        writers = [pool.submit(update_other, first.id, "second"), pool.submit(update_other, second.id, "first")]
        results = [writer.result(timeout=10) for writer in writers]
    assert sorted(results) == [False, True]
    assert "errno=1213" in caplog.text
    for target, succeeded in zip((second, first), results):
        target.refresh_from_db()
        expected = dict(previous)
        if succeeded:
            expected["trace"] = {"last_data_at": 100, "checked_at": 110}
        assert target.heartbeat == expected
        assert target.source == (["log", "trace"] if succeeded else ["log"])
