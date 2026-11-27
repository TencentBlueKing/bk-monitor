from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from elasticsearch_dsl import Search
from rest_framework.exceptions import ValidationError

from bkmonitor.iam.space_page import SpacePageAccess
from fta_web.home import resources as home
from iam_engine.exceptions import ProviderUnavailable
from monitor_web.commons.biz import space_page


@pytest.fixture
def selector(monkeypatch, settings):
    settings.BLOCK_SPACE_RULE = ""
    monkeypatch.setattr(home, "get_request_tenant_id", lambda: "tenant-a")
    monkeypatch.setattr(home, "get_request_username", lambda: "alice")
    request = SimpleNamespace(external_user=None)
    monkeypatch.setattr(home, "get_request", lambda **kwargs: request)
    permission = Mock(return_value=SimpleNamespace(skip_check=True))
    monkeypatch.setattr(home, "Permission", permission)
    prepare = Mock(return_value=SpacePageAccess(frozenset({"2"})))
    monkeypatch.setattr(home, "prepare_space_page_access", prepare)
    assigned = Mock(return_value={"2", "7"})
    real_assigned = home.BizWithAlertStatisticsResource.__dict__["_assigned_biz_ids"]
    monkeypatch.setattr(home.BizWithAlertStatisticsResource, "_assigned_biz_ids", assigned)

    def page(tenant, username, params, access, **options):
        assert (tenant, username, options["namespace"]) == ("tenant-a", request.external_user or "alice", "alert:31")
        return {
            "items": [{"bk_biz_id": int(key), "display_name": f"Space {key}"} for key in sorted(access.ids)],
            "next_cursor": None,
        }

    reader = Mock(side_effect=page)
    monkeypatch.setattr(home, "search_space_page", reader)
    return SimpleNamespace(
        run=home.BizWithAlertStatisticsResource().request,
        assigned=assigned,
        real_assigned=real_assigned,
        reader=reader,
        prepare=prepare,
        request=request,
        permission=permission,
    )


def test_only_alert_recipient_spaces_supplement_visible_directory(selector, monkeypatch):
    receipt = Mock(return_value=(["2", "7"], None))
    monkeypatch.setattr(home.BizWithAlertStatisticsResource, "_assigned_page", receipt)
    page = selector.run(mode="page")
    assert page == {"items": [{"bk_biz_id": 7, "bk_biz_name": "Space 7", "has_data": True}], "next_cursor": None}
    selector.permission.assert_called_once_with(username="alice", bk_tenant_id="tenant-a")
    assert not selector.permission.return_value.skip_check
    assert receipt.call_args.args[:3] == ("alice", "tenant-a", 31)
    selector.assigned.assert_not_called()


def test_known_labels_keep_original_visibility_and_alert_status(selector):
    rows = selector.run(mode="page", bk_biz_ids="7,13")["items"]
    assert [(row["bk_biz_id"], row["has_data"]) for row in rows] == [(13, False), (7, True)]
    selector.assigned.assert_called_once_with("alice", "tenant-a", 31, frozenset({"7", "13"}))


def test_wildcard_and_blocked_users_have_no_supplemental_list(selector, settings):
    selector.prepare.return_value = SpacePageAccess(None)
    assert selector.run(mode="page") == {"items": [], "next_cursor": None}
    settings.BLOCK_SPACE_RULE = "^alice$"
    selector.prepare.reset_mock()
    assert selector.run(mode="page") == {"items": [], "next_cursor": None}
    selector.prepare.assert_not_called()
    selector.assigned.assert_not_called()


def test_restricted_users_cannot_resolve_arbitrary_labels(selector, settings):
    settings.BLOCK_SPACE_RULE = "^alice$"
    assert [row["bk_biz_id"] for row in selector.run(mode="page", bk_biz_ids="2,7")["items"]] == [2]
    selector.assigned.assert_called_once_with("alice", "tenant-a", 31, frozenset({"2"}))


def test_external_label_lookup_is_limited_to_live_grants_and_requested_ids(selector, monkeypatch):
    grants = Mock()
    monkeypatch.setattr(home.ListSpacesResource, "external_permissions", grants)
    selector.request.external_user = "external-user"
    assert selector.run(mode="page")["items"] == []
    grants.assert_not_called()
    grants.return_value.filter.return_value.values_list.return_value = [7]
    assert [row["bk_biz_id"] for row in selector.run(mode="page", bk_biz_ids="2,7")["items"]] == [7]
    grants.assert_called_once_with("external-user")
    grants.return_value.filter.assert_called_once_with(bk_biz_id__in=frozenset({"2", "7"}))
    selector.permission.assert_not_called()


def test_permission_failure_leaves_alert_only_classification_unknown(selector):
    selector.prepare.return_value = SpacePageAccess(frozenset({"2"}), partial=True)
    with pytest.raises(ProviderUnavailable):
        home.BizWithAlertStatisticsResource().perform_request({"mode": "page", "days": 31})
    selector.assigned.assert_not_called()


def test_legacy_response_keeps_all_three_lists(monkeypatch):
    legacy = {
        "business_list": {2: {"bk_biz_id": 2}},
        "business_with_permission": [{"bk_biz_id": 2}],
        "unauthorized_biz_ids": set(),
    }
    monkeypatch.setattr(home.BizWithAlertStatisticsResource, "get_all_business_list", lambda self: legacy)
    monkeypatch.setattr(home, "get_request_username", lambda: "alice")
    assert home.BizWithAlertStatisticsResource().request() == {
        "business_with_alert": [],
        "business_with_permission": [{"bk_biz_id": 2}],
        "business_list": [{"bk_biz_id": 2}],
    }


def test_received_spaces_read_only_the_requested_windows_and_reauthorize_each_page(
    selector, monkeypatch, settings
):
    settings.ENABLE_MULTI_TENANT_MODE = True
    monkeypatch.setattr(home.AlertDocument, "search", lambda **kwargs: Search(index="alerts"))
    calls = []

    def execute(search):
        dsl = search.to_dict()
        calls.append(dsl)
        window = dsl["aggs"]["assigned_spaces"]["composite"]
        after = window.get("after", {}).get("biz", 0)
        last = min(after + window["size"], 2049)
        ids = range(after + 1, last + 1)
        buckets = [SimpleNamespace(key=SimpleNamespace(biz=i)) for i in ids]
        return SimpleNamespace(
            aggs=SimpleNamespace(
                assigned_spaces=SimpleNamespace(
                    buckets=buckets, after_key=SimpleNamespace(to_dict=lambda: {"biz": last})
                )
            )
        )

    monkeypatch.setattr(Search, "execute", execute)
    first = selector.run(mode="page", page_size=20)
    assert [row["bk_biz_id"] for row in first["items"]] == [1, *range(3, 21)]
    assert len(calls) == 1
    selector.prepare.return_value = SpacePageAccess(frozenset({"2", "25"}))
    second = selector.run(mode="page", page_size=20, cursor=first["next_cursor"])
    assert [row["bk_biz_id"] for row in second["items"]] == [*range(21, 25), *range(26, 41)]
    assert len(calls) == 2 and selector.prepare.call_count == 2
    assert calls[0]["aggs"]["assigned_spaces"]["composite"]["size"] == 20
    assert calls[1]["aggs"]["assigned_spaces"]["composite"]["after"] == {"biz": 20}
    all_ids = [row["bk_biz_id"] for row in first["items"] + second["items"]]
    cursor = second["next_cursor"]
    while cursor:
        result = selector.run(mode="page", page_size=20, cursor=cursor)
        all_ids.extend(row["bk_biz_id"] for row in result["items"])
        cursor = result["next_cursor"]
    assert all_ids == [i for i in range(1, 2050) if i not in (2, 25)]
    assert len(calls) == 103
    scoped = calls[0]["query"]["bool"]["filter"]
    assert scoped[0]["bool"]["should"] == [{"term": {"assignee": "alice"}}, {"term": {"appointee": "alice"}}]
    assert {"term": {"bk_tenant_id": "tenant-a"}} in scoped[1]["bool"]["should"]
    with pytest.raises(ValidationError):
        selector.run(mode="page", cursor=first["next_cursor"], days=7)
    with pytest.raises(ValidationError):
        selector.run(mode="page", cursor=first["next_cursor"], type="bkci")
    with pytest.raises(ValidationError):
        selector.run(mode="page", cursor=first["next_cursor"] + "x")
    with monkeypatch.context() as scoped_patch:
        scoped_patch.setattr(home, "get_request_tenant_id", lambda: "other-tenant")
        with pytest.raises(ValidationError):
            selector.run(mode="page", cursor=first["next_cursor"])
    monkeypatch.setattr(home, "get_request_username", lambda: "other")
    with pytest.raises(ValidationError):
        selector.run(mode="page", cursor=first["next_cursor"])
    assert len(calls) == 103


def test_sparse_receipts_return_a_continuation_after_bounded_empty_windows(selector, monkeypatch):
    selector.prepare.return_value = SpacePageAccess(frozenset(str(i) for i in range(1, 61)))
    receipt = Mock(
        side_effect=[([str(i) for i in range(start, start + 20)], {"biz": start + 19}) for start in (1, 21, 41)]
        + [(["61"], None)]
    )
    monkeypatch.setattr(home.BizWithAlertStatisticsResource, "_assigned_page", receipt)
    first = selector.run(mode="page")
    assert first["items"] == [] and first["next_cursor"] and receipt.call_count == 3
    second = selector.run(mode="page", cursor=first["next_cursor"])
    assert [row["bk_biz_id"] for row in second["items"]] == [61]
    assert second["next_cursor"] is None and receipt.call_count == 4
    assert receipt.call_args.kwargs["after"] == {"biz": 60}


def test_search_reads_ranked_candidates_and_queries_only_their_receipts(selector, monkeypatch):
    monkeypatch.setattr(home.BizWithAlertStatisticsResource, "_assigned_biz_ids", selector.real_assigned)
    monkeypatch.setattr(home, "search_space_page", space_page.search_space_page)
    monkeypatch.setattr(home.SpaceApi, "read_space_page_types", lambda: {"bkcc": "业务"})
    names = {1: "match-1", 3: "match-3", 5: "match", 8: "match"}
    keys = [(key, "bkcc", str(key), name, "", "业务") for key, name in names.items()]
    monkeypatch.setattr(
        home.SpaceApi,
        "iter_space_search_keys",
        lambda _tenant, _ids, _type, after, **kw: (row for row in keys if row[0] > after),
    )

    def hydrate(_tenant, _ids, _type, after, limit, *, row_ids, **kwargs):
        return [
            dict(
                id=i,
                bk_biz_id=i,
                space_type_id="bkcc",
                space_id=str(i),
                space_name=names[i],
                space_code="",
                type_name="业务",
                display_name=names[i],
            )
            for i in sorted(row_ids)
        ][:limit]

    monkeypatch.setattr(home.SpaceApi, "read_space_page_candidates", hydrate)
    monkeypatch.setattr(home.AlertDocument, "search", lambda **kw: Search(index="alerts"))
    received = {3, 8, *range(100, 2147)}
    reads = []

    def execute(search):
        dsl = search.to_dict()
        terms = next(f["terms"]["event.bk_biz_id"] for f in dsl["query"]["bool"]["filter"] if "terms" in f)
        asked = {int(value) for value in terms}
        assert dsl["aggs"]["assigned_spaces"]["composite"]["size"] == len(asked) == 1
        reads.append(asked)
        buckets = [SimpleNamespace(key=SimpleNamespace(biz=i)) for i in received.intersection(asked)]
        return SimpleNamespace(aggs=SimpleNamespace(assigned_spaces=SimpleNamespace(buckets=buckets)))

    monkeypatch.setattr(Search, "execute", execute)
    first = selector.run(mode="page", query="match", page_size=1)
    second = selector.run(mode="page", query="match", page_size=1, cursor=first["next_cursor"])
    assert [row["bk_biz_id"] for row in first["items"] + second["items"]] == [8, 3]
    assert second["next_cursor"] is None
    assert reads == [{5}, {8}, {1}, {3}]
