"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from datetime import datetime

import arrow
from django.db.models import Count
from django.utils.functional import cached_property
from monitor_web.extend_account.constants import VisitSource
from monitor_web.extend_account.models import UserAccessRecord
from monitor_web.statistics.v2.base import TIME_RANGE, BaseCollector

from core.statistics.metric import Metric, register


class SiteCollector(BaseCollector):
    """站点指标采集器"""

    @cached_property
    def now(self):
        return arrow.now()

    @staticmethod
    def _get_extra_infos_by_visit_source(visit_source: VisitSource, start_from: datetime):
        return (
            UserAccessRecord.objects.filter(source=visit_source.value, updated_at__gt=start_from)
            .exclude(bk_biz_id="None")
            .values("bk_biz_id")
            .annotate(biz_count=Count("bk_biz_id"))
            .order_by()
        )

    @register(labelnames=("time_range", "bk_biz_id", "bk_biz_name"))
    def unique_visitor_pc_count(self, metric: Metric):
        """PC端访问用户数"""
        for le_en, seconds in TIME_RANGE:
            extra_infos = self._get_extra_infos_by_visit_source(
                VisitSource.PC, self.now.replace(seconds=-seconds).datetime
            )

            for info in extra_infos:
                bk_biz_id = info.get("bk_biz_id")
                # 旧数据未记录 bk_biz_id，-1 为标志位
                if bk_biz_id == "-1":
                    continue

                metric.labels(time_range=le_en, bk_biz_id=bk_biz_id, bk_biz_name=self.get_biz_name(bk_biz_id)).inc(
                    info.get("biz_count")
                )

    @register(labelnames=("time_range", "bk_biz_id", "bk_biz_name"))
    def unique_visitor_mobile_count(self, metric: Metric):
        """移动端访问用户数"""
        for le_en, seconds in TIME_RANGE:
            extra_infos = self._get_extra_infos_by_visit_source(
                VisitSource.MOBILE, self.now.replace(seconds=-seconds).datetime
            )

            for info in extra_infos:
                bk_biz_id = info.get("bk_biz_id")
                # 旧数据未记录 bk_biz_id，-1 为标志位
                if bk_biz_id == "-1":
                    continue

                metric.labels(time_range=le_en, bk_biz_id=bk_biz_id, bk_biz_name=self.get_biz_name(bk_biz_id)).inc(
                    info.get("biz_count")
                )
