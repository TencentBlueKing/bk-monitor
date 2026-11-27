from types import SimpleNamespace
from unittest.mock import Mock
import re

import pytest
from django.urls import resolve
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from bkmonitor.iam.space_page import SpacePageAccess, prepare_space_page_access
from bkmonitor.space import space_api
from bkmonitor.space.pinyin import pinyin_search_patterns
from iam_engine.core.config import AuthMode
from iam_engine.core.types import AuthorizedResourceScope
from iam_engine.exceptions import ProviderUnavailable
from monitor_web.commons.biz import resources
from monitor_web.commons.biz.space_page import search_space_page


def space(pk, name):
    return dict(
        id=pk,
        space_type_id="bkci",
        space_id=f"project-{pk}",
        space_name=name,
        space_code="",
        type_name="研发项目",
        bk_biz_id=-pk,
        space_uid=f"bkci__project-{pk}",
    )


@pytest.fixture
def directory(mocker):
    rows = {}
    mocker.patch.object(resources.SpaceApi, "read_space_page_types", return_value={"bkci": "研发项目"})

    def selected(tenant, ids, kind, after, uids):
        return [
            r
            for r in rows.values()
            if r["id"] > after and (ids is None or str(r["bk_biz_id"]) in ids) and (not uids or r["space_uid"] in uids)
        ]

    def keys(tenant, ids, kind, after, *, type_names, space_uids=None, text_filter="", search_pinyin=False):
        for row in selected(tenant, ids, kind, after, space_uids):
            yield tuple(row[k] for k in ("id", "space_type_id", "space_id", "space_name", "space_code", "type_name"))

    def page(tenant, ids, kind, after, limit, *, type_names, space_uids=None, row_ids=None):
        return [r for r in selected(tenant, ids, kind, after, space_uids) if row_ids is None or r["id"] in row_ids][
            :limit
        ]

    search = mocker.patch.object(resources.SpaceApi, "iter_space_search_keys", side_effect=keys)
    hydrate = mocker.patch.object(resources.SpaceApi, "read_space_page_candidates", side_effect=page)
    return rows, search, hydrate


def query(access=None, *, username="alice", **options):
    return search_space_page(
        "tenant", username, {"query": "", "type": "", "page_size": 2, **options}, access or SpacePageAccess(None)
    )


@pytest.mark.parametrize("term", ["蓝鲸", "lanjing", "lj"])
def test_exact_then_partial_order_cursor_and_search_projections(directory, term):
    rows, keys, hydrate = directory
    rows.update({i: r for i, r in enumerate([space(1, "蓝鲸平台"), space(2, "蓝鲸"), space(3, "蓝鲸服务")], 1)})
    first = query(query=term, page_size=1)
    second = query(query=term, page_size=1, cursor=first["next_cursor"])
    third = query(query=term, page_size=1, cursor=second["next_cursor"])
    assert [p["items"][0]["id"] for p in [first, second, third]] == [2, 1, 3]
    assert third["next_cursor"] is None
    assert keys.call_count == 1
    assert all(c.kwargs["row_ids"] for c in hydrate.call_args_list)


def test_cursor_rechecks_current_access_and_names_and_is_query_bound(directory):
    rows, _, _ = directory
    rows.update({i: space(i, "目标") for i in range(1, 5)})
    first = query(query="目标", page_size=1)
    rows[3]["space_name"] = "已更名"
    answer = query(SpacePageAccess(frozenset({"-1", "-3", "-4"})), query="目标", cursor=first["next_cursor"])
    assert [r["id"] for r in answer["items"]] == [4]
    assert answer["next_cursor"] is None
    for changes in [{"username": "bob"}, {"query": "已更名"}, {"type": "bkci"}, {"bk_biz_ids": {"-1"}}]:
        with pytest.raises(ValidationError):
            query(**{"query": "目标", **changes}, cursor=first["next_cursor"])
    with pytest.raises(ValidationError):
        query(cursor=first["next_cursor"] + "x")


def test_no_query_paginates_after_permission_and_filters_restore_ids(directory):
    rows, keys, _ = directory
    rows.update({i: space(i, "名字") for i in range(1, 305)})
    scope = SpacePageAccess(matches_policy=lambda key: int(key) % 100 == 0)
    first = query(scope)
    second = query(scope, cursor=first["next_cursor"])
    assert [r["bk_biz_id"] for r in first["items"] + second["items"]] == [-100, -200, -300]
    assert second["next_cursor"] is None
    keys.assert_not_called()
    assert [r["id"] for r in query(scope, bk_biz_ids={"-200", "-201"})["items"]] == [200]
    assert [r["id"] for r in query(scope, space_uids={"bkci__project-200", "bkci__project-201"})["items"]] == [200]


def test_many_matches_continue_across_window_boundary_without_duplicates(directory):
    rows, _, _ = directory
    rows.update({i: space(i, "蓝鲸" if i % 3 == 0 else "蓝鲸项目") for i in range(1, 194)})
    ids, cursor = [], None
    while True:
        page = query(query="蓝鲸", page_size=16, cursor=cursor)
        ids.extend(row["id"] for row in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert ids == sorted(rows, key=lambda pk: (pk % 3 != 0, pk))


@pytest.mark.parametrize(
    "params",
    [
        {"page_size": 101},
        {"bk_biz_ids": "1,not-numeric"},
        {"space_uids": "bad"},
        {"bk_biz_ids": "1", "space_uids": "bkci__a"},
        {"show_all": True},
        {"bk_biz_ids": ",".join(map(str, range(101)))},
    ],
)
def test_page_parameters_reject_invalid_inputs(params):
    serial = resources.ListSpacesResource.RequestSerializer(data={"bk_tenant_id": "tenant", "mode": "page", **params})
    assert not serial.is_valid()


@pytest.mark.parametrize("mode", [AuthMode.V3, AuthMode.V4, AuthMode.UNION])
def test_finite_grants_use_each_selected_provider_once(mode):
    perm = Mock(username="alice", bk_tenant_id="tenant")
    perm.mode_provider.get_mode.return_value = mode
    v3, v4 = Mock(), Mock()
    v3.query_policy.return_value = {"op": "in", "field": "space.id", "value": ["4", "-5", 8]}
    v4.list_authorized_resources.return_value = AuthorizedResourceScope.concrete("space", {"9"}, provider_name="v4")
    perm.get_provider.side_effect = lambda k: {"v3": v3, "v4": v4}[k]
    access = prepare_space_page_access(perm)
    assert access.ids == {"v3": {"4", "-5"}, "v4": {"9"}, "union": {"4", "-5", "9"}}[mode.value]
    assert not access.allows("8")
    assert v3.query_policy.call_count == int(mode is not AuthMode.V4)
    assert v4.list_authorized_resources.call_count == int(mode is not AuthMode.V3)


def test_complex_policy_uses_sdk_once_and_union_failures_remain_visible(directory):
    rows, _, _ = directory
    rows.update({i: space(i, "x") for i in range(1, 6)})
    perm = Mock(username="alice", bk_tenant_id="tenant")
    perm.mode_provider.get_mode.return_value = AuthMode.UNION
    v3, v4 = Mock(), Mock()
    perm.get_provider.side_effect = lambda k: {"v3": v3, "v4": v4}[k]
    v3.query_policy.return_value = {
        "op": "OR",
        "content": [{"op": "eq", "field": "space.id", "value": "-2"}, {"op": "eq", "field": "space.id", "value": "-4"}],
    }
    v4.list_authorized_resources.side_effect = RuntimeError("unavailable")
    access = prepare_space_page_access(perm)
    assert [r["id"] for r in query(access)["items"]] == [2, 4]
    assert query(access)["partial"] is True
    v3.query_policy.assert_called_once()
    with pytest.raises(ProviderUnavailable):
        query(access, bk_biz_ids={"-5"})
    v3.query_policy.side_effect = RuntimeError("unavailable")
    with pytest.raises(ProviderUnavailable):
        prepare_space_page_access(perm)


@pytest.mark.parametrize("external", [False, True])
def test_public_get_restores_only_visible_rows_with_the_request_identity(directory, mocker, external):
    rows, _, _ = directory
    rows.update({i: space(i, "业务") for i in range(1, 5)})
    mocker.patch.object(
        resources, "get_request", return_value=SimpleNamespace(external_user="guest" if external else None)
    )
    mocker.patch.object(resources, "get_request_username", return_value="signed-in")
    mocker.patch("bkmonitor.utils.serializers.get_request_tenant_id", return_value="tenant")
    permission = mocker.patch.object(resources, "Permission")
    access = mocker.patch.object(
        resources, "prepare_space_page_access", return_value=SpacePageAccess(frozenset({"-2"}))
    )
    grants = mocker.patch.object(resources.ListSpacesResource, "external_permissions")
    grants.return_value.values_list.return_value.distinct.return_value = [-4]
    route = "/rest/v2/commons/list_spaces/"
    request = APIRequestFactory().get(route, {"mode": "page", "bk_biz_ids": "-1,-2,-4", "bk_tenant_id": "other"})
    force_authenticate(request, user=mocker.Mock(is_authenticated=True))
    response = resolve(route).func(request)
    response.render()
    assert response.status_code == 200
    assert response.data == {"items": [rows[4 if external else 2]], "next_cursor": None}
    if external:
        access.assert_not_called()
        grants.assert_called_once_with("guest")
    else:
        permission.assert_called_once_with(username="signed-in", bk_tenant_id="tenant")
        grants.assert_not_called()


@pytest.mark.parametrize("name,term", [("重庆", "chongqing"), ("重庆", "cq"), ("银行", "yinhang"), ("A蓝鲸", "alj")])
def test_phonetic_prefilter_keeps_polyphones_initials_and_mixed_names(name, term):
    assert all(re.search(pattern, name, re.I) for pattern in pinyin_search_patterns(term))


@pytest.mark.parametrize("version", [(5, 7), (8, 0)])
def test_legacy_mysql_keeps_complete_phonetic_candidates(mocker, version):
    conn = mocker.MagicMock(mysql_version=version, mysql_is_mariadb=False)
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [(4, "bkci", "project", "蓝鲸", "")]
    mocker.patch.object(space_api, "connections", {"monitor_api": conn})
    result = list(
        space_api.InjectSpaceApi.iter_space_search_keys(
            "tenant",
            None,
            "",
            0,
            type_names={"bkci": "研发项目"},
            text_filter="lj",
            search_pinyin=True,
        )
    )
    sql, _ = cursor.execute.call_args.args
    assert ("REGEXP" in sql) == (version >= (8, 0))
    assert ("LOCATE" in sql) == (version >= (8, 0))
    assert result == [(4, "bkci", "project", "蓝鲸", "", "研发项目")]


def test_demo_bookmarks_stay_in_the_visible_id_filter(settings):
    settings.DEMO_BIZ_ID = 7
    serial = resources.ListSpacesResource.RequestSerializer(
        data={"mode": "page", "bk_tenant_id": "tenant", "bk_biz_ids": "9", "include_demo": 1}
    )
    assert serial.is_valid(), serial.errors
    assert serial.validated_data["bk_biz_ids"] == {"7", "9"}
