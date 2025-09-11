# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
"""
监控SaaS配置初始化，所有的初始化集中在此文件处理
"""


from django.apps import AppConfig
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.db import models

from bkmonitor.utils.cache import UsingCache
from bkmonitor.views import serializers
from bkmonitor.views.fields import DateTimeField


class MonitorConfig(AppConfig):
    name = "monitor"
    verbose_name = "Monitor"
    label = "monitor"

    def ready(self):
        self.clear_cache()

        # change serializer_field_mapping in ModelSerializer of rest_framework
        serializers.ModelSerializer.serializer_field_mapping[models.DateTimeField] = DateTimeField

    def clear_cache(self):
        """
        启动时清空缓存
        """
        if settings.CLEAR_CACHE_ON_RESTART:
            try:
                if hasattr(cache, "delete_pattern"):
                    # 只删除using_cache相关的web缓存
                    cache.delete_pattern("%s*" % UsingCache.key_prefix)
                else:
                    cache.clear()
            except Exception:
                # 异常有可能是因为尚未创建缓存表，尝试创建
                call_command("createcachetable")
