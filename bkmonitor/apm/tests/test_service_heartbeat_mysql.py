import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import Any

import pytest
from django.db import connections, transaction

pytest_plugins = ("apm.tests.test_service_heartbeat",)

from apm.models import TopoNode
from apm.tests.test_service_heartbeat import make_node


def require_mysql(alias: str) -> None:
    if connections[alias].vendor != "mysql":
        pytest.skip("设置 APM_HEARTBEAT_TEST_MYSQL_SOCKET 后，在隔离 MySQL 测试库验证行锁")


def test_mysql_concurrent_heartbeat_merges_preserve_both_sources(heartbeat_db: str) -> None:
    require_mysql(heartbeat_db)
    node = make_node()
    initial_updated_at = node.updated_at
    locked = Event()
    release = Event()

    def first_writer() -> None:
        try:
            with transaction.atomic(using=heartbeat_db):
                TopoNode.touch_heartbeat(2, "app", "trace", {"demo": 100}, 110)
                locked.set()
                assert release.wait(10)
        finally:
            connections[heartbeat_db].close()

    def second_writer() -> bool:
        try:
            assert locked.wait(5)
            return TopoNode.touch_heartbeat(2, "app", "metric", {"demo": 120}, 130)
        finally:
            connections[heartbeat_db].close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_writer)
        second = pool.submit(second_writer)
        try:
            assert locked.wait(5)
            deadline = time.monotonic() + 5
            waiting = False
            while time.monotonic() < deadline:
                with connections[heartbeat_db].cursor() as cursor:
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


def test_mysql_lock_timeout_keeps_previous_heartbeat(heartbeat_db: str) -> None:
    require_mysql(heartbeat_db)
    previous: dict[str, Any] = {"trace": {"last_data_at": 100, "checked_at": 110}}
    node = make_node(heartbeat=previous)

    def blocked_writer() -> bool:
        try:
            with connections[heartbeat_db].cursor() as cursor:
                cursor.execute("SET SESSION innodb_lock_wait_timeout = 1")
            return TopoNode.touch_heartbeat(2, "app", "log", {"demo": 200}, 210)
        finally:
            connections[heartbeat_db].close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic(using=heartbeat_db):
            TopoNode.objects.using(heartbeat_db).select_for_update().get(id=node.id)
            assert pool.submit(blocked_writer).result(timeout=5) is False
    node.refresh_from_db()
    assert node.heartbeat == previous
