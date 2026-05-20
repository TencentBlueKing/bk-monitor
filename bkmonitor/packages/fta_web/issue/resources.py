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
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from rest_framework import serializers

from bkmonitor.documents.issue import (
    IssueActivityDocument,
    IssueDocument,
    IssueDocumentWriteError,
    IssueNotFoundError,
)
from bkmonitor.utils.request import get_request_username
from bkmonitor.utils.thread_backend import ThreadPool
from constants.issue import IssuePriority, IssueStatus, IssueActivityType
from core.drf_resource import Resource, api, resource
from fta_web.alert.handlers.alert import AlertQueryHandler
from fta_web.alert.utils import slice_time_interval
from fta_web.issue.handlers.issue import (
    IssueQueryHandler,
)
from fta_web.issue.serializers import IssueSearchSerializer


logger = logging.getLogger("root")


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


def _run_batch(
    issues: list[dict],
    action_fn: Callable[[int, str], dict],
    max_workers: int = 10,
) -> dict:
    """
    批量操作公共执行框架：
    每条 Issue 的操作作为一个完整任务单元，由 ThreadPoolExecutor 并发执行。
    单条失败不影响其他条目，异常统一归入 failed 列表。

    Args:
        issues: Issue 条目列表，每项为 {"bk_biz_id": int, "issue_id": str}，至少 1 条。
                每条携带明确的 bk_biz_id，支持跨业务空间批量操作，同时保证权限校验精确。
        action_fn: 对单条 Issue 执行的业务操作，接收 (bk_biz_id, issue_id)，
                   执行成功时返回该条目的结果 dict，失败时抛出异常。
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
            bk_biz_id: 该条目声明的业务 ID。
            issue_id: 要处理的 Issue ID。

        Returns:
            dict，包含 ok 字段标识处理结果：
            - 成功：{"ok": True, "result": action_fn 的返回值}
            - 失败：{"ok": False, "issue_id": issue_id, "message": 错误信息}
        """
        try:
            result = action_fn(bk_biz_id, issue_id)
            return {"ok": True, "result": result}
        except IssueNotFoundError as e:
            return {"ok": False, "bk_biz_id": bk_biz_id, "issue_id": issue_id, "message": str(e)}
        except IssueDocumentWriteError as e:
            return {"ok": False, "bk_biz_id": bk_biz_id, "issue_id": issue_id, "message": f"ES 写入失败：{e}"}
        except Exception as e:
            return {"ok": False, "bk_biz_id": bk_biz_id, "issue_id": issue_id, "message": str(e)}

    succeeded = []
    failed = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(issues))) as executor:
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


class IssueTopNResultResource(Resource):
    """Issue TopN 子资源，供 bulk_request 并行调用"""

    class RequestSerializer(IssueSearchSerializer):
        fields = serializers.ListField(label="查询字段列表", child=serializers.CharField(), default=[])
        size = serializers.IntegerField(label="获取的桶数量", default=10)
        is_time_partitioned = serializers.BooleanField(required=False, default=False, label="是否按时间分片")
        is_finally_partition = serializers.BooleanField(required=False, default=False, label="是否是最后一个分片")
        authorized_bizs = serializers.ListField(child=serializers.IntegerField(), default=None)
        unauthorized_bizs = serializers.ListField(child=serializers.IntegerField(), default=None)
        need_bucket_count = serializers.BooleanField(required=False, default=True, label="是否需要进行基数聚合")

    def perform_request(self, validated_request_data):
        fields = validated_request_data.pop("fields")
        size = validated_request_data.pop("size")

        handler = IssueQueryHandler(**validated_request_data)
        return handler.top_n(fields=fields, size=size)


class IssueTopNResource(Resource):
    """Issue TopN 统计"""

    handler_cls = IssueQueryHandler

    class RequestSerializer(IssueSearchSerializer):
        fields = serializers.ListField(label="查询字段列表", child=serializers.CharField(), default=[])
        size = serializers.IntegerField(label="获取的桶数量", default=10)
        need_time_partition = serializers.BooleanField(required=False, default=True, label="是否需要按时间分片")

    def perform_request(self, validated_request_data):
        """
        执行 Issue TopN 查询，支持按时间分片并行查询以提升大时间跨度下的查询性能

        参数:
            validated_request_data: 已通过 RequestSerializer 校验的请求参数字典，主要包含：
                - bk_biz_ids: 业务ID列表，用于权限过滤
                - fields: 需要做 TopN 聚合的字段列表
                - size: 每个字段返回的桶数量上限
                - start_time / end_time: 查询的时间范围（Unix 时间戳，秒）
                - need_time_partition: 是否启用时间分片并行查询
                - 其他 IssueSearchSerializer 支持的过滤条件（query_string、conditions 等）

        返回值:
            dict: TopN 聚合结果，结构为 {"doc_count": int, "fields": [{...}, ...]}
                - doc_count: 命中的 Issue 总数
                - fields: 每个字段的 TopN 桶列表，含 bucket_count（桶基数）、buckets（桶详情）
        """
        # 步骤1：解析业务权限，把 bk_biz_ids 拆分为当前用户"有权限"与"无权限"两组，
        # 后续用于控制查询范围以及在结果中补齐 0 计数的授权业务
        bk_biz_ids = validated_request_data.get("bk_biz_ids")
        if bk_biz_ids is not None:
            authorized_bizs, unauthorized_bizs = self.handler_cls.parse_biz_item(bk_biz_ids)
            validated_request_data["authorized_bizs"] = authorized_bizs
            validated_request_data["unauthorized_bizs"] = unauthorized_bizs

        # 步骤2：fields 去重，保持传入顺序不变
        # 原因：分片合并时以 field 名作为聚合 key，若 fields 出现重复项，
        # 同一分片返回中该字段会出现多次，进入合并循环后会对同一 (id, name) 桶重复累加，
        # 最终导致 count 成倍虚高（倍数 = 重复次数）。此处在入口统一去重兜底。
        fields = validated_request_data.get("fields") or []
        validated_request_data["fields"] = list(dict.fromkeys(fields))

        need_time_partition = validated_request_data.pop("need_time_partition")
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")

        # 步骤3：时间跨度不超过7天时不启用分片，直接单次查询
        # 小时间范围下 ES 单次聚合已足够高效，分片反而带来额外开销
        if need_time_partition and (end_time - start_time) <= 7 * 24 * 3600:
            need_time_partition = False

        if not need_time_partition:
            # 非分片分支：直接交给底层 Resource 完成单次 ES 聚合
            return resource.issue.issue_top_n_result(**validated_request_data)

        # 步骤4：分片分支 —— 并行获取 bucket_count 基数聚合
        # 基数聚合需要跨越完整时间范围，无法通过分片结果简单相加得到准确值，
        # 因此放在子线程中与各分片 TopN 查询并行执行，避免串行等待
        executor = ThreadPool(processes=1)
        try:
            future = executor.apply_async(self.get_bucket_count, [validated_request_data])

            # 切分时间区间：pop 掉原始 start/end，用切片后的区间替代下发到每个分片请求
            validated_request_data.pop("start_time")
            validated_request_data.pop("end_time")
            slice_times = slice_time_interval(start_time, end_time)
            size = validated_request_data.get("size", 10)

            # 步骤5：并行请求各时间分片
            # - is_time_partitioned=True：通知底层按分片语义过滤（resolved_time 区间归属）
            # - is_finally_partition：最后一个分片承接"未解决 Issue"（~exists 仅在此处出现一次）
            # - need_bucket_count=False：分片内部不做基数聚合，由上面的并行线程统一获取
            results = resource.issue.issue_top_n_result.bulk_request(
                [
                    {
                        "start_time": sliced_start_time,
                        "end_time": sliced_end_time,
                        "is_finally_partition": index == len(slice_times) - 1,
                        "is_time_partitioned": True,
                        "need_bucket_count": False,
                        **validated_request_data,
                    }
                    for index, (sliced_start_time, sliced_end_time) in enumerate(slice_times)
                ]
            )

            # 步骤6：合并各分片结果
            # field_buckets_map 结构：{ field_name: {"field", "is_char", "id_buckets_map": {(id, name): {...}}} }
            # 使用 (id, name) 作为桶的唯一键，同键累加 count
            result = {"doc_count": 0, "fields": []}
            field_buckets_map = {}

            for sliced_result in results:
                # doc_count 直接相加（分片间按 resolved_time 不重叠归属，无重复）
                result["doc_count"] += sliced_result["doc_count"]

                for field_info in sliced_result["fields"]:
                    field = field_info["field"]
                    if field not in field_buckets_map:
                        field_buckets_map[field] = {
                            "id_buckets_map": {},
                            "field": field,
                            "is_char": field_info.get("is_char", False),
                        }

                    id_buckets_map = field_buckets_map[field]["id_buckets_map"]

                    # 桶级合并：同 (id, name) 累加 count，不同则新建
                    for bucket in field_info["buckets"]:
                        _id = bucket["id"]
                        name = bucket["name"]
                        if (_id, name) not in id_buckets_map:
                            id_buckets_map[(_id, name)] = {
                                "id": _id,
                                "name": name,
                                "count": bucket["count"],
                            }
                        else:
                            id_buckets_map[(_id, name)]["count"] += bucket["count"]

            # 将合并后的分桶 map 转为最终的字段列表结构
            for field_info in field_buckets_map.values():
                field = {
                    "field": field_info["field"],
                    "is_char": field_info["is_char"],
                    "bucket_count": 0,
                    "buckets": list(field_info["id_buckets_map"].values()),
                }
                result["fields"].append(field)

            # 步骤7：后处理 —— 补充 bucket_count 并将 buckets 截断到 size
            # 阻塞等待并行的基数聚合结果
            field_bucket_count_map = future.get()
        finally:
            executor.close()
            executor.join()

        for field_data in result["fields"]:
            field = field_data["field"]
            field_info = field_bucket_count_map.get(field) or {}
            bucket_count = field_info.get("bucket_count", 0)

            # bk_biz_id 字段特殊处理：把当前用户"有权限但查询结果为 0"的业务也补到桶里
            # 便于前端展示"所有授权业务"的分布情况（含 0 命中业务）
            if field == "bk_biz_id":
                exist_bizs = {int(bucket["id"]) for bucket in field_data["buckets"]}
                authorized_bizs = field_info.get("authorized_bizs", set())
                for biz in authorized_bizs:
                    # 补齐时也不能超过 size，避免桶数膨胀
                    if len(exist_bizs) > size:
                        break
                    if int(biz) not in exist_bizs:
                        field_data["buckets"].append({"id": biz, "name": biz, "count": 0})
                        bucket_count += 1

            # 按 count 倒序取 Top-size
            bucket_length = len(field_data["buckets"])
            field_data["buckets"].sort(key=lambda x: x["count"], reverse=True)
            field_data["buckets"] = field_data["buckets"][:size]

            # bucket_count 优先使用基数聚合结果；若实际桶数 <= size，则直接用当前桶数（更准确）
            field_data["bucket_count"] = bucket_count
            if field_data["bucket_count"] <= size:
                field_data["bucket_count"] = bucket_length

        return result

    def get_bucket_count(self, validated_request_data):
        """获取各字段的桶基数，用于在合并结果中填充准确的 bucket_count

        返回值统一为 dict 结构：{field: {"bucket_count": int, ...额外数据}}
        - 普通字段：{"bucket_count": int}
        - bk_biz_id：{"bucket_count": int, "authorized_bizs": set[int]}
        - impact_dimensions：{"bucket_count": int}
        """
        fields = validated_request_data.get("fields", [])
        handler = self.handler_cls(**validated_request_data)
        search_object = handler.get_search_object()
        search_object = handler.add_conditions(search_object)
        search_object = handler.add_query_string(search_object)
        search_object = search_object.params(track_total_hits=True).extra(size=0)

        bucket_count_suffix = handler.bucket_count_suffix

        for field in fields:
            actual_field = field.lstrip("-+")
            if actual_field == "impact_dimensions":
                handler.add_agg_bucket(search_object.aggs, field)
                continue
            handler.add_cardinality_bucket(search_object.aggs, field, bucket_count_suffix)

        search_result = search_object.execute()
        result = {}

        for field in fields:
            if not search_result.aggs:
                continue
            actual_field = field.lstrip("-+")
            if actual_field == "impact_dimensions":
                # impact_dimensions 使用 filters 聚合，bucket_count 取聚合返回 buckets 的数量
                buckets = handler._parse_impact_dimensions_buckets(search_result)  # noqa
                result[actual_field] = {"bucket_count": len(buckets)}
            elif actual_field == "bk_biz_id" and hasattr(handler, "authorized_bizs"):
                authorized_bizs = set(handler.authorized_bizs)
                result[actual_field] = {"bucket_count": len(authorized_bizs), "authorized_bizs": authorized_bizs}
            elif actual_field.startswith("dimension_values."):
                # dimension_values.{key}：cardinality agg name 经 sanitize（"." → "__"），
                # 与 IssueQueryHandler.add_cardinality_bucket 保持一致
                agg_name = actual_field.replace(".", "__") + bucket_count_suffix
                agg = getattr(search_result.aggs, agg_name, None)
                result[actual_field] = {"bucket_count": agg.value if agg else 0}
            else:
                agg = getattr(search_result.aggs, f"{field}{bucket_count_suffix}", None)
                result[actual_field] = {"bucket_count": agg.value if agg else 0}

        return result


class SearchIssueResource(Resource):
    """查询 Issue 列表"""

    class RequestSerializer(IssueSearchSerializer):
        ordering = serializers.ListField(label="排序", child=serializers.CharField(), default=[])
        page = serializers.IntegerField(label="页数", min_value=1, default=1)
        page_size = serializers.IntegerField(label="每页大小", min_value=0, max_value=500, default=10)
        show_aggs = serializers.BooleanField(label="展示聚合统计信息", default=True)
        show_dsl = serializers.BooleanField(label="返回ES DSL查询语句", default=False)
        trend_start_time = serializers.IntegerField(label="趋势图起始时间", required=False)
        trend_end_time = serializers.IntegerField(label="趋势图结束时间", required=False)

    def perform_request(self, validated_request_data):
        show_aggs = validated_request_data.pop("show_aggs")
        show_dsl = validated_request_data.pop("show_dsl")
        handler = IssueQueryHandler(**validated_request_data)
        result = handler.search(show_aggs=show_aggs, show_dsl=show_dsl)

        return result


class IssueDetailResource(Resource):
    """获取单个 Issue 的元数据信息（不包含告警动态数据）"""

    class RequestSerializer(serializers.Serializer):
        id = IssueIDField(label="Issue ID")
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)

    def perform_request(self, validated_request_data):
        """获取 Issue 元数据，告警动态数据由前端调用告警中心接口获取"""
        issue_id = validated_request_data["id"]
        bk_biz_id = validated_request_data["bk_biz_id"]

        issue = IssueDocument.get_issue_or_raise(issue_id, bk_biz_id=bk_biz_id)
        result = IssueQueryHandler.clean_document(issue)

        # 填充 anomaly_message（查询最新告警的 description）
        self._fill_anomaly_message(issue, result)

        return result

    @staticmethod
    def _fill_anomaly_message(issue: "IssueDocument", result: dict) -> None:
        """查询最新告警的 description 作为 anomaly_message"""
        from bkmonitor.documents.alert import AlertDocument

        try:
            # 优先使用 first_alert_time 限定索引范围；
            # 兜底使用 create_time 时提前 7 天，因为 issue.create_time 晚于实际告警时间
            _FALLBACK_BUFFER = 7 * 86400
            if issue.first_alert_time:
                start_time = int(issue.first_alert_time)
            else:
                start_time = int(issue.create_time) - _FALLBACK_BUFFER
            end_time = int(time.time())
            search = (
                AlertDocument.search(start_time=start_time, end_time=end_time)
                .filter("term", **{"event.bk_biz_id": issue.bk_biz_id})
                .filter("term", issue_id=issue.id)
                .sort({"create_time": {"order": "desc"}})
                .params(size=1)
                .source(["event.description"])
            )
            hits = search.execute().hits
            if hits:
                source = hits[0].to_dict()
                event_data = source.get("event", {})
                description = event_data.get("description", "") if isinstance(event_data, dict) else ""
                result["anomaly_message"] = description or "--"
            else:
                result["anomaly_message"] = "--"
        except Exception as e:
            logger.exception("IssueDetailResource._fill_anomaly_message failed: %s", e)
            result["anomaly_message"] = "--"


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

        def _action(bk_biz_id, issue_id):
            """
            指派或改派 Issue 负责人。
            待审核状态执行首次指派（PENDING_REVIEW → UNRESOLVED），其他状态执行改派（不触发状态流转）。

            Args:
                bk_biz_id: 业务 ID。
                issue_id: Issue ID。

            Returns:
                dict，包含 issue_id、status、assignee、update_time 字段。
            """
            return api.issue.assign(
                bk_biz_id=bk_biz_id,
                issue_id=issue_id,
                assignee=assignee,
                operator=operator,
            )

        return _run_batch(validated_request_data["issues"], _action)


class ResolveIssueResource(Resource):
    """批量标记为已解决"""

    class RequestSerializer(serializers.Serializer):
        issues = serializers.ListField(label="Issue 列表", child=IssueItemSerializer(), min_length=1)

    def perform_request(self, validated_request_data):
        operator = get_request_username()

        def _action(bk_biz_id, issue_id):
            """
            将 Issue 标记为已解决。

            Args:
                bk_biz_id: 业务 ID。
                issue_id: Issue ID。

            Returns:
                dict，包含 issue_id、status、resolved_time、update_time 字段。
            """
            return api.issue.resolve(
                bk_biz_id=bk_biz_id,
                issue_id=issue_id,
                operator=operator,
            )

        return _run_batch(validated_request_data["issues"], _action)


class ArchiveIssueResource(Resource):
    """批量归档 Issue（实例级）"""

    class RequestSerializer(serializers.Serializer):
        issues = serializers.ListField(label="Issue 列表", child=IssueItemSerializer(), min_length=1)

    def perform_request(self, validated_request_data):
        operator = get_request_username()

        def _action(bk_biz_id, issue_id):
            return api.issue.archive(
                bk_biz_id=bk_biz_id,
                issue_id=issue_id,
                operator=operator,
            )

        return _run_batch(validated_request_data["issues"], _action)


class ReopenIssueResource(Resource):
    """批量重新打开 Issue（已解决 → 未解决）"""

    class RequestSerializer(serializers.Serializer):
        issues = serializers.ListField(label="Issue 列表", child=IssueItemSerializer(), min_length=1)

    def perform_request(self, validated_request_data):
        operator = get_request_username()

        def _action(bk_biz_id, issue_id):
            return api.issue.reopen(
                bk_biz_id=bk_biz_id,
                issue_id=issue_id,
                operator=operator,
            )

        return _run_batch(validated_request_data["issues"], _action)


class RestoreIssueResource(Resource):
    """批量恢复归档 Issue（归档 → 归档前状态）"""

    class RequestSerializer(serializers.Serializer):
        issues = serializers.ListField(label="Issue 列表", child=IssueItemSerializer(), min_length=1)

    def perform_request(self, validated_request_data):
        operator = get_request_username()

        def _action(bk_biz_id, issue_id):
            return api.issue.restore(
                bk_biz_id=bk_biz_id,
                issue_id=issue_id,
                operator=operator,
            )

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

        def _action(bk_biz_id, issue_id):
            return api.issue.update_priority(
                bk_biz_id=bk_biz_id,
                issue_id=issue_id,
                priority=priority,
                operator=operator,
            )

        return _run_batch(validated_request_data["issues"], _action)


class AddIssueFollowUpResource(Resource):
    """添加跟进信息（支持向多个 Issue 写入同一条评论）"""

    class RequestSerializer(serializers.Serializer):
        issues = serializers.ListField(label="Issue 列表", child=IssueItemSerializer(), min_length=1)
        content = serializers.CharField(label="跟进内容", min_length=1)

    def perform_request(self, validated_request_data):
        content = validated_request_data["content"]
        operator = get_request_username()

        def _action(bk_biz_id, issue_id):
            return api.issue.add_follow_up(
                bk_biz_id=bk_biz_id,
                issue_id=issue_id,
                content=content,
                operator=operator,
            )

        return _run_batch(validated_request_data["issues"], _action)


class EditIssueFollowUpResource(Resource):
    """编辑跟进评论"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        activity_id = serializers.CharField(label="评论活动 ID", min_length=1)
        content = serializers.CharField(label="编辑后的内容", min_length=1)

    def perform_request(self, validated_request_data):
        operator = get_request_username()
        return api.issue.edit_follow_up(
            bk_biz_id=validated_request_data["bk_biz_id"],
            issue_id=validated_request_data["issue_id"],
            activity_id=validated_request_data["activity_id"],
            content=validated_request_data["content"],
            operator=operator,
        )


class RenameIssueResource(Resource):
    """重命名 Issue"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        new_name = serializers.CharField(label="Issue 名称", min_length=1, max_length=256)

    def perform_request(self, validated_request_data):
        operator = get_request_username()
        return api.issue.rename(
            bk_biz_id=validated_request_data["bk_biz_id"],
            issue_id=validated_request_data["issue_id"],
            new_name=validated_request_data["new_name"],
            operator=operator,
        )


class ListIssueActivitiesResource(Resource):
    """查询 Issue 变更记录（活动日志）"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")

    def perform_request(self, validated_request_data):
        issue_id = validated_request_data["issue_id"]
        bk_biz_id = validated_request_data["bk_biz_id"]

        # 校验 Issue 存在且归属当前业务（单条查询，bk_biz_id 为单个值）
        IssueDocument.get_issue_or_raise(issue_id, bk_biz_id=bk_biz_id)

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
                "bk_biz_id": hit.bk_biz_id,
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
        current_issue = IssueDocument.get_issue_or_raise(issue_id, bk_biz_id=bk_biz_id)

        # fingerprint 为空：legacy 1:1 数据（迁移函数已自动 RESOLVE，但用户仍可能查 RESOLVED 列表里的旧 Issue）
        # 新模型下"同问题历史"按 fingerprint 切分，旧 1:1 数据无法对齐到新模型语义，直接返回空列表。
        # 真正的"同策略相关 Issue"用户可通过列表页 strategy_id 过滤获得。
        # 前端可通过 issue.fingerprint 字段判断是否为 legacy（响应 schema 保持 list 不变以兼容现有前端）
        if not current_issue.fingerprint:
            return []

        # 按 fingerprint 查"同一具体问题"已解决历史，排除当前 Issue 自身，按解决时间降序，最多 200 条
        search = (
            IssueDocument.search(all_indices=True)
            .filter("term", bk_biz_id=str(bk_biz_id))
            .filter("term", fingerprint=current_issue.fingerprint)
            .filter("term", status=IssueStatus.RESOLVED)
            .exclude("term", **{"_id": issue_id})
            .sort("-resolved_time")
            .params(size=200)
        )
        hits = search.execute().hits

        return [
            {
                "bk_biz_id": hit.bk_biz_id,
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


class ExportIssueResource(Resource):
    """导出 Issue 列表数据"""

    class RequestSerializer(serializers.Serializer):
        issues = serializers.ListField(label="Issue 列表", child=IssueItemSerializer(), min_length=1, max_length=500)
        trend_start_time = serializers.IntegerField(label="趋势图起始时间", required=False)
        trend_end_time = serializers.IntegerField(label="趋势图结束时间", required=False)

    def perform_request(self, validated_request_data):
        issues = validated_request_data["issues"]
        issue_ids = [item["issue_id"] for item in issues]
        bk_biz_ids = [item["bk_biz_id"] for item in issues]

        handler = IssueQueryHandler(
            bk_biz_ids=bk_biz_ids,
            conditions=[{"key": "id", "value": issue_ids, "method": "eq"}],
            page=1,
            page_size=len(issue_ids),
            trend_start_time=validated_request_data.get("trend_start_time"),
            trend_end_time=validated_request_data.get("trend_end_time"),
        )
        result = handler.search(show_aggs=False)
        issue_list = result.get("issues", [])

        if not issue_list:
            raise ValueError("未找到符合条件的 Issue，无法导出")

        return resource.export_import.export_package(json_list_data=issue_list)


class ListRecentAssigneesResource(Resource):
    """获取最近经常指派的负责人列表（基于指派事件聚合）"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(
            label="业务ID", default=None, allow_null=True, child=serializers.IntegerField()
        )
        recent_days = serializers.IntegerField(label="最近天数", min_value=1, max_value=30, default=7)

    def perform_request(self, validated_request_data):
        bk_biz_ids = validated_request_data.get("bk_biz_ids") or []
        recent_days = validated_request_data["recent_days"]

        # 业务权限校验：仅保留当前用户有权限的业务
        authorized_bizs = IssueQueryHandler.parse_biz_item(bk_biz_ids)[0]
        if not authorized_bizs:
            return []
        authorized_biz_ids = [str(b) for b in authorized_bizs]

        end_time = int(time.time())
        start_time = end_time - recent_days * 86400

        # 基于活动日志查询指派事件
        search = (
            IssueActivityDocument.search(start_time=start_time, end_time=end_time)
            .filter("range", time={"gte": start_time, "lte": end_time})
            .filter("term", activity_type=IssueActivityType.ASSIGNEE_CHANGE)
            .filter("terms", bk_biz_id=authorized_biz_ids)
        )

        # terms 聚合：按 to_value 分组（to_value 存储逗号分隔的负责人列表）
        search.aggs.bucket("assignees", "terms", field="to_value", size=500, order={"_count": "desc"})
        search = search.params(size=0, track_total_hits=False)

        result = search.execute()

        # to_value 是逗号分隔的字符串（如 "user1,user2"），拆分后重新统计频次
        counter = Counter()
        if result.aggs:
            for bucket in result.aggs.assignees.buckets:
                if not bucket.key:
                    continue
                for assignee in bucket.key.split(","):
                    assignee = assignee.strip()
                    if assignee:
                        counter[assignee] += bucket.doc_count

        return [username for username, _ in counter.most_common(100)]
