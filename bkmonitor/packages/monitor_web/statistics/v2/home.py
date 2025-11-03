"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.utils.functional import cached_property

from bkmonitor.models import HomeAlarmGraphConfig
from core.statistics.metric import Metric, register
from monitor_web.statistics.v2.base import BaseCollector


class HomeCollector(BaseCollector):
    """
    首页
    """

    @cached_property
    def home_alarm_graph_configs(self):
        return HomeAlarmGraphConfig.objects.filter(bk_biz_id__in=list(self.biz_info.keys()))

    @register(labelnames=("bk_biz_id", "username", "bk_biz_name"))
    def home_alarm_graph_count(self, metric: Metric):
        """
        某个用户配置的某个业务告警视图下有几个视图
        """

        for config in self.home_alarm_graph_configs:
            for _ in config.config:
                metric.labels(
                    bk_biz_id=config.bk_biz_id,
                    bk_biz_name=self.get_biz_name(config.bk_biz_id),
                    username=config.username,
                ).inc()
