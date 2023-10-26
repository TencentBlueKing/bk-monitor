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

from django.core.management.base import BaseCommand

from metadata import models


class Command(BaseCommand):
    help = "remove repeated target dimension"

    def handle(self, *args, **options):
        """移除操作
        包含下面两个:
            - TimeSeriesMetric
            - Event
        """
        # 去除 TimeSeriesMetric 中重复的维度
        for obj in models.TimeSeriesMetric.objects.all():
            obj.tag_list = list(set(obj.tag_list))
            obj.save(update_fields=["tag_list"])

        self.stdout.write("models: TimeSeriesMetric has removed target dimension")

        # 去除 Event 中重复维度
        for obj in models.Event.objects.all():
            obj.dimension_list = list(set(obj.dimension_list))
            obj.save(update_fields=["dimension_list"])

        self.stdout.write("models: event has removed target dimension")
