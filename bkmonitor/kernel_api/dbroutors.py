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

from django.conf import settings


class KernelAPIRouter(object):
    routers = {"monitor_api": settings.BACKEND_DATABASE_NAME, "metadata": settings.BACKEND_DATABASE_NAME}

    def db_for_read(self, model, **hints):
        return self.routers.get(model._meta.app_label, "default")

    def db_for_write(self, model, **hints):
        return self.routers.get(model._meta.app_label, "default")

    def allow_relation(self, obj1, obj2, **hints):
        db1 = self.routers.get(obj1._meta.app_label, "default")
        db2 = self.routers.get(obj2._meta.app_label, "default")
        return db1 == db2

    def allow_migrate(self, db, app_label, model_name=None, model=None, **hints):
        return app_label not in self.routers
