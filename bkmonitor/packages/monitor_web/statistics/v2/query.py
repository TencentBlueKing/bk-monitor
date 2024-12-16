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

from django.conf import settings
from django.utils.functional import cached_property
from prometheus_client import Counter

from bkm_space.api import SpaceApi
from core.prometheus.base import OPERATION_REGISTRY
from core.statistics.metric import Metric, register
from monitor_web.models.data_explorer import QueryHistory
from monitor_web.statistics.v2.base import BaseCollector

logger = logging.getLogger(__name__)


class QueryCollector(BaseCollector):
    """
    检索采集器
    """

    @cached_property
    def search_favorites(self):
        return QueryHistory.objects.filter()

    @register(labelnames=("bk_biz_id", "bk_biz_name"))
    def event_query_star_count(self, metric: Metric):
        """事件检索收藏数"""
        for sf in self.search_favorites.filter(type="event"):
            metric.labels(
                bk_biz_id=sf.bk_biz_id,
                bk_biz_name=self.get_biz_name(sf.bk_biz_id),
            ).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name"))
    def metric_query_star_count(self, metric: Metric):
        """指标检索收藏数"""
        for sf in self.search_favorites.filter(type="time_series"):
            metric.labels(
                bk_biz_id=sf.bk_biz_id,
                bk_biz_name=self.get_biz_name(sf.bk_biz_id),
            ).inc()


EVENT_QUERY_COUNT = Counter(
    name="event_query_count",
    documentation="事件检索数",
    labelnames=("bk_biz_id", "bk_biz_name", "data_source_label", "job"),
    registry=OPERATION_REGISTRY,
)

METRIC_QUERY_COUNT = Counter(
    name="metric_query_count",
    documentation="指标检索数",
    labelnames=("bk_biz_id", "bk_biz_name", "data_source_label", "job"),
    registry=OPERATION_REGISTRY,
)

TRACE_QUERY_COUNT = Counter(
    name="trace_query_count",
    documentation="调用链检索数",
    labelnames=("bk_biz_id", "bk_biz_name", "app_name", "job"),
    registry=OPERATION_REGISTRY,
)

_data_type_label_map = {"time_series": METRIC_QUERY_COUNT, "event": EVENT_QUERY_COUNT, "trace": TRACE_QUERY_COUNT}


def unify_query_count(data_type_label: str, bk_biz_id: str, **labels):
    """unify query 查询运营打点"""
    try:
        space = SpaceApi.get_space_detail(bk_biz_id=bk_biz_id)
        biz_display_name = space.display_name
    except Exception:
        logger.exception("failed to get biz info, may cause incorrect label in metrics")
        biz_display_name = None

    metric = _data_type_label_map.get(data_type_label)
    if metric:
        metric.labels(
            bk_biz_id=bk_biz_id,
            # 当未获取到 biz name 时降级使用 biz_id
            bk_biz_name=biz_display_name or bk_biz_id,
            # Q: 为什么要在这里手动指定 job 而不是通过 push_to_gateway ?
            # A: 因为当前 push gateway 使用了 UDP 方式，而不是 HTTP，而原生方法 push_to_gateway 中的 job 又和具体协议绑定
            #    所以在这里手动添加 job label 实现类似效果
            job=settings.OPERATION_STATISTICS_METRIC_PUSH_JOB,
            **labels,
        ).inc()
