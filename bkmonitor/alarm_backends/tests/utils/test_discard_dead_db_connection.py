"""连接已死的数据库错误必须丢掉当前连接，语句错误和事务中的失败不能换连接。"""

import sqlite3
from unittest import TestCase

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        USE_TZ=False,
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    )
    django.setup()

from django.db import InterfaceError, OperationalError
from django.db.backends.sqlite3.base import DatabaseWrapper

from bkmonitor.utils.db_connection import install_discard_dead_db_connection


class RawConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class PooledConnection(RawConnection):
    def __init__(self):
        super().__init__()
        self.driver_connection = object()
        self.invalidated = False

    def invalidate(self):
        self.invalidated = True


def _wrapper():
    wrapper = DatabaseWrapper({"NAME": "unused.sqlite3", "AUTOCOMMIT": True, "CONN_HEALTH_CHECKS": False})
    wrapper.in_atomic_block = False
    wrapper.closed_in_transaction = False
    wrapper.needs_rollback = False
    return wrapper


class TestDiscardDeadDbConnection(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        install_discard_dead_db_connection()

    def test_lost_connection_is_discarded_and_error_propagates(self):
        wrapper = _wrapper()
        raw = RawConnection()
        wrapper.connection = raw

        with self.assertRaises(OperationalError):
            with wrapper.wrap_database_errors:
                raise sqlite3.OperationalError(2013, "Lost connection to MySQL server during query")

        self.assertIsNone(wrapper.connection)
        self.assertTrue(raw.closed)

    def test_statement_error_keeps_connection(self):
        wrapper = _wrapper()
        raw = RawConnection()
        wrapper.connection = raw

        with self.assertRaises(OperationalError):
            with wrapper.wrap_database_errors:
                raise sqlite3.OperationalError("database is locked")

        self.assertIs(wrapper.connection, raw)
        self.assertFalse(raw.closed)

    def test_interface_error_is_discarded(self):
        wrapper = _wrapper()
        raw = RawConnection()
        wrapper.connection = raw

        with self.assertRaises(InterfaceError):
            with wrapper.wrap_database_errors:
                raise sqlite3.InterfaceError("connection already closed")

        self.assertIsNone(wrapper.connection)
        self.assertTrue(raw.closed)

    def test_atomic_block_marks_rollback_without_swapping_connection(self):
        wrapper = _wrapper()
        wrapper.in_atomic_block = True
        raw = RawConnection()
        wrapper.connection = raw

        with self.assertRaises(OperationalError):
            with wrapper.wrap_database_errors:
                raise sqlite3.OperationalError(2006, "MySQL server has gone away")

        self.assertIs(wrapper.connection, raw)
        self.assertTrue(wrapper.needs_rollback)
        self.assertTrue(wrapper.closed_in_transaction)

    def test_pooled_connection_is_invalidated_before_close(self):
        wrapper = _wrapper()
        pooled = PooledConnection()
        wrapper.connection = pooled

        with self.assertRaises(OperationalError):
            with wrapper.wrap_database_errors:
                raise sqlite3.OperationalError(2055, "Lost connection")

        self.assertTrue(pooled.invalidated)
        self.assertTrue(pooled.closed)
        self.assertIsNone(wrapper.connection)

    def test_install_is_idempotent(self):
        from django.db.utils import DatabaseErrorWrapper

        wrapped = DatabaseErrorWrapper.__exit__
        install_discard_dead_db_connection()
        self.assertIs(DatabaseErrorWrapper.__exit__, wrapped)
