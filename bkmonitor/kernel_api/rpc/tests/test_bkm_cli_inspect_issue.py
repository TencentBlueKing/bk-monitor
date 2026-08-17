"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from elasticsearch_dsl.utils import AttrDict

from core.drf_resource.exceptions import CustomException
from kernel_api.resource.bkm_cli import BkmCliOpCallResource
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.functions.bkm_cli import issue as issue_module
from kernel_api.rpc.registry import KernelRPCRegistry


class FakeIssueSearch:
    """链式调用 fake，记录每一步参数。"""

    def __init__(self, hits, total=None):
        self.hits = list(hits)
        self.total = total
        self.filters: list[tuple[str, dict]] = []
        self.sort_args: dict | None = None
        self.params_kwargs: dict = {}
        self.extra_kwargs: dict = {}
        self.slice_arg = None

    def filter(self, lookup, **kwargs):
        self.filters.append((lookup, kwargs))
        return self

    def sort(self, *args):
        self.sort_args = args[0] if len(args) == 1 else args
        return self

    def params(self, **kwargs):
        self.params_kwargs.update(kwargs)
        return self

    def extra(self, **kwargs):
        self.extra_kwargs.update(kwargs)
        return self

    def __getitem__(self, item):
        self.slice_arg = item
        return self

    def execute(self):
        return SimpleNamespace(
            hits=SimpleNamespace(
                __iter__=lambda s: iter(self.hits),
                total=SimpleNamespace(value=self.total) if self.total is not None else None,
            )
        )


def _wrap_hits(hits, total=None):
    """构造可被 hits.total.value / iter(hits) 同时消费的对象。"""

    class HitsContainer(list):
        pass

    container = HitsContainer(hits)
    container.total = SimpleNamespace(value=total) if total is not None else None
    return container


class StubSearch:
    """简化 ES 链式调用 stub，不用 SimpleNamespace 重复造迭代器。"""

    def __init__(self, hits, total=None):
        self._hits = hits
        self._total = total
        self.filter_calls: list[tuple[str, dict]] = []
        self.sort_arg = None
        self.params_kwargs: dict = {}
        self.extra_kwargs: dict = {}
        self.slice_arg = None

    def filter(self, lookup, **kwargs):
        self.filter_calls.append((lookup, kwargs))
        return self

    def sort(self, arg):
        self.sort_arg = arg
        return self

    def params(self, **kwargs):
        self.params_kwargs.update(kwargs)
        return self

    def extra(self, **kwargs):
        self.extra_kwargs.update(kwargs)
        return self

    def __getitem__(self, item):
        self.slice_arg = item
        return self

    def execute(self):
        return SimpleNamespace(hits=_wrap_hits(self._hits, self._total))


def test_inspect_issue_registered_as_bkm_cli_op():
    op = BkmCliOpRegistry.resolve("inspect-issue")
    detail = KernelRPCRegistry.get_function_detail("bkm_cli.inspect_issue")
    assert op.func_name == "bkm_cli.inspect_issue"
    assert op.capability_level == "inspect"
    assert op.risk_level == "low"
    assert detail is not None
    assert "readonly" in op.audit_tags
    assert "list_llm_title_candidates" in op.params_schema["operation"]
    assert "list_llm_title_candidates" in detail["params_schema"]["operation"]


def test_inspect_issue_rejects_unknown_operation():
    with pytest.raises(CustomException, match="不支持的 inspect-issue operation"):
        issue_module.inspect_issue({"operation": "create"})


# ---------- detail ----------


def test_inspect_issue_detail_returns_cleaned_doc(monkeypatch):
    fake_issue = SimpleNamespace(id="i-1", bk_biz_id="2", status="ABNORMAL")

    monkeypatch.setattr(
        "bkmonitor.documents.issue.IssueDocument.get_issue_or_raise",
        classmethod(lambda cls, issue_id, bk_biz_id=None: fake_issue),
    )
    monkeypatch.setattr(
        "fta_web.issue.handlers.issue.IssueQueryHandler.clean_document",
        classmethod(
            lambda cls, doc: {"id": doc.id, "bk_biz_id": doc.bk_biz_id, "status": doc.status, "duration": "1h"}
        ),
    )

    result = BkmCliOpCallResource().perform_request(
        {"op_id": "inspect-issue", "params": {"operation": "detail", "issue_id": "i-1", "bk_biz_id": 2}}
    )

    payload = result["result"]
    assert payload["operation"] == "detail"
    assert payload["issue_id"] == "i-1"
    assert payload["issue"]["status"] == "ABNORMAL"
    assert payload["issue"]["duration"] == "1h"


def test_inspect_issue_detail_rejects_missing_issue_id():
    with pytest.raises(CustomException, match="issue_id"):
        issue_module.inspect_issue({"operation": "detail"})


def test_inspect_issue_detail_passes_through_not_found(monkeypatch):
    from bkmonitor.documents.issue import IssueNotFoundError

    def raise_not_found(cls, issue_id, bk_biz_id=None):
        raise IssueNotFoundError("not found")

    monkeypatch.setattr(
        "bkmonitor.documents.issue.IssueDocument.get_issue_or_raise",
        classmethod(raise_not_found),
    )
    with pytest.raises(CustomException, match="Issue 不存在"):
        issue_module.inspect_issue({"operation": "detail", "issue_id": "nope", "bk_biz_id": 2})


# ---------- list_by_strategy ----------


def test_inspect_issue_list_by_strategy_filters_and_returns_total(monkeypatch):
    hits = [SimpleNamespace(id=f"i-{i}", bk_biz_id="2", status="ABNORMAL") for i in range(2)]
    stub = StubSearch(hits=hits, total=7)

    monkeypatch.setattr("bkmonitor.documents.issue.IssueDocument.search", staticmethod(lambda **kw: stub))
    monkeypatch.setattr(
        "fta_web.issue.handlers.issue.IssueQueryHandler.clean_document",
        classmethod(lambda cls, doc: {"id": doc.id, "bk_biz_id": doc.bk_biz_id, "status": doc.status}),
    )

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "inspect-issue",
            "params": {
                "operation": "list_by_strategy",
                "strategy_id": "10313",
                "bk_biz_id": 2,
                "status": ["ABNORMAL"],
                "start_time": 1776380000,
                "end_time": 1776390000,
                "limit": 50,
            },
        }
    )

    payload = result["result"]
    assert payload["operation"] == "list_by_strategy"
    assert payload["strategy_id"] == "10313"
    assert payload["count"] == 2
    assert payload["total"] == 7
    assert payload["truncated"] is True
    assert payload["issues"][0]["status"] == "ABNORMAL"

    # filter 顺序：term strategy_id → term bk_biz_id → terms status → range create_time × 2
    filter_lookups = [lookup for lookup, _ in stub.filter_calls]
    assert filter_lookups == ["term", "term", "terms", "range", "range"]
    assert stub.filter_calls[0][1] == {"strategy_id": "10313"}
    # bk_biz_id 必须以 string 形式 filter（IssueDocument.bk_biz_id 是 Keyword）
    assert stub.filter_calls[1][1] == {"bk_biz_id": "2"}
    assert stub.filter_calls[2][1] == {"status": ["ABNORMAL"]}
    assert stub.params_kwargs == {"size": 50, "track_total_hits": True}


def test_inspect_issue_list_by_strategy_requires_strategy_id_and_bk_biz_id():
    with pytest.raises(CustomException, match="strategy_id"):
        issue_module.inspect_issue({"operation": "list_by_strategy", "bk_biz_id": 2})
    with pytest.raises(CustomException, match="bk_biz_id"):
        issue_module.inspect_issue({"operation": "list_by_strategy", "strategy_id": "10313"})


# ---------- list_by_fingerprint ----------


def test_inspect_issue_list_by_fingerprint_uses_fingerprint_term(monkeypatch):
    stub = StubSearch(hits=[SimpleNamespace(id="i-1", bk_biz_id="2", status="RESOLVED")], total=1)

    monkeypatch.setattr("bkmonitor.documents.issue.IssueDocument.search", staticmethod(lambda **kw: stub))
    monkeypatch.setattr(
        "fta_web.issue.handlers.issue.IssueQueryHandler.clean_document",
        classmethod(lambda cls, doc: {"id": doc.id, "status": doc.status}),
    )

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "inspect-issue",
            "params": {
                "operation": "list_by_fingerprint",
                "fingerprint": "fp-abc",
                "bk_biz_id": 2,
            },
        }
    )

    payload = result["result"]
    assert payload["operation"] == "list_by_fingerprint"
    assert payload["fingerprint"] == "fp-abc"
    assert payload["count"] == 1
    assert stub.filter_calls[0] == ("term", {"fingerprint": "fp-abc"})


# ---------- list_activities ----------


def test_inspect_issue_list_activities_no_biz_check(monkeypatch):
    hits = [
        SimpleNamespace(
            meta=SimpleNamespace(id="a-1"),
            issue_id="i-1",
            bk_biz_id="2",
            activity_type="STATUS_CHANGED",
            operator="bot",
            from_value="ABNORMAL",
            to_value="RESOLVED",
            content="auto resolve",
            time=1776380000,
        ),
    ]
    stub = StubSearch(hits=hits, total=1)
    monkeypatch.setattr("bkmonitor.documents.issue.IssueActivityDocument.search", staticmethod(lambda **kw: stub))

    result = BkmCliOpCallResource().perform_request(
        {"op_id": "inspect-issue", "params": {"operation": "list_activities", "issue_id": "i-1"}}
    )

    payload = result["result"]
    assert payload["count"] == 1
    assert payload["activities"][0]["activity_id"] == "a-1"
    assert payload["activities"][0]["activity_type"] == "STATUS_CHANGED"
    assert payload["activities"][0]["time"] == 1776380000
    # 未传 bk_biz_id 时不走 get_issue_or_raise，filter 链路只看 issue_id
    assert stub.filter_calls == [("term", {"issue_id": "i-1"})]


def test_inspect_issue_list_activities_with_biz_validates_ownership(monkeypatch):
    hits = []
    stub = StubSearch(hits=hits, total=0)
    monkeypatch.setattr("bkmonitor.documents.issue.IssueActivityDocument.search", staticmethod(lambda **kw: stub))

    seen = {}

    def fake_get(cls, issue_id, bk_biz_id=None):
        seen["called"] = (issue_id, bk_biz_id)
        return SimpleNamespace(id=issue_id, bk_biz_id=str(bk_biz_id))

    monkeypatch.setattr(
        "bkmonitor.documents.issue.IssueDocument.get_issue_or_raise",
        classmethod(fake_get),
    )

    issue_module.inspect_issue({"operation": "list_activities", "issue_id": "i-1", "bk_biz_id": 2})

    assert seen["called"] == ("i-1", 2)


# ---------- list_llm_title_candidates ----------


def test_list_llm_title_candidates_returns_only_safe_candidates(monkeypatch):
    def _issue(issue_id, name="策略名"):
        return SimpleNamespace(
            meta=SimpleNamespace(id=issue_id),
            name=name,
            strategy_name="策略名",
            strategy_id="strategy-1",
            dimension_values={},
            is_regression=False,
            status="pending_review",
            create_time=1776380000,
        )

    stub = StubSearch(
        hits=[
            _issue("i-candidate"),
            _issue("i-user"),
            _issue("i-merged"),
            _issue("i-no-alert"),
            _issue("i-title-changed", name="已经生成的标题"),
        ],
        total=12,
    )
    monkeypatch.setattr("bkmonitor.documents.issue.IssueDocument.search", staticmethod(lambda **kw: stub))
    monkeypatch.setattr(
        issue_module,
        "_latest_name_change_operators",
        lambda issue_ids: {"i-user": "alice"},
        raising=False,
    )
    monkeypatch.setattr(
        issue_module,
        "_active_merge_main_issue_ids",
        lambda issue_ids, bk_biz_id: {"i-merged": "main-issue"},
        raising=False,
    )
    monkeypatch.setattr(
        issue_module,
        "_latest_alert_ids",
        lambda issue_ids: {
            "i-candidate": "alert-1",
            "i-user": "alert-2",
            "i-merged": "alert-3",
        },
        raising=False,
    )

    payload = issue_module.inspect_issue(
        {
            "operation": "list_llm_title_candidates",
            "bk_biz_id": 2,
            "offset": 5,
            "limit": 5,
        }
    )

    assert stub.filter_calls == [
        ("term", {"bk_biz_id": "2"}),
        ("terms", {"status": ["pending_review", "unresolved"]}),
    ]
    assert stub.slice_arg == slice(5, 10, None)
    assert payload["operation"] == "list_llm_title_candidates"
    assert payload["scanned_count"] == 5
    assert payload["candidate_count"] == 1
    assert payload["total_active"] == 12
    assert payload["offset"] == 5
    assert payload["next_offset"] == 10
    assert payload["truncated"] is True
    assert payload["excluded_counts"] == {
        "title_changed": 1,
        "user_renamed": 1,
        "merged_member": 1,
        "no_alert": 1,
    }
    assert payload["candidates"] == [
        {
            "issue_id": "i-candidate",
            "name": "策略名",
            "default_name": "策略名",
            "status": "pending_review",
            "strategy_id": "strategy-1",
            "strategy_name": "策略名",
            "create_time": 1776380000,
            "alert_id": "alert-1",
            "safe_to_regenerate": True,
            "candidate_reason": "active_default_title_safe",
        }
    ]


def test_llm_title_candidate_batch_queries_use_latest_collapsed_hits(monkeypatch):
    activity_stub = StubSearch(
        hits=[SimpleNamespace(issue_id="i-1", operator="alice")],
    )
    alert_stub = StubSearch(
        hits=[SimpleNamespace(meta=SimpleNamespace(id="alert-1"), issue_id="i-1")],
    )
    monkeypatch.setattr(
        "bkmonitor.documents.issue.IssueActivityDocument.search", staticmethod(lambda **kwargs: activity_stub)
    )
    monkeypatch.setattr("bkmonitor.documents.alert.AlertDocument.search", staticmethod(lambda **kwargs: alert_stub))

    assert issue_module._latest_name_change_operators(["i-1", "i-2"]) == {"i-1": "alice"}
    assert issue_module._latest_alert_ids(["i-1", "i-2"]) == {"i-1": "alert-1"}

    assert activity_stub.filter_calls == [
        ("terms", {"issue_id": ["i-1", "i-2"]}),
        ("term", {"activity_type": "name_change"}),
    ]
    assert activity_stub.sort_arg == {"time": {"order": "desc"}}
    assert activity_stub.extra_kwargs == {
        "collapse": {
            "field": "issue_id",
            "inner_hits": {
                "name": "latest_name_changes",
                "size": 2,
                "sort": [{"time": {"order": "desc"}}],
            },
        }
    }
    assert activity_stub.params_kwargs == {"size": 2}
    assert alert_stub.filter_calls == [("terms", {"issue_id": ["i-1", "i-2"]})]
    assert alert_stub.sort_arg == {"begin_time": {"order": "desc"}}
    assert alert_stub.extra_kwargs == {"collapse": {"field": "issue_id"}}
    assert alert_stub.params_kwargs == {"size": 2}


def test_latest_name_change_operators_fail_closed_on_same_second_tie(monkeypatch):
    inner_hits = SimpleNamespace(
        hits=SimpleNamespace(
            hits=[
                SimpleNamespace(operator="system", time=1776380000),
                SimpleNamespace(operator="alice", time=1776380000),
            ]
        )
    )
    outer_hit = SimpleNamespace(
        issue_id="i-1",
        operator="system",
        time=1776380000,
        meta=SimpleNamespace(inner_hits=SimpleNamespace(latest_name_changes=inner_hits)),
    )
    activity_stub = StubSearch(hits=[outer_hit])
    monkeypatch.setattr(
        "bkmonitor.documents.issue.IssueActivityDocument.search", staticmethod(lambda **kwargs: activity_stub)
    )

    assert issue_module._latest_name_change_operators(["i-1"]) == {"i-1": ""}


def test_latest_name_change_operators_read_raw_inner_hit_sources(monkeypatch):
    inner_hits = SimpleNamespace(
        hits=SimpleNamespace(
            hits=[
                AttrDict({"_source": {"operator": "system", "time": 1776380001}}),
                AttrDict({"_source": {"operator": "alice", "time": 1776380000}}),
            ]
        )
    )
    outer_hit = SimpleNamespace(
        issue_id="i-1",
        operator="system",
        time=1776380001,
        meta=SimpleNamespace(inner_hits=SimpleNamespace(latest_name_changes=inner_hits)),
    )
    activity_stub = StubSearch(hits=[outer_hit])
    monkeypatch.setattr(
        "bkmonitor.documents.issue.IssueActivityDocument.search", staticmethod(lambda **kwargs: activity_stub)
    )

    assert issue_module._latest_name_change_operators(["i-1"]) == {"i-1": "system"}


def test_llm_title_candidate_dependency_error_returns_no_partial_candidates(monkeypatch):
    monkeypatch.setattr(
        "bkmonitor.documents.issue.IssueActivityDocument.search",
        staticmethod(lambda **kwargs: (_ for _ in ()).throw(RuntimeError("activity unavailable"))),
    )

    with pytest.raises(CustomException, match="未返回候选"):
        issue_module._latest_name_change_operators(["i-1"])


def test_list_llm_title_candidates_requires_biz_and_non_negative_offset():
    with pytest.raises(CustomException, match="bk_biz_id"):
        issue_module.inspect_issue({"operation": "list_llm_title_candidates"})
    with pytest.raises(CustomException, match="offset 不能小于 0"):
        issue_module.inspect_issue({"operation": "list_llm_title_candidates", "bk_biz_id": 2, "offset": -1})


# ---------- limit guards ----------


def test_inspect_issue_limit_over_max_raises():
    with pytest.raises(CustomException, match="超过硬上限"):
        issue_module.inspect_issue(
            {"operation": "list_by_strategy", "strategy_id": "10313", "bk_biz_id": 2, "limit": 9999}
        )


def test_inspect_issue_limit_non_positive_raises():
    with pytest.raises(CustomException, match="大于 0"):
        issue_module.inspect_issue(
            {"operation": "list_by_strategy", "strategy_id": "10313", "bk_biz_id": 2, "limit": 0}
        )


# ---------- JSON-safe（lazy / datetime 等转换）----------


def test_to_json_safe_converts_gettext_lazy_to_str():
    """
    锁定契约：_to_json_safe 必须把 gettext_lazy 转成 str，
    避免 BkmCliOpCallResource.result (JSONField) 校验报错。
    """
    from django.utils.translation import gettext_lazy as _

    payload = {
        "display_name": _("目标IP"),
        "nested": {"label": _("业务ID"), "list": [_("挂载点"), "已是 str"]},
    }
    safe = issue_module._to_json_safe(payload)

    # gettext_lazy 实例本身不是 str（是 __proxy__），转换后必须是 str
    assert isinstance(safe["display_name"], str) and safe["display_name"] == "目标IP"
    assert isinstance(safe["nested"]["label"], str) and safe["nested"]["label"] == "业务ID"
    assert isinstance(safe["nested"]["list"][0], str) and safe["nested"]["list"][0] == "挂载点"


def test_inspect_issue_list_by_strategy_returns_json_safe_payload(monkeypatch):
    """
    端到端：clean_document 返回含 gettext_lazy 的 dict 时，inspect_issue 整体
    返回值必须能通过 BkmCliOpCallResource.ResponseSerializer 校验（即 JSON-safe）。
    """
    from django.utils.translation import gettext_lazy as _

    hits = [SimpleNamespace(id="i-1", bk_biz_id="2", status="ABNORMAL")]
    stub = StubSearch(hits=hits, total=1)

    monkeypatch.setattr("bkmonitor.documents.issue.IssueDocument.search", staticmethod(lambda **kw: stub))
    monkeypatch.setattr(
        "fta_web.issue.handlers.issue.IssueQueryHandler.clean_document",
        # 模拟真实 enrich_aggregate_dimensions 输出含 gettext_lazy 的场景
        classmethod(
            lambda cls, doc: {
                "id": doc.id,
                "aggregate_config": {"aggregate_dimensions": [{"field": "bk_target_ip", "display_name": _("目标IP")}]},
            }
        ),
    )

    result = BkmCliOpCallResource().perform_request(
        {"op_id": "inspect-issue", "params": {"operation": "list_by_strategy", "strategy_id": "10313", "bk_biz_id": 2}}
    )

    # 关键断言：lazy 已转 str，JSONField 校验不会报错
    issue = result["result"]["issues"][0]
    assert issue["aggregate_config"]["aggregate_dimensions"][0]["display_name"] == "目标IP"
    assert isinstance(issue["aggregate_config"]["aggregate_dimensions"][0]["display_name"], str)

    # 通过 ResponseSerializer 完整序列化一次（模拟真实 HTTP 返回路径），不应抛任何异常
    serialized = BkmCliOpCallResource.ResponseSerializer(result).data
    assert serialized["op_id"] == "inspect-issue"
