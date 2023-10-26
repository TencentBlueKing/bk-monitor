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
import logging

from blueapps.middleware.xss.decorators import escape_exempt
from django.apps import AppConfig, apps
from django.conf import settings


def escape_xss():
    from blueapps.account import views

    views.login_page = escape_exempt(views.login_page)


class MonitorWebConfig(AppConfig):
    name = "monitor_web"
    verbose_name = "monitor_web"
    label = "monitor_web"

    def ready(self):
        try:
            # register saas version
            # run after bkmontior.ready()
            if settings.REAL_SAAS_VERSION:
                GlobalConfig = apps.get_model("bkmonitor.GlobalConfig")
                GlobalConfig.objects.filter(key="SAAS_VERSION").update(value=settings.REAL_SAAS_VERSION)
            # register web app code & secret key for api
            if settings.ROLE == "web":
                settings.SAAS_APP_CODE = settings.APP_CODE
                settings.SAAS_SECRET_KEY = settings.SECRET_KEY
                # fix login url with xss encode
                escape_xss()
        except Exception as e:
            logging.warning(e)
