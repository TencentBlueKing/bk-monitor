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
import time
from abc import ABC
from typing import Callable, Dict, List, Optional

from django.utils.translation import ugettext as _
from elasticsearch_dsl import AttrDict, Q, Search
from elasticsearch_dsl.aggs import Bucket
from elasticsearch_dsl.response import Response
from luqum.auto_head_tail import auto_head_tail
from luqum.elasticsearch import ElasticsearchQueryBuilder, SchemaAnalyzer
from luqum.exceptions import ParseError
from luqum.parser import lexer, parser
from luqum.tree import AndOperation, FieldGroup, SearchField, Word

from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.utils.elasticsearch.handler import BaseTreeTransformer
from bkmonitor.utils.ip import exploded_ip
from bkmonitor.utils.request import get_request, get_request_username
from constants.alert import EventTargetType
from core.errors.alert import QueryStringParseError
from fta_web.alert.handlers.translator import AbstractTranslator


class QueryField:
    def __init__(
        self,
        field: str,
        display: str,
        es_field: str = None,
        agg_field: str = None,
        searchable: bool = True,
        is_char: bool = False,
        alias_func: Optional[Callable[[SearchField], None]] = None,
    ):
        """
        :param field: 展示的字段英文名
        :param display: 展示的字段中文名
        :param es_field: 实际用于查询ES的底层字段名
        :param agg_field: ES 用于聚合计算的字段
        :param searchable: 是否为计算字段（即不在ES中保存）
        :param is_char: 是否为字符字段
        :param alias_func:
        """
        self.field = field
        self.display = display
        self.es_field = field if es_field is None else es_field
        self.agg_field = self.es_field if agg_field is None else agg_field
        self.searchable = searchable
        self.is_char = is_char
        self.alias_func = alias_func

    def get_value_by_es_field(self, data: dict):
        """
        根据ES字段从Hit中拿出对应字段数据
        :param data:
        :return:
        """
        if not self.es_field:
            return None
        value = data
        try:
            for path in self.es_field.split("."):
                value = value.get(path, None)
        except Exception:
            value = None
        return value


class BaseQueryTransformer(BaseTreeTransformer):
    """
    Elasticsearch 自定义 query_string 到 标准化 query_string 转换器
    """

    # 可供查询的ES字段配置
    query_fields: List[QueryField] = []

    # 需要转换的嵌套KV字段，key 为匹配前缀，value 为搜索字段
    # 例如 "tags.": "event.tags"
    NESTED_KV_FIELDS = {}

    # 需要进行值转换的字段
    VALUE_TRANSLATE_FIELDS = {}

    # ES 文档类
    doc_cls = None

    def visit_search_field(self, node, context):
        if context.get("ignore_search_field"):
            yield from self.generic_visit(node, context)
        else:
            origin_node_name = node.name
            for field, es_field in self.NESTED_KV_FIELDS.items():
                if node.name.startswith(f"{field}."):
                    self.has_nested_field = True
                    # 对标签进行特殊处理， (tags.a : b) => (tags.key : a AND tags.value : b)
                    node = SearchField(
                        es_field,
                        FieldGroup(
                            AndOperation(
                                SearchField("key", Word(node.name[len(field) + 1 :])), SearchField("value", node.expr)
                            )
                        ),
                    )
                    break
            else:
                query_field = self.get_field_info(node.name)
                if query_field and query_field.alias_func:
                    query_field.alias_func(node)

                node = SearchField(self.transform_field_to_es_field(node.name), node.expr)

            if node.name == "event.ipv6":
                ipv6 = exploded_ip(node.expr.value.strip('"'))
                node.expr.value = f"\"{ipv6}\""

            yield from self.generic_visit(
                node, {"search_field_name": node.name, "search_field_origin_name": origin_node_name}
            )

    @classmethod
    def transform_query_string(cls, query_string: str):
        if not query_string:
            return ""
        try:
            query_tree = parser.parse(query_string, lexer=lexer)
        except ParseError as e:
            raise QueryStringParseError({"msg": e})

        transformer = cls()
        query_tree = transformer.visit(query_tree)

        if getattr(transformer, "has_nested_field", False) and cls.doc_cls:
            # 如果有嵌套字段，就不能用 query_string 查询了，需要转成 dsl（dsl 模式并不能完全兼容 query_string，只是折中方案）
            schema_analyzer = SchemaAnalyzer(cls.doc_cls._index.to_dict())
            es_builder = QueryBuilder(**schema_analyzer.query_builder_options())
            dsl = es_builder(query_tree)
            return dsl

        # 手动修改后的语法数可能会有一些空格丢失的问题，因此需要对树的头尾进行重整
        query_tree = auto_head_tail(query_tree)

        return str(query_tree)

    @classmethod
    def get_field_info(cls, field: str) -> Optional[QueryField]:
        """查询 QueryField"""
        for field_info in cls.query_fields:
            if field_info.searchable and field in [field_info.field, str(field_info.display), _(field_info.display)]:
                return field_info

    @classmethod
    def transform_field_to_es_field(cls, field: str, for_agg=False):
        """
        将字段名转换为ES可查询的真实字段名
        """
        field_info = cls.get_field_info(field)
        if field_info:
            return field_info.agg_field if for_agg else field_info.es_field

        return field


class BaseQueryHandler:
    # query_string 语法树自定义解析类
    query_transformer = None

    class DurationOption:
        # 关于时间差的选项
        FILTER = {
            "minute": {"lt": 60 * 60},
            "hour": {"gte": 60 * 60, "lt": 24 * 60 * 60},
            "day": {"gte": 24 * 60 * 60},
        }
        AGG = {
            "minute": {"key": "minute", "to": 60 * 60},
            "hour": {"key": "hour", "from": 60 * 60, "to": 24 * 60 * 60},
            "day": {"key": "day", "from": 24 * 60 * 60},
        }
        QUERYSTRING = {
            "minute": f"<{60 * 60}",
            "hour": f"[{60 * 60} TO {24 * 60 * 60}]",
            "day": f">{24 * 60 * 60}",
        }
        DISPLAY = {
            "minute": _("小于1h"),
            "hour": _("大于1h且小于1d"),
            "day": _("大于1d"),
        }

    def __init__(
        self,
        start_time: int = None,
        end_time: int = None,
        ordering: List[str] = None,
        query_string: str = "",
        conditions: List = None,
        page: int = 1,
        page_size: int = 10,
        **kwargs,
    ):
        self.start_time = start_time
        # 结束时间为未来时间的时候，默认为当前时间 加1min
        self.end_time = end_time
        if self.end_time:
            self.end_time = min(int(time.time() + 60), end_time)
        self.query_string = query_string
        self.conditions = conditions
        self.page = page
        self.page_size = page_size

        # 转换 ordering 字段
        self.ordering = self.query_transformer.transform_ordering_fields(ordering)
        # 转换 condition 的字段
        self.conditions = self.query_transformer.transform_condition_fields(conditions)

    def scan(self):
        """
        扫描全量符合条件的文档
        """
        search_object = self.get_search_object()
        search_object = self.add_conditions(search_object)
        search_object = self.add_query_string(search_object)
        search_object = self.add_ordering(search_object)

        for hit in search_object.params(preserve_order=True).scan():
            yield self.handle_hit(hit)

    def export(self):
        """
        将数据导出，用于生成 csv 文件
        :return:
        """
        docs = []
        for hit in self.scan():
            doc = {}
            for field in self.query_transformer.query_fields:
                # 替换字段名为中文（表头）
                doc[str(field.display)] = hit.get(field.field)
            docs.append(doc)
        return docs

    def get_search_object(self, *args, **kwargs) -> Search:
        """
        获取ES查询对象的方式，子类必须实现
        """
        raise NotImplementedError

    def add_pagination(self, search_object: Search, page: int = None, page_size: int = None):
        """
        分页
        """
        page = self.page if page is None else page
        page_size = self.page_size if page_size is None else page_size

        end_offset = page * page_size
        start_offset = end_offset - page_size
        search_object = search_object[start_offset:end_offset]
        return search_object

    def add_ordering(self, search_object: Search, ordering=None):
        """
        排序
        """
        ordering = self.ordering if ordering is None else self.query_transformer.transform_ordering_fields(ordering)

        if ordering:
            search_object = search_object.sort(*ordering)

        return search_object

    def add_query_string(self, search_object: Search, query_string: str = None):
        """
        处理 query_string
        """
        query_string = self.query_string if query_string is None else query_string
        if query_string:
            query_dsl = self.query_transformer.transform_query_string(query_string)
            if isinstance(query_dsl, str):
                # 如果 query_dsl 是字符串，就使用 query_string 查询
                search_object = search_object.query("query_string", query=query_dsl)
            else:
                # 如果 query_dsl 是字典，就使用 filter 查询
                search_object = search_object.query(query_dsl)
        return search_object

    def add_conditions(self, search_object: Search, conditions: List = None):
        """
        处理 filter 条件
        """
        conditions = (
            self.conditions if conditions is None else self.query_transformer.transform_condition_fields(conditions)
        )

        if not conditions:
            return search_object

        cond_q = None
        for condition in conditions:
            q = self.parse_condition_item(condition)
            if condition["method"] == "neq":
                q = ~q
            if cond_q is None:
                cond_q = q
            elif condition["condition"] == "or":
                cond_q |= q
            else:
                cond_q &= q

        if cond_q is not None:
            search_object = search_object.filter(cond_q)

        return search_object

    def parse_condition_item(self, condition: dict) -> Q:
        """
        解析单个filter条件为 Q
        """
        return Q("terms", **{condition["key"]: condition["value"]})

    @classmethod
    def calculate_agg_interval(cls, start_time: int, end_time: int, interval: str = "auto"):
        """
        根据起止时间计算聚合步长
        返回单位：秒
        """
        if not interval or interval == "auto":
            hour_interval = (end_time - start_time) // 3600
            if hour_interval <= 1:
                # 1分钟
                interval = 60
            elif hour_interval <= 6:
                # 5分钟
                interval = 5 * 60
            elif hour_interval <= 72:
                # 1小时
                interval = 60 * 60
            else:
                # 1天
                interval = 24 * 60 * 60
        else:
            interval = int(interval)

        return interval

    @classmethod
    def handle_hit_list(cls, hits=None):
        hits = hits or []
        return [cls.handle_hit(hit) for hit in hits]

    @classmethod
    def handle_hit(cls, hit):
        if isinstance(hit, dict):
            data = hit
        else:
            data = hit.to_dict()

        if not cls.query_transformer.query_fields:
            return data

        cleaned_data = {}

        # 固定字段
        for field in cls.query_transformer.query_fields:
            cleaned_data[field.field] = field.get_value_by_es_field(data)
        return cleaned_data

    @classmethod
    def make_empty_response(cls):
        """
        构造一个空的ES返回请求
        :return:
        """
        result = {"hits": {"total": {"value": 0, "relation": "eq"}, "max_score": 1.0, "hits": []}}
        return Response(Search(), result)

    def add_agg_bucket(self, search_object: Bucket, field: str, size: int = 10, bucket_count_suffix: str = ""):
        """
        按字段添加聚合桶
        """
        # 处理桶排序
        if field.startswith("-"):
            order = {"_count": "desc"}
            actual_field = field[1:]
        elif field.startswith("+"):
            order = {"_count": "asc"}
            actual_field = field[1:]
        else:
            # 默认情况
            order = {"_count": "desc"}
            actual_field = field

        if actual_field.startswith("tags."):
            # tags 标签需要做嵌套查询
            tag_key = actual_field[len("tags.") :]

            # 进行桶聚合
            new_search_object = (
                search_object.bucket(field, "nested", path="event.tags")
                .bucket("key", "filter", {"term": {"event.tags.key": tag_key}})
                .bucket(
                    "value",
                    "terms",
                    field="event.tags.value.raw",
                    size=size,
                    order=order,
                )
            )

            # 计算桶的个数
            if bucket_count_suffix:
                search_object.bucket(f"{field}{bucket_count_suffix}", "nested", path="event.tags").bucket(
                    "key", "filter", {"term": {"event.tags.key": tag_key}}
                ).bucket("value", "cardinality", field="event.tags.value.raw")
        else:
            agg_field = self.query_transformer.transform_field_to_es_field(actual_field, for_agg=True)
            if agg_field == "duration":
                # 对于Duration，需要进行范围桶聚合
                new_search_object = search_object.bucket(
                    field,
                    "range",
                    ranges=list(self.DurationOption.AGG.values()),
                    field=agg_field,
                )
            else:
                new_search_object = search_object.bucket(
                    field,
                    "terms",
                    field=agg_field,
                    order=order,
                    size=size,
                )
            if bucket_count_suffix:
                search_object.bucket(f"{field}{bucket_count_suffix}", "cardinality", field=agg_field)

        return new_search_object

    def top_n(self, fields: List, size=10, translators: Dict[str, AbstractTranslator] = None, char_add_quotes=True):
        """
        字段值 TOP N 统计
        :param fields: 需要统计的字段，"+abc" 为升序排列，"-abc" 为降序排列，默认降序排列
        :param size: 大小
        :param translators: 翻译配置
        :param char_add_quotes: 字符字段是否需要加上双引号
        :return:
        {
            "doc_count": 10,
            "fields": [
                {
                    "field": "alert_name",
                    "bucket_count": 10,
                    "buckets": [
                        {
                            "key": "CPU Usage",
                            "doc_count": 5
                        }
                    ]
                }
            ]
        }
        """
        translators = translators or {}

        search_object = self.get_search_object()
        search_object = self.add_conditions(search_object)
        search_object = self.add_query_string(search_object)
        search_object = search_object.params(track_total_hits=True).extra(size=0)

        # 最多不能超过10000个桶
        size = min(size, 10000)

        bucket_count_suffix = ".bucket_count"

        for field in fields:
            self.add_agg_bucket(search_object.aggs, field, size=size, bucket_count_suffix=bucket_count_suffix)

        search_result = search_object.execute()

        result = {
            "doc_count": search_result.hits.total.value,
            "fields": [],
        }

        char_fields = [field_info.field for field_info in self.query_transformer.query_fields if field_info.is_char]

        # 返回结果的数据处理
        for field in fields:
            if not search_result.aggs:
                result["fields"].append(
                    {
                        "field": field,
                        "is_char": field in char_fields,
                        "bucket_count": 0,
                        "buckets": [],
                    }
                )
                continue

            actual_field = field.strip("-+")

            if actual_field.startswith("tags."):
                bucket_count = getattr(search_result.aggs, f"{field}{bucket_count_suffix}").key.value.value
                buckets = [
                    {"id": bucket.key, "name": bucket.key, "count": bucket.doc_count}
                    for bucket in getattr(search_result.aggs, field).key.value.buckets
                ]
            elif actual_field == "duration":
                bucket_count = len(self.DurationOption.AGG)
                buckets = [
                    {
                        "id": self.DurationOption.QUERYSTRING[bucket.key],
                        "name": self.DurationOption.DISPLAY[bucket.key],
                        "count": bucket.doc_count,
                    }
                    for bucket in getattr(search_result.aggs, field).buckets
                ]
            elif actual_field == "bk_biz_id" and hasattr(self, "authorized_bizs"):
                buckets = [
                    {"id": bucket.key, "name": bucket.key, "count": bucket.doc_count}
                    for bucket in getattr(search_result.aggs, field).buckets
                ]
                exist_bizs = {int(bucket["id"]) for bucket in buckets}
                for bk_biz_id in self.authorized_bizs:
                    # 数量为0的业务，查不出来，但也需要填充
                    if len(buckets) >= size:
                        break
                    if int(bk_biz_id) in exist_bizs:
                        continue
                    buckets.append({"id": bk_biz_id, "name": bk_biz_id, "count": 0})
                bucket_count = len(set(self.authorized_bizs) | exist_bizs)
            else:
                # 桶的总数
                bucket_count = getattr(search_result.aggs, f"{field}{bucket_count_suffix}").value
                buckets = []
                for bucket in getattr(search_result.aggs, field).buckets:
                    if not bucket.key:
                        bucket_count -= 1
                    else:
                        buckets.append({"id": bucket.key, "name": bucket.key, "count": bucket.doc_count})

            if actual_field in translators:
                translators[actual_field].translate_from_dict(buckets, "id", "name")

            # 对于字符字段，需要将桶的 key 加上双引号
            if char_add_quotes:
                for bucket in buckets:
                    if actual_field in char_fields or actual_field.startswith("tags."):
                        bucket["id"] = '"{}"'.format(bucket["id"])

            result["fields"].append(
                {
                    "field": field,
                    "is_char": actual_field in char_fields or actual_field.startswith("tags."),
                    "bucket_count": bucket_count,
                    "buckets": buckets,
                }
            )
        return result


class BaseBizQueryHandler(BaseQueryHandler, ABC):
    def __init__(
        self,
        bk_biz_ids: List[int] = None,
        username: str = "",
        **kwargs,
    ):
        super(BaseBizQueryHandler, self).__init__(**kwargs)
        self.bk_biz_ids = bk_biz_ids
        self.authorized_bizs = self.bk_biz_ids
        self.unauthorized_bizs = []
        self.username = username
        self.request_username = username or get_request_username()
        if self.bk_biz_ids is not None:
            self.parse_biz_item()

    def parse_biz_item(self):
        try:
            req = get_request()
        except Exception:
            return
        self.authorized_bizs = Permission(request=req).filter_biz_ids_by_action(
            action=ActionEnum.VIEW_EVENT, bk_biz_ids=self.bk_biz_ids
        )
        if self.bk_biz_ids:
            self.unauthorized_bizs = list(set(self.bk_biz_ids) - set(self.authorized_bizs))


class QueryBuilder(ElasticsearchQueryBuilder):
    """
    Elasticsearch query_string 到 DSL 转换器
    """

    def _yield_nested_children(self, parent, children):
        for child in children:
            # 同级语句同时出现 AND 与 OR 时，忽略默认的报错
            yield child


class AlertDimensionFormatter:
    """
    将告警维度格式化为人类可读字符串
    """

    @staticmethod
    def get_dimension_display_value(value):
        if isinstance(value, list):
            display_value = ",".join(value)
        else:
            display_value = value

        return display_value

    @classmethod
    def get_dimensions_str(cls, dimensions):
        if not dimensions:
            return ""

        dimension_list = cls.get_dimensions(dimensions)

        dimension_str_list = []
        for dimension in dimension_list:
            if dimension["key"] in ["bk_cloud_id"] and str(dimension["value"]) == "0":
                continue
            dimension_str_list.append("{display_key}({display_value})".format(**dimension))

        # 隐藏默认云区域
        return " - ".join(dimension_str_list)

    @classmethod
    def get_dimensions(cls, dimensions):
        """
        获取维度展示字段
        :param dimensions: 维度列表
        :rtype: list(dict)
        """
        if not dimensions:
            return []

        dimension_list = []

        for dimension in dimensions:
            if isinstance(dimension, AttrDict):
                dimension = dimension.to_dict()
            dimension_list.append(
                {
                    "key": dimension["key"],
                    "value": dimension["value"],
                    "display_key": dimension.get("display_key", dimension["key"]),
                    "display_value": cls.get_dimension_display_value(dimension.get("display_value", "")),
                }
            )

        return dimension_list

    @classmethod
    def get_target_key(cls, target_type, dimensions):
        if not dimensions:
            return ""

        dimension_dict = {d["key"]: d for d in dimensions}

        display_key = ""

        if target_type == EventTargetType.HOST and "ip" in dimension_dict:
            dimension_field = "ip"
            display_key = _("主机")
        elif target_type == EventTargetType.SERVICE and "bk_service_instance_id" in dimension_dict:
            dimension_field = "bk_service_instance_id"
        elif target_type == EventTargetType.TOPO and "bk_topo_node" in dimension_dict:
            dimension_field = "bk_topo_node"
        elif "target" in dimension_dict:
            dimension_field = "target"
        else:
            return ""

        return "{} {}".format(
            display_key or dimension_dict[dimension_field].get("display_key", ""),
            dimension_dict[dimension_field].get("display_value", ""),
        )
