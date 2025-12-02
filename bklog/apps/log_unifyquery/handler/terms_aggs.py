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

from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.utils.thread import MultiExecuteFunc


class UnifyQueryTermsAggsHandler(UnifyQueryHandler):
    def __init__(self, agg_fields: list, param: dict):
        super().__init__(param)

        self.agg_fields = agg_fields
        self.base_dict_list = self.init_base_dict_list()

    def init_base_dict_list(self):
        base_dict_list = list()
        for agg_field in self.agg_fields:
            base_dict = self.init_base_dict(agg_field=agg_field)
            base_dict_list.append(base_dict)
        return base_dict_list

    def terms(self):
        aggs = dict()
        aggs_items = dict()

        # 获取基础查询条件
        query_conditions = copy.deepcopy(self.base_dict_list)

        # 多线程
        multi_execute_func = MultiExecuteFunc()

        for index, query_condition in enumerate(query_conditions):
            agg_field = self.agg_fields[index]

            multi_execute_func_params = {
                "agg_field": agg_field,
                "query_condition": query_condition,
                "size": self.search_params.get("size"),
            }

            # 多线程请求 unify-query
            multi_execute_func.append(
                result_key=f"union_search_terms_{agg_field}",
                func=self._terms_unify_query,
                params=multi_execute_func_params,
                multi_func_params=True,
            )

        multi_result = multi_execute_func.run()

        for agg_field in self.agg_fields:
            query_result = multi_result.get(f"union_search_terms_{agg_field}", {})

            series = query_result.get("series")

            if series:
                # 处理获得聚合结果
                agg = self.obtain_agg(agg_field, series)
                agg_items = self.obtain_agg_items(agg_field, agg)
                if agg and agg_items:
                    aggs.update(agg)
                    aggs_items.update(agg_items)

        return {"aggs": aggs, "aggs_items": aggs_items}

    @staticmethod
    def obtain_agg_items(agg_field: str, agg: dict) -> dict:
        """
        处理聚合结果, 获得聚合后数据列表
        """
        agg_field_data = agg.get(agg_field, dict())
        buckets = agg_field_data.get("buckets", [])

        agg_item_list = [item["key"] for item in buckets if item.get("key")]

        return {agg_field: agg_item_list} if agg_item_list else dict()

    @staticmethod
    def obtain_agg(agg_field: str, series: list) -> dict:
        """
        处理响应中的有效数据, 生成聚合结果
        """
        buckets_dict = dict()

        for item in series:
            group_values = item.get("group_values")
            values = item.get("values")

            if group_values and values:
                key = group_values[0]
                doc_count = values[0][1]
                # 合并结果
                if key not in buckets_dict:
                    buckets_dict[key] = {"key": key, "doc_count": doc_count}
                else:
                    buckets_dict[key]["doc_count"] += doc_count

        # 按数量倒叙排序
        buckets = sorted(buckets_dict.values(), key=lambda x: x.get("doc_count"), reverse=True)

        return {agg_field: {"buckets": buckets}} if buckets else dict()

    def _terms_unify_query(self, agg_field, query_condition, size=10000):
        """
        unify_query 查询 terms
        """
        # 构建完整查询条件
        for query in query_condition["query_list"]:
            query["limit"] = size
            query["function"] = [{"method": "count", "dimensions": [agg_field]}]

            # 增加字段不为空的条件
            if len(query["conditions"]["field_list"]) > 0:
                query["conditions"]["condition_list"].append("and")
            query["conditions"]["field_list"].append({"field_name": agg_field, "value": [""], "op": "ne"})

            query["reference_name"] = "a"

        query_condition.update({"order_by": ["-_value"], "metric_merge": "a"})

        return self.query_ts_reference(query_condition)
