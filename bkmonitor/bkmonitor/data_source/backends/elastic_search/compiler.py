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

import copy
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from django.core.exceptions import EmptyResultSet
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from bkmonitor.data_source import CpAggMethods
from bkmonitor.data_source.backends.base import compiler


class SQLCompiler(compiler.SQLCompiler):
    TIME_SECOND_AGG_FIELD_RE = re.compile(r"time\((?P<second>\d+)s\)")
    SELECT_RE = re.compile(
        r"(?P<agg_method>[^\( ]+)[\( ]+" r"(?P<metric_field>[^\) ]+)[\) ]+" r"([ ]?as[ ]+(?P<metric_alias>[^ ]+))?"
    )
    DEFAULT_AGG_METHOD = "count"
    DEFAULT_METRIC_FIELD = "_index"
    DEFAULT_METRIC_ALIAS = "count"

    DEFAULT_TIME_FIELD = "time"

    COMPOSITE_AGG_NAME = "_group_"

    METRIC_AGG_TRANSLATE = {
        "count": "value_count",
        "min": "min",
        "max": "max",
        "avg": "avg",
        "sum": "sum",
        "distinct": "cardinality",
    }

    PERCENTILES_AGG_TRANSLATE = {
        CpAggMethods["cp50"].vargs_list[0]: "50.0",
        CpAggMethods["cp90"].vargs_list[0]: "90.0",
        CpAggMethods["cp95"].vargs_list[0]: "95.0",
        CpAggMethods["cp99"].vargs_list[0]: "99.0",
    }

    operators = {
        "eq": "must terms",
        "is one of": "must terms",
        "include": "should wildcard",
        "neq": "must not terms",
        "is not one of": "must not terms",
        "exclude": "must not wildcard",
        "gt": "must range gt",
        "gte": "must range gte",
        "lt": "must range lt",
        "lte": "must range lte",
        "regexp": "must regexp",
        # https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-exists-query.html
        "exists": "must exists",
        "nexists": "must not exists",
    }

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

            __, dimensions = self._get_dimensions()
            dimensions.reverse()
            if self.query.enable_date_histogram and self.query.time_field:
                dimensions.append(self.query.time_field)

            records = []

            __, select_fields = self._parser_select()
            self._get_buckets(records, dimensions, result.get("aggregations"), select_fields)

            return records
        except Exception:
            raise

    def as_sql(self):
        dsl = {}

        return_fields, select_fields = self._parser_select()

        # 0. add _source
        if return_fields:
            dsl["_source"] = return_fields

        # 1. parse group by (agg_dimension)
        agg_interval, dimensions = self._get_dimensions()
        aggregations = self._get_aggregations(agg_interval, dimensions, select_fields)
        if aggregations:
            dsl["aggregations"] = aggregations

        # 2. parse filter & keywords_query_string
        query_content = {}
        filter_dict = self._parser_filter(self.query.where)
        if filter_dict:
            query_content["filter"] = self._parser_filter(self.query.where)

        if self.query.raw_query_string and self.query.raw_query_string != "*":
            query_string_dsl = {"query_string": {"query": self.query.raw_query_string}}
            query_content["must"] = {"bool": {"should": [query_string_dsl], "minimum_should_match": 1}}

        if self.query.nested_paths:
            for nested_path, query_string in self.query.nested_paths.items():
                if "must" not in query_content:
                    query_content["must"] = {"bool": {"should": [], "minimum_should_match": 1}}
                if query_string and query_string != "*":
                    query_content["must"]["bool"]["should"].append(
                        {"nested": {"path": nested_path, "query": {"query_string": {"query": query_string}}}}
                    )

        query_content.update(self._parse_agg_condition())

        if query_content:
            dsl["query"] = {"bool": query_content}

        dsl["sort"] = self._parser_order_by()

        dsl["size"] = self._get_size()
        if self.query.offset is not None:
            dsl["from"] = self.query.offset

        if self.query.use_full_index_names:
            dsl["use_full_index_names"] = True

        if self.query.distinct:
            dsl.update({"track_total_hits": True, "collapse": {"field": self.query.distinct}})

        return self.query.table_name, dsl

    def _parser_order_by(self):
        sort_list: List[Dict[str, str]] = []
        for ordering in self.query.order_by:
            if len(ordering.split()) == 1:
                field, order = ordering, "asc"
            else:
                field, order = ordering.split(maxsplit=1)
            sort_list.append({field: order})
        return sort_list

    def _parser_filter(self, node):
        result = {}
        params = {}
        if node.connector == "OR":
            result["bool"] = {"should": []}
            params = result["bool"]["should"]
        else:
            result["bool"] = params

        # 合并同类字段
        children = []
        field_values = defaultdict(list)
        for child in node.children:
            if isinstance(child, tuple) and len(child) == 2:
                if isinstance(child[1], (tuple, list)):
                    field_values[child[0]].extend(child[1])
                else:
                    field_values[child[0]].append(child[1])
            else:
                children.append(child)
        for field, values in field_values.items():
            children.append([field, values])
        node.children = children

        for child in node.children:
            if isinstance(child, (tuple, list)) and len(child) == 2:
                field = child[0].split("__")
                if len(field) == 1:
                    field = field[0]
                    method = "eq"
                else:
                    field, method = field[:-1], field[-1]
                    field = "__".join(field)

                if node.connector == "OR":
                    params.append({"bool": {}})
                    getattr(self, f"_operate_{method}")(params[-1]["bool"], field, child[1])
                else:
                    getattr(self, f"_operate_{method}")(params, field, child[1])
            elif isinstance(child, Q):
                sub_query = self._parser_filter(child)
                if not sub_query:
                    continue

                if node.connector == "OR":
                    params.append(sub_query)
                else:
                    params.setdefault("must", []).append(sub_query)

        if not params:
            return {}

        if len(params) == 1 and node.connector == "OR":
            result["bool"] = params[0]["bool"]

        return result

    def _parser_select(self) -> Tuple[List[str], List[Dict[str, str]]]:
        if not self.query.select:
            return [], []

        return_fields: List[str] = []
        select_fields: List[Dict[str, str]] = []
        for select_field in self.query.select:
            if "(" in select_field and ")" in select_field:
                match_result = self.SELECT_RE.match(select_field)
                group_dict = match_result.groupdict() if match_result else {}
                agg_method = group_dict.get("agg_method") or self.DEFAULT_AGG_METHOD
                metric_field = group_dict.get("metric_field") or self.DEFAULT_METRIC_FIELD
                metric_alias = group_dict.get("metric_alias") or metric_field
                select_fields.append(
                    {"agg_method": agg_method, "metric_field": metric_field, "metric_alias": metric_alias}
                )
            else:
                return_fields.append(select_field)

        return return_fields, select_fields

    def _get_size(self) -> int:
        if self.query.group_hits_size < 0:
            return 0
        if self.query.high_mark is None:
            return 1
        return self.query.high_mark - self.query.low_mark

    def _get_bucket_size(self) -> int:
        return (min(1440, self.query.high_mark or 0 - self.query.low_mark), 1440)[self.query.high_mark is None]

    def _get_dimensions(self) -> Tuple[int, List[str]]:
        second = 60
        group_by_fields = self.query.group_by
        group_by = sorted(set(group_by_fields), key=group_by_fields.index)

        dimensions = group_by[:]
        for idx, dim in enumerate(dimensions):
            time_agg_field = self.TIME_SECOND_AGG_FIELD_RE.match(dim)
            if time_agg_field:
                second = time_agg_field.groupdict().get("second")
                dimensions.pop(idx)
                break
        return second, dimensions

    def _get_agg_method_dict(self, select_fields) -> Dict[str, Dict[str, Any]]:
        agg_method_dict: Dict[str, Dict[str, Any]] = {}
        for field in select_fields:
            method: str = str(field["agg_method"]).lower()
            if method in CpAggMethods:
                agg_method_dict[field["metric_alias"]] = {
                    "percentiles": {
                        "field": field["metric_field"],
                        "percents": [int(float(self.PERCENTILES_AGG_TRANSLATE[CpAggMethods[method].vargs_list[0]]))],
                    }
                }
            else:
                agg_method_dict[field["metric_alias"]] = {
                    self.METRIC_AGG_TRANSLATE[method]: {"field": field["metric_field"]}
                }
        return agg_method_dict

    def _get_aggregations(
        self, agg_interval: int, dimensions: List[str], select_fields: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if self.query.search_after_key is None:
            return self._get_normal_aggregations(agg_interval, dimensions, select_fields)
        else:
            return self._get_composite_aggregations(agg_interval, dimensions, select_fields)

    def _get_composite_aggregations(self, agg_interval: int, dimensions, select_fields):
        if not select_fields:
            return {}

        aggregations = {
            self.COMPOSITE_AGG_NAME: {
                "composite": {
                    "size": self._get_bucket_size(),
                    "sources": [{dimension: {"terms": {"field": dimension}}} for dimension in dimensions],
                },
                "aggregations": self._get_agg_method_dict(select_fields),
            }
        }

        if self.query.search_after_key:
            aggregations[self.COMPOSITE_AGG_NAME]["composite"]["after"] = self.query.search_after_key

        return aggregations

    def _get_normal_aggregations(self, agg_interval: int, dimensions, select_fields):
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
        # 如果没有选择字段，则不聚合
        if not select_fields:
            return {}

        aggregations: Dict[str, Dict] = self._get_agg_method_dict(select_fields)
        # 每个分组获取原始数据记录
        if self.query.group_hits_size > 0:
            aggregations["latest_hits"] = {
                "top_hits": {"size": self.query.group_hits_size, "sort": [{self.query.time_field: {"order": "desc"}}]}
            }

        # metric aggregation
        if self.query.enable_date_histogram and self.query.time_field:
            # Deprecated in 7.2. interval field is deprecated
            # https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-datehistogram-aggregation.html
            # use fixed_interval instead
            aggregations = {
                self.query.time_field: {
                    "date_histogram": {
                        "field": self.query.time_field,
                        "interval": "%ss" % agg_interval,
                        "time_zone": timezone.get_current_timezone_name(),
                    },
                    "aggregations": aggregations,
                },
            }

        # dimension aggregation
        for dimension in dimensions:
            _aggregations = {dimension: {"terms": {"field": dimension, "size": self._get_bucket_size()}}}
            _aggregations[dimension]["aggregations"] = aggregations
            aggregations = _aggregations

        return aggregations

    @classmethod
    def _fill_values_to_record(cls, aggs: Dict[str, Any], record: Dict[str, Any], select_fields: List[Dict[str, Any]]):
        for field in select_fields:
            alias: str = field["metric_alias"]
            method: str = str(field["agg_method"]).lower()
            if method in CpAggMethods:
                # get value from: {"p50_duration": {"values": {"50.0": 6.0}}}
                record[alias] = (
                    aggs.get(alias, {})
                    .get("values", {})
                    .get(cls.PERCENTILES_AGG_TRANSLATE[CpAggMethods[method].vargs_list[0]])
                )
            else:
                # get value from: {"total_count": {"value": 123}}
                record[alias] = aggs.get(alias, {}).get("value")

    @classmethod
    def _handle_middle_bucket(cls, dimension: str, bucket: Dict[str, Any]) -> Dict[str, Any]:
        return bucket

    @classmethod
    def _extract_dimension_buckets(cls, dimension: str, aggs: Dict[str, Any]) -> List[Dict[str, Any]]:
        try:
            return aggs[dimension]["buckets"]
        except KeyError:
            return []

    def _get_buckets(self, records, dimensions, aggs, select_fields):
        if not aggs:
            return

        if self.query.search_after_key is None:
            return self._get_agg_buckets(records, dimensions, aggs, select_fields)
        else:
            return self._get_composite_buckets(records, dimensions, aggs, select_fields)

    def _get_agg_buckets(
        self,
        records: List[Dict[str, Any]],
        dimensions: List[str],
        aggs: Dict[str, Any],
        select_fields,
        record: Optional[Dict[str, Any]] = None,
        idx: int = 0,
    ):
        if record is None:
            record = {}

        if not dimensions:
            self._fill_values_to_record(aggs, record, select_fields)
            records.append(copy.deepcopy(record))
            return

        dimension = dimensions[idx]
        for bucket in self._extract_dimension_buckets(dimension, aggs):
            record[dimension] = bucket.get("key")
            if idx + 1 == len(dimensions):
                # 获取分组最新的一条记录
                if "latest_hits" in bucket and bucket["latest_hits"]["hits"]["hits"]:
                    record["hits"] = []
                    for hit in bucket["latest_hits"]["hits"]["hits"]:
                        record["hits"].append(hit["_source"])
                    record["hits_total"] = bucket["latest_hits"]["hits"]["total"]["value"]

                self._fill_values_to_record(bucket, record, select_fields)
                records.append(copy.deepcopy(record))
            else:
                bucket = self._handle_middle_bucket(dimension, bucket)
                self._get_agg_buckets(records, dimensions, bucket, select_fields, record, idx + 1)

    def _get_composite_buckets(self, records, dimensions, aggs, select_fields):
        aggs = aggs[self.COMPOSITE_AGG_NAME]
        for bucket in aggs["buckets"]:
            record: Dict[str, Any] = {"_after_key_": aggs["after_key"]}
            record.update({dimension: bucket["key"].get(dimension) for dimension in dimensions})
            self._fill_values_to_record(bucket, record, select_fields)

            records.append(record)

    def _parse_agg_condition(self):
        """
        agg_condition format:
         [{u'key': u'bk_cloud_id', u'method': u'gte', u'value': u'2'},
         {u'condition': u'and', u'key': u'ip', u'value': u'127.0.0.1', u'method': u'is'},
         {u'condition': u'or', u'key': u'bk_cloud_id', u'value': u'2', u'method': u'lt'},
         {u'condition': u'and', u'key': u'ip', u'value': u'127.0.0.2', u'method': u'is not one of'}]
        列表结构：
        - 每一个item代表一个条件，第一个item，没有condition连接字段
        - 以or为分割，将各个部分的条件用括号括起来

        返回结果: 使用Q表达式包起来
        Q(bk_cloud_id='2', ip='127.0.0.1') | Q(bk_cloud_id='2', ip='127.0.0.2')

        {
            "should": [{
                "bool": {
                    "must": [{
                        "range": {
                            "bk_cloud_id": {
                                "gte": "2"
                            }
                        }
                    }, {
                        "term": {
                            "ip": "127.0.0.1"
                        }
                    }]
                }
            }, {
                "bool": {
                    "must_not": [{
                        "terms": {
                            "ip": ["127.0.0.2"]
                        }
                    }],
                    "must": [{
                        "range": {
                            "bk_cloud_id": {
                                "lt": "2"
                            }
                        }
                    }]
                }
            }]
        }
        """

        if not self.query.agg_condition:
            return {}

        condition_list = []

        where_cond = {}
        for cond in self.query.agg_condition:
            field_lookup = "{}__{}".format(cond["key"], cond["method"])
            value = cond["value"]

            condition = cond.get("condition")
            if condition:
                if condition.upper() == "AND":
                    where_cond[field_lookup] = value
                elif condition.upper() == "OR":
                    condition_list.append(where_cond)
                    where_cond = {field_lookup: value}
                else:
                    raise Exception("Unsupported connector(%s)" % condition)
            else:
                where_cond = {field_lookup: value}

        if where_cond:
            condition_list.append(where_cond)
        ret = {"should": [], "minimum_should_match": 1}
        for and_condition in condition_list:
            and_map = {}
            for key, values in and_condition.items():
                field, operator = key.split("__")
                if not isinstance(values, list):
                    values = [values]
                func = getattr(self, "_operate_{}".format(operator), None)
                if func is None:
                    raise Exception(_("不支持的条件({})".format(operator)))
                func(and_map, field, values)
            ret["should"].append({"bool": and_map})
        return ret

    @staticmethod
    def _operate_eq(and_map, field, values):
        and_map.setdefault("must", []).append({"terms": {field: values}})

    @staticmethod
    def _operate_neq(and_map, field, values):
        and_map.setdefault("must_not", []).append({"terms": {field: values}})

    @staticmethod
    def _operate_include(and_map, field, values):
        for value in values:
            and_map.setdefault("should", []).append({"wildcard": {field: "*{}*".format(value)}})

    @staticmethod
    def _operate_nested(and_map, field: str, values):
        field, path, lookup = field.rsplit("__", 2)

        def _nested_query(_query: Dict[str, Any]):
            return {"nested": {"path": path, "query": _query}}

        if lookup == "qs":
            for value in values:
                if field == "*":
                    and_map.setdefault("must", []).append({"query_string": {"query": value}})
                elif path == "*":
                    and_map.setdefault("must", []).append({"query_string": {"query": value, "default_field": field}})
                else:
                    and_map.setdefault("must", []).append(
                        _nested_query({"query_string": {"query": value, "default_field": field}})
                    )
        elif lookup == "eq" or lookup == "include":
            op: str = {"eq": "term", "include": "wildcard"}[lookup]
            for value in values:
                and_map.setdefault("must", []).append(_nested_query({op: {field: {"value": value}}}))

    @staticmethod
    def _operate_exclude(and_map, field, values):
        for value in values:
            and_map.setdefault("must_not", []).append({"wildcard": {field: "*{}*".format(value)}})

    @staticmethod
    def _operate_gt(and_map, field, values):
        and_map.setdefault("must", []).append({"range": {field: {"gt": max(values)}}})

    @staticmethod
    def _operate_gte(and_map, field, values):
        and_map.setdefault("must", []).append({"range": {field: {"gte": max(values)}}})

    @staticmethod
    def _operate_lt(and_map, field, values):
        and_map.setdefault("must", []).append({"range": {field: {"lt": min(values)}}})

    @staticmethod
    def _operate_lte(and_map, field, values):
        and_map.setdefault("must", []).append({"range": {field: {"lte": min(values)}}})

    @staticmethod
    def _operate_regexp(and_map, field, values):
        for value in values:
            and_map.setdefault("must", []).append({"regexp": {field: value}})

    @staticmethod
    def _operate_reg(and_map, field, values):
        for value in values:
            and_map.setdefault("must", []).append({"regexp": {field: value}})

    @staticmethod
    def _operate_exists(and_map, field, values):
        and_map.setdefault("must", []).append({"exists": {"field": field}})

    @staticmethod
    def _operate_nexists(and_map, field, values):
        and_map.setdefault("must_not", []).append({"exists": {"field": field}})
