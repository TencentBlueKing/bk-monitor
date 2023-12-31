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

import abc
import datetime
import itertools
import logging
import traceback
from abc import ABC
from typing import List, NamedTuple, Tuple

from apm import constants
from apm.core.discover.precalculation.processor import PrecalculateProcessor
from apm.core.discover.precalculation.storage import PrecalculateStorage
from apm.models import ApmApplication, ApmTopoDiscoverRule, TraceDataSource
from apm.utils.base import divide_biscuit
from constants.apm import OtlpKey, SpanKind
from opentelemetry.semconv.resource import ResourceAttributes

from bkmonitor.utils.thread_backend import ThreadPool

logger = logging.getLogger("apm")


def get_topo_instance_key(keys: List[Tuple[str, str]], kind: str, category: str, item, skip_component_prefix=False):
    if item is None:
        return OtlpKey.UNKNOWN_SERVICE
    instance_keys = []
    if (
        kind in [ApmTopoDiscoverRule.TOPO_COMPONENT, ApmTopoDiscoverRule.TOPO_REMOTE_SERVICE]
        and not skip_component_prefix
    ):
        instance_keys = [category]
    for first_key, second_key in keys:
        key = item.get(first_key, item).get(second_key, "")
        instance_keys.append(str(key))
    return ":".join(instance_keys)


def exists_field(predicate_key: Tuple[str, str], item) -> bool:
    if item is None:
        return False
    predicate_first_key, predicate_second_key = predicate_key
    if item.get(predicate_first_key, item).get(predicate_second_key):
        return True
    return False


def extract_field_value(key: Tuple[str, str], item):
    first_key, second_key = key
    return item.get(first_key, item).get(second_key)


class ApmTopoDiscoverRuleCls(NamedTuple):
    instance_keys: List[Tuple[str, str]]
    topo_kind: str
    category_id: str
    predicate_key: Tuple[str, str]
    endpoint_key: Tuple[str, str]


class DiscoverBase(ABC):
    DISCOVER_CLS = []
    MAX_COUNT = None
    model = None

    @classmethod
    def register(cls, target):
        cls.DISCOVER_CLS.append(target)
        return target

    @classmethod
    def discovers(cls):
        for target in cls.DISCOVER_CLS:
            yield target

    def __init__(self, bk_biz_id, app_name):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name

    @property
    def application(self):
        return ApmApplication.get_application(self.bk_biz_id, self.app_name)

    def _get_key_pair(self, key: str):
        pair = key.split(".", 1)
        if len(pair) == 1:
            return "", pair[0]
        return pair[0], pair[1]

    def get_rules(self):
        rule_instances = ApmTopoDiscoverRule.get_application_rule(self.bk_biz_id, self.app_name)

        rules = []
        other_rules = []

        for rule in rule_instances:
            instance = ApmTopoDiscoverRuleCls(
                topo_kind=rule.topo_kind,
                category_id=rule.category_id,
                endpoint_key=self._get_key_pair(rule.endpoint_key),
                instance_keys=[self._get_key_pair(i) for i in rule.instance_key.split(",")],
                predicate_key=self._get_key_pair(rule.predicate_key),
            )
            if instance.category_id == ApmTopoDiscoverRule.APM_TOPO_CATEGORY_OTHER:
                other_rules.append(instance)

            (rules, other_rules)[instance.category_id == ApmTopoDiscoverRule.APM_TOPO_CATEGORY_OTHER].append(instance)

        return rules, other_rules[0]

    def filter_rules(self, rule_kind):
        rules, other_rule = self.get_rules()
        return [r for r in rules + [other_rule] if r.topo_kind == rule_kind]

    def get_service_name(self, span):
        return extract_field_value((OtlpKey.RESOURCE, ResourceAttributes.SERVICE_NAME), span)

    def get_match_rule(self, span, rules, other_rule=None):
        res = next((rule for rule in rules if exists_field(rule.predicate_key, span)), None)

        return res if res else other_rule

    def clear_if_overflow(self):
        count = self.model.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).count()
        if count > self.MAX_COUNT:
            delete_count = count - self.MAX_COUNT
            delete_pks = self.model.objects.order_by("updated_at").values_list("pk", flat=True)[:delete_count]
            self.model.objects.filter(pk__in=list(delete_pks)).delete()

    def clear_expired(self):
        # clean expired topo data based on expiration
        boundary = datetime.datetime.now() - datetime.timedelta(self.application.trace_datasource.retention)
        filter_params = {"bk_biz_id": self.bk_biz_id, "app_name": self.app_name, "updated_at__lte": boundary}

        self.model.objects.filter(**filter_params).delete()

    def get_and_clear_if_repeat(self, exists_mapping):
        res = {}
        need_delete_ids = []

        for key, value in exists_mapping.items():
            if value and len(value) != 1:
                v = tuple(value)
                need_delete_ids += sorted(v, reverse=True)[1:]
                res[key] = {v[0]}
            else:
                res[key] = value

        if need_delete_ids:
            self.model.objects.filter(id__in=need_delete_ids).delete()

        return res

    @abc.abstractmethod
    def discover(self, origin_data):
        pass


class TopoHandler:

    TRACE_ID_CHUNK_MAX_DURATION = 10 * 60
    # 最大发现的TraceId数量
    TRACE_ID_MAX_SIZE = 50000
    # 每一轮最多分析多少个TraceId
    PER_ROUND_TRACE_ID_MAX_SIZE = 100

    FILTER_KIND = [
        SpanKind.SPAN_KIND_SERVER,
        SpanKind.SPAN_KIND_CLIENT,
        SpanKind.SPAN_KIND_PRODUCER,
        SpanKind.SPAN_KIND_CONSUMER,
    ]

    _ES_MAX_RESULT_WINDOWS = 10000

    def __init__(self, bk_biz_id, app_name):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.datasource = TraceDataSource.objects.filter(app_name=app_name, bk_biz_id=bk_biz_id).first()
        self.application = ApmApplication.get_application(self.bk_biz_id, self.app_name)

    def __str__(self):
        return f"bk_biz_id: {self.bk_biz_id} app_name: {self.app_name}"

    def is_valid(self) -> bool:
        """Topo Instance validator"""
        if not self.datasource:
            logger.warning(f"[TopoHandler]validated fail {self} not init datasource, skip")
            return False

        return True

    def _get_after_key_body(self, after_key=None):
        body = {
            "size": 0,
            "query": {"bool": {"must": {"range": {"time": {"gte": "now-10m", "lt": "now"}}}}},
            "aggs": {
                "unique_trace_id": {
                    "composite": {
                        "size": self.PER_ROUND_TRACE_ID_MAX_SIZE,
                        "sources": [{"trace_id_source": {"terms": {"field": "trace_id"}}}],
                    }
                }
            },
        }

        if after_key:
            body["aggs"]["unique_trace_id"]["composite"]["after"] = after_key

        return body

    def list_trace_ids(self):

        start = datetime.datetime.now()
        after_key = None

        while True:
            query_body = self._get_after_key_body(after_key)

            response = self.datasource.es_client.search(
                index=self.datasource.index_name, body=query_body, request_timeout=60
            )

            per_round_trace_ids = []
            # 处理结果
            buckets = response.get("aggregations", {}).get("unique_trace_id", {}).get("buckets", [])
            for bucket in buckets:
                per_round_trace_ids.append(bucket["key"]["trace_id_source"])

            if (datetime.datetime.now() - start).seconds >= self.TRACE_ID_CHUNK_MAX_DURATION:
                logger.warning(
                    f"[TopoHandler] {self.bk_biz_id} {self.app_name} "
                    f"list trace_ids over {constants.DISCOVER_TIME_RANGE}, break"
                )
                break
            yield per_round_trace_ids

            after_key = response.get("aggregations", {}).get("unique_trace_id", {}).get("after_key")
            if not after_key:
                break

    def list_span_by_trace_ids(self, trace_ids, max_result_count):

        if max_result_count >= constants.DISCOVER_BATCH_SIZE * len(trace_ids):
            # 直接获取
            query = {
                "query": {"bool": {"must": [{"terms": {OtlpKey.TRACE_ID: trace_ids}}]}},
                "size": constants.DISCOVER_BATCH_SIZE * len(trace_ids),
            }
            response = self.datasource.es_client.search(index=self.datasource.index_name, body=query)
            hits = response["hits"]["hits"]
            return [i["_source"] for i in hits]
        else:
            # 使用scroll获取
            res = []
            query = {
                "query": {"bool": {"must": [{"terms": {OtlpKey.TRACE_ID: trace_ids}}]}},
                "size": constants.DISCOVER_BATCH_SIZE * len(trace_ids),
            }
            response = self.datasource.es_client.search(index=self.datasource.index_name, body=query, scroll="5m")
            hits = response["hits"]["hits"]
            res += [i["_source"] for i in hits]

            scroll_id = response["_scroll_id"]

            while len(hits):
                response = self.datasource.es_client.scroll(scroll_id=scroll_id, scroll="5m")
                hits = response["hits"]["hits"]
                res += [i["_source"] for i in hits]

            self.datasource.es_client.clear_scroll(scroll_id=scroll_id)
            return res

    def _discover_handle(self, discover, spans, handle_type):
        def _topo_handle():
            discover(self.bk_biz_id, self.app_name).discover(spans)

        def _pre_calculate_handle():
            discover.handle(spans)

        start = datetime.datetime.now()
        try:
            {"topo": _topo_handle, "pre_calculate": _pre_calculate_handle}[handle_type]()
        except Exception as e:  # noqa
            logger.error(
                f"[TopoHandler] discover failed"
                f"bk_biz_id: {self.bk_biz_id} app_name: {self.app_name} "
                f"discover: {str(discover)} handle_type: {handle_type}"
                f"error: {e} exception: {traceback.format_exc()}"
            )

        duration = (datetime.datetime.now() - start).seconds
        logger.info(f"[{handle_type}] round discover success. span count: {len(spans)} duration: {duration}ms")

    def _get_trace_task_splits(self):
        """根据此索引最大的结果返回数量判断每个子任务需要传递多少个traceId"""
        index_settings = self.datasource.es_client.indices.get_settings(index=self.datasource.index_name)
        if not index_settings:
            max_size_count = self._ES_MAX_RESULT_WINDOWS
        else:
            lastly_index = max(
                index_settings.keys(),
                key=lambda i: index_settings[i].get("settings", {}).get("index", {}).get("creation_date", 0),
            )

            max_size_count = index_settings[lastly_index].get("settings", {}).get("index", {}).get("max_result_window")
        # ES 1.x-7.x默认值
        max_size_count = int(max_size_count) if max_size_count else self._ES_MAX_RESULT_WINDOWS

        if max_size_count >= constants.DISCOVER_BATCH_SIZE:
            return max_size_count, max_size_count // constants.DISCOVER_BATCH_SIZE

        logger.info(f"[TopoHandler] found max_size_count: {max_size_count} < {constants.DISCOVER_BATCH_SIZE}")

        return max_size_count, 1

    def discover(self):
        """application spans discover"""

        start = datetime.datetime.now()
        pre_calculate_storage = PrecalculateStorage(self.bk_biz_id, self.app_name)
        trace_id_count = 0
        span_count = 0
        max_result_count, per_trace_size = self._get_trace_task_splits()

        for trace_ids in self.list_trace_ids():
            trace_id_count += len(trace_ids)

            pool = ThreadPool()
            get_spans_params = [(i, max_result_count) for i in divide_biscuit(trace_ids, per_trace_size)]
            results = pool.map_ignore_exception(self.list_span_by_trace_ids, get_spans_params)
            all_spans = list(itertools.chain(*[i for i in results if i]))
            span_count += len(all_spans)

            topo_spans = [i for i in all_spans if i[OtlpKey.KIND] in self.FILTER_KIND]

            # 拓扑发现任务
            topo_params = [(c, topo_spans, "topo") for c in DiscoverBase.DISCOVER_CLS]

            # 预计算任务
            if pre_calculate_storage.is_valid:
                # 灰度应用不参与定时任务中的预计算功能
                from apm.core.discover.precalculation.daemon import (
                    PrecalculateGrayRelease,
                )

                if not PrecalculateGrayRelease.exist(self.application.id):
                    pre_calculate_params = [
                        (
                            PrecalculateProcessor(pre_calculate_storage, self.bk_biz_id, self.app_name),
                            all_spans,
                            "pre_calculate",
                        )
                    ]
                    topo_params += pre_calculate_params

            pool.map_ignore_exception(self._discover_handle, topo_params)

        logger.info(
            f"[TopoHandler] discover finished {self.bk_biz_id} {self.app_name} "
            f"trace count: {trace_id_count} span count: {span_count} "
            f"elapsed: {(datetime.datetime.now() - start).seconds}s"
        )
