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
from django.utils.functional import cached_property
from monitor_web.statistics.v2.base import BaseCollector

from bkmonitor.models import Shield
from bkmonitor.utils import time_tools
from core.statistics.metric import Metric, register


class ShieldCollector(BaseCollector):
    """
    告警屏蔽
    """

    @cached_property
    def shield(self):
        return Shield.objects.filter(bk_biz_id__in=list(self.biz_info.keys()), failure_time__gt=time_tools.now())

    @register(labelnames=("bk_biz_id", "bk_biz_name", "category"))
    def shield_config_count(self, metric: Metric):
        """
        生效中的告警屏蔽配置数
        """
        for shield in self.shield:
            metric.labels(
                bk_biz_id=shield.bk_biz_id,
                bk_biz_name=self.get_biz_name(shield.bk_biz_id),
                category=shield.category,
            ).inc()
