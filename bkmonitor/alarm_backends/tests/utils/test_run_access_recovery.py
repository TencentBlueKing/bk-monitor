"""重启 access 主循环时，使用 Django 的真实错误标记与连接清理逻辑。"""

import sqlite3
from unittest import TestCase
from unittest.mock import Mock, patch

from django.db import close_old_connections
from django.db.backends.sqlite3.base import DatabaseWrapper

from alarm_backends.management.commands import run_access


class TestAccessConnectionRecovery(TestCase):
    def test_next_start_discards_failed_connection_before_dispatch(self):
        connection = DatabaseWrapper({"NAME": "unused.sqlite3", "AUTOCOMMIT": True, "CONN_HEALTH_CHECKS": False})
        failed_connection = Mock()
        connection.connection = failed_connection
        connection.autocommit = True
        connection.close_at = None
        connection.is_usable = Mock(return_value=False)
        command = object.__new__(run_access.Command)
        command.path_prefix = "access"
        command._HASH_RING_ = 1
        handler_cls = Mock()
        observed_connections = []

        def dispatch():
            observed_connections.append(connection.connection)
            if connection.connection is failed_connection:
                # 真实 DatabaseErrorWrapper 将驱动错误转为 Django 异常并标记连接。
                with connection.wrap_database_errors:
                    raise sqlite3.OperationalError("connection lost")
            return [], [1]

        command.dispatch = dispatch
        with (
            patch.object(run_access, "settings", ENVIRONMENT="production"),
            patch.object(run_access, "load_handler_cls", return_value=handler_cls),
            patch.object(run_access, "close_old_connections", wraps=close_old_connections),
            patch("django.db.connections.all", return_value=[connection]),
            patch.object(connection, "_close"),
            self.assertLogs(run_access.logger, level="ERROR"),
        ):
            command.on_start()
            self.assertTrue(connection.errors_occurred)
            command.on_start()

        self.assertEqual(observed_connections, [failed_connection, None])
        handler_cls.return_value.handle.assert_called_once_with()
