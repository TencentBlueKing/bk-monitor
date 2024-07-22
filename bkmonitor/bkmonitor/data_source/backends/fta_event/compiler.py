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

from bkmonitor.data_source.backends.elastic_search.compiler import (
    SQLCompiler as ElasticSearchSQLCompiler,
)


class SQLCompiler(ElasticSearchSQLCompiler):
    RAW_FIELDS = ["alert_name"]
    TAGS_FIELD_PREFIX = "tags."
    DEFAULT_TIME_FIELD = "time"

    def _get_aggregations(self, agg_interval, dimensions, select_fields):
        """
        agg format:

        "aggs": {
            "name": {
                "terms": {
                    "field": "name",
                    "size": 10
                },
                "aggs": {
                    "host": {
                        "terms": {
                            "field": "host",
                            "size": 0
                        },
                        "aggs": {
                            "dtEventTimeStamp": {
                                "date_histogram": {
                                    "field": "dtEventTimeStamp",
                                    'interval': "minute",

                                },
                                "aggs": {
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

        # metric aggregation
        if self.query.time_field:
            aggs = {
                self.query.time_field: {
                    "date_histogram": {"field": self.query.time_field, "interval": "%sm" % agg_interval},
                    "aggs": self._get_agg_method_dict(select_fields),
                },
            }
        else:
            aggs = self._get_agg_method_dict(select_fields)

        # dimension aggregation
        for dimension in dimensions:
            if dimension.startswith(SQLCompiler.TAGS_FIELD_PREFIX):
                tag_key = dimension[len(SQLCompiler.TAGS_FIELD_PREFIX) :]
                _aggs = {
                    dimension: {
                        "nested": {"path": "tags"},
                        "aggs": {
                            "key": {
                                "filter": {"term": {"tags.key": tag_key}},
                                "aggs": {
                                    "value": {
                                        "terms": {"field": "tags.value.raw", "size": 1440},
                                        "aggs": {"_reverse": {"reverse_nested": {}, "aggs": aggs}},
                                    }
                                },
                            },
                        },
                    }
                }
            else:
                if dimension in self.RAW_FIELDS:
                    field = f"{dimension}.raw"
                else:
                    field = dimension
                _aggs = {dimension: {"terms": {"field": field, "size": 1440}, "aggs": aggs}}
            aggs = _aggs
        return aggs

    def _get_buckets(self, records, record, dimensions, i, aggs, metric_alias):
        if not aggs:
            return

        if dimensions:
            count = len(dimensions)
            dimension = dimensions[i]
            if dimension.startswith(self.TAGS_FIELD_PREFIX):
                buckets = aggs[dimension]["key"]["value"]["buckets"]
            else:
                buckets = aggs[dimension]["buckets"]
            for bucket in buckets:
                record[dimension] = bucket.get("key")
                if i + 1 == count:
                    for alias in metric_alias:
                        record[alias] = bucket.get(alias).get("value")
                    records.append(copy.deepcopy(record))
                else:
                    if dimension.startswith(self.TAGS_FIELD_PREFIX):
                        bucket = bucket["_reverse"]
                    self._get_buckets(records, record, dimensions, i + 1, bucket, metric_alias)
        else:
            for alias in metric_alias:
                record[alias] = aggs.get(alias).get("value")
            records.append(copy.deepcopy(record))

    @staticmethod
    def _operate_eq(and_map, field, values):
        dsl = SQLCompiler._convert_tag_query("terms", field, values)
        and_map.setdefault("must", []).append(dsl)

    @staticmethod
    def _operate_neq(and_map, field, values):
        dsl = SQLCompiler._convert_tag_query("terms", field, values)
        and_map.setdefault("must_not", []).append(dsl)

    @staticmethod
    def _operate_include(and_map, field, values):
        for value in values:
            dsl = SQLCompiler._convert_tag_query("wildcard", field, "*{}*".format(value))
            and_map.setdefault("should", []).append(dsl)

    @staticmethod
    def _operate_exclude(and_map, field, values):
        for value in values:
            dsl = SQLCompiler._convert_tag_query("wildcard", field, "*{}*".format(value))
            and_map.setdefault("must_not", []).append(dsl)

    @staticmethod
    def _operate_gt(and_map, field, values):
        dsl = SQLCompiler._convert_tag_query("range", field, {"gt": max(values)})
        and_map.setdefault("must", []).append(dsl)

    @staticmethod
    def _operate_gte(and_map, field, values):
        dsl = SQLCompiler._convert_tag_query("range", field, {"gte": max(values)})
        and_map.setdefault("must", []).append(dsl)

    @staticmethod
    def _operate_lt(and_map, field, values):
        dsl = SQLCompiler._convert_tag_query("range", field, {"lt": min(values)})
        and_map.setdefault("must", []).append(dsl)

    @staticmethod
    def _operate_lte(and_map, field, values):
        dsl = SQLCompiler._convert_tag_query("range", field, {"lte": min(values)})
        and_map.setdefault("must", []).append(dsl)

    @staticmethod
    def _operate_regexp(and_map, field, values):
        for value in values:
            dsl = SQLCompiler._convert_tag_query("regexp", field, value)
            and_map.setdefault("must", []).append(dsl)

    @staticmethod
    def _operate_reg(and_map, field, values):
        for value in values:
            dsl = SQLCompiler._convert_tag_query("regexp", field, value)
            and_map.setdefault("must", []).append(dsl)

    @classmethod
    def _convert_tag_query(cls, operate, field, value):
        """
        对标签查询进行特殊转换
        """
        if field == cls.DEFAULT_TIME_FIELD:
            # 对时间字段的特殊处理，毫秒转为秒
            if isinstance(value, int):
                return {operate: {field: int(str(value)[:10])}}
            elif isinstance(value, dict):
                for k in value:
                    if isinstance(value[k], int):
                        value[k] = int(str(value[k])[:10])
                return {operate: {field: value}}

        if not field.startswith(SQLCompiler.TAGS_FIELD_PREFIX):
            return {operate: {field: value}}
        # 从field中裁剪出真实的tag key
        tag_key = field[len(SQLCompiler.TAGS_FIELD_PREFIX) :]
        dsl = {
            "nested": {
                "path": "tags",
                "query": {
                    "bool": {
                        "must": [
                            {
                                "term": {
                                    "tags.key": tag_key,
                                }
                            },
                            {
                                operate: {
                                    "tags.value.raw": value,
                                }
                            },
                        ]
                    }
                },
            }
        }
        return dsl
