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
