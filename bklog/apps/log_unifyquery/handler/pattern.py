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

import copy

from apps.log_unifyquery.handler.base import UnifyQueryHandler


class UnifyQueryPatternHandler(UnifyQueryHandler):
    def query_pattern(self):
        # 获取基础查询条件
        query_condition = copy.deepcopy(self.base_dict)

        result = self._pattern_unify_query(query_condition, self.search_params.get("size"))

        return self.handle_result_formats(result)

    def _pattern_unify_query(self, query_condition: dict, size: int = 10000) -> dict:
        """
        unify_query 查询 pattern
        """
        # 增加聚合维度
        dimensions = [self.agg_field] + self.search_params.get("group_by", [])

        # 构建完整查询条件
        for query in query_condition["query_list"]:
            query["limit"] = size
            query["function"] = [{"method": "count", "dimensions": dimensions}]

        query_condition.update({"order_by": ["-_value"]})

        return self.query_ts_reference(query_condition)

    @staticmethod
    def handle_result_formats(result: dict) -> list:
        """
        处理结果格式
        """
        if not result or not result.get("series"):
            return []

        result_after_format = []

        for item in result.get("series"):
            group_values = item.get("group_values")
            values = item.get("values")

            if group_values and values and len(values[0]) > 1:
                result_after_format.append(
                    {"key": group_values[0], "doc_count": values[0][1], "group": "|".join(group_values[1:])}
                )

        return result_after_format
