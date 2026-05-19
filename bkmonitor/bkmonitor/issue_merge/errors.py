"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _


class MergeCrossBizForbiddenError(Exception):
    """合并跨业务被拒。"""

    code = "MERGE_CROSS_BIZ_FORBIDDEN"

    def __init__(self):
        super().__init__(_("不允许跨业务合并 Issue"))

    def to_dict(self) -> dict:
        return {"code": self.code, "message": str(self)}


class MergeConflictError(Exception):
    """成员 Issue 已是另一主 Issue 的活跃 member。"""

    code = "MERGE_CONFLICT"

    def __init__(self, conflicting_main_issue_id: str):
        self.conflicting_main_issue_id = conflicting_main_issue_id
        super().__init__(_("待合并的 Issue 已被合并到 #{main_id}，请先拆分").format(main_id=conflicting_main_issue_id))

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "conflicting_main_issue_id": self.conflicting_main_issue_id,
            "message": str(self),
        }


class MergeTargetIsMemberError(Exception):
    """主 Issue 自己是某行活跃关系的 member（防链式合并）。"""

    code = "MERGE_TARGET_IS_MEMBER"

    def __init__(self, main_issue_id: str, conflicting_main_issue_id: str):
        self.main_issue_id = main_issue_id
        self.conflicting_main_issue_id = conflicting_main_issue_id
        super().__init__(
            _("目标主 Issue {main_id} 自身已被合并到 #{conflict_id}，请先拆分再作为主 Issue").format(
                main_id=main_issue_id, conflict_id=conflicting_main_issue_id
            )
        )

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "main_issue_id": self.main_issue_id,
            "conflicting_main_issue_id": self.conflicting_main_issue_id,
            "message": str(self),
        }


class SplitNotFoundError(Exception):
    """拆分对象未在 active 关系中。"""

    code = "SPLIT_NOT_FOUND"

    def __init__(self, member_issue_id: str):
        self.member_issue_id = member_issue_id
        super().__init__(_("Issue {issue_id} 不在合并状态，无需拆分").format(issue_id=member_issue_id))

    def to_dict(self) -> dict:
        return {"code": self.code, "member_issue_id": self.member_issue_id, "message": str(self)}
