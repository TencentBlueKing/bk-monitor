"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import os
import time
from collections import defaultdict
from functools import wraps

import settings
from bkmonitor.utils.local import local

logger = logging.getLogger(__name__)

backend_db_apps = ["monitor_api", "metadata", "bkmonitor", "apm", "calendars"]

backend_alert_models = ["ActionInstance", "ConvergeInstance", "ConvergeRelation"]


def is_backend(app_label):
    return app_label in [app for app in backend_db_apps]


backend_router = "monitor_api"
if settings.BACKEND_DATABASE_NAME == "default":
    backend_alert_router = "default"
else:
    backend_alert_router = "backend_alert"


BK_MONITOR_MODULE = os.getenv("BK_MONITOR_MODULE", "default")

_table_visit_count_log_time: float = 0
_table_visit_count: dict[str, int] = defaultdict(int)


class BackendRouter:
    def db_for_read(self, model, **hints):
        # 动态路由判断
        if getattr(local, "DB_FOR_READ_OVERRIDE", []):
            return local.DB_FOR_READ_OVERRIDE[-1]
        if model._meta.object_name in backend_alert_models:
            return backend_alert_router
        if is_backend(model._meta.app_label):
            return backend_router
        if model._meta.app_label == "django_cache":
            return backend_router
        return None

    def db_for_write(self, model, **hints):
        # 动态路由判断
        if getattr(local, "DB_FOR_WRITE_OVERRIDE", []):
            return local.DB_FOR_WRITE_OVERRIDE[-1]
        if model._meta.object_name in backend_alert_models:
            return backend_alert_router
        if is_backend(model._meta.app_label):
            return backend_router
        if model._meta.app_label == "django_cache":
            return backend_router
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if is_backend(obj1._meta.app_label) and is_backend(obj2._meta.app_label):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # django_cache 应用总是允许迁移
        if app_label == "django_cache":
            return True

        # 防止后端应用在默认数据库中迁移
        if db == "default" and is_backend(app_label):
            return False

        # 后端告警路由数据库只允许告警相关模型迁移
        if db == backend_alert_router and model_name in backend_alert_models:
            return True

        # 后端路由数据库只允许后端应用迁移
        if db == backend_router:
            return is_backend(app_label)

        # 禁止在nodeman数据库中进行迁移
        if db in ["nodeman"]:
            return False

        # 对于其他情况，返回None让Django使用默认行为
        return None


class TableVisitCountRouter:
    def db_for_read(self, model, **hints):
        global _table_visit_count_log_time, _table_visit_count

        # 每分钟打印一次表访问次数
        now = time.time()
        if _table_visit_count_log_time < now - 60:
            _table_visit_count_log_time = now
            logger.info(f"table_visit_count: count: {json.dumps(_table_visit_count)}, module: {BK_MONITOR_MODULE}")

        # 记录表访问次数
        _table_visit_count[model.__name__] += 1
        return None

    def db_for_write(self, model, **hints):
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return None


class UsingDB:
    """A decorator and context manager to do queries on a given database.
    Usage as a context manager:
    .. code-block:: python
        from my_django_app.utils import tricky_query
        with using_db('Database_A'):
            results = tricky_query()
    Usage as a decorator:
    .. code-block:: python
        from my_django_app.models import Account


        @using_db("Database_B")
        def lowest_id_account():
            Account.objects.order_by("-id")[0]
    """

    def __init__(self, database):
        self.database = database

    def __enter__(self):
        if not hasattr(local, "DB_FOR_READ_OVERRIDE"):
            local.DB_FOR_READ_OVERRIDE = []
        if not hasattr(local, "DB_FOR_WRITE_OVERRIDE"):
            local.DB_FOR_WRITE_OVERRIDE = []
        local.DB_FOR_READ_OVERRIDE.append(self.database)
        local.DB_FOR_WRITE_OVERRIDE.append(self.database)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        local.DB_FOR_READ_OVERRIDE.pop()
        local.DB_FOR_WRITE_OVERRIDE.pop()

    def __call__(self, querying_func):
        @wraps(querying_func)
        def inner(*args, **kwargs):
            # Call the function in our context manager
            with self:
                return querying_func(*args, **kwargs)

        return inner


using_db = UsingDB
