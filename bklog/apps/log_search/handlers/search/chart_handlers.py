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
import time

import arrow
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _
from opentelemetry import trace

from apps.api import BkDataQueryApi
from apps.log_search import metrics
from apps.log_search.constants import (
    SQL_CONDITION_MAPPINGS,
    SQL_PREFIX,
    SQL_SUFFIX,
    SearchMode,
    SQLGenerateMode,
)
from apps.log_search.exceptions import (
    BaseSearchIndexSetException,
    IndexSetDorisQueryException,
    SQLQueryException,
)
from apps.log_search.models import LogIndexSet
from apps.utils.local import get_request_app_code, get_request_username
from apps.utils.log import logger


class ChartHandler(object):
    def __init__(self, index_set_id):
        self.index_set_id = index_set_id
        try:
            self.data = LogIndexSet.objects.get(index_set_id=self.index_set_id)
        except LogIndexSet.DoesNotExist:
            raise BaseSearchIndexSetException(
                BaseSearchIndexSetException.MESSAGE.format(index_set_id=self.index_set_id)
            )

    @classmethod
    def get_instance(cls, index_set_id, mode):
        mapping = {
            SearchMode.UI.value: "UIChartHandler",
            SearchMode.SQL.value: "SQLChartHandler",
        }
        try:
            chart_instance = import_string(
                "apps.log_search.handlers.search.chart_handlers.{}".format(mapping.get(mode))
            )
            return chart_instance(index_set_id=index_set_id)
        except ImportError as error:
            raise NotImplementedError(f"{mode} class not implement, error: {error}")

    def get_chart_data(self, params: dict) -> dict:
        """
        获取图表相关信息
        :param params: 图表参数
        :return: 图表数据 dict
        """
        raise NotImplementedError(_("功能暂未实现"))

    @staticmethod
    def generate_sql(
        addition,
        start_time,
        end_time,
        sql_param=None,
        action=SQLGenerateMode.COMPLETE.value,
    ) -> dict:
        """
        根据过滤条件生成sql
        :param addition: 过滤条件
        :param sql_param: SQL条件
        :param start_time: 开始时间
        :param end_time: 结束时间
        :param action: 生成SQL的方式
        """
        start_date = arrow.get(start_time).format("YYYYMMDD")
        end_date = arrow.get(end_time).format("YYYYMMDD")
        sql = (
            f"thedate >= {start_date} AND thedate <= {end_date} AND "
            f"dtEventTimeStamp >= {start_time} AND dtEventTimeStamp <= {end_time}"
        )

        for condition in addition:
            field_name = condition["field"]
            operator = condition["operator"]
            values = condition["value"]
            # 获取sql操作符
            sql_operator = SQL_CONDITION_MAPPINGS.get(operator)
            # 异常情况,跳过
            if not sql_operator or field_name in ["*", "query_string"]:
                continue

            if sql:
                sql += " AND "

            # IS TRUE和IS FALSE的逻辑
            if operator in ["is true", "is false"]:
                sql += f"{field_name} {sql_operator}"
                continue

            # values 不为空时才走后面的逻辑
            if not values:
                continue

            # _ext.a.b的字段名需要转化为JSON_EXTRACT的形式
            if "." in field_name:
                field_list = field_name.split(".")
                field_name = field_list[0] + "".join([f"['{sub_field}']" for sub_field in field_list[1:]])
                field_name = f"CAST({field_name} AS TEXT)"

            # 组内条件的与或关系
            condition_type = "OR"
            if operator in ["&=~", "&!=~", "all contains match phrase", "all not contains match phrase"]:
                condition_type = "AND"

            tmp_sql = ""
            for index, value in enumerate(values):
                if operator in ["=~", "&=~", "!=~", "&!=~"]:
                    # 替换通配符
                    value = value.replace("*", "%").replace("?", "_")
                    if not value.startswith("%"):
                        value = "%" + value
                    if not value.endswith("%"):
                        value += "%"
                elif operator in ["contains", "not contains"]:
                    # 添加通配符
                    value = f"%{value}%"

                if index > 0:
                    tmp_sql += f" {condition_type} "
                if isinstance(value, str):
                    value = value.replace("'", "''")
                    value = f"\'{value}\'"
                tmp_sql += f"{field_name} {sql_operator} {value}"

            # 有两个以上的值时加括号
            sql += tmp_sql if len(values) == 1 else ("(" + tmp_sql + ")")

        if action == SQLGenerateMode.WHERE_CLAUSE.value:
            # 返回SQL条件
            return sql

        # 保存where子句变量
        additional_where_clause = sql

        if sql_param:
            pattern = (
                r"^\s*?(SELECT\s+?.+?)"
                r"(?:\bFROM\b.+?)?"
                r"(?:\bWHERE\b.+?)?"
                r"(\bGROUP\s+?BY\b.*|\bHAVING\b.*|\bORDER\s+?BY\b.*|\bLIMIT\b.*|\bINTO\s+?OUTFILE\b.*)?$"
            )
            matches = re.match(pattern, sql_param, re.DOTALL | re.IGNORECASE)
            final_sql = matches.group(1)
            if sql:
                final_sql += f"WHERE {sql} "
            if matches.group(2):
                final_sql += matches.group(2)
        else:
            final_sql = f"{SQL_PREFIX} WHERE {sql} {SQL_SUFFIX}" if sql else f"{SQL_PREFIX} {SQL_SUFFIX}"
        return {"sql": final_sql, "additional_where_clause": f"WHERE {additional_where_clause}"}


class UIChartHandler(ChartHandler):
    def get_chart_data(self, params: dict) -> dict:
        """
        UI模式获取图表相关信息
        :param params: 图表参数
        :return: 图表数据 dict
        """
        # TODO 待实现
        return {}


class SQLChartHandler(ChartHandler):
    def get_chart_data(self, params) -> dict:
        """
        Sql模式获取图表相关信息
        :param params: 图表参数
        :return: 图表数据 dict
        """
        try:
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("bkdata_doris_query") as span:
                span.set_attribute("index_set_id", self.index_set_id)
                span.set_attribute("user.username", get_request_username())
                span.set_attribute("space_uid", self.data.space_uid)

                if not self.data.support_doris:
                    raise IndexSetDorisQueryException()
                span.set_attribute("db.table", self.data.doris_table_id)
                parsed_sql = self.parse_sql_syntax(self.data.doris_table_id, params)
                span.set_attribute("db.statement", parsed_sql)
                span.set_attribute("db.system", "doris")

                data = self.fetch_query_data(parsed_sql)
                span.set_attribute("total_records", data["total_records"])
                span.set_attribute("time_taken", data["time_taken"])

                return data
        except Exception as e:
            raise e

    def parse_sql_syntax(self, doris_table_id: str, params: dict):
        """
        解析sql语法
        """
        where_clause = self.generate_sql(
            addition=params["addition"],
            start_time=params["start_time"],
            end_time=params["end_time"],
            action=SQLGenerateMode.WHERE_CLAUSE.value,
        )
        # 如果不存在FROM则添加,存在则覆盖
        pattern = (
            r"^\s*?(SELECT\s+?.+?)"
            r"(?:\bFROM\b.+?)?"
            r"(\bWHERE\b.+?)?"
            r"(\bGROUP\s+?BY\b.*|\bHAVING\b.*|\bORDER\s+?BY\b.*|\bLIMIT\b.*|\bINTO\s+?OUTFILE\b.*)?$"
        )
        matches = re.match(pattern, params["sql"], re.DOTALL | re.IGNORECASE)
        if not matches:
            raise SQLQueryException(SQLQueryException.MESSAGE.format(name=_("缺少SQL查询的关键字")))
        parsed_sql = matches.group(1) + f" FROM {doris_table_id}\n"
        if matches.group(2):
            where_condition = matches.group(2) + f"AND {where_clause}\n"
        else:
            where_condition = f"WHERE {where_clause}\n"
        parsed_sql += where_condition

        if matches.group(3):
            parsed_sql += matches.group(3)
        return parsed_sql

    def fetch_query_data(self, sql: str) -> dict:
        """
        获取查询结果
        :param sql: 查询sql
        :return: 查询结果 dict
        """
        start_at = time.time()
        exc = None
        try:
            result_data = BkDataQueryApi.query({"sql": sql}, raw=True)
            result = result_data.get("result")
            if not result:
                # SQL查询失败, 抛出异常
                errors_message = result_data.get("message", "")
                errors = result_data.get("errors", {}).get("error")
                if errors:
                    errors_message = errors_message + ":" + errors
                exc = errors_message
                logger.info(
                    "[doris query] QUERY ERROR! username: %s, execute sql: \"%s\", error info: %s",
                    get_request_username(),
                    sql.replace("\n", " "),
                    errors_message,
                )
                raise SQLQueryException(
                    SQLQueryException.MESSAGE.format(name=errors_message),
                    errors={"sql": sql},
                )
        finally:
            labels = {
                "index_set_id": self.index_set_id,
                "result_table_id": self.data.doris_table_id,
                "status": str(exc),
                "source_app_code": get_request_app_code(),
            }
            metrics.DORIS_QUERY_LATENCY.labels(**labels).observe(time.time() - start_at)
            metrics.DORIS_QUERY_COUNT.labels(**labels).inc()

        data_list = result_data["data"]["list"]
        result_schema = result_data["data"].get("result_schema", [])

        data = {
            "total_records": result_data["data"]["totalRecords"],
            "time_taken": result_data["data"]["timetaken"],
            "list": data_list,
            "select_fields_order": result_data["data"]["select_fields_order"],
            "result_schema": result_schema,
        }
        # 记录doris日志
        if result_data["data"]["timetaken"] < 5:
            logger.info(
                "[doris query] username: %s, execute sql: \"%s\", total records: %s, time taken: %ss",
                get_request_username(),
                sql.replace("\n", " "),
                result_data["data"]["totalRecords"],
                result_data["data"]["timetaken"],
            )
        else:
            # 大于 5s 的判定为慢查询
            logger.info(
                "[doris query] SLOW QUERY! username: %s, execute sql: \"%s\", total records: %s, time taken: %ss",
                get_request_username(),
                sql.replace("\n", " "),
                result_data["data"]["totalRecords"],
                result_data["data"]["timetaken"],
            )
        return data
