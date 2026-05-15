"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

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

    def filter(self, lookup, **kwargs):
        self.filters.append((lookup, kwargs))
        return self

    def sort(self, *args):
        self.sort_args = args[0] if len(args) == 1 else args
        return self

    def params(self, **kwargs):
        self.params_kwargs.update(kwargs)
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

    def filter(self, lookup, **kwargs):
        self.filter_calls.append((lookup, kwargs))
        return self

    def sort(self, arg):
        self.sort_arg = arg
        return self

    def params(self, **kwargs):
        self.params_kwargs.update(kwargs)
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
