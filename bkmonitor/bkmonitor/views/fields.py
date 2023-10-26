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
from django.utils import timezone
from rest_framework import serializers

from bkmonitor.utils import time_tools


class DateTimeField(serializers.DateTimeField):
    def to_representation(self, value):
        return time_tools.strftime_local(value)

    def default_timezone(self):
        return timezone.get_current_timezone() if settings.USE_TZ else None


class ToListField(serializers.ListField):
    def to_internal_value(self, data):
        if isinstance(data, list):
            data = [data]
        return data
