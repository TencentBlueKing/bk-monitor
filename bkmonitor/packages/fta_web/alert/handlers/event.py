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
from typing import Dict, List

from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy as _lazy

from bkmonitor.documents import EventDocument
from constants.alert import EVENT_SEVERITY, EVENT_STATUS, EVENT_TARGET_TYPE
from constants.data_source import DATA_SOURCE_LABEL_CHOICE
from fta_web.alert.handlers.base import (
    BaseQueryHandler,
    BaseQueryTransformer,
    QueryField,
)
from fta_web.alert.handlers.translator import (
    AbstractTranslator,
    CategoryTranslator,
    StrategyTranslator,
)


class EventQueryTransformer(BaseQueryTransformer):
    NESTED_KV_FIELDS = {"tags": "tags"}
    VALUE_TRANSLATE_FIELDS = {
        "severity": EVENT_SEVERITY,
        "status": EVENT_STATUS,
        "target_type": EVENT_TARGET_TYPE,
        "data_type": DATA_SOURCE_LABEL_CHOICE,
    }
    query_fields = [
        QueryField("id", _lazy("全局事件ID")),
        QueryField("event_id", _lazy("事件ID")),
        QueryField("plugin_id", _lazy("插件ID")),
        QueryField("alert_name", _lazy("告警名称"), agg_field="alert_name.raw"),
        QueryField("status", _lazy("状态")),
        QueryField("description", _lazy("描述")),
        QueryField("severity", _lazy("级别")),
        QueryField("metric", _lazy("指标ID")),
        QueryField("bk_biz_id", _lazy("业务ID")),
        QueryField("assignee", _lazy("负责人")),
        QueryField("strategy_id", _lazy("策略ID")),
        QueryField("time", _lazy("事件时间")),
        QueryField("bk_ingest_time", _lazy("采集时间")),
        QueryField("anomaly_time", _lazy("异常时间")),
        QueryField("create_time", _lazy("入库时间")),
        QueryField("target_type", _lazy("目标类型")),
        QueryField("target", _lazy("目标")),
        QueryField("category", _lazy("分类")),
        QueryField("tags", _lazy("标签")),
        QueryField("ip", _lazy("目标IP")),
        QueryField("bk_cloud_id", _lazy("目标云区域ID")),
        QueryField("bk_service_instance_id", _lazy("目标服务实例ID")),
        QueryField("data_type", _lazy("数据类型")),
        QueryField("bk_topo_node", _lazy("目标节点")),
    ]
    doc_cls = EventDocument


class EventQueryHandler(BaseQueryHandler):
    """
    事件查询
    """

    query_transformer = EventQueryTransformer

    def __init__(self, dedupe_md5: str = "", **kwargs):
        super(EventQueryHandler, self).__init__(**kwargs)
        self.dedupe_md5 = dedupe_md5

        if not self.ordering:
            # 默认排序
            self.ordering = ["-time"]

    def get_search_object(self):
        search_object = EventDocument.search(all_indices=True).filter(
            "range", time={"gte": self.start_time, "lte": self.end_time}
        )

        if self.dedupe_md5:
            search_object = search_object.filter("term", dedupe_md5=self.dedupe_md5)

        return search_object

    def search(self, show_dsl=False):
        search_object = self.get_search_object()
        search_object = self.add_conditions(search_object)
        search_object = self.add_query_string(search_object)
        search_object = self.add_ordering(search_object)
        search_object = self.add_pagination(search_object)

        if show_dsl:
            return {"dsl": search_object.to_dict()}

        search_result = search_object.execute()
        events = self.handle_hit_list(search_result.hits)

        result = {
            "total": min(search_result.hits.total.value, 10000),
            "events": events,
        }

        return result

    @classmethod
    def handle_hit_list(cls, hits=None):
        hits = hits or []
        events = [cls.handle_hit(hit) for hit in hits]
        CategoryTranslator().translate_from_dict(events, "category", "category_display")
        return events

    def date_histogram(self, interval: str = "auto"):
        interval = self.calculate_agg_interval(self.start_time, self.end_time, interval)
        search_object = self.get_search_object()
        search_object = self.add_conditions(search_object)
        search_object = self.add_query_string(search_object)
        search_object = self.add_pagination(search_object, page_size=0)

        search_object.aggs.bucket(
            "group_by_histogram",
            "date_histogram",
            field="time",
            fixed_interval=f"{interval}s",
            format="epoch_millis",
            min_doc_count=0,
            extended_bounds={"min": self.start_time * 1000, "max": self.end_time * 1000},
        )

        search_result = search_object.execute()
        if not search_result.aggs:
            series_data = []
        else:
            series_data = [
                [int(bucket.key_as_string), bucket.doc_count]
                for bucket in search_result.aggs.group_by_histogram.buckets
            ]

        result_data = {
            "series": [{"data": series_data, "name": _("当前")}],
            "unit": "",
        }
        return result_data

    def top_n(self, fields: List, size=10, translators: Dict[str, AbstractTranslator] = None, char_add_quotes=True):
        translators = {
            "strategy_id": StrategyTranslator(),
            "category": CategoryTranslator(),
        }
        return super(EventQueryHandler, self).top_n(fields, size, translators, char_add_quotes)
