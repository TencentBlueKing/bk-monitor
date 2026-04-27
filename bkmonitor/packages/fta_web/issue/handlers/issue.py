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
from elasticsearch_dsl.response import Response

from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.issue import IssueDocument
from bkmonitor.utils.time_tools import hms_string
from constants.issue import ImpactScopeDimension, IssuePriority, IssueStatus
from fta_web.alert.handlers.base import BaseBizQueryHandler, BaseQueryTransformer, QueryField
from fta_web.alert.handlers.translator import BizTranslator, StrategyTranslator

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
        QueryField("name", "Issue 名称", es_field="name.raw", is_char=True),
        QueryField("status", "状态"),
        QueryField("priority", "优先级"),
        QueryField("assignee", "负责人"),
        QueryField("strategy_id", "策略ID"),
        QueryField("strategy_name", "策略名称", es_field="strategy_name.raw", is_char=True),
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
        trend_start_time: int = None,
        trend_end_time: int = None,
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

        self.trend_start_time = trend_start_time if trend_start_time is not None else self.start_time
        self.trend_end_time = trend_end_time if trend_end_time is not None else self.end_time

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

    def parse_condition_item(self, condition: dict) -> Q:
        """处理 impact_scope 相关的查询条件

        支持两种过滤方式：
        1. 维度级过滤（impact_dimensions）→ exists 查询
        2. 实例 ID 级过滤（impact_scope.{维度}.{ID字段}）→ terms 查询
        """
        key = condition["key"]

        if key == "impact_dimensions":
            # 维度级过滤：判断是否包含某个维度
            should_clauses = [Q("exists", field=f"impact_scope.{dim}") for dim in condition["value"]]
            return Q("bool", should=should_clauses, minimum_should_match=1)

        if key.startswith("impact_scope."):
            # 实例 ID 级过滤：按具体实例 ID 精确匹配
            # key: "impact_scope.host.bk_host_id" → ES field: "impact_scope.host.instance_list.bk_host_id"
            parts = key.split(".", 2)  # ["impact_scope", "host", "bk_host_id"]
            if len(parts) == 3:
                dimension, id_field = parts[1], parts[2]
                es_field = f"impact_scope.{dimension}.instance_list.{id_field}"
                # Flattened 类型所有值为 keyword，统一转字符串
                values = [str(v) for v in condition["value"]]
                return Q("terms", **{es_field: values})

        return super().parse_condition_item(condition)

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
        cleaned["impact_scope"] = add_dimension_display_name(impact_scope)

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
            fill_thread.join()
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
        fill_thread.join()

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
