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
import json
import re
import time

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers, exceptions
from rest_framework.decorators import api_view

from bkm_space.utils import bk_biz_id_to_space_uid
from bkmonitor.documents.issue import (
    IssueActivityDocument,
    IssueDocument,
    IssueDocumentWriteError,
    IssueNotFoundError,
)
from bkmonitor.issue_merge import IssueFrozenError, IssueMergeResolver
from bkmonitor.models import TapdWorkspaceBinding, TapdWorkspaceManualUnbind
from bkmonitor.models.issue import IssueMergeRelation, IssueTapdRelation
from bkmonitor.utils.request import get_request_username, get_request
from django.db import transaction
from bkmonitor.utils.tenant import space_uid_to_bk_tenant_id, bk_biz_id_to_bk_tenant_id
from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.utils.user import set_local_username
from constants.issue import IssuePriority, IssueStatus, IssueActivityType
from core.drf_resource import Resource, api, resource
from core.drf_resource.exceptions import CustomException
from core.errors.api import BKAPIError
from core.errors.common import HTTP404Error
from fta_web.alert.handlers.alert import AlertQueryHandler
from fta_web.alert.utils import slice_time_interval
from fta_web.issue.handlers.issue import (
    IssueQueryHandler,
)
from fta_web.issue.serializers import IssueSearchSerializer
from fta_web.constants import TapdWorkspaceBindStatus
from fta_web.issue.utils.tapd import (
    save_tapd_token,
    verify_signed_state,
    generate_install_url,
    try_bind_importable,
    normalize_redirect_url,
    get_tapd_token,
    delete_tapd_token,
    generate_auth_url,
)

logger = logging.getLogger("root")


def _sanitize_for_log(value) -> str:
    return str(value).replace("\r", "").replace("\n", "")


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
        except IssueFrozenError as e:
            # 本地直接调用路径（如非中转场景）的合并冻结
            return {
                "ok": False,
                "bk_biz_id": bk_biz_id,
                "issue_id": issue_id,
                "code": e.extra.get("business_code"),
                "detail": e.extra,
                "message": e.message,
            }
        except BKAPIError as e:
            # 状态机操作经 web→api role 中转：冻结在 api role 抛出，过 HTTP 后已不是
            # IssueFrozenError 实例，而是 BKAPIError（e.data 即 api 的 result_json）。
            # custom_exception_handler 把 Error.extra **平铺到响应顶层**（result.update(exc.extra)，
            # 见 core/drf_resource/exceptions.py），故 business_code/conflicting_main_issue_id 在
            # payload 顶层；同时兼容潜在的嵌套 extra 形状（payload["extra"]）。
            payload = e.data if isinstance(e.data, dict) else {}
            fields = payload.get("extra") if isinstance(payload.get("extra"), dict) else payload
            item = {
                "ok": False,
                "bk_biz_id": bk_biz_id,
                "issue_id": issue_id,
                "message": payload.get("message") or str(e),
            }
            if fields.get("business_code") == "MERGE_FREEZE_VIOLATION":
                item["code"] = fields.get("business_code")
                item["detail"] = {
                    "business_code": fields.get("business_code"),
                    "conflicting_main_issue_id": fields.get("conflicting_main_issue_id"),
                    "issue_id": fields.get("issue_id"),
                }
            return item
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
                # 旧错误路径仅含 message；IssueFrozenError 额外带 code + detail（向后兼容）
                failed_item = {
                    "bk_biz_id": item["bk_biz_id"],
                    "issue_id": item["issue_id"],
                    "message": item["message"],
                }
                if "code" in item:
                    failed_item["code"] = item["code"]
                if "detail" in item:
                    failed_item["detail"] = item["detail"]
                failed.append(failed_item)

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

    def perform_request(self, validated_request_data: dict) -> dict:
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

    def perform_request(self, validated_request_data: dict) -> dict:
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

    def perform_request(self, validated_request_data: dict) -> dict:
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

    def perform_request(self, validated_request_data: dict) -> dict:
        """获取 Issue 元数据，告警动态数据由前端调用告警中心接口获取。

        合并视图：若请求的 issue_id 是 active member，自动返回主 Issue 数据 +
        ``redirected_from=<原 issue_id>`` 字段；前端据此 URL 静默替换为主 Issue。
        主 Issue 自身则注入 ``merge_status.active_members`` 摘要供详情页展示。
        """
        issue_id = validated_request_data["id"]
        bk_biz_id = validated_request_data["bk_biz_id"]

        # 合并视图：member id → 主 id 重定向（仅 active 关系）
        from bkmonitor.issue_merge import IssueMergeResolver, MergeResolverContext

        ctx = MergeResolverContext(bk_biz_id)
        ctx.load()
        display_id = IssueMergeResolver.resolve_display_id(issue_id, ctx)
        redirected_from = issue_id if display_id != issue_id else None

        issue = IssueDocument.get_issue_or_raise(display_id, bk_biz_id=bk_biz_id)
        result = IssueQueryHandler.clean_document(issue)

        # 注入 merge_status（主 Issue 拼装 active_members；member 拼装 main_issue_id）
        IssueMergeResolver.hydrate_aggregations([result], ctx)

        # hydrate union 改写了主 Issue 的 impact_scope（member 维度的 instance 是 ES 原始字段、
        # 未经 enrich），role='main' 时需重跑 enrich_impact_scope 补 alert_query_fields，
        # 与 IssueQueryHandler.search 同款修复。
        if result.get("merge_status", {}).get("role") == "main" and result.get("impact_scope"):
            IssueQueryHandler.enrich_impact_scope(result["impact_scope"])

        if redirected_from:
            result["redirected_from"] = redirected_from

        # 填充 anomaly_message（查询最新告警的 description）
        # 合并视图：主 Issue 取「自身 + 全部 active member」范围内的最新告警，口径与
        # 告警列表 / 趋势保持一致（未合并时 expand_to_full_ids 透传为 [display_id]）。
        anomaly_issue_ids = IssueMergeResolver.expand_to_full_ids([display_id], ctx)
        self._fill_anomaly_message(issue, result, issue_ids=anomaly_issue_ids)

        # 注入 split_info（独立 Issue 拿到拆分溯源信息）：
        # 仅当 issue 不是 active member 重定向得到的（redirected_from is None）
        # 且自己曾经是别人的 split 产物时，前端可据此展示「来自合并 Issues 拆分」+「拆分依据」标签
        if not redirected_from:
            self._fill_split_info(display_id, bk_biz_id, result)

        return result

    @staticmethod
    def _fill_split_info(issue_id: str, bk_biz_id: int, result: dict) -> None:
        """查 IssueMergeRelation 中 status='split' 的最新一条关系，拼装 split_info。

        多次 split 取最新（按 update_time desc）。reasons 优先读关系表（结构化
        source-of-truth），活动日志 SPLIT_FROM.content 为审计副本。
        失败 fail-open：不阻塞主路径，仅 warning。
        """
        try:
            relation = (
                IssueMergeRelation.objects.filter(
                    member_issue_id=issue_id,
                    bk_biz_id=bk_biz_id,
                    status=IssueMergeRelation.STATUS_SPLIT,
                )
                .order_by("-update_time", "-id")
                .first()
            )
        except Exception:
            logger.warning(
                "[issue-merge] fill split_info SQL query failed (fail-open, issue_id=%s)",
                issue_id,
                exc_info=True,
            )
            return

        if not relation:
            return

        # 查主 Issue name（拼装"来自 Issue X (name) 拆分"提示）；ES 异常时 name 留空兜底
        main_name = None
        try:
            main_hits = (
                IssueDocument.search(all_indices=True)
                .filter("term", _id=relation.main_issue_id)
                .source(["name"])
                .params(size=1)
                .execute()
                .hits
            )
            if main_hits:
                main_name = getattr(main_hits[0], "name", None)
        except Exception:
            logger.warning(
                "[issue-merge] fill split_info main name fetch failed (fail-open, main_id=%s)",
                relation.main_issue_id,
                exc_info=True,
            )

        result["split_info"] = {
            "split_from_main_issue_id": relation.main_issue_id,
            "split_from_main_issue_name": main_name or f"{relation.main_issue_id} (已删除)",
            "split_reasons": relation.split_reasons or [],
            "split_kind": relation.split_kind,
            "split_time": int(relation.update_time.timestamp()) if relation.update_time else 0,
            "split_operator": relation.update_user,
        }

    @staticmethod
    def _fill_anomaly_message(issue: "IssueDocument", result: dict, issue_ids: list[str] | None = None) -> None:
        """查询最新告警的 description 作为 anomaly_message。

        ``issue_ids``：参与查询的 Issue id 集合，合并视图下为主 Issue 自身 + 全部 active
        member（由 caller 经 expand_to_full_ids 展开）；为空时退回 ``[issue.id]``。
        """
        from bkmonitor.documents.alert import AlertDocument

        query_issue_ids = issue_ids or [issue.id]
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
                .filter("terms", issue_id=query_issue_ids)
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

    def perform_request(self, validated_request_data: dict) -> dict:
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
        bk_biz_ids: [int],
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
                    "bk_biz_ids": bk_biz_ids,
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

    def perform_request(self, validated_request_data: dict) -> dict:
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

    def perform_request(self, validated_request_data: dict) -> dict:
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

    def perform_request(self, validated_request_data: dict) -> dict:
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

    def perform_request(self, validated_request_data: dict) -> dict:
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

    def perform_request(self, validated_request_data: dict) -> dict:
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

    def perform_request(self, validated_request_data: dict) -> dict:
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

    def perform_request(self, validated_request_data: dict) -> dict:
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

    def perform_request(self, validated_request_data: dict) -> dict:
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

    def perform_request(self, validated_request_data: dict) -> dict:
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

    def perform_request(self, validated_request_data: dict) -> dict:
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

    def perform_request(self, validated_request_data: dict) -> dict:
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

        # 排除"当前是 active 关系冻结 member"的 Issue：合并后 member 归属主 Issue 展示，
        # 不应再作为独立历史出现在"同问题历史"列表（与 Search/TopN/Export 的 active member
        # 隐藏口径一致；本接口自建查询、未走 get_search_object，需单独排除）。放开"非活跃
        # Issue 可并入活跃主"后，RESOLVED 冻结 member 更易命中同 fingerprint 历史查询，故必须排除。
        # get_active_member_ids 内部 fail-open（SQL 失败返回 []，退化为不排除）。
        from bkmonitor.issue_merge import IssueMergeResolver

        active_member_ids = IssueMergeResolver.get_active_member_ids(bk_biz_id)

        # 按 fingerprint 查"同一具体问题"已解决历史，排除当前 Issue 自身 + active 冻结 member，
        # 按解决时间降序，最多 200 条
        search = (
            IssueDocument.search(all_indices=True)
            .filter("term", bk_biz_id=str(bk_biz_id))
            .filter("term", fingerprint=current_issue.fingerprint)
            .filter("term", status=IssueStatus.RESOLVED)
            .exclude("term", **{"_id": issue_id})
            .sort("-resolved_time")
            .params(size=200)
        )
        if active_member_ids:
            search = search.exclude("terms", _id=active_member_ids)
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

    def perform_request(self, validated_request_data: dict) -> dict:
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

    def perform_request(self, validated_request_data: dict) -> dict:
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


class MergeIssueResource(Resource):
    """合并 Issue：web 端薄壳，转 api role 端 ``api.issue.merge`` 执行。

    与现网其他状态变更 Resource（resolve / archive / reopen 等）保持架构一致：
    cache 写入必须在 api role 执行（web role 缺 ``REDIS_*_CONF``，会被静默吞）。
    校验、关系写入、活动日志、cache invalidate 全部在 ``kernel_api/views/v4/issue.py:MergeResource``。
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        main_issue_id = IssueIDField(label="主 Issue ID")
        members = serializers.ListField(label="并入 Issue ID 列表", child=IssueIDField(), min_length=1, max_length=100)
        # 合并依据非必填：缺省/空列表均合法（与拆分依据对齐；下游 merge_reasons 默认空列表已兜底）
        reasons = serializers.ListField(label="合并依据", child=serializers.CharField(), required=False, default=list)

    def perform_request(self, validated_request_data: dict) -> dict:
        return api.issue.merge(
            bk_biz_id=validated_request_data["bk_biz_id"],
            main_issue_id=validated_request_data["main_issue_id"],
            members=validated_request_data["members"],
            reasons=validated_request_data["reasons"],
            operator=get_request_username(),
        )


class SplitIssueResource(Resource):
    """拆分单个 member Issue：web 端薄壳，转 api role 端 ``api.issue.split`` 执行。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        member_issue_id = IssueIDField(label="并入 Issue ID")
        # 拆分依据非必填：缺省/空列表均合法（下游 bulk_reset_for_split 与 split_info 已按空兜底）
        reasons = serializers.ListField(label="拆分依据", child=serializers.CharField(), required=False, default=list)

    def perform_request(self, validated_request_data: dict) -> dict:
        return api.issue.split(
            bk_biz_id=validated_request_data["bk_biz_id"],
            member_issue_id=validated_request_data["member_issue_id"],
            reasons=validated_request_data["reasons"],
            operator=get_request_username(),
        )


_MERGE_SOURCES_ANOMALY_FALLBACK_BUFFER = 30 * 86400


def _fetch_member_anomaly_messages(member_ids: list[str], first_alert_time_map: dict[str, int]) -> dict[str, str]:
    """批量查 member 最新告警 description。复用 IssueQueryHandler._fill_anomaly_message 范式：
    1 次 AlertDocument terms agg + top_hits(size=1, sort begin_time desc)。

    Args:
        member_ids: 待查询的 member Issue ID 列表（active + split 全集）。
        first_alert_time_map: ``{member_id: first_alert_time}``，用于取 min 作为索引时间窗下界；
            缺失或全空时回退 ``now - 30d``，覆盖 ES 索引典型保留窗口。

    Returns:
        ``{member_id: description}``；未命中或失败的 member 不在返回字典中。
        失败统一 fail-open（warning + 空 dict），由 caller 兜底为 ``"--"``。
    """
    if not member_ids:
        return {}

    from bkmonitor.documents.alert import AlertDocument

    valid_times = [t for t in first_alert_time_map.values() if t]
    end_time = int(time.time())
    start_time = min(valid_times) if valid_times else end_time - _MERGE_SOURCES_ANOMALY_FALLBACK_BUFFER

    try:
        search_object = AlertDocument.search(start_time=start_time, end_time=end_time).filter(
            "terms", issue_id=member_ids
        )
        issue_agg = search_object.aggs.bucket("issues", "terms", field="issue_id", size=len(member_ids))
        issue_agg.metric(
            "latest_alert",
            "top_hits",
            size=1,
            sort=[{"begin_time": {"order": "desc"}}],
            _source=["event.description"],
        )
        result = search_object[:0].execute()
    except Exception as e:
        logger.warning("[issue-merge] list_merge_sources fill anomaly_message failed (fail-open): %s", e)
        return {}

    msg_map: dict[str, str] = {}
    for issue_bucket in result.aggs.issues.buckets:
        if not hasattr(issue_bucket, "latest_alert") or not issue_bucket.latest_alert:
            continue
        hits = issue_bucket.latest_alert.hits
        if not hits or not hits.hits:
            continue
        # top_hits 返回的 hit 是 AttrDict，_source 在 hit["_source"] 中
        source = hits.hits[0].to_dict().get("_source", {})
        event_data = source.get("event", {})
        description = event_data.get("description", "") if isinstance(event_data, dict) else ""
        if description:
            msg_map[issue_bucket.key] = description
    return msg_map


class ListMergeSourcesResource(Resource):
    """列主 Issue 的合并来源（active + split 历史，数据源以 MySQL 关系表为主）。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        main_issue_id = IssueIDField(label="主 Issue ID")

    def perform_request(self, validated_request_data: dict) -> dict:
        bk_biz_id = validated_request_data["bk_biz_id"]
        main_id = validated_request_data["main_issue_id"]

        relations = list(
            IssueMergeRelation.objects.filter(main_issue_id=main_id, bk_biz_id=bk_biz_id).order_by("-create_time")
        )

        result = {"main_issue_id": main_id, "active_members": [], "split_history": []}
        if not relations:
            return result

        member_ids = [r.member_issue_id for r in relations]
        # 同次 ES 查询多 source 一个 first_alert_time，用于后续 anomaly_message 查询的索引时间窗
        member_hits = (
            IssueDocument.search(all_indices=True)
            .filter("terms", _id=member_ids)
            .source(["name", "status", "first_alert_time"])
            .params(size=len(member_ids))
            .execute()
            .hits
        )
        name_map = {hit.meta.id: getattr(hit, "name", None) for hit in member_hits}
        first_alert_time_map = {hit.meta.id: int(getattr(hit, "first_alert_time", 0) or 0) for hit in member_hits}
        # member 当前 ES status：方案 A cascade follow 落地后 active member 的 status 会跟随主，
        # 前端可据此展示 member 当前真实状态（如"已跟随主 Issue RESOLVED"）
        member_es_status_map = {hit.meta.id: getattr(hit, "status", None) for hit in member_hits}

        # 批量拉 member 最新告警 description（1 次 ES agg；失败 fail-open）
        anomaly_map = _fetch_member_anomaly_messages(member_ids, first_alert_time_map)

        for r in relations:
            item = {
                "member_issue_id": r.member_issue_id,
                "member_name": name_map.get(r.member_issue_id) or f"{r.member_issue_id} (已删除)",
                "anomaly_message": anomaly_map.get(r.member_issue_id, "--"),
                "merge_reasons": r.merge_reasons,
                "merge_operator": r.create_user,
                "merge_time": int(r.create_time.timestamp()) if r.create_time else 0,
                # 关系状态（active / split）。旧字段 `status` 保留一个发布周期向后兼容，
                # 待前端切到 `relation_status` 后下一版移除
                "status": r.status,
                "relation_status": r.status,
                # member 自身的 ES status（PENDING_REVIEW / UNRESOLVED / RESOLVED / ARCHIVED）。
                # ES 缺失时为 None，前端按"已删除"占位渲染
                "member_es_status": member_es_status_map.get(r.member_issue_id),
            }
            if r.status == IssueMergeRelation.STATUS_SPLIT:
                item.update(
                    {
                        # split_reasons 模型 default=None，统一 or [] 兜底（与 split_info / resolver /
                        # bkm_cli 三处读取口径一致），避免同一字段在不同接口出现 null vs [] 形状分叉
                        "split_reasons": r.split_reasons or [],
                        "split_operator": r.update_user,
                        "split_time": int(r.update_time.timestamp()) if r.update_time else 0,
                        "split_kind": r.split_kind,
                    }
                )
                result["split_history"].append(item)
            else:
                result["active_members"].append(item)
        return result


class AlertIssueEnrichResource(Resource):
    """alert.issue_id → 主 Issue 展示信息批量 enrich（模块解耦）。

    前端在 alert 列表/详情拿到 alert 后调一次此接口拼装"所属 Issue"列：
    - member id 自动 resolve 为主 id（合并视图）
    - 返回主 Issue name；查不到则展示 ``"{issue_id} (已删除)"``

    模块边界：alert 模块不依赖 issue 内部模型；按需调用，alert search 不增加延迟。
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_ids = serializers.ListField(
            label="alert.issue_id 列表", child=serializers.CharField(), min_length=1, max_length=500
        )

    def perform_request(self, validated_request_data: dict) -> dict:
        from bkmonitor.issue_merge import IssueMergeResolver, MergeResolverContext

        bk_biz_id = validated_request_data["bk_biz_id"]
        issue_ids = list(dict.fromkeys(validated_request_data["issue_ids"]))  # 去重保序

        ctx = MergeResolverContext(bk_biz_id)
        ctx.load()
        display_map = {iid: IssueMergeResolver.resolve_display_id(iid, ctx) for iid in issue_ids}

        # 批量查主 Issue name（去重后查 ES）
        main_ids = list(set(display_map.values()))
        name_map: dict[str, str] = {}
        if main_ids:
            try:
                hits = (
                    IssueDocument.search(all_indices=True)
                    .filter("terms", _id=main_ids)
                    .source(["name"])
                    .params(size=len(main_ids))
                    .execute()
                    .hits
                )
                name_map = {hit.meta.id: getattr(hit, "name", None) for hit in hits}
            except Exception as e:
                logger.warning("[issue-merge] alert enrich name lookup failed: %s", e)

        return {
            iid: {
                "display_issue_id": display_map[iid],
                "display_issue_name": name_map.get(display_map[iid]) or f"{display_map[iid]} (已删除)",
            }
            for iid in issue_ids
        }


class ListTapdWorkspaceResource(Resource):
    """获取已授权的tapd项目列表"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        workspace_id = serializers.IntegerField(label="项目ID", required=False)
        created = serializers.CharField(label="创建时间", required=False, help_text="格式：YYYY-MM-DD，支持范围查询")
        limit = serializers.IntegerField(label="返回数量限制", min_value=1, max_value=200, default=30, required=False)
        page = serializers.IntegerField(label="页码", min_value=1, default=1, required=False)
        order = serializers.CharField(
            label="排序规则",
            required=False,
            default="created desc",
            help_text="格式：字段名 ASC或DESC，如：created desc",
        )
        fields = serializers.CharField(label="获取字段", required=False, help_text="多个字段以逗号分隔，如：id,created")

    def perform_request(self, validated_request_data: dict) -> dict:
        # 第一步：获取已授权的workspace列表
        params = {
            "workspace_id": validated_request_data.get("workspace_id"),
            "created": validated_request_data.get("created"),
            "limit": validated_request_data.get("limit"),
            "page": validated_request_data.get("page"),
            "order": validated_request_data.get("order", "created desc"),
            "fields": validated_request_data.get("fields"),
        }
        params = {k: v for k, v in params.items() if v is not None}
        tapd_workspace_result = api.tapd.get_granted_workspaces(**params)
        workspaces = tapd_workspace_result.get("list", [])

        if not workspaces:
            return []

        # 第二步：并发获取每个workspace的详细信息
        def _get_workspace_info(workspace_item, index):
            """获取单个workspace的详细信息"""
            workspace_data = workspace_item.get("OpenOrganizationApp", {})
            workspace_id = workspace_data.get("workspace_id", "")
            try:
                workspace_id = int(workspace_id)
                workspace_info = api.tapd.get_workspace_info(workspace_id=workspace_id)["Workspace"]
                return {
                    "index": index,  # 记录原始位置
                    "workspace_id": workspace_info["id"],
                    "workspace_name": workspace_info["name"],
                    "pretty_name": workspace_info["pretty_name"],
                    "created": workspace_info["created"],
                    "creator": workspace_info["creator"],
                    "description": workspace_info["description"],
                    "status": workspace_info["status"],
                    "category": workspace_info["category"],
                }
            except Exception as e:
                logger.warning("获取TAPD workspace信息失败, workspace_id=%s: %s", workspace_id, e)
                return {
                    "index": index,  # 记录原始位置
                    "workspace_id": str(workspace_id),
                    "workspace_name": f"{workspace_id}",
                    "pretty_name": "",
                    "created": workspace_data.get("created", ""),
                    "creator": "",
                    "description": "",
                    "status": "",
                    "category": "",
                }

        # 使用线程池并发调用，最大并发数限制为10
        max_workers = min(10, len(workspaces))
        tapd_workspace_info = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务，记录每个workspace的原始索引
            future_to_index = {}
            for i, workspace in enumerate(workspaces):
                future = executor.submit(_get_workspace_info, workspace, i)
                future_to_index[future] = i

            for future in as_completed(future_to_index):
                result = future.result()
                if result:
                    tapd_workspace_info.append(result)

        # 第三步：按照原始顺序排序，保持与第一步查询结果一致的排序
        tapd_workspace_info.sort(key=lambda x: x["index"])

        # 移除临时索引字段
        for item in tapd_workspace_info:
            item.pop("index", None)

        return tapd_workspace_info


class GetTapdFieldsResource(Resource):
    """
    获取 Tapd 单据字段
    """

    # 核心字段定义（固定必填、不可取消）
    # Story 核心字段：
    #   - name: 标题
    #   - description: 详细描述
    #   - owner: 处理人
    #   - priority_label: 优先级
    #   - iteration_id: 所属迭代
    STORY_CORE_FIELDS: set[str] = {"name", "description", "owner", "priority_label", "iteration_id"}

    # Bug 核心字段：
    #   - title: 标题
    #   - description: 详细描述
    #   - current_owner: 处理人
    #   - priority_label: 优先级
    #   - iteration_id: 所属迭代
    #   - te: 测试人员
    BUG_CORE_FIELDS: set[str] = {"title", "description", "current_owner", "priority_label", "iteration_id", "te"}

    # 缺陷字段ID的映射（统一返回结构）
    BUG_FIELD_ID_MAPPING: dict[str, str] = {"title": "name", "current_owner": "owner"}

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        workspace_id = serializers.IntegerField(label="项目ID")
        tapd_type = serializers.CharField(label="tapd单据类型")
        template_id = serializers.IntegerField(label="模板ID", default=0)

    @staticmethod
    def _convert_options(options: dict | list) -> list[dict[str, str]]:
        """将选项从字典格式转换为列表格式

        Args:
            options: TAPD API 返回的选项数据，可能是字典、或空列表

        Returns:
            标准化的选项列表，每个元素包含 id 和 name 字段

        Examples:
            >>> _convert_options({"urgent": "紧急", "high": "高"})
            [{"id": "urgent", "name": "紧急"}, {"id": "high", "name": "高"}]
        """
        if isinstance(options, dict):
            return [{"id": key, "name": value} for key, value in options.items()]
        return []

    def _get_core_fields(self, tapd_type: str) -> set[str]:
        """获取指定单据类型的核心字段集合

        Args:
            tapd_type: 单据类型，'story' 或 'bug'

        Returns:
            核心字段 ID 集合
        """
        if tapd_type == "story":
            return self.STORY_CORE_FIELDS
        elif tapd_type == "bug":
            return self.BUG_CORE_FIELDS
        else:
            return set()

    def _map_field_id(self, field_id: str, tapd_type: str) -> str:
        """映射字段 ID

        将缺陷字段 ID 映射为统一的字段 ID

        Args:
            field_id: 原始字段 ID
            tapd_type: 单据类型

        Returns:
            映射后的字段 ID
        """
        if tapd_type == "bug" and field_id in self.BUG_FIELD_ID_MAPPING:
            return self.BUG_FIELD_ID_MAPPING[field_id]
        return field_id

    def perform_request(self, validated_request_data: dict) -> list[dict]:
        bk_biz_id = validated_request_data["bk_biz_id"]
        workspace_id = validated_request_data["workspace_id"]
        tapd_type = validated_request_data["tapd_type"]
        template_id = validated_request_data.get("template_id", 0)

        # 当前仅支持 story 和 bug 单据类型以及 template_id=0（默认模板），不支持自定义模板字段查询，后续再扩展
        if tapd_type not in ("story", "bug"):
            raise serializers.ValidationError(f"不支持的 TAPD 单据类型: {tapd_type}，仅支持 story 和 bug")
        if template_id != 0:
            raise serializers.ValidationError(
                f"当前不支持模板自定义字段查询，请传入 template_id=0（默认模板），当前传入值: {template_id}"
            )

        # 获取 TAPD 字段信息
        if tapd_type == "story":
            fields_info = api.tapd.get_story_fields_info(workspace_id=workspace_id)
        else:  # tapd_type == "bug"
            fields_info = api.tapd.get_bug_fields_info(workspace_id=workspace_id)

        if not fields_info:
            raise serializers.ValidationError(
                f"获取 TAPD 字段信息失败，workspace_id={workspace_id}，tapd_type={tapd_type}，"
                f"请检查 TAPD 项目配置或联系管理员"
            )

        # 获取核心字段集合
        core_fields = self._get_core_fields(tapd_type)

        result = []
        for field_id, detail in fields_info.items():
            # 本期只返回核心字段，下期再完善管理字段功能
            if field_id not in core_fields:
                continue

            mapped_field_id = self._map_field_id(field_id, tapd_type)
            options = self._convert_options(detail["options"])

            result.append(
                {
                    "bk_biz_id": bk_biz_id,
                    "workspace_id": workspace_id,
                    "tapd_type": tapd_type,
                    "template_id": template_id,
                    "field_id": mapped_field_id,
                    "field_name": detail.get("label", field_id),
                    "field_type": detail["html_type"],
                    "options": options,
                    "is_core_field": True,
                    "is_selected": True,
                    "is_required": True,
                }
            )

        return result


class SearchTAPDItemsResource(Resource):
    """查询 TAPD 平台上已有的需求（story）或缺陷（bug）单据列表

    通过 tapd_type 参数指定单据类型，支持按 ID 或标题过滤，支持分页和排序。
    """

    # 字段映射：统一字段名 → TAPD 原始字段名（仅需映射的字段）
    # 查询参数和响应字段共用：查询时 name→title，响应时 title→name
    BUG_FIELD_MAPPING: dict[str, str] = {"name": "title", "owner": "current_owner"}
    # 构建反向映射：TAPD 原始字段名 → 统一字段名
    BUG_FIELD_MAPPING_REVERSE: dict[str, str] = {v: k for k, v in BUG_FIELD_MAPPING.items()}

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        workspace_id = serializers.IntegerField(label="项目ID")
        tapd_type = serializers.ChoiceField(
            label="单据类型",
            choices=["story", "bug"],
            help_text="单据类型：story(需求), bug(缺陷)",
        )
        id = serializers.CharField(
            label="单据ID",
            required=False,
            help_text="支持多ID查询，多个以逗号分隔",
        )
        name = serializers.CharField(
            label="标题",
            required=False,
            help_text="支持模糊匹配",
        )
        limit = serializers.IntegerField(
            label="返回数量限制",
            required=False,
            default=30,
            min_value=1,
            max_value=200,
        )
        page = serializers.IntegerField(
            label="页码",
            required=False,
            default=1,
            min_value=1,
        )
        order = serializers.CharField(
            label="排序规则",
            required=False,
            default="created desc",
            help_text="格式：字段名 ASC 或 字段名 DESC，如：created desc",
        )

        def validate_order(self, value: str) -> str:
            """验证 order 参数格式"""
            # 支持的格式：字段名 ASC 或 字段名 DESC（不区分大小写）
            pattern = r"^[a-zA-Z_][a-zA-Z0-9_]*\s+(ASC|DESC)$"
            if not re.match(pattern, value.strip(), re.IGNORECASE):
                raise serializers.ValidationError(
                    "order 参数格式错误，应为：字段名 ASC 或 字段名 DESC，如：created desc"
                )
            return value.strip()

        fields = serializers.CharField(
            label="返回字段",
            required=False,
            default="id,name,status,created,priority_label",
            help_text="设置返回的字段，多个字段间以逗号隔开。bk_biz_id、workspace_id、tapd_type 固定返回，无需指定。",
        )

    @classmethod
    def _query_tapd_items(
        cls,
        tapd_type: str,
        workspace_id: int,
        limit: int,
        page: int,
        order: str,
        fields: str,
        id: str = "",
        name: str = "",
    ) -> list[dict]:
        """调用 TAPD API 查询单据列表

        Args:
            tapd_type: 单据类型，story 或 bug
            workspace_id: TAPD 项目 ID
            id: 单据 ID，支持逗号分隔多 ID
            name: 标题模糊匹配
            limit: 返回数量限制
            page: 页码
            order: 排序规则
            fields: 返回字段列表

        Returns:
            TAPD 数据列表
        """
        # 处理 fields 参数：将统一字段名映射为 TAPD 原始字段名
        params = {}
        if fields:
            field_list = [f.strip() for f in fields.split(",")]
            if tapd_type == "bug":
                field_list = [cls.BUG_FIELD_MAPPING.get(f, f) for f in field_list]
            params["fields"] = ",".join(field_list)

        params.update(
            {
                "workspace_id": workspace_id,
                "limit": limit,
                "page": page,
                "order": order,
            }
        )
        if id:
            params["id"] = id
        if name:
            params["name"] = name

        if tapd_type == "bug":
            # 查询参数字段重命名（name → title，owner → current_owner）
            params = {cls.BUG_FIELD_MAPPING.get(k, k): v for k, v in params.items()}
            tapd_data = api.tapd.get_bugs(**params)
            field_mapping = cls.BUG_FIELD_MAPPING_REVERSE
        else:
            tapd_data = api.tapd.get_stories(**params)
            field_mapping = {}

        # 解包外层类型 key：{"Story": {...}} → {...}
        # 响应字段重命名（bug 类型：title → name）
        wrapper_key = tapd_type.capitalize()
        results = []
        for tapd in tapd_data:
            item = tapd[wrapper_key]
            if field_mapping:
                item = {field_mapping.get(k, k): v for k, v in item.items()}
            results.append(item)

        # 补充 status_display_name：根据字段元数据的 options 映射状态值
        if any(item.get("status") for item in results):
            try:
                if tapd_type == "bug":
                    fields_info = api.tapd.get_bug_fields_info(workspace_id=workspace_id)
                else:
                    fields_info = api.tapd.get_story_fields_info(workspace_id=workspace_id)
                status_options = (fields_info or {}).get("status", {}).get("options", {})
                for item in results:
                    status = item.get("status")
                    if not status:
                        continue
                    item["status_display_name"] = status_options.get(status, status)
            except Exception:
                logger.warning(
                    "Failed to get status options for tapd_type=%s, workspace_id=%s",
                    tapd_type,
                    workspace_id,
                    exc_info=True,
                )
                for item in results:
                    status = item.get("status")
                    if status:
                        item["status_display_name"] = status

        return results

    def perform_request(self, validated_request_data: dict) -> list[dict]:
        bk_biz_id = validated_request_data["bk_biz_id"]
        workspace_id = validated_request_data["workspace_id"]
        tapd_type = validated_request_data["tapd_type"]

        tapd_items = self._query_tapd_items(
            tapd_type=tapd_type,
            workspace_id=workspace_id,
            id=validated_request_data.get("id", ""),
            name=validated_request_data.get("name", ""),
            limit=validated_request_data["limit"],
            page=validated_request_data["page"],
            order=validated_request_data["order"],
            fields=validated_request_data["fields"],
        )

        for item in tapd_items:
            item["bk_biz_id"] = bk_biz_id
            item["workspace_id"] = str(workspace_id)
            item["tapd_type"] = tapd_type

        return tapd_items


class CreateTapdResource(Resource):
    """创建TAPD单据接口
    支持两种单据类型：
    1. story - 需求单据
    2. bug - 缺陷单据
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")

        tapd_type = serializers.ChoiceField(
            label="TAPD单据类型",
            choices=["story", "bug"],
            help_text="单据类型：story(需求), bug(缺陷)",
        )
        workspace_id = serializers.IntegerField(label="项目ID")
        name = serializers.CharField(label="单据标题")
        description = serializers.CharField(label="详细描述")
        owner = serializers.CharField(label="单据处理人", help_text="支持多成员，如：aaa;bbb;")
        priority_label = serializers.CharField(label="优先级")
        iteration_id = serializers.CharField(label="迭代ID")
        te = serializers.CharField(label="测试人员", required=False)
        sync_status = serializers.BooleanField(
            label="同步单据状态",
            help_text="勾选后，TAPD单据完成时自动同步状态到Issue",
        )

        def validate(self, attrs):
            # 创建bug单据时te字段必填
            if attrs.get("tapd_type") == "bug" and not attrs.get("te"):
                raise serializers.ValidationError("The te field is required when tapd_type is bug")
            if attrs.get("sync_status"):
                raise serializers.ValidationError("sync_status is not supported until TAPD status sync is implemented")

            return attrs

    @staticmethod
    def _read_activities(issue_id: str) -> list:
        """读取当前 Issue 全部活动日志（按时间降序）

        Args:
            issue_id: Issue ID

        Returns:
            活动日志列表，每项包含 bk_biz_id、activity_id、activity_type、
            operator、from_value、to_value、content、time 字段。
            查询失败时返回空列表。
        """
        try:
            search = (
                IssueActivityDocument.search(all_indices=True)
                .filter("term", issue_id=issue_id)
                .sort("-time")
                .extra(size=500)
            )
            hits = search.execute().hits
            return [
                {
                    "bk_biz_id": hit.bk_biz_id,
                    "activity_id": hit.meta.id,
                    "activity_type": hit.activity_type,
                    "operator": hit.operator or "",
                    "from_value": hit.from_value,
                    "to_value": hit.to_value,
                    "content": hit.content,
                    "time": int(hit.time) if hit.time else 0,
                }
                for hit in hits
            ]
        except Exception:
            logger.exception("Failed to read activities, issue_id=%s", issue_id)
            return []

    @staticmethod
    def _create_tapd(
        tapd_type: str,
        workspace_id: int,
        name: str,
        description: str,
        owner: str,
        priority_label: str,
        iteration_id: str,
        te: str = "",
    ) -> dict:
        """调用 TAPD API 创建单据并返回统一结构的单据信息

        Args:
            tapd_type: 单据类型，story 或 bug
            workspace_id: TAPD 项目 ID
            name: 单据标题
            description: 详细描述
            owner: 处理人
            priority_label: 优先级
            iteration_id: 迭代 ID
            te: 测试人员（bug 类型必填）

        Returns:
            统一结构的单据信息 dict，包含 tapd_id、tapd_type、name、
            description、owner、priority_label、iteration_id 等字段。
            bug 类型额外包含 te 字段。
        """
        if tapd_type == "story":
            params = {
                "workspace_id": workspace_id,
                "name": name,
                "description": description,
                "owner": owner,
                "priority_label": priority_label,
                "iteration_id": iteration_id,
            }
            params = {k: v for k, v in params.items() if v is not None}
            rs = api.tapd.add_story(**params)["Story"]
            return {
                "tapd_id": str(rs["id"]),
                "tapd_type": tapd_type,
                "name": rs["name"],
                "description": rs["description"],
                "owner": rs["owner"],
                "priority_label": rs["priority_label"],
                "iteration_id": rs["iteration_id"],
            }
        else:
            params = {
                "workspace_id": workspace_id,
                "title": name,
                "description": description,
                "current_owner": owner,
                "priority_label": priority_label,
                "iteration_id": iteration_id,
                "te": te,
            }
            params = {k: v for k, v in params.items() if v is not None}
            rs = api.tapd.add_bug(**params)["Bug"]
            return {
                "tapd_id": str(rs["id"]),
                "tapd_type": tapd_type,
                "name": rs["title"],
                "description": rs["description"],
                "owner": rs["current_owner"],
                "priority_label": rs["priority_label"],
                "iteration_id": rs["iteration_id"],
                "te": rs["te"],
            }

    @staticmethod
    def _save_relation(tapd_info: dict) -> None:
        """保存 Issue 与 TAPD 单据的关联关系

        如果相同 bk_biz_id + workspace_id + issue_id + tapd_id 的关联记录已存在，则修改。

        Args:
            tapd_info: TAPD 单据信息字典，必须包含以下字段：
                - tapd_id: TAPD 单据 ID（用于关联查询）
                - tapd_type: 单据类型（story/bug）
                - name: 单据标题
                - bk_biz_id: 业务 ID
                - issue_id: Issue ID
                - workspace_id: TAPD 项目 ID
                - sync_status: 是否同步状态
        """
        tapd_id = tapd_info["tapd_id"]
        obj, created = IssueTapdRelation.objects.update_or_create(
            bk_biz_id=tapd_info["bk_biz_id"],
            issue_id=tapd_info["issue_id"],
            workspace_id=tapd_info["workspace_id"],
            tapd_id=tapd_id,
            defaults={
                "tapd_type": tapd_info["tapd_type"],
                "tapd_title": tapd_info["name"],
                "link_mode": "create",
                "sync_status": tapd_info["sync_status"],
            },
        )
        if not created:
            logger.info(
                "IssueTapdRelation already exists, issue_id=%s, tapd_id=%s, skip creating",
                tapd_info["issue_id"],
                tapd_id,
            )

    def _record_activity(
        self,
        issue_id: str,
        bk_biz_id: int,
        tapd_info: dict,
    ) -> list:
        """记录 TAPD 创建活动日志并合并返回完整活动列表

        写入 ES 失败时重试一次，仍失败则仅记录日志，不将失败的活动拼入返回，
        避免返回无效的 activity_id。

        Args:
            issue_id: Issue ID
            bk_biz_id: 业务 ID
            tapd_info: TAPD 单据信息（序列化为 content）

        Returns:
            完整的活动日志列表（新活动在前，历史在后）
        """
        # 读取历史活动日志（先读后写，避免 ES 延迟）
        existing_activities = self._read_activities(issue_id)

        create_time = int(time.time())
        create_username = get_request_username()
        tapd_content = json.dumps(tapd_info, ensure_ascii=False)

        new_activity = IssueActivityDocument(
            issue_id=issue_id,
            bk_biz_id=bk_biz_id,
            activity_type=IssueActivityType.CREATE_TAPD,
            from_value=None,
            to_value=None,
            operator=create_username,
            content=tapd_content,
            time=create_time,
            create_time=create_time,
        )

        write_succeeded = False
        try:
            IssueActivityDocument.bulk_create([new_activity])
            write_succeeded = True
        except Exception as e:
            logger.warning(
                "IssueActivityDocument create_tapd activity write failed, retrying once, issue_id=%s: %s",
                issue_id,
                e,
            )
            try:
                IssueActivityDocument.bulk_create([new_activity])
                write_succeeded = True
            except Exception as e2:
                logger.error(
                    "IssueActivityDocument create_tapd activity write retry failed, issue_id=%s: %s",
                    issue_id,
                    e2,
                )

        if not write_succeeded:
            return existing_activities

        new_activity_item = {
            "bk_biz_id": new_activity.bk_biz_id,
            "activity_id": new_activity.id,
            "activity_type": new_activity.activity_type,
            "operator": new_activity.operator or "",
            "from_value": new_activity.from_value,
            "to_value": new_activity.to_value,
            "content": new_activity.content,
            "time": new_activity.time,
        }
        return [new_activity_item] + existing_activities

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        issue_id = validated_request_data["issue_id"]

        IssueDocument.get_issue_or_raise(issue_id, bk_biz_id=bk_biz_id)

        # 已被合并冻结的 Issue 禁止创建 TAPD（与状态机操作一致）
        IssueMergeResolver.assert_not_frozen(issue_id)

        tapd_type = validated_request_data["tapd_type"]
        workspace_id = validated_request_data["workspace_id"]
        name = validated_request_data["name"]
        description = validated_request_data["description"]
        owner = validated_request_data["owner"]
        sync_status = validated_request_data["sync_status"]
        priority_label = validated_request_data["priority_label"]
        iteration_id = validated_request_data["iteration_id"]
        te = validated_request_data.get("te", "")

        if sync_status:
            # TODO: [issue-tapd-sync] 实现 TAPD 单据状态同步功能
            logger.warning(
                "sync_status=True requested but not yet implemented, issue_id=%s, tapd_type=%s",
                issue_id,
                tapd_type,
            )

        # Step 1: 调用 TAPD API 创建单据
        tapd_info = self._create_tapd(
            tapd_type=tapd_type,
            workspace_id=workspace_id,
            name=name,
            description=description,
            owner=owner,
            priority_label=priority_label,
            iteration_id=iteration_id,
            te=te,
        )

        # 补充公共字段
        tapd_info.update(
            {
                "bk_biz_id": bk_biz_id,
                "issue_id": issue_id,
                "workspace_id": workspace_id,
                "sync_status": sync_status,
            }
        )

        # Step 2: 保存issue与tapd单据的关联记录
        self._save_relation(tapd_info=tapd_info)

        # Step 3: 记录活动日志并返回完整活动列表
        tapd_info["activities"] = self._record_activity(issue_id=issue_id, bk_biz_id=bk_biz_id, tapd_info=tapd_info)

        return tapd_info


class ListIssueTapdRelationsResource(Resource):
    """
    获取指定 Issue 关联的 TAPD 单据信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务 ID")
        issue_id = IssueIDField(label="Issue ID")

    def perform_request(self, validated_request_data: dict) -> list:
        bk_biz_id = validated_request_data["bk_biz_id"]
        issue_id = validated_request_data["issue_id"]

        # 校验 Issue 存在且归属当前业务
        IssueDocument.get_issue_or_raise(issue_id, bk_biz_id=bk_biz_id)

        # 查询关联关系
        relations = IssueTapdRelation.objects.filter(
            bk_biz_id=bk_biz_id,
            issue_id=issue_id,
        ).order_by("-create_time")

        # 构建 results
        results = []
        for obj in relations:
            results.append(
                {
                    "relation_id": obj.id,
                    "bk_biz_id": obj.bk_biz_id,
                    "issue_id": obj.issue_id,
                    "workspace_id": obj.workspace_id,
                    "tapd_id": obj.tapd_id,
                    "tapd_type": obj.tapd_type,
                    "tapd_title": obj.tapd_title,
                    "link_mode": obj.link_mode,
                    "sync_status": obj.sync_status,
                }
            )

        return results


class LinkIssueToTapdResource(Resource):
    """
    将指定 Issue 与一个或多个 TAPD 单据建立关联关系
    """

    class RequestSerializer(serializers.Serializer):
        class TapdItem(serializers.Serializer):
            tapd_id = serializers.CharField(label="TAPD 单据 ID")
            tapd_type = serializers.ChoiceField(label="TAPD 单据类型", choices=["story", "bug"])
            tapd_title = serializers.CharField(label="TAPD 单据标题")

        bk_biz_id = serializers.IntegerField(label="业务 ID")
        issue_id = IssueIDField(label="Issue ID")
        workspace_id = serializers.IntegerField(label="TAPD 项目 ID")
        tapd_items = serializers.ListField(
            label="TAPD 单据列表",
            child=TapdItem(),
            min_length=1,
            max_length=200,
        )
        sync_status = serializers.BooleanField(
            label="是否同步单据状态",
            help_text="勾选后，TAPD单据完成时自动同步状态到Issue",
        )

        def validate(self, attrs):
            if attrs.get("sync_status"):
                raise serializers.ValidationError("sync_status is not supported until TAPD status sync is implemented")

            seen_tapd_ids = set()
            for item in attrs.get("tapd_items", []):
                tapd_id = item["tapd_id"]
                if tapd_id in seen_tapd_ids:
                    raise serializers.ValidationError(f"duplicate TAPD ID: {tapd_id}")
                seen_tapd_ids.add(tapd_id)
            return attrs

    @staticmethod
    def _validate_workspace_binding(bk_biz_id: int, workspace_id: int) -> None:
        """校验当前业务空间已绑定 TAPD 项目。"""
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        tenant_id = space_uid_to_bk_tenant_id(space_uid)
        if not TapdWorkspaceBinding.objects.filter(
            bk_tenant_id=tenant_id,
            space_uid=space_uid,
            tapd_workspace_id=str(workspace_id),
        ).exists():
            raise serializers.ValidationError(f"TAPD 项目 {workspace_id} 未与当前业务关联")

    @staticmethod
    def _validate_tapd_items(workspace_id: int, tapd_items: list[dict]) -> list[dict]:
        """校验 TAPD 单据真实存在且归属于指定项目，并用 TAPD 返回标题覆盖前端传值。"""
        items_by_type: dict[str, dict[str, dict]] = {}
        for item in tapd_items:
            items_by_type.setdefault(item["tapd_type"], {})[str(item["tapd_id"])] = item

        for tapd_type, items_by_id in items_by_type.items():
            expected_ids = list(items_by_id.keys())
            queried_items = SearchTAPDItemsResource._query_tapd_items(
                tapd_type=tapd_type,
                workspace_id=workspace_id,
                id=",".join(expected_ids),
                limit=len(expected_ids),
                page=1,
                order="created desc",
                fields="id,name",
            )
            queried_items_by_id = {str(item.get("id")): item for item in queried_items}
            missing_ids = sorted(set(expected_ids) - set(queried_items_by_id.keys()))
            if missing_ids:
                raise serializers.ValidationError(
                    f"TAPD 单据不存在或不属于项目 {workspace_id}: {', '.join(missing_ids)}"
                )

            for tapd_id, item in items_by_id.items():
                item["tapd_title"] = queried_items_by_id[tapd_id].get("name") or item.get("tapd_title", "")

        return tapd_items

    @staticmethod
    def _bulk_check_existing(
        bk_biz_id: int,
        issue_id: str,
        workspace_id: int,
        tapd_ids: list[str],
    ) -> dict[tuple[int, int, str, str], IssueTapdRelation]:
        """批量查重：返回已关联的记录 {(bk_biz_id, issue_id, workspace_id, tapd_id): IssueTapdRelation}"""
        existing = IssueTapdRelation.objects.filter(
            bk_biz_id=bk_biz_id,
            issue_id=issue_id,
            workspace_id=workspace_id,
            tapd_id__in=tapd_ids,
        )
        return {(obj.bk_biz_id, obj.issue_id, obj.workspace_id, obj.tapd_id): obj for obj in existing}

    @staticmethod
    def _bulk_create_relations(
        bk_biz_id: int,
        issue_id: str,
        workspace_id: int,
        sync_status: bool,
        to_create: list[dict],
    ) -> list[IssueTapdRelation]:
        """批量创建关联记录

        注意：MySQL 下 bulk_create 返回的对象不会填充 PK，因此需要重新查询。
        """
        objs = [
            IssueTapdRelation(
                bk_biz_id=bk_biz_id,
                issue_id=issue_id,
                workspace_id=workspace_id,
                tapd_id=item["tapd_id"],
                tapd_type=item["tapd_type"],
                tapd_title=item.get("tapd_title", ""),
                link_mode="link",
                sync_status=sync_status,
            )
            for item in to_create
        ]
        IssueTapdRelation.objects.bulk_create(objs)
        # MySQL 下 bulk_create 返回的对象不会填充 PK，需要重新查询
        return IssueTapdRelation.objects.filter(
            bk_biz_id=bk_biz_id,
            issue_id=issue_id,
            workspace_id=workspace_id,
            tapd_id__in=[item["tapd_id"] for item in to_create],
        )

    @staticmethod
    def _record_link_activities(
        issue_id: str,
        bk_biz_id: int,
        workspace_id: int,
        items: list[dict],
    ) -> list[dict]:
        """记录关联活动日志并返回完整活动列表

        Args:
            issue_id: Issue ID
            bk_biz_id: 业务 ID
            workspace_id: TAPD 项目 ID
            items: 需要记录活动的关联项列表

        Returns:
            完整的活动日志列表（新活动在前，历史在后）
        """
        # 读取历史活动日志
        try:
            search = (
                IssueActivityDocument.search(all_indices=True)
                .filter("term", issue_id=issue_id)
                .sort("-time")
                .extra(size=500)
            )
            existing_activities = [
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
                for hit in search.execute().hits
            ]
        except Exception:
            logger.exception("Failed to read activities, issue_id=%s", issue_id)
            existing_activities = []

        if not items:
            return existing_activities

        # 批量写入活动日志
        create_time = int(time.time())
        create_username = get_request_username()
        new_activities = []
        for item in items:
            tapd_content = json.dumps(
                {
                    "tapd_id": item["tapd_id"],
                    "tapd_type": item["tapd_type"],
                    "tapd_title": item.get("tapd_title", ""),
                    "workspace_id": workspace_id,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            new_activities.append(
                IssueActivityDocument(
                    issue_id=issue_id,
                    bk_biz_id=bk_biz_id,
                    activity_type=IssueActivityType.TAPD_LINK,
                    from_value=None,
                    to_value=str(item["tapd_id"]),
                    operator=create_username,
                    content=tapd_content,
                    time=create_time,
                    create_time=create_time,
                )
            )

        try:
            IssueActivityDocument.bulk_create(new_activities)
        except Exception as e:
            logger.warning(
                "IssueActivityDocument tapd_link activity write failed, retrying once, issue_id=%s: %s",
                issue_id,
                e,
            )
            try:
                IssueActivityDocument.bulk_create(new_activities)
            except Exception as e2:
                logger.error(
                    "IssueActivityDocument tapd_link activity write retry failed, issue_id=%s: %s",
                    issue_id,
                    e2,
                )
                return existing_activities

        # 拼装新活动
        new_activity_items = [
            {
                "bk_biz_id": act.bk_biz_id,
                "activity_id": act.id,
                "activity_type": act.activity_type,
                "operator": act.operator or "",
                "from_value": act.from_value,
                "to_value": act.to_value,
                "content": act.content,
                "time": act.time,
            }
            for act in new_activities
        ]
        return new_activity_items + existing_activities

    def perform_request(self, validated_request_data: dict) -> dict:
        bk_biz_id = validated_request_data["bk_biz_id"]
        issue_id = validated_request_data["issue_id"]
        workspace_id = validated_request_data["workspace_id"]
        sync_status = validated_request_data["sync_status"]
        tapd_items = validated_request_data["tapd_items"]

        # 校验 Issue 存在且归属当前业务
        IssueDocument.get_issue_or_raise(issue_id, bk_biz_id=bk_biz_id)
        # 已被合并冻结的 Issue 禁止关联 TAPD
        IssueMergeResolver.assert_not_frozen(issue_id)
        # 校验 TAPD 项目已绑定当前业务空间
        self._validate_workspace_binding(bk_biz_id, workspace_id)
        # 校验 TAPD 单据存在且归属于当前项目
        tapd_items = self._validate_tapd_items(workspace_id, tapd_items)

        # 提取 tapd_id 列表用于批量查重
        tapd_ids = [item["tapd_id"] for item in tapd_items]
        # 批量查重：当前 issue 已关联的记录
        existing_map = self._bulk_check_existing(bk_biz_id, issue_id, workspace_id, tapd_ids)
        # 分离需要新建的关联项
        to_create = [
            item for item in tapd_items if (bk_biz_id, issue_id, workspace_id, item["tapd_id"]) not in existing_map
        ]

        # 批量创建关联记录
        created_objs = []
        if to_create:
            created_objs = self._bulk_create_relations(
                bk_biz_id=bk_biz_id,
                issue_id=issue_id,
                workspace_id=workspace_id,
                sync_status=sync_status,
                to_create=to_create,
            )

        # 更新已存在关联的 sync_status
        if existing_map:
            to_update = []
            for _, obj in existing_map.items():
                if obj.sync_status != sync_status:
                    obj.sync_status = sync_status
                    to_update.append(obj)
            if to_update:
                IssueTapdRelation.objects.bulk_update(to_update, ["sync_status"])

        # 构建 results（包含所有关联项，已存在 + 新建）
        results = []
        # 新建的关联项
        for obj in created_objs:
            results.append(
                {
                    "relation_id": obj.id,
                    "bk_biz_id": obj.bk_biz_id,
                    "issue_id": obj.issue_id,
                    "workspace_id": obj.workspace_id,
                    "tapd_id": obj.tapd_id,
                    "tapd_type": obj.tapd_type,
                    "tapd_title": obj.tapd_title,
                    "sync_status": obj.sync_status,
                }
            )
        # 已存在的关联项
        for _, obj in existing_map.items():
            results.append(
                {
                    "relation_id": obj.id,
                    "bk_biz_id": obj.bk_biz_id,
                    "issue_id": obj.issue_id,
                    "workspace_id": obj.workspace_id,
                    "tapd_id": obj.tapd_id,
                    "tapd_type": obj.tapd_type,
                    "tapd_title": obj.tapd_title,
                    "sync_status": obj.sync_status,
                }
            )

        # 记录活动日志
        activities = self._record_link_activities(
            issue_id=issue_id,
            bk_biz_id=bk_biz_id,
            workspace_id=workspace_id,
            items=to_create,
        )

        return {
            "results": results,
            "activities": activities,
        }


class ListUserTapdWorkspaceResource(Resource):
    """查询当前用户有权限的 TAPD 项目列表（冷启动去关联用）

    端点：POST /fta/issue/tapd/user_workspace/
    Body: { bk_biz_id, success_url, error_url }
    数据源：TAPD 用户态 API（Bearer Token，从 Redis 解密获取）。

    success_url: 成功/失败回调后 302 重定向的前端页面地址（含 #）。
    error_url: 授权失败时重定向的前端错误页面地址（含 #）。
        若未传则回退到 success_url（同一页面，前端根据 URL 参数区分成功/失败）。

    四态判定（以用户级已授权项目为基准全集，项目级×本地为二维标记）：
    - bound      用户级✓ + 项目级✓ + 本地✓
    - importable 用户级✓ + 项目级✓ + 本地✗（静默尝试建 binding，成功转 bound）
    - stale      用户级✓ + 项目级✗ + 本地✓
    - unbound    用户级✓ + 项目级✗ + 本地✗

    注：用户级无权限但本地有 binding 的项目不展示（用户已无权限，不应再操作）。
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="蓝鲸业务ID")
        success_url = serializers.CharField(label="成功回调重定向地址（含#）", max_length=512)
        error_url = serializers.CharField(label="失败回调重定向地址（含#）", max_length=512, required=False)

    def perform_request(self, validated_request_data: dict) -> dict:
        bk_biz_id = validated_request_data["bk_biz_id"]
        success_url = validated_request_data["success_url"]
        # 未传 error_url 时回退到 success_url
        error_url = validated_request_data.get("error_url") or success_url

        # URL 补全：前端可传路径或全 URL，路径自动补 / 前缀和域名
        request = get_request()
        success_url = normalize_redirect_url(success_url, request)
        error_url = normalize_redirect_url(error_url, request)

        space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        tenant_id = space_uid_to_bk_tenant_id(space_uid)
        username = get_request_username()

        # 查本地 binding（用于四态标记的【本地存在】侧）
        local_bindings = {
            str(b["tapd_workspace_id"]): b
            for b in TapdWorkspaceBinding.objects.filter(bk_tenant_id=tenant_id, space_uid=space_uid).values(
                "tapd_workspace_id", "tapd_workspace_name", "create_user"
            )
        }

        token_payload = get_tapd_token(bk_tenant_id=tenant_id, username=username)
        access_token = token_payload.get("access_token", "")

        # 1. 获取用户级已授权 workspace_id 列表（Bearer Token）
        #    无 token / token 失效 → raise 403 + auth_url 引导重新授权
        user_workspace_ids = self._fetch_user_workspace_ids(
            tenant_id, username, bk_biz_id, success_url, error_url, access_token
        )

        # 2. 并发查详情拿 workspace_name（复用 ListTapdWorkspaceResource 模式）
        workspace_details = self._enrich_workspace_details(user_workspace_ids, access_token)

        # 3. 五态标记（项目级×本地 二维判定 + tombstone 检查）
        app_granted_ids = self._fetch_app_granted_ids(bk_biz_id)
        # 批量查询 tombstone，避免 N+1（§ 2.8 非功能性需求）
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        tombstone_ids = set(
            TapdWorkspaceManualUnbind.objects.filter(bk_tenant_id=tenant_id, space_uid=space_uid).values_list(
                "tapd_workspace_id", flat=True
            )
        )
        items, any_unbound_or_stale = self._mark_bind_status(
            workspace_details, app_granted_ids, local_bindings, bk_biz_id, tenant_id, username, tombstone_ids
        )

        # install_url 仅在存在 unbound 或 stale 时按需构建（涉及签名生成，避免无用开销）
        install_url = ""
        if any_unbound_or_stale:
            request = get_request()
            backend_callback = request.build_absolute_uri(reverse("fta_web:tapd_app_install_callback"))
            install_url = generate_install_url(
                bk_biz_id=bk_biz_id,
                bk_tenant_id=tenant_id,
                space_uid=space_uid,
                initiator=username,
                success_url=success_url,
                error_url=error_url,
                backend_callback=backend_callback,
            )

        return {
            "total": len(items),
            "items": items,
            "install_url": install_url,
            "method": "GET",
        }

    @classmethod
    def _is_tapd_token_invalid_422(cls, error: BKAPIError) -> bool:
        """判断 BKAPIError 是否为 TAPD access_token 无效/过期导致的 422 错误。

        TAPD 返回 HTTP 422 时，APIResource.raise_for_status 先抛 HTTPError → BKAPIError，
        此时 e.data 可能是 response.content 字符串（非 dict），e.message 含 "422"。
        """
        error_code = ""
        if isinstance(error.data, dict):
            error_code = str(error.data.get("code", ""))
        elif isinstance(error.data, str) and "422" in error.data:
            error_code = "422"
        return error_code == "422" or "422" in str(error.message)

    @classmethod
    def _raise_reauth_required(
        cls, bk_biz_id: int, tenant_id: str, username: str, success_url: str, error_url: str
    ) -> None:
        """构造 403 + auth_url 响应，引导前端跳转 TAPD 用户态授权页。
        与 view 层 TAPDAuthPermission 同模式（views.py:126-142）。
        """
        req = get_request()
        oauth_callback = req.build_absolute_uri(reverse("fta_web:tapd_user_oauth_callback"))
        auth_url = generate_auth_url(
            bk_biz_id=bk_biz_id,
            bk_tenant_id=tenant_id,
            initiator=username,
            success_url=success_url,
            error_url=error_url,
            backend_callback=oauth_callback,
        )
        exc = CustomException(
            message="TAPD 用户态授权未生效",
            data={"auth_url": auth_url},
            code=403,
        )
        exc.status_code = 200
        raise exc

    def _fetch_user_workspace_ids(
        self,
        tenant_id: str,
        username: str,
        bk_biz_id: int,
        success_url: str,
        error_url: str,
        access_token: str,
    ) -> list[str]:
        """获取用户级已授权的 workspace_id 列表（Bearer Token）。

        无 token → raise 403；token 失效（422）→ 清理 token + raise 403。
        :return: ws_ids 列表
        """
        if not access_token:
            self._raise_reauth_required(bk_biz_id, tenant_id, username, success_url, error_url)

        try:
            user_granted_resp = api.tapd.get_granted_workspaces(access_token=access_token)
        except BKAPIError as e:
            # 422 = access_token 无效/过期，清理失效 token，统一转 403 + auth_url 引导重新授权
            if self._is_tapd_token_invalid_422(e):
                logger.info("TAPD user token invalid (422), clearing token for reauth: %s", e)
                delete_tapd_token(tenant_id=tenant_id, username=username)
                self._raise_reauth_required(bk_biz_id, tenant_id, username, success_url, error_url)
            # 其他 API 错误直接抛出
            raise

        user_granted_list = (
            user_granted_resp.get("list", []) if isinstance(user_granted_resp, dict) else (user_granted_resp or [])
        )
        # 提取 workspace_id 列表（OpenOrganizationApp 内层不含 name，名称由 _enrich 补全）
        ws_ids = []
        for ws in user_granted_list:
            ws_inner = ws.get("OpenOrganizationApp", {}) if isinstance(ws, dict) else {}
            ws_id = str(ws_inner.get("workspace_id", ""))
            if ws_id:
                ws_ids.append(ws_id)
        return ws_ids

    @classmethod
    def _enrich_workspace_details(cls, workspace_ids: list[str], access_token: str) -> list[dict]:
        """并发查 workspace 详情拿 name（复用 bulk_request 框架）。

        :param workspace_ids: workspace_id 字符串列表
        :param access_token: 用户态 access_token（Bearer Token 认证）
        :return: [{workspace_id, workspace_name}, ...]，顺序与入参一致；失败的兜底为 ws_id
        """
        if not workspace_ids:
            return []

        params = [{"workspace_id": int(ws_id), "access_token": access_token} for ws_id in workspace_ids]
        # ignore_exceptions=True：单个失败返回 None，不中断整体
        raw_results = api.tapd.get_workspace_info.bulk_request(params, ignore_exceptions=True)

        details = []
        for ws_id, raw in zip(workspace_ids, raw_results):
            if raw and isinstance(raw, dict) and "Workspace" in raw:
                ws_info = raw["Workspace"]
                details.append(
                    {
                        "workspace_id": str(ws_info["id"]),
                        "workspace_name": ws_info["name"],
                        "pretty_name": ws_info.get("pretty_name", ""),
                        "category": ws_info.get("category", ""),
                        "status": ws_info.get("status", ""),
                        "description": ws_info.get("description", ""),
                        "creator": ws_info.get("creator", ""),
                        "created": ws_info.get("created", ""),
                    }
                )
            else:
                # 查询失败兜底
                logger.warning("获取TAPD workspace信息失败, workspace_id=%s", ws_id)
                details.append(
                    {
                        "workspace_id": str(ws_id),
                        "workspace_name": str(ws_id),
                        "pretty_name": "",
                        "category": "",
                        "status": "",
                        "description": "",
                        "creator": "",
                        "created": "",
                    }
                )
        return details

    @classmethod
    def _fetch_app_granted_ids(cls, bk_biz_id: int) -> set[str]:
        """获取项目级（应用级，Basic Auth）已授权的 workspace_id 集合。"""
        try:
            app_granted_resp = api.tapd.get_granted_workspaces(bk_biz_id=bk_biz_id)
        except Exception as e:
            logger.warning("GetGrantedWorkspaces failed for B-01: %s", e)
            app_granted_resp = {}

        app_granted_list = (
            app_granted_resp.get("list", []) if isinstance(app_granted_resp, dict) else (app_granted_resp or [])
        )
        app_granted_ids = set()
        for ws in app_granted_list:
            ws_inner = ws.get("OpenOrganizationApp", {}) if isinstance(ws, dict) else {}
            ws_id = str(ws_inner.get("workspace_id", ""))
            if ws_id:
                app_granted_ids.add(ws_id)
        return app_granted_ids

    @classmethod
    def _mark_bind_status(
        cls,
        workspace_details: list[dict],
        app_granted_ids: set[str],
        local_bindings: dict[str, dict],
        bk_biz_id: int,
        tenant_id: str,
        username: str,
        tombstone_ids: set[str],
    ) -> tuple[list[dict], bool]:
        """五态标记：以用户级为基准全集，按 项目级×本地 二维判定。

        新增状态 manually_unbound：当项目是 importable（in_app && !in_local）
        但 tombstone（手动解绑记录）存在时，标记为此状态。

        :param tombstone_ids: 当前业务空间下已手动解绑的 workspace_id 集合（避免 N+1 查询）
        :return: (items, any_unbound_or_stale)
        """
        items = []
        any_unbound_or_stale = False

        for ws in workspace_details:
            ws_id = ws["workspace_id"]
            workspace_name = ws["workspace_name"]
            in_app = ws_id in app_granted_ids
            in_local = ws_id in local_bindings

            if in_app and in_local:
                status = TapdWorkspaceBindStatus.BOUND
            elif in_app and not in_local:
                # 五态判定：importable 状态增加 tombstone 检查，若存在则标记为 manually_unbound
                # 🔒 约束：batch tombstone 查询已在 loop 外完成（避免 N+1）
                if tombstone_ids and ws_id in tombstone_ids:
                    status = TapdWorkspaceBindStatus.MANUALLY_UNBOUND
                else:
                    status = TapdWorkspaceBindStatus.IMPORTABLE
                    if try_bind_importable(ws_id, bk_biz_id, tenant_id, username, tapd_workspace_name=workspace_name):
                        status = TapdWorkspaceBindStatus.BOUND
            elif not in_app and in_local:
                status = TapdWorkspaceBindStatus.STALE
                any_unbound_or_stale = True
            else:  # not in_app and not in_local
                status = TapdWorkspaceBindStatus.UNBOUND
                any_unbound_or_stale = True

            # 名称优先用本地 binding（可能用户改过名），其次详情 API 返回值
            final_name = local_bindings.get(ws_id, {}).get("tapd_workspace_name") or workspace_name
            items.append({"workspace_id": ws_id, "workspace_name": final_name, "is_bound": status})

        return items, any_unbound_or_stale


class UnbindTapdWorkspaceResource(Resource):
    """解除 TAPD 项目与当前业务的关联

    仅删除本地 TapdWorkspaceBinding，不在 TAPD 侧撤回应用授权。
    端点：POST /fta/issue/tapd/unbind_workspace
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="蓝鲸业务ID", required=True)
        workspace_id = serializers.CharField(label="TAPD项目ID", required=True)

    def perform_request(self, validated_request_data: dict) -> dict:
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        workspace_id: str = validated_request_data["workspace_id"]
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        tenant_id = space_uid_to_bk_tenant_id(space_uid)

        binding_qs = TapdWorkspaceBinding.objects.filter(
            bk_tenant_id=tenant_id,
            space_uid=space_uid,
            tapd_workspace_id=workspace_id,
        )
        if not binding_qs.exists():
            raise HTTP404Error(
                message=f"TAPD 项目 {workspace_id} 未与当前业务关联",
            )

        # 写入 tombstone + 删除 binding，放在同一事务中保证一致性（避免 tombstone 已写但 binding 删除失败）
        with transaction.atomic():
            TapdWorkspaceManualUnbind.objects.get_or_create(
                bk_tenant_id=tenant_id,
                space_uid=space_uid,
                tapd_workspace_id=workspace_id,
                defaults={"bk_biz_id": bk_biz_id},
            )
            # 删除 binding（不存在时 delete() 返回 (0, {})）
            deleted_count, _ = binding_qs.delete()
        logger.info(
            "UnbindTapdWorkspace: tombstone created + binding deleted biz=%s ws=%s tenant=%s count=%s",
            bk_biz_id,
            workspace_id,
            tenant_id,
            deleted_count,
        )

        return {"success": True}


class RebindTapdWorkspaceResource(Resource):
    """重新关联 TAPD 项目与当前业务

    删除 tombstone 记录后，创建本地 TapdWorkspaceBinding。
    重新获取项目信息（Basic Auth）以填充 workspace_name。
    端点：POST /fta/issue/tapd/rebind_workspace
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="蓝鲸业务ID", required=True)
        workspace_id = serializers.CharField(label="TAPD项目ID", required=True)

    def perform_request(self, validated_request_data: dict) -> dict:
        bk_biz_id = validated_request_data["bk_biz_id"]
        workspace_id = validated_request_data["workspace_id"]
        username = get_request_username()
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        tenant_id = space_uid_to_bk_tenant_id(space_uid)

        # 1. 验重：若 binding 已存在，无需重新关联
        try:
            existing = TapdWorkspaceBinding.objects.get(
                bk_tenant_id=tenant_id, space_uid=space_uid, tapd_workspace_id=workspace_id
            )
            # 兜底：清理可能残留的 tombstone（并发/脏数据场景）
            TapdWorkspaceManualUnbind.objects.filter(
                bk_tenant_id=tenant_id, space_uid=space_uid, tapd_workspace_id=workspace_id
            ).delete()
            return {"success": True, "workspace": {"id": workspace_id, "name": existing.tapd_workspace_name}}
        except TapdWorkspaceBinding.DoesNotExist:
            pass

        # 2. 校验用户态 token 存在并可用（重新关联需用户明确授权）
        # 授权失效时返回 403（HTTP 状态码 200），前端按 code=403 自行跳转授权流程，无需 auth_url
        user_token = get_tapd_token(tenant_id, username)
        if not user_token.get("access_token"):
            exc = CustomException(message="TAPD 用户态授权已失效或未授权，请先完成授权", code=403)
            exc.status_code = 200
            raise exc

        # 3. 校验当前用户是否仍有权访问该 workspace（用户态鉴权有效性检查）
        try:
            ws_info = api.tapd.get_workspace_info(
                workspace_id=workspace_id,
                access_token=user_token["access_token"],
            )["Workspace"]
            workspace_name = ws_info.get("name", "")
        except BKAPIError as e:
            if ListUserTapdWorkspaceResource._is_tapd_token_invalid_422(e):
                logger.info("TAPD user token invalid (422) during rebind, clearing token: ws=%s", workspace_id)
                delete_tapd_token(tenant_id=tenant_id, username=username)
                # token 失效，返回 403（HTTP 状态码 200），前端按 code=403 自行跳转授权流程
                exc = CustomException(message="TAPD 用户态授权已失效（422），请重新完成授权", code=403)
                exc.status_code = 200
                raise exc
            raise

        # 4. 删除 tombstone + 创建 binding，事务包裹保证原子性
        with transaction.atomic():
            TapdWorkspaceManualUnbind.objects.filter(
                bk_tenant_id=tenant_id, space_uid=space_uid, tapd_workspace_id=workspace_id
            ).delete()
            binding, _ = TapdWorkspaceBinding.objects.get_or_create(
                bk_tenant_id=tenant_id,
                space_uid=space_uid,
                tapd_workspace_id=workspace_id,
                defaults={
                    "bk_biz_id": bk_biz_id,
                    "tapd_workspace_name": workspace_name,
                    "create_user": username,
                    "update_user": username,
                },
            )

        return {"success": True, "workspace": {"id": workspace_id, "name": binding.tapd_workspace_name}}


class RevokeTapdUserAuthResource(Resource):
    """撤销 TAPD 用户态授权

    仅清除用户级用户态 token（Redis），不清除 TapdWorkspaceBinding。
    前端重新授权即可恢复。
    端点：POST /fta/issue/tapd/revoke_auth
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="蓝鲸业务ID", required=True)

    def perform_request(self, validated_request_data: dict) -> dict:
        # 1. 获取当前用户和租户
        username = get_request_username()
        tenant_id = bk_biz_id_to_bk_tenant_id(validated_request_data["bk_biz_id"])

        # 2. 删除用户态 token（Redis）
        delete_tapd_token(tenant_id, username)

        logger.info("RevokeTapdUserAuth: token deleted tenant=%s user=%s", tenant_id, username)

        return {"success": True, "message": "授权已撤销"}


@api_view(["GET"])
@csrf_exempt
def tapd_app_install_callback(request):
    """TAPD `open_app_install` 回调 — 应用态授权。

    Query params: code, resource, signed_state
    1. 解析 signed_state → 验签、验过期
    2. 提取 workspace_id → 调 app 级 Basic Auth 获取 name
    3. upsert TapdWorkspaceBinding（create_user = initiator）
    4. 302 重定向前端 success / 失败重定向 error_url
    """
    signed_state = request.query_params.get("signed_state", "")
    if not signed_state:
        # signed_state 缺失时无法获取前端地址，回退到根路径
        return HttpResponseRedirect(request.build_absolute_uri("/"))

    # 1) 解析并验签 signed_state
    try:
        payload = verify_signed_state(signed_state)
    except exceptions.ValidationError as e:
        logger.warning("signed_state verification failed: %s", e.detail)
        return HttpResponseRedirect(request.build_absolute_uri("/"))

    bk_biz_id = payload["bk_biz_id"]
    tenant_id = payload["bk_tenant_id"]
    space_uid = payload["space_uid"]
    initiator = payload["initiator"]
    success_url = payload["success_url"]
    error_url = payload["error_url"]

    # 安全性由 verify_signed_state 保证：HMAC 签名 + 过期时间校验
    # 解码 resource JSON 获取 workspace_id
    resource_json = request.query_params.get("resource", "{}")
    try:
        resource = json.loads(resource_json) if resource_json else {}
    except Exception:
        safe_resource_json = resource_json.replace("\r", "").replace("\n", "")
        logger.warning("invalid resource JSON: %s", safe_resource_json)
        return HttpResponseRedirect(error_url)

    if not isinstance(resource, dict):
        logger.warning("invalid resource JSON object")
        return HttpResponseRedirect(error_url)

    raw_workspace_id = resource.get("workspace_id", "")
    try:
        workspace_id = str(int(raw_workspace_id))
    except (TypeError, ValueError):
        logger.warning("invalid workspace_id: %s", _sanitize_for_log(raw_workspace_id))
        return HttpResponseRedirect(error_url)

    # 2) 获取项目信息（app 级 Basic Auth）
    try:
        info = api.tapd.get_workspace_info(workspace_id=int(workspace_id))
        ws = info.get("Workspace", {})
        ws_name = ws.get("name") or ws.get("pretty_name") or str(workspace_id)
    except BKAPIError:
        logger.exception("get_workspace_info failed: ws=%s", _sanitize_for_log(workspace_id))
        return HttpResponseRedirect(error_url)
    except Exception as e:
        logger.exception(f"get_workspace_info unexpected error: ws=%s,{e}", workspace_id)
        return HttpResponseRedirect(error_url)

    # 3) upsert binding（set_local_username 确保 AbstractRecordModel.save() 审计字段正确）
    set_local_username(initiator)
    TapdWorkspaceBinding.objects.update_or_create(
        bk_tenant_id=tenant_id,
        space_uid=space_uid,
        tapd_workspace_id=workspace_id,
        defaults={
            "bk_biz_id": bk_biz_id,
            "tapd_workspace_name": ws_name,
            "create_user": initiator,
            "update_user": initiator,
        },
    )
    logger.info(
        "TapdWorkspaceBinding upserted: tenant=%s space=%s ws=%s name=%s initiator=%s",
        tenant_id,
        space_uid,
        workspace_id,
        ws_name,
        initiator,
    )

    return HttpResponseRedirect(success_url)


@api_view(["GET"])
@csrf_exempt
def tapd_user_oauth_callback(request):
    """TAPD 用户态 OAuth 回调。

    Query params: code, state（signed_state）
    1. state 为自包含 signed_state → 验签、验过期（不依赖 session）
    2. 用 code 换取 access_token（UserOauthTokenResource），redirect_uri 取 payload 中的 backend_callback
    3. 加密 token → 存入 Redis（TTL = expires_in），key = tapd_uat:{tenant}:{user}
    4. 302 重定向前端 success_url
    """
    code = request.query_params.get("code", "")
    state = request.query_params.get("state", "")

    if not code or not state:
        # 缺少必要参数，回退到根路径
        return HttpResponseRedirect(request.build_absolute_uri("/"))

    # 1) 解析并验签 signed_state（自包含 payload，不依赖 session）
    try:
        payload = verify_signed_state(state)
    except exceptions.ValidationError as e:
        logger.warning("signed_state verification failed: %s", e.detail)
        return HttpResponseRedirect(request.build_absolute_uri("/"))

    bk_biz_id = payload["bk_biz_id"]
    tenant_id = payload["bk_tenant_id"]
    username = payload["initiator"]
    success_url = payload.get("success_url", "")
    error_url = payload.get("error_url") or success_url or request.build_absolute_uri("/")

    # 校验失败统一处理：记日志 + 重定向到 error_url
    def _fail(log_msg, *args):
        logger.warning(log_msg, *args)
        return HttpResponseRedirect(error_url)

    # 2) 校验 username + backend_callback
    if not username:
        return _fail("missing initiator in signed_state payload, bk_biz_id=%s", bk_biz_id)

    callback_username = get_request_username()
    if not callback_username or callback_username != username:
        return _fail(
            "TAPD user oauth callback user mismatch, bk_biz_id=%s, initiator=%s, callback_user=%s",
            bk_biz_id,
            username,
            callback_username,
        )

    backend_callback = payload.get("backend_callback", "")
    if not backend_callback:
        return _fail("missing backend_callback in signed_state payload, bk_biz_id=%s", bk_biz_id)

    # 3) code 换 token（Basic Auth，client_id:client_secret）
    # redirect_uri 必须和 authorize 时传给 TAPD 的一致（即 backend_callback）
    try:
        token_resp = api.tapd.user_oauth_token(
            code=code,
            redirect_uri=backend_callback.rstrip("/"),
        )
    except BKAPIError:
        logger.exception("exchange token failed")
        return HttpResponseRedirect(error_url)
    except Exception:
        logger.exception("exchange token unexpected error")
        return HttpResponseRedirect(error_url)

    access_token = token_resp.get("access_token", "")
    expires_in = token_resp.get("expires_in", 7200)
    if not access_token:
        return _fail("empty access_token from TAPD")

    # 4) 存 Redis（AESCipher 加密），key 按 (tenant, username)
    save_tapd_token(
        tenant_id=tenant_id,
        username=username,
        token_data=token_resp,
        expires_in=expires_in,
    )

    # 5) 302 重定向到 success_url（含 # 的前端地址）
    return HttpResponseRedirect(success_url)
