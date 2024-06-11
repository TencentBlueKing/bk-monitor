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
from apps.log_unifyquery.constants import BASE_OP_MAP, OP_TRANSFORMER, REFERENCE_ALIAS
from apps.utils.local import get_local_param
from apps.utils.log import logger


class UnifyQueryHandler(object):
    def __init__(self, params):
        self.search_params: Dict[str, Any] = params
        self.start_time = params["start_time"]
        self.end_time = params["end_time"]
        self.base_dict = self.init_base_dict()
        self.is_union_search: bool = len(params.get("result_table_ids", [])) > 1

    def init_default_interval(self):
        # 兼容查询时间段为默认近十五分钟的情况
        if not self.start_time or not self.end_time:
            return "1m"
        hour_interval = (int(self.end_time) - int(self.start_time)) / 3600
        if hour_interval <= 1:
            return "1m"
        elif hour_interval <= 6:
            return "5m"
        elif hour_interval <= 72:
            return "1h"
        else:
            return "1d"

    def init_base_dict(self):
        # 自动周期转换
        if self.search_params.get("interval", "auto") == "auto":
            interval = self.init_default_interval()
        else:
            interval = self.search_params["interval"]

        # 拼接查询参数列表
        query_list = [
            {
                "query_string": self.search_params.get("keyword", "*"),
                "data_source": settings.UNIFY_QUERY_DATA_SOURCE,
                "table_id": result_table_id,
                "field_name": self.search_params["agg_field"],
                "reference_name": REFERENCE_ALIAS[index],
                "dimensions": [],
                "time_field": "time",
                "conditions": self.transform_additions(),
                "function": [],
            }
            for index, result_table_id in enumerate(self.search_params.get("result_table_ids", []))
        ]

        return {
            "query_list": query_list,
            "metric_merge": " + ".join([query["reference_name"] for query in query_list]),
            "order_by": ["-time"],
            "step": interval,
            "start_time": str(self.start_time),
            "end_time": str(self.end_time),
            "down_sample_range": "",
            "timezone": get_local_param("time_zone", settings.TIME_ZONE),
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

    def transform_additions(self):
        field_list = []
        condition_list = []
        for addition in self.search_params.get("addition", []):
            if addition["operator"] in BASE_OP_MAP:
                field_list.append(
                    {
                        "field_name": addition["field"],
                        "op": BASE_OP_MAP[addition["operator"]],
                        "value": [addition["value"]],
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

    def get_total_count(self):
        search_dict = copy.deepcopy(self.base_dict)
        search_dict.update({"metric_merge": "a"})
        for query in search_dict["query_list"]:
            query["function"] = [{"method": "count"}]
        data = self.query_ts_reference(search_dict)
        if data.get("series", []):
            series = data["series"][0]
            return series["values"][0][1]
        return 0

    def get_field_count(self):
        search_dict = copy.deepcopy(self.base_dict)
        search_dict.update({"metric_merge": "a"})
        for query in search_dict["query_list"]:
            if len(query["conditions"]["field_list"]) > 0:
                query["conditions"]["condition_list"].append("and")
            query["conditions"]["field_list"].append(
                {"field_name": self.search_params["agg_field"], "value": [""], "op": "ncontains"}
            )
            query["function"] = [{"method": "count"}]
        data = self.query_ts_reference(search_dict)
        if data.get("series", []):
            series = data["series"][0]
            return series["values"][0][1]
        return 0

    def get_bucket_count(self, start, end):
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
        if data.get("series", []):
            series = data["series"][0]
            return series["values"][0][1]
        return 0

    def get_distinct_count(self):
        search_dict = copy.deepcopy(self.base_dict)
        data = {}
        if self.is_union_search:
            reference_list = []
            for query in search_dict["query_list"]:
                query["time_aggregation"] = {"function": "count_over_time", "window": search_dict["step"]}
                query["function"] = [{"method": "sum", "dimensions": [self.search_params["agg_field"]]}]
                reference_list.append(query["reference_name"])
            metric_merge = "count(" + " or ".join(reference_list) + ")"
            search_dict.update({"metric_merge": metric_merge, "instant": True})
            data = self.query_ts(search_dict)
        else:
            for query in search_dict["query_list"]:
                query["function"] = [{"method": "cardinality"}]
                search_dict.update({"metric_merge": "a"})
                data = self.query_ts_reference(search_dict)
        if data.get("series", []):
            series = data["series"][0]
            return series["values"][0][1]
        return 0

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
            if len(query["conditions"]["field_list"]) > 0:
                query["conditions"]["condition_list"].extend(["and"] * 2)
            else:
                query["conditions"]["condition_list"].extend(["and"])
            query["conditions"]["field_list"].extend(
                [
                    {"field_name": self.search_params["agg_field"], "value": [""], "op": "ne"},
                    {"field_name": self.search_params["agg_field"], "value": topk_group_values, "op": "eq"},
                ]
            )
        data = self.query_ts(search_dict)
        return data

    def get_agg_value(self, agg_method):
        search_dict = copy.deepcopy(self.base_dict)
        search_dict.update({"metric_merge": "a"})
        for query in search_dict["query_list"]:
            if agg_method == "median":
                query["function"] = [{"method": "percentiles", "vargs_list": [50]}]
            else:
                query["function"] = [{"method": agg_method}]
        data = self.query_ts_reference(search_dict)
        if data.get("series", []):
            series = data["series"][0]
            return round(series["values"][0][1], 2)
        return 0

    def get_topk_list(self, limit: int = 5):
        search_dict = copy.deepcopy(self.base_dict)
        reference_list = []
        for query in search_dict["query_list"]:
            query["limit"] = limit
            query["function"] = [{"method": "count", "dimensions": [self.search_params["agg_field"]]}]
            if len(query["conditions"]["field_list"]) > 0:
                query["conditions"]["condition_list"].append("and")
            query["conditions"]["field_list"].extend(
                [{"field_name": self.search_params["agg_field"], "value": [""], "op": "ne"}]
            )
            reference_list.append(query["reference_name"])
        search_dict.update({"order_by": ["-_value"], "metric_merge": " or ".join(reference_list)})
        data = self.query_ts_reference(search_dict)
        series = data["series"]
        return sorted([[s["group_values"][0], s["values"][0][1]] for s in series[:limit]], key=lambda x: x[1], reverse=True)

    def get_bucket_data(self, min_value: int, max_value: int):
        # 浮点数分桶区间精度默认为两位小数
        digits = None
        if self.search_params.get("field_type") and self.search_params["field_type"] in ["double", "float"]:
            digits = 2
        step = round((max_value - min_value) / 10, digits)
        bucket_data = []
        for index in range(10):
            start = min_value + index * step
            end = start + step if index < 9 else max_value
            bucket_count = self.get_bucket_count(start, end)
            bucket_data.append([start, bucket_count])
        return bucket_data
