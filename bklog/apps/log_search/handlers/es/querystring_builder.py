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
from apps.log_esquery.esquery.dsl_builder.query_builder.query_builder_logic import (
    BoolQueryOperation,
)


class QueryStringBuilder(object):
    @staticmethod
    def to_querystring(params: dict):
        """
        把查询参数转化为QueryString语法
        :param params: 查询参数
        :return: str
        """
        querystring_list = []
        addition = params["addition"]
        for index, condition in enumerate(addition):
            # 跳过values为空的异常情况
            if (
                condition["operator"] not in ["is true", "is false", "exists", "does not exists"]
                and not condition["value"]
            ):
                continue

            # 全文检索的情况
            if condition["field"] in ["*", "__query_string__"]:
                if condition["field"] == "*" and "prefix" in condition["operator"]:
                    continue
                transform_result_list = []
                for value in condition["value"]:
                    if condition["field"] == "*":
                        value = value.replace('"', '\\"')
                        value = f"\"{value}\""
                    transform_result_list.append(value)
                transform_result = " OR ".join(transform_result_list)
                querystring_list.append(f"({transform_result})")
                continue

            # 获取querystring
            query_object = BoolQueryOperation.get_op(op=condition["operator"], bool_dict=condition)
            transform_result = query_object.to_querystring()
            if transform_result:
                querystring_list.append(transform_result)
        return " AND ".join(querystring_list)
