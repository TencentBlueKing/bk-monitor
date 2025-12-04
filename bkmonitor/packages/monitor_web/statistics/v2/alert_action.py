"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

import arrow
from django.conf import settings
from django.utils import translation
from django.utils.functional import cached_property
from elasticsearch_dsl import Q

from bkmonitor.documents import ActionInstanceDocument, AlertDocument
from bkmonitor.models import StrategyModel
from bkmonitor.utils.user import set_local_username
from constants.action import ActionPluginType, ActionStatus
from constants.alert import EVENT_SEVERITY_DICT
from core.drf_resource import resource
from core.statistics.metric import Metric, register
from fta_web.models.alert import SearchFavorite
from monitor_web.statistics.v2.base import TIME_RANGE, BaseCollector

logger = logging.getLogger(__name__)


class AlertActionCollector(BaseCollector):
    """
    告警事件
    """

    @cached_property
    def now(self):
        return arrow.now()

    @cached_property
    def biz_alert_data(self):
        all_data = {}
        set_local_username(settings.COMMON_USERNAME)
        for time_range, days in [("1d", 1), ("7d", 7), ("15d", 15), ("30d", 30)]:
            details = {}
            statistics = resource.home.statistics(page=0, days=days)["details"]
            for data in statistics:
                details[data["bk_biz_id"]] = data
            all_data[time_range] = details
        return all_data

    @register(labelnames=("bk_biz_id", "bk_biz_name", "status", "method", "time_range"))
    def action_notice_count(self, metric: Metric):
        """
        告警通知数
        """
        for le_en, seconds in TIME_RANGE:
            start_time = int(self.now.shift(seconds=-seconds).timestamp)
            search_object = (
                ActionInstanceDocument.search(start_time=start_time, end_time=int(self.now.timestamp))
                .filter("range", create_time={"gte": start_time, "lte": int(self.now.timestamp)})
                .filter("term", action_plugin_type=ActionPluginType.NOTICE)
                .exclude("term", is_parent_action=True)
            )
            search_object.aggs.bucket("bk_biz_id", "terms", field="bk_biz_id", size=10000).bucket(
                "method", "terms", field="operate_target_string", size=100
            ).bucket("status", "terms", field="status")

            search_result = search_object[:0].execute()
            if search_result.aggs:
                for biz_bucket in search_result.aggs.bk_biz_id.buckets:
                    for method_bucket in biz_bucket.method.buckets:
                        for status_bucket in method_bucket.status.buckets:
                            # 后台聚合逻辑，运营指标不关心
                            if status_bucket.key == ActionStatus.SKIPPED:
                                continue

                            metric.labels(
                                bk_biz_id=biz_bucket.key,
                                bk_biz_name=self.get_biz_name(biz_bucket.key),
                                method=method_bucket.key,
                                status=status_bucket.key,
                                time_range=le_en,
                            ).set(status_bucket.doc_count)

    @register(labelnames=("bk_biz_id", "bk_biz_name", "plugin_type", "status", "time_range"))
    def action_count(self, metric: Metric):
        """
        处理记录数
        """
        for le_en, seconds in TIME_RANGE:
            start_time = int(self.now.shift(seconds=-seconds).timestamp)
            search_object = (
                ActionInstanceDocument.search(start_time=start_time, end_time=int(self.now.timestamp))
                .filter("range", create_time={"gte": start_time, "lte": int(self.now.timestamp)})
                .exclude("term", is_parent_action=True)
            )

            search_object.aggs.bucket("bk_biz_id", "terms", field="bk_biz_id", size=10000).bucket(
                "action_plugin_type", "terms", field="action_plugin_type", size=100
            ).bucket("status", "terms", field="status")

            search_result = search_object[:0].execute()

            if search_result.aggs:
                for biz_bucket in search_result.aggs.bk_biz_id.buckets:
                    for action_bucket in biz_bucket.action_plugin_type.buckets:
                        for status_bucket in action_bucket.status.buckets:
                            metric.labels(
                                bk_biz_id=biz_bucket.key,
                                bk_biz_name=self.get_biz_name(biz_bucket.key),
                                plugin_type=action_bucket.key,
                                status=status_bucket.key,
                                time_range=le_en,
                            ).set(status_bucket.doc_count)

    @register(
        labelnames=(
            "bk_biz_id",
            "bk_biz_name",
            # "strategy_id",
            # "strategy_name",
            "severity",
            "stage",
            "status",
            "time_range",
        )
    )
    def alert_count(self, metric: Metric):
        """
        告警事件数
        """
        strategy_mapping = {}
        for strategy in StrategyModel.objects.values("id", "name"):
            strategy_mapping[strategy["id"]] = strategy

        for le_en, seconds in TIME_RANGE:
            start_time = int(self.now.shift(seconds=-seconds).timestamp)
            end_time = int(self.now.timestamp)
            search_object = AlertDocument.search(all_indices=True).filter(
                (Q("range", end_time={"gte": start_time}) | ~Q("exists", field="end_time"))
                & (Q("range", begin_time={"lte": end_time}) | Q("range", create_time={"lte": end_time}))
            )

            search_object.aggs.bucket("bk_biz_id", "terms", field="event.bk_biz_id", size=10000).bucket(
                "severity", "terms", field="severity", size=10000
            ).bucket("status", "terms", field="status", size=10000).bucket(
                "is_handled",
                "terms",
                field="is_handled",
                size=10000,
                missing=False,
            ).bucket(
                "is_ack",
                "terms",
                field="is_ack",
                size=10000,
                missing=False,
            ).bucket(
                "is_shielded",
                "terms",
                field="is_shielded",
                size=10000,
                missing=False,
            )

            search_result = search_object[:0].execute()
            if not search_result.aggs:
                return

            language = translation.get_language()
            translation.activate("en")
            try:
                self._generate_alert_count_metric(metric, search_result, le_en)
            except Exception as e:
                logger.error(f"generate alert count metric error: {e}")
            translation.activate(language)

    def _generate_alert_count_metric(self, metric: Metric, search_result, le_en: str):
        """
        生成告警事件数指标
        """
        for biz_bucket in search_result.aggs.bk_biz_id.buckets:
            for severity_bucket in biz_bucket.severity.buckets:
                for status_bucket in severity_bucket.status.buckets:
                    for is_handled_bucket in status_bucket.is_handled.buckets:
                        for is_ack_bucket in is_handled_bucket.is_ack.buckets:
                            for is_shielded_bucket in is_ack_bucket.is_shielded.buckets:
                                if is_handled_bucket.key:
                                    stage = "handled"
                                elif is_ack_bucket.key:
                                    stage = "ack"
                                elif is_shielded_bucket.key:
                                    stage = "shielded"
                                else:
                                    stage = "none"
                                metric.labels(
                                    bk_biz_id=biz_bucket.key,
                                    bk_biz_name=self.get_biz_name(biz_bucket.key),
                                    severity=EVENT_SEVERITY_DICT.get(severity_bucket.key, severity_bucket.key),
                                    stage=stage,
                                    status=status_bucket.key,
                                    time_range=le_en,
                                ).set(is_shielded_bucket.doc_count)

    @register(labelnames=("username", "search_type"))
    def search_favorite_item_count(self, metric: Metric):
        """
        搜索收藏数
        """
        items = SearchFavorite.objects.all()
        for item in items:
            metric.labels(username=item.create_user, search_type=item.search_type).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name", "time_range"))
    def mtta(self, metric: Metric):
        """
        MTTA
        """
        for day in ["1d", "7d", "15d", "30d"]:
            for bk_biz_id in self.biz_info.keys():
                overview_data = self.biz_alert_data[day].get(bk_biz_id)
                if not overview_data or overview_data["mtta"] is None:
                    continue
                metric.labels(bk_biz_id=bk_biz_id, bk_biz_name=self.get_biz_name(bk_biz_id), time_range=day).set(
                    overview_data["mtta"]
                )

    @register(labelnames=("bk_biz_id", "bk_biz_name", "time_range"))
    def mttr(self, metric: Metric):
        """
        MTTR
        """
        for day in ["1d", "7d", "15d", "30d"]:
            for bk_biz_id in self.biz_info.keys():
                overview_data = self.biz_alert_data[day].get(bk_biz_id)
                if not overview_data or overview_data["mttr"] is None:
                    continue
                metric.labels(bk_biz_id=bk_biz_id, bk_biz_name=self.get_biz_name(bk_biz_id), time_range=day).set(
                    overview_data["mttr"]
                )

    @register(labelnames=("bk_biz_id", "bk_biz_name", "time_range"))
    def auto_recovery_ratio(self, metric: Metric):
        """
        自愈率
        """
        for day in ["1d", "7d", "15d", "30d"]:
            for bk_biz_id in self.biz_info.keys():
                overview_data = self.biz_alert_data[day].get(bk_biz_id)
                if not overview_data or overview_data["auto_recovery_ratio"] is None:
                    continue
                metric.labels(bk_biz_id=bk_biz_id, bk_biz_name=self.get_biz_name(bk_biz_id), time_range=day).set(
                    overview_data["auto_recovery_ratio"]
                )

    @register(labelnames=("bk_biz_id", "bk_biz_name", "time_range"))
    def noise_reduction_ratio(self, metric: Metric):
        """
        降噪比
        """
        for day in ["1d", "7d", "15d", "30d"]:
            for bk_biz_id in self.biz_info.keys():
                overview_data = self.biz_alert_data[day].get(bk_biz_id)
                if not overview_data or overview_data["noise_reduction_ratio"] is None:
                    continue
                metric.labels(bk_biz_id=bk_biz_id, bk_biz_name=self.get_biz_name(bk_biz_id), time_range=day).set(
                    overview_data["noise_reduction_ratio"]
                )
