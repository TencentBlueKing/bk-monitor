from types import SimpleNamespace

import pytest
from elasticsearch_dsl import Search

from bkmonitor.iam import ActionEnum, Permission
from iam_engine.provider.requests import VisibleResult
from fta_web.alert.handlers import base as base_handler_module
from fta_web.alert.handlers.action import ActionQueryHandler
from fta_web.alert.handlers.alert import AlertQueryHandler
from fta_web.alert.handlers.base import BaseBizQueryHandler, TENANT_WIDE_AUTHORIZED_REQUEST_ATTR
from fta_web.alert.handlers.incident import IncidentQueryHandler
from fta_web.issue.handlers.issue import IssueQueryHandler

# 四个 Handler 的业务字段：Alert 落在 event 下，Issue 的 bk_biz_id 是字符串型
BIZ_FIELD_CASES = [
    (AlertQueryHandler, "event.bk_biz_id"),
    (IncidentQueryHandler, "bk_biz_id"),
    (ActionQueryHandler, "bk_biz_id"),
    (IssueQueryHandler, "bk_biz_id"),
]

TENANT_ID = "tenant-a"


def _make_handler(handler_cls, bk_biz_ids, authorized_bizs, unauthorized_bizs):
    handler = handler_cls.__new__(handler_cls)
    handler.bk_biz_ids = bk_biz_ids
    handler.authorized_bizs = authorized_bizs
    handler.unauthorized_bizs = unauthorized_bizs
    handler.request_username = "admin"
    return handler


def _patch_tenant_mode(monkeypatch, *, multi_tenant=False):
    monkeypatch.setattr(base_handler_module.settings, "ENABLE_MULTI_TENANT_MODE", multi_tenant)


def _patch_request(monkeypatch, *, tenant_wide_authorized=False):
    request = SimpleNamespace(user=SimpleNamespace(username="admin"))
    setattr(request, TENANT_WIDE_AUTHORIZED_REQUEST_ATTR, tenant_wide_authorized)
    monkeypatch.setattr(base_handler_module, "get_request", lambda: request)
    return request


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


def _terms_values(dsl, field):
    return [node["terms"][field] for node in _walk_dsl(dsl) if node.get("terms", {}).get(field)]


def _contains_match_none(dsl):
    return any("match_none" in node for node in _walk_dsl(dsl))


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


def test_parse_biz_item_normalizes_all_biz_marker_from_propagated_scope():
    authorized_bizs, unauthorized_bizs = BaseBizQueryHandler.parse_biz_item(
        [-1],
        authorized_bizs=[1, 2, 3],
        unauthorized_bizs=[-1],
    )

    assert authorized_bizs == [1, 2, 3]
    assert unauthorized_bizs == []


def test_parse_all_biz_marks_trusted_tenant_wide_scope(monkeypatch):
    request = _patch_request(monkeypatch)

    class FakePermission:
        def __init__(self, username, bk_tenant_id):
            pass

        def filter_space_list_by_action_with_scope(self, action):
            assert action == ActionEnum.VIEW_BUSINESS
            return [{"bk_biz_id": biz_id} for biz_id in (1, 2, 3)], True

    monkeypatch.setattr(base_handler_module, "Permission", FakePermission, raising=False)

    authorized_bizs, unauthorized_bizs = BaseBizQueryHandler.parse_biz_item([-1])

    assert authorized_bizs == [1, 2, 3]
    assert unauthorized_bizs == []
    assert getattr(request, TENANT_WIDE_AUTHORIZED_REQUEST_ATTR) is True


@pytest.mark.parametrize(
    ("handler_cls", "field", "expected_values"),
    [
        (AlertQueryHandler, "event.bk_biz_id", [1, 2]),
        (IncidentQueryHandler, "bk_biz_id", [1, 2]),
        (ActionQueryHandler, "bk_biz_id", [1, 2]),
        (IssueQueryHandler, "bk_biz_id", ["1", "2"]),
    ],
)
def test_add_biz_condition_keeps_authorized_filter_when_unauthorized_is_empty(
    monkeypatch, handler_cls, field, expected_values
):
    _patch_tenant_mode(monkeypatch)
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


@pytest.mark.parametrize(("handler_cls", "field"), BIZ_FIELD_CASES)
def test_add_biz_condition_fails_closed_when_no_biz_clause_can_be_built(monkeypatch, handler_cls, field):
    """指定了业务范围却构不出任何业务子句时必须查空，不得退化为索引内全业务数据。

    授权业务为空时 build_es_terms_query 返回 None，子句列表随之为空；若此时直接返回
    search_object，业务过滤会整体消失——这是失败开放，比查空严重得多。
    """
    _patch_tenant_mode(monkeypatch)
    handler = _make_handler(handler_cls, bk_biz_ids=[1], authorized_bizs=[], unauthorized_bizs=[])

    dsl = handler.add_biz_condition(Search()).to_dict()

    assert _contains_match_none(dsl)
    assert not _terms_values(dsl, field)


@pytest.mark.parametrize(("handler_cls", "field"), BIZ_FIELD_CASES)
def test_add_biz_condition_omits_terms_for_trusted_tenant_wide_scope(monkeypatch, handler_cls, field):
    """IAM 明确授予租户全量权限时，业务维度无区分度，不再生成 terms 子句。

    管理员的授权业务可达十万级，这条子句实测能把单次请求的 DSL 撑到 1MB 以上。
    """
    _patch_tenant_mode(monkeypatch)
    _patch_request(monkeypatch, tenant_wide_authorized=True)
    handler = _make_handler(handler_cls, bk_biz_ids=[-1], authorized_bizs=[1, 2, 3], unauthorized_bizs=[])

    search_object = handler.add_biz_condition(Search())

    assert not _terms_values(search_object.to_dict(), field)
    # 免过滤而非查空：管理员本就可见本租户全部业务
    assert not _contains_match_none(search_object.to_dict())
    assert search_object.to_dict() == Search().to_dict()


@pytest.mark.parametrize(("handler_cls", "field"), BIZ_FIELD_CASES)
def test_add_biz_condition_keeps_terms_without_trusted_tenant_wide_scope(monkeypatch, handler_cls, field):
    """缓存空间集合被授权集覆盖，也不足以证明 IAM 策略允许访问当前及未来的全部业务。"""
    _patch_tenant_mode(monkeypatch)
    _patch_request(monkeypatch, tenant_wide_authorized=False)
    handler = _make_handler(handler_cls, bk_biz_ids=[-1], authorized_bizs=[1, 2, 3], unauthorized_bizs=[])

    dsl = handler.add_biz_condition(Search()).to_dict()

    assert _terms_values(dsl, field)


@pytest.mark.parametrize(("handler_cls", "field"), BIZ_FIELD_CASES)
def test_add_biz_condition_keeps_terms_for_explicit_biz_list(monkeypatch, handler_cls, field):
    """即使用户具备全量权限，显式业务列表仍是调用方要求保留的查询范围。"""
    _patch_tenant_mode(monkeypatch)
    _patch_request(monkeypatch, tenant_wide_authorized=True)
    handler = _make_handler(handler_cls, bk_biz_ids=[1, 2, 3], authorized_bizs=[1, 2, 3], unauthorized_bizs=[])

    dsl = handler.add_biz_condition(Search()).to_dict()

    assert _terms_values(dsl, field)


@pytest.mark.parametrize(("handler_cls", "field"), BIZ_FIELD_CASES)
def test_add_biz_condition_keeps_terms_in_multi_tenant_mode(monkeypatch, handler_cls, field):
    """多租户部署下即使授权覆盖全量也必须保留业务 terms。

    告警检索链路并不过滤 bk_tenant_id（该字段只写不读，且早期索引里完全没有），
    业务 terms 同时承担着租户隔离，省掉就会跨租户泄漏。
    """
    _patch_tenant_mode(monkeypatch, multi_tenant=True)
    _patch_request(monkeypatch, tenant_wide_authorized=True)
    handler = _make_handler(handler_cls, bk_biz_ids=[-1], authorized_bizs=[1, 2, 3], unauthorized_bizs=[])

    dsl = handler.add_biz_condition(Search()).to_dict()

    assert _terms_values(dsl, field)


@pytest.mark.parametrize(("handler_cls", "field"), BIZ_FIELD_CASES)
def test_add_biz_condition_keeps_terms_without_request_context(monkeypatch, handler_cls, field):
    """无请求上下文时拿不到可信 IAM 标记，内部调用必须继续按业务过滤。"""
    _patch_tenant_mode(monkeypatch)

    def get_request_without_context():
        raise RuntimeError("request context unavailable")

    monkeypatch.setattr(base_handler_module, "get_request", get_request_without_context)
    handler = _make_handler(handler_cls, bk_biz_ids=[-1], authorized_bizs=[1, 2, 3], unauthorized_bizs=[])

    dsl = handler.add_biz_condition(Search()).to_dict()

    assert _terms_values(dsl, field)


@pytest.mark.parametrize(("handler_cls", "field"), BIZ_FIELD_CASES)
def test_add_biz_condition_keeps_terms_with_real_unauthorized_bizs(monkeypatch, handler_cls, field):
    """存在真实未授权业务时，即使 IAM 标记为全量也不得进入省略分支。"""
    _patch_tenant_mode(monkeypatch)
    _patch_request(monkeypatch, tenant_wide_authorized=True)
    handler = _make_handler(handler_cls, bk_biz_ids=[-1, 9], authorized_bizs=[1, 2, 3], unauthorized_bizs=[9])

    dsl = handler.add_biz_condition(Search()).to_dict()

    assert _terms_values(dsl, field)


def test_add_biz_condition_without_biz_scope_keeps_existing_semantics(monkeypatch):
    """未指定业务范围时保持既有语义：Alert 退化为"与我相关"，而不是查空。"""
    _patch_tenant_mode(monkeypatch)
    handler = _make_handler(AlertQueryHandler, bk_biz_ids=None, authorized_bizs=None, unauthorized_bizs=[])

    dsl = handler.add_biz_condition(Search()).to_dict()

    assert not _contains_match_none(dsl)
    assert any(node.get("term", {}).get("assignee") == "admin" for node in _walk_dsl(dsl))


@pytest.mark.parametrize(
    ("visible_result", "expected_biz_ids", "expected_tenant_wide"),
    [
        (VisibleResult(all_granted=True, visible_ids=("1", "2")), [1, 2], True),
        (VisibleResult(all_granted=False, visible_ids=("1",)), [1], False),
    ],
)
def test_filter_space_list_by_action_reports_trusted_scope(
    monkeypatch, visible_result, expected_biz_ids, expected_tenant_wide
):
    spaces = [{"bk_biz_id": 1}, {"bk_biz_id": 2}]
    monkeypatch.setattr(
        "bkmonitor.iam.permission.SpaceApi.list_spaces_dict",
        lambda **kwargs: spaces,
    )

    permission = Permission.__new__(Permission)
    permission.bk_tenant_id = TENANT_ID
    permission.username = "admin"
    permission.skip_check = False
    monkeypatch.setattr(permission, "filter_visible_resources", lambda subject, action_id, candidates: visible_result)

    authorized_spaces, tenant_wide_authorized = permission.filter_space_list_by_action_with_scope(
        ActionEnum.VIEW_BUSINESS
    )

    assert [space["bk_biz_id"] for space in authorized_spaces] == expected_biz_ids
    assert tenant_wide_authorized is expected_tenant_wide


def test_filter_space_list_by_action_reports_skip_check_as_trusted_scope(monkeypatch):
    spaces = [{"bk_biz_id": 1}, {"bk_biz_id": 2}]
    monkeypatch.setattr(
        "bkmonitor.iam.permission.SpaceApi.list_spaces_dict",
        lambda **kwargs: spaces,
    )

    permission = Permission.__new__(Permission)
    permission.bk_tenant_id = TENANT_ID
    permission.skip_check = True

    authorized_spaces, tenant_wide_authorized = permission.filter_space_list_by_action_with_scope(
        ActionEnum.VIEW_BUSINESS
    )

    assert authorized_spaces == spaces
    assert tenant_wide_authorized is True


def test_filter_space_list_by_action_keeps_list_return_contract(monkeypatch):
    spaces = [{"bk_biz_id": 1}, {"bk_biz_id": 2}]
    monkeypatch.setattr(
        "bkmonitor.iam.permission.SpaceApi.list_spaces_dict",
        lambda **kwargs: spaces,
    )

    permission = Permission.__new__(Permission)
    permission.bk_tenant_id = TENANT_ID
    permission.skip_check = True

    assert permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS) == spaces


# ---------------------------------------------------------------------------
# 权限候选收窄：显式业务列表只针对请求的业务构造候选（避免全租户空间的 O(N) 计算）
# ---------------------------------------------------------------------------


def test_parse_biz_item_narrows_candidates_for_explicit_biz_list(monkeypatch):
    request = _patch_request(monkeypatch)
    captured = {}

    class FakePermission:
        def __init__(self, username, bk_tenant_id):
            pass

        def filter_space_list_by_action_with_scope(self, action, candidate_biz_ids=None):
            assert action == ActionEnum.VIEW_BUSINESS
            captured["candidates"] = candidate_biz_ids
            # 故意多返回一个未请求的业务，验证结果仍按请求集合收敛
            return [{"bk_biz_id": biz_id} for biz_id in (1, 2, 8, -12)], True

    monkeypatch.setattr(base_handler_module, "Permission", FakePermission, raising=False)

    authorized_bizs, unauthorized_bizs = BaseBizQueryHandler.parse_biz_item([1, 2, 3, -12])

    # 只把请求的业务交给 IAM 构造候选（顺序不作保证，按集合比较）
    assert sorted(captured["candidates"]) == [-12, 1, 2, 3]
    # 结果仍为「请求的业务 ∩ 有权限的业务」，与旧实现一致
    assert sorted(authorized_bizs) == [-12, 1, 2]
    assert unauthorized_bizs == [3]
    # 收窄后的 all_granted 不具备全租户语义，不得写入 tenant_wide 标记
    assert getattr(request, TENANT_WIDE_AUTHORIZED_REQUEST_ATTR) is False


def test_parse_biz_item_all_biz_marker_keeps_full_candidates(monkeypatch):
    request = _patch_request(monkeypatch)
    captured = {}

    class FakePermission:
        def __init__(self, username, bk_tenant_id):
            pass

        def filter_space_list_by_action_with_scope(self, action, candidate_biz_ids=None):
            captured["candidates"] = candidate_biz_ids
            return [{"bk_biz_id": 1}, {"bk_biz_id": 2}], True

    monkeypatch.setattr(base_handler_module, "Permission", FakePermission, raising=False)

    authorized_bizs, unauthorized_bizs = BaseBizQueryHandler.parse_biz_item([-1])

    # 全业务请求仍走全量候选，tenant_wide 语义不受影响
    assert captured["candidates"] is None
    assert authorized_bizs == [1, 2]
    assert unauthorized_bizs == []
    assert getattr(request, TENANT_WIDE_AUTHORIZED_REQUEST_ATTR) is True


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.description = [("id",), ("bk_tenant_id",), ("space_type_id",), ("space_id",)]
        self.executed = None

    def execute(self, sql, params):
        self.executed = (sql, params)

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeConnections:
    def __init__(self, cursor):
        self._cursor = cursor

    def __getitem__(self, alias):
        return SimpleNamespace(cursor=lambda: self._cursor)


def test_list_space_dicts_by_biz_ids_maps_negative_ids_and_filters_tenant(monkeypatch):
    from bkmonitor.space import space_api

    cursor = _FakeCursor(
        [
            (7, "tenant-a", "bkcc", "5000140"),  # 正数业务
            (12, "tenant-a", "bklog", "9"),  # 非 CMDB 空间 → bk_biz_id = -12
            (13, "tenant-b", "bklog", "9"),  # 其他租户，应被过滤
        ]
    )
    monkeypatch.setattr(space_api, "connections", _FakeConnections(cursor))

    result = space_api.InjectSpaceApi.list_space_dicts_by_biz_ids([5000140, -12, -13], bk_tenant_id="tenant-a")

    assert result == [{"bk_biz_id": 5000140}, {"bk_biz_id": -12}]
    sql, params = cursor.executed
    # 正数按 bkcc + space_id 查，负数按 id 查
    assert "s.space_type_id = %s AND s.space_id IN" in sql
    assert "s.id IN" in sql
    # space_type_id 为 NULL 的历史数据也属于非 CMDB 空间，不能被 != 过滤掉
    assert "s.space_type_id IS NULL" in sql
    assert "5000140" in params and 12 in params and 13 in params


def test_list_space_dicts_by_biz_ids_empty_input_skips_query(monkeypatch):
    from bkmonitor.space import space_api

    class _Boom:
        def __getitem__(self, alias):
            raise AssertionError("空入参不应触发 SQL")

    monkeypatch.setattr(space_api, "connections", _Boom())

    assert space_api.InjectSpaceApi.list_space_dicts_by_biz_ids([]) == []


def test_parse_biz_item_normalizes_string_biz_ids(monkeypatch):
    """字符串型 biz_id 也要归一化为 int，避免集合求交时被静默判成"全部无权限"。"""
    _patch_request(monkeypatch)
    captured = {}

    class FakePermission:
        def __init__(self, username, bk_tenant_id):
            pass

        def filter_space_list_by_action_with_scope(self, action, candidate_biz_ids=None):
            captured["candidates"] = candidate_biz_ids
            return [{"bk_biz_id": 1}, {"bk_biz_id": 2}], False

    monkeypatch.setattr(base_handler_module, "Permission", FakePermission, raising=False)

    authorized_bizs, unauthorized_bizs = BaseBizQueryHandler.parse_biz_item(["1", "2", "3"])

    assert sorted(captured["candidates"]) == [1, 2, 3]
    assert sorted(authorized_bizs) == [1, 2]
    assert unauthorized_bizs == [3]


def test_parse_biz_item_falls_back_when_narrowed_query_fails(monkeypatch, caplog):
    """收窄查询异常时退回全量路径，失败模式与改造前一致。"""
    import logging

    _patch_request(monkeypatch)
    calls = []

    class FakePermission:
        def __init__(self, username, bk_tenant_id):
            pass

        def filter_space_list_by_action_with_scope(self, action, candidate_biz_ids=None):
            calls.append(candidate_biz_ids)
            if candidate_biz_ids is not None:
                raise RuntimeError("monitor_api db unavailable")
            return [{"bk_biz_id": biz_id} for biz_id in (1, 2, 3)], False

    monkeypatch.setattr(base_handler_module, "Permission", FakePermission, raising=False)

    with caplog.at_level(logging.WARNING):
        authorized_bizs, unauthorized_bizs = BaseBizQueryHandler.parse_biz_item([1, 2, 9])

    assert len(calls) == 2
    assert calls[0] is not None and sorted(calls[0]) == [1, 2, 9]
    assert calls[1] is None  # 退回全量路径
    assert sorted(authorized_bizs) == [1, 2]
    assert unauthorized_bizs == [9]
    assert any("fallback to full space list" in record.getMessage() for record in caplog.records)
