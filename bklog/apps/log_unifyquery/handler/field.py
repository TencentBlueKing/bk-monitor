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
from apps.log_unifyquery.handler.base import UnifyQueryHandler
import copy

from apps.log_search.constants import MAX_FIELD_VALUE_LIST_NUM
from apps.log_unifyquery.constants import FLOATING_NUMERIC_FIELD_TYPES
from apps.utils.log import logger


class UnifyQueryFieldHandler(UnifyQueryHandler):
    @staticmethod
    def handle_count_data(data, digits=None):
        """
        处理聚合count类型数据
        """
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
        """
        获取日志聚合总条数
        """
        search_dict = copy.deepcopy(self.base_dict)
        reference_list = []
        for query in search_dict["query_list"]:
            query["function"] = [{"method": "count"}]
            reference_list.append(query["reference_name"])
        search_dict.update({"metric_merge": " + ".join(reference_list)})
        data = self.query_ts_reference(search_dict)
        return self.handle_count_data(data)

    def get_field_count(self):
        """
        获取字段存在的聚合总条数
        """
        search_dict = copy.deepcopy(self.base_dict)
        reference_list = []
        for query in search_dict["query_list"]:
            if len(query["conditions"]["field_list"]) > 0:
                query["conditions"]["condition_list"].append("and")
            # 增加字段不为空的条件
            query["conditions"]["field_list"].append(
                {"field_name": self.search_params["agg_field"], "value": [""], "op": "ne"}
            )
            query["function"] = [{"method": "count"}]
            reference_list.append(query["reference_name"])
        search_dict.update({"metric_merge": " + ".join(reference_list)})
        data = self.query_ts_reference(search_dict)
        return self.handle_count_data(data)

    def get_bucket_count(self, start: int, end: int):
        """
        根据聚合桶大小计算字段聚合数
        """
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
        """
        获取字段去重的聚合总条数
        """
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
        """
        获取topk时序数据，默认为前5
        """
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
        """
        获取不同聚合方法计算出的字段数量
        """
        search_dict = copy.deepcopy(self.base_dict)
        search_dict.update({"metric_merge": "a"})
        for query in search_dict["query_list"]:
            # 中位数聚合方法默认使用P50
            if agg_method == "median":
                query["function"] = [{"method": "percentiles", "vargs_list": [50]}]
            else:
                query["function"] = [{"method": agg_method}]
        data = self.query_ts_reference(search_dict)
        return self.handle_count_data(data, digits=2)

    def get_topk_list(self, limit: int = 5):
        """
        获取topk聚合字段列表，默认为前5
        """
        search_dict = copy.deepcopy(self.base_dict)
        reference_list = []
        for query in search_dict["query_list"]:
            query["limit"] = limit * 2 + 10
            query["function"] = [{"method": "count", "dimensions": [self.search_params["agg_field"]]}]
            # 增加字段不为空的条件
            if len(query["conditions"]["field_list"]) > 0:
                query["conditions"]["condition_list"].append("and")
            query["conditions"]["field_list"].append(
                {"field_name": self.search_params["agg_field"], "value": [""], "op": "ne"}
            )

            reference_list.append(query["reference_name"])
        search_dict.update({"order_by": ["-_value"], "metric_merge": " or ".join(reference_list)})
        data = self.query_ts_reference(search_dict)
        series = data["series"]
        return [[s["group_values"][0], s["values"][0][1]] for s in sorted(
            series,
            key=lambda x: x["values"][0][1],
            reverse=True
        )[:limit]]

    def get_value_list(self, limit: int = 10):
        """
        获取聚合字段数量列表，默认limit为10；并返回占总数的百分比，默认保留四位小数
        """
        limit = limit if limit <= MAX_FIELD_VALUE_LIST_NUM else MAX_FIELD_VALUE_LIST_NUM
        search_dict = copy.deepcopy(self.base_dict)
        reference_list = []
        for query in search_dict["query_list"]:
            query["limit"] = limit
            query["function"] = [{"method": "count", "dimensions": [self.search_params["agg_field"]]}]
            reference_list.append(query["reference_name"])
        search_dict.update({"order_by": ["-_value"], "metric_merge": " or ".join(reference_list)})
        data = self.query_ts_reference(search_dict)
        series = data["series"]
        total_count = self.get_total_count()
        return sorted(
            [
                [s["group_values"][0], s["values"][0][1], round(s["values"][0][1] / total_count, 4)]
                for s in series[:limit]
            ],
            key=lambda x: x[1],
            reverse=True,
        )

    def get_bucket_data(self, min_value: int, max_value: int, bucket_range: int = 10):
        """
        计算聚合桶周期，分次获取聚合桶数据
        """
        digits = None
        # 浮点数分桶区间精度默认为两位小数
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
