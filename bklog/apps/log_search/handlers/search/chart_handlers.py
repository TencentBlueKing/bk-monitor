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
from luqum.parser import lexer, parser
from luqum.tree import (
    AndOperation,
    FieldGroup,
    Group,
    Not,
    OrOperation,
    Phrase,
    Prohibit,
    Range,
    Regex,
    SearchField,
    Term,
    Word,
)
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
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.models import LogIndexSet
from apps.log_search.utils import add_highlight_mark
from apps.utils.grep_syntax_parse import grep_parser
from apps.utils.local import get_request_app_code, get_request_username
from apps.utils.log import logger
from apps.utils.lucene import EnhanceLuceneAdapter


class ChartHandler:
    AND = "AND"
    OR = "OR"

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
            chart_instance = import_string(f"apps.log_search.handlers.search.chart_handlers.{mapping.get(mode)}")
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
    def to_like_syntax(value: str):
        """
        转化为like语法
        :param value: 值
        """
        value = value.replace("*", "%").replace("?", "_")
        if not value.startswith("%"):
            value = "%" + value
        if not value.endswith("%"):
            value += "%"
        return value

    @classmethod
    def lucene_to_where_clause(cls, lucene_query, alias_mappings):
        # 解析 Lucene 查询
        query_tree = parser.parse(lucene_query, lexer=lexer.clone())

        # 递归遍历语法树并生成 SQL WHERE 子句
        def build_condition(node):
            if isinstance(node, SearchField):
                field_name = node.name
                # 使用别名替换
                if field_name in alias_mappings:
                    field_name = alias_mappings[field_name]
                # _ext.a.b的字段名需要转化为JSON_EXTRACT的形式
                field_name = cls.convert_object_field(field_name)
                expr = node.expr
                if isinstance(expr, Phrase):
                    # 处理带引号的短语
                    value = expr.value.replace("'", "''")
                    op = "MATCH_PHRASE" if field_name == "log" else "="
                    return f"{field_name} {op} {value}"
                elif isinstance(expr, Regex):
                    # 处理正则表达式
                    regex = expr.value.strip("/")
                    return f"{field_name} REGEXP '{regex}'"
                elif isinstance(expr, Range):
                    # 处理范围查询，例如 year:[2020 TO 2023]
                    low = expr.low
                    high = expr.high
                    return f"{field_name} BETWEEN {low} AND {high}"
                elif isinstance(expr, Term):
                    # 处理不带引号的术语,替换通配符
                    value = expr.value
                    if (
                        value.startswith(">")
                        or value.startswith(">=")
                        or value.startswith("<")
                        or value.startswith("<=")
                    ):
                        return f"{field_name} {value}"
                    value = cls.to_like_syntax(expr.value)
                    return f"LOWER({field_name}) LIKE LOWER('{value}')"
                elif isinstance(expr, AndOperation):
                    # 处理 AND 操作
                    conditions = []
                    for child in expr.children:
                        search_field = SearchField(name=f"{field_name}", expr=child)
                        conditions.append(build_condition(search_field))
                    return " AND ".join(cond for cond in conditions if cond is not None)
                elif isinstance(expr, FieldGroup):
                    # 处理 FieldGroup 节点，例如 ("a" AND b OR c)
                    op = cls.AND
                    if isinstance(expr.children[0], OrOperation):
                        op = cls.OR
                    result_list = []
                    conditions = []
                    for child in expr.children[0].children:
                        if isinstance(child, Phrase) or isinstance(child, Word):
                            # child 是短语的情况
                            search_field = SearchField(name=f"{field_name}", expr=child)
                            condition = build_condition(search_field)
                            conditions.append(condition)
                        elif hasattr(child, "children"):
                            # child 带括号和AND操作符的情况
                            search_field = SearchField(name=f"{field_name}", expr=child)
                            child_condition = build_condition(search_field)
                            result_list.append(child_condition)
                    phrase_condition = f" {op} ".join(conditions)
                    if phrase_condition:
                        result_list.append(phrase_condition if len(conditions) == 1 else f"({phrase_condition})")
                    result = f" {op} ".join(result_list)
                    return result if len(result_list) == 1 or op == cls.AND else f"({result})"
                elif isinstance(expr, Group):
                    # 处理 Group 节点
                    result_list = []
                    op = cls.AND
                    if isinstance(expr.children[0], OrOperation):
                        op = cls.OR
                    conditions = []
                    for child in expr.children[0].children:
                        if isinstance(child, Phrase) or isinstance(child, Word):
                            # child 是短语的情况
                            search_field = SearchField(name=f"{field_name}", expr=child)
                            condition = build_condition(search_field)
                            conditions.append(condition)
                        elif isinstance(child, Group):
                            # child 带括号的情况
                            search_field = SearchField(name=f"{field_name}", expr=child)
                            result = build_condition(search_field)
                            result_list.append(result)
                    phrase_condition = f" {op} ".join(conditions)
                    if phrase_condition:
                        result_list.append(phrase_condition if len(conditions) == 1 else f"({phrase_condition})")
                    result = f" {op} ".join(result_list)
                    return result if len(result_list) == 1 or op == cls.AND else f"({result})"

            elif isinstance(node, OrOperation):
                # 处理 OR 操作
                conditions = [build_condition(child) for child in node.children]
                return " OR ".join(cond for cond in conditions if cond is not None)
            elif isinstance(node, AndOperation):
                # 处理 AND 操作
                conditions = [build_condition(child) for child in node.children]
                return " AND ".join(cond for cond in conditions if cond is not None)
            elif isinstance(node, Group):
                # 处理 Group 节点，例如 (author:John OR author:Jane)
                return f"({build_condition(node.children[0])})"
            elif isinstance(node, Phrase):
                # 处理带引号的短语
                return f"log MATCH_PHRASE {node.value}"
            elif isinstance(node, Word):
                # 处理不带引号的短语
                value = cls.to_like_syntax(node.value)
                return f"LOWER(log) LIKE LOWER('{value}')"
            elif isinstance(node, Not) or isinstance(node, Prohibit):
                # 处理 NOT 操作
                return f"NOT {build_condition(node.children[0])}"

        return build_condition(query_tree)

    @classmethod
    def generate_sql(
        cls,
        addition,
        start_time,
        end_time,
        sql_param=None,
        keyword=None,
        action=SQLGenerateMode.COMPLETE.value,
        alias_mappings=None,
    ) -> dict:
        """
        根据过滤条件生成sql
        :param addition: 过滤条件
        :param sql_param: SQL条件
        :param start_time: 开始时间
        :param end_time: 结束时间
        :param keyword: 搜索关键字
        :param action: 生成SQL的方式
        :param alias_mappings: 别名映射
        """
        alias_mappings = alias_mappings or {}

        # 根据 bkbase 的规范，thedate 固定按东八区转换
        start_date = arrow.get(start_time).to("Asia/Shanghai").format("YYYYMMDD")
        end_date = arrow.get(end_time).to("Asia/Shanghai").format("YYYYMMDD")

        additional_where_clause = (
            f"thedate >= {start_date} AND thedate <= {end_date} AND "
            f"dtEventTimeStamp >= {start_time} AND dtEventTimeStamp <= {end_time}"
        )

        if keyword and keyword != "*":
            # 加上keyword的查询条件
            enhance_lucene_adapter = EnhanceLuceneAdapter(query_string=keyword)
            keyword = enhance_lucene_adapter.enhance()
            where_clause = cls.lucene_to_where_clause(keyword, alias_mappings)
            if where_clause:
                additional_where_clause += f" AND {where_clause}"

        sql = ""
        for condition in addition:
            field_name = condition["field"]
            if field_name == "*":
                # TODO: 全文检索字段需要支持动态调整
                field_name = "log"

            if field_name in alias_mappings:
                field_name = alias_mappings[field_name]
            operator = condition["operator"]
            values = condition["value"]
            # 获取sql操作符
            sql_operator = SQL_CONDITION_MAPPINGS.get(operator)
            # 异常情况,跳过
            if not sql_operator or field_name in ["__query_string__"]:
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
            field_name = cls.convert_object_field(field_name)

            # 组内条件的与或关系
            condition_type = "OR"
            if operator in ["&=~", "&!=~", "all contains match phrase", "all not contains match phrase"]:
                condition_type = "AND"

            if "LIKE" in sql_operator:
                field_name = f"LOWER({field_name})"
            tmp_sql = ""
            for index, value in enumerate(values):
                if operator in ["=~", "&=~", "!=~", "&!=~"]:
                    # 替换通配符
                    value = cls.to_like_syntax(value)
                elif operator in ["contains", "not contains"]:
                    # 添加通配符
                    value = f"%{value}%"

                if index > 0:
                    tmp_sql += f" {condition_type} "
                if isinstance(value, str):
                    value = value.replace("'", "''")
                    value = f"'{value}'"
                if "LIKE" in sql_operator:
                    value = f"LOWER({value})"
                tmp_sql += f"{field_name} {sql_operator} {value}"

            # 有两个以上的值时加括号
            sql += tmp_sql if len(values) == 1 else ("(" + tmp_sql + ")")

        if sql:
            additional_where_clause += f" AND {sql}"

        if action == SQLGenerateMode.WHERE_CLAUSE.value:
            # 返回SQL条件
            return additional_where_clause

        if sql_param:
            final_sql = sql_param
        else:
            final_sql = f"{SQL_PREFIX} {SQL_SUFFIX}"
        return {"sql": final_sql, "additional_where_clause": f"WHERE {additional_where_clause}"}

    @staticmethod
    def convert_to_where_clause(grep_field, commands: list[dict]):
        """
        将解析后的grep命令转换为 doris SQL的where子句
        :param grep_field: grep查询字段
        :param commands: 解析后的grep命令列表
        :return: 查询条件
        """
        conditions = []

        for cmd in commands:
            args = cmd["args"]
            pattern = f"'{cmd['pattern']}'"
            use_not = False
            ignore_case = False
            for arg in args:
                if "v" in arg:
                    use_not = True
                if "i" in arg:
                    ignore_case = True

            # 构建正则表达式条件
            regex_op = "REGEXP"
            if use_not:
                regex_op = f"NOT {regex_op}"

            field_name = grep_field
            if ignore_case:
                field_name = f"LOWER({grep_field})"
                pattern = f"LOWER({pattern})"

            # 构建条件表达式
            condition = f"{field_name} {regex_op} {pattern}"
            conditions.append(condition)

        # 返回所有组合条件
        return " AND ".join(conditions)

    @staticmethod
    def convert_object_field(field_name):
        """
        将object字段转化为JSON_EXTRACT的形式
        """
        if "." in field_name:
            field_list = field_name.split(".")
            field_name = field_list[0] + "".join([f"['{sub_field}']" for sub_field in field_list[1:]])
            field_name = f"CAST({field_name} AS TEXT)"
        return field_name

    def add_grep_condition(self, where_clause, grep_query, grep_field, alias_mappings, sort_list, size=10, begin=0):
        """
        添加grep查询条件
        :param where_clause: sql的where子句
        :param grep_query: 查询语句
        :param grep_field: 查询字段
        :param alias_mappings: 别名
        :param sort_list: 排序字段
        :param size: 查询数据条数
        :param begin: 偏移量
        """
        pattern = ""
        ignore_case = False
        if grep_query and grep_field:
            # 使用别名作为查询条件
            grep_field = alias_mappings.get(grep_field, grep_field)
            # 加上 grep 查询条件
            grep_syntax_list = grep_parser(grep_query)
            # _ext.a.b的字段名需要转化为JSON_EXTRACT的形式
            _grep_field = self.convert_object_field(grep_field)
            grep_where_clause = self.convert_to_where_clause(_grep_field, grep_syntax_list)
            if grep_where_clause:
                use_not = False
                ignore_case = False
                for arg in grep_syntax_list[-1]["args"]:
                    if "v" in arg:
                        use_not = True
                    if "i" in arg:
                        ignore_case = True
                if not use_not:
                    pattern = grep_where_clause.rsplit("REGEXP ", maxsplit=1)[-1]
                    if ignore_case:
                        pattern = re.match(r"LOWER\((.*)\)", pattern).group(1)
                    pattern = pattern.strip("'")
                where_clause += f" AND {grep_where_clause}"
        # 加上排序条件
        if not sort_list:
            sort_list = SearchHandler(self.index_set_id, {}).sort_list
        # 构建 ORDER BY 子句
        order_by_clause = ""
        for field, direction in sort_list:
            order_field = alias_mappings.get(field, field)
            # _ext.a.b的字段名需要转化为JSON_EXTRACT的形式
            order_field = self.convert_object_field(order_field)
            if order_by_clause:
                order_by_clause += ", "
            order_by_clause += f"{order_field} {direction.upper()}"
        if order_by_clause:
            where_clause += f" ORDER BY {order_by_clause}"
        # 加上分页条件
        where_clause += f" LIMIT {size} OFFSET {begin}"
        return where_clause, pattern, ignore_case

    def add_doris_query_trace(self, sql, total_records=None, time_taken=None):
        """
        添加doris查询的trace记录
        :param sql: 执行的SQL语句
        :param total_records: 总条数
        :param time_taken: 总耗时
        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("bkdata_doris_query") as span:
            span.set_attribute("index_set_id", self.index_set_id)
            span.set_attribute("user.username", get_request_username())
            span.set_attribute("space_uid", self.data.space_uid)
            span.set_attribute("db.table", self.data.doris_table_id)
            span.set_attribute("db.statement", sql)
            span.set_attribute("db.system", "doris")
            span.set_attribute("total_records", total_records)
            span.set_attribute("time_taken", time_taken)


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
        trace_params = {"sql": parsed_sql}
        try:
            # 执行doris查询
            data = self.fetch_query_data(parsed_sql)
            trace_params.update({"total_records": data["total_records"], "time_taken": data["time_taken"]})
        finally:
            self.add_doris_query_trace(**trace_params)
        return data

    def parse_sql_syntax(self, doris_table_id: str, params: dict):
        """
        解析sql语法
        """
        where_clause = self.generate_sql(
            addition=params["addition"],
            start_time=params["start_time"],
            end_time=params["end_time"],
            keyword=params.get("keyword"),
            action=SQLGenerateMode.WHERE_CLAUSE.value,
            alias_mappings=params["alias_mappings"],
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
            where_condition = matches.group(2) + f" AND {where_clause}\n"
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
                    '[doris query] QUERY ERROR! username: %s, execute sql: "%s", error info: %s',
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
                '[doris query] username: %s, execute sql: "%s", total records: %s, time taken: %ss',
                get_request_username(),
                sql.replace("\n", " "),
                result_data["data"]["totalRecords"],
                result_data["data"]["timetaken"],
            )
        else:
            # 大于 5s 的判定为慢查询
            logger.info(
                '[doris query] SLOW QUERY! username: %s, execute sql: "%s", total records: %s, time taken: %ss',
                get_request_username(),
                sql.replace("\n", " "),
                result_data["data"]["totalRecords"],
                result_data["data"]["timetaken"],
            )
        return data

    def fetch_grep_query_data(self, params):
        """
        :param params: 查询相关参数
        """
        if not self.data.support_doris:
            raise IndexSetDorisQueryException()
        alias_mappings = params["alias_mappings"]
        where_clause = self.generate_sql(
            addition=params["addition"],
            start_time=params["start_time"],
            end_time=params["end_time"],
            keyword=params.get("keyword"),
            action=SQLGenerateMode.WHERE_CLAUSE.value,
            alias_mappings=alias_mappings,
        )
        grep_field = params.get("grep_field")
        where_clause, pattern, ignore_case = self.add_grep_condition(
            where_clause=where_clause,
            grep_field=grep_field,
            grep_query=params.get("grep_query"),
            alias_mappings=alias_mappings,
            sort_list=params.get("sort_list", []),
            size=params["size"],
            begin=params["begin"],
        )
        sql = f"SELECT * FROM {self.data.doris_table_id} WHERE {where_clause}"
        trace_params = {"sql": sql}
        try:
            # 执行doris查询
            result = self.fetch_query_data(sql)
            trace_params.update({"total_records": result["total_records"], "time_taken": result["time_taken"]})
        finally:
            self.add_doris_query_trace(**trace_params)
        # 添加高亮标记
        log_list = add_highlight_mark(
            data_list=result["list"],
            match_field=alias_mappings.get(grep_field, grep_field),
            pattern=pattern,
            ignore_case=ignore_case,
        )
        return {"list": log_list, "total": result["total_records"], "took": result["time_taken"]}
