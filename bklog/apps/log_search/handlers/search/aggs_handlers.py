# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import abc
import copy
import datetime
import operator
import typing
from collections import defaultdict

from elasticsearch_dsl import A, Search

from apps.log_search.constants import TimeFieldTypeEnum, TimeFieldUnitEnum
from apps.log_search.exceptions import DateHistogramException
from apps.log_search.handlers.search.search_handlers_esquery import (
    SearchHandler as SearchHandlerEsquery,
)
from apps.utils.local import get_local_param
from apps.utils.log import logger
from apps.utils.thread import MultiExecuteFunc
from apps.utils.time_handler import (
    DTEVENTTIMESTAMP_MULTIPLICATOR,
    generate_time_range,
    timestamp_to_timeformat,
)


class AggsBase(abc.ABC):
    @classmethod
    def terms(cls, index_set_id, query_data: dict):
        pass

    @classmethod
    def date_histogram(cls, index_set_id, query_data: dict):
        pass


class AggsHandlers(AggsBase):
    AGGS_BUCKET_SIZE = 100
    DEFAULT_ORDER = {"_count": "desc"}
    TIME_FORMAT = "yyyy-MM-dd HH:mm:ss"
    TIME_FORMAT_MAP = {
        "1m": "HH:mm",
        "5m": "HH:mm",
        "1h": "yyyy-MM-dd HH",
        "1d": "yyyy-MM-dd",
    }
    DATETIME_FORMAT_MAP = {"1m": "%H:%M", "5m": "%H:%M", "1h": "%Y-%m-%d %H", "1d": "%Y-%m-%d"}
    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    MIN_DOC_COUNT = 0

    def __init__(self):
        pass

    @classmethod
    def terms(cls, index_set_id, query_data: dict):
        """
        聚合搜索
        :param index_set_id: 索引集ID
        :param query_data: 聚合属性列表
        :return:
        """
        # 组合聚合查询字段
        query_data = copy.deepcopy(query_data)
        s = Search()
        s = cls._build_terms_aggs(
            s,
            query_data["fields"],
            query_data.get("size", cls.AGGS_BUCKET_SIZE),
            query_data.get("order", cls.DEFAULT_ORDER),
        )
        s = s.extra(size=0)
        query_data.update(s.to_dict())
        return SearchHandlerEsquery(index_set_id, query_data, only_for_agg=True).search(search_type=None)

    @classmethod
    def _build_terms_aggs(cls, s: Search, fields: list, size: int, order: dict) -> Search:
        for field in fields:
            if isinstance(field, list):
                s = cls._build_level_terms_aggs(s, field, size, order)
                continue
            # 字段为空时将其丢弃，防止构建出不合法的aggs
            if isinstance(field, str) and field == "":
                continue
            s = cls._build_not_level_terms_aggs(s, field, size, order)
        return s

    @classmethod
    def _build_not_level_terms_aggs(cls, s: Search, field: str, size: int, order: dict) -> Search:
        cls._build_terms_bucket(s.aggs, field, size, order)
        return s

    @classmethod
    def _build_level_terms_aggs(cls, s: Search, level_fields: typing.List[str], size: int, order: dict) -> Search:
        level_aggs = s.aggs
        for field in level_fields:
            level_aggs = cls._build_terms_bucket(level_aggs, field, size, order)
        return s

    @classmethod
    def _build_terms_bucket(cls, aggs, field: str, size: int, order: dict) -> Search:
        sub_aggs = {}
        extra_params = {}
        field_name = field
        if isinstance(field, dict):
            field_name = field.get("field_name")
            sub_fields = field.get("sub_fields")

            if "missing" in field:
                # 填充默认值
                extra_params["missing"] = field["missing"]

            if sub_fields:
                sub_aggs = cls._build_sub_terms_fields(sub_fields, size, order)
        terms = A("terms", field=field_name, size=size, order=order, aggs=sub_aggs, **extra_params)
        return aggs.bucket(field_name, terms)

    @classmethod
    def _build_sub_terms_fields(cls, sub_fields, size: int, order: dict):
        if not sub_fields:
            return
        if isinstance(sub_fields, dict):
            sub_fields = [sub_fields]
        aggs = {}
        for sub_field in sub_fields:
            field_name = sub_field
            extra_params = {}
            if isinstance(sub_field, dict):
                field_name = sub_field.get("field_name")
                sub_fields = sub_field.get("sub_fields")

                if "missing" in sub_field:
                    # 填充默认值
                    extra_params["missing"] = sub_field["missing"]

                if sub_fields:
                    aggs[field_name] = A(
                        "terms",
                        field=field_name,
                        size=size,
                        order=order,
                        aggs=cls._build_sub_terms_fields(sub_fields, size, order),
                        **extra_params,
                    )
                    continue
            aggs[field_name] = A("terms", field=field_name, size=size, order=order, **extra_params)
        return aggs

    @classmethod
    def date_histogram(cls, index_set_id, query_data: dict):
        query_data = copy.deepcopy(query_data)
        s = Search()
        # 按照日期时间聚合
        interval = query_data.get("interval")

        # 生成起止时间
        time_zone = get_local_param("time_zone")
        start_time, end_time = generate_time_range(
            query_data.get("time_range"), query_data.get("start_time"), query_data.get("end_time"), time_zone
        )

        if not interval or interval == "auto":
            interval = cls._init_default_interval(start_time, end_time)

        time_format = cls.TIME_FORMAT_MAP.get(interval, cls.TIME_FORMAT)
        datetime_format = cls.DATETIME_FORMAT_MAP.get(interval, cls.DATETIME_FORMAT)

        time_field, time_field_type, time_field_unit = SearchHandlerEsquery.init_time_field(index_set_id)
        # https://github.com/elastic/elasticsearch/issues/42270 非date类型不支持timezone, time format也无效
        if time_field_type == TimeFieldTypeEnum.DATE.value:
            min_value = int(start_time.timestamp()) * 1000
            max_value = int(end_time.timestamp()) * 1000
            date_histogram = A(
                "date_histogram",
                field=time_field,
                interval=interval,
                format=time_format,
                time_zone=time_zone,
                min_doc_count=cls.MIN_DOC_COUNT,
                extended_bounds={"min": min_value, "max": max_value},
            )
        else:
            num = 10**3
            if time_field_unit == TimeFieldUnitEnum.SECOND.value:
                num = 1
            elif time_field_unit == TimeFieldUnitEnum.MICROSECOND.value:
                num = 10**6
            min_value = int(start_time.timestamp()) * num
            max_value = int(end_time.timestamp()) * num
            date_histogram = A(
                "date_histogram",
                field=time_field,
                interval=interval,
                min_doc_count=cls.MIN_DOC_COUNT,
                extended_bounds={"min": min_value, "max": max_value},
            )

        aggs = s.aggs.bucket("group_by_histogram", date_histogram)
        cls._build_date_histogram_aggs(aggs, query_data["fields"], query_data.get("size", cls.AGGS_BUCKET_SIZE))
        s = s.extra(size=0)
        query_data.update(s.to_dict())
        logger.info(query_data)

        result = SearchHandlerEsquery(index_set_id, query_data, only_for_agg=True).search(search_type=None)
        if time_field_type != TimeFieldTypeEnum.DATE.value:
            buckets = result.get("aggregations", {}).get("group_by_histogram", {}).get("buckets", [])
            time_multiplicator = 1 / (10**3)
            if time_field_unit == TimeFieldUnitEnum.SECOND.value:
                time_multiplicator = 1
            elif time_field_unit == TimeFieldUnitEnum.MICROSECOND.value:
                time_multiplicator = 1 / (10**6)
            for _buckets in buckets:
                _buckets["key_as_string"] = timestamp_to_timeformat(
                    _buckets["key"], time_multiplicator=time_multiplicator, t_format=datetime_format, tzformat=False
                )

        return result

    @staticmethod
    def _init_default_interval(start_time: datetime, end_time: datetime):
        hour_interval = int((end_time - start_time).total_seconds() / 3600)
        if hour_interval <= 1:
            return "1m"
        elif hour_interval <= 6:
            return "5m"
        elif hour_interval <= 72:
            return "1h"
        else:
            return "1d"

    @classmethod
    def _build_date_histogram_aggs(cls, s: Search, fields: typing.List[dict], size) -> Search:
        for _field in fields:
            field_name = _field.get("term_filed")
            if not field_name:
                continue
            if isinstance(field_name, list):
                s = cls._build_level_date_histogram_aggs(s, _field, size)
                continue
            s = cls._build_not_level_date_histogram_aggs(s, _field, size)
        return s

    @classmethod
    def _build_level_date_histogram_aggs(cls, s: Search, field: dict, size: int) -> Search:
        field_list = field.get("term_filed")
        metric_type = field.get("metric_type")
        metric_field = field.get("metric_field")
        level_aggs = s
        for _field in field_list:
            level_aggs = cls._build_date_histogram_aggs_item(level_aggs, _field, metric_type, metric_field, size)
        return s

    @classmethod
    def _build_not_level_date_histogram_aggs(
        cls, s: Search, field, size: int
    ) -> Search:  # pylint: disable=function-name-too-long
        cls._build_date_histogram_aggs_item(
            s, field.get("term_filed"), field.get("metric_type"), field.get("metric_field"), size
        )
        return s

    @classmethod
    def _build_date_histogram_aggs_item(cls, aggs, field, metric_type, metric_field, size: int):
        terms = A("terms", field=field, size=size, min_doc_count=cls.MIN_DOC_COUNT)
        metric_aggs = aggs.bucket(field, terms)
        if metric_type:
            return metric_aggs.metric(field, metric_type, field=metric_field)
        return metric_aggs


class AggsViewAdapter(object):
    def __init__(self):
        self._aggs_handlers = AggsHandlers

    def terms(self, index_set_id, query_data: dict):
        terms_result = self._aggs_handlers.terms(index_set_id, query_data)
        aggs_result = terms_result.get("aggs", {})
        terms_data = defaultdict(dict)

        for _field in query_data["fields"]:
            field_agg_result = aggs_result.get(_field)
            if not field_agg_result:
                terms_data["aggs"].update({_field: []})
                terms_data["aggs_items"].update({_field: []})
                continue
            terms_data["aggs"].update({_field: field_agg_result})
            terms_data["aggs_items"].update(
                {_field: list(map(lambda item: item.get("key"), field_agg_result.get("buckets", [])))}
            )
        return terms_data

    def date_histogram(self, index_set_id, query_data: dict):
        histogram_result = self._aggs_handlers.date_histogram(index_set_id, query_data)
        histogram_data = histogram_result.get("aggs", {}).get("group_by_histogram", {})
        # 当返回的数据为空且包含failures字段时报错
        failures = histogram_result.get("_shards", {}).get("failures")
        if failures:
            logger.error(f"Get date_histogram error: {failures}")
            raise DateHistogramException(
                DateHistogramException.MESSAGE.format(index_set_id=index_set_id, err=failures[0]["reason"]["type"])
            )

        field_have_metric = {
            item["term_filed"]: True if item.get("metric_type") else False for item in query_data["fields"]
        }

        agg_fields = {field["term_filed"]: field["term_filed"] for field in query_data.get("fields")}
        # 按照fields返回数据
        return_data = {"aggs": {}}
        if not agg_fields:
            return_data["aggs"] = histogram_result.get("aggregations", {})
            return return_data

        histogram_dict = {}
        labels = []
        for _data in histogram_data.get("buckets", []):
            # labels 横坐标时间轴
            labels.append(_data.get("key_as_string"))

            # filed 查询结果
            for field in agg_fields.keys():
                _filed_key = field
                filed_data_dict = histogram_dict.get(_filed_key, {}).get("datasets", {})

                # 获取需要返回的指标key,如：doc_count, avg_key
                metric_key = "doc_count"
                # metric_agg: dict = aggs["group_by_histogram"]["aggs"].get(_filed_key, {}).get("aggs", {})
                if field_have_metric[_filed_key]:
                    metric_key = _filed_key

                # doc: key, count
                buckets = _data.get(field, {}).get("buckets", [])
                for _doc in buckets:
                    # 获取指标值和doc_count
                    if metric_key == "doc_count":
                        doc_count = doc_value = _doc.get("doc_count") or 0
                    else:
                        doc_count = _doc.get("doc_count") or 0
                        doc_value = int(_doc.get(metric_key, {}).get("value") or 0)

                    doc_key = _doc["key"]
                    if doc_key not in filed_data_dict:
                        filed_data_dict.update(
                            {
                                doc_key: {
                                    "label": _doc.get("key"),
                                    "data": [
                                        {
                                            "label": timestamp_to_timeformat(
                                                _data.get("key"), time_multiplicator=DTEVENTTIMESTAMP_MULTIPLICATOR
                                            ),
                                            "value": doc_value,
                                            "count": doc_count,
                                        }
                                    ],
                                }
                            }
                        )
                    else:
                        filed_data_dict[doc_key]["data"].append(
                            {
                                "label": timestamp_to_timeformat(
                                    _data.get("key"), time_multiplicator=DTEVENTTIMESTAMP_MULTIPLICATOR
                                ),
                                "value": doc_value,
                                "count": doc_count,
                            }
                        )

                histogram_dict.update({_filed_key: {"labels": labels, "datasets": filed_data_dict}})

        for _filed in agg_fields:
            filed_data = histogram_dict.get(_filed, None)
            if filed_data:
                return_data["aggs"].update(
                    {
                        agg_fields[_filed]: {
                            "labels": filed_data["labels"],
                            "datasets": list(filed_data["datasets"].values()),
                        }
                    }
                )
        return_data["aggs"] = self._del_empty_histogram(return_data["aggs"])
        return return_data

    @staticmethod
    def union_search_date_histogram(query_data: dict):
        index_set_ids = query_data.get("index_set_ids", [])

        # 多线程请求数据
        multi_execute_func = MultiExecuteFunc()

        for index_set_id in index_set_ids:
            params = {"index_set_id": index_set_id, "query_data": query_data}
            multi_execute_func.append(
                result_key=f"union_search_date_histogram_{index_set_id}",
                func=AggsViewAdapter().date_histogram,
                params=params,
                multi_func_params=True,
            )

        multi_result = multi_execute_func.run()

        buckets_info = dict()
        # 处理返回结果
        for index_set_id in index_set_ids:
            result = multi_result.get(f"union_search_date_histogram_{index_set_id}", {})
            aggs = result.get("aggs", {})
            if not aggs:
                continue
            buckets = aggs["group_by_histogram"]["buckets"]
            for bucket in buckets:
                key_as_string = bucket["key_as_string"]
                if key_as_string not in buckets_info:
                    buckets_info[key_as_string] = bucket
                else:
                    buckets_info[key_as_string]["doc_count"] += bucket["doc_count"]

        ret_data = (
            {"aggs": {"group_by_histogram": {"buckets": buckets_info.values()}}} if buckets_info else {"aggs": {}}
        )

        return ret_data

    @staticmethod
    def union_search_terms(query_data: dict):
        index_set_ids = query_data.get("index_set_ids", [])

        # 多线程请求数据
        multi_execute_func = MultiExecuteFunc()

        for index_set_id in index_set_ids:
            params = {"index_set_id": index_set_id, "query_data": query_data}
            multi_execute_func.append(
                result_key=f"union_search_terms_{index_set_id}",
                func=AggsViewAdapter().terms,
                params=params,
                multi_func_params=True,
            )

        multi_result = multi_execute_func.run()

        aggs_all = dict()
        aggs_items_all = dict()
        # 处理返回结果
        for index_set_id in index_set_ids:
            result = multi_result.get(f"union_search_terms_{index_set_id}", {})

            if not result:
                continue

            # 处理 aggs
            for key, value in result.get("aggs", {}).items():
                if not value or not isinstance(value, dict):
                    value = dict()
                if key not in aggs_all:
                    aggs_all[key] = value
                else:
                    try:
                        for v_kk, v_vv in value.items():
                            if isinstance(v_vv, int):
                                aggs_all[key][v_kk] += v_vv
                            elif isinstance(v_vv, list):
                                aggs_all[key][v_kk].extend(v_vv)
                    except Exception as e:  # pylint: disable=broad-except
                        logger.error(f"[union_search_terms error] e={e}")
                        continue

            # 处理 aggs_items
            for items_k, items_v in result.get("aggs_items", {}).items():
                if items_k not in aggs_items_all:
                    aggs_items_all[items_k] = items_v
                    continue
                elif isinstance(items_v, list):
                    aggs_items_all[items_k].extend(items_v)
                aggs_items_all[items_k] = list(set(aggs_items_all[items_k]))

        # buckets 合并排序
        for all_key, all_value in aggs_all.items():
            if not all_value or not isinstance(all_value, dict):
                continue
            buckets = all_value.get("buckets", [])
            if not buckets:
                continue
            buckets_info = dict()
            for bucket in buckets:
                bucket_key = bucket["key"]
                if bucket_key not in buckets_info:
                    buckets_info[bucket_key] = bucket
                else:
                    buckets_info[bucket_key]["doc_count"] += bucket["doc_count"]

            sorted_buckets = sorted(list(buckets_info.values()), key=operator.itemgetter("doc_count"), reverse=True)
            all_value["buckets"] = sorted_buckets

        return {"aggs": aggs_all, "aggs_items": aggs_items_all}

    def _del_empty_histogram(self, aggs):
        """
        将对应data.count为空的label去除
        @param aggs [Dict] 聚合检索处理后的结果
        {
            "tags.result_code":{
                "labels":[
                    "16:48",
                    "16:49",
                    "16:50",
                    "16:51",
                    "16:52",
                    "16:53"
                ],
                "datasets":[
                    {
                        "label":972,
                        "data":[
                            {
                                "label":"2021-06-22 16:48:00",
                                "value":0,
                                "count":0
                            }
                        ]
                    }
                ]
            }
        }
        """
        for agg in aggs.values():
            datasets = copy.deepcopy(agg["datasets"])
            for dataset in datasets:
                for index, data in enumerate(dataset["data"]):
                    if data["count"] or data["value"]:
                        break
                    if index == len(dataset["data"]) - 1:
                        agg["datasets"].remove(dataset)

        return aggs
