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
import socket
import sys

from django.apps import AppConfig, apps
from django.conf import settings
from django.db.models.signals import post_migrate

from bkmonitor.trace.log_trace import BluekingInstrumentor
from bkmonitor.utils.common_utils import get_local_ip
from bkmonitor.utils.dynamic_settings import hack_settings
from patches.bkoauth import patch_bkoauth_update_user_access_token


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

        # 注册iam migrate信号
        post_migrate.connect(_migrate_iam, sender=self, dispatch_uid="bkmonitor iam")
        # 调用自定义实现的patch_bkoauth方法，消除大量的MissingSchema异常堆栈，之所以在这里调用，是因为bkoauth的初始化依赖于Django的初始化
        post_migrate.connect(patch_bkoauth_update_user_access_token, sender=self, dispatch_uid="bkoauth")

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
                    import pyroscope

                    auth_token = os.getenv("BKAPP_CONTINUOUS_PROFILING_TOKEN") or os.getenv("BKAPP_OTLP_BK_DATA_TOKEN")
                    pyroscope.configure(
                        application_name=settings.SERVICE_NAME,
                        server_address=os.getenv("BKAPP_CONTINUOUS_PROFILING_ENDPOINT", ""),
                        tags={
                            "service.name": settings.SERVICE_NAME,
                            "service.version": settings.VERSION,
                            "service.environment": settings.ENVIRONMENT,
                            "net.host.ip": get_local_ip(),
                            "net.host.name": socket.gethostname(),
                        },
                        http_headers={
                            "X-BK-TOKEN": auth_token,
                        },
                    )
                except Exception as err:  # pylint: disable=broad-except
                    print("start continues profiling failed: %s" % err)


def _refresh_cache_node(sender, **kwargs):
    from bkmonitor.models import CacheNode

    CacheNode.refresh_from_settings()


def _migrate_iam(sender, **kwargs):
    if settings.SKIP_IAM_PERMISSION_CHECK:
        return

    from bkmonitor.migrate import Migrator

    if settings.RUN_MODE == "DEVELOP":
        return
    Migrator("iam", "bkmonitor.iam.migrations").migrate()
