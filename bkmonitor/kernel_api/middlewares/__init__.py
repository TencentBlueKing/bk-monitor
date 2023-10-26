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

import pytz
from django.conf import settings
from django.utils import timezone, translation
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class ApiTimeZoneMiddleware(MiddlewareMixin):
    """
    时区处理中间件
    """

    def process_request(self, request):
        tz_name = request.META.get("HTTP_BLUEKING_TIMEZONE", settings.TIME_ZONE)
        if tz_name:
            timezone.activate(pytz.timezone(tz_name))
        else:
            timezone.deactivate()


class ApiLanguageMiddleware(MiddlewareMixin):
    """
    语言处理中间件
    """

    @staticmethod
    def get_locale(language_code):
        if not language_code:
            # logger.info("get_locale: {}".format(settings.DEFAULT_LOCALE))
            return settings.DEFAULT_LOCALE

        if language_code.lower() in ["zh", "zh_cn", "zh-cn", "1", "zh-hans", "zh-hans-cn"]:
            locale = "zh_Hans_CN"
        else:
            locale = "en"

        # logger.info("get_locale: {}".format(locale))

        return locale

    def process_request(self, request):
        language_code = request.META.get("HTTP_BLUEKING_LANGUAGE")
        translation.activate(self.get_locale(language_code))
