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
import logging
import re

from django.core.exceptions import EmptyResultSet
from django.db.models import Q
from django.utils import timezone

from bkmonitor.data_source.backends.base import compiler
from constants.common import DEFAULT_TENANT_ID

logger = logging.getLogger("bkmonitor.data_source.log_search")


class SQLCompiler(compiler.SQLCompiler):
    TIME_SECOND_AGG_FIELD_RE = re.compile(r"time\((?P<second>\d+)s\)")
    SELECT_RE = re.compile(
        r"(?P<agg_method>[^\( ]+)[\( ]+" r"(?P<metric_field>[^\) ]+)[\) ]+" r"([ ]?as[ ]+(?P<metric_alias>[^ ]+))?"
    )
    SPECIAL_CHARS = re.compile(r'([+\-=&|><!(){}[\]^"~*?\\:\/ ])')
    ESCAPED_SPECIAL_CHARS = re.compile(r'\\([+\-=&|><!(){}[\]^"~*?\\:\/ ])')

    DEFAULT_AGG_METHOD = "count"
    DEFAULT_METRIC_FIELD = "_index"
    DEFAULT_METRIC_ALIAS = "count"

    DEFAULT_TIME_FIELD = "dtEventTimeStamp"

    METRIC_AGG_TRANSLATE = {"count": "value_count", "min": "min", "max": "max", "avg": "avg", "sum": "sum"}

    def execute_sql(self):
        try:
            sql, params = self.as_sql()
        except Exception:
            raise

        if not params:
            raise EmptyResultSet

        try:
            result = self.connection.execute(sql, params)
            if not result:
                return []

            _, metric_field, metric_alias = self._get_metric()

            agg_interval, dimensions = self._get_dimensions()
            dimensions.reverse()
            dimensions.append(self._get_time_field())

            records = []
            self._get_buckets(records, {}, dimensions, 0, result.get("aggregations"), metric_alias)
            return records
        except Exception:
            raise

    def _parse_filter(self, node):
        sub_queries = []
        for child in node.children:
            if isinstance(child, tuple) and len(child) == 2:
                field = child[0].split("__")
                if len(field) == 1 or "" in field:
                    field = child[0]
                    method = "eq"
                else:
                    field, method = field[:-1], field[-1]
                    field = "__".join(field)

                if not isinstance(child[1], list):
                    values = [child[1]]
                else:
                    values = child[1]

                if not values:
                    continue

                # 转义特殊字符
                values = [self.escape_char(value) for value in values]

                # 映射操作符到查询语法模板
                connector = "OR"
                if method == "eq":
                    expr_template = '{}: "{}"'
                elif method == "neq":
                    expr_template = 'NOT {}: "{}"'
                    connector = "AND"
                elif method == "gt":
                    expr_template = "{}: ({}, *)"
                    values = [max(values)]
                elif method == "gte":
                    expr_template = "{}: [{}, *)"
                    values = [max(values)]
                elif method == "lt":
                    expr_template = "{}: (*, {})"
                    values = [min(values)]
                elif method == "lte":
                    expr_template = "{}: (*, {}]"
                    values = [min(values)]
                elif method == "include":
                    expr_template = "{}: *{}*"
                elif method == "exclude":
                    expr_template = "NOT {}: *{}*"
                    connector = "AND"
                else:
                    continue

                sub_query_string = f" {connector} ".join(expr_template.format(field, value) for value in values)
                if len(values) > 1:
                    sub_query_string = f"({sub_query_string})"

                sub_queries.append(sub_query_string)
            elif isinstance(child, Q):
                sub_query_string = self._parse_filter(child)
                if not sub_query_string:
                    continue
                sub_queries.append(sub_query_string)

        query_string = f" {node.connector} ".join(sub_queries)
        if len(sub_queries) > 1:
            query_string = f"({query_string})"

        return query_string

    def escape_char(self, s):
        """
        转义query string中的特殊字符
        """
        if not isinstance(s, str):
            return s

        # 避免双重转义：先移除已有转义
        s = self.ESCAPED_SPECIAL_CHARS.sub(r"\1", s)
        return self.SPECIAL_CHARS.sub(r"\\\1", str(s))

    def as_sql(self):
        bk_tenant_id = self.query.bk_tenant_id
        if not bk_tenant_id:
            logger.warning(
                f"get_query_tenant_id is empty, log query: {self.query.index_set_id or self.query.table_name or self.query.raw_query_string}"
            )
            bk_tenant_id = DEFAULT_TENANT_ID

        result = {"bk_tenant_id": bk_tenant_id}
        time_field = self._get_time_field()

        # 0. parse select field(metric_field)
        agg_method, metric_field, metric_alias = self._get_metric()

        # 1. parse indices / index_set_id
        if self.query.index_set_id:
            result["index_set_id"] = self.query.index_set_id
        elif self.query.table_name:
            result["indices"] = self.query.table_name
            result["time_field"] = time_field
        else:
            raise Exception("SQL Error: Empty table name")

        # 2. parse group by (agg_dimension)
        agg_interval, dimensions = self._get_dimensions()
        result["aggs"] = self._get_aggregations(agg_interval, dimensions, agg_method, metric_field, metric_alias)

        # 3. parse filter (agg_condition)
        if self.query.agg_condition:
            query_filter = []
            for cond in self.query.agg_condition:
                new_cond = {
                    "field": cond.get("field", cond.get("key")),
                    "operator": cond.get("operator", cond.get("method")),
                    "value": cond["value"],
                }
                if "condition" in cond:
                    new_cond["condition"] = cond["condition"]
                query_filter.append(new_cond)
            result["filter"] = query_filter

        # 4. parse where (get start_time/end_time from where node)
        time_field_list = [f"{time_field}__{method}" for method in ["lt", "lte", "gt", "gte"]]
        where_dict = {}
        for i in self.query.where.children:
            if isinstance(i, tuple) and len(i) == 2:
                where_dict[i[0]] = i[1]
        self.query.where.children = [
            i
            for i in self.query.where.children
            if not (isinstance(i, tuple) and len(i) == 2 and i[0] in time_field_list)
        ]

        gte_field = f"{time_field}__gte"
        lte_field = f"{time_field}__lte"
        lt_field = f"{time_field}__lt"
        start_time = where_dict.get(gte_field)
        end_time = where_dict.get(lte_field) or where_dict.get(lt_field)
        if start_time:
            result["start_time"] = start_time // 1000
        if end_time:
            result["end_time"] = end_time // 1000

        # 5. parse keywords_query_string
        filter_string = self._parse_filter(self.query.where)
        if self.query.raw_query_string and self.query.raw_query_string != "*":
            if filter_string:
                result["query_string"] = f"({self.query.raw_query_string}) AND {self._parse_filter(self.query.where)}"
            else:
                result["query_string"] = self.query.raw_query_string
        elif filter_string:
            result["query_string"] = self._parse_filter(self.query.where)

        # 6. set limit offset/size
        if self.query.high_mark is not None:
            result["size"] = self.query.high_mark - self.query.low_mark
        else:
            result["size"] = 1

        # result["sort_list"] = [[time_field, "desc"]]

        if self.query.offset is not None:
            result["start"] = self.query.offset

        return "", result

    def _get_metric(self):
        if self.query.select:
            select_field = self.query.select[0]
            if "(" in select_field and ")" in select_field:
                match_result = self.SELECT_RE.match(select_field)
                group_dict = match_result.groupdict() if match_result else {}
                agg_method = group_dict.get("agg_method") or self.DEFAULT_AGG_METHOD
                metric_field = group_dict.get("metric_field") or self.DEFAULT_METRIC_FIELD
                metric_alias = group_dict.get("metric_alias") or metric_field
                return agg_method, metric_field, metric_alias
            else:
                return self.DEFAULT_AGG_METHOD, select_field, select_field
        else:
            return self.DEFAULT_AGG_METHOD, self.DEFAULT_METRIC_FIELD, self.DEFAULT_METRIC_ALIAS

    def _get_dimensions(self):
        group_by_fields = self.query.group_by
        group_by = sorted(set(group_by_fields), key=group_by_fields.index)

        second = 60
        dimensions = group_by[:]
        for idx, dim in enumerate(dimensions):
            time_agg_field = self.TIME_SECOND_AGG_FIELD_RE.match(dim)
            if time_agg_field:
                second = time_agg_field.groupdict().get("second")
                dimensions.pop(idx)
                break
        return second, dimensions

    def _get_time_field(self):
        return self.query.time_field or self.DEFAULT_TIME_FIELD

    def _get_aggregations(self, agg_interval, dimensions, agg_method, metric_field, metric_alias):
        """
        agg format:

        "aggregations": {
            "name": {
                "terms": {
                    "field": "name",
                    "size": 10
                },
                "aggregations": {
                    "host": {
                        "terms": {
                            "field": "host",
                            "size": 0
                        },
                        "aggregations": {
                            "dtEventTimeStamp": {
                                "date_histogram": {
                                    "field": "dtEventTimeStamp",
                                    'interval': "minute",

                                },
                                "aggregations": {
                                    "count": {
                                        "value_count": {
                                            "field": "_index"
                                        }
                                    }
                                }
                            }
                        },
                    }
                }
            }
        }
        """

        # metric aggregation
        metric_agg_method = self.METRIC_AGG_TRANSLATE[str(agg_method).lower()]
        metric_aggragations = {metric_alias: {metric_agg_method: {"field": metric_field}}}

        # datetime aggregation
        time_field = self._get_time_field()
        aggragations = {
            time_field: {
                "date_histogram": {
                    "field": time_field,
                    "interval": f"{agg_interval}s",
                    "time_zone": timezone.get_current_timezone().zone,
                },
                "aggregations": metric_aggragations,
            },
        }

        # dimension aggregation
        for dimension in dimensions:
            _aggragations = {dimension: {"terms": {"field": dimension, "size": 10000}}}
            _aggragations[dimension]["aggregations"] = aggragations
            aggragations = _aggragations

        return aggragations

    def _get_buckets(self, records, record, dimensions, i, aggs, metric_alias):
        if not aggs:
            return

        if dimensions:
            count = len(dimensions)
            buckets = aggs.get(dimensions[i]).get("buckets")
            dimension = dimensions[i]
            for bucket in buckets:
                record[dimension] = bucket.get("key")
                if i + 1 == count:
                    record[metric_alias] = bucket.get(metric_alias).get("value")
                    records.append(copy.deepcopy(record))
                else:
                    self._get_buckets(records, record, dimensions, i + 1, bucket, metric_alias)
        else:
            record[metric_alias] = aggs.get(metric_alias).get("value")
            records.append(copy.deepcopy(record))


class SQLInsertCompiler(compiler.SQLInsertCompiler, SQLCompiler):
    pass


class SQLDeleteCompiler(compiler.SQLDeleteCompiler, SQLCompiler):
    pass


class SQLUpdateCompiler(compiler.SQLUpdateCompiler, SQLCompiler):
    pass


class SQLAggregateCompiler(compiler.SQLAggregateCompiler, SQLCompiler):
    pass
