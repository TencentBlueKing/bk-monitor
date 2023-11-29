# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


from functools import wraps

from bkmonitor.utils.local import local

backend_db_apps = ["monitor_api", "bkmonitor", "apm", "calendars"]


def is_backend(app_label):
    return app_label in [app for app in backend_db_apps]


backend_router = "monitor_api"


class BackendRouter(object):
    def db_for_read(self, model, **hints):
        # 动态路由判断
        if getattr(local, "DB_FOR_READ_OVERRIDE", []):
            return local.DB_FOR_READ_OVERRIDE[-1]

        if is_backend(model._meta.app_label):
            return backend_router
        if model._meta.app_label == "django_cache":
            return "monitor_api"
        return None

    def db_for_write(self, model, **hints):
        # 动态路由判断
        if getattr(local, "DB_FOR_WRITE_OVERRIDE", []):
            return local.DB_FOR_WRITE_OVERRIDE[-1]

        if is_backend(model._meta.app_label):
            return backend_router
        if model._meta.app_label == "django_cache":
            return "monitor_api"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if is_backend(obj1._meta.app_label) and is_backend(obj2._meta.app_label):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == "django_cache":
            return True
        if db == "default" and is_backend(app_label):
            return False
        if db == backend_router:
            return is_backend(app_label)
        if db in ["nodeman"]:
            return False


class UsingDB(object):
    """A decorator and context manager to do queries on a given database.
    Usage as a context manager:
    .. code-block:: python
        from my_django_app.utils import tricky_query
        with using_db('Database_A'):
            results = tricky_query()
    Usage as a decorator:
    .. code-block:: python
        from my_django_app.models import Account
        @using_db('Database_B')
        def lowest_id_account():
            Account.objects.order_by('-id')[0]
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
