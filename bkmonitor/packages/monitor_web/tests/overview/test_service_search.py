import threading
from unittest import mock

import pytest

from apm_web.constants import CustomServiceMatchType
from bkmonitor.iam.action import ActionEnum
from monitor_web.overview.search import ApmServiceSearchItem, Searcher


def app(biz=2, name="unrelated_app", app_id=1, profiling=True):
    return {
        "bk_biz_id": biz,
        "app_name": name,
        "application_id": app_id,
        "is_enabled_profiling": profiling,
    }


def service(name="demo_v4_test", application="unrelated_app"):
    return {"app_name": application, "service_name": name}


def test_service_search_uses_application_permission_without_application_name_filter():
    applications = [app(), app(3, "private", 2)]
    qs = mock.MagicMock()
    qs.order_by.return_value.values.return_value = applications
    with (
        mock.patch("monitor_web.overview.search.Application.objects.filter", return_value=qs) as query,
        mock.patch(
            "monitor_web.overview.search.filter_data_by_permission", return_value=applications[:1]
        ) as permission,
    ):
        assert ApmServiceSearchItem._get_allowed_applications("tenant", "user") == applications[:1]
    query.assert_called_once_with(bk_tenant_id="tenant")
    assert permission.call_args.kwargs["data"] == applications
    assert permission.call_args.kwargs["actions"] == [ActionEnum.VIEW_APM_APPLICATION]
    assert permission.call_args.kwargs["username"] == "user"
    assert permission.call_args.kwargs["bk_tenant_id"] == "tenant"


def test_service_search_is_cross_business_and_merges_duplicate_sources():
    with (
        mock.patch.object(ApmServiceSearchItem, "_get_allowed_applications", return_value=[app(), app(3, app_id=2)]),
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
        mock.patch.object(ApmServiceSearchItem, "_get_allowed_applications", return_value=[]),
        mock.patch.object(ApmServiceSearchItem, "_search_services") as search,
    ):
        assert list(ApmServiceSearchItem.search("tenant", "user", "demo_v4")) == []
    search.assert_not_called()


def test_batch_query_keeps_business_scope_and_stops_at_limit():
    applications = [app(name=f"app_{i}", app_id=i) for i in range(101)] + [app(3, app_id=200)]
    with (
        mock.patch.object(ApmServiceSearchItem, "_get_allowed_applications", return_value=applications),
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
        mock.patch.object(ApmServiceSearchItem, "_get_allowed_applications", return_value=[app(), app(3, app_id=2)]),
        mock.patch.object(ApmServiceSearchItem, "_search_services", side_effect=cancel) as search,
        mock.patch.object(ApmServiceSearchItem, "_get_biz_name", return_value="业务"),
    ):
        snapshots = list(ApmServiceSearchItem.search("tenant", "user", "demo", stop_event=stop))
    # 已发起的批次可以完成，停止信号阻止后续批次；调度器负责丢弃停止后的结果。
    assert len(snapshots) == (0 if already_stopped else 1)
    assert search.call_count == (0 if already_stopped else 1)


def test_batch_queries_only_authorized_apps_and_enabled_profiling():
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
        result = ApmServiceSearchItem._search_services(
            2, [app(), app(name="trace_only", profiling=False)], "demo_v4", 20
        )
    backend.assert_called_once_with(
        bk_biz_id=2,
        app_names=["unrelated_app", "trace_only"],
        profiling_app_names=["unrelated_app"],
        query="demo_v4",
        limit=20,
    )
    custom.assert_called_once_with(
        bk_biz_id=2, app_name__in=["unrelated_app", "trace_only"], match_type=CustomServiceMatchType.MANUAL
    )
    assert result == [service(), service("http:demo_v4")]


def test_failed_service_search_does_not_block_other_categories():
    class OtherItem:
        match = staticmethod(lambda query: True)
        search = staticmethod(lambda *args, **kwargs: [{"type": "other", "items": []}])

    with (
        mock.patch.object(Searcher, "search_items", [ApmServiceSearchItem, OtherItem]),
        mock.patch.object(ApmServiceSearchItem, "_get_allowed_applications", side_effect=RuntimeError("unavailable")),
    ):
        assert list(Searcher("tenant", "user").search("demo_v4")) == [{"type": "other", "items": []}]
