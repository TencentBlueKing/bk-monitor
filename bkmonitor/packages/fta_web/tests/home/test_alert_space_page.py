from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from elasticsearch_dsl import Search

from bkmonitor.iam.space_page import SpacePageAccess
from fta_web.home import resources as home
from iam_engine.exceptions import ProviderUnavailable


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
    monkeypatch.setattr(home.BizWithAlertStatisticsResource, "_assigned_biz_ids", assigned)

    def page(tenant, username, params, access, **options):
        assert (tenant, username, options["namespace"]) == ("tenant-a", "alice", "alert:31")
        return {
            "items": [{"bk_biz_id": int(key), "display_name": f"Space {key}"} for key in sorted(access.ids)],
            "next_cursor": None,
        }

    reader = Mock(side_effect=page)
    monkeypatch.setattr(home, "search_space_page", reader)
    return SimpleNamespace(
        run=home.BizWithAlertStatisticsResource().request,
        assigned=assigned,
        reader=reader,
        prepare=prepare,
        request=request,
        permission=permission,
    )


def test_only_alert_recipient_spaces_supplement_visible_directory(selector):
    page = selector.run(mode="page")
    assert page == {"items": [{"bk_biz_id": 7, "bk_biz_name": "Space 7", "has_data": True}], "next_cursor": None}
    selector.permission.assert_called_once_with(username="alice", bk_tenant_id="tenant-a")
    assert not selector.permission.return_value.skip_check
    selector.assigned.assert_called_once_with("alice", "tenant-a", 31, None)


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


def test_assignee_search_scopes_identity_tenant_and_continues_aggregation(monkeypatch, settings):
    settings.ENABLE_MULTI_TENANT_MODE = True
    monkeypatch.setattr(home.AlertDocument, "search", lambda **kwargs: Search(index="alerts"))
    calls = []

    def execute(search):
        dsl = search.to_dict()
        calls.append(dsl)
        ids = range(1, 513) if len(calls) == 1 else [527]
        buckets = [SimpleNamespace(key=SimpleNamespace(biz=i)) for i in ids]
        return SimpleNamespace(
            aggs=SimpleNamespace(
                assigned_spaces=SimpleNamespace(
                    buckets=buckets, after_key=SimpleNamespace(to_dict=lambda: {"biz": 512})
                )
            )
        )

    monkeypatch.setattr(Search, "execute", execute)
    assigned = home.BizWithAlertStatisticsResource._assigned_biz_ids("alice", "tenant-a", 7)
    assert len(assigned) == 513 and {"1", "512", "527"} <= assigned
    assert calls[0]["aggs"]["assigned_spaces"]["composite"]["size"] == 512
    assert calls[1]["aggs"]["assigned_spaces"]["composite"]["after"] == {"biz": 512}
    scoped = calls[0]["query"]["bool"]["filter"]
    assert scoped[0]["bool"]["should"] == [{"term": {"assignee": "alice"}}, {"term": {"appointee": "alice"}}]
    assert {"term": {"bk_tenant_id": "tenant-a"}} in scoped[1]["bool"]["should"]
    assert home.BizWithAlertStatisticsResource._assigned_biz_ids("alice", "tenant-a", 7, frozenset()) == set()
    assert len(calls) == 2
