"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from rest_framework import serializers

from bkmonitor.documents.issue import IssueActivityDocument, IssueDocument, IssueDocumentWriteError
from bkmonitor.utils.request import get_request_username
from constants.issue import IssueActivityType, IssuePriority, IssueStatus
from core.drf_resource import Resource
from fta_web.alert.handlers.alert import AlertQueryHandler
from fta_web.alert.utils import slice_time_interval
from fta_web.issue.handlers.issue import IssueQueryHandler
from fta_web.issue.serializers import IssueSearchSerializer


logger = logging.getLogger("root")


class IssueNotFoundError(Exception):
    """issue not found"""


class IssueIDField(serializers.CharField):
    """Issue ID 合法性校验"""

    def run_validation(self, *args, **kwargs):
        value = super().run_validation(*args, **kwargs)
        try:
            IssueDocument.parse_timestamp_by_id(value)
        except Exception as e:
            logger.error("Invalid Issue ID, issue_id=%s, error: %s", value, e)
            raise serializers.ValidationError(f"'{value}' is not a valid Issue ID")
        return value


def _get_issue_or_raise(issue_id: str, bk_biz_id: int | None = None) -> IssueDocument:
    """
    按 issue_id 查询 IssueDocument，不存在则抛出 IssueNotFoundError。
    使用 all_indices=True 避免跨天漏查（对齐 IssueAggregationProcessor._find_active_issue 查询口径）。

    Args:
        issue_id: 要查询的 Issue ID。
        bk_biz_id: 若传入，则在查出 Issue 后校验业务归属，防止越权操作。
                   Issue 的 bk_biz_id 与传入值不匹配时抛出 IssueNotFoundError（而非权限错误），
                   避免泄露其他业务的 Issue 存在信息。

    Returns:
        IssueDocument 实例。

    Raises:
        IssueNotFoundError: Issue 不存在，或 bk_biz_id 不匹配时抛出。
    """
    search = IssueDocument.search(all_indices=True).filter("term", **{"_id": issue_id}).params(size=1)
    hits = search.execute().hits
    if not hits:
        raise IssueNotFoundError(f"Issue not found, issue_id={issue_id}")
    source = hits[0].to_dict()
    # IssueDocument._source 中含 id 字段，需先 pop 再显式传入 meta.id，
    # 否则会触发 "multiple values for keyword argument 'id'"；
    # 若不传 meta.id，__init__ 会自动生成新 ID，导致 UPSERT 退化为 INSERT。
    source.pop("id", None)
    issue = IssueDocument(id=hits[0].meta.id, **source)
    if bk_biz_id is not None and issue.bk_biz_id != bk_biz_id:
        raise IssueNotFoundError(f"Issue not found, issue_id={issue_id}")
    return issue


def _run_batch(
        issues: list[dict],
        action_fn: Callable[[IssueDocument], dict],
        max_workers: int = 10,
) -> dict:
    """
    批量操作公共执行框架：
    每条 Issue 的查询 + 写入作为一个完整任务单元，由 ThreadPoolExecutor 并发执行。
    单条失败不影响其他条目，异常统一归入 failed 列表。

    Args:
        issues: Issue 条目列表，每项为 {"bk_biz_id": int, "issue_id": str}，至少 1 条。
                每条携带明确的 bk_biz_id，支持跨业务空间批量操作，同时保证权限校验精确。
        action_fn: 对单条 Issue 执行的业务操作，执行成功时返回该条目的结果 dict，失败时抛出异常。
        max_workers: 线程池最大并发数，默认 10。

    Returns:
        dict，包含两个键：
        - succeeded: list[dict]，成功处理的条目结果列表，内容由 action_fn 返回值决定。
        - failed: list[dict]，失败的条目列表，每项包含 issue_id 和 message 字段。
    """

    def _process_one(bk_biz_id: int, issue_id: str) -> dict:
        """
        处理单条 Issue，返回结果 dict：
        - 成功：{"ok": True, "result": ...}
        - 失败：{"ok": False, "issue_id": ..., "message": ...}

        Args:
            bk_biz_id: 该条目声明的业务 ID，用于校验 Issue 归属。
            issue_id: 要处理的 Issue ID。

        Returns:
            dict，包含 ok 字段标识处理结果：
            - 成功：{"ok": True, "result": action_fn 的返回值}
            - 失败：{"ok": False, "issue_id": issue_id, "message": 错误信息}
        """
        try:
            issue = _get_issue_or_raise(issue_id, bk_biz_id=bk_biz_id)
            return {"ok": True, "result": action_fn(issue)}
        except IssueNotFoundError as e:
            return {"ok": False, "bk_biz_id": bk_biz_id, "issue_id": issue_id, "message": str(e)}
        except IssueDocumentWriteError as e:
            return {"ok": False, "bk_biz_id": bk_biz_id, "issue_id": issue_id, "message": f"ES 写入失败：{e}"}
        except Exception as e:
            return {"ok": False, "bk_biz_id": bk_biz_id, "issue_id": issue_id, "message": str(e)}

    succeeded = []
    failed = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_process_one, item["bk_biz_id"], item["issue_id"]) for item in issues]
        for future in as_completed(futures):
            item = future.result()
            if item["ok"]:
                succeeded.append(item["result"])
            else:
                failed.append(
                    {"bk_biz_id": item["bk_biz_id"], "issue_id": item["issue_id"], "message": item["message"]}
                )

    return {"succeeded": succeeded, "failed": failed}


class IssueItemSerializer(serializers.Serializer):
    """单条 Issue 条目（bk_biz_id + issue_id 配对）"""

    bk_biz_id = serializers.IntegerField(label="业务ID")
    issue_id = IssueIDField(label="Issue ID")


class SearchIssueResource(Resource):
    """查询 Issue 列表"""

    class RequestSerializer(IssueSearchSerializer):
        ordering = serializers.ListField(label="排序", child=serializers.CharField(), default=[])
        page = serializers.IntegerField(label="页数", min_value=1, default=1)
        page_size = serializers.IntegerField(label="每页大小", min_value=0, max_value=500, default=10)
        show_aggs = serializers.BooleanField(label="展示聚合统计信息", default=True)
        show_dsl = serializers.BooleanField(label="返回ES DSL查询语句", default=False)

    def perform_request(self, validated_request_data):
        show_aggs = validated_request_data.pop("show_aggs")
        show_dsl = validated_request_data.pop("show_dsl")
        handler = IssueQueryHandler(**validated_request_data)
        result = handler.search(show_aggs=show_aggs, show_dsl=show_dsl)

        return result


class IssueAlertDateHistogramResultResource(Resource):
    """查询 Issue 关联的告警趋势图（支持 group_by 分组维度）"""

    def perform_request(self, validated_request_data):
        interval = validated_request_data.pop("interval", "auto")
        group_by = validated_request_data.pop("group_by", None)
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")

        handler = AlertQueryHandler(**validated_request_data)
        results = handler.date_histogram(interval=interval, group_by=group_by)

        if not results:
            return {"default_time_series": {"start_time": start_time, "end_time": end_time, "interval": interval}}

        # 未指定 group_by 时保持与 AlertDateHistogramResultResource 一致的返回格式
        if not group_by:
            return list(results.values())[0]

        return results

    @staticmethod
    def sliced_date_histogram(
        start_time: int,
        end_time: int,
        interval: int | str = "auto",
        handler_kwargs: dict = None,
        group_by: list[str] | None = None,
    ) -> dict:
        """
        按时间分片并行查询告警趋势图，合并各分片结果。

        通过 bulk_request 调用自身 perform_request 实现并行，
        根据是否指定 group_by 采用不同的合并策略。

        参数:
            start_time: 起始时间戳（秒）
            end_time: 结束时间戳（秒）
            interval: 聚合间隔，"auto" 表示自动计算
            handler_kwargs: 构造 AlertQueryHandler 的额外参数（如 conditions、bk_biz_ids 等）
            group_by: 分组维度列表，默认 None 表示按 status 分组

        返回值示例:

        1) 无 group_by（默认按 status 分组）—— 两层结构 {状态: {时间戳: 数量}}:
           sliced_date_histogram(start_time=1741334400, end_time=1741348800, ...)
           {
               "ABNORMAL":  {1741334400000: 5, 1741338000000: 8, ...},
               "RECOVERED": {1741334400000: 0, 1741338000000: 2, ...},
               "CLOSED":    {1741334400000: 0, 1741338000000: 1, ...},
           }

        2) 有 group_by —— 三层结构 {维度元组: {状态: {时间戳: 数量}}}:
           sliced_date_histogram(..., group_by=["issue_id"])
           {
               ("issue-abc",): {
                   "ABNORMAL":  {1741334400000: 3, 1741338000000: 5, ...},
                   "RECOVERED": {1741334400000: 0, 1741338000000: 1, ...},
                   "CLOSED":    {1741334400000: 0, 1741338000000: 0, ...},
               },
               ("issue-def",): {
                   "ABNORMAL":  {1741334400000: 2, 1741338000000: 3, ...},
                   "RECOVERED": {1741334400000: 0, 1741338000000: 1, ...},
                   "CLOSED":    {1741334400000: 0, 1741338000000: 1, ...},
               },
           }
        """
        handler_kwargs = handler_kwargs or {}

        # 构造分片请求列表，通过 bulk_request 并行执行
        results = IssueAlertDateHistogramResultResource().bulk_request(
            [
                {
                    "start_time": sliced_start,
                    "end_time": sliced_end,
                    "interval": interval,
                    "group_by": group_by,
                    **handler_kwargs,
                }
                for sliced_start, sliced_end in slice_time_interval(start_time, end_time)
            ]
        )

        if group_by:
            # 有 group_by：三层结构 {维度元组: {状态: {时间戳: 数量}}}
            merged = {}
            for result in results:
                if isinstance(result, dict) and "default_time_series" in result:
                    continue
                for dimension_tuple, status_series in result.items():
                    if dimension_tuple not in merged:
                        merged[dimension_tuple] = {}
                    for status_key, ts_map in status_series.items():
                        if status_key not in merged[dimension_tuple]:
                            merged[dimension_tuple][status_key] = {}
                        merged[dimension_tuple][status_key].update(ts_map)
            return merged
        else:
            # 无 group_by：两层结构 {状态: {时间戳: 数量}}
            merged = {}
            for result in results:
                for status, series in result.items():
                    if status == "default_time_series":
                        continue
                    if status not in merged:
                        merged[status] = {}
                    merged[status].update(series)
            return merged


class AssignIssueResource(Resource):
    """指派/改派负责人（支持批量）"""

    class RequestSerializer(serializers.Serializer):
        issues = serializers.ListField(label="Issue 列表", child=IssueItemSerializer(), min_length=1)
        assignee = serializers.ListField(label="负责人列表", child=serializers.CharField(min_length=1), min_length=1)

    def perform_request(self, validated_request_data):
        assignee = validated_request_data["assignee"]
        operator = get_request_username()

        def _action(issue):
            """
            指派或改派 Issue 负责人。
            待审核状态执行首次指派，未解决状态执行改派，其他状态不允许操作。

            Args:
                issue: 要操作的 IssueDocument 实例。

            Returns:
                dict，包含 issue_id、status、assignee、update_time 字段。

            Raises:
                ValueError: Issue 当前状态不允许指派时抛出。
            """
            if issue.status == IssueStatus.PENDING_REVIEW:
                issue.assign(assignees=assignee, operator=operator)
            elif issue.status == IssueStatus.UNRESOLVED:
                issue.reassign(assignees=assignee, operator=operator)
            else:
                raise ValueError(
                    f"Issue {issue.id} 当前状态 {issue.status} 不允许指派，"
                    f"仅允许 {IssueStatus.PENDING_REVIEW} / {IssueStatus.UNRESOLVED}"
                )
            return {
                "bk_biz_id": issue.bk_biz_id,
                "issue_id": str(issue.id),
                "status": str(issue.status),
                "assignee": list(issue.assignee or []),
                "update_time": issue.update_time,
            }

        return _run_batch(validated_request_data["issues"], _action)


class ResolveIssueResource(Resource):
    """批量标记为已解决"""

    class RequestSerializer(serializers.Serializer):
        issues = serializers.ListField(label="Issue 列表", child=IssueItemSerializer(), min_length=1)

    def perform_request(self, validated_request_data):
        operator = get_request_username()

        def _action(issue):
            """
            将 Issue 标记为已解决。

            Args:
                issue: 要操作的 IssueDocument 实例。

            Returns:
                dict，包含 issue_id、status、resolved_time、update_time 字段。
            """
            issue.resolve(operator=operator)
            return {
                "bk_biz_id": issue.bk_biz_id,
                "issue_id": issue.id,
                "status": issue.status,
                "resolved_time": issue.resolved_time,
                "update_time": issue.update_time,
            }

        return _run_batch(validated_request_data["issues"], _action)


class ArchiveIssueResource(Resource):
    """批量归档 Issue（实例级）"""

    class RequestSerializer(serializers.Serializer):
        issues = serializers.ListField(label="Issue 列表", child=IssueItemSerializer(), min_length=1)

    def perform_request(self, validated_request_data):
        operator = get_request_username()

        def _action(issue):
            """
            将 Issue 归档。

            Args:
                issue: 要操作的 IssueDocument 实例。

            Returns:
                dict，包含 issue_id、status、update_time 字段。
            """
            issue.archive(operator=operator)
            return {
                "bk_biz_id": issue.bk_biz_id,
                "issue_id": issue.id,
                "status": issue.status,
                "update_time": issue.update_time,
            }

        return _run_batch(validated_request_data["issues"], _action)


class UpdateIssuePriorityResource(Resource):
    """批量修改优先级"""

    class RequestSerializer(serializers.Serializer):
        issues = serializers.ListField(label="Issue 列表", child=IssueItemSerializer(), min_length=1)
        priority = serializers.ChoiceField(
            label="优先级",
            choices=[IssuePriority.P0, IssuePriority.P1, IssuePriority.P2],
        )

    def perform_request(self, validated_request_data):
        priority = validated_request_data["priority"]
        operator = get_request_username()

        def _action(issue):
            """
            修改 Issue 优先级。

            Args:
                issue: 要操作的 IssueDocument 实例。

            Returns:
                dict，包含 issue_id、priority、update_time 字段。
            """
            issue.update_priority(priority=priority, operator=operator)
            return {
                "bk_biz_id": issue.bk_biz_id,
                "issue_id": str(issue.id),
                "priority": str(issue.priority),
                "update_time": issue.update_time,
            }

        return _run_batch(validated_request_data["issues"], _action)


class AddIssueFollowUpResource(Resource):
    """添加跟进信息（支持向多个 Issue 写入同一条评论）"""

    class RequestSerializer(serializers.Serializer):
        issues = serializers.ListField(label="Issue 列表", child=IssueItemSerializer(), min_length=1)
        content = serializers.CharField(label="跟进内容", min_length=1)

    def perform_request(self, validated_request_data):
        content = validated_request_data["content"]
        operator = get_request_username()
        now = int(time.time())

        def _action(issue):
            """
            向 Issue 写入一条跟进评论。

            Args:
                issue: 要操作的 IssueDocument 实例。

            Returns:
                dict，包含 activity_id、issue_id、activity_type、content、operator、time 字段。
            """
            activity = IssueActivityDocument(
                issue_id=issue.id,
                bk_biz_id=issue.bk_biz_id,
                activity_type=IssueActivityType.COMMENT,
                content=content,
                operator=operator,
                time=now,
                create_time=now,
            )
            IssueActivityDocument.bulk_create([activity])
            return {
                "bk_biz_id": issue.bk_biz_id,
                "activity_id": activity.id,
                "issue_id": issue.id,
                "activity_type": IssueActivityType.COMMENT,
                "content": content,
                "operator": operator,
                "time": now,
            }

        return _run_batch(validated_request_data["issues"], _action)


class ListIssueActivitiesResource(Resource):
    """查询 Issue 变更记录（活动日志）"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")

    def perform_request(self, validated_request_data):
        issue_id = validated_request_data["issue_id"]

        # 校验 Issue 存在且归属当前业务（单条查询，bk_biz_id 为单个值）
        _get_issue_or_raise(issue_id, bk_biz_id=validated_request_data["bk_biz_id"])

        # 查询该 Issue 的全部活动日志，按时间降序排列（最近发生的在前）
        # 使用 all_indices=True 避免跨天漏查（活动日志与 Issue 可能跨天）
        search = (
            IssueActivityDocument.search(all_indices=True)
            .filter("term", issue_id=issue_id)
            .sort("-time")
            .params(size=500)
        )
        hits = search.execute().hits

        return [
            {
                "activity_id": hit.meta.id,
                "activity_type": hit.activity_type,
                "operator": hit.operator or "",
                "from_value": getattr(hit, "from_value", None) or None,
                "to_value": getattr(hit, "to_value", None) or None,
                "content": getattr(hit, "content", None) or None,
                "time": int(hit.time) if hit.time else 0,
            }
            for hit in hits
        ]


class ListIssueHistoryResource(Resource):
    """查询历史 Issue（同策略下已解决的历史 Issue 列表）"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="当前 Issue ID")

    def perform_request(self, validated_request_data):
        issue_id = validated_request_data["issue_id"]
        bk_biz_id = validated_request_data["bk_biz_id"]

        # 校验当前 Issue 存在且归属当前业务
        current_issue = _get_issue_or_raise(issue_id, bk_biz_id=bk_biz_id)

        # 查询同策略下所有已解决的历史 Issue（排除当前 Issue 自身），按解决时间降序排列，最多返回 200 条
        search = (
            IssueDocument.search(all_indices=True)
            .filter("term", bk_biz_id=str(bk_biz_id))
            .filter("term", strategy_id=current_issue.strategy_id)
            .filter("term", status=IssueStatus.RESOLVED)
            .exclude("term", **{"_id": issue_id})
            .sort("-resolved_time")
            .params(size=200)
        )
        hits = search.execute().hits

        return [
            {
                "issue_id": hit.meta.id,
                "name": hit.name,
                "status": hit.status,
                "priority": hit.priority,
                "assignee": list(hit.assignee) if hit.assignee else [],
                "is_regression": bool(hit.is_regression) if hit.is_regression is not None else False,
                "alert_count": int(hit.alert_count) if hit.alert_count is not None else 0,
                "first_alert_time": int(hit.first_alert_time) if hit.first_alert_time is not None else 0,
                "last_alert_time": int(hit.last_alert_time) if hit.last_alert_time is not None else 0,
                "create_time": int(hit.create_time) if hit.create_time is not None else 0,
                "resolved_time": int(hit.resolved_time) if hit.resolved_time is not None else 0,
            }
            for hit in hits
        ]
