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
import os

from django.apps import AppConfig, apps
from django.conf import settings
from django.db.models.signals import post_migrate


class FtaWebConfig(AppConfig):
    name = "fta_web"
    verbose_name = "fta_web"
    label = "fta_web"

    def ready(self):
        from .handlers import (
            migrate_fta_strategy,
            register_builtin_action_configs,
            register_builtin_plugins,
            register_global_event_plugin,
            rollover_es_indices,
        )

        # register saas version
        # run after bkmontior.ready()
        if getattr(settings, "REAL_FTA_SAAS_VERSION", None):
            GlobalConfig = apps.get_model("bkmonitor.GlobalConfig")
            GlobalConfig.objects.filter(key="FTA_SAAS_VERSION").update(value=settings.REAL_FTA_SAAS_VERSION)

        post_migrate.connect(rollover_es_indices, sender=self)
        if os.getenv("MIGRATE_ACTION_PLUGIN_ENABLED", "enabled") == "enabled":
            post_migrate.connect(register_builtin_plugins, sender=self)
            post_migrate.connect(register_builtin_action_configs, sender=self)
            post_migrate.connect(register_global_event_plugin, sender=self)
        if getattr(settings, "IS_FTA_MIGRATED", None) is False and settings.DATABASES.get("fta"):
            # 当未进行迁移且不存在
            post_migrate.connect(migrate_fta_strategy, sender=self)
            settings.IS_FTA_MIGRATED = True
