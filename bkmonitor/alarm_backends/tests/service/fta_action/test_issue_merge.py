"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

Issue 合并/拆分功能单测：覆盖 Resolver fast-path noop + 异常类 + content JSON 格式。
"""

import json

import pytest

from bkmonitor.documents.issue import IssueFrozenError
from bkmonitor.issue_merge import (
    IssueMergeResolver,
    MergeConflictError,
    MergeCrossBizForbiddenError,
    MergeResolverContext,
    MergeTargetIsMemberError,
    SplitNotFoundError,
)


class TestIssueFrozenError:
    """合并冻结异常：含 conflicting_main_issue_id 供前端跳转。"""

    def test_carries_conflicting_main_issue_id(self):
        err = IssueFrozenError(issue_id="b1", conflicting_main_issue_id="a1")
        assert err.issue_id == "b1"
        assert err.conflicting_main_issue_id == "a1"
        assert err.code == "MERGE_FREEZE_VIOLATION"

    def test_to_dict_has_all_fields(self):
        err = IssueFrozenError(issue_id="b1", conflicting_main_issue_id="a1")
        d = err.to_dict()
        assert d["code"] == "MERGE_FREEZE_VIOLATION"
        assert d["issue_id"] == "b1"
        assert d["conflicting_main_issue_id"] == "a1"
        assert "message" in d


class TestMergeErrors:
    """合并/拆分业务异常：继承 core.errors.Error → 由 custom_exception_handler 渲染。

    code 是 int（3337xxx 段），business_code 字符串通过 ``extra`` 暴露给前端。
    """

    def test_merge_cross_biz_forbidden(self):
        err = MergeCrossBizForbiddenError()
        assert err.code == 3337101
        assert err.extra["business_code"] == "MERGE_CROSS_BIZ_FORBIDDEN"
        assert err.status_code == 400

    def test_merge_conflict_carries_main_id(self):
        err = MergeConflictError(conflicting_main_issue_id="a1")
        assert err.code == 3337102
        assert err.conflicting_main_issue_id == "a1"
        assert err.extra["business_code"] == "MERGE_CONFLICT"
        assert err.extra["conflicting_main_issue_id"] == "a1"
        assert err.status_code == 409

    def test_merge_target_is_member(self):
        err = MergeTargetIsMemberError(main_issue_id="a1", conflicting_main_issue_id="c1")
        assert err.code == 3337103
        assert err.main_issue_id == "a1"
        assert err.conflicting_main_issue_id == "c1"
        assert err.extra["business_code"] == "MERGE_TARGET_IS_MEMBER"

    def test_split_not_found(self):
        err = SplitNotFoundError(member_issue_id="b1")
        assert err.code == 3337104
        assert err.member_issue_id == "b1"
        assert err.extra["business_code"] == "SPLIT_NOT_FOUND"

    def test_merge_issues_not_found(self):
        from bkmonitor.issue_merge import MergeIssuesNotFoundError

        err = MergeIssuesNotFoundError(["b1", "b2"])
        assert err.code == 3337105
        assert err.missing_ids == ["b1", "b2"]
        assert err.extra["business_code"] == "MERGE_ISSUES_NOT_FOUND"
        assert err.extra["missing_ids"] == ["b1", "b2"]
        assert err.status_code == 404


class TestMergeResolverFastPath:
    """Resolver fast-path：未 load context 或 degraded 时全部 noop（行为等价于无合并）。"""

    def test_context_unloaded_returns_none(self):
        ctx = MergeResolverContext(bk_biz_id=2)
        assert ctx.main_of("any_id") is None
        assert ctx.members_of("any_id") == []
        assert ctx.is_member("any_id") is False

    def test_degraded_context_all_noop(self):
        ctx = MergeResolverContext(bk_biz_id=2)
        ctx.degraded = True
        ctx._loaded = True
        assert ctx.main_of("x") is None
        assert ctx.members_of("x") == []

    def test_expand_to_full_ids_noop_when_unloaded(self):
        ctx = MergeResolverContext(bk_biz_id=2)
        result = IssueMergeResolver.expand_to_full_ids(["a", "b"], ctx)
        assert result == ["a", "b"]

    def test_resolve_display_id_passthrough_when_unloaded(self):
        ctx = MergeResolverContext(bk_biz_id=2)
        assert IssueMergeResolver.resolve_display_id("x", ctx) == "x"

    def test_filter_out_members_noop_when_unloaded(self):
        ctx = MergeResolverContext(bk_biz_id=2)
        assert IssueMergeResolver.filter_out_members(["a", "b", "c"], ctx) == ["a", "b", "c"]

    def test_hydrate_aggregations_noop_when_degraded(self):
        ctx = MergeResolverContext(bk_biz_id=2)
        ctx.degraded = True
        ctx._loaded = True
        issues = [{"id": "a"}, {"id": "b"}]
        IssueMergeResolver.hydrate_aggregations(issues, ctx)
        # 无合并关系时不注入 merge_status
        assert "merge_status" not in issues[0]
        assert "merge_status" not in issues[1]


class TestMergeResolverHydrate:
    """Resolver hydrate_aggregations：根据 context 注入 merge_status 字段。"""

    def test_main_role_injected(self):
        ctx = MergeResolverContext(bk_biz_id=2)
        ctx._loaded = True
        ctx._main_to_members = {
            "a1": [{"member_issue_id": "b1", "merge_time": 1000, "merge_reasons": ["r"], "merge_operator": "u"}]
        }
        ctx._member_to_main = {"b1": "a1"}

        issues = [{"id": "a1"}]
        IssueMergeResolver.hydrate_aggregations(issues, ctx)
        assert issues[0]["merge_status"]["role"] == "main"
        assert len(issues[0]["merge_status"]["active_members"]) == 1
        assert issues[0]["merge_status"]["active_members"][0]["member_issue_id"] == "b1"

    def test_member_role_injected(self):
        ctx = MergeResolverContext(bk_biz_id=2)
        ctx._loaded = True
        ctx._main_to_members = {"a1": [{"member_issue_id": "b1"}]}
        ctx._member_to_main = {"b1": "a1"}

        issues = [{"id": "b1"}]
        IssueMergeResolver.hydrate_aggregations(issues, ctx)
        assert issues[0]["merge_status"]["role"] == "member"
        assert issues[0]["merge_status"]["main_issue_id"] == "a1"

    def test_normal_issue_no_injection(self):
        ctx = MergeResolverContext(bk_biz_id=2)
        ctx._loaded = True
        ctx._main_to_members = {}
        ctx._member_to_main = {}

        issues = [{"id": "c1"}]
        IssueMergeResolver.hydrate_aggregations(issues, ctx)
        assert "merge_status" not in issues[0]


class TestExpandAndFilter:
    """expand_to_full_ids / filter_out_members / resolve_display_id 行为。"""

    @pytest.fixture
    def ctx(self):
        c = MergeResolverContext(bk_biz_id=2)
        c._loaded = True
        c._main_to_members = {
            "a1": [{"member_issue_id": "b1"}, {"member_issue_id": "b2"}],
        }
        c._member_to_main = {"b1": "a1", "b2": "a1"}
        return c

    def test_expand_main_includes_members(self, ctx):
        result = IssueMergeResolver.expand_to_full_ids(["a1"], ctx)
        assert set(result) == {"a1", "b1", "b2"}

    def test_expand_non_main_passthrough(self, ctx):
        result = IssueMergeResolver.expand_to_full_ids(["c1"], ctx)
        assert result == ["c1"]

    def test_filter_out_active_members(self, ctx):
        # b1, b2 是 active member，应被剔除；a1 / c1 透传
        result = IssueMergeResolver.filter_out_members(["a1", "b1", "b2", "c1"], ctx)
        assert result == ["a1", "c1"]

    def test_resolve_member_to_main(self, ctx):
        assert IssueMergeResolver.resolve_display_id("b1", ctx) == "a1"
        assert IssueMergeResolver.resolve_display_id("b2", ctx) == "a1"

    def test_resolve_non_member_passthrough(self, ctx):
        assert IssueMergeResolver.resolve_display_id("a1", ctx) == "a1"
        assert IssueMergeResolver.resolve_display_id("c1", ctx) == "c1"


class TestActivityContentFormat:
    """合并/拆分活动日志的 content JSON 字段结构（前端按 kind 渲染）。"""

    def test_merge_main_content_has_members(self):
        content = json.dumps({"kind": "manual", "members": ["b1", "b2"]}, ensure_ascii=False)
        data = json.loads(content)
        assert data["kind"] == "manual"
        assert data["members"] == ["b1", "b2"]

    def test_split_content_has_main_id_and_kind(self):
        for kind in ("manual", "by_main_resolve", "by_main_archive"):
            content = json.dumps({"kind": kind, "main_issue_id": "a1"}, ensure_ascii=False)
            data = json.loads(content)
            assert data["kind"] == kind
            assert data["main_issue_id"] == "a1"
