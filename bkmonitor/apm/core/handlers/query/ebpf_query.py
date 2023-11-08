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
import logging

from apm import constants
from apm.core.deepflow.base import DeepFlowHandler
from apm.core.handlers.query.base import EsQueryBuilderMixin
from apm.utils.es_search import EsSearch
from constants.apm import OtlpKey
from core.drf_resource import api

logger = logging.getLogger("deep-flow")


class EbpfQuery(EsQueryBuilderMixin):
    DEFAULT_SORT_FIELD = "end_time"

    def __init__(self, es_client, index_name):
        self.client = es_client
        self.client = es_client
        self.index_name = f"{index_name.replace('.', '_')}_*"

    @property
    def search(self):
        return EsSearch(using=self.client, index=self.index_name)

    def query_by_trace_id(self, trace_id):
        query = self.search

        query = self.add_filter(query, OtlpKey.TRACE_ID, trace_id)
        query = query.extra(size=constants.DISCOVER_BATCH_SIZE).sort(OtlpKey.START_TIME)

        return [i.to_dict() for i in query.execute()]


class DeepFlowQuery:
    @classmethod
    def get_ebpf(cls, trace_id: str):
        """
        获取ebpf数据
        """
        ebpf_spans = []
        ebpf_param = {"trace_id": trace_id}
        try:
            res = api.deepflow.query(ebpf_param)
            for item in res:
                span_data = DeepFlowHandler.l7_flow_log_to_resource_span(item)
                ebpf_spans.append(span_data)
        except Exception as e:
            logging.info("get_ebpf, {}".format(e))
        return ebpf_spans
