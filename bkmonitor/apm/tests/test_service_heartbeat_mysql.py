import logging
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from typing import Any

import pytest
from django.db import connections, router, transaction

from apm.models import TopoNode
from apm.tests.test_service_heartbeat import make_node


pytestmark = pytest.mark.django_db(databases="__all__", transaction=True)


def test_mysql_concurrent_heartbeat_merges_preserve_both_sources() -> None:
    database = router.db_for_write(TopoNode)
    assert connections[database].vendor == "mysql", "并发与锁超时测试必须使用 MySQL"
    node = make_node()
    initial_updated_at = node.updated_at
    locked = Event()
    release = Event()

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
                    cursor.execute("SELECT COUNT(*) FROM performance_schema.data_lock_waits")
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
    assert node.updated_at == initial_updated_at


def test_mysql_lock_timeout_keeps_previous_heartbeat() -> None:
    database = router.db_for_write(TopoNode)
    assert connections[database].vendor == "mysql", "并发与锁超时测试必须使用 MySQL"
    previous: dict[str, Any] = {"trace": {"last_data_at": 100, "checked_at": 110}}
    node = make_node(heartbeat=previous)

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


def test_mysql_deadlock_keeps_victims_previous_heartbeat(caplog: pytest.LogCaptureFixture) -> None:
    database = router.db_for_write(TopoNode)
    assert connections[database].vendor == "mysql", "死锁测试必须使用 MySQL"
    previous = {"log": {"last_data_at": 80, "checked_at": 90}}
    first = make_node("first", heartbeat=previous)
    second = make_node("second", heartbeat=previous)
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


@pytest.mark.parametrize("data_type", ["trace", "metric"])
def test_mysql_discovery_waits_for_source_append_and_preserves_it(data_type: str) -> None:
    database = router.db_for_write(TopoNode)
    assert connections[database].vendor == "mysql"
    node = make_node(source=["trace"], heartbeat={"trace": {"last_data_at": 100, "checked_at": 110}})
    initial_heartbeat = node.heartbeat
    started = Event()

    def stale_writer() -> None:
        try:
            started.set()
            TopoNode.bulk_update_discovered_nodes(2, "app", [node], ["system"], data_type)
        finally:
            connections[database].close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic(using=database):
            TopoNode.upsert_telemetry_nodes(2, "app", "profiling", {"demo"}, {})
            pending = pool.submit(stale_writer)
            assert started.wait(5)
            deadline = time.monotonic() + 5
            waiting = False
            while time.monotonic() < deadline:
                with connections[database].cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM performance_schema.data_lock_waits")
                    waiting = cursor.fetchone()[0] > 0
                if waiting:
                    break
                time.sleep(0.02)
            assert waiting, "发现更新必须等待来源追加事务提交后再读取 source"
            assert not pending.done()
        pending.result(timeout=5)
    node.refresh_from_db()
    assert node.source == (["trace", "profiling"] if data_type == "trace" else ["trace", "profiling", "metric"])
    assert node.heartbeat == initial_heartbeat
