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
import sys

from django.apps import AppConfig, apps
from django.conf import settings
from django.db.models.signals import post_migrate

from bkmonitor.trace.log_trace import BluekingInstrumentor
from bkmonitor.utils.dynamic_settings import hack_settings


class Config(AppConfig):
    name = "bkmonitor"
    verbose_name = "bkmonitor"
    label = "bkmonitor"

    def ready(self):
        # 动态配置库自动更新
        from bkmonitor.define import global_config
        from bkmonitor.models import CacheNode, GlobalConfig

        global_config.run(apps)

        # 检测是否运行测试（python manage.py test 或 pytest）
        if "test" in sys.argv or "pytest" in sys.modules and settings.ROLE != "worker":
            hack_settings(GlobalConfig, settings)
            if settings.ROLE == "worker":
                post_migrate.connect(_refresh_cache_node, sender=self, dispatch_uid="bkmonitor test")
        elif "migrate" not in sys.argv:
            hack_settings(GlobalConfig, settings)
            if settings.ROLE == "worker":
                CacheNode.refresh_from_settings()

        if os.getenv("BK_MONITOR_UNIFY_QUERY_HOST"):
            settings.UNIFY_QUERY_URL = (
                f"http://{os.getenv('BK_MONITOR_UNIFY_QUERY_HOST')}:{os.getenv('BK_MONITOR_UNIFY_QUERY_PORT')}/"
            )
        if "celery" in sys.argv:
            # celery 初始化，使用worker_process_init信号
            return
        if os.getenv("BKAPP_OTLP_HTTP_HOST") and (
            os.getenv("BKAPP_OTLP_BK_DATA_ID") or os.getenv("BKAPP_OTLP_BK_DATA_TOKEN")
        ):
            BluekingInstrumentor().instrument()
            # continues profiling support, only enabled in web service
            if os.environ.get("BKAPP_CONTINUOUS_PROFILING_ENABLED", False) and settings.ROLE == "web":
                # those data collecting may cause 2-5% overhead
                # enabling manually is a safer way to do in production
                try:
                    from ddtrace.profiling.profiler import Profiler

                    from bkmonitor.profiling import patch_ddtrace_to_pyroscope

                    patch_ddtrace_to_pyroscope()
                    prof = Profiler()
                    prof.start()

                except Exception as err:  # pylint: disable=broad-except
                    print("start continues profiling failed: %s" % err)


def _refresh_cache_node(sender, **kwargs):
    from bkmonitor.models import CacheNode

    CacheNode.refresh_from_settings()
