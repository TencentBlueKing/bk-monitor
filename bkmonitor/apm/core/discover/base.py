"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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
from collections import defaultdict
from typing import NamedTuple
from collections.abc import Callable

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from opentelemetry.semconv.resource import ResourceAttributes

from apm import constants
from apm.constants import DiscoverRuleType
from apm.core.discover.instance_data import BaseInstanceData
from apm.models import ApmApplication, ApmTopoDiscoverRule, TraceDataSource
from apm.utils.base import divide_biscuit
from apm.utils.es_search import limits
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import OtlpKey, SpanKind, TelemetryDataType
from core.drf_resource.exceptions import CustomException

logger = logging.getLogger("apm")


def get_topo_instance_key(
    keys: list[tuple[str, str]],
    kind: str,
    category: str,
    item,
    simple_component_instance=True,
    component_predicate_key=None,
):
    """
    simple_component_instance / component_predicate_key
    对于组件类型 topo
    如果simple_component_instance为 True 则只会返回 predicate.value 的值 需要在外部进行额外处理(拼接服务名称)
    """
    if item is None:
        return OtlpKey.UNKNOWN_SERVICE

    if component_predicate_key and isinstance(component_predicate_key, list):
        # 忽略 predicate_key 为多个的情况 直接取第一个
        component_predicate_key = component_predicate_key[0]

    instance_keys = []
    if kind == ApmTopoDiscoverRule.TOPO_COMPONENT:
        if simple_component_instance and component_predicate_key:
            return item.get(component_predicate_key[0], item).get(component_predicate_key[1], OtlpKey.UNKNOWN_COMPONENT)
    elif kind == ApmTopoDiscoverRule.TOPO_REMOTE_SERVICE:
        instance_keys = [category]

    for first_key, second_key in keys:
        key = item.get(first_key, item).get(second_key, "")
        instance_keys.append(str(key))
    return ":".join(instance_keys)


def exists_field(predicate_key: tuple[str, str] | list[tuple[str, str]], item) -> bool:
    if item is None:
        return False

    if isinstance(predicate_key, tuple):
        predicate_key = [predicate_key]

    all_exists = []
    for i in predicate_key:
        first, second = i

        all_exists.append(bool(item.get(first, item).get(second)))

    return all(all_exists)


def extract_field_value(key: list[tuple[str, str]] | tuple[str, str], item):
    if key and isinstance(key, list):
        # 忽略 predicate_key 为多个的情况 直接取第一个
        key = key[0]

    first_key, second_key = key
    return item.get(first_key, item).get(second_key)


def combine_list(target, source):
    """
    合并两个列表
    相同 name 的进行 extra_data 合并
    不同 name 的追加在数组中
    """
    if not target and not source:
        return []
    if not target:
        return source
    if not source:
        return target

    merged_dict = {}

    for item in target:
        name = item["name"]
        extra_data = item["extra_data"]
        merged_dict[name] = extra_data

    for item in source:
        name = item["name"]
        extra_data = item["extra_data"]
        if name in merged_dict:
            merged_dict[name].update(extra_data)
        else:
            merged_dict[name] = extra_data

    return [{"name": name, "extra_data": data} for name, data in merged_dict.items()]


class ApmTopoDiscoverRuleCls(NamedTuple):
    instance_keys: list[tuple[str, str]]
    topo_kind: str
    category_id: str
    predicate_key: tuple[str, str] | list[tuple[str, str]]
    endpoint_key: tuple[str, str] | None
    type: str
    sort: int


class DiscoverContainer:
    _discover_mapping = defaultdict(list)

    @classmethod
    def register(cls, module, target):
        cls._discover_mapping[module].append(target)

    @classmethod
    def list_discovers(cls, module):
        if module not in cls._discover_mapping:
            raise ValueError(f"[DiscoverContainer] 未找到 discover 类型为: {module} ")
        return cls._discover_mapping[module]


# DiscoverBase: Trace 数据拓扑发现基类
class DiscoverBase(ABC):
    MAX_COUNT = None
    model = None
    # 定义此发现器根据 span 列表发现时 span 列表是否为过滤后的 span 列表
    DISCOVERY_ALL_SPANS = False

    def __init__(self, bk_biz_id, app_name):
        self.bk_biz_id = bk_biz_id
        self.bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        self.app_name = app_name

    @property
    def application(self):
        app = ApmApplication.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).first()
        if not app:
            raise CustomException(_("业务下的应用: {} 不存在").format(self.app_name))
        return app

    def _get_key_pair(self, key: str):
        pair = key.split(".", 1)
        if len(pair) == 1:
            return "", pair[0]
        return pair[0], pair[1]

    @classmethod
    def join_keys(cls, keys):
        return ".".join(keys)

    def get_rules(self, _type=DiscoverRuleType.CATEGORY.value):
        rule_instances = ApmTopoDiscoverRule.get_application_rule(self.bk_biz_id, self.app_name, _type=_type)

        rules = []
        other_rules = []

        for rule in rule_instances:
            # [!!!] predicate_key 可能为单个也可能为多个
            # 注意这里类型可能是 string 或者 list
            # 目前只有 k8s 规则存在多个
            p_keys = rule.predicate_key.split(",")
            if len(p_keys) <= 1:
                p_keys = self._get_key_pair(p_keys[0]) if p_keys else ""
            else:
                p_keys = [self._get_key_pair(i) for i in p_keys]

            instance = ApmTopoDiscoverRuleCls(
                topo_kind=rule.topo_kind,
                category_id=rule.category_id,
                endpoint_key=self._get_key_pair(rule.endpoint_key) if rule.endpoint_key else None,
                instance_keys=[self._get_key_pair(i) for i in rule.instance_key.split(",")]
                if rule.instance_key
                else [],
                predicate_key=p_keys,
                type=rule.type,
                sort=rule.sort,
            )

            (rules, other_rules)[instance.category_id == ApmTopoDiscoverRule.APM_TOPO_CATEGORY_OTHER].append(instance)
        return rules, other_rules[0]

    def filter_rules(self, rule_kind):
        rules, other_rule = self.get_rules()
        return [r for r in rules + [other_rule] if r.topo_kind == rule_kind]

    def get_service_name(self, span):
        return extract_field_value((OtlpKey.RESOURCE, ResourceAttributes.SERVICE_NAME), span)

    def get_match_rule(
        self, span, rules, other_rule=None, extra_cond: Callable[[ApmTopoDiscoverRuleCls], bool] = lambda x: True
    ):
        res = next((rule for rule in rules if exists_field(rule.predicate_key, span) and extra_cond(rule)), None)

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
    def discover(self, origin_data, remain_data: dict[tuple, BaseInstanceData]):
        pass

    def get_remain_data(self):
        return None

    @classmethod
    def build_instance_data(cls, instance_obj) -> BaseInstanceData:
        raise NotImplementedError("Subclass must implement build_instance_data()")

    @classmethod
    def _to_found_key(cls, instance_data: BaseInstanceData) -> tuple:
        """
        从实例数据对象生成业务唯一标识（不包含数据库ID）用于在 discover 过程中匹配已存在的实例
        :param instance_data: 实例数据对象
        :return: 业务唯一标识元组
        """
        raise NotImplementedError("Subclass must implement _to_found_key()")

    @classmethod
    def get_attr_value(cls, obj, attr_name):
        if hasattr(obj, attr_name):
            return getattr(obj, attr_name)
        return obj.get(attr_name) if isinstance(obj, dict) else None

    def process_duplicate_records(
        self, db_instances, delete_duplicates: bool = False, keep_last: bool = False
    ) -> dict[tuple, BaseInstanceData]:
        """
        处理重复数据的通用方法
        :param db_instances: 数据库查询结果（QuerySet 或列表）
        :param delete_duplicates: 是否删除重复记录，默认为 False
        :param keep_last: 是否保留最后一条记录（ID 最大），False 则保留第一条（ID 最小），默认为 False
        :return: 去重后的字典映射，key 为实例 key，value 为 BaseInstanceData 实例
        """
        exists_mapping = {}
        for instance in db_instances:
            # 构建实例数据对象
            instance_data = self.build_instance_data(instance)
            # 获取唯一键
            key = self._to_found_key(instance_data)
            if key not in exists_mapping:
                exists_mapping[key] = []
            exists_mapping[key].append(instance_data)

        # 处理重复数据并构建最终结果
        res = {}
        need_delete_ids = []

        for key, records in exists_mapping.items():
            records.sort(key=lambda x: x.id)
            keep_record = records[-1] if keep_last else records[0]

            # 收集需要删除的重复记录ID（仅在 delete_duplicates=True 时）
            if len(records) > 1 and delete_duplicates:
                if keep_last:
                    need_delete_ids.extend([r.id for r in records[:-1]])
                else:
                    need_delete_ids.extend([r.id for r in records[1:]])

            # 保留的记录
            res[key] = keep_record

        # 执行数据库删除操作
        if need_delete_ids:
            # 注意：这里需要子类提供 model 属性
            self.model.objects.filter(id__in=need_delete_ids).delete()
            logger.info(
                f"[{self.__class__.__name__}] Deleted {len(need_delete_ids)} duplicate records: {need_delete_ids}"
            )

        return res


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

    def list_trace_ids(self, index_name):
        start = datetime.datetime.now()
        after_key = None

        while True:
            query_body = self._get_after_key_body(after_key)
            logger.info(f"[TopoHandler] {self.bk_biz_id} {self.app_name} list_trace_ids body: {query_body}")
            response = self.datasource.es_client.search(index=index_name, body=query_body, request_timeout=60)

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

    @limits(calls=100, period=1)
    def list_span_by_trace_ids(self, trace_ids, max_result_count, index_name):
        if max_result_count > constants.DISCOVER_BATCH_SIZE * len(trace_ids):
            # 直接获取
            query = {
                "query": {"bool": {"must": [{"terms": {OtlpKey.TRACE_ID: trace_ids}}]}},
                "size": constants.DISCOVER_BATCH_SIZE * len(trace_ids),
            }
            response = self.datasource.es_client.search(index=index_name, body=query)
            hits = response["hits"]["hits"]
            return [i["_source"] for i in hits]
        else:
            # 使用scroll获取
            res = []
            query = {
                "query": {"bool": {"must": [{"terms": {OtlpKey.TRACE_ID: trace_ids}}]}},
                "size": max_result_count,
            }
            response = self.datasource.es_client.search(index=index_name, body=query, scroll="5m")
            hits = response["hits"]["hits"]
            res += [i["_source"] for i in hits]

            scroll_id = response["_scroll_id"]

            while len(hits):
                response = self.datasource.es_client.scroll(scroll_id=scroll_id, scroll="5m")
                hits = response["hits"]["hits"]
                res += [i["_source"] for i in hits]

            self.datasource.es_client.clear_scroll(scroll_id=scroll_id)
            return res

    def _discover_handle(self, discover, spans, handle_type, remain_data):
        def _topo_handle():
            instance = discover(self.bk_biz_id, self.app_name)
            instance.discover(spans, remain_data)

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
        logger.info(
            f"[TopoHandler] round discover success. "
            f"bk_biz_id: {self.bk_biz_id} app_name: {self.app_name} "
            f"discover: {str(discover)} handle_type: {handle_type} "
            f"span count: {len(spans)} duration: {duration}ms"
        )

    def _get_trace_task_splits(self):
        """根据此索引最大的结果返回数量判断每个子任务需要传递多少个traceId"""
        lastly_index_name = self.datasource.index_name.split(",")[0]
        index_settings = self.datasource.es_client.indices.get_settings(index=lastly_index_name)
        max_size_count = None
        if not index_settings:
            max_size_count = self._ES_MAX_RESULT_WINDOWS
        else:
            if lastly_index_name in index_settings:
                max_size_count = (
                    index_settings[lastly_index_name].get("settings", {}).get("index", {}).get("max_result_window")
                )
        # ES 1.x-7.x默认值为 10000
        max_size_count = int(max_size_count) if max_size_count else self._ES_MAX_RESULT_WINDOWS

        if max_size_count >= constants.DISCOVER_BATCH_SIZE:
            return max_size_count, max_size_count // constants.DISCOVER_BATCH_SIZE, lastly_index_name

        logger.info(f"[TopoHandler] found max_size_count: {max_size_count} < {constants.DISCOVER_BATCH_SIZE}")

        return max_size_count, 1, lastly_index_name

    @classmethod
    def calculate_round_count(cls, avg_group_span_count):
        # 最大分析 Span 的数量不能超过 1000，防止每轮 Trace 数量增多导致OOM
        if cls.PER_ROUND_TRACE_ID_MAX_SIZE * avg_group_span_count > settings.PER_ROUND_SPAN_MAX_SIZE:
            max_span_count = settings.PER_ROUND_SPAN_MAX_SIZE
        else:
            max_span_count = cls.PER_ROUND_TRACE_ID_MAX_SIZE * avg_group_span_count

        per_trace_size = int(max_span_count / avg_group_span_count)
        if per_trace_size > cls.PER_ROUND_TRACE_ID_MAX_SIZE:
            per_trace_size = cls.PER_ROUND_TRACE_ID_MAX_SIZE

        return 1 if not per_trace_size else per_trace_size

    def discover(self):
        """application spans discover"""
        start = datetime.datetime.now()
        trace_id_count = 0
        span_count = 0
        filter_span_count = 0
        try:
            max_result_count, per_trace_size, index_name = self._get_trace_task_splits()
        except Exception as e:
            logger.error(
                f"[TopoHandler] 业务id: {self.bk_biz_id}和应用名: {self.app_name}"
                f"构建的TopoHandler对象在discover方法内发生异常, error({e})"
            )
            return

        # 提前构造topo_params结构
        topo_params_template = []
        for c in DiscoverContainer.list_discovers(TelemetryDataType.TRACE.value):
            topo_params_template.append((c, None, "topo", c(self.bk_biz_id, self.app_name).get_remain_data()))

        for round_index, trace_ids in enumerate(self.list_trace_ids(index_name)):
            if not trace_ids:
                continue

            trace_id_count += len(trace_ids)

            pool = ThreadPool()
            get_spans_params = [(i, max_result_count, index_name) for i in divide_biscuit(trace_ids, per_trace_size)]
            results = pool.map_ignore_exception(self.list_span_by_trace_ids, get_spans_params)
            all_spans_group = [i for i in results if i]
            all_spans = list(itertools.chain(*all_spans_group))
            avg_group_span_count = len(all_spans) / len(get_spans_params)
            if round_index == 0 and avg_group_span_count:
                per_trace_size = self.calculate_round_count(avg_group_span_count)

                logger.info(
                    f"[TopoHandler] {self.bk_biz_id} {self.app_name} "
                    f"index_name: {index_name} "
                    f"per_trace_size: {per_trace_size} "
                    f"avg_group_span_count: {avg_group_span_count} "
                    f"span_count: {len(all_spans)}"
                )

            span_count += len(all_spans)

            # 拓扑发现任务
            # endpoint\relation\remote_service_relation\root_endpoint 需要 kind != 0/1 数据
            # host\instance\node 需要全部 span 数据
            topo_params = []
            filter_spans = [i for i in all_spans if i[OtlpKey.KIND] in self.FILTER_KIND]
            filter_span_count += len(filter_spans)
            # 根据模板更新spans数据
            for c, spans, handle_type, remain_data in topo_params_template:
                if c.DISCOVERY_ALL_SPANS:
                    topo_params.append((c, all_spans, handle_type, remain_data))
                else:
                    topo_params.append((c, filter_spans, handle_type, remain_data))

            pool.map_ignore_exception(self._discover_handle, topo_params)

        logger.info(
            f"[TopoHandler] discover finished {self.bk_biz_id} {self.app_name} "
            f"trace count: {trace_id_count} all span count: {span_count} filter span count: {filter_span_count}"
            f"elapsed: {(datetime.datetime.now() - start).seconds}s"
        )
        return True
