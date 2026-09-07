import threading
from contextlib import contextmanager
from unittest import mock

import pytest

from apm_web.constants import CustomServiceMatchType
from bkmonitor.iam.action import ActionEnum
from monitor_web.overview.search import ApmServiceSearchItem, Searcher


def app(biz=2, name="unrelated_app", app_id=1):
    return {
        "bk_biz_id": biz,
        "app_name": name,
        "application_id": app_id,
    }


def service(name="demo_v4_test", application="unrelated_app"):
    return {"app_name": application, "service_name": name}


def allow_stage(_tenant, _user, stage):
    return stage


@contextmanager
def patch_search(applications, visits=None, iam=allow_stage):
    visits = visits or set()
    visited = [item for item in applications if (item["bk_biz_id"], item["app_name"]) in visits]
    with (
        mock.patch.object(ApmServiceSearchItem, "_list_visited_applications", return_value=visited),
        mock.patch.object(ApmServiceSearchItem, "_list_applications", return_value=applications),
        mock.patch.object(ApmServiceSearchItem, "_filter_allowed_applications", side_effect=iam),
    ):
        yield


def test_list_applications_does_not_filter_by_application_name():
    applications = [app(), app(3, "private", 2)]
    qs = mock.MagicMock()
    qs.order_by.return_value.values.return_value = applications
    with mock.patch("monitor_web.overview.search.Application.objects.filter", return_value=qs) as query:
        assert ApmServiceSearchItem._list_applications("tenant") == applications
    query.assert_called_once_with(bk_tenant_id="tenant")


def test_empty_visits_skip_application_query():
    visits = mock.MagicMock()
    visits.filter.return_value.values.return_value = [{"bk_biz_id": 2, "app_name": ""}]
    with (
        mock.patch("monitor_web.overview.search.UserVisitRecord.objects", visits),
        mock.patch("monitor_web.overview.search.Application.objects.filter") as query,
    ):
        assert ApmServiceSearchItem._list_visited_applications("tenant", "user") == []
    query.assert_not_called()
    assert visits.filter.call_args.kwargs["created_by"] == "user"


def test_list_visited_applications_keeps_exact_visit_pairs():
    visits = mock.MagicMock()
    visits.filter.return_value.values.return_value = [{"bk_biz_id": 2, "app_name": "visited"}]
    qs = mock.MagicMock()
    qs.order_by.return_value.values.return_value = [app(2, "visited", 1), app(3, "visited", 2)]
    with (
        mock.patch("monitor_web.overview.search.UserVisitRecord.objects", visits),
        mock.patch("monitor_web.overview.search.Application.objects.filter", return_value=qs) as query,
    ):
        assert ApmServiceSearchItem._list_visited_applications("tenant", "user") == [app(2, "visited", 1)]
    query.assert_called_once_with(bk_tenant_id="tenant", bk_biz_id__in={2}, app_name__in={"visited"})


def test_filter_allowed_applications_uses_view_permission():
    applications = [app(), app(3, "private", 2)]
    with mock.patch(
        "monitor_web.overview.search.filter_data_by_permission", return_value=applications[:1]
    ) as permission:
        assert ApmServiceSearchItem._filter_allowed_applications("tenant", "user", applications) == applications[:1]
    assert permission.call_args.kwargs["data"] == applications
    assert permission.call_args.kwargs["actions"] == [ActionEnum.VIEW_APM_APPLICATION]
    assert permission.call_args.kwargs["username"] == "user"
    assert permission.call_args.kwargs["bk_tenant_id"] == "tenant"


def test_empty_application_stage_skips_iam():
    with mock.patch("monitor_web.overview.search.filter_data_by_permission") as permission:
        assert ApmServiceSearchItem._filter_allowed_applications("tenant", "user", []) == []
    permission.assert_not_called()


def test_service_search_is_cross_business_and_merges_duplicate_sources():
    with (
        patch_search([app(), app(3, app_id=2)]),
        mock.patch.object(
            ApmServiceSearchItem,
            "_search_services",
            side_effect=[[service(), service(), service("http:demo_v4")], [service()]],
        ),
        mock.patch.object(ApmServiceSearchItem, "_get_biz_name", side_effect=str),
    ):
        snapshots = list(ApmServiceSearchItem.search("tenant", "user", "demo_v4", current_bk_biz_id=2))
    assert [len(snapshot["items"]) for snapshot in snapshots] == [2, 3]
    assert [(item["bk_biz_id"], item["service_name"]) for item in snapshots[-1]["items"]] == [
        (2, "demo_v4_test"),
        (2, "http:demo_v4"),
        (3, "demo_v4_test"),
    ]
    assert snapshots[-1]["type"] == "apm_service"
    assert snapshots[-1]["items"][0]["app_name"] == "unrelated_app"


def test_permission_denied_does_not_query_services():
    with (
        patch_search([app()], iam=lambda *_: []),
        mock.patch.object(ApmServiceSearchItem, "_search_services") as search,
    ):
        assert list(ApmServiceSearchItem.search("tenant", "user", "demo_v4")) == []
    search.assert_not_called()


def test_recent_visits_are_searched_before_remaining_apps():
    applications = [app(4, "other", 1), app(3, "visited", 2)]
    authorized = []

    def iam(_tenant, _user, stage):
        authorized.append([item["app_name"] for item in stage])
        return stage

    with (
        patch_search(applications, visits={(3, "visited")}, iam=iam),
        mock.patch.object(
            ApmServiceSearchItem,
            "_search_services",
            side_effect=lambda _biz, apps, _query, _limit: [service(application=apps[0]["app_name"])],
        ),
        mock.patch.object(ApmServiceSearchItem, "_get_biz_name", return_value="业务"),
    ):
        snapshots = list(ApmServiceSearchItem.search("tenant", "user", "demo", limit=2))
    assert authorized == [["visited"], ["other"]]
    assert [item["app_name"] for item in snapshots[-1]["items"]] == ["visited", "other"]


def test_visit_results_skip_remaining_application_query():
    with (
        mock.patch.object(ApmServiceSearchItem, "_list_visited_applications", return_value=[app(2, "visited", 1)]),
        mock.patch.object(ApmServiceSearchItem, "_list_applications") as list_all,
        mock.patch.object(ApmServiceSearchItem, "_filter_allowed_applications", side_effect=allow_stage) as iam,
        mock.patch.object(ApmServiceSearchItem, "_search_services", return_value=[service(application="visited")]),
        mock.patch.object(ApmServiceSearchItem, "_get_biz_name", return_value="业务"),
    ):
        result = list(ApmServiceSearchItem.search("tenant", "user", "demo", limit=1))
    assert len(result[-1]["items"]) == 1
    assert iam.call_count == 1
    assert iam.call_args.args[2] == [app(2, "visited", 1)]
    list_all.assert_not_called()


def test_remaining_apps_are_authorized_once():
    applications = [app(name=f"app_{i}", app_id=i) for i in range(3)]
    with (
        patch_search(applications),
        mock.patch.object(ApmServiceSearchItem, "_filter_allowed_applications", side_effect=allow_stage) as iam,
        mock.patch.object(ApmServiceSearchItem, "_search_services", return_value=[]),
    ):
        assert list(ApmServiceSearchItem.search("tenant", "user", "demo")) == []
    assert iam.call_count == 1
    assert iam.call_args.args[2] == applications


def test_batch_query_keeps_business_scope_and_stops_at_limit():
    applications = [app(name=f"app_{i}", app_id=i) for i in range(101)] + [app(3, app_id=200)]
    with (
        patch_search(applications),
        mock.patch.object(
            ApmServiceSearchItem, "_search_services", side_effect=[[], [service(application="app_100")]]
        ) as search,
        mock.patch.object(ApmServiceSearchItem, "_get_biz_name", return_value="业务"),
    ):
        result = list(ApmServiceSearchItem.search("tenant", "user", "demo", limit=1))
    assert len(result[-1]["items"]) == 1
    assert [len(call.args[1]) for call in search.call_args_list] == [100, 1]
    assert [call.args[0] for call in search.call_args_list] == [2, 2]


@pytest.mark.parametrize("already_stopped", [False, True])
def test_search_cancellation_stops_subsequent_batches(already_stopped):
    stop = threading.Event()
    if already_stopped:
        stop.set()

    def cancel(*args):
        stop.set()
        return [service()]

    with (
        patch_search([app(), app(3, app_id=2)]),
        mock.patch.object(ApmServiceSearchItem, "_search_services", side_effect=cancel) as search,
        mock.patch.object(ApmServiceSearchItem, "_get_biz_name", return_value="业务"),
    ):
        snapshots = list(ApmServiceSearchItem.search("tenant", "user", "demo", stop_event=stop))
    # 已发起的批次可以完成，停止信号阻止后续批次；调度器负责丢弃停止后的结果。
    assert len(snapshots) == (0 if already_stopped else 1)
    assert search.call_count == (0 if already_stopped else 1)


def test_batch_queries_only_authorized_apps():
    custom_qs = mock.MagicMock()
    custom_qs.annotate.return_value.filter.return_value.order_by.return_value.values.return_value.distinct.return_value.__getitem__.return_value = [
        service("http:demo_v4")
    ]
    with (
        mock.patch("monitor_web.overview.search.api.apm_api.search_service_names", return_value=[service()]) as backend,
        mock.patch(
            "monitor_web.overview.search.ApplicationCustomService.objects.filter", return_value=custom_qs
        ) as custom,
    ):
        result = ApmServiceSearchItem._search_services(2, [app(), app(name="another_app")], "demo_v4", 20)
    backend.assert_called_once_with(
        bk_biz_id=2,
        app_names=["unrelated_app", "another_app"],
        query="demo_v4",
        limit=20,
    )
    custom.assert_called_once_with(
        bk_biz_id=2, app_name__in=["unrelated_app", "another_app"], match_type=CustomServiceMatchType.MANUAL
    )
    assert result == [service(), service("http:demo_v4")]


def test_failed_service_search_does_not_block_other_categories():
    class OtherItem:
        match = staticmethod(lambda query: True)
        search = staticmethod(lambda *args, **kwargs: [{"type": "other", "items": []}])

    with (
        mock.patch.object(Searcher, "search_items", [ApmServiceSearchItem, OtherItem]),
        mock.patch.object(ApmServiceSearchItem, "_list_visited_applications", return_value=[]),
        mock.patch.object(ApmServiceSearchItem, "_list_applications", side_effect=RuntimeError("unavailable")),
    ):
        assert list(Searcher("tenant", "user").search("demo_v4")) == [{"type": "other", "items": []}]
