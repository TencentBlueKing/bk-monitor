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
import time

from functools import reduce
from typing import Any

from elasticsearch_dsl import Q, Search
from elasticsearch_dsl.response import Response

from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.issue import IssueDocument
from bkmonitor.utils.time_tools import hms_string
from constants.issue import ImpactScopeDimension, IssuePriority, IssueStatus
from core.drf_resource import resource
from fta_web.alert.handlers.base import BaseBizQueryHandler, BaseQueryTransformer, QueryField
from fta_web.alert.handlers.translator import BizTranslator, StrategyTranslator
from fta_web.alert.utils import slice_time_interval

logger = logging.getLogger("fta_action.issue")


class IssueQueryTransformer(BaseQueryTransformer):
    """Issue ES 查询字段转换器"""

    VALUE_TRANSLATE_FIELDS = {
        "status": IssueStatus.CHOICES,
        "priority": IssuePriority.CHOICES,
    }
    doc_cls = IssueDocument

    query_fields = [
        QueryField("id", "Issue ID"),
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
    ]


def add_dimension_display_name(impact_scope: dict) -> dict:
    """为 impact_scope 中每个维度添加 display_name 字段"""
    for dimension_key, dimension_data in impact_scope.items():
        if isinstance(dimension_data, dict):
            dimension_data["display_name"] = ImpactScopeDimension.get_display_name(dimension_key)
    return impact_scope


class IssueQueryHandler(BaseBizQueryHandler):
    """Issue 列表查询处理器"""

    query_transformer = IssueQueryTransformer

    MY_ISSUE_STATUS_NAME = "MY_ISSUE"
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

        # 默认排序：活跃状态优先，同状态按更新时间倒序
        if not self.ordering:
            self.ordering = ["status", "-update_time"]

    def get_search_object(self, start_time: int = None, end_time: int = None, **kwargs) -> Search:
        start_time = start_time or self.start_time
        end_time = end_time or self.end_time

        # Issue 跨天存在，使用全量索引查询
        search_object = IssueDocument.search(all_indices=True)

        # 时间范围过滤：end_time → create_time, start_time → resolved_time
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
                if s == self.MY_ISSUE_STATUS_NAME:
                    queries.append(Q("term", assignee=self.request_username))
                elif s == self.NO_ASSIGNEE_STATUS_NAME:
                    queries.append(~Q("exists", field="assignee"))

            if queries:
                combined = queries[0]
                for q in queries[1:]:
                    combined = combined | q
                search_object = search_object.filter(combined)

        return search_object

    def add_biz_condition(self, search_object):
        """业务权限过滤"""
        queries = []
        if self.authorized_bizs is not None and self.bk_biz_ids:
            # 有权限的业务直接过滤
            queries.append(Q("terms", bk_biz_id=[str(b) for b in self.authorized_bizs]))

        user_condition = Q("term", assignee=self.request_username)

        if not self.bk_biz_ids:
            # 不带业务信息时，只查与当前用户相关的 Issue
            queries.append(user_condition)

        if self.unauthorized_bizs and self.request_username:
            # 无权限的业务，需要同时是负责人才能看到
            queries.append(Q("terms", bk_biz_id=[str(b) for b in self.unauthorized_bizs]) & user_condition)

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
        status_display = dict(IssueStatus.CHOICES)
        priority_display = dict(IssuePriority.CHOICES)

        # 优先级聚合
        priority_buckets = []
        for bucket in search_result.aggs.priority.buckets:
            priority_buckets.append(
                {
                    "id": bucket.key,
                    "name": str(priority_display.get(bucket.key, bucket.key)),
                    "count": bucket.doc_count,
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

        # 状态聚合
        status_buckets = []
        for bucket in search_result.aggs.status.buckets:
            status_buckets.append(
                {
                    "id": bucket.key,
                    "name": str(status_display.get(bucket.key, bucket.key)),
                    "count": bucket.doc_count,
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

        # 类型聚合（是否回归）
        regression_buckets = []
        for bucket in search_result.aggs.is_regression.buckets:
            key_str = str(bucket.key).lower()
            name = "回归问题" if key_str in ("true", "1") else "新问题"
            regression_buckets.append(
                {
                    "id": key_str,
                    "name": name,
                    "count": bucket.doc_count,
                }
            )
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
    def clean_document(cls, doc: Any) -> dict:
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
        cleaned["impact_scope"] = add_dimension_display_name(impact_scope)

        # aggregate_config 直接透传
        cleaned["aggregate_config"] = data.get("aggregate_config") or {}

        return cleaned

    @classmethod
    def handle_hit(cls, hit: Any) -> dict:
        return cls.clean_document(hit)

    def add_alert_trend(self, issues: list[dict]) -> None:
        """
        批量查询 AlertDocument，为每个 Issue 填充 trend、alert_count 和 anomaly_message。

        参数:
            issues: search() 已清洗完成的 Issue 列表（会被原地修改）
        """
        issue_ids = [issue["id"] for issue in issues if issue.get("id")]
        if not issue_ids:
            return

        # 从本页 Issue 中提取告警时间边界
        first_alert_times = [issue["first_alert_time"] for issue in issues if issue.get("first_alert_time")]
        last_alert_times = [issue["last_alert_time"] for issue in issues if issue.get("last_alert_time")]

        start_time = int(min(first_alert_times))
        end_time = int(max(last_alert_times))
        interval = self.calculate_agg_interval(start_time, end_time)

        # 用请求参数一次性生成默认零值时间序列，无需在每个分片中重复计算
        aligned_start = start_time // interval * interval
        aligned_end = end_time // interval * interval + interval
        default_time_series = [[ts * 1000, 0] for ts in range(aligned_start, aligned_end, interval)]

        if not first_alert_times or not last_alert_times:
            for issue in issues:
                issue["trend"] = list(default_time_series)
                issue["alert_count"] = 0
                issue["anomaly_message"] = "--"
            return

        # 复用 AlertDateHistogramResultResource + 时间分片并行查询
        try:
            results = resource.alert.alert_date_histogram_result.bulk_request(
                [
                    {
                        "start_time": sliced_start_time,
                        "end_time": sliced_end_time,
                        "interval": interval,
                        "conditions": [{"key": "issue_id", "value": issue_ids, "method": "eq"}],
                        "group_by": ["issue_id"],
                    }
                    for sliced_start_time, sliced_end_time in slice_time_interval(start_time, end_time)
                ]
            )
        except Exception:
            logger.exception("add_alert_trend: bulk_request failed")
            for issue in issues:
                issue["trend"] = []
                issue["alert_count"] = 0
                issue["anomaly_message"] = "--"
            return

        # 合并各时间分片的结果
        merged = {}

        for result in results:
            for dimension_tuple, status_series in result.items():
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
                # status_group=False 时只返回 ABNORMAL 序列
                abnormal_series = status_series.get("ABNORMAL", {})
                merged[issue_id].update(abnormal_series)

        # 解析结果，回填到 Issue 列表
        for issue in issues:
            issue_id = issue["id"]
            if issue_id in merged:
                series = merged[issue_id]
                trend_data = []
                total_count = 0

                for ts, value in series.items():
                    trend_data.append([ts, value])
                    total_count += value

                issue["trend"] = trend_data
                issue["alert_count"] = total_count
            else:
                issue["trend"] = list(default_time_series)
                issue["alert_count"] = 0

        # 单独获取 anomaly_message
        self._fill_anomaly_message(issues, issue_ids, start_time, end_time)

    def _fill_anomaly_message(self, issues: list[dict], issue_ids: list[str], start_time: int, end_time: int) -> None:
        """单独查询每个 Issue 最新告警的 description 作为 anomaly_message"""
        try:
            search_object = AlertDocument.search(start_time=start_time, end_time=end_time)
            search_object = search_object.filter("terms", issue_id=issue_ids)

            issue_agg = search_object.aggs.bucket("issues", "terms", field="issue_id", size=len(issue_ids))
            issue_agg.metric(
                "latest_alert",
                "top_hits",
                size=1,
                sort=[{"begin_time": {"order": "desc"}}],
                _source=["description"],
            )

            result = search_object[:0].execute()

            msg_map = {}
            for issue_bucket in result.aggs.issues.buckets:
                issue_id = issue_bucket.key
                anomaly_message = "--"
                if hasattr(issue_bucket, "latest_alert") and issue_bucket.latest_alert:
                    hits = issue_bucket.latest_alert.hits
                    if hits and hits.hits and len(hits.hits) > 0:
                        source = hits.hits[0].to_dict().get("_source", {})
                        description = source.get("description", "")
                        if description:
                            anomaly_message = description
                msg_map[issue_id] = anomaly_message

            for issue in issues:
                issue["anomaly_message"] = msg_map.get(issue["id"], "--")
        except Exception:
            logger.exception("_fill_anomaly_message failed")
            for issue in issues:
                issue.setdefault("anomaly_message", "--")
