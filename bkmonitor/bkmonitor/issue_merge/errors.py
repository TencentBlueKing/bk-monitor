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
    """部分 member Issue 自身是别的活跃合并关系的主 Issue（防链式合并的对称校验）。

    与 ``MergeTargetIsMemberError`` 对称：那个校验"目标主自身被合并"，这个校验
    "目标 member 自己是别人的主"——都是为了拒绝链式合并，否则 hydrate 视图层会陷入
    "主 → member → member 的 member"递归。
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
