"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# 会话已经不存在。下一次查询必须换新连接，不能沿用当前句柄。
_DEAD_SESSION_ERRNOS = frozenset(
    {
        2006,  # CR_SERVER_GONE_ERROR
        2013,  # CR_SERVER_LOST
        2055,  # CR_SERVER_LOST_EXTENDED
    }
)

_installed = False


def install_discard_dead_db_connection():
    """连接已死时，在异常冒泡前丢掉该连接。

    Django 对这类错误只设置 errors_occurred，要等请求或任务边界上的
    close_old_connections() 才真正关闭。调用方接住异常并继续查库时，会复用
    同一条坏连接。这里包住所有后端共用的 DatabaseErrorWrapper，事务中的失败
    仍交给 Django 的 close() 标成需要回滚，避免中途换连接把半成品事务写完。
    """
    global _installed
    if _installed:
        return

    from django.db.utils import DatabaseErrorWrapper

    original_exit = DatabaseErrorWrapper.__exit__

    def __exit__(self, exc_type, exc_value, traceback):
        discard = exc_type is not None and _is_dead_connection_error(self.wrapper, exc_type, exc_value)
        try:
            return original_exit(self, exc_type, exc_value, traceback)
        finally:
            if discard:
                _discard_dead_connection(self.wrapper)

    DatabaseErrorWrapper.__exit__ = __exit__
    _installed = True


def _is_dead_connection_error(wrapper, exc_type, exc_value):
    database = wrapper.Database
    interface_error = getattr(database, "InterfaceError", ())
    if isinstance(interface_error, type) and issubclass(exc_type, interface_error):
        return True
    operational_error = getattr(database, "OperationalError", ())
    if not isinstance(operational_error, type) or not issubclass(exc_type, operational_error):
        return False
    args = getattr(exc_value, "args", ())
    return bool(args) and isinstance(args[0], int) and args[0] in _DEAD_SESSION_ERRNOS


def _discard_dead_connection(wrapper):
    if getattr(wrapper, "_discarding_dead_connection", False) or wrapper.connection is None:
        return
    wrapper._discarding_dead_connection = True
    try:
        connection = wrapper.connection
        invalidate = getattr(connection, "invalidate", None)
        # 连接池取出的句柄要先作废，再 close；否则 close 会把坏连接还回池里。
        if callable(invalidate) and hasattr(connection, "driver_connection"):
            try:
                invalidate()
            except Exception:
                pass
        try:
            wrapper.close()
        except Exception:
            if not wrapper.in_atomic_block and wrapper.connection is connection:
                wrapper.connection = None
    finally:
        wrapper._discarding_dead_connection = False
