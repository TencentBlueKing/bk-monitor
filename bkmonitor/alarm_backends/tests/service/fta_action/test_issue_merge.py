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


class TestListMergeSourcesAnomalyMessage:
    """``_fetch_member_anomaly_messages`` 行为：

    1) 正常路径：terms agg + top_hits 返回 description → 命中的 member 进入结果字典
    2) 部分 member 无 alert → 不在结果字典（caller 兜底 ``"--"``）
    3) AlertDocument.search 抛异常 → 返回空 dict (fail-open)
    4) first_alert_time 全空 → 走 ``now - 30d`` 兜底窗口（不应抛异常）
    """

    @staticmethod
    def _build_search_stub(buckets: list, on_search=None):
        """构造一条链式可调用的 ES search stub，``buckets`` 即 ``result.aggs.issues.buckets``。"""
        from unittest.mock import MagicMock

        result = MagicMock()
        result.aggs.issues.buckets = buckets

        search_obj = MagicMock()
        search_obj.filter.return_value = search_obj
        search_obj.__getitem__.return_value.execute.return_value = result

        def _search(**kwargs):
            if on_search is not None:
                on_search(kwargs)
            return search_obj

        return _search, search_obj

    @staticmethod
    def _make_bucket(member_id: str, description: str | None):
        """模拟单个 issue_id terms 桶。``description=None`` 表示 top_hits 命中但 description 为空。"""
        from unittest.mock import MagicMock

        bucket = MagicMock()
        bucket.key = member_id
        if description is None:
            bucket.latest_alert.hits.hits = []
        else:
            hit = MagicMock()
            hit.to_dict.return_value = {"_source": {"event": {"description": description}}}
            bucket.latest_alert.hits.hits = [hit]
        return bucket

    def test_normal_path_returns_description_map(self, monkeypatch):
        from bkmonitor.documents import alert as alert_mod
        from fta_web.issue.resources import _fetch_member_anomaly_messages

        buckets = [
            self._make_bucket("b1", "AVG(CPU) >= 10%, 当前值 10.19%"),
            self._make_bucket("b2", "Disk IO 异常"),
        ]
        search_fn, _ = self._build_search_stub(buckets)
        monkeypatch.setattr(alert_mod.AlertDocument, "search", search_fn)

        result = _fetch_member_anomaly_messages(["b1", "b2"], {"b1": 1_700_000_000, "b2": 1_700_000_500})
        assert result == {
            "b1": "AVG(CPU) >= 10%, 当前值 10.19%",
            "b2": "Disk IO 异常",
        }

    def test_partial_miss_omits_member(self, monkeypatch):
        from bkmonitor.documents import alert as alert_mod
        from fta_web.issue.resources import _fetch_member_anomaly_messages

        # b1 命中、b2 top_hits 为空、b3 description 为空字符串：均不进入结果
        buckets = [
            self._make_bucket("b1", "CPU 异常"),
            self._make_bucket("b2", None),
            self._make_bucket("b3", ""),
        ]
        search_fn, _ = self._build_search_stub(buckets)
        monkeypatch.setattr(alert_mod.AlertDocument, "search", search_fn)

        result = _fetch_member_anomaly_messages(["b1", "b2", "b3"], {"b1": 1_700_000_000, "b2": 0, "b3": 0})
        assert result == {"b1": "CPU 异常"}

    def test_empty_member_ids_returns_empty(self):
        from fta_web.issue.resources import _fetch_member_anomaly_messages

        # 空入参不应触发 ES 查询，直接返回空 dict
        assert _fetch_member_anomaly_messages([], {}) == {}

    def test_search_exception_fail_open(self, monkeypatch):
        from bkmonitor.documents import alert as alert_mod
        from fta_web.issue.resources import _fetch_member_anomaly_messages

        def _explode(**kwargs):
            raise RuntimeError("ES cluster unreachable")

        monkeypatch.setattr(alert_mod.AlertDocument, "search", _explode)

        # fail-open：返回空 dict，由 caller 在 list_merge_sources 中兜底为 "--"
        assert _fetch_member_anomaly_messages(["b1"], {"b1": 1_700_000_000}) == {}

    def test_all_first_alert_time_empty_uses_fallback_window(self, monkeypatch):
        """所有 member 的 first_alert_time 为空（如旧数据）→ 走 now-30d 兜底窗口，不抛异常。"""
        from bkmonitor.documents import alert as alert_mod
        from fta_web.issue.resources import _MERGE_SOURCES_ANOMALY_FALLBACK_BUFFER, _fetch_member_anomaly_messages

        captured: dict = {}

        def _capture(kwargs):
            captured.update(kwargs)

        search_fn, _ = self._build_search_stub([self._make_bucket("b1", "fallback window hit")], on_search=_capture)
        monkeypatch.setattr(alert_mod.AlertDocument, "search", search_fn)

        result = _fetch_member_anomaly_messages(["b1"], {"b1": 0})
        assert result == {"b1": "fallback window hit"}
        # 兜底窗口 ≈ now - 30d；允许少量调用时延误差
        assert captured["end_time"] - captured["start_time"] == _MERGE_SOURCES_ANOMALY_FALLBACK_BUFFER
