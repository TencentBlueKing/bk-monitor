# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2022 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import datetime

from elasticsearch_dsl import Q

from apm.core.handlers.discover_handler import DiscoverHandler
from apm.core.handlers.ebpf.base import EbpfHandler
from apm.core.handlers.query.base import EsQueryBuilderMixin
from apm.utils.es_search import EsSearch
from constants.apm import OtlpKey


class TraceQuery(EsQueryBuilderMixin):
    DEFAULT_SORT_FIELD = "min_start_time"

    KEY_PREFIX_TRANSLATE_FIELDS = {
        f"{OtlpKey.ATTRIBUTES}.": "collections",
        f"{OtlpKey.RESOURCE}.": "collections",
        OtlpKey.KIND: "collections",
        OtlpKey.SPAN_NAME: "collections",
    }

    KEY_REPLACE_FIELDS = {"duration": "trace_duration"}

    def __init__(self, bk_biz_id, app_name, es_client, index_name):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.client = es_client
        self.index_name = index_name

    @property
    def search(self):
        return EsSearch(using=self.client, index=self.index_name)

    def list(self, start_time, end_time, offset, limit, filters=None, es_dsl=None, exclude_field=None):
        query = self.search
        if es_dsl:
            query = query.update_from_dict(es_dsl)

        start, end = self.add_time_by_expire(start_time, end_time)
        if not start or not end:
            return [], 0

        query = self.add_time(query, start, end)

        query = self.add_app_filter(query)

        if filters:
            query = self.add_filter_params(query, filters)

        query = self.distinct_fields(query, OtlpKey.TRACE_ID)
        query = self.add_sort(query)
        query = query.source(exclude=["collections", "bk_app_code", "biz_name", "root_span_id"])

        query = query[offset : offset + limit]

        response = query.execute()

        # 将collapsed字段打平
        res = []
        for i in response.hits:
            item = i.to_dict()
            res.append({"trace_id": item.pop("trace_id")[0], **item})

        return res, response.aggregations.total_size.value

    def add_app_filter(self, query):
        query = self.add_filter(query, "biz_id", self.bk_biz_id)
        query = self.add_filter(query, "app_name", self.app_name)
        return query

    def _get_ebpf_application(self):
        return EbpfHandler.get_ebpf_application(self.bk_biz_id)

    def query_relation_by_trace_id(self, trace_id, start_time=None, end_time=None):
        """
        查询此traceId是否有跨应用关联
        查询时需要排除此业务下的EBPF应用
        """

        query = self.search

        ebpf_application = self._get_ebpf_application()
        if ebpf_application:
            app_filter_params = [
                {"term": {"biz_id": self.bk_biz_id}},
                {"terms": {"app_name": [self.app_name, ebpf_application.app_name]}},
            ]
        else:
            app_filter_params = [{"term": {"biz_id": self.bk_biz_id}}, {"term": {"app_name": self.app_name}}]

        query = query.query(
            "bool",
            must_not=[{"bool": {"filter": app_filter_params}}],
        )

        # 以此TraceId开始-结束时间为范围 在此时间范围内才为跨应用
        time_query = []
        if start_time:
            time_query.append(Q("range", **{"min_start_time": {"gte": start_time}}))
        if end_time:
            time_query.append(Q("range", **{"max_end_time": {"lte": end_time}}))
        if time_query:
            query = query.query("bool", must=time_query)

        query = self.add_filter(query, OtlpKey.TRACE_ID, trace_id)
        query = query.extra(size=1).sort("-time")
        response = query.execute()

        return response.hits[0].to_dict() if response.hits else None

    def query_latest(self, trace_id):
        query = self.search

        query = self.add_app_filter(query)
        query = self.add_filter(query, OtlpKey.TRACE_ID, trace_id)

        query = query.extra(size=1).sort("-time")

        response = query.execute()

        return response.hits[0].to_dict() if response.hits else None

    def query_option_values(self, start_time, end_time, fields):
        query = self.search

        start, end = self.add_time_by_expire(start_time, end_time)
        if not start or not end:
            return {}

        query = self.add_time(query, start, end)
        query = self.add_app_filter(query)

        return self._query_option_values(query, fields)

    @classmethod
    def _translate_key(cls, key):
        for i, prefix in cls.KEY_PREFIX_TRANSLATE_FIELDS.items():
            if key.startswith(i):
                return f"{prefix}.{key}"

        if key in cls.KEY_REPLACE_FIELDS:
            return cls.KEY_REPLACE_FIELDS[key]

        return key

    @classmethod
    def _add_logic_filter(cls, query, key, value):
        if key == "error":
            query = query.query("bool", must_not=[Q("term", **{"error_count": 0})])

        return query

    @classmethod
    def query_by_trace_ids(cls, client, index_name, trace_ids, start_time, end_time):
        query = EsSearch(using=client, index=index_name)
        query = cls.add_time(query, start_time, end_time)
        query = cls.add_sort(query, f"-{cls.DEFAULT_SORT_FIELD}")
        query = query.query("bool", filter=[Q("terms", **{OtlpKey.TRACE_ID: trace_ids})])
        query = query.extra(size=len(trace_ids))
        query = query.source(
            ["trace_id", "app_name", "error", "trace_duration", "root_service_category", "root_span_id"]
        )

        response = query.execute()
        return [i.to_dict() for i in response.hits] if response.hits else []

    def query_simple_info(self, start_time, end_time, offset, limit):
        """查询App下的简单Trace信息"""

        query = self.search

        start, end = self.add_time_by_expire(start_time, end_time)
        if not start or not end:
            return [], 0

        query = self.add_time(query, start, end)
        query = self.add_app_filter(query)
        query = self.add_sort(query, f"-{self.DEFAULT_SORT_FIELD}")
        query = self.distinct_fields(query, OtlpKey.TRACE_ID)
        query = query.source(["trace_id", "app_name", "error", "trace_duration", "root_service_category"])
        query = query[offset : offset + limit]

        response = query.execute()
        return [i.to_dict() for i in response.hits] if response.hits else [], response.aggregations.total_size.value

    def add_time_by_expire(self, start_time, end_time):
        """根据业务的ES过期时间限制查询的时间范围"""

        retention = DiscoverHandler.get_app_retention(self.bk_biz_id, self.app_name)
        now = datetime.datetime.now()
        days_ago = now - datetime.timedelta(days=retention)

        start_time = datetime.datetime.fromtimestamp(start_time)
        end_time = datetime.datetime.fromtimestamp(end_time)

        if end_time < days_ago:
            return None, None

        if start_time < days_ago:
            start_time = days_ago

        return int(start_time.timestamp()), int(end_time.timestamp())
