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
import copy
from typing import Any, Dict

from django.conf import settings

from apps.api import UnifyQueryApi
from apps.log_esquery.esquery.builder.query_string_builder import QueryStringBuilder
from apps.log_esquery.exceptions import BaseSearchIndexSetException
from apps.log_search.constants import TimeFieldTypeEnum, TimeFieldUnitEnum
from apps.log_search.handlers.index_set import BaseIndexSetHandler
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.models import LogIndexSet, LogIndexSetData, Scenario
from apps.log_unifyquery.constants import (
    BASE_OP_MAP,
    FLOATING_NUMERIC_FIELD_TYPES,
    OP_TRANSFORMER,
    REFERENCE_ALIAS,
)
from apps.utils.local import get_local_param
from apps.utils.log import logger
from apps.utils.lucene import EnhanceLuceneAdapter


class UnifyQueryHandler(object):
    def __init__(self, params):
        self.search_params: Dict[str, Any] = params

        # 必需参数，索引集id列表
        self.index_set_ids = self.search_params["index_set_ids"]

        # 必需参数，业务id
        self.bk_biz_id = self.search_params["bk_biz_id"]

        # 查询语句
        self.query_string = self.search_params.get("keyword", "")
        self.origin_query_string: str = self.search_params.get("keyword")
        self._enhance()
        self.query_string = QueryStringBuilder(self.query_string).query_string

        # 聚合查询：字段名称
        self.agg_field = self.search_params.get("agg_field", "")

        # 排序参数
        self.order_by = self.search_params.get("sort_list", [])

        # 是否为联合查询
        self.is_multi_rt: bool = len(self.index_set_ids) > 1

        # 查询时间范围
        self.start_time = self.search_params["start_time"]
        self.end_time = self.search_params["end_time"]

        # 基础查询参数初始化
        self.base_dict = self.init_base_dict()

    def _enhance(self):
        """
        语法增强
        """
        if self.query_string is not None:
            enhance_lucene_adapter = EnhanceLuceneAdapter(query_string=self.query_string)
            self.query_string = enhance_lucene_adapter.enhance()

    @staticmethod
    def init_time_field(index_set_id: int, scenario_id: str = None) -> tuple:
        """
        初始化时间字段信息
        """
        if not scenario_id:
            scenario_id = LogIndexSet.objects.filter(index_set_id=index_set_id).first().scenario_id
        # get timestamp field
        if scenario_id in [Scenario.BKDATA, Scenario.LOG]:
            return "dtEventTimeStamp", TimeFieldTypeEnum.DATE.value, TimeFieldUnitEnum.SECOND.value
        else:
            log_index_set_obj = LogIndexSet.objects.filter(index_set_id=index_set_id).first()
            time_field = log_index_set_obj.time_field
            time_field_type = log_index_set_obj.time_field_type
            time_field_unit = log_index_set_obj.time_field_unit
            if time_field:
                return time_field, time_field_type, time_field_unit
            index_set_obj: LogIndexSetData = LogIndexSetData.objects.filter(index_set_id=index_set_id).first()
            if not index_set_obj:
                raise BaseSearchIndexSetException(BaseSearchIndexSetException.MESSAGE.format(index_set_id=index_set_id))
            time_field = index_set_obj.time_field
            return time_field, TimeFieldTypeEnum.DATE.value, TimeFieldUnitEnum.SECOND.value

    def init_default_interval(self):
        """
        初始化聚合周期
        """
        if not self.start_time or not self.end_time:
            # 兼容查询时间段为默认近十五分钟的情况
            return "1m"
        hour_interval = (int(self.end_time) - int(self.start_time)) / 3600
        if hour_interval <= 1:
            return "1m"
        elif hour_interval <= 6:
            return "5m"
        elif hour_interval <= 24 * 3:
            return "1h"
        else:
            return "1d"

    def init_base_dict(self):
        # 自动周期转换
        if self.search_params.get("interval", "auto") == "auto":
            interval = self.init_default_interval()
        else:
            interval = self.search_params["interval"]

        index_set_list = list(
            LogIndexSet.objects.filter(index_set_id__in=self.search_params.get("index_set_ids", [])).values(
                "index_set_id", "scenario_id"
            )
        )

        # 拼接查询参数列表
        query_list = []
        for index, index_set in enumerate(index_set_list):
            query_dict = {
                "query_string": self.query_string,
                "data_source": settings.UNIFY_QUERY_DATA_SOURCE,
                "table_id": BaseIndexSetHandler.get_data_label(index_set["scenario_id"], index_set["index_set_id"]),
                "reference_name": REFERENCE_ALIAS[index],
                "dimensions": [],
                "time_field": "time",
                "conditions": self.transform_additions(),
                "function": [],
            }

            if self.agg_field:
                query_dict["field_name"] = self.agg_field
            else:
                # 时间字段 & 类型 & 单位
                time_field, time_field_type, time_field_unit = SearchHandler.init_time_field(index_set["index_set_id"])
                query_dict["field_name"] = time_field

            query_list.append(query_dict)

        return {
            "query_list": query_list,
            "metric_merge": " + ".join([query["reference_name"] for query in query_list]),
            "order_by": self.order_by,
            "step": interval,
            "start_time": str(self.start_time),
            "end_time": str(self.end_time),
            "down_sample_range": "",
            "timezone": get_local_param("time_zone", settings.TIME_ZONE),
            "bk_biz_id": self.bk_biz_id,
        }

    @staticmethod
    def query_ts(search_dict, raise_exception=True):
        """
        查询时序型数据
        """
        try:
            return UnifyQueryApi.query_ts(search_dict)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("query ts error: %s, search params: %s", e, search_dict)
            if raise_exception:
                raise e

    @staticmethod
    def query_ts_reference(search_dict, raise_exception=False):
        """
        查询非时序型数据
        """
        try:
            return UnifyQueryApi.query_ts_reference(search_dict)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("query ts reference error: %s, search params: %s", e, search_dict)
            if raise_exception:
                raise e
            return {"series": []}

    def transform_additions(self):
        field_list = []
        condition_list = []
        for addition in self.search_params.get("addition", []):
            if addition["operator"] in BASE_OP_MAP:
                field_list.append(
                    {
                        "field_name": addition["field"],
                        "op": BASE_OP_MAP[addition["operator"]],
                        "value": addition["value"] if isinstance(addition["value"], list)
                        else addition["value"].split(","),
                    }
                )
            else:
                transformer = OP_TRANSFORMER[addition["operator"]]
                new_field_list, new_condition_list = transformer(addition)
                field_list.extend(new_field_list)
                condition_list.extend(new_condition_list)
            if len(field_list) > 1:
                condition_list.append("and")
        return {"field_list": field_list, "condition_list": condition_list}

    @staticmethod
    def handle_count_data(data, digits=None):
        if data.get("series", []):
            series = data["series"][0]
            return round(series["values"][0][1], digits)
        elif data.get("status", {}):
            # 普通异常信息日志记录，暂不抛出异常
            error_code = data["status"].get("code", "")
            error_message = data["status"].get("message", "")
            logger.exception("query ts reference error code: %s, message: %s", error_code, error_message)
        return 0

    def get_total_count(self):
        search_dict = copy.deepcopy(self.base_dict)
        reference_list = []
        for query in search_dict["query_list"]:
            query["function"] = [{"method": "count"}]
            reference_list.append(query["reference_name"])
        search_dict.update({"metric_merge": " + ".join(reference_list)})
        data = self.query_ts_reference(search_dict)
        return self.handle_count_data(data)

    def get_field_count(self):
        search_dict = copy.deepcopy(self.base_dict)
        reference_list = []
        for query in search_dict["query_list"]:
            if len(query["conditions"]["field_list"]) > 0:
                query["conditions"]["condition_list"].append("and")
            query["conditions"]["field_list"].append(
                {"field_name": self.search_params["agg_field"], "value": [""], "op": "ncontains"}
            )
            query["function"] = [{"method": "count"}]
            reference_list.append(query["reference_name"])
        search_dict.update({"metric_merge": " + ".join(reference_list)})
        data = self.query_ts_reference(search_dict)
        return self.handle_count_data(data)

    def get_bucket_count(self, start: int, end: int):
        search_dict = copy.deepcopy(self.base_dict)
        search_dict.update({"metric_merge": "a"})
        for query in search_dict["query_list"]:
            if len(query["conditions"]["field_list"]) > 0:
                query["conditions"]["condition_list"].extend(["and"] * 2)
            else:
                query["conditions"]["condition_list"].extend(["and"])
            query["conditions"]["field_list"].extend(
                [
                    {"field_name": self.search_params["agg_field"], "value": [str(start)], "op": "gte"},
                    {"field_name": self.search_params["agg_field"], "value": [str(end)], "op": "lte"},
                ]
            )
            query["function"] = [{"method": "count"}]
        data = self.query_ts_reference(search_dict)
        return self.handle_count_data(data)

    def get_distinct_count(self):
        search_dict = copy.deepcopy(self.base_dict)
        data = {}
        if self.is_multi_rt:
            reference_list = []
            for query in search_dict["query_list"]:
                query["time_aggregation"] = {"function": "count_over_time", "window": search_dict["step"]}
                query["function"] = [{"method": "sum", "dimensions": [self.search_params["agg_field"]]}]
                reference_list.append(query["reference_name"])
            metric_merge = "count(" + " or ".join(reference_list) + ")"
            search_dict.update({"metric_merge": metric_merge, "instant": True})
            data = self.query_ts_reference(search_dict)
        else:
            for query in search_dict["query_list"]:
                query["function"] = [{"method": "cardinality"}]
                search_dict.update({"metric_merge": "a"})
                data = self.query_ts_reference(search_dict, raise_exception=True)
        return self.handle_count_data(data)

    def get_topk_ts_data(self, vargs: int = 5):
        topk_group_values = [group[0] for group in self.get_topk_list()]
        search_dict = copy.deepcopy(self.base_dict)
        search_dict.update({"metric_merge": "a"})
        for query in search_dict["query_list"]:
            query["time_aggregation"] = {"function": "count_over_time", "window": search_dict["step"]}
            query["function"] = [
                {"method": "sum", "dimensions": [self.search_params["agg_field"]]},
                {"method": "topk", "vargs_list": [vargs]},
            ]
            if not topk_group_values:
                continue
            if len(query["conditions"]["field_list"]) > 0:
                query["conditions"]["condition_list"].extend(["and"])
            query["conditions"]["field_list"].append(
                {"field_name": self.search_params["agg_field"], "value": topk_group_values, "op": "eq"}
            )
        data = self.query_ts(search_dict)
        return data

    def get_agg_value(self, agg_method: str):
        search_dict = copy.deepcopy(self.base_dict)
        search_dict.update({"metric_merge": "a"})
        for query in search_dict["query_list"]:
            if agg_method == "median":
                query["function"] = [{"method": "percentiles", "vargs_list": [50]}]
            else:
                query["function"] = [{"method": agg_method}]
        data = self.query_ts_reference(search_dict)
        return self.handle_count_data(data, digits=2)

    def get_topk_list(self, limit: int = 5):
        search_dict = copy.deepcopy(self.base_dict)
        reference_list = []
        for query in search_dict["query_list"]:
            query["limit"] = limit
            query["function"] = [{"method": "count", "dimensions": [self.search_params["agg_field"]]}]
            reference_list.append(query["reference_name"])
        search_dict.update({"order_by": ["-_value"], "metric_merge": " or ".join(reference_list)})
        data = self.query_ts_reference(search_dict)
        series = data["series"]
        return sorted(
            [[s["group_values"][0], s["values"][0][1]] for s in series[:limit]], key=lambda x: x[1], reverse=True
        )

    def get_bucket_data(self, min_value: int, max_value: int, bucket_range: int = 10):
        # 浮点数分桶区间精度默认为两位小数
        digits = None
        if self.search_params.get("field_type") and self.search_params["field_type"] in FLOATING_NUMERIC_FIELD_TYPES:
            digits = 2
        step = round((max_value - min_value) / bucket_range, digits)
        bucket_data = []
        for index in range(bucket_range):
            start = min_value + index * step
            end = start + step if index < bucket_range - 1 else max_value
            bucket_count = self.get_bucket_count(start, end)
            bucket_data.append([start, bucket_count])
        return bucket_data
