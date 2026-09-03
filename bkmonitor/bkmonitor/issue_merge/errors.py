"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

Issue 合并/拆分模块业务异常。继承 ``core.errors.Error``，由 ``custom_exception_handler``
统一渲染为 ``{result:false, code, name, message, data, extra}``，业务字段通过 ``extra`` 暴露给前端。

错误码段 3337xxx（issues 合并/拆分），与 alert (3324xxx) / incident (3336xxx) 等模块解耦。
"""

from django.utils.translation import gettext_lazy as _lazy

from core.errors import Error


class IssuesMergeError(Error):
    """Issues 合并/拆分模块基础错误（不直接抛出，作为子类共同祖先）。"""

    status_code = 500
    code = 3337001
    name = _lazy("Issues 合并/拆分模块错误")
    message_tpl = _lazy("Issues 合并/拆分模块错误")


class MergeCrossBizForbiddenError(IssuesMergeError):
    """合并跨业务被拒。"""

    status_code = 400
    code = 3337101
    name = _lazy("跨业务合并被拒")
    message_tpl = _lazy("不允许跨业务合并 Issue")

    def __init__(self):
        super().__init__(extra={"business_code": "MERGE_CROSS_BIZ_FORBIDDEN"})


class MergeConflictError(IssuesMergeError):
    """成员 Issue 已是另一主 Issue 的活跃 member。"""

    status_code = 409
    code = 3337102
    name = _lazy("合并冲突")
    message_tpl = _lazy("待合并的 Issue 已被合并到 #{conflicting_main_issue_id}，请先拆分")

    def __init__(self, conflicting_main_issue_id: str):
        self.conflicting_main_issue_id = conflicting_main_issue_id
        super().__init__(
            context={"conflicting_main_issue_id": conflicting_main_issue_id},
            extra={
                "business_code": "MERGE_CONFLICT",
                "conflicting_main_issue_id": conflicting_main_issue_id,
            },
        )


class MergeTargetIsMemberError(IssuesMergeError):
    """主 Issue 自身是某行活跃关系的 member（防链式合并）。"""

    status_code = 409
    code = 3337103
    name = _lazy("主 Issue 自身被合并")
    message_tpl = _lazy(
        "目标主 Issue {main_issue_id} 自身已被合并到 #{conflicting_main_issue_id}，请先拆分再作为主 Issue"
    )

    def __init__(self, main_issue_id: str, conflicting_main_issue_id: str):
        self.main_issue_id = main_issue_id
        self.conflicting_main_issue_id = conflicting_main_issue_id
        super().__init__(
            context={
                "main_issue_id": main_issue_id,
                "conflicting_main_issue_id": conflicting_main_issue_id,
            },
            extra={
                "business_code": "MERGE_TARGET_IS_MEMBER",
                "main_issue_id": main_issue_id,
                "conflicting_main_issue_id": conflicting_main_issue_id,
            },
        )


class SplitNotFoundError(IssuesMergeError):
    """拆分对象未在 active 关系中。"""

    status_code = 404
    code = 3337104
    name = _lazy("拆分对象不在合并状态")
    message_tpl = _lazy("Issue {member_issue_id} 不在合并状态，无需拆分")

    def __init__(self, member_issue_id: str):
        self.member_issue_id = member_issue_id
        super().__init__(
            context={"member_issue_id": member_issue_id},
            extra={"business_code": "SPLIT_NOT_FOUND", "member_issue_id": member_issue_id},
        )


class MergeIssuesNotFoundError(IssuesMergeError):
    """merge 入参中部分 Issue 在 ES 中不存在（main 或 members 任一）。

    防止"主 Issue 不存在也能写关系，member 被冻结并 resolve 到不存在的主 Issue"。
    """

    status_code = 404
    code = 3337105
    name = _lazy("合并的 Issue 不存在")
    message_tpl = _lazy("以下 Issue 不存在或业务归属不匹配: {missing_ids}")

    def __init__(self, missing_ids: list[str]):
        self.missing_ids = list(missing_ids)
        super().__init__(
            context={"missing_ids": ", ".join(self.missing_ids)},
            extra={"business_code": "MERGE_ISSUES_NOT_FOUND", "missing_ids": self.missing_ids},
        )


class MergeMainStatusForbiddenError(IssuesMergeError):
    """⚠ 已废弃，不再 raise（保留仅为错误码 3337106 占位 + 历史兼容）。

    曾用于禁止把成员合并到已 RESOLVED / ARCHIVED 的主 Issue。现已放开该限制：合并/拆分只
    建立或解除合并关系，与 Issue 状态解耦——主 Issue 处于任意状态都可作为合并目标。被合并
    member 合并后冻结 + 列表隐藏，自身 ES 状态不再权威，由主状态级联（_cascade_follow_status）
    与拆分重置接管，故 `MergeResource` 不再对 main 校验状态。保留本类避免错误码回收造成的
    客户端兼容问题；如需彻底移除，同步删 `__init__`/`__all__` 导出与单测。
    """

    status_code = 400
    code = 3337106
    name = _lazy("主 Issue 状态不允许合并")
    message_tpl = _lazy("主 Issue {main_issue_id} 当前状态 {main_status} 不允许合并，必须是活跃状态")

    def __init__(self, main_issue_id: str, main_status: str):
        self.main_issue_id = main_issue_id
        self.main_status = main_status
        super().__init__(
            context={"main_issue_id": main_issue_id, "main_status": main_status},
            extra={
                "business_code": "MERGE_MAIN_STATUS_FORBIDDEN",
                "main_issue_id": main_issue_id,
                "main_status": main_status,
            },
        )


class MergeMemberStatusForbiddenError(IssuesMergeError):
    """⚠ 已废弃，不再 raise（保留仅为错误码 3337107 占位 + 历史兼容）。

    曾用于禁止把已 RESOLVED / ARCHIVED 的 member 合并进活跃主。现已放开该限制：
    member 合并后被冻结，自身 ES 状态不再权威，由主状态级联与拆分重置接管，故
    `MergeResource` 不再对 member 校验状态（main 同样已放开，见 ``MergeMainStatusForbiddenError``）。
    保留本类避免错误码回收造成的客户端兼容问题；如需彻底移除，同步删 `__init__`/`__all__` 导出与单测。
    """

    status_code = 400
    code = 3337107
    name = _lazy("成员 Issue 状态不允许合并")
    message_tpl = _lazy("以下 Issue 状态不允许合并（必须是活跃状态）: {invalid_summary}")

    def __init__(self, invalid_members: list[dict]):
        # invalid_members: [{"issue_id": ..., "status": ...}, ...]
        self.invalid_members = list(invalid_members)
        invalid_summary = ", ".join(f"{m['issue_id']}({m['status']})" for m in self.invalid_members)
        super().__init__(
            context={"invalid_summary": invalid_summary},
            extra={
                "business_code": "MERGE_MEMBER_STATUS_FORBIDDEN",
                "invalid_members": self.invalid_members,
            },
        )


class MergeMemberIsAnotherMainError(IssuesMergeError):
    """⚠ 已废弃，不再 raise（保留仅为错误码 3337108 占位 + 历史兼容）。

    曾用于拒绝把"自身是别组 active main"的 Issue 作为 member 并入，理由是防止 hydrate 视图层
    陷入"主 → member → member 的 member"递归。该理由只在**真嵌套**下成立。

    现已放开：把已成组的主 A 并入 B 时，``MergeResource`` 在同一写事务内把 A 的 active 成员
    **改挂**（reparent）到 B，令其成为 B 的平级 member——关系深度仍恒为 1，视图层不会递归。
    环由 ``MergeTargetIsMemberError``（校验 2）天然拦住：若 B 本就是 A 的 member，
    merge(main=B, members=[A]) 在校验 2 即被拒。

    保留本类避免错误码回收造成的客户端兼容问题；如需彻底移除，同步删 `__init__`/`__all__`
    导出与单测。
    """

    status_code = 409
    code = 3337108
    name = _lazy("成员 Issue 自身是别的合并组主")
    message_tpl = _lazy("以下 Issue 自身是别的合并组主，请先拆分这些组再合并: {chain_members_summary}")

    def __init__(self, chain_members: list[str]):
        # chain_members: 那些自身是 active main 的 member id 列表
        self.chain_members = list(chain_members)
        super().__init__(
            context={"chain_members_summary": ", ".join(self.chain_members)},
            extra={
                "business_code": "MERGE_MEMBER_IS_ANOTHER_MAIN",
                "chain_members": self.chain_members,
            },
        )


class IssueFrozenError(IssuesMergeError):
    """Issue 被合并冻结，不允许写操作。

    抛出位置：IssueDocument 状态机方法入口的 ``IssueMergeResolver.assert_not_frozen`` 守卫
    （active member 被直接操作时）。

    必须是 ``IssuesMergeError`` 子类而非裸 Exception：状态机操作经 web→api role 中转，
    在 api role 抛出后由 ``custom_exception_handler`` 渲染为结构化响应，``conflicting_main_issue_id``
    经 ``extra`` 过 HTTP 边界回到 web；否则降级为通用错误，前端拿不到"跳转主 Issue"所需字段。
    """

    status_code = 409
    code = 3337109
    name = _lazy("Issue 已被合并冻结")
    message_tpl = _lazy("Issue {issue_id} 已被合并到 #{conflicting_main_issue_id}，请前往主 Issue 操作或先拆分")

    def __init__(self, issue_id: str, conflicting_main_issue_id: str):
        self.issue_id = issue_id
        self.conflicting_main_issue_id = conflicting_main_issue_id
        super().__init__(
            context={"issue_id": issue_id, "conflicting_main_issue_id": conflicting_main_issue_id},
            extra={
                "business_code": "MERGE_FREEZE_VIOLATION",
                "issue_id": issue_id,
                "conflicting_main_issue_id": conflicting_main_issue_id,
            },
        )


class MergeGroupTooLargeError(IssuesMergeError):
    """合并后组成员总数超过上限。

    把已成组的主并入另一主时，被并入主的成员会一起改挂过来，组规模可成倍增长。
    ``IssueMergeResolver.hydrate_aggregations`` 与 ``IssueDocument.bulk_follow_status`` 的
    ES 查询是 ``size=len(member_ids)``，无界组会退化成慢查询，故设上限。

    与"单策略活跃 Issue 数"的 warn-only 不同，这里**拒绝**而非放行：那边放行是因为阻塞会让
    告警永久失联（数据代价），这里超限只是一次交互失败，用户先拆分再合并即可。
    """

    status_code = 409
    code = 3337110
    name = _lazy("合并组过大")
    message_tpl = _lazy("合并后组成员数 {total} 超过上限 {limit}，请先拆分部分成员再合并")

    def __init__(self, current: int, incoming: int, carried: int, limit: int):
        self.current = current
        self.incoming = incoming
        self.carried = carried
        self.limit = limit
        super().__init__(
            context={"total": current + incoming + carried, "limit": limit},
            extra={
                "business_code": "MERGE_GROUP_TOO_LARGE",
                "current": current,
                "incoming": incoming,
                "carried": carried,
                "limit": limit,
            },
        )


class MergeGroupInconsistentError(IssuesMergeError):
    """待改挂的成员本身处于不一致状态，拒绝合并（失败关闭）。

    两种情形，都意味着**改动前**关系表已有不一致：
    - 待改挂成员已经是目标主的 active 成员（等价于已存在 duplicate_active_members）；
    - 待改挂成员自身还带着 active 成员（等价于已存在深度违例）。

    刻意不静默跳过、不自动修复：掩盖会把已存在的不一致扩散到更大的组，事后更难对账。
    运维用 bkm-cli ``inspect-issue list_conflicts`` 发现 + ``repair_issue_merge_state`` 修复后重试。
    """

    status_code = 409
    code = 3337111
    name = _lazy("合并组状态不一致")
    message_tpl = _lazy("以下 Issue 合并关系状态不一致（{reason}），请先修复再合并: {issue_ids_summary}")

    def __init__(self, issue_ids: list[str], reason: str):
        self.issue_ids = list(issue_ids)
        self.reason = reason
        super().__init__(
            context={"issue_ids_summary": ", ".join(self.issue_ids), "reason": reason},
            extra={
                "business_code": "MERGE_GROUP_INCONSISTENT",
                "issue_ids": self.issue_ids,
                "reason": reason,
            },
        )
