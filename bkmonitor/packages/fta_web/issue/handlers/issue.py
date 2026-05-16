"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import operator
import threading
import time

from functools import reduce
from typing import Any

from django.utils.translation import gettext_lazy as _

from elasticsearch_dsl import Q, Search
from elasticsearch_dsl.aggs import Bucket
from elasticsearch_dsl.response import Response

from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.issue import IssueDocument
from bkmonitor.utils.time_tools import hms_string
from constants.issue import ImpactScopeDimension, IssuePriority, IssueStatus
from fta_web.alert.handlers.base import BaseBizQueryHandler, BaseQueryTransformer, QueryField
from fta_web.alert.handlers.translator import BizTranslator, StrategyTranslator
from fta_web.issue.handlers.translator import StatusTranslator, PriorityTranslator

logger = logging.getLogger("fta_action.issue")


class IssueQueryTransformer(BaseQueryTransformer):
    """Issue ES 查询字段转换器"""

    VALUE_TRANSLATE_FIELDS = {
        "status": IssueStatus.CHOICES,
        "priority": IssuePriority.CHOICES,
    }

    KEYWORD_FIELD_MAPPING = {
        "name": "name.raw",
        "strategy_name": "strategy_name.raw",
        # fingerprint 本身就是 keyword，不需要 .raw；放进 mapping 是声明它属于"按精确值检索"语义
        "fingerprint": "fingerprint",
    }

    doc_cls = IssueDocument

    query_fields = [
        QueryField("id", "Issue ID", is_char=True),
        QueryField("name", "Issue 名称", agg_field="name.raw", is_char=True),
        QueryField("status", "状态"),
        QueryField("priority", "优先级"),
        QueryField("assignee", "负责人"),
        QueryField("strategy_id", "策略ID"),
        QueryField("strategy_name", "策略名称", agg_field="strategy_name.raw", is_char=True),
        QueryField("bk_biz_id", "业务ID"),
        QueryField("labels", "标签", is_char=True),
        QueryField("is_regression", "是否回归"),
        QueryField("alert_count", "告警数量"),
        QueryField("first_alert_time", "首次告警时间"),
        QueryField("last_alert_time", "最近告警时间"),
        QueryField("create_time", "创建时间"),
        QueryField("update_time", "更新时间"),
        QueryField("resolved_time", "解决时间"),
        # fingerprint：按"同一具体问题"精确检索/聚合（同维度组合的所有 Issue 含历史）
        QueryField("fingerprint", "Issue 指纹"),
        # dimension_values：Flattened 动态 key，前端通过 conditions 传 dimension_values.{key}
        # 路径直接 term 过滤；TopN 聚合也走子字段路径（详见 IssueTopNResource 适配）
        QueryField("dimension_values", "维度组合"),
    ] + [
        QueryField(
            field=f"impact_scope.{impact_field}",
            display=str(name),
            es_field=ImpactScopeDimension.get_full_dimension(impact_field),
            is_char=True,
        )
        for impact_field, name in ImpactScopeDimension.CHOICES
    ]


class IssueQueryHandler(BaseBizQueryHandler):
    """Issue 列表查询处理器"""

    query_transformer = IssueQueryTransformer

    MY_ISSUE_STATUS_NAME = "MY_ASSIGNEE"
    NO_ASSIGNEE_STATUS_NAME = "NO_ASSIGNEE"

    def __init__(
        self,
        bk_biz_ids: list[int] = None,
        username: str = "",
        status: list[str] = None,
        start_time: int = None,
        end_time: int = None,
        ordering: list[str] = None,
        query_string: str = "",
        conditions: list = None,
        page: int = 1,
        page_size: int = 10,
        trend_start_time: int = None,
        trend_end_time: int = None,
        is_time_partitioned: bool = False,
        is_finally_partition: bool = False,
        need_bucket_count: bool = True,
        fingerprint: str = "",
        **kwargs,
    ):
        super().__init__(
            bk_biz_ids=bk_biz_ids,
            username=username,
            start_time=start_time,
            end_time=end_time,
            ordering=ordering,
            query_string=query_string,
            conditions=conditions,
            page=page,
            page_size=page_size,
            **kwargs,
        )
        self.status = [status] if isinstance(status, str) else status
        # fingerprint 精确过滤：定位"同一具体问题"的全部 Issue（含历史）
        self.fingerprint = fingerprint or ""

        # 默认排序：最早发生时间降序 > 优先级 > 状态
        if not self.ordering:
            self.ordering = ["-first_alert_time", "priority", "status"]

        self.trend_start_time = trend_start_time if trend_start_time is not None else self.start_time
        self.trend_end_time = trend_end_time if trend_end_time is not None else self.end_time

        # 时间分片查询相关标记
        self.is_time_partitioned = is_time_partitioned
        self.is_finally_partition = is_finally_partition
        self.need_bucket_count = need_bucket_count

    def get_search_object(
        self,
        start_time: int = None,
        end_time: int = None,
        is_time_partitioned: bool = False,
        is_finally_partition: bool = False,
        **kwargs,
    ) -> Search:
        start_time = start_time or self.start_time
        end_time = end_time or self.end_time
        is_time_partitioned = is_time_partitioned or self.is_time_partitioned
        is_finally_partition = is_finally_partition or self.is_finally_partition

        # Issue 跨天存在，使用全量索引查询
        search_object = IssueDocument.search(all_indices=True)

        # 时间范围过滤：
        # - end_time 约束 create_time（该时间前已创建）
        # - start_time 约束 resolved_time（在该时间之后才解决）
        # 分片模式下，按 resolved_time 唯一归属分片，避免同一 Issue 被多分片重复计数：
        #   非最后分片：resolved_time ∈ [start, end)，仅覆盖"已解决且解决在本分片内"的 Issue
        #   最后分片  ：resolved_time >= start OR 未解决，承接"未解决的 Issue"（~exists 只在此处出现一次）
        if is_time_partitioned and not is_finally_partition:
            if end_time:
                search_object = search_object.filter("range", create_time={"lte": end_time})
            if start_time and end_time:
                search_object = search_object.filter("range", resolved_time={"gte": start_time, "lt": end_time})
        else:
            if end_time:
                search_object = search_object.filter("range", create_time={"lte": end_time})
            if start_time:
                search_object = search_object.filter(
                    Q("range", resolved_time={"gte": start_time}) | ~Q("exists", field="resolved_time")
                )

        # 业务权限过滤
        search_object = self.add_biz_condition(search_object)

        # 状态过滤（含虚拟状态）
        if self.status:
            queries = []
            for s in self.status:
                s_lower = s.lower()
                if s_lower == self.MY_ISSUE_STATUS_NAME.lower():
                    queries.append(Q("term", assignee=self.request_username))
                elif s_lower == self.NO_ASSIGNEE_STATUS_NAME.lower():
                    queries.append(~Q("exists", field="assignee"))

            if queries:
                combined = queries[0]
                for q in queries[1:]:
                    combined = combined | q
                search_object = search_object.filter(combined)

        # 指纹精确过滤
        if self.fingerprint:
            search_object = search_object.filter("term", fingerprint=self.fingerprint)

        return search_object

    def parse_condition_item(self, condition: dict) -> Q:
        """处理 impact_scope 相关的查询条件

        支持两种过滤方式：
        1. 维度级过滤（impact_dimensions）→ exists 查询
        2. 实例 ID 级过滤（impact_scope.{维度}.{ID字段}）→ terms 查询
        """
        key = condition["key"]
        raw_query_fields = self.query_transformer.KEYWORD_FIELD_MAPPING

        if key == "impact_dimensions":
            # 维度级过滤：判断是否包含某个维度
            # flattened 类型下，使用 instance_list 中的具体 ID 字段路径
            should_clauses = []
            for impact_field in condition["value"]:
                impact_field = impact_field.removeprefix("impact_scope.")
                es_field = ImpactScopeDimension.get_full_dimension(impact_field)
                # impact_field: "impact_scope.host.instance_list.bk_host_id"
                should_clauses.append(Q("exists", field=es_field))
            return Q("bool", should=should_clauses, minimum_should_match=1)

        elif key in raw_query_fields:
            condition["key"] = raw_query_fields[key]

        return super().parse_condition_item(condition)

    def top_n(self, fields: list, size=10, translators: dict = None, char_add_quotes=True):
        """Issue TopN 查询

        impact_dimensions: filters 聚合，需特殊解析
        impact_scope.{维度}.{ID字段}: terms 聚合，需特殊解析
        其余字段（含 id）走基类标准流程
        """
        translators = translators or {
            "status": StatusTranslator(),
            "priority": PriorityTranslator(),
            "bk_biz_id": BizTranslator(),
            "strategy_id": StrategyTranslator(),
        }

        search_object = self.get_search_object()
        search_object = self.add_conditions(search_object)
        search_object = self.add_query_string(search_object)
        search_object = search_object.params(track_total_hits=True).extra(size=0)

        size = min(size, 10000)
        bucket_count_suffix = self.bucket_count_suffix

        for field in fields:
            self.add_agg_bucket(search_object.aggs, field, size=size)
            if bucket_count_suffix:
                self.add_cardinality_bucket(search_object.aggs, field, bucket_count_suffix)

        search_result = search_object.execute()

        result = {"doc_count": search_result.hits.total.value, "fields": []}
        char_fields = [f.field for f in self.query_transformer.query_fields if f.is_char]

        for field in fields:
            actual_field = field.lstrip("+-")
            bucket_count = 0
            if not search_result.aggs:
                result["fields"].append(
                    {
                        "field": field,
                        "is_char": actual_field in char_fields,
                        "bucket_count": bucket_count,
                        "buckets": [],
                    }
                )
                continue

            # impact_dimensions: filters 聚合结果解析
            if actual_field == "impact_dimensions":
                buckets = self._parse_impact_dimensions_buckets(search_result)

                bucket_count = len(buckets)
                # 按 count 降序排列，数量多的优先
                buckets = sorted(buckets, key=lambda x: x["count"], reverse=True)
                # filters 聚合不支持 size 参数，手动截断
                if size is not None and size > 0:
                    buckets = buckets[:size]

                result["fields"].append(
                    {
                        "field": field,
                        "is_char": False,
                        "bucket_count": bucket_count,
                        "buckets": buckets,
                    }
                )
                continue

            # impact_scope.{dim}.{id_field}: terms 聚合结果解析
            if actual_field.startswith("impact_scope."):
                buckets = self._parse_impact_scope_buckets(search_result, actual_field, translators, char_add_quotes)
                result["fields"].append(
                    {"field": field, "is_char": True, "bucket_count": len(buckets), "buckets": buckets}
                )
                continue

            # dimension_values.{key}: Flattened 子字段 terms 聚合结果解析
            # bucket.key 即 dim 的实际值（如 host_id "9185731"），无需翻译
            if actual_field.startswith("dimension_values."):
                agg_name = self._sanitize_dim_agg_name(actual_field)
                bucket_count = None
                if bucket_count_suffix:
                    cardinality_agg = getattr(search_result.aggs, f"{agg_name}{bucket_count_suffix}", None)
                    bucket_count = cardinality_agg.value if cardinality_agg else 0
                buckets = []
                terms_agg = getattr(search_result.aggs, agg_name, None)
                if terms_agg:
                    for bucket in terms_agg.buckets:
                        if bucket.key is not None:
                            buckets.append({"id": bucket.key, "name": bucket.key, "count": bucket.doc_count})
                result["fields"].append(
                    {"field": field, "is_char": False, "bucket_count": bucket_count, "buckets": buckets}
                )
                continue

            # bk_biz_id：需要补充授权业务中数量为0的桶
            elif actual_field == "bk_biz_id" and hasattr(self, "authorized_bizs"):
                buckets = [
                    {"id": bucket.key, "name": bucket.key, "count": bucket.doc_count}
                    for bucket in getattr(search_result.aggs, field).buckets
                ]
                exist_bizs = {int(bucket["id"]) for bucket in buckets}
                for bk_biz_id in self.authorized_bizs:
                    if len(buckets) >= size:
                        break
                    if int(bk_biz_id) in exist_bizs:
                        continue
                    buckets.append({"id": bk_biz_id, "name": bk_biz_id, "count": 0})

                if bucket_count_suffix:
                    bucket_count = len(set(self.authorized_bizs) | exist_bizs)

            # 普通字段（含 id）：标准 terms 聚合结果解析
            else:
                bucket_count = None
                if bucket_count_suffix:
                    bucket_count = getattr(search_result.aggs, f"{field}{bucket_count_suffix}").value

                buckets = []
                for bucket in getattr(search_result.aggs, field).buckets:
                    if bucket_count_suffix and not bucket.key:
                        bucket_count -= 1
                    else:
                        buckets.append({"id": bucket.key, "name": bucket.key, "count": bucket.doc_count})

            if actual_field in translators:
                translators[actual_field].translate_from_dict(buckets, "id", "name")

            if char_add_quotes:
                for bucket in buckets:
                    if actual_field in char_fields:
                        bucket["id"] = '"{}"'.format(bucket["id"])

            result["fields"].append(
                {
                    "field": field,
                    "is_char": actual_field in char_fields,
                    "bucket_count": bucket_count,
                    "buckets": buckets,
                }
            )

        return result

    def _parse_impact_dimensions_buckets(self, search_result):
        """解析 impact_dimensions filters 聚合结果，只返回实际有数据的维度

        参数:
            size: 返回的最大维度数量，None 表示不限制
        """
        buckets = []
        agg_result = getattr(search_result.aggs, "impact_dimensions", None)
        if agg_result:
            for dim, _name in ImpactScopeDimension.CHOICES:
                bucket = getattr(agg_result.buckets, dim, None) if hasattr(agg_result.buckets, dim) else None
                count = bucket.doc_count if bucket else 0
                if count == 0:
                    continue
                display_name = str(ImpactScopeDimension.get_display_name(dim))
                buckets.append({"id": f"impact_scope.{dim}", "name": display_name, "count": count})

        return buckets

    def _parse_impact_scope_buckets(self, search_result, actual_field, translators, char_add_quotes):
        """解析 impact_scope.{维度} terms 聚合结果"""
        buckets = []
        if search_result.aggs:
            for bucket in getattr(search_result.aggs, actual_field).buckets:
                if bucket.key is not None:
                    display_name = None
                    # 从 top_hits 子聚合中提取 display_name
                    first_doc = getattr(getattr(bucket, "first_doc", None), "hits", None)
                    if first_doc and first_doc.hits:
                        source = first_doc.hits[0].to_dict().get("_source", {})
                        if source:
                            # 按 dimension 解析出 display_name 路径（AttrDict 用属性访问）
                            dimension = actual_field.removeprefix("impact_scope.")
                            id_field = ImpactScopeDimension.get_id_field(dimension)
                            instance_list = source.get("impact_scope", {}).get(dimension, {}).get("instance_list", [])
                            for instance in instance_list:
                                if str(instance.get(id_field, None)) == str(bucket.key):
                                    display_name = instance.get("display_name", None)
                                    break

                    name = display_name if display_name is not None else bucket.key
                    buckets.append({"id": bucket.key, "name": name, "count": bucket.doc_count})

        if actual_field in translators:
            translators[actual_field].translate_from_dict(buckets, "id", "name")

        if char_add_quotes:
            for bucket in buckets:
                bucket["id"] = '"{}"'.format(bucket["id"])

        return buckets

    def add_cardinality_bucket(self, search_object: Bucket, field: str, bucket_count_suffix: str):
        """添加基数聚合桶，支持 impact_dimensions / impact_scope / dimension_values.{key} 特殊字段"""
        actual_field = field.lstrip("+-")

        if actual_field == "impact_dimensions":
            # 直接取 buckets 的数量作为 bucket_count
            return search_object

        if actual_field.startswith("dimension_values."):
            # ES agg name 不能含 "."，sanitize 为 "__"；ES field 仍用原路径（Flattened 子字段）
            agg_name = self._sanitize_dim_agg_name(actual_field) + bucket_count_suffix
            return search_object.bucket(agg_name, "cardinality", field=actual_field)

        return super().add_cardinality_bucket(search_object, field, bucket_count_suffix)

    @staticmethod
    def _sanitize_dim_agg_name(field: str) -> str:
        """把 dimension_values.{key} 转成合法的 ES agg name（不能含 "."）。

        使用 "__" 分隔避免与原 . 路径混淆；与 impact_scope 类的 agg name 风格一致。
        """
        return field.replace(".", "__")

    def add_agg_bucket(self, search_object, field: str, size: int = 10):
        """
        按字段添加聚合桶，支持 impact_dimensions 和 impact_scope 特殊字段。

        参数:
            search_object: elasticsearch_dsl 聚合桶对象，用于挂载子聚合
            field: 聚合字段名，可带 +/- 排序前缀（如 "-impact_scope.host"）
            size: terms 聚合返回的最大桶数量，默认 10

        返回值:
            添加聚合桶后的 search_object
        """
        # 去除排序前缀，得到实际字段名
        actual_field = field.lstrip("+-")

        if actual_field == "impact_dimensions":
            # flattened 类型不支持对子路径使用 exists 查询，
            # 改为查询 instance_list 中的具体 ID 字段是否存在，
            # 每个维度构造一个 exists 过滤条件，最终使用 filters 聚合分桶
            filters = {}
            for dim, _name in ImpactScopeDimension.CHOICES:
                # 获取维度在 ES 中的完整叶子节点路径，如 impact_scope.host.instance_list.bk_host_id
                es_field = ImpactScopeDimension.get_full_dimension(dim)
                filters[dim] = Q("exists", field=es_field)
            new_search_object = search_object.bucket("impact_dimensions", "filters", filters=filters)
            return new_search_object

        if actual_field.startswith("impact_scope."):
            # 将前端字段名转换为 ES flattened 类型下的叶子节点路径，用于 terms 聚合
            es_field = self.query_transformer.transform_field_to_es_field(actual_field, for_agg=True)
            # display_name 字段路径，用于 top_hits 子聚合获取实例展示名称
            display_name_field = f"{actual_field}.instance_list.display_name"
            # terms 聚合按实例 ID 分桶，top_hits 子聚合取第一条文档以获取 display_name
            new_search_object = search_object.bucket(actual_field, "terms", field=es_field, size=size).metric(
                "first_doc", "top_hits", size=1, _source=[display_name_field, es_field]
            )
            return new_search_object

        if actual_field.startswith("dimension_values."):
            # Flattened 子字段：ES field 用原路径（如 dimension_values.bk_host_id），
            # 但 agg name 必须 sanitize（去 "."）才能在结果端用 getattr 取桶
            agg_name = self._sanitize_dim_agg_name(actual_field)
            return search_object.bucket(agg_name, "terms", field=actual_field, size=size)

        # 其他字段走基类标准流程
        return super().add_agg_bucket(search_object, field, size)

    def add_biz_condition(self, search_object):
        """业务权限过滤"""
        queries = []
        if self.authorized_bizs is not None and self.bk_biz_ids:
            # 有权限的业务直接过滤
            authorized_biz_ids = [str(b) for b in self.authorized_bizs]
            authorized_query = self.build_es_terms_query("bk_biz_id", authorized_biz_ids)
            if authorized_query is not None:
                queries.append(authorized_query)

        user_condition = Q("term", assignee=self.request_username)

        if not self.bk_biz_ids:
            # 不带业务信息时，只查与当前用户相关的 Issue
            queries.append(user_condition)

        if self.unauthorized_bizs and self.request_username:
            # 无权限的业务，需要同时是负责人才能看到
            unauthorized_query = self.build_es_terms_query("bk_biz_id", [str(b) for b in self.unauthorized_bizs])
            if unauthorized_query is not None:
                queries.append(unauthorized_query & user_condition)

        if queries:
            return search_object.filter(reduce(operator.or_, queries))
        return search_object

    def search_raw(self, show_aggs: bool = False, show_dsl: bool = False) -> tuple[Response, dict | None]:
        search_object = self.get_search_object()
        search_object = self.add_conditions(search_object)
        search_object = self.add_query_string(search_object)
        search_object = self.add_ordering(search_object)
        search_object = self.add_pagination(search_object)

        if show_aggs:
            search_object = self.add_aggs(search_object)

        search_result = search_object.params(track_total_hits=True).execute()

        if show_dsl:
            return search_result, search_object.to_dict()

        return search_result, None

    def search(self, show_aggs: bool = False, show_dsl: bool = False) -> dict:
        exc = None
        try:
            search_result, dsl = self.search_raw(show_aggs=show_aggs, show_dsl=show_dsl)
        except Exception as e:
            logger.exception("search issues error: %s", e)
            search_result = self.make_empty_response()
            dsl = None
            exc = e

        issues = self.handle_hit_list(search_result)

        # 字段翻译
        StrategyTranslator().translate_from_dict(issues, "strategy_id", "strategy_name")
        BizTranslator().translate_from_dict(issues, "bk_biz_id", "bk_biz_name")

        # 批量查询关联告警趋势
        self.add_alert_trend(issues)

        result = {"issues": issues, "total": search_result.hits.total.value}

        if show_aggs:
            result["aggs"] = self.handle_aggs(search_result)

        if dsl:
            result["dsl"] = dsl

        if exc:
            exc.data = result
            raise exc

        return result

    def add_aggs(self, search_object: Search) -> Search:
        """高级筛选聚合"""
        search_object.aggs.bucket("priority", "terms", field="priority")
        search_object.aggs.bucket("status", "terms", field="status")
        search_object.aggs.bucket(
            "assignee",
            "filters",
            filters={
                "my_assignee": Q("term", assignee=self.request_username),
                "no_assignee": (~Q("exists", field="assignee")),
            },
        )
        search_object.aggs.bucket("is_regression", "terms", field="is_regression")
        return search_object

    def handle_aggs(self, search_result: Response) -> list[dict]:
        """解析聚合结果为前端所需格式"""
        if not search_result.aggs:
            return []

        aggs = []

        # 优先级聚合：确保所有优先级选项都展示，count 为 0 的也展示
        priority_bucket_map = {bucket.key: bucket.doc_count for bucket in search_result.aggs.priority.buckets}
        priority_buckets = []
        for priority_key, priority_name in IssuePriority.CHOICES:
            priority_buckets.append(
                {
                    "id": priority_key,
                    "name": str(priority_name),
                    "count": priority_bucket_map.get(priority_key, 0),
                }
            )
        aggs.append(
            {
                "id": "priority",
                "name": "优先级",
                "count": search_result.hits.total.value,
                "children": priority_buckets,
            }
        )

        # 状态聚合：确保所有状态选项都展示，count 为 0 的也展示
        status_bucket_map = {bucket.key: bucket.doc_count for bucket in search_result.aggs.status.buckets}
        status_buckets = []
        for status_key, status_name in IssueStatus.CHOICES:
            status_buckets.append(
                {
                    "id": status_key,
                    "name": str(status_name),
                    "count": status_bucket_map.get(status_key, 0),
                }
            )
        aggs.append(
            {
                "id": "status",
                "name": "状态",
                "count": search_result.hits.total.value,
                "children": status_buckets,
            }
        )

        # 负责人聚合
        assignee_agg = search_result.aggs.assignee
        assignee_children = [
            {"id": "my_assignee", "name": "我负责的", "count": assignee_agg.buckets.my_assignee.doc_count},
            {"id": "no_assignee", "name": "未分配", "count": assignee_agg.buckets.no_assignee.doc_count},
        ]
        aggs.append(
            {
                "id": "assignee",
                "name": "负责人",
                "count": search_result.hits.total.value,
                "children": assignee_children,
            }
        )

        # 类型聚合（是否回归）：确保"新问题"和"回归问题"都展示
        regression_bucket_map = {}
        for bucket in search_result.aggs.is_regression.buckets:
            # ES boolean 字段聚合，key 为 True/False（或 "true"/"false"），统一归一化
            key = bucket.key
            if isinstance(key, str):
                key = key.lower() in ("true", "1")
            regression_bucket_map[bool(key)] = bucket.doc_count

        regression_buckets = [
            {
                "id": "false",
                "name": "新问题",
                "count": regression_bucket_map.get(False, 0),
            },
            {
                "id": "true",
                "name": "回归问题",
                "count": regression_bucket_map.get(True, 0),
            },
        ]
        aggs.append(
            {
                "id": "is_regression",
                "name": "类型",
                "count": search_result.hits.total.value,
                "children": regression_buckets,
            }
        )

        return aggs

    @classmethod
    def handle_hit(cls, hit: Any) -> dict:
        return cls.clean_document(hit)

    @classmethod
    def clean_document(cls, doc: IssueDocument) -> dict:
        """数据清洗：从 ES Hit 中提取并格式化字段"""
        if isinstance(doc, dict):
            data = doc
        else:
            data = doc.to_dict()

        cleaned = {}

        # 固定字段
        for field in cls.query_transformer.query_fields:
            cleaned[field.field] = field.get_value_by_es_field(data)

        # 计算字段
        now = int(time.time())
        create_time = cleaned.get("create_time")
        resolved_time = cleaned.get("resolved_time")

        if create_time:
            if resolved_time:
                duration_seconds = int(resolved_time) - int(create_time)
            else:
                duration_seconds = now - int(create_time)
            cleaned["duration"] = hms_string(max(duration_seconds, 0))
        else:
            cleaned["duration"] = "--"

        status_display = dict(IssueStatus.CHOICES)
        priority_display = dict(IssuePriority.CHOICES)
        cleaned["status_display"] = str(status_display.get(cleaned.get("status"), cleaned.get("status", "")))
        cleaned["priority_display"] = str(priority_display.get(cleaned.get("priority"), cleaned.get("priority", "")))
        cleaned["is_resolved"] = resolved_time is not None

        # impact_scope 添加 display_name
        impact_scope = data.get("impact_scope") or {}
        cleaned["impact_scope"] = cls.enrich_impact_scope(impact_scope)

        # aggregate_config 添加display_name
        cleaned["aggregate_config"] = cls.enrich_aggregate_dimensions(data.get("aggregate_config") or {})

        return cleaned

    @classmethod
    def enrich_aggregate_dimensions(cls, aggregate_config: dict) -> dict:
        """
        为 aggregate_config 中的 aggregate_dimensions 补充 display_name 和正确的字段前缀

        参数:
            aggregate_config: 聚合配置字典，需包含 "aggregate_dimensions" 列表，
                列表中每个元素为字符串形式的维度字段名（如 "bk_biz_id" 或 "tags.xxx"）
        """
        if not aggregate_config or "aggregate_dimensions" not in aggregate_config:
            return aggregate_config

        # 硬编码的维度字段到中文名映射（ES Document 顶层字段）
        dimension_name_mapping = {
            "bk_agent_id": _("Agent ID"),
            "bk_biz_id": _("业务ID"),
            "bk_cloud_id": _("采集器云区域ID"),
            "bk_host_id": _("采集主机ID"),
            "bk_target_cloud_id": _("云区域ID"),
            "bk_target_host_id": _("目标主机ID"),
            "bk_target_ip": _("目标IP"),
            "device_name": _("设备名"),
            "device_type": _("设备类型"),
            "hostname": _("主机名"),
            "ip": _("采集器IP"),
            "mount_point": _("挂载点"),
        }

        # 独立维护 AlertQueryTransformer 动态字段的映射，用于后续判断是否为已知顶层字段
        transformer_field_mapping = {}

        # 延迟导入避免循环引用
        from fta_web.alert.handlers.alert import AlertQueryTransformer

        for field in AlertQueryTransformer.query_fields:
            transformer_field_mapping[field.field] = field.display

        # 合并映射表：用于统一查找维度的中文名
        dimension_name_mapping.update(transformer_field_mapping)

        new_aggregate_dimensions = []

        for dim in aggregate_config["aggregate_dimensions"]:
            # 保留原始字段名，后续可能需要补 tags. 前缀
            field = dim
            # 去除 tags. 前缀，用于在映射表中查找中文名
            if dim.startswith("tags."):
                dim = dim.removeprefix("tags.")

            # 前缀修正逻辑：
            # - 原始字段不带 tags. 前缀，且不属于 AlertQueryTransformer 的已知顶层字段
            # - 说明该维度是标签字段，需要补 tags. 前缀以匹配 ES 中的实际存储路径
            if not field.startswith("tags.") and dim not in transformer_field_mapping:
                field = f"tags.{field}"

            # 优先从映射表获取中文名，否则通过 ImpactScopeDimension 兜底获取
            name = dimension_name_mapping.get(dim) or ImpactScopeDimension.get_display_name(dim)
            new_aggregate_dimensions.append({"field": field, "display_name": name})

        aggregate_config["aggregate_dimensions"] = new_aggregate_dimensions

        return aggregate_config

    @classmethod
    def enrich_impact_scope(cls, impact_scope: dict) -> dict:
        """丰富 impact_scope 数据：为每个维度添加 display_name，为每个实例渲染 alert_query_fields"""
        for dimension_key, dimension_data in impact_scope.items():
            if isinstance(dimension_data, dict):
                dimension_data["display_name"] = ImpactScopeDimension.get_display_name(dimension_key)
                # 为每个实例渲染 alert_query_fields（后端预渲染，前端直接使用）
                mapping_key = f"impact_scope.{dimension_key}"
                mapping_entries = ImpactScopeDimension.ALERT_QUERY_MAPPING.get(mapping_key)
                if mapping_entries and "instance_list" in dimension_data:
                    for instance in dimension_data["instance_list"]:
                        instance["alert_query_fields"] = cls._render_alert_query_fields(mapping_entries, instance)
        return impact_scope

    @classmethod
    def _render_alert_query_fields(cls, mapping_entries: list[dict], instance: dict) -> list[dict]:
        """根据 ALERT_QUERY_MAPPING 模板和实例数据，渲染出实际的查询字段列表

        返回值示例:
            [{"keys": ["event.bk_host_id", "tags.bk_host_id"], "value": "9185731"}]
        """
        result = []
        for entry in mapping_entries:
            try:
                value = entry["value_tpl"].format(**instance)
            except (KeyError, IndexError):
                continue
            result.append({"keys": entry["keys"], "value": value, "condition": entry.get("condition", "or")})
        return result

    def add_alert_trend(self, issues: list[dict]) -> None:
        """
        批量查询 AlertDocument，为每个 Issue 填充 trend、alert_count 和 anomaly_message。

        参数:
            issues: search() 已清洗完成的 Issue 列表（会被原地修改）
        """
        issue_ids = [issue["id"] for issue in issues if issue.get("id")]
        if not issue_ids:
            return

        # 从本页 Issue 中提取告警时间边界（空值检查必须在 min/max 之前）
        first_alert_times = [issue["first_alert_time"] for issue in issues if issue.get("first_alert_time")]
        last_alert_times = [issue["last_alert_time"] for issue in issues if issue.get("last_alert_time")]

        if not first_alert_times or not last_alert_times:
            for issue in issues:
                issue["trend"] = []
                issue["alert_count"] = 0
                issue["anomaly_message"] = "--"
            return

        # 仅用于限定 _fill_anomaly_message 查询 AlertDocument 的索引范围
        start_time = int(min(first_alert_times))
        end_time = int(max(last_alert_times))

        # 趋势图时间范围：优先使用前端传入的固定范围，兜底退回本页 Issue 的实际告警时间边界
        trend_start = self.trend_start_time if self.trend_start_time is not None else start_time
        trend_end = self.trend_end_time if self.trend_end_time is not None else end_time
        interval = self.calculate_agg_interval(trend_start, trend_end)

        # 生成默认零值时间序列
        aligned_start = trend_start // interval * interval
        aligned_end = trend_end // interval * interval + interval
        default_time_series = [[ts * 1000, 0] for ts in range(aligned_start, aligned_end, interval)]

        # 启动后台线程查询 anomaly_message 和 alert_count
        fill_result = {"alert_count_map": {}, "anomaly_message_map": {}}
        fill_thread = threading.Thread(
            target=self._fill_anomaly_message,
            args=(issue_ids, start_time, end_time, fill_result),
        )
        fill_thread.start()

        # 查询告警趋势：≤7天直接单次请求，>7天走时间分片并行查询
        SLICED_THRESHOLD = 7 * 24 * 60 * 60  # 7天
        try:
            from fta_web.issue.resources import IssueAlertDateHistogramResultResource

            if (trend_end - trend_start) <= SLICED_THRESHOLD:
                result = IssueAlertDateHistogramResultResource().request(
                    start_time=trend_start,
                    end_time=trend_end,
                    interval=interval,
                    conditions=[{"key": "issue_id", "value": issue_ids, "method": "eq"}],
                    group_by=["issue_id"],
                )
            else:
                result = IssueAlertDateHistogramResultResource.sliced_date_histogram(
                    start_time=trend_start,
                    end_time=trend_end,
                    interval=interval,
                    handler_kwargs={
                        "conditions": [{"key": "issue_id", "value": issue_ids, "method": "eq"}],
                    },
                    group_by=["issue_id"],
                )
        except Exception as e:
            logger.exception(f"add_alert_trend: date_histogram failed, exception:{e}")
            fill_thread.join(timeout=30)
            for issue in issues:
                issue["trend"] = list(default_time_series)
                issue["alert_count"] = 0
                issue["anomaly_message"] = "--"
            return

        # 从合并结果中提取每个 issue 的时间序列
        merged = {}  # {issue_id: {ts_ms: count}}
        for dimension_tuple, status_series in result.items():
            # 跳过空结果标记（perform_request 在无数据时返回 default_time_series）
            if dimension_tuple == "default_time_series":
                continue
            issue_id = None
            for key, value in dimension_tuple:
                if key == "issue_id":
                    issue_id = value
                    break
            if issue_id is None:
                continue

            if issue_id not in merged:
                merged[issue_id] = {}
            # group_by=["issue_id"] 不含 status，只返回 ABNORMAL 序列
            abnormal_series = status_series.get("ABNORMAL", {})
            merged[issue_id].update(abnormal_series)

        # 等待后台线程完成
        fill_thread.join(timeout=30)

        # 回填到 Issue 列表
        for issue in issues:
            issue_id = issue["id"]
            if issue_id in merged:
                issue["trend"] = sorted([[ts, value] for ts, value in merged[issue_id].items()])
            else:
                issue["trend"] = list(default_time_series)

            issue["anomaly_message"] = fill_result["anomaly_message_map"].get(issue_id, "--")
            issue["alert_count"] = fill_result["alert_count_map"].get(issue_id, 0)

    def _fill_anomaly_message(self, issue_ids: list[str], start_time: int, end_time: int, fill_result: dict) -> None:
        """后台线程：查询每个 Issue 最新告警的 description 作为 anomaly_message，同时统计 alert_count"""
        try:
            search_object = AlertDocument.search(start_time=start_time, end_time=end_time)
            search_object = search_object.filter("terms", issue_id=issue_ids)

            issue_agg = search_object.aggs.bucket("issues", "terms", field="issue_id", size=len(issue_ids))
            issue_agg.metric(
                "latest_alert",
                "top_hits",
                size=1,
                sort=[{"begin_time": {"order": "desc"}}],
                _source=["event.description"],
            )
            # 统计每个 Issue 的告警数量
            issue_agg.metric("alert_count", "value_count", field="id")

            result = search_object[:0].execute()

            msg_map = {}
            count_map = {}
            for issue_bucket in result.aggs.issues.buckets:
                issue_id = issue_bucket.key

                # 解析 anomaly_message
                anomaly_message = "--"
                if hasattr(issue_bucket, "latest_alert") and issue_bucket.latest_alert:
                    hits = issue_bucket.latest_alert.hits
                    if hits and hits.hits and len(hits.hits) > 0:
                        hit = hits.hits[0]
                        # top_hits 返回的 hit 是 AttrDict，_source 在 hit["_source"] 中
                        source = hit.to_dict().get("_source", {})
                        event_data = source.get("event", {})
                        description = event_data.get("description", "") if isinstance(event_data, dict) else ""
                        if description:
                            anomaly_message = description
                msg_map[issue_id] = anomaly_message

                # 解析 alert_count
                if hasattr(issue_bucket, "alert_count"):
                    count_map[issue_id] = int(issue_bucket.alert_count.value or 0)

            fill_result["anomaly_message_map"] = msg_map
            fill_result["alert_count_map"] = count_map
        except Exception as e:
            logger.exception(f"_fill_anomaly_message failed, exception:{e}")
