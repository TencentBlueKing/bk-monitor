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
import sys

from django.apps import AppConfig
from django.conf import settings
from django.core.management import call_command
from django.db import ProgrammingError, connections

from core.errors.errors import MigrateError


class MonitorAPIConfig(AppConfig):
    name = "monitor_api"
    verbose_name = "MonitorAPI"
    label = "monitor_api"

    def migrate(self):
        from bkmonitor.models import GlobalConfig
        from bkmonitor.utils.dynamic_settings import hack_settings

        try:
            call_command("migrate", "--noinput", database="monitor_api")
            hack_settings(GlobalConfig, settings)
            call_command("migrate", "--noinput")
        except MigrateError as err:
            print("Migrate Error:{}".format(err))
            raise err
        except Exception as e:
            print("Migrate Error:{}".format(e))
        # api migration end

    def check_external_db(self):
        """
        检查额外的db配置
        """
        for alias in ["nodeman"]:
            if alias not in settings.DATABASES:
                continue
            try:
                with connections[alias].cursor() as cursor:
                    cursor.execute("SELECT 1;")
            except Exception as e:
                print("db[{}] query error: {}".format(alias, e))
                # 如果操作失败，说明 DB 不存在，直接从 settings 中去掉
                settings.DATABASES.pop(alias, None)

    def ready(self):
        from bkmonitor.migrate import Migrator

        self.check_external_db()
        if "migrate" not in sys.argv:
            return

        if settings.MIGRATE_MONITOR_API:
            # 创建缓存表
            call_command("createcachetable", database="monitor_api")
            # 迁移DB
            self.migrate()
            # healthz指标自动更新
            # healthz_metric.run(apps)

        # 迁移IAM
        try:
            Migrator("iam", "bkmonitor.iam.migrations").migrate()
        except ProgrammingError:
            pass
