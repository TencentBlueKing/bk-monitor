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
import time

import arrow
from sqlglot import expressions, parse_one
from sqlglot.dialects import Doris
from sqlglot.errors import ParseError
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _

from apps.api import BkDataQueryApi
from apps.log_search import metrics
from apps.log_search.constants import (
    SQL_CONDITION_MAPPINGS,
    SQL_PREFIX,
    SQL_SUFFIX,
    SearchMode,
)
from apps.log_search.exceptions import (
    BaseSearchIndexSetException,
    IndexSetDorisQueryException,
    SQLParserException,
    SQLQueryException,
)
from apps.log_search.models import LogIndexSet
from apps.utils.local import get_local_param, get_request_app_code, get_request_username
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
    def generate_sql(params: dict) -> str:
        """
        根据过滤条件生成sql
        :param params: 过滤条件
        """
        sql_param = params.get("sql")
        sql = ""
        addition = params["addition"]

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
                field_list = field_name.split(".", 1)
                field_name = f"JSON_EXTRACT({field_list[0]},'$.{field_list[-1]}')"

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
                    value = f"\'\"{value}\"\'" if "." in field_name and operator in ["=", "!="] else f"\'{value}\'"
                tmp_sql += f"{field_name} {sql_operator} {value}"

            # 有两个以上的值时加括号
            sql += tmp_sql if len(values) == 1 else ("(" + tmp_sql + ")")
        if sql_param:
            try:
                tree = parse_one(sql_param, dialect="doris")
            except ParseError as e:
                raise SQLQueryException(SQLQueryException.MESSAGE.format(name=e))
            tree.set("where", expressions.Where(this=parse_one(sql)))
            final_sql = tree.sql(dialect=Doris, pretty=False)
        else:
            final_sql = f"{SQL_PREFIX} WHERE {sql} {SQL_SUFFIX}" if sql else f"{SQL_PREFIX} {SQL_SUFFIX}"
        return final_sql


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
        if not self.data.support_doris:
            raise IndexSetDorisQueryException()
        parsed_sql = self.parse_sql_syntax(self.data.doris_table_id, params)
        data = self.fetch_query_data(parsed_sql)
        return data

    @staticmethod
    def parse_sql_syntax(doris_table_id: str, params: dict):
        """
        解析sql语法
        """
        raw_sql = params["sql"]
        start_time = params["start_time"]
        end_time = params["end_time"]
        start_date = arrow.get(start_time).format("YYYYMMDD")
        end_date = arrow.get(end_time).format("YYYYMMDD")
        try:
            tree = parse_one(raw_sql, dialect="doris")
        except ParseError as e:
            raise SQLQueryException(SQLQueryException.MESSAGE.format(name=e))

        # 覆盖 FROM 的子语句
        tree.set(
            "from",
            expressions.From(
                this=expressions.Table(
                    this=expressions.Identifier(this=doris_table_id, quoted=False)
                )
            )
        )
        # 获取 WHERE 子句
        where_clause = tree.args.get("where")

        # 自定义条件
        custom_condition = parse_one(
            f"(dtEventTimeStamp >= {start_time} AND dtEventTimeStamp <= {end_time}"
            f"AND thedate >= {start_date} and thedate <= {end_date})"
        )

        # 将自定义条件添加到 WHERE 子句中
        if where_clause:
            # 如果已有 WHERE 子句，使用 AND 连接新条件
            new_where = expressions.And(
                this=where_clause,
                expression=custom_condition
            )
            tree.set("where", new_where)
        else:
            # 如果没有 WHERE 子句，直接添加 WHERE 条件
            tree.set("where", expressions.Where(this=custom_condition))
        return tree.sql(dialect=Doris, pretty=False)

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
                logger.info("SQL query exception [%s]", errors_message)
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
        logger.info(
            "[doris query] username: %s, execute sql: \"%s\", total records: %s, time taken: %ss",
            get_request_username(),
            sql.replace("\n", " "),
            result_data["data"]["totalRecords"],
            result_data["data"]["timetaken"],
        )
        return data
