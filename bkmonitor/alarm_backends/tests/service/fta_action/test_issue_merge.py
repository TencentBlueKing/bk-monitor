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

from bkmonitor.issue_merge import (
    IssueFrozenError,
    IssueMergeResolver,
    MergeConflictError,
    MergeCrossBizForbiddenError,
    MergeResolverContext,
    MergeTargetIsMemberError,
    SplitNotFoundError,
)


class TestIssueFrozenError:
    """合并冻结异常：IssuesMergeError 子类，conflicting_main_issue_id 经 extra 过 HTTP 给前端。"""

    def test_carries_conflicting_main_issue_id(self):
        err = IssueFrozenError(issue_id="b1", conflicting_main_issue_id="a1")
        assert err.issue_id == "b1"
        assert err.conflicting_main_issue_id == "a1"
        # code 是 int（3337xxx 段），不再是字符串 business_code
        assert err.code == 3337109
        assert err.status_code == 409

    def test_extra_exposes_business_code_and_main_id(self):
        err = IssueFrozenError(issue_id="b1", conflicting_main_issue_id="a1")
        # business_code + conflicting_main_issue_id 走 extra（custom_exception_handler 渲染到响应顶层）
        assert err.extra["business_code"] == "MERGE_FREEZE_VIOLATION"
        assert err.extra["conflicting_main_issue_id"] == "a1"
        assert err.extra["issue_id"] == "b1"
        # message_tpl 用 context 渲染，含主 Issue id
        assert "a1" in err.message


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

    def test_merge_main_status_forbidden(self):
        """主 Issue 当前状态不允许合并：携带 main_issue_id + main_status，前端可据此引导。"""
        from bkmonitor.issue_merge import MergeMainStatusForbiddenError

        err = MergeMainStatusForbiddenError(main_issue_id="a1", main_status="RESOLVED")
        assert err.code == 3337106
        assert err.main_issue_id == "a1"
        assert err.main_status == "RESOLVED"
        assert err.extra["business_code"] == "MERGE_MAIN_STATUS_FORBIDDEN"
        assert err.extra["main_issue_id"] == "a1"
        assert err.extra["main_status"] == "RESOLVED"
        assert err.status_code == 400

    def test_merge_member_status_forbidden(self):
        """成员 Issue 状态不允许合并：携带 invalid_members 列表（含 issue_id + status）。"""
        from bkmonitor.issue_merge import MergeMemberStatusForbiddenError

        invalid = [
            {"issue_id": "b1", "status": "RESOLVED"},
            {"issue_id": "b2", "status": "ARCHIVED"},
        ]
        err = MergeMemberStatusForbiddenError(invalid)
        assert err.code == 3337107
        assert err.invalid_members == invalid
        assert err.extra["business_code"] == "MERGE_MEMBER_STATUS_FORBIDDEN"
        assert err.extra["invalid_members"] == invalid
        assert err.status_code == 400

    def test_merge_member_is_another_main(self):
        """成员 Issue 自身是别的合并组主（防链式合并，与 MergeTargetIsMemberError 对称）。"""
        from bkmonitor.issue_merge import MergeMemberIsAnotherMainError

        err = MergeMemberIsAnotherMainError(chain_members=["b1", "b3"])
        assert err.code == 3337108
        assert err.chain_members == ["b1", "b3"]
        assert err.extra["business_code"] == "MERGE_MEMBER_IS_ANOTHER_MAIN"
        assert err.extra["chain_members"] == ["b1", "b3"]
        assert err.status_code == 409


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


class TestMergeStatusConflictHint:
    """终态主 Issue 持有活跃 member 时，merge_status 暴露 status_conflict + active_member_count。

    合并/拆分与状态解耦后，活跃 member 可被并入已结案（resolved/archived）主 Issue，主状态不级联，
    于是出现「历史 Issue 下仍有活跃关联问题」。该提示让前端避免用户误判异常已结束。
    需 mock Step 2 的 IssueDocument.search（取 member ES 状态）；不 mock 时 ES 失败 fail-open，
    回落到 Step 1 默认值（status_conflict=False / active_member_count=0）。
    """

    @staticmethod
    def _ctx(main_to_members):
        ctx = MergeResolverContext(bk_biz_id=2)
        ctx._loaded = True
        ctx._main_to_members = main_to_members
        ctx._member_to_main = {m["member_issue_id"]: main for main, members in main_to_members.items() for m in members}
        return ctx

    @staticmethod
    def _patch_member_docs(monkeypatch, status_by_id):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from bkmonitor.documents.issue import IssueDocument

        hits = [
            SimpleNamespace(
                meta=SimpleNamespace(id=mid),
                status=st,
                first_alert_time=None,
                last_alert_time=None,
                impact_scope=None,
            )
            for mid, st in status_by_id.items()
        ]
        search_mock = MagicMock()
        search_mock.filter.return_value.source.return_value.params.return_value.execute.return_value.hits = hits
        monkeypatch.setattr(IssueDocument, "search", classmethod(lambda cls, **kw: search_mock))

    def test_conflict_when_terminal_main_holds_active_member(self, monkeypatch):
        from constants.issue import IssueStatus

        ctx = self._ctx({"a1": [{"member_issue_id": "b1"}, {"member_issue_id": "b2"}]})
        self._patch_member_docs(monkeypatch, {"b1": IssueStatus.UNRESOLVED, "b2": IssueStatus.RESOLVED})

        issues = [{"id": "a1", "status": IssueStatus.RESOLVED}]
        IssueMergeResolver.hydrate_aggregations(issues, ctx)

        ms = issues[0]["merge_status"]
        assert ms["role"] == "main"
        assert ms["active_member_count"] == 1  # 仅 b1 活跃；b2 已解决不计入
        assert ms["status_conflict"] is True

    def test_no_conflict_when_main_active(self, monkeypatch):
        from constants.issue import IssueStatus

        ctx = self._ctx({"a1": [{"member_issue_id": "b1"}]})
        self._patch_member_docs(monkeypatch, {"b1": IssueStatus.UNRESOLVED})

        issues = [{"id": "a1", "status": IssueStatus.UNRESOLVED}]
        IssueMergeResolver.hydrate_aggregations(issues, ctx)

        ms = issues[0]["merge_status"]
        assert ms["active_member_count"] == 1
        assert ms["status_conflict"] is False  # 主非终态，活跃 member 属正常合并，不算冲突

    def test_no_conflict_when_terminal_main_all_members_inactive(self, monkeypatch):
        from constants.issue import IssueStatus

        ctx = self._ctx({"a1": [{"member_issue_id": "b1"}, {"member_issue_id": "b2"}]})
        self._patch_member_docs(monkeypatch, {"b1": IssueStatus.RESOLVED, "b2": IssueStatus.ARCHIVED})

        issues = [{"id": "a1", "status": IssueStatus.ARCHIVED}]
        IssueMergeResolver.hydrate_aggregations(issues, ctx)

        ms = issues[0]["merge_status"]
        assert ms["active_member_count"] == 0
        assert ms["status_conflict"] is False  # 主终态但 member 已随主结案，无冲突

    def test_conflict_fields_default_when_es_fails(self):
        from constants.issue import IssueStatus

        # 不 mock IssueDocument.search → Step 2 ES 查询失败 fail-open，保留 Step 1 默认值
        ctx = self._ctx({"a1": [{"member_issue_id": "b1"}]})

        issues = [{"id": "a1", "status": IssueStatus.RESOLVED}]
        IssueMergeResolver.hydrate_aggregations(issues, ctx)

        ms = issues[0]["merge_status"]
        assert ms["role"] == "main"
        assert ms["status_conflict"] is False
        assert ms["active_member_count"] == 0


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


class TestUnionImpactScope:
    """_union_impact_scope 行为：跨维度 union / 去重忽略 enrich volatile 字段 / count 维护。

    Reviewer 反馈 1.3：主 Issue 在 clean_document 阶段已被 enrich（instance 含 alert_query_fields），
    member 走 ES 原始字段（不含 alert_query_fields）。如果去重键直接用 frozenset(item.items())，
    主 / member 字段集不一致会导致同一 instance 被判为不同 → 重复保留 + 前端字段不一致。
    本测试覆盖修复后的"忽略 volatile 字段去重"行为。
    """

    def test_cross_dimension_union(self):
        """跨策略合并：主 host 维度，member cluster 维度——各自独立保留。"""
        main_issue = {
            "id": "a1",
            "impact_scope": {
                "host": {"instance_list": [{"bk_host_id": "1", "display_name": "host-A"}], "count": 1},
            },
        }
        member_scope = {
            "cluster": {"instance_list": [{"bcs_cluster_id": "BCS-1"}], "count": 1},
        }
        IssueMergeResolver._union_impact_scope(main_issue, member_scope)
        assert set(main_issue["impact_scope"].keys()) == {"host", "cluster"}
        assert main_issue["impact_scope"]["host"]["count"] == 1
        assert main_issue["impact_scope"]["cluster"]["count"] == 1
        assert main_issue["impact_scope"]["cluster"]["instance_list"] == [{"bcs_cluster_id": "BCS-1"}]

    def test_same_dimension_dedup_main_enriched_vs_member_raw(self):
        """同 host_id 在主（已 enrich，含 alert_query_fields）+ member（未 enrich）：必须去重为 1 条。"""
        main_issue = {
            "id": "a1",
            "impact_scope": {
                "host": {
                    "instance_list": [
                        {
                            "bk_host_id": "9185731",
                            "display_name": "host-A",
                            "alert_query_fields": [{"keys": ["event.bk_host_id"], "value": "9185731"}],
                        }
                    ],
                    "count": 1,
                },
            },
        }
        member_scope = {
            "host": {
                "instance_list": [
                    {"bk_host_id": "9185731", "display_name": "host-A"}  # member 无 alert_query_fields
                ],
            },
        }
        IssueMergeResolver._union_impact_scope(main_issue, member_scope)
        # 去重成功：仍是 1 条
        assert len(main_issue["impact_scope"]["host"]["instance_list"]) == 1
        # count 与 instance_list 长度同步
        assert main_issue["impact_scope"]["host"]["count"] == 1
        # 保留主版本（带 alert_query_fields，对前端友好）
        first = main_issue["impact_scope"]["host"]["instance_list"][0]
        assert first["bk_host_id"] == "9185731"
        # 注：主版本是 existing 优先入 merged，alert_query_fields 应保留
        assert "alert_query_fields" in first

    def test_same_dimension_union_unique_instances(self):
        """同维度不同 host_id：两者都保留 + count = 2。"""
        main_issue = {
            "id": "a1",
            "impact_scope": {
                "host": {"instance_list": [{"bk_host_id": "1"}], "count": 1},
            },
        }
        member_scope = {
            "host": {"instance_list": [{"bk_host_id": "2"}]},
        }
        IssueMergeResolver._union_impact_scope(main_issue, member_scope)
        assert len(main_issue["impact_scope"]["host"]["instance_list"]) == 2
        assert main_issue["impact_scope"]["host"]["count"] == 2
        host_ids = {inst["bk_host_id"] for inst in main_issue["impact_scope"]["host"]["instance_list"]}
        assert host_ids == {"1", "2"}

    def test_main_without_dimension_member_supplements(self):
        """主无 cluster 维度，member 有：透传 member 维度全部字段（含 link_tpl）+ count 设置。"""
        main_issue = {
            "id": "a1",
            "impact_scope": {
                "host": {"instance_list": [{"bk_host_id": "1"}], "count": 1},
            },
        }
        member_scope = {
            "cluster": {
                "instance_list": [{"bcs_cluster_id": "BCS-1"}, {"bcs_cluster_id": "BCS-2"}],
                "link_tpl": "/cluster/{bcs_cluster_id}",  # 前端跳转模板
                "display_name": "BCS集群",
            },
        }
        IssueMergeResolver._union_impact_scope(main_issue, member_scope)
        assert main_issue["impact_scope"]["cluster"]["count"] == 2
        assert len(main_issue["impact_scope"]["cluster"]["instance_list"]) == 2
        # 关键断言：member 维度的 link_tpl / display_name 等字段必须透传，否则前端无法渲染跳转
        assert main_issue["impact_scope"]["cluster"]["link_tpl"] == "/cluster/{bcs_cluster_id}"
        assert main_issue["impact_scope"]["cluster"]["display_name"] == "BCS集群"
        # 同时 instance_list 应是副本（不共享原引用，避免后续聚合污染 member 数据）
        assert main_issue["impact_scope"]["cluster"]["instance_list"] is not member_scope["cluster"]["instance_list"]

    def test_empty_member_scope_noop(self):
        """member.impact_scope 为空：主不变。"""
        main_issue = {
            "id": "a1",
            "impact_scope": {"host": {"instance_list": [{"bk_host_id": "1"}], "count": 1}},
        }
        IssueMergeResolver._union_impact_scope(main_issue, {})
        assert main_issue["impact_scope"] == {"host": {"instance_list": [{"bk_host_id": "1"}], "count": 1}}


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

    def test_split_from_content_includes_reasons(self):
        """M7：SPLIT_FROM content 应包含用户传入的 reasons（自包含审计副本）。"""
        content = json.dumps(
            {"kind": "manual", "main_issue_id": "a1", "reasons": ["真正的 IO 异常，独立处理"]},
            ensure_ascii=False,
        )
        data = json.loads(content)
        assert data["kind"] == "manual"
        assert data["main_issue_id"] == "a1"
        assert data["reasons"] == ["真正的 IO 异常，独立处理"]

    def test_follow_status_content_format(self):
        """cascade follow 写 STATUS_CHANGE 活动 content 格式（前端按 kind 渲染）。

        kind 取值与 4 个主状态变更方法一一对应：
        - by_main_resolve / by_main_archive：原 cascade_split 的语义衍生
        - by_main_reopen / by_main_restore：新增的"主复活时 member 跟随"
        """
        for kind in ("by_main_resolve", "by_main_archive", "by_main_reopen", "by_main_restore"):
            content = json.dumps({"kind": kind, "main_issue_id": "a1"}, ensure_ascii=False)
            data = json.loads(content)
            assert data["kind"] == kind
            assert data["main_issue_id"] == "a1"


class TestSplitInfoFieldContract:
    """split_info 字段契约：detail 接口 + bkm-cli inspect-issue detail 同口径返回。

    满足需求 2.c / 2.d：前端拿到独立 Issue 后渲染「来自合并 Issues 拆分」+
    「拆分依据」标签。reasons 优先取自关系表（结构化 source-of-truth）。
    """

    def test_split_info_keys(self):
        """split_info 必含 6 字段：main_id / main_name / reasons / kind / time / operator。"""
        info = {
            "split_from_main_issue_id": "a1",
            "split_from_main_issue_name": "context deadline exceed",
            "split_reasons": ["真正的 IO 异常，独立处理"],
            "split_kind": "manual",
            "split_time": 1716580800,
            "split_operator": "willgchen",
        }
        # 前端按这 6 个 key 渲染——任一缺失即视为契约破裂
        for key in (
            "split_from_main_issue_id",
            "split_from_main_issue_name",
            "split_reasons",
            "split_kind",
            "split_time",
            "split_operator",
        ):
            assert key in info, f"split_info 必须包含 {key} 字段"

    def test_split_info_main_name_fallback(self):
        """主 Issue 已删除时，split_from_main_issue_name 用 `<id> (已删除)` 兜底。"""
        # 模拟主 Issue ES 查询返回空时的兜底文案
        main_id = "abc"
        main_name = None
        fallback = main_name or f"{main_id} (已删除)"
        assert fallback == "abc (已删除)"

    def test_split_info_reasons_from_relation(self):
        """reasons 取关系表 split_reasons（结构化 SoT），活动日志 SPLIT_FROM.content 为审计副本。"""
        relation_reasons = ["原因 1", "原因 2"]
        # 模拟 _fill_split_info 取数：result["split_info"]["split_reasons"] 来自 relation.split_reasons
        info = {"split_reasons": relation_reasons or []}
        assert info["split_reasons"] == ["原因 1", "原因 2"]

        # 关系表 split_reasons 为 None 时退化为空列表
        info_empty = {"split_reasons": None or []}
        assert info_empty["split_reasons"] == []


class TestGetSplitInfoMap:
    """``IssueMergeResolver.get_split_info_map`` 行为：列表批量拆分溯源注入的取数层。

    与详情 split_info 同键集（列表场景 main_name 留空）；多条 split 取最新；fail-open。
    """

    @staticmethod
    def _patch_rows(monkeypatch, rows=None, explode=False):
        """patch ``IssueMergeRelation.objects.filter(...).order_by(...).values(...)`` 链。"""
        from unittest.mock import MagicMock

        from bkmonitor.issue_merge import resolver as resolver_mod

        manager = MagicMock()
        if explode:
            manager.filter.side_effect = RuntimeError("db unreachable")
        else:
            manager.filter.return_value.order_by.return_value.values.return_value = rows or []
        monkeypatch.setattr(resolver_mod.IssueMergeRelation, "objects", manager)
        return manager

    def test_empty_member_ids_returns_empty(self):
        # 空入参不查 DB，直接返回 {}
        assert IssueMergeResolver.get_split_info_map([]) == {}

    def test_bk_biz_ids_adds_biz_filter(self, monkeypatch):
        """传 bk_biz_ids 时附加 bk_biz_id__in，与详情 _fill_split_info 口径一致（P2-2）。"""
        manager = self._patch_rows(monkeypatch, rows=[])
        IssueMergeResolver.get_split_info_map(["m1", "m2"], bk_biz_ids=[2, 3])
        kwargs = manager.filter.call_args.kwargs
        assert kwargs["member_issue_id__in"] == ["m1", "m2"]
        assert kwargs["bk_biz_id__in"] == [2, 3]

    def test_no_bk_biz_ids_omits_biz_filter(self, monkeypatch):
        """不传 bk_biz_ids 时只按 member_issue_id 查（向后兼容）。"""
        manager = self._patch_rows(monkeypatch, rows=[])
        IssueMergeResolver.get_split_info_map(["m1"])
        assert "bk_biz_id__in" not in manager.filter.call_args.kwargs

    def test_hit_returns_split_info_fields(self, monkeypatch):
        import datetime

        ts = datetime.datetime(2026, 5, 14, 12, 0, 0)
        self._patch_rows(
            monkeypatch,
            rows=[
                {
                    "member_issue_id": "m1",
                    "main_issue_id": "A",
                    "split_reasons": ["误合并，根因不同"],
                    "split_kind": "manual",
                    "update_time": ts,
                    "update_user": "willgchen",
                }
            ],
        )
        info = IssueMergeResolver.get_split_info_map(["m1"])["m1"]
        # 与详情 split_info 同键集
        assert set(info.keys()) == {
            "split_from_main_issue_id",
            "split_from_main_issue_name",
            "split_reasons",
            "split_kind",
            "split_time",
            "split_operator",
        }
        assert info["split_from_main_issue_id"] == "A"
        assert info["split_from_main_issue_name"] is None  # 列表不查主名（省 ES）
        assert info["split_reasons"] == ["误合并，根因不同"]
        assert info["split_time"] == int(ts.timestamp())
        assert info["split_operator"] == "willgchen"

    def test_multiple_split_keeps_latest(self, monkeypatch):
        import datetime

        newer = datetime.datetime(2026, 5, 14, 12, 0, 0)
        older = datetime.datetime(2026, 5, 1, 9, 0, 0)
        # DB 已按 -update_time, -id 排序；首见即最新
        self._patch_rows(
            monkeypatch,
            rows=[
                {
                    "member_issue_id": "m1",
                    "main_issue_id": "NEW",
                    "split_reasons": ["最新"],
                    "split_kind": "manual",
                    "update_time": newer,
                    "update_user": "u2",
                },
                {
                    "member_issue_id": "m1",
                    "main_issue_id": "OLD",
                    "split_reasons": ["历史"],
                    "split_kind": "manual",
                    "update_time": older,
                    "update_user": "u1",
                },
            ],
        )
        result = IssueMergeResolver.get_split_info_map(["m1"])
        assert len(result) == 1
        assert result["m1"]["split_from_main_issue_id"] == "NEW"
        assert result["m1"]["split_time"] == int(newer.timestamp())

    def test_reasons_none_degrades_to_empty_list(self, monkeypatch):
        import datetime

        self._patch_rows(
            monkeypatch,
            rows=[
                {
                    "member_issue_id": "m1",
                    "main_issue_id": "A",
                    "split_reasons": None,
                    "split_kind": "manual",
                    "update_time": datetime.datetime(2026, 5, 14, 0, 0, 0),
                    "update_user": "u",
                }
            ],
        )
        assert IssueMergeResolver.get_split_info_map(["m1"])["m1"]["split_reasons"] == []

    def test_sql_exception_fail_open(self, monkeypatch):
        self._patch_rows(monkeypatch, explode=True)
        # fail-open：DB 异常返回 {}，列表无拆分标签但不阻塞
        assert IssueMergeResolver.get_split_info_map(["m1"]) == {}


class TestMergeResolverContextMultiBiz:
    """P2a：MergeResolverContext 支持 int|list[int]，按业务集合 bk_biz_id__in 加载。
    单业务调用方（含测试关键字传参）向后兼容；跨业务 map 按全局唯一 id 无冲突。
    """

    @staticmethod
    def _patch_rows(monkeypatch, rows):
        from unittest.mock import MagicMock

        from bkmonitor.issue_merge import resolver as resolver_mod

        manager = MagicMock()
        manager.filter.return_value.values.return_value = rows
        monkeypatch.setattr(resolver_mod.IssueMergeRelation, "objects", manager)
        return manager

    def test_single_int_backward_compat(self, monkeypatch):
        from bkmonitor.issue_merge import MergeResolverContext

        manager = self._patch_rows(monkeypatch, [])
        ctx = MergeResolverContext(bk_biz_id=2)
        ctx.load()
        assert ctx.bk_biz_ids == [2]
        assert manager.filter.call_args.kwargs["bk_biz_id__in"] == [2]

    def test_multi_biz_list_maps_across_biz(self, monkeypatch):
        import datetime

        from bkmonitor.issue_merge import MergeResolverContext

        rows = [
            {
                "main_issue_id": "A",
                "member_issue_id": "m1",
                "merge_reasons": [],
                "create_user": "u",
                "create_time": datetime.datetime(2026, 5, 1, 0, 0, 0),
            },
            {
                "main_issue_id": "B",
                "member_issue_id": "m2",
                "merge_reasons": [],
                "create_user": "u",
                "create_time": datetime.datetime(2026, 5, 1, 0, 0, 0),
            },
        ]
        manager = self._patch_rows(monkeypatch, rows)
        ctx = MergeResolverContext([2, 3])
        ctx.load()
        assert manager.filter.call_args.kwargs["bk_biz_id__in"] == [2, 3]
        # 跨业务的两条关系都进同一 context（按全局唯一 issue_id）
        assert ctx.main_of("m1") == "A"
        assert ctx.main_of("m2") == "B"
        assert len(ctx.members_of("A")) == 1


class TestGetActiveMemberIdsSqlOnly:
    """web-cache：get_active_member_ids 改 SQL-only（不碰 service Redis），fail-open。"""

    def test_returns_sql_result(self, monkeypatch):
        from unittest.mock import MagicMock

        from bkmonitor.issue_merge import IssueMergeResolver
        from bkmonitor.issue_merge import resolver as resolver_mod

        manager = MagicMock()
        manager.filter.return_value.values_list.return_value = ["m1", "m2"]
        monkeypatch.setattr(resolver_mod.IssueMergeRelation, "objects", manager)
        assert IssueMergeResolver.get_active_member_ids(2) == ["m1", "m2"]

    def test_fail_open_returns_empty(self, monkeypatch):
        from unittest.mock import MagicMock

        from bkmonitor.issue_merge import IssueMergeResolver
        from bkmonitor.issue_merge import resolver as resolver_mod

        manager = MagicMock()
        manager.filter.side_effect = RuntimeError("db down")
        monkeypatch.setattr(resolver_mod.IssueMergeRelation, "objects", manager)
        assert IssueMergeResolver.get_active_member_ids(2) == []

    def test_single_int_normalized_to_in_filter(self, monkeypatch):
        from unittest.mock import MagicMock

        from bkmonitor.issue_merge import IssueMergeResolver
        from bkmonitor.issue_merge import resolver as resolver_mod

        manager = MagicMock()
        manager.filter.return_value.values_list.return_value = ["m1"]
        monkeypatch.setattr(resolver_mod.IssueMergeRelation, "objects", manager)
        IssueMergeResolver.get_active_member_ids(2)
        # 单 int 归一化为 bk_biz_id__in=[2]（统一走 IN 查询）
        assert manager.filter.call_args.kwargs["bk_biz_id__in"] == [2]

    def test_multi_biz_list_single_in_query(self, monkeypatch):
        """[-1] 展开后的多业务集：一次 bk_biz_id__in 查询批量排除（P2 修复）。"""
        from unittest.mock import MagicMock

        from bkmonitor.issue_merge import IssueMergeResolver
        from bkmonitor.issue_merge import resolver as resolver_mod

        manager = MagicMock()
        manager.filter.return_value.values_list.return_value = ["m1", "m2", "m3"]
        monkeypatch.setattr(resolver_mod.IssueMergeRelation, "objects", manager)
        result = IssueMergeResolver.get_active_member_ids([2, 3, 5])
        assert result == ["m1", "m2", "m3"]
        assert manager.filter.call_args.kwargs["bk_biz_id__in"] == [2, 3, 5]
        assert manager.filter.call_count == 1  # 单次查询，非每 biz 一次

    def test_empty_biz_list_returns_empty_no_query(self, monkeypatch):
        from unittest.mock import MagicMock

        from bkmonitor.issue_merge import IssueMergeResolver
        from bkmonitor.issue_merge import resolver as resolver_mod

        manager = MagicMock()
        monkeypatch.setattr(resolver_mod.IssueMergeRelation, "objects", manager)
        assert IssueMergeResolver.get_active_member_ids([]) == []
        manager.filter.assert_not_called()


class TestCascadeFollowTouchesRelation:
    """P1：cascade follow 时 touch active 关系 update_time，让 repair/list_conflicts
    的 update_time__gte 窗口能扫到本次参与流转的关系（ES 同步失败时兜底可发现）。
    """

    def test_touches_update_time_and_passes_bk_biz_id(self, monkeypatch):
        from unittest.mock import MagicMock

        from bkmonitor.documents.issue import IssueDocument
        from bkmonitor.models import issue as models_issue

        doc = IssueDocument(id="main-1", bk_biz_id="2")

        active_qs = MagicMock()
        active_qs.values_list.return_value = ["m1", "m2"]
        manager = MagicMock()
        manager.filter.return_value = active_qs
        monkeypatch.setattr(models_issue.IssueMergeRelation, "objects", manager)

        captured: dict = {}
        monkeypatch.setattr(
            IssueDocument,
            "bulk_follow_status",
            classmethod(lambda cls, member_ids, **kw: captured.update({"member_ids": member_ids, **kw})),
        )

        doc._cascade_follow_status(operator="alice", target_status="RESOLVED", kind="by_main_resolve")

        # 关系被 touch：update_time + update_user=operator
        active_qs.update.assert_called_once()
        update_kwargs = active_qs.update.call_args.kwargs
        assert update_kwargs["update_user"] == "alice"
        assert "update_time" in update_kwargs
        # bulk_follow_status 收到 member 业务 ID（cascade 传 self.bk_biz_id）
        assert captured["member_ids"] == ["m1", "m2"]
        assert captured["bk_biz_id"] == "2"

    def test_touch_failure_does_not_block_follow(self, monkeypatch):
        """touch update_time 写失败（如行锁）只 warning，不能阻断核心 bulk_follow_status。"""
        from unittest.mock import MagicMock

        from bkmonitor.documents.issue import IssueDocument
        from bkmonitor.models import issue as models_issue

        doc = IssueDocument(id="main-1", bk_biz_id="2")

        active_qs = MagicMock()
        active_qs.values_list.return_value = ["m1"]
        active_qs.update.side_effect = RuntimeError("lock wait timeout")  # touch 写失败
        manager = MagicMock()
        manager.filter.return_value = active_qs
        monkeypatch.setattr(models_issue.IssueMergeRelation, "objects", manager)

        called = {"follow": False}
        monkeypatch.setattr(
            IssueDocument,
            "bulk_follow_status",
            classmethod(lambda cls, *a, **kw: called.update({"follow": True})),
        )

        # 不应抛异常，且 cascade 仍执行
        doc._cascade_follow_status(operator="alice", target_status="RESOLVED", kind="by_main_resolve")
        assert called["follow"] is True

    def test_member_read_failure_returns_early(self, monkeypatch):
        """读 active member 失败才停止——此时无 member 可同步，return 不触 follow。"""
        from unittest.mock import MagicMock

        from bkmonitor.documents.issue import IssueDocument
        from bkmonitor.models import issue as models_issue

        doc = IssueDocument(id="main-1", bk_biz_id="2")

        active_qs = MagicMock()
        active_qs.values_list.side_effect = RuntimeError("db unreachable")  # 读 member 失败
        manager = MagicMock()
        manager.filter.return_value = active_qs
        monkeypatch.setattr(models_issue.IssueMergeRelation, "objects", manager)

        called = {"follow": False}
        monkeypatch.setattr(
            IssueDocument,
            "bulk_follow_status",
            classmethod(lambda cls, *a, **kw: called.update({"follow": True})),
        )

        doc._cascade_follow_status(operator="alice", target_status="RESOLVED", kind="by_main_resolve")
        # 读失败 → 提前 return，不 touch、不 follow
        active_qs.update.assert_not_called()
        assert called["follow"] is False

    def test_no_members_skips_touch_and_follow(self, monkeypatch):
        from unittest.mock import MagicMock

        from bkmonitor.documents.issue import IssueDocument
        from bkmonitor.models import issue as models_issue

        doc = IssueDocument(id="main-1", bk_biz_id="2")

        active_qs = MagicMock()
        active_qs.values_list.return_value = []
        manager = MagicMock()
        manager.filter.return_value = active_qs
        monkeypatch.setattr(models_issue.IssueMergeRelation, "objects", manager)

        called = {"follow": False}
        monkeypatch.setattr(
            IssueDocument,
            "bulk_follow_status",
            classmethod(lambda cls, *a, **kw: called.update({"follow": True})),
        )

        doc._cascade_follow_status(operator="alice", target_status="RESOLVED", kind="by_main_resolve")

        # 无 active member：不 touch、不 follow
        active_qs.update.assert_not_called()
        assert called["follow"] is False


class TestBulkActivitiesCarryBizId:
    """P2b：bulk_reset_for_split / bulk_follow_status 写的活动日志必须带 bk_biz_id
    （与普通 _write_activities 对齐，否则审计/按业务过滤缺字段）。
    """

    @staticmethod
    def _patch_es_noop(monkeypatch):
        """patch IssueDocument.bulk_create + search（fingerprint/status 查空），避免触 ES。"""
        from unittest.mock import MagicMock

        from bkmonitor.documents.issue import IssueDocument

        monkeypatch.setattr(IssueDocument, "bulk_create", classmethod(lambda cls, docs, **kw: None))
        search_mock = MagicMock()
        search_mock.filter.return_value.source.return_value.params.return_value.execute.return_value.hits = []
        monkeypatch.setattr(IssueDocument, "search", classmethod(lambda cls, **kw: search_mock))

    def test_bulk_reset_for_split_sets_bk_biz_id(self, monkeypatch):
        from bkmonitor.documents.issue import IssueActivityDocument, IssueDocument

        self._patch_es_noop(monkeypatch)
        captured: dict = {}
        monkeypatch.setattr(
            IssueActivityDocument, "bulk_create", classmethod(lambda cls, acts, **kw: captured.update({"acts": acts}))
        )

        IssueDocument.bulk_reset_for_split(
            ["m1", "m2"], operator="alice", kind="manual", main_issue_id="main-1", bk_biz_id=7, reasons=["r"]
        )

        acts = captured["acts"]
        assert acts  # 3N 条活动
        assert all(int(a.bk_biz_id) == 7 for a in acts)

    def test_bulk_follow_status_sets_bk_biz_id(self, monkeypatch):
        from bkmonitor.documents.issue import IssueActivityDocument, IssueDocument
        from constants.issue import IssueStatus

        self._patch_es_noop(monkeypatch)
        captured: dict = {}
        monkeypatch.setattr(
            IssueActivityDocument, "bulk_create", classmethod(lambda cls, acts, **kw: captured.update({"acts": acts}))
        )

        # target_status 用活跃态（UNRESOLVED）跳过 fp cache DEL 分支，避免触 Redis
        IssueDocument.bulk_follow_status(
            ["m1"],
            target_status=IssueStatus.UNRESOLVED,
            operator="alice",
            kind="by_main_reopen",
            main_issue_id="main-1",
            bk_biz_id=7,
        )

        acts = captured["acts"]
        assert acts
        assert all(int(a.bk_biz_id) == 7 for a in acts)


class TestResolveIdempotent:
    """resolve 幂等：已是 RESOLVED 时 no-op（不报错、不改状态、零副作用）；
    其它非活跃态（如 ARCHIVED）仍报错；活跃态正常流转。"""

    @staticmethod
    def _patch(monkeypatch):
        from unittest import mock

        from bkmonitor.documents.issue import IssueDocument
        from bkmonitor.issue_merge import IssueMergeResolver

        monkeypatch.setattr(IssueMergeResolver, "assert_not_frozen", staticmethod(lambda *a, **k: None))
        persist = mock.Mock()
        write = mock.Mock(return_value=["act"])
        cascade = mock.Mock()
        monkeypatch.setattr(IssueDocument, "_persist_and_cache", persist)
        monkeypatch.setattr(IssueDocument, "_write_activities", write)
        monkeypatch.setattr(IssueDocument, "_cascade_follow_status", cascade)
        return persist, write, cascade

    @staticmethod
    def _issue(status, name="订单服务异常"):
        from bkmonitor.documents.issue import IssueDocument

        issue = IssueDocument()
        issue.id = "iss-1"
        issue.name = name
        issue.status = status
        return issue

    def test_already_resolved_is_noop(self, monkeypatch):
        from constants.issue import IssueStatus

        persist, write, cascade = self._patch(monkeypatch)
        issue = self._issue(IssueStatus.RESOLVED)

        result = issue.resolve(operator="alice")

        assert result == []  # 无活动日志
        assert issue.status == IssueStatus.RESOLVED  # 状态不变
        persist.assert_not_called()  # 零副作用
        write.assert_not_called()
        cascade.assert_not_called()

    def test_already_resolved_frozen_member_still_noop(self, monkeypatch):
        """主 resolve 级联后 member 已是 RESOLVED 但合并关系仍 active（frozen）；对其重复 resolve
        应 no-op 成功，而非被冻结守卫拦成 IssueFrozenError 落入 failed。"""
        from unittest import mock

        from bkmonitor.documents.issue import IssueDocument
        from bkmonitor.issue_merge import IssueFrozenError, IssueMergeResolver
        from constants.issue import IssueStatus

        # 模拟 frozen member：冻结守卫一旦被调用就抛错
        def _raise_frozen(*a, **k):
            raise IssueFrozenError(issue_id="iss-1", conflicting_main_issue_id="main-1")

        monkeypatch.setattr(IssueMergeResolver, "assert_not_frozen", staticmethod(_raise_frozen))
        persist = mock.Mock()
        monkeypatch.setattr(IssueDocument, "_persist_and_cache", persist)

        issue = self._issue(IssueStatus.RESOLVED)
        result = issue.resolve(operator="alice")  # 不应抛 IssueFrozenError

        assert result == []
        assert issue.status == IssueStatus.RESOLVED
        persist.assert_not_called()

    def test_archived_still_raises_with_friendly_message(self, monkeypatch):
        from constants.issue import IssueStatus

        self._patch(monkeypatch)
        issue = self._issue(IssueStatus.ARCHIVED, name="订单服务异常")

        with pytest.raises(ValueError) as ei:
            issue.resolve(operator="alice")
        msg = str(ei.value)
        # 面向用户：带 issue 名称 + 中文可读状态 + 动作，不暴露裸 id / 枚举值
        assert "订单服务异常" in msg
        assert "归档" in msg
        assert "标记已解决" in msg
        assert "archived" not in msg and "resolved" not in msg

    def test_active_status_transitions_normally(self, monkeypatch):
        from constants.issue import IssueStatus

        persist, write, cascade = self._patch(monkeypatch)
        issue = self._issue(IssueStatus.UNRESOLVED)

        result = issue.resolve(operator="alice")

        assert issue.status == IssueStatus.RESOLVED  # 正常流转
        assert result == ["act"]
        persist.assert_called_once()
        write.assert_called_once()
        cascade.assert_called_once()


class TestMergeReasonsOptional:
    """合并依据 reasons 非必填：缺省 / 空列表均合法（与拆分依据对齐）。"""

    MAIN_ID = "1716000000abcdef01"
    MEMBER_ID = "1716000000abcdef02"

    def test_api_merge_serializer_reasons_optional(self):
        from kernel_api.views.v4.issue import MergeResource

        # 缺省 reasons → 合法，默认空列表
        s = MergeResource.RequestSerializer(
            data={"bk_biz_id": 2, "main_issue_id": self.MAIN_ID, "members": [self.MEMBER_ID], "operator": "alice"}
        )
        assert s.is_valid(), s.errors
        assert s.validated_data["reasons"] == []

        # 空列表 → 合法
        s2 = MergeResource.RequestSerializer(
            data={
                "bk_biz_id": 2,
                "main_issue_id": self.MAIN_ID,
                "members": [self.MEMBER_ID],
                "reasons": [],
                "operator": "alice",
            }
        )
        assert s2.is_valid(), s2.errors
        assert s2.validated_data["reasons"] == []

        # 传入 reasons 仍正常
        s3 = MergeResource.RequestSerializer(
            data={
                "bk_biz_id": 2,
                "main_issue_id": self.MAIN_ID,
                "members": [self.MEMBER_ID],
                "reasons": ["影响范围一样"],
                "operator": "alice",
            }
        )
        assert s3.is_valid(), s3.errors
        assert s3.validated_data["reasons"] == ["影响范围一样"]

    def test_web_merge_serializer_reasons_optional(self):
        from fta_web.issue.resources import MergeIssueResource

        s = MergeIssueResource.RequestSerializer(
            data={"bk_biz_id": 2, "main_issue_id": self.MAIN_ID, "members": [self.MEMBER_ID]}
        )
        assert s.is_valid(), s.errors
        assert s.validated_data["reasons"] == []


class TestMergeDecoupledFromStatus:
    """合并与 Issue 状态完全解耦：main 与 member 处于任意状态（含已解决 / 已归档）都可参与合并。

    直接驱动 ``MergeResource.perform_request``，mock 掉 ES 查询 + 关系表 SQL + 事务，
    断言「member 非活跃可并入」且「main 非活跃也可作为合并目标」。
    """

    MAIN_ID = "1716000000abcdef01"
    MEMBER_ID = "1716000000abcdef02"

    class _Hit:
        """模拟 ES hit：暴露 meta.id / bk_biz_id / status。"""

        def __init__(self, _id, status, bk_biz_id="2"):
            from types import SimpleNamespace

            self.meta = SimpleNamespace(id=_id)
            self.bk_biz_id = bk_biz_id
            self.status = status

    def _patch_io(self, monkeypatch, hits):
        """patch ES search / IssueMergeRelation.objects / transaction / router / 活动日志写入。"""
        import contextlib
        from unittest import mock
        from unittest.mock import MagicMock

        from kernel_api.views.v4 import issue as issue_mod

        # 校验 1：ES 存在性查询
        search_mock = MagicMock()
        search_mock.filter.return_value.source.return_value.params.return_value.execute.return_value.hits = hits
        monkeypatch.setattr(issue_mod.IssueDocument, "search", classmethod(lambda cls, **kw: search_mock))

        # 校验 2/3 关系查询全部"无冲突"，bulk_create 捕获写入行
        manager = MagicMock()
        manager.select_for_update.return_value.filter.return_value.values.return_value.first.return_value = None
        manager.filter.return_value.values_list.return_value.distinct.return_value = []
        # 组规模门禁：现有 active 成员数（MagicMock 默认返回 MagicMock，与 int 比较会 TypeError）
        manager.filter.return_value.count.return_value = 0
        captured: dict = {}
        manager.bulk_create.side_effect = lambda objs, **kw: captured.update({"rows": list(objs)})
        monkeypatch.setattr(issue_mod.IssueMergeRelation, "objects", manager)

        # 事务 / 路由：避免触真实 DB 连接
        fake_tx = mock.Mock()
        fake_tx.atomic = lambda *a, **k: contextlib.nullcontext()
        monkeypatch.setattr(issue_mod, "transaction", fake_tx)
        fake_router = mock.Mock()
        fake_router.db_for_write = lambda *a, **k: "default"
        monkeypatch.setattr(issue_mod, "router", fake_router)

        # 活动日志写入 noop（避免触 ES）
        monkeypatch.setattr(issue_mod.IssueActivityDocument, "bulk_create", classmethod(lambda cls, acts, **kw: None))
        return captured

    def _data(self):
        return {
            "bk_biz_id": 2,
            "main_issue_id": self.MAIN_ID,
            "members": [self.MEMBER_ID],
            "reasons": [],
            "operator": "alice",
        }

    @pytest.mark.parametrize("member_status_attr", ["RESOLVED", "ARCHIVED"])
    def test_inactive_member_can_merge_into_active_main(self, monkeypatch, member_status_attr):
        from constants.issue import IssueStatus
        from kernel_api.views.v4.issue import MergeResource

        hits = [
            self._Hit(self.MAIN_ID, IssueStatus.UNRESOLVED),
            self._Hit(self.MEMBER_ID, getattr(IssueStatus, member_status_attr)),
        ]
        captured = self._patch_io(monkeypatch, hits)

        result = MergeResource().perform_request(self._data())

        assert result["status"] == "ok"
        assert result["members"] == [self.MEMBER_ID]
        # 非活跃 member 不影响关系写入：确实写了 1 条 active 关系
        rows = captured["rows"]
        assert len(rows) == 1
        assert rows[0].member_issue_id == self.MEMBER_ID
        assert rows[0].main_issue_id == self.MAIN_ID

    @pytest.mark.parametrize("main_status_attr", ["RESOLVED", "ARCHIVED"])
    def test_inactive_main_now_allowed(self, monkeypatch, main_status_attr):
        """主非活跃（已解决 / 已归档）也可作为合并目标：状态门槛已彻底移除，合并/拆分与状态解耦。"""
        from constants.issue import IssueStatus
        from kernel_api.views.v4.issue import MergeResource

        hits = [
            self._Hit(self.MAIN_ID, getattr(IssueStatus, main_status_attr)),
            self._Hit(self.MEMBER_ID, IssueStatus.UNRESOLVED),
        ]
        captured = self._patch_io(monkeypatch, hits)

        result = MergeResource().perform_request(self._data())

        assert result["status"] == "ok"
        rows = captured["rows"]
        assert len(rows) == 1
        assert rows[0].main_issue_id == self.MAIN_ID
        assert rows[0].member_issue_id == self.MEMBER_ID


class TestListIssueHistoryExcludesActiveMembers:
    """ListIssueHistory 自建 ES 查询、未走 get_search_object，必须单独排除 active 冻结 member，
    否则放开非活跃合并后 RESOLVED 冻结 member 会泄漏进"同问题历史"。
    """

    def _patch(self, monkeypatch, *, active_member_ids):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from bkmonitor.documents.issue import IssueDocument
        from bkmonitor.issue_merge import IssueMergeResolver

        current = SimpleNamespace(fingerprint="fp-1", bk_biz_id="2", id="iss-cur")
        monkeypatch.setattr(IssueDocument, "get_issue_or_raise", classmethod(lambda cls, *a, **k: current))
        monkeypatch.setattr(
            IssueMergeResolver, "get_active_member_ids", staticmethod(lambda *a, **k: active_member_ids)
        )

        search_mock = MagicMock()
        search_mock.filter.return_value = search_mock
        search_mock.exclude.return_value = search_mock
        search_mock.sort.return_value = search_mock
        search_mock.params.return_value = search_mock
        search_mock.execute.return_value.hits = []
        monkeypatch.setattr(IssueDocument, "search", classmethod(lambda cls, **kw: search_mock))
        return search_mock

    def test_excludes_active_members(self, monkeypatch):
        from fta_web.issue.resources import ListIssueHistoryResource

        search_mock = self._patch(monkeypatch, active_member_ids=["m1", "m2"])
        ListIssueHistoryResource().perform_request({"bk_biz_id": 2, "issue_id": "iss-cur"})

        terms_excludes = [
            c
            for c in search_mock.exclude.call_args_list
            if c.args[:1] == ("terms",) and c.kwargs.get("_id") == ["m1", "m2"]
        ]
        assert terms_excludes, "应对 active 冻结 member 调用 exclude(terms, _id=[...])"

    def test_no_active_members_no_terms_exclude(self, monkeypatch):
        from fta_web.issue.resources import ListIssueHistoryResource

        search_mock = self._patch(monkeypatch, active_member_ids=[])
        ListIssueHistoryResource().perform_request({"bk_biz_id": 2, "issue_id": "iss-cur"})

        terms_excludes = [c for c in search_mock.exclude.call_args_list if c.args[:1] == ("terms",)]
        assert not terms_excludes


class _FakeRelationRow:
    """IssueMergeRelation 行的最小内存替身（只带本测试关心的字段）。"""

    _next_pk = 1

    def __init__(self, **kwargs):
        cls = type(self)
        # Django 语义：id 即主键，pk 是它的别名（生产代码 values("id") 与 filter(pk=...) 都会用到）
        self.id = cls._next_pk
        cls._next_pk += 1
        self.bk_biz_id = kwargs.get("bk_biz_id")
        self.main_issue_id = kwargs.get("main_issue_id")
        self.member_issue_id = kwargs.get("member_issue_id")
        self.status = kwargs.get("status")
        self.merge_reasons = kwargs.get("merge_reasons")
        self.split_reasons = kwargs.get("split_reasons")
        self.split_kind = kwargs.get("split_kind")
        self.via_issue_id = kwargs.get("via_issue_id")
        self.create_user = kwargs.get("create_user")
        self.update_user = kwargs.get("update_user")
        self.create_time = kwargs.get("create_time")
        self.update_time = kwargs.get("update_time")

    @property
    def pk(self):
        return self.id


class _FakeQuerySet:
    """支持 MergeResource 实际用到的链式调用的最小 QuerySet。

    覆盖：filter(精确 / __in) / select_for_update / values / values_list(flat, distinct)
    / first / count / annotate(Count) / order_by / 切片 / update。
    刻意用真实语义（而非 MagicMock）实现，才能验证改挂前后的行状态。
    """

    def __init__(self, store, rows=None):
        self._store = store
        self._rows = list(store.rows if rows is None else rows)

    def _clone(self, rows):
        return _FakeQuerySet(self._store, rows)

    def select_for_update(self):
        self._store.locked = True
        return self

    def filter(self, **kw):
        rows = self._rows
        for key, value in kw.items():
            if key.endswith("__in"):
                field = key[: -len("__in")]
                allowed = set(value)
                rows = [r for r in rows if getattr(r, field) in allowed]
            elif key.endswith("__gte"):
                rows = [r for r in rows if getattr(r, key[: -len("__gte")]) >= value]
            elif key == "pk":
                rows = [r for r in rows if r.id == value]
            else:
                rows = [r for r in rows if getattr(r, key) == value]
        return self._clone(rows)

    def exclude(self, **kw):
        keep = {r.id for r in self.filter(**kw)._rows}
        return self._clone([r for r in self._rows if r.id not in keep])

    def values(self, *fields):
        return _FakeValuesList({f: getattr(r, f) for f in fields} for r in self._rows)

    def values_list(self, *fields, flat=False):
        if flat:
            out = [getattr(r, fields[0]) for r in self._rows]
            return _FakeValuesList(out)
        return _FakeValuesList([tuple(getattr(r, f) for f in fields) for r in self._rows])

    def first(self):
        return self._rows[0] if self._rows else None

    def count(self):
        return len(self._rows)

    def annotate(self, **kw):
        """只支持 Count("id") 形态：按当前已 filter 的行做分组计数。

        调用方形态是 .values("x").annotate(n=Count("id"))，故这里在 _FakeValuesList 上实现。
        """
        raise NotImplementedError("annotate 应在 values() 之后调用")

    def order_by(self, *_args):
        return self

    def update(self, **kw):
        for r in self._rows:
            for key, value in kw.items():
                setattr(r, key, value)
        self._store.updates.append((sorted(r.id for r in self._rows), dict(kw)))
        return len(self._rows)

    def __iter__(self):
        return iter(self._rows)

    def __getitem__(self, item):
        return self._rows[item]

    def __len__(self):
        return len(self._rows)


class _FakeValuesList(list):
    """values() / values_list() 的返回值：额外支持 distinct / first / annotate。"""

    def distinct(self):
        seen, out = set(), []
        for v in self:
            key = tuple(sorted(v.items())) if isinstance(v, dict) else v
            if key not in seen:
                seen.add(key)
                out.append(v)
        return _FakeValuesList(out)

    def first(self):
        return self[0] if self else None

    def annotate(self, **kw):
        """只支持 ``Count("id")``：按 values() 选出的字段分组计数。

        形态：.values("member_issue_id").annotate(active_count=Count("id"))
        """
        assert len(kw) == 1, "fake annotate 只支持单个聚合"
        alias = next(iter(kw))
        groups: dict = {}
        for row in self:
            key = tuple(sorted(row.items()))
            groups.setdefault(key, {"row": row, "n": 0})
            groups[key]["n"] += 1
        return _FakeValuesList([{**g["row"], alias: g["n"]} for g in groups.values()])


class _FakeRelationStore:
    """内存关系表：manager 入口 + 行集合 + 写入记录。"""

    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.updates = []
        self.created = []
        self.locked = False

    # --- manager 接口 ---
    @property
    def objects(self):
        return self

    def filter(self, **kw):
        return _FakeQuerySet(self).filter(**kw)

    def select_for_update(self):
        return _FakeQuerySet(self).select_for_update()

    def bulk_create(self, objs):
        objs = list(objs)
        self.created.extend(objs)
        self.rows.extend(objs)
        return objs

    # --- 断言辅助 ---
    def active(self):
        return [r for r in self.rows if r.status == "active"]

    def members_of(self, main_id):
        return sorted(r.member_issue_id for r in self.active() if r.main_issue_id == main_id)

    def row_for(self, member_id):
        for r in self.rows:
            if r.member_issue_id == member_id:
                return r
        return None

    def assert_depth_is_one(self):
        """深度不变量：任一 active member 不得同时是别行的 active main。"""
        member_ids = {r.member_issue_id for r in self.active()}
        main_ids = {r.main_issue_id for r in self.active()}
        overlap = member_ids & main_ids
        assert not overlap, f"关系深度违例（member 同时是 main）: {sorted(overlap)}"


class TestMergeGroupReparent:
    """已合并主 Issue 继续合并：A 及其成员扁平化改挂到 B（深度恒为 1）。

    对应设计 042-merge-group-reparent 的 AC-01 / AC-03~AC-07。
    直接驱动 ``MergeResource.perform_request``，用内存 fake 关系表（非 MagicMock）
    以便断言改挂前后的真实行状态。
    """

    BIZ = 2
    B = "1716000000bbbbbb01"  # 目标主
    B1 = "1716000000bbbbbb02"  # B 的既有成员
    A = "1716000000aaaaaa01"  # 已成组的主（本次被并入 B）
    M1 = "1716000000aaaaaa02"  # A 的成员
    M2 = "1716000000aaaaaa03"  # A 的成员

    class _Hit:
        def __init__(self, _id, bk_biz_id="2"):
            from types import SimpleNamespace

            self.meta = SimpleNamespace(id=_id)
            self.bk_biz_id = bk_biz_id

    def _store_two_groups(self):
        """B──B1 与 A──M1,M2 两个 active 组。"""
        import datetime

        t0 = datetime.datetime(2026, 8, 1, 10, 0, 0)
        return _FakeRelationStore(
            [
                _FakeRelationRow(
                    bk_biz_id=self.BIZ,
                    main_issue_id=self.B,
                    member_issue_id=self.B1,
                    status="active",
                    merge_reasons=["b 组原因"],
                    create_user="u0",
                    update_user="u0",
                    create_time=t0,
                    update_time=t0,
                ),
                _FakeRelationRow(
                    bk_biz_id=self.BIZ,
                    main_issue_id=self.A,
                    member_issue_id=self.M1,
                    status="active",
                    merge_reasons=["a 组原因"],
                    create_user="u1",
                    update_user="u1",
                    create_time=t0,
                    update_time=t0,
                ),
                _FakeRelationRow(
                    bk_biz_id=self.BIZ,
                    main_issue_id=self.A,
                    member_issue_id=self.M2,
                    status="active",
                    merge_reasons=["a 组原因"],
                    create_user="u1",
                    update_user="u1",
                    create_time=t0,
                    update_time=t0,
                ),
            ]
        )

    def _patch_io(self, monkeypatch, store, es_ids, group_limit=500):
        """patch ES 存在性查询 + 关系表 + 事务 / 路由 + 活动日志写入，返回捕获的活动日志。"""
        import contextlib
        from unittest import mock
        from unittest.mock import MagicMock

        from django.conf import settings

        from kernel_api.views.v4 import issue as issue_mod

        search_mock = MagicMock()
        hits = [self._Hit(i) for i in es_ids]
        search_mock.filter.return_value.source.return_value.params.return_value.execute.return_value.hits = hits
        monkeypatch.setattr(issue_mod.IssueDocument, "search", classmethod(lambda cls, **kw: search_mock))

        monkeypatch.setattr(issue_mod.IssueMergeRelation, "objects", store.objects)

        fake_tx = mock.Mock()
        fake_tx.atomic = lambda *a, **k: contextlib.nullcontext()
        monkeypatch.setattr(issue_mod, "transaction", fake_tx)
        fake_router = mock.Mock()
        fake_router.db_for_write = lambda *a, **k: "default"
        monkeypatch.setattr(issue_mod, "router", fake_router)
        monkeypatch.setattr(settings, "ISSUE_MAX_MERGE_GROUP_SIZE", group_limit, raising=False)

        acts: list = []
        monkeypatch.setattr(
            issue_mod.IssueActivityDocument,
            "bulk_create",
            classmethod(lambda cls, a, **kw: acts.extend(a)),
        )
        return acts

    def _merge(self, main_id, members, reasons=None, operator="alice"):
        from kernel_api.views.v4.issue import MergeResource

        return MergeResource().perform_request(
            {
                "bk_biz_id": self.BIZ,
                "main_issue_id": main_id,
                "members": list(members),
                "reasons": reasons if reasons is not None else [],
                "operator": operator,
            }
        )

    # ---------- AC-01 ----------

    def test_reparent_moves_members_to_new_main(self, monkeypatch):
        """把已成组的主 A 并入 B：A 与 A 的成员全部成为 B 的平级成员。"""
        store = self._store_two_groups()
        self._patch_io(monkeypatch, store, [self.B, self.A])

        result = self._merge(self.B, [self.A], reasons=["同根因"])

        assert result["status"] == "ok"
        assert result["members"] == [self.A]
        assert sorted(result["reparented_members"]) == sorted([self.M1, self.M2])
        # B 组现有 4 个平级成员
        assert store.members_of(self.B) == sorted([self.B1, self.A, self.M1, self.M2])
        # A 名下不再有 active 成员
        assert store.members_of(self.A) == []
        store.assert_depth_is_one()

    def test_reparent_records_via_issue_id_and_preserves_original_merge_facts(self, monkeypatch):
        """改挂只改归属与 via/update_*，create_time / create_user 保留原始合并事实。"""
        store = self._store_two_groups()
        original = {mid: (store.row_for(mid).create_user, store.row_for(mid).create_time) for mid in (self.M1, self.M2)}
        self._patch_io(monkeypatch, store, [self.B, self.A])

        self._merge(self.B, [self.A], operator="bob")

        for mid in (self.M1, self.M2):
            row = store.row_for(mid)
            assert row.main_issue_id == self.B
            assert row.via_issue_id == self.A, "被携带成员必须记上一跳主"
            assert row.status == "active", "改挂不得把关系标成 split（否则前端误挂「由合并拆分」标签）"
            assert (row.create_user, row.create_time) == original[mid], "原始合并事实不可改写"
            assert row.update_user == "bob"
            assert row.update_time is not None, "update_time 必须显式赋值（.update() 不触发 auto_now）"
        # 直接合并进来的 A 自身 via 为空
        assert store.row_for(self.A).via_issue_id is None

    def test_reparent_writes_activity_with_reparent_kind(self, monkeypatch):
        """被改挂成员写 kind=reparent 活动日志，区别于用户直接合并的 kind=manual。"""
        store = self._store_two_groups()
        acts = self._patch_io(monkeypatch, store, [self.B, self.A])

        self._merge(self.B, [self.A])

        by_issue = {}
        for a in acts:
            by_issue.setdefault(a.issue_id, []).append(json.loads(a.content) if a.content else {})
        assert by_issue[self.A][0]["kind"] == "manual"
        for mid in (self.M1, self.M2):
            payload = by_issue[mid][0]
            assert payload["kind"] == "reparent"
            assert payload["from_main_issue_id"] == self.A
            assert payload["main_issue_id"] == self.B

    def test_plain_merge_without_carried_members_unchanged(self, monkeypatch):
        """未成组的普通 member 合并：不产生改挂，行为与改造前一致。"""
        store = self._store_two_groups()
        self._patch_io(monkeypatch, store, [self.B, "1716000000cccccc01"])

        result = self._merge(self.B, ["1716000000cccccc01"])

        assert result["reparented_members"] == []
        assert store.updates == [], "无被携带成员时不应发生任何 UPDATE"
        store.assert_depth_is_one()

    # ---------- AC-04：环 ----------

    def test_cycle_rejected_by_target_is_member_check(self, monkeypatch):
        """B 已是 A 的 member 时，merge(main=B, members=[A]) 必须被校验 2 拒绝，不产生环。"""
        from bkmonitor.issue_merge import MergeTargetIsMemberError

        store = _FakeRelationStore(
            [
                _FakeRelationRow(
                    bk_biz_id=self.BIZ,
                    main_issue_id=self.A,
                    member_issue_id=self.B,
                    status="active",
                    merge_reasons=[],
                )
            ]
        )
        self._patch_io(monkeypatch, store, [self.B, self.A])

        with pytest.raises(MergeTargetIsMemberError) as exc:
            self._merge(self.B, [self.A])

        assert exc.value.extra["business_code"] == "MERGE_TARGET_IS_MEMBER"
        assert store.created == [], "被拒后不得有任何写入"
        store.assert_depth_is_one()

    # ---------- AC-05：组规模 ----------

    def test_group_size_limit_rejects_and_writes_nothing(self, monkeypatch):
        """合并后组成员数超上限：抛 3337110，且关系表零写入。"""
        from bkmonitor.issue_merge import MergeGroupTooLargeError

        store = self._store_two_groups()
        # 现有 1（B1）+ 入参 1（A）+ 携带 2（M1/M2）= 4 > limit 3
        self._patch_io(monkeypatch, store, [self.B, self.A], group_limit=3)

        with pytest.raises(MergeGroupTooLargeError) as exc:
            self._merge(self.B, [self.A])

        assert exc.value.code == 3337110
        assert exc.value.extra["business_code"] == "MERGE_GROUP_TOO_LARGE"
        assert exc.value.extra["current"] == 1
        assert exc.value.extra["incoming"] == 1
        assert exc.value.extra["carried"] == 2
        assert exc.value.extra["limit"] == 3
        assert store.created == [], "门禁必须在写入之前，不得留半写状态"
        assert store.updates == []

    def test_group_size_limit_disabled_when_zero(self, monkeypatch):
        """阈值 0 = 关闭门禁：超大组也放行。"""
        store = self._store_two_groups()
        self._patch_io(monkeypatch, store, [self.B, self.A], group_limit=0)

        result = self._merge(self.B, [self.A])

        assert result["status"] == "ok"
        assert sorted(result["reparented_members"]) == sorted([self.M1, self.M2])

    # ---------- AC-06：前置一致性失败关闭 ----------

    def test_carried_member_already_in_target_group_fails_closed(self, monkeypatch):
        """待改挂成员已是目标主的 active 成员（历史 race 残留）→ 3337111，零写入。"""
        from bkmonitor.issue_merge import MergeGroupInconsistentError

        store = self._store_two_groups()
        # 造不一致：M1 同时挂在 B 下
        store.rows.append(
            _FakeRelationRow(
                bk_biz_id=self.BIZ,
                main_issue_id=self.B,
                member_issue_id=self.M1,
                status="active",
                merge_reasons=[],
            )
        )
        self._patch_io(monkeypatch, store, [self.B, self.A])

        with pytest.raises(MergeGroupInconsistentError) as exc:
            self._merge(self.B, [self.A])

        assert exc.value.code == 3337111
        assert exc.value.extra["business_code"] == "MERGE_GROUP_INCONSISTENT"
        assert exc.value.extra["reason"] == "already_active_member_of_target"
        assert self.M1 in exc.value.extra["issue_ids"]
        assert store.created == []
        assert store.updates == []

    def test_carried_member_with_own_members_fails_closed(self, monkeypatch):
        """待改挂成员自身还带 active 成员（已存在深度违例）→ 3337111，零写入。"""
        from bkmonitor.issue_merge import MergeGroupInconsistentError

        store = self._store_two_groups()
        # 造深度违例：M1 自己还是别人的主
        store.rows.append(
            _FakeRelationRow(
                bk_biz_id=self.BIZ,
                main_issue_id=self.M1,
                member_issue_id="1716000000dddddd01",
                status="active",
                merge_reasons=[],
            )
        )
        self._patch_io(monkeypatch, store, [self.B, self.A])

        with pytest.raises(MergeGroupInconsistentError) as exc:
            self._merge(self.B, [self.A])

        assert exc.value.extra["reason"] == "carried_member_has_own_members"
        assert self.M1 in exc.value.extra["issue_ids"]
        assert store.created == []
        assert store.updates == []

    # ---------- AC-03：拆分语义（决策 2） ----------

    def test_split_only_restores_the_merged_main(self, monkeypatch):
        """拆分 A 只恢复 A，M1/M2 仍留在 B 下（via_issue_id 保留）。"""
        import contextlib
        from unittest import mock

        from kernel_api.views.v4 import issue as issue_mod
        from kernel_api.views.v4.issue import SplitResource

        store = self._store_two_groups()
        self._patch_io(monkeypatch, store, [self.B, self.A])
        self._merge(self.B, [self.A])

        # split 走同一 store；patch 掉 ES 重置与时间
        monkeypatch.setattr(issue_mod.IssueMergeRelation, "objects", store.objects)
        fake_tx = mock.Mock()
        fake_tx.atomic = lambda *a, **k: contextlib.nullcontext()
        monkeypatch.setattr(issue_mod, "transaction", fake_tx)
        reset_calls: list = []
        monkeypatch.setattr(
            issue_mod.IssueDocument,
            "bulk_reset_for_split",
            classmethod(lambda cls, ids, **kw: reset_calls.append((list(ids), kw))),
        )

        SplitResource().perform_request(
            {
                "bk_biz_id": self.BIZ,
                "member_issue_id": self.A,
                "reasons": ["误判"],
                "operator": "carol",
            }
        )

        # A 的关系变 split，只有 A 被 ES 重置
        assert store.row_for(self.A).status == "split"
        assert reset_calls[0][0] == [self.A]
        # M1/M2 不受影响：仍在 B 组、via 保留
        for mid in (self.M1, self.M2):
            row = store.row_for(mid)
            assert row.status == "active"
            assert row.main_issue_id == self.B
            assert row.via_issue_id == self.A, "via 可指向已不在本组的 Issue（纯溯源标签）"
        assert store.members_of(self.B) == sorted([self.B1, self.M1, self.M2])
        store.assert_depth_is_one()

    # ---------- AC-07：并发 ----------

    def test_concurrent_merge_of_same_group_second_one_conflicts(self, monkeypatch):
        """两路并发把同一 A 并入不同主：第二路被校验 3（member 已在 active 关系）拒绝。"""
        from bkmonitor.issue_merge import MergeConflictError

        store = self._store_two_groups()
        self._patch_io(monkeypatch, store, [self.B, self.A])
        self._merge(self.B, [self.A])  # 第一路成功

        c_main = "1716000000cccccc09"
        self._patch_io(monkeypatch, store, [c_main, self.A])
        with pytest.raises(MergeConflictError) as exc:
            self._merge(c_main, [self.A])  # 第二路

        assert exc.value.conflicting_main_issue_id == self.B
        # A 的成员没被拆到两个组
        assert store.members_of(self.B) == sorted([self.B1, self.A, self.M1, self.M2])
        store.assert_depth_is_one()

    def test_select_for_update_used_on_carried_rows(self, monkeypatch):
        """改挂路径必须走 select_for_update（防并发 split / 另一路 merge 改动被携带行）。"""
        store = self._store_two_groups()
        self._patch_io(monkeypatch, store, [self.B, self.A])

        self._merge(self.B, [self.A])

        assert store.locked, "收集被携带成员时必须 select_for_update 加锁"
