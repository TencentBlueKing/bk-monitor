"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from django.db import router, transaction
from django.utils import timezone
from rest_framework import serializers

from constants.issue import IssueActivityType, IssuePriority, IssueStatus
from core.drf_resource import Resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from bkmonitor.documents.issue import (
    IssueActivityDocument,
    IssueActivityNotFoundError,
    IssueDocument,
    IssueNameDuplicatedError,
)
from bkmonitor.issue_merge import (
    MergeConflictError,
    MergeCrossBizForbiddenError,
    MergeIssuesNotFoundError,
    MergeMemberIsAnotherMainError,
    MergeTargetIsMemberError,
    SplitNotFoundError,
)
from bkmonitor.models.issue import IssueMergeRelation
from fta_web.issue.resources import IssueIDField

logger = logging.getLogger("root")


class AssignResource(Resource):
    """指派/改派 Issue 负责人"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        assignee = serializers.ListField(label="负责人列表", child=serializers.CharField(min_length=1), min_length=1)
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        issue = IssueDocument.get_issue_or_raise(
            validated_request_data["issue_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        assignee = validated_request_data["assignee"]
        operator = validated_request_data["operator"]
        if issue.status == IssueStatus.PENDING_REVIEW:
            activities = issue.assign(assignees=assignee, operator=operator)
        else:
            activities = issue.reassign(assignees=assignee, operator=operator)
        return {
            "bk_biz_id": issue.bk_biz_id,
            "issue_id": issue.id,
            "status": issue.status,
            "assignee": list(issue.assignee or []),
            "update_time": issue.update_time,
            "activities": activities or [],
        }


class ResolveResource(Resource):
    """标记 Issue 为已解决"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        issue = IssueDocument.get_issue_or_raise(
            validated_request_data["issue_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        activities = issue.resolve(operator=validated_request_data["operator"])
        return {
            "bk_biz_id": issue.bk_biz_id,
            "issue_id": issue.id,
            "status": issue.status,
            "resolved_time": issue.resolved_time,
            "update_time": issue.update_time,
            "activities": activities or [],
        }


class ArchiveResource(Resource):
    """归档 Issue"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        issue = IssueDocument.get_issue_or_raise(
            validated_request_data["issue_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        activities = issue.archive(operator=validated_request_data["operator"])
        return {
            "bk_biz_id": issue.bk_biz_id,
            "issue_id": issue.id,
            "status": issue.status,
            "update_time": issue.update_time,
            "activities": activities or [],
        }


class ReopenResource(Resource):
    """重新打开 Issue"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        issue = IssueDocument.get_issue_or_raise(
            validated_request_data["issue_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        activities = issue.reopen(operator=validated_request_data["operator"])
        return {
            "bk_biz_id": issue.bk_biz_id,
            "issue_id": issue.id,
            "status": issue.status,
            "update_time": issue.update_time,
            "activities": activities or [],
        }


class RestoreResource(Resource):
    """恢复归档 Issue"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        issue = IssueDocument.get_issue_or_raise(
            validated_request_data["issue_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        activities = issue.restore(operator=validated_request_data["operator"])
        return {
            "bk_biz_id": issue.bk_biz_id,
            "issue_id": issue.id,
            "status": issue.status,
            "update_time": issue.update_time,
            "activities": activities or [],
        }


class UpdatePriorityResource(Resource):
    """修改 Issue 优先级"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        priority = serializers.ChoiceField(
            label="优先级",
            choices=[IssuePriority.P0, IssuePriority.P1, IssuePriority.P2],
        )
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        issue = IssueDocument.get_issue_or_raise(
            validated_request_data["issue_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        activities = issue.update_priority(
            priority=validated_request_data["priority"], operator=validated_request_data["operator"]
        )
        return {
            "bk_biz_id": issue.bk_biz_id,
            "issue_id": issue.id,
            "status": issue.status,
            "priority": issue.priority,
            "update_time": issue.update_time,
            "activities": activities or [],
        }


class RenameResource(Resource):
    """重命名 Issue"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        new_name = serializers.CharField(label="Issue 名称", min_length=1, max_length=256)
        operator = serializers.CharField(label="操作人")

        def validate_new_name(self, value: str) -> str:
            stripped = value.strip()
            if not stripped:
                raise serializers.ValidationError("Issue name cannot be empty")
            return stripped

    def perform_request(self, validated_request_data):
        issue = IssueDocument.get_issue_or_raise(
            validated_request_data["issue_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        try:
            activities = issue.rename(
                new_name=validated_request_data["new_name"], operator=validated_request_data["operator"]
            )
        except IssueNameDuplicatedError as e:
            # 同业务下已存在同名 Issue
            raise serializers.ValidationError(str(e))
        return {
            "bk_biz_id": issue.bk_biz_id,
            "issue_id": issue.id,
            "status": issue.status,
            "name": issue.name,
            "update_time": issue.update_time,
            "activities": activities or [],
        }


class AddFollowUpResource(Resource):
    """向 Issue 添加跟进评论"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        content = serializers.CharField(label="跟进内容", min_length=1)
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        issue = IssueDocument.get_issue_or_raise(
            validated_request_data["issue_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        content = validated_request_data["content"]
        operator = validated_request_data["operator"]
        activities = issue.add_comment(content=content, operator=operator)
        return {
            "bk_biz_id": issue.bk_biz_id,
            "issue_id": issue.id,
            "status": issue.status,
            "update_time": issue.update_time,
            "activities": activities or [],
        }


class EditFollowUpResource(Resource):
    """编辑 Issue 跟进评论"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        activity_id = serializers.CharField(label="评论活动 ID", min_length=1)
        content = serializers.CharField(label="编辑后的内容", min_length=1)
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        issue = IssueDocument.get_issue_or_raise(
            validated_request_data["issue_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        try:
            activities = issue.edit_comment(
                activity_id=validated_request_data["activity_id"],
                content=validated_request_data["content"],
                operator=validated_request_data["operator"],
            )
        except IssueActivityNotFoundError as e:
            # 评论不存在或不属于当前 Issue（含传入非 comment 类型 activity_id 的情况）
            raise serializers.ValidationError(str(e))
        except PermissionError as e:
            # 非原作者尝试编辑评论
            raise serializers.ValidationError(str(e))
        return {
            "bk_biz_id": issue.bk_biz_id,
            "issue_id": issue.id,
            "status": issue.status,
            "content": validated_request_data["content"],
            "update_time": issue.update_time,
            "activities": activities or [],
        }


class MergeResource(Resource):
    """合并 Issue：把多个 Issue 收敛到一个主 Issue（api role 端执行，cache 真生效）。

    合并/拆分只建立或解除合并关系，与 Issue 状态完全解耦：main 与 member 处于任意状态
    （含已解决/已归档）都可参与合并。合并后 member 被冻结 + 列表隐藏，自身 status 不再权威，
    由主状态变更级联（_cascade_follow_status）与拆分重置接管，仅把其影响范围/告警追加到主
    聚合，不改变告警路由。

    校验顺序（按"轻量 → 重"组织）：
    1. ES 存在性 + 跨业务一致
    2. 防链式（main 端）：main 自身不能是别行 active 关系的 member
    3. 防链式（member 端）：members 自身不能是别行 active 关系的 main
    4. 任一 member 不能已在 active 关系（不可重复合并）
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        main_issue_id = IssueIDField(label="主 Issue ID")
        members = serializers.ListField(
            label="并入 Issue ID 列表",
            child=IssueIDField(),
            min_length=1,
            max_length=100,
        )
        # 合并依据非必填：缺省/空列表均合法（与拆分依据对齐；merge_reasons 模型默认空列表）
        reasons = serializers.ListField(label="合并依据", child=serializers.CharField(), required=False, default=list)
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        main_id = validated_request_data["main_issue_id"]
        members = list(dict.fromkeys(validated_request_data["members"]))  # 去重保序
        reasons = validated_request_data["reasons"]
        operator = validated_request_data["operator"]

        if main_id in members:
            members = [m for m in members if m != main_id]
        if not members:
            raise serializers.ValidationError("members 去重后为空")

        # 校验 1: ES 存在性 + 跨业务一致
        all_ids = [main_id, *members]
        biz_hits = (
            IssueDocument.search(all_indices=True)
            .filter("terms", _id=all_ids)
            .source(["bk_biz_id"])
            .params(size=len(all_ids))
            .execute()
            .hits
        )
        found_ids = {hit.meta.id for hit in biz_hits}
        missing_ids = [iid for iid in all_ids if iid not in found_ids]
        if missing_ids:
            raise MergeIssuesNotFoundError(missing_ids)

        biz_set = {str(getattr(h, "bk_biz_id", "")) for h in biz_hits if getattr(h, "bk_biz_id", None)}
        if not biz_set or len(biz_set) > 1 or str(bk_biz_id) not in biz_set:
            raise MergeCrossBizForbiddenError()

        # 状态不再校验：合并/拆分与 Issue 状态解耦，main 处于任意状态（含已解决/已归档）都可作为
        # 合并目标（详见类 docstring）。member 同样不限状态。

        # SQL 关系校验 2/3/4 + 写入放进同一事务，对关系行加锁（select_for_update）重查：
        # 表无 DB UNIQUE 约束，唯一性靠应用层 SELECT。并发 merge 同一 member 时，两侧校验 4
        # 都可能查不到 active 关系而各写一行，破坏"一 member 至多一个 active main"。校验 4 的
        # select_for_update 利用 (member_issue_id, status) 索引间隙锁，阻断并发事务在该区间插入，
        # 把竞态窗口收窄到提交前。极端残留（隔离级别/边界）仍由 list_conflicts + repair
        # resolve_conflicts 周期对账兜底（彻底方案是 DB 层 active member 唯一约束，更重，未做）。
        #
        # atomic 必须显式指定 IssueMergeRelation 实际写入的库：api role 启用 BackendRouter 后，
        # bkmonitor app 路由到 monitor_api 库，而 transaction.atomic() 缺省作用于 default 库。
        # 二者不一致时，事务开在 default、select_for_update 跑在 monitor_api（autocommit），
        # 触发 "select_for_update cannot be used outside of a transaction"。用 router.db_for_write
        # 取真实写库（同时兼容 default==backend 的单库部署），保证锁与事务落在同一连接。
        with transaction.atomic(using=router.db_for_write(IssueMergeRelation)):
            # 校验 2: 主 issue 自身是某行活跃 member（防链式 - main 端）
            target_as_member = (
                IssueMergeRelation.objects.select_for_update()
                .filter(
                    member_issue_id=main_id,
                    status=IssueMergeRelation.STATUS_ACTIVE,
                )
                .values("main_issue_id")
                .first()
            )
            if target_as_member:
                raise MergeTargetIsMemberError(main_id, target_as_member["main_issue_id"])

            # 校验 3: members 自身是别的 active 关系的 main（防链式 - member 端，与校验 2 对称）
            chain_members = list(
                IssueMergeRelation.objects.filter(
                    main_issue_id__in=members,
                    status=IssueMergeRelation.STATUS_ACTIVE,
                )
                .values_list("main_issue_id", flat=True)
                .distinct()
            )
            if chain_members:
                raise MergeMemberIsAnotherMainError(chain_members)

            # 校验 4: 任一 member 已在 active 关系（不可重复合并）——加锁重查，间隙锁阻断并发重复插入
            existing = (
                IssueMergeRelation.objects.select_for_update()
                .filter(
                    member_issue_id__in=members,
                    status=IssueMergeRelation.STATUS_ACTIVE,
                )
                .values("member_issue_id", "main_issue_id")
                .first()
            )
            if existing:
                raise MergeConflictError(existing["main_issue_id"])

            # 写关系表（与校验同事务，受上面行锁保护）
            IssueMergeRelation.objects.bulk_create(
                [
                    IssueMergeRelation(
                        bk_biz_id=bk_biz_id,
                        main_issue_id=main_id,
                        member_issue_id=m,
                        status=IssueMergeRelation.STATUS_ACTIVE,
                        merge_reasons=reasons,
                        create_user=operator,
                        update_user=operator,
                    )
                    for m in members
                ]
            )

        # 写 ES 活动日志（main 1 条 + 每 member 1 条 MERGED_INTO，失败仅 warning）
        now = int(time.time())
        bk_biz_id_str = str(bk_biz_id)
        activities: list[IssueActivityDocument] = [
            IssueActivityDocument(
                issue_id=main_id,
                bk_biz_id=bk_biz_id_str,
                activity_type=IssueActivityType.MERGED_INTO,
                from_value=None,
                to_value=None,
                operator=operator,
                content=json.dumps({"kind": "manual", "members": members}, ensure_ascii=False),
                time=now,
                create_time=now,
            ),
        ]
        for m in members:
            activities.append(
                IssueActivityDocument(
                    issue_id=m,
                    bk_biz_id=bk_biz_id_str,
                    activity_type=IssueActivityType.MERGED_INTO,
                    from_value=None,
                    to_value=main_id,
                    operator=operator,
                    content=json.dumps({"kind": "manual", "main_issue_id": main_id}, ensure_ascii=False),
                    time=now,
                    create_time=now,
                )
            )
        try:
            IssueActivityDocument.bulk_create(activities)
        except Exception as e:
            logger.warning("[issue-merge] merge activity bulk write failed: %s", e)

        return {"status": "ok", "main_issue_id": main_id, "members": members}


class SplitResource(Resource):
    """拆分单个 member Issue：恢复为独立 Issue 并重置状态为 PENDING_REVIEW + 清 assignee。

    api role 端执行，bulk_reset_for_split 的 cache DEL 真生效。
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        member_issue_id = IssueIDField(label="并入 Issue ID")
        # 拆分依据非必填：缺省/空列表均合法（下游 bulk_reset_for_split 与 split_info 已按空兜底）
        reasons = serializers.ListField(label="拆分依据", child=serializers.CharField(), required=False, default=list)
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        member_id = validated_request_data["member_issue_id"]
        reasons = validated_request_data["reasons"]
        operator = validated_request_data["operator"]

        # 关系必须存在且 active
        relation = IssueMergeRelation.objects.filter(
            bk_biz_id=bk_biz_id,
            member_issue_id=member_id,
            status=IssueMergeRelation.STATUS_ACTIVE,
        ).first()
        if not relation:
            raise SplitNotFoundError(member_id)

        # SQL UPDATE 改 status=split（单条 UPDATE 已原子，无需事务）
        # 显式写 update_time：split 关系的 update_time 即"拆分时间"，被 split_info.split_time
        # 消费（详情/列表展示 + 前端"刚拆出"瞬态高亮）。QuerySet.update() 不触发 auto_now，
        # 不显式赋值会残留合并时间 / cascade 触达时间，导致 split_time 错误。
        IssueMergeRelation.objects.filter(pk=relation.pk).update(
            status=IssueMergeRelation.STATUS_SPLIT,
            split_kind=IssueMergeRelation.SPLIT_KIND_MANUAL,
            split_reasons=reasons,
            update_user=operator,
            update_time=timezone.now(),
        )

        # ES 重置 member 状态 + 写活动日志（含 reasons，让 SPLIT_FROM content 自包含）
        # 失败仅 warning，bkm-cli + management command 兜底
        IssueDocument.bulk_reset_for_split(
            [member_id],
            operator=operator,
            kind=IssueMergeRelation.SPLIT_KIND_MANUAL,
            main_issue_id=relation.main_issue_id,
            bk_biz_id=bk_biz_id,
            reasons=reasons,
        )

        return {"status": "ok", "member_issue_id": member_id}


class RegenerateTitleResource(Resource):
    """批量重跑 Issue LLM 标题（运维显式补偿，同步执行，最多 5 个）。

    用于修复"未重命名成功"（LLM 标题任务失败/超时/未派发，Issue 仍是默认名）。语义与约束
    见 ``alarm_backends...issue_tasks.regenerate_issue_llm_title``：绕过业务白名单 +
    ENABLE_ISSUE_LLM_TITLE 部署闸门，保留业务级限流；已被用户手工改名的跳过，上次 LLM 改的可覆盖。

    并发（而非串行）执行：单条含 LLM 调用尾延迟可达数十秒，串行 5 条易撞网关超时；
    并发后接口耗时收敛到最慢一条。单条异常隔离进各自 result，不影响其他条目。
    注：本接口在 api role 执行（同步直调 regenerate_issue_llm_title，非 apply_async 派发），
    api role 具备 REDIS_*_CONF（限流/示例缓存）与 AIDEV 网关配置，可直接跑 LLM。

    超时兜底：补偿路径复用的 _apply_llm_title 不像原 Celery 任务带 soft/hard time_limit，
    而取关联日志（get_alert_relation_info）下游有 sleep 重试 + 无超时的日志平台查询，卡住会
    长期占用请求线程。故每条用 future.result(timeout) 限时：超时则该条记 timeout 结果、
    释放请求线程（游离线程由 ES/HTTP 客户端自身 socket 超时收尾，不阻塞 API 返回）。
    单条上限 = AIDEV 客户端 TIMEOUT(30s) + 取日志重试冗余，取 60s。
    """

    # 单条重跑墙钟上限（秒）：AIDEV chat_completion TIMEOUT=30s + get_alert_relation_info
    # 一次 sleep 重试 + 日志查询冗余。超过即判该条 timeout，释放请求线程。
    PER_ISSUE_TIMEOUT = 60

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_ids = serializers.ListField(
            label="Issue ID 列表", child=IssueIDField(), min_length=1, max_length=5
        )
        # 操作人可选：运维显式补偿默认记 system（与自动派发路径一致），传入则记该账号便于审计
        operator = serializers.CharField(label="操作人", required=False, default="system")

    def perform_request(self, validated_request_data):
        from concurrent.futures import TimeoutError as FuturesTimeoutError

        from alarm_backends.service.fta_action.tasks.issue_tasks import regenerate_issue_llm_title

        bk_biz_id = validated_request_data["bk_biz_id"]
        issue_ids = list(dict.fromkeys(validated_request_data["issue_ids"]))  # 去重保序
        operator = validated_request_data["operator"]

        def _fallback(issue_id: str, result: str) -> dict:
            return {
                "issue_id": issue_id,
                "bk_biz_id": bk_biz_id,
                "result": result,
                "old_name": None,
                "new_name": None,
            }

        # submit + result(timeout) 而非 executor.map：单条超时只影响该条（记 timeout），
        # 不让卡住的取数拖垮整个请求线程；其余条目正常返回。
        # 不用 with 上下文：其 __exit__ 会 shutdown(wait=True) 阻塞到卡住线程结束，反而抵消超时；
        # 改为手动 shutdown(wait=False)——请求线程即时返回，游离线程由客户端 socket 超时自行收尾。
        executor = ThreadPoolExecutor(max_workers=len(issue_ids))
        try:
            future_map = {
                executor.submit(regenerate_issue_llm_title, iid, bk_biz_id, operator=operator): iid
                for iid in issue_ids
            }
            results = []
            for future, iid in future_map.items():
                try:
                    results.append(future.result(timeout=self.PER_ISSUE_TIMEOUT))
                except FuturesTimeoutError:
                    logger.warning("[issue][llm_title] regenerate timeout, issue(%s)", iid)
                    results.append(_fallback(iid, "timeout"))
                except Exception as e:  # 单条异常隔离，不影响其他条目
                    logger.warning("[issue][llm_title] regenerate failed, issue(%s): %s", iid, e)
                    results.append(_fallback(iid, "llm_error"))
        finally:
            executor.shutdown(wait=False)

        return {"bk_biz_id": bk_biz_id, "results": results}


class IssueViewSet(ResourceViewSet):
    """
    Issue 接口
    """

    resource_routes = [
        # 指派或改派 issue 负责人
        ResourceRoute("POST", AssignResource(), endpoint="assign"),
        # 标记 issue 已解决
        ResourceRoute("POST", ResolveResource(), endpoint="resolve"),
        # 归档 issue
        ResourceRoute("POST", ArchiveResource(), endpoint="archive"),
        # 重新打开已解决 issue
        ResourceRoute("POST", ReopenResource(), endpoint="reopen"),
        # 恢复归档 issue
        ResourceRoute("POST", RestoreResource(), endpoint="restore"),
        # 修改 issue 优先级
        ResourceRoute("POST", UpdatePriorityResource(), endpoint="update_priority"),
        # 重命名 issue
        ResourceRoute("POST", RenameResource(), endpoint="rename"),
        # 向 Issue 添加跟进评论
        ResourceRoute("POST", AddFollowUpResource(), endpoint="add_follow_up"),
        # 编辑 Issue 跟进评论
        ResourceRoute("POST", EditFollowUpResource(), endpoint="edit_follow_up"),
        # 合并 Issue（独立映射层）
        ResourceRoute("POST", MergeResource(), endpoint="merge"),
        # 拆分 Issue
        ResourceRoute("POST", SplitResource(), endpoint="split"),
        # 批量重跑 Issue LLM 标题（运维显式补偿，≤5，同步）
        ResourceRoute("POST", RegenerateTitleResource(), endpoint="regenerate_title"),
    ]
