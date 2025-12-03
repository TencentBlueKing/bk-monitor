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


class UnifyQueryTermsAggsHandler(UnifyQueryHandler):
    def __init__(self, agg_fields: list, param: dict):
        super().__init__(param)

        self.agg_fields = agg_fields
        self.base_dict = self.init_base_dict_list()

    def terms(self):
        aggs = dict()
        aggs_items = dict()

        # 获取基础查询条件
        query_condition = copy.deepcopy(self.base_dict)

        # 请求 unify-query
        series_dict = self._terms_unify_query(query_condition, self.search_params.get("size"))

        for agg_field in self.agg_fields:
            series = series_dict.get(agg_field)
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

    def _terms_unify_query(self, query_condition: dict, size: int = 10000) -> dict:
        """
        unify_query 查询 terms
        """
        # 构建完整查询条件
        for query in query_condition["query_list"]:
            query["limit"] = size
            query["function"] = [{"method": "count", "dimensions": [query.get("field_name")]}]

            # 增加字段不为空的条件
            if len(query["conditions"]["field_list"]) > 0:
                query["conditions"]["condition_list"].append("and")
            query["conditions"]["field_list"].append({"field_name": query.get("field_name"), "value": [""], "op": "ne"})

        query_condition.update({"order_by": ["-_value"]})

        result = self.query_ts_reference(query_condition)

        # 对返回的结果按聚合字段进行分组
        series_dict = dict()

        if not result.get("series"):
            return series_dict

        for item in result.get("series"):
            group_keys = item.get("group_keys")
            if not group_keys:
                continue
            group_key = group_keys[0]
            if group_key not in series_dict:
                series_dict[group_key] = []
            series_dict[group_key].append(item)

        return series_dict

    def init_base_dict_list(self):
        """
        重构 unify-query 接口基础请求参数, 适配 terms 接口查询
        """
        base_dict = copy.deepcopy(self.result_merge_base_dict)

        query_list = copy.deepcopy(base_dict.get("query_list"))

        reference_name_list = ["a"]

        # 多聚合字段查询的情况下, 创建相对应的查询参数
        for index, agg_field in enumerate(self.agg_fields[1:]):
            # 从 b 开始, 相同聚合字段的查询参数中 reference_name 也必须相同, 用于合并聚合结果
            reference_name = self.generate_reference_name(index + 1)
            reference_name_list.append(reference_name)

            for query in query_list:
                new_query = copy.deepcopy(query)
                new_query["reference_name"] = reference_name
                new_query["field_name"] = agg_field

                base_dict["query_list"].append(new_query)

        # 结果按不同聚合字段进行合并
        base_dict["metric_merge"] = " or ".join(reference_name_list)

        return base_dict
