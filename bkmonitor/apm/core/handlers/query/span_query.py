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

from apm import constants
from apm.core.handlers.query.base import EsQueryBuilderMixin
from apm.utils.es_search import EsSearch
from constants.apm import OtlpKey


class SpanQuery(EsQueryBuilderMixin):
    DEFAULT_SORT_FIELD = "end_time"

    KEY_REPLACE_FIELDS = {"duration": "elapsed_time"}

    def __init__(self, es_client, index_name):
        self.client = es_client
        self.index_name = index_name

    @property
    def search(self):
        return EsSearch(using=self.client, index=self.index_name)

    def list(self, start_time, end_time, offset, limit, filter_params=None, es_dsl=None, exclude_field=None):
        query = self.search
        if es_dsl:
            query = query.update_from_dict(es_dsl)

        query = self.add_time(query, start_time, end_time)
        self.add_total_size(query, OtlpKey.SPAN_ID)

        if filter_params:
            query = self.add_filter_params(query, filter_params)

        query = self.add_sort(query)
        if exclude_field is None:
            query = query.source(exclude=["attributes", "links", "events"])
        else:
            query = query.source(exclude=exclude_field)

        query = query[offset : offset + limit]

        response = query.execute()

        return [i.to_dict() for i in response.hits], response.aggregations.total_size.value

    def query_option_values(self, start_time, end_time, fields):
        query = self.search
        query = self.add_time(query, start_time, end_time)

        return self._query_option_values(query, fields)

    def query_by_trace_id(self, trace_id):
        query = self.search

        query = self.add_filter(query, OtlpKey.TRACE_ID, trace_id)
        query = query.extra(size=constants.DISCOVER_BATCH_SIZE).sort(OtlpKey.START_TIME)

        return [i.to_dict() for i in query.execute()]

    def query_by_span_id(self, span_id):
        query = self.search

        query = self.add_filter(query, OtlpKey.SPAN_ID, span_id)
        query = query.extra(size=1).sort(f"-{OtlpKey.START_TIME}")

        response = query.execute()

        if response.hits.total.value:
            return response[0].to_dict()

        return None

    @classmethod
    def _translate_key(cls, key):
        if key in cls.KEY_REPLACE_FIELDS:
            return cls.KEY_REPLACE_FIELDS[key]

        return key
