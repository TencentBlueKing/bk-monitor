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
import hashlib
import json

from django.utils.translation import gettext_lazy as _
from elasticsearch_dsl import Q

from alarm_backends.core.storage.redis import Cache
from apm.constants import DISCOVER_BATCH_SIZE
from apm.core.handlers.query.base import EsQueryBuilderMixin, LogicSupportOperator
from apm.core.handlers.query.define import QueryStatisticsMode
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import OtlpKey

AFTER_CACHE_KEY_EXPIRE = 60 * 60 * 24 * 1

redis_cli = Cache("cache")


class Deque:
    def __init__(self, params_md5):
        deque_key = f"monitor:apm:statistics:deque:{params_md5}"
        self.cache_key = deque_key
        self.redis_client = redis_cli

    @property
    def length(self):
        if not self.redis_client.exists(self.cache_key):
            return 0

        return self.redis_client.llen(self.cache_key)

    def extend(self, item_list):
        json_list = [json.dumps(i) for i in item_list]
        self.redis_client.rpush(self.cache_key, *json_list)
        # 续期
        self.redis_client.expire(self.cache_key, AFTER_CACHE_KEY_EXPIRE)

    def popleft(self):
        self.redis_client.lpop(self.cache_key)

    def pop_data(self, limit):
        list_data = []
        if self.length == 0:
            return list_data

        for _i in range(limit):
            item = self.redis_client.lpop(self.cache_key)
            if item:
                list_data.append(item)

        return [json.loads(i) for i in list_data]


class StatisticsQuery(EsQueryBuilderMixin):
    DEFAULT_SORT_FIELD = "end_time"
    LOGIC_FILTER_ALLOW_KEYS = ["root_span", "root_service_span"]
    LOGIC_FILTER_KEY_MAPPING = {
        "root_span": {"span_name": "root_span_name", "service_name": "root_span_service", "kind": "root_span_kind"},
        "root_service_span": {
            "span_name": "root_service_span_name",
            "service_name": "root_service",
            "kind": "root_service_kind",
        },
    }
    LOGIC_FILTER_KEY_ID_MAPPING = {"root_span": "root_span_id", "root_service_span": "root_service_span_id"}

    # 当每批超过1000条数据时 需要进行并发查询
    SPLIT_SPAN_COUNT_SIZE_LIMIT = 1000
    # 需要将总数量切分几段出来
    SPLIT_SPAN_BATCH_SIZE = 5

    GROUP_MODE_KEY_MAPPING = {
        QueryStatisticsMode.SPAN_NAME: "span_name",
        QueryStatisticsMode.SERVICE: "resource.service.name",
    }

    GROUP_KEY_CONFIG = {
        QueryStatisticsMode.SPAN_NAME: [
            {"group_key": "span_name", "display_key": "span_name"},
            {"group_key": "resource.service.name", "display_key": "service_name"},
            {"group_key": "kind", "display_key": "kind"},
        ],
        QueryStatisticsMode.SERVICE: [
            {"group_key": "resource.service.name", "display_key": "service_name"},
            {
                "group_key": "kind",
                "display_key": "kind",
            },
        ],
    }

    def __init__(self, trace_query, span_query):
        self.trace_query = trace_query
        self.span_query = span_query

    def query_statistics(self, query_mode, start_time, end_time, limit, offset, filters=None, es_dsl=None):
        return self._new_query_statistics_by_group(query_mode, start_time, end_time, limit, offset, filters, es_dsl)

    def _new_query_statistics_by_group(self, group_key, start_time, end_time, limit, offset, filters=None, es_dsl=None):
        query = self.span_query.search

        if es_dsl:
            query = query.update_from_dict(es_dsl)

        query = self.add_time(query, start_time, end_time)
        logic_filters, es_filters = self._parse_filters(filters)
        if es_filters:
            # 使用span_query进行添加
            query = self.span_query.add_filter_params(query, es_filters)
        query = self.add_sort(query)

        k = f"{group_key}:{start_time}{end_time}{limit}{filters}{es_dsl}"
        param_md5 = str(hashlib.md5(k.encode()).hexdigest())

        return self._query_data(
            group_key, query.to_dict(), start_time, end_time, offset, limit, param_md5, logic_filters
        )

    def _query_data(self, group_key, query_params, start_time, end_time, offset, limit, params_md5, logic_filters):
        es_query = self.span_query.search
        es_query = es_query.update_from_dict(query_params)

        # 获取分页游标
        after_key_params = self.get_after_key_param(offset, params_md5)

        # 不包含 根span、服务入口span 或者 查询统计视角等于service 时, 直接分组获取指标数据
        if not logic_filters or group_key == QueryStatisticsMode.SERVICE:
            return self._query_metric_data(es_query, group_key, offset, limit, params_md5, after_key_params)

        # step1 获取分组信息
        group_key_mapping = self._query_group_info(es_query, group_key, limit, after_key_params)
        # step2 获取specific_span_ids
        specific_span_ids = self._batch_query_specific_span_ids(start_time, end_time, group_key_mapping, logic_filters)
        # step3 从 span 中获取数据
        if not specific_span_ids:
            return []

        specific_q = self._build_specific_query(query_params, specific_span_ids)
        return self._query_metric_data(specific_q, group_key, offset, limit, params_md5, after_key_params)

    def _query_group_info(self, query, group_key, limit, after_key_params):
        query = query.extra(size=0)
        query = query.update_from_dict(
            {
                "aggs": {
                    "group": {
                        "composite": {
                            **after_key_params,
                            "size": limit,
                            "sources": [
                                {i["display_key"]: {"terms": {"field": i["group_key"]}}}
                                for i in self.GROUP_KEY_CONFIG[group_key]
                            ],
                        }
                    }
                }
            }
        )
        response = query.execute()
        results = response.to_dict()
        # 分组信息
        buckets = results["aggregations"]["group"]["buckets"]
        group_key_mapping = {item["display_key"]: set() for item in self.GROUP_KEY_CONFIG[group_key]}
        for bucket in buckets:
            for i in self.GROUP_KEY_CONFIG[group_key]:
                display_key = i["display_key"]
                group_key_mapping[display_key].add(bucket["key"][display_key])

        return group_key_mapping

    def _query_metric_data(self, query, group_key, offset, limit, params_md5, after_key_params):
        query = query.extra(size=0)
        query = query.update_from_dict(
            {
                "aggs": {
                    "group": {
                        "composite": {
                            **after_key_params,
                            "size": limit,
                            "sources": [
                                {i["display_key"]: {"terms": {"field": i["group_key"]}}}
                                for i in self.GROUP_KEY_CONFIG[group_key]
                            ],
                        },
                        "aggs": self.get_metric_aggs(group_key),
                    }
                }
            }
        )

        response = query.execute()
        results = response.to_dict()

        after_key = results["aggregations"]["group"].get("after_key")
        if after_key:
            redis_cli.set(f"{params_md5}:{offset + limit}", json.dumps(after_key), AFTER_CACHE_KEY_EXPIRE)

        buckets = response.aggregations.group.buckets
        results = []
        for bucket in buckets:
            total_count = bucket.total_count.value
            error_count = bucket.error_count.count.value
            error_rate = round(error_count / total_count, 2)
            avg_duration = round(bucket.avg_duration.value, 2)
            p50_duration = round(bucket.p50_duration.values["50.0"], 2)
            p90_duration = round(bucket.p90_duration.values["90.0"], 2)
            results.append(
                {
                    **bucket.key.to_dict(),
                    "span_count": total_count,
                    "error_count": error_count,
                    "error_rate": error_rate,
                    "avg_duration": avg_duration,
                    "p50_duration": p50_duration,
                    "p90_duration": p90_duration,
                    "source": "opentelemetry",
                }
            )
        return results

    def _build_specific_query(self, query_params, specific_span_ids):
        es_query = self.span_query.search
        es_query = es_query.update_from_dict(query_params)
        es_query = es_query.update_from_dict({"size": 0})
        specific_q = es_query.query("bool", filter=[Q("terms", span_id=specific_span_ids)])
        return specific_q

    @classmethod
    def get_after_key_param(cls, offset, params_md5):
        after_key = None
        if offset != 0:
            cache_key = f"{params_md5}:{offset}"
            if not redis_cli.exists(cache_key):
                raise ValueError(_("参数丢失 需要重新从第一页获取"))
            cache_value = redis_cli.get(cache_key)
            if cache_value:
                after_key = json.loads(cache_value)

        return {"after": after_key} if after_key else {}

    def get_metric_aggs(self, group_key):
        metric_aggs = {
            "total_count": {"value_count": {"field": self.GROUP_MODE_KEY_MAPPING[group_key]}},
            "error_count": {
                "filter": {"bool": {"must_not": [{"term": {OtlpKey.STATUS_CODE: 0}}]}},
                "aggs": {"count": {"value_count": {"field": OtlpKey.STATUS_CODE}}},
            },
            "avg_duration": {"avg": {"field": OtlpKey.ELAPSED_TIME}},
            "p50_duration": {"percentiles": {"field": OtlpKey.ELAPSED_TIME, "percents": [50]}},
            "p90_duration": {"percentiles": {"field": OtlpKey.ELAPSED_TIME, "percents": [90]}},
        }
        return metric_aggs

    def _get_specific_span_ids(self, start_time, end_time, logic_name, filter_map):
        t_q = self.trace_query.search
        t_q = self.add_time(t_q, start_time, end_time, time_field=self.trace_query.DEFAULT_SORT_FIELD)
        t_q = self.trace_query.add_app_filter(t_q)

        field_span_id = self.LOGIC_FILTER_KEY_ID_MAPPING[logic_name]
        logic_span_map = self.LOGIC_FILTER_KEY_MAPPING[logic_name]
        filter_param = {logic_span_map.get(k): v for k, v in filter_map.items() if logic_span_map.get(k)}

        t_q = t_q.query("bool", filter=[Q("terms", **{k: list(v)}) for k, v in filter_param.items()])
        t_q = t_q.update_from_dict({"_source": [field_span_id], "size": DISCOVER_BATCH_SIZE})

        t_q_response = t_q.execute()
        specific_span_ids = [i.to_dict()[field_span_id] for i in t_q_response.hits]

        return specific_span_ids

    def _batch_query_specific_span_ids(self, start_time, end_time, group_key_mapping, logic_filters):
        pool = ThreadPool()
        params = [(start_time, end_time, logic_name, group_key_mapping) for logic_name in logic_filters]
        results = pool.map_ignore_exception(self._get_specific_span_ids, params)
        specific_span_ids = {span_id for result in results if result for span_id in result}
        return list(specific_span_ids)

    def _query_statistics_by_group(self, group_key, start_time, end_time, limit, offset, filters=None, es_dsl=None):
        query = self.span_query.search

        if es_dsl:
            query = query.update_from_dict(es_dsl)

        query = self.add_time(query, start_time, end_time)
        logic_filters, es_filters = self._parse_filters(filters)
        if es_filters:
            # 使用span_query进行添加
            query = self.span_query.add_filter_params(query, es_filters)
        query = self.add_sort(query)

        k = f"{group_key}:{start_time}{end_time}{limit}{filters}{es_dsl}"
        param_md5 = str(hashlib.md5(k.encode()).hexdigest())

        data_generator = self._batch_query(
            group_key,
            query.to_dict(),
            start_time,
            end_time,
            offset,
            limit,
            param_md5,
            es_filters,
            es_dsl,
            logic_filters,
        )

        deque = Deque(param_md5)

        while deque.length < limit:

            try:
                processed_batch = next(data_generator)
            except StopIteration:
                break

            if processed_batch:
                # 单端队列存储溢出的结果
                deque.extend(processed_batch)

        return deque.pop_data(limit)

    def balanced_biscuit(self, input_list, num_splits):
        """切分"""
        split_size = len(input_list) // num_splits
        remainder = len(input_list) % num_splits
        result = []
        current_index = 0

        for i in range(num_splits):
            current_split_size = split_size + int(i < remainder)
            result.append(input_list[current_index : current_index + current_split_size])
            current_index += current_split_size

        return result

    def _batch_query(
        self,
        group_key,
        query_params,
        start_time,
        end_time,
        offset,
        limit,
        params_md5,
        es_filters,
        es_dsl,
        logic_filters,
    ):

        after_key = None
        if offset != 0:
            cache_key = f"{params_md5}:{offset}"
            if not redis_cli.exists(cache_key):
                raise ValueError(_("参数丢失 需要重新从第一页获取"))
            after_key = json.loads(redis_cli.get(cache_key))

        after_key_params = {"after": after_key} if after_key else {}
        q = self.span_query.search
        q = q.update_from_dict(query_params)
        q = q.update_from_dict({"size": 0})
        q = q.update_from_dict(
            {
                "aggs": {
                    "group": {
                        "composite": {
                            **after_key_params,
                            "size": limit,
                            "sources": [
                                {i["display_key"]: {"terms": {"field": i["group_key"]}}}
                                for i in self.GROUP_KEY_CONFIG[group_key]
                            ],
                        }
                    }
                }
            }
        )

        while True:

            results = q.execute()
            results = results.to_dict()
            groups = results["aggregations"]["group"]["buckets"]
            if not groups:
                break

            batch_group_values = []
            for i in groups:

                mapping = {}

                for j in self.GROUP_KEY_CONFIG[group_key]:
                    mapping[j["group_key"]] = i["key"][j["display_key"]]

                batch_group_values.append({"query": mapping, "display": i["key"]})

            after_key = results["aggregations"]["group"]["after_key"]
            redis_cli.set(f"{params_md5}:{offset + limit}", json.dumps(after_key), AFTER_CACHE_KEY_EXPIRE)

            batch = self._fetch_spans(
                group_key, start_time, end_time, batch_group_values, es_filters, es_dsl, logic_filters
            )

            after_key = results["aggregations"]["group"]["after_key"]
            redis_cli.set(f"{params_md5}:{offset + limit}", json.dumps(after_key), AFTER_CACHE_KEY_EXPIRE)
            q = q.update_from_dict(
                {
                    "aggs": {
                        "group": {
                            "composite": {
                                "after": after_key,
                                "size": limit,
                                "sources": [
                                    {i["display_key"]: {"terms": {"field": i["group_key"]}}}
                                    for i in self.GROUP_KEY_CONFIG[group_key]
                                ],
                            }
                        }
                    }
                }
            )
            tmp_q = self.span_query.search
            tmp_q.update_from_dict(q.to_dict())
            q = tmp_q

            yield batch

    def _fetch_by_span_ids(self, log_filter, specific_span_ids, group_value_mapping, start_time, end_time):

        convert_rule = self.LOGIC_FILTER_KEY_MAPPING[log_filter]
        convert_group_value_mapping = {}
        for k, v in group_value_mapping.items():
            convert_group_value_mapping[convert_rule[k]] = v

        t_q = self.trace_query.search
        t_q = self.add_time(t_q, start_time, end_time, time_field=self.trace_query.DEFAULT_SORT_FIELD)
        t_q = self.trace_query.add_app_filter(t_q)

        field_span_id = self.LOGIC_FILTER_KEY_ID_MAPPING[log_filter]
        t_q = t_q.query(
            "bool",
            must=[
                Q("terms", **{field_span_id: specific_span_ids}),
            ]
            + [Q("term", **{k: v}) for k, v in convert_group_value_mapping.items()],
        )
        t_q = t_q.update_from_dict({"_source": [field_span_id], "size": DISCOVER_BATCH_SIZE})
        t_q_response = t_q.execute()
        return [i.to_dict()[field_span_id] for i in t_q_response.hits]

    @property
    def _logic_filters_handler_mapping(self):
        return {
            QueryStatisticsMode.SPAN_NAME: self._fetch_span_name_logic_filters,
        }

    def _fetch_by_group(self, group_key, group_value_mapping, start_time, end_time, es_filters, es_dsl, logic_filters):
        specific_span_ids = []
        if logic_filters:
            specific_span_ids = self._logic_filters_handler_mapping.get(group_key, lambda *_: [])(
                start_time, end_time, logic_filters, group_value_mapping["display"]
            )
            if not specific_span_ids:
                return []

        q = self.span_query.search
        if es_filters:
            q = self.span_query.add_filter_params(q, es_filters)
        if es_dsl:
            q = q.update_from_dict(es_dsl)
        q = self.add_time(q, start_time, end_time)

        if not logic_filters:
            q = q.query("bool", must=[Q("term", **{k: v}) for k, v in group_value_mapping["query"].items()])
        else:
            q = q.query("bool", must=[Q("terms", span_id=list(set(specific_span_ids)))])

        metrics = self._calculate_metrics(group_key, q)
        if not metrics:
            return None

        return {**metrics, **group_value_mapping["display"]}

    def _calculate_metrics(self, group_key, query):
        # 计算指标

        query = query.extra(size=0)

        query = query.update_from_dict(
            {
                "aggs": {
                    "total_count": {"value_count": {"field": self.GROUP_MODE_KEY_MAPPING[group_key]}},
                    "error_count": {
                        "filter": {"bool": {"must_not": [{"term": {OtlpKey.STATUS_CODE: 0}}]}},
                        "aggs": {"count": {"value_count": {"field": OtlpKey.STATUS_CODE}}},
                    },
                    "avg_duration": {"avg": {"field": OtlpKey.ELAPSED_TIME}},
                    "p50_duration": {"percentiles": {"field": OtlpKey.ELAPSED_TIME, "percents": [50]}},
                    "p90_duration": {"percentiles": {"field": OtlpKey.ELAPSED_TIME, "percents": [90]}},
                }
            }
        )

        response = query.execute()

        # 总数量
        total_count = response.aggregations.total_count.value
        if not total_count:
            return {}

        # 错误数
        error_count = response.aggregations.error_count.count.value
        # 错误率
        error_rate = round(error_count / total_count, 2)
        # 平均耗时
        avg_duration = round(response.aggregations.avg_duration.value, 2)
        # P50
        p50_duration = round(response.aggregations.p50_duration.values["50.0"], 2)
        # P90
        p90_duration = round(response.aggregations.p90_duration.values["90.0"], 2)

        return {
            "span_count": total_count,
            "error_count": error_count,
            "error_rate": error_rate,
            "avg_duration": avg_duration,
            "p50_duration": p50_duration,
            "p90_duration": p90_duration,
            "source": "opentelemetry",
        }

    def _fetch_span_name_logic_filters(self, start_time, end_time, logic_filters, group_value_mapping):

        convert_group_value_mapping = {}
        convert_rule = self.LOGIC_FILTER_KEY_MAPPING[logic_filters[0]]
        for k, v in group_value_mapping.items():
            convert_group_value_mapping[convert_rule[k]] = v

        # 如果有逻辑过滤字段
        t_q = self.trace_query.search
        t_q = self.add_time(t_q, start_time, end_time, time_field=self.trace_query.DEFAULT_SORT_FIELD)
        t_q = self.trace_query.add_app_filter(t_q)

        field_span_id = self.LOGIC_FILTER_KEY_ID_MAPPING[logic_filters[0]]
        t_q = t_q.query("bool", must=[Q("term", **{k: v}) for k, v in convert_group_value_mapping.items()])
        t_q = t_q.update_from_dict({"_source": [field_span_id], "size": DISCOVER_BATCH_SIZE})
        t_q_response = t_q.execute()
        specific_span_ids = [i.to_dict()[field_span_id] for i in t_q_response.hits]

        if len(logic_filters) != 1 and specific_span_ids:
            # 如果全部勾选 需要跟进第一次查询出的SpanId结果再使用In查询保证Span是同一个
            logic_filter = logic_filters[1]
            if len(specific_span_ids) >= self.SPLIT_SPAN_COUNT_SIZE_LIMIT:
                pool = ThreadPool()
                params = [
                    (logic_filter, batch_specific_span_ids, group_value_mapping, start_time, end_time)
                    for batch_specific_span_ids in self.balanced_biscuit(specific_span_ids, self.SPLIT_SPAN_BATCH_SIZE)
                ]
                results = pool.map_ignore_exception(self._fetch_by_span_ids, params)
                tmp_span_ids = []
                for result in results:
                    if result:
                        tmp_span_ids += result
                specific_span_ids = tmp_span_ids

            else:
                specific_span_ids = self._fetch_by_span_ids(
                    logic_filter, specific_span_ids, group_value_mapping, start_time, end_time
                )

        return specific_span_ids

    def _fetch_spans(self, group_key, start_time, end_time, group_values, es_filters, es_dsl, logic_filters):

        pool = ThreadPool()
        params = [(group_key, i, start_time, end_time, es_filters, es_dsl, logic_filters) for i in group_values]
        results = pool.map_ignore_exception(self._fetch_by_group, params)

        res = []
        for result in results:
            if result:
                res.append(result)

        return res

    def _parse_filters(self, filters):
        # filters中可能保存特殊逻辑的查询 需要进行分离
        logic_filters = []
        es_filters = []
        if not filters:
            return logic_filters, es_filters

        for item in filters:
            if item["operator"] == LogicSupportOperator.LOGIC:
                # 对于统计 只有根Span、服务入口Span需要走特殊逻辑
                if item["key"] not in self.LOGIC_FILTER_ALLOW_KEYS:
                    raise ValueError(_("不支持的过滤KEY: %s").format(item['key']))
                logic_filters.append(item["key"])
            else:
                es_filters.append(item)

        return logic_filters, es_filters
