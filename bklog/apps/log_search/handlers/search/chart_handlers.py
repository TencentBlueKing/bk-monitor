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
import re

from apps.api import BkDataQueryApi
from apps.log_search.constants import SearchMode
from apps.log_search.exceptions import (
    BaseSearchIndexSetException,
    IndexSetDorisQueryException,
    SqlSyntaxException,
)
from apps.log_search.models import LogIndexSet
from apps.utils.log import logger


class ChartHandler(object):
    def __init__(self, index_set_id=None):
        self.index_set_id = index_set_id
        if self.index_set_id:
            try:
                self.data = LogIndexSet.objects.get(index_set_id=self.index_set_id)
            except LogIndexSet.DoesNotExist:
                raise BaseSearchIndexSetException(
                    BaseSearchIndexSetException.MESSAGE.format(index_set_id=self.index_set_id)
                )

    def get_chart_data(self, params):
        """
        获取图表信息
        """
        if params["query_mode"] == SearchMode.SQL.value:
            parsed_sql = self.parser_sql_syntax(params["sql"])
            result_data = BkDataQueryApi.query({"sql": parsed_sql}, raw=True)
            result = result_data.get("result")
            if not result:
                errors_message = result_data.get("message", {})
                errors = result_data.get("errors", {}).get("error")
                if errors:
                    errors_message = errors_message + ":" + errors
                logger.info("SQL语法异常 [{}]".format(errors_message))
                raise SqlSyntaxException(errors_message)

            data_list = result_data["data"]["list"]
            result_schema = []
            index = 0
            # 构造result_schema
            if data_list:
                for key, value in data_list[0].items():
                    if isinstance(value, int):
                        field_type = "long"
                    elif isinstance(value, float):
                        field_type = "double"
                    else:
                        field_type = "string"
                    result_schema.append(
                        {"field_type": field_type, "field_name": key, "field_alias": key, "field_index": index}
                    )
                    index += 1
            data = {
                "total_records": result_data["data"]["totalRecords"],
                "time_taken": result_data["data"]["timetaken"],
                "list": data_list,
                "select_fields_order": result_data["data"]["select_fields_order"],
                "result_schema": result_schema,
            }
            return data
        else:
            return {}

    def parser_sql_syntax(self, raw_sql: str):
        """
        解析sql语法
        """
        support_doris = self.data.support_doris
        if not support_doris:
            raise IndexSetDorisQueryException()
        # 如果不存在FROM则添加,存在则覆盖
        doris_table_id = self.data.doris_table_id
        pattern = (
            r"^\s*?(SELECT\s+?.+?)"
            r"(?:\bFROM\b.+?)?"
            r"(\bWHERE\b.*|\bGROUP\s+?BY\b.*|\bHAVING\b.*|\bORDER\s+?BY\b.*|\bINTO\s+?OUTFILE\b.*)?$"
        )
        matches = re.match(pattern, raw_sql, re.DOTALL | re.IGNORECASE)
        if not matches:
            raise SqlSyntaxException("缺少SQL查询的关键字")
        parsed_sql = matches.group(1) + f" FROM {doris_table_id} "
        if matches.group(2):
            parsed_sql += matches.group(2)
        return parsed_sql
