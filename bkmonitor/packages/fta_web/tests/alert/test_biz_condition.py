from types import SimpleNamespace

import pytest
from elasticsearch_dsl import Search

from fta_web.alert.handlers import base
from fta_web.alert.handlers.action import ActionQueryHandler
from fta_web.alert.handlers.alert import AlertQueryHandler
from fta_web.alert.handlers.base import BaseBizQueryHandler
from fta_web.alert.handlers.incident import IncidentQueryHandler
from fta_web.issue.handlers.issue import IssueQueryHandler


def _patch_authorized_space(monkeypatch, biz_ids):
    """让 parse_biz_item 走 request 分支，返回指定授权业务集（不依赖真实鉴权 / DB）。"""
    monkeypatch.setattr(base, "get_request", lambda: SimpleNamespace(user=SimpleNamespace()))
    monkeypatch.setattr(
        base,
        "resource",
        SimpleNamespace(space=SimpleNamespace(get_bk_biz_ids_by_user=lambda user: list(biz_ids))),
    )


def _make_handler(handler_cls, bk_biz_ids, authorized_bizs, unauthorized_bizs):
    handler = handler_cls.__new__(handler_cls)
    handler.bk_biz_ids = bk_biz_ids
    handler.authorized_bizs = authorized_bizs
    handler.unauthorized_bizs = unauthorized_bizs
    handler.request_username = "admin"
    return handler


def _walk_dsl(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dsl(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dsl(child)


def _contains_terms(dsl, field, values):
    return any(node.get("terms", {}).get(field) == values for node in _walk_dsl(dsl))


def _contains_must_not_terms(dsl, field, values):
    for node in _walk_dsl(dsl):
        must_not = node.get("bool", {}).get("must_not", [])
        if isinstance(must_not, dict):
            must_not = [must_not]
        if any(item.get("terms", {}).get(field) == values for item in must_not):
            return True
    return False


def test_parse_biz_item_preserves_explicit_empty_authorized_bizs():
    authorized_bizs, unauthorized_bizs = BaseBizQueryHandler.parse_biz_item(
        [1],
        authorized_bizs=[],
        unauthorized_bizs=[1],
    )

    assert authorized_bizs == []
    assert unauthorized_bizs == [1]


@pytest.mark.parametrize(
    ("handler_cls", "field", "expected_values"),
    [
        (AlertQueryHandler, "event.bk_biz_id", [1, 2]),
        (IncidentQueryHandler, "bk_biz_id", [1, 2]),
        (ActionQueryHandler, "bk_biz_id", [1, 2]),
        (IssueQueryHandler, "bk_biz_id", ["1", "2"]),
    ],
)
def test_add_biz_condition_keeps_authorized_filter_when_unauthorized_is_empty(handler_cls, field, expected_values):
    handler = _make_handler(
        handler_cls,
        bk_biz_ids=[1, 2],
        authorized_bizs=[1, 2],
        unauthorized_bizs=[],
    )

    dsl = handler.add_biz_condition(Search()).to_dict()

    assert _contains_terms(dsl, field, expected_values)
    assert not _contains_must_not_terms(dsl, field, [])


def test_add_biz_condition_keeps_authorized_filter_for_all_biz_marker():
    handler = _make_handler(
        AlertQueryHandler,
        bk_biz_ids=[-1],
        authorized_bizs=[1, 2],
        unauthorized_bizs=[-1],
    )

    dsl = handler.add_biz_condition(Search()).to_dict()

    assert _contains_terms(dsl, "event.bk_biz_id", [1, 2])
    assert not _contains_must_not_terms(dsl, "event.bk_biz_id", [-1])


def test_parse_biz_item_drops_all_biz_sentinel_from_unauthorized(monkeypatch):
    _patch_authorized_space(monkeypatch, [1, 2])

    authorized_bizs, unauthorized_bizs = BaseBizQueryHandler.parse_biz_item([-1])

    assert sorted(authorized_bizs) == [1, 2]
    # -1 是"全部授权业务"哨兵而非真实业务，不得残留
    assert unauthorized_bizs == []


def test_add_biz_condition_omits_sentinel_only_clause(monkeypatch):
    # 解析结果直接喂给 add_biz_condition：不应再生成 bk_biz_id IN [-1] 的恒假子句
    _patch_authorized_space(monkeypatch, [1, 2])
    authorized_bizs, unauthorized_bizs = BaseBizQueryHandler.parse_biz_item([-1])
    handler = _make_handler(AlertQueryHandler, [-1], authorized_bizs, unauthorized_bizs)

    dsl = handler.add_biz_condition(Search()).to_dict()

    assert _contains_terms(dsl, "event.bk_biz_id", [1, 2])
    assert not _contains_terms(dsl, "event.bk_biz_id", [-1])


def test_add_biz_condition_splits_large_authorized_filter(monkeypatch):
    monkeypatch.setattr(AlertQueryHandler, "ES_TERMS_QUERY_MAX_SIZE", 2, raising=False)
    handler = _make_handler(
        AlertQueryHandler,
        bk_biz_ids=[1, 2, 3, 4, 5],
        authorized_bizs=[1, 2, 3, 4, 5],
        unauthorized_bizs=[6, 7, 8, 9, 10, 11],
    )

    dsl = handler.add_biz_condition(Search()).to_dict()

    assert _contains_terms(dsl, "event.bk_biz_id", [1, 2])
    assert _contains_terms(dsl, "event.bk_biz_id", [3, 4])
    assert _contains_terms(dsl, "event.bk_biz_id", [5])
