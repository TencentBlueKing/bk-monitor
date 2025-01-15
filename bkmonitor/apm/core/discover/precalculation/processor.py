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
import logging
import operator

import networkx
from networkx import dag_longest_path_length
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import StatusCode

from apm.constants import KindCategory
from apm.models import ApmApplication
from apm_web.handlers.span_infer import InferenceHandler
from bkm_space.api import SpaceApi
from bkmonitor.utils import group_by
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import (
    OtlpKey,
    PreCalculateSpecificField,
    SpanKind,
    SpanStandardField,
)

logger = logging.getLogger("apm")


class PrecalculateProcessor:
    """
    预计算处理类
    [旧] 目前应用已经迁移至 BMW 预计算处
    """

    def __init__(self, storage, bk_biz_id, app_name):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.storage = storage
        self.application = ApmApplication.get_application(bk_biz_id=bk_biz_id, app_name=app_name)
        space = SpaceApi.get_space_detail(bk_biz_id=bk_biz_id)
        bk_biz_name = space.display_name
        self.bk_biz_name = bk_biz_name

    def handle(self, all_span):
        trace_mapping = group_by(all_span, operator.itemgetter(OtlpKey.TRACE_ID))

        logger.info(f"[PrecalculateProcessor] group by total {len(trace_mapping)} trace")
        pool = ThreadPool()
        params = [(k, v) for k, v in trace_mapping.items()]

        results = pool.map_ignore_exception(self.get_trace_info, params)

        data = []
        for result in results:
            if not result:
                continue

            # 指定 Id 字段
            data.append({"_index": self.storage.save_index_name, "_id": result["trace_id"], "_source": result})

        # 存储数据
        self.storage.save(data)

    def get_status_code(self, span):
        for i in [SpanAttributes.HTTP_STATUS_CODE, SpanAttributes.RPC_GRPC_STATUS_CODE]:
            if i in span[OtlpKey.ATTRIBUTES]:
                return span[OtlpKey.ATTRIBUTES][i]

        return None

    def get_trace_info(self, trace_id, spans):
        from apm_web.constants import CategoryEnum

        sorted_spans = sorted(spans, key=lambda s: s[OtlpKey.START_TIME])
        nodes = set()
        edges = set()
        services = set()
        start_times = []
        end_times = []
        durations = []
        error_count = 0
        category_statistics = {
            CategoryEnum.HTTP: 0,
            CategoryEnum.RPC: 0,
            CategoryEnum.DB: 0,
            CategoryEnum.MESSAGING: 0,
            CategoryEnum.ASYNC_BACKEND: 0,
            CategoryEnum.OTHER: 0,
        }
        kind_statistics = {
            KindCategory.ASYNC: 0,
            KindCategory.SYNC: 0,
            KindCategory.INTERNAL: 0,
            KindCategory.UNSPECIFIED: 0,
        }
        collections = self.init_collections()

        span_id_mapping = {}

        for i in sorted_spans:
            span_id_mapping[i[OtlpKey.SPAN_ID]] = i

            if i[OtlpKey.PARENT_SPAN_ID]:
                nodes.add(i[OtlpKey.PARENT_SPAN_ID])
                nodes.add(i[OtlpKey.SPAN_ID])
                edges.add((i[OtlpKey.PARENT_SPAN_ID], i[OtlpKey.SPAN_ID]))
            else:
                nodes.add(i[OtlpKey.SPAN_ID])
                edges.add((i[OtlpKey.SPAN_ID], "--"))

            service_name = i[OtlpKey.RESOURCE].get(ResourceAttributes.SERVICE_NAME)
            if service_name:
                services.add(service_name)

            start_times.append(i[OtlpKey.START_TIME])
            end_times.append(i[OtlpKey.END_TIME])
            durations.append(i[OtlpKey.END_TIME] - i[OtlpKey.START_TIME])

            if i[OtlpKey.STATUS]["code"] == StatusCode.ERROR.value:
                error_count += 1

            category_statistics[InferenceHandler.infer(i)] += 1
            kind_statistics[KindCategory.get_category(i[OtlpKey.KIND])] += 1
            self.collect(collections, i)

        # 层级数
        graph = networkx.DiGraph()
        graph.add_nodes_from(nodes)
        graph.add_edges_from(edges)
        hierarchy_count = dag_longest_path_length(graph)
        degree_mapping = self.list_span_degree(graph, span_id_mapping)

        # 入口服务&入口接口&入口状态码&入口调用类型
        root_service_span = next(
            iter(
                sorted(
                    [v for k, v in degree_mapping.items() if v["node"][OtlpKey.KIND] in SpanKind.called_kinds()],
                    key=lambda x: (x["degree"], x["node"][OtlpKey.START_TIME]),
                )
            ),
            None,
        )
        if root_service_span:
            root_service_span = root_service_span["node"]
            root_service_span_id = root_service_span[OtlpKey.SPAN_ID]
            root_service = root_service_span[OtlpKey.RESOURCE][ResourceAttributes.SERVICE_NAME]
            root_service_span_name = root_service_span[OtlpKey.SPAN_NAME]
            root_service_status_code = self.get_status_code(root_service_span)
            root_service_category = InferenceHandler.infer(root_service_span)
            root_service_kind = root_service_span[OtlpKey.KIND]
        else:
            root_service_span_id = None
            root_service = None
            root_service_span_name = None
            root_service_status_code = None
            root_service_category = None
            root_service_kind = None

        # 根Span
        root_span = next(iter(sorted([v for k, v in degree_mapping.items()], key=lambda x: x["degree"])))["node"]
        root_span_id = root_span[OtlpKey.SPAN_ID]
        root_span_name = root_span[OtlpKey.SPAN_NAME]
        root_span_service = root_span[OtlpKey.RESOURCE].get(ResourceAttributes.SERVICE_NAME)
        root_span_kind = root_span[OtlpKey.KIND]

        # 服务数
        service_count = len(services)

        # Span数量
        span_count = len(spans)

        # 最早开始时间
        min_start_time = sorted(start_times)[0]

        # 最晚结束时间
        max_end_time = sorted(end_times, reverse=True)[0]

        # Trace耗时
        trace_duration = max_end_time - min_start_time

        # 单Span最大耗时
        span_max_duration = max(durations)

        # 单Span最小耗时
        span_min_duration = min(durations)

        # 是否出错
        error = bool(error_count)

        return {
            PreCalculateSpecificField.BIZ_ID.value: self.bk_biz_id,
            PreCalculateSpecificField.BIZ_NAME.value: self.bk_biz_name,
            PreCalculateSpecificField.APP_ID.value: self.application.id,
            PreCalculateSpecificField.APP_NAME.value: self.app_name,
            PreCalculateSpecificField.TRACE_ID.value: trace_id,
            PreCalculateSpecificField.HIERARCHY_COUNT.value: hierarchy_count,
            PreCalculateSpecificField.SERVICE_COUNT.value: service_count,
            PreCalculateSpecificField.SPAN_COUNT.value: span_count,
            PreCalculateSpecificField.MIN_START_TIME.value: min_start_time,
            PreCalculateSpecificField.MAX_END_TIME.value: max_end_time,
            PreCalculateSpecificField.TRACE_DURATION.value: trace_duration,
            PreCalculateSpecificField.SPAN_MAX_DURATION.value: span_max_duration,
            PreCalculateSpecificField.SPAN_MIN_DURATION.value: span_min_duration,
            PreCalculateSpecificField.ROOT_SERVICE.value: root_service,
            PreCalculateSpecificField.ROOT_SERVICE_SPAN_ID.value: root_service_span_id,
            PreCalculateSpecificField.ROOT_SERVICE_SPAN_NAME.value: root_service_span_name,
            PreCalculateSpecificField.ROOT_SERVICE_STATUS_CODE.value: root_service_status_code,
            PreCalculateSpecificField.ROOT_SERVICE_CATEGORY.value: root_service_category,
            PreCalculateSpecificField.ROOT_SERVICE_KIND.value: root_service_kind,
            PreCalculateSpecificField.ROOT_SPAN_ID.value: root_span_id,
            PreCalculateSpecificField.ROOT_SPAN_NAME.value: root_span_name,
            PreCalculateSpecificField.ROOT_SPAN_SERVICE.value: root_span_service,
            PreCalculateSpecificField.ROOT_SPAN_KIND.value: root_span_kind,
            PreCalculateSpecificField.ERROR.value: error,
            PreCalculateSpecificField.ERROR_COUNT.value: error_count,
            PreCalculateSpecificField.TIME.value: int(datetime.datetime.now().timestamp() * 1000 * 1000),
            PreCalculateSpecificField.CATEGORY_STATISTICS.value: category_statistics,
            PreCalculateSpecificField.KIND_STATISTICS.value: kind_statistics,
            PreCalculateSpecificField.COLLECTIONS.value: collections,
        }

    def init_collections(self):
        res = {}
        for f in SpanStandardField.COMMON_STANDARD_FIELDS:
            if f.source == f.key:
                res[f.source] = []
            else:
                if f.source in res:
                    res[f.source][f.key] = []
                else:
                    res[f.source] = {f.key: []}

        return res

    def collect(self, collections, span):
        for f in SpanStandardField.COMMON_STANDARD_FIELDS:
            v = span[f.source]
            if isinstance(v, dict):
                if v.get(f.key) and v[f.key] not in collections[f.source][f.key]:
                    collections[f.source][f.key].append(v[f.key])
            else:
                if span.get(f.key) and span[f.key] not in collections[f.source]:
                    collections[f.source].append(span[f.key])

    @classmethod
    def list_span_degree(cls, graph, node_data):
        """获取span层级等信息"""

        res = {}
        for node in node_data.values():
            degree = graph.in_degree(node[OtlpKey.SPAN_ID])
            res[node[OtlpKey.SPAN_ID]] = {
                "degree": degree,
                "node": node,
            }

        return res
