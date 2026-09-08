import threading
from unittest import mock

from bkmonitor.iam.action import ActionEnum
from monitor_web.overview.search import ApmApplicationSearchItem, ApmServiceSearchItem, Searcher


def app(biz=2, name="app", app_id=1):
    return {
        "bk_biz_id": biz,
        "app_name": name,
        "application_id": app_id,
    }


def service(biz=2, application="app", name="demo"):
    return {"bk_biz_id": biz, "app_name": application, "service_name": name}


def test_match_reuses_application_search():
    assert ApmServiceSearchItem.match("demo_v4")
    assert ApmServiceSearchItem.match("demo_v4") == ApmApplicationSearchItem.match("demo_v4")


def test_list_applications_keeps_exact_service_pairs():
    qs = mock.MagicMock()
    qs.order_by.return_value.values.return_value = [
        app(2, "app_a", 1),
        app(2, "app_b", 2),
        app(3, "app_b", 3),
    ]
    with mock.patch("monitor_web.overview.search.Application.objects.filter", return_value=qs) as query:
        assert ApmServiceSearchItem._list_applications(
            "tenant",
            [service(2, "app_a"), service(3, "app_b")],
        ) == [app(2, "app_a", 1), app(3, "app_b", 3)]
    query.assert_called_once_with(bk_tenant_id="tenant", bk_biz_id__in={2, 3}, app_name__in={"app_a", "app_b"})


def test_no_business_permission_does_not_query_services():
    with (
        mock.patch.object(ApmServiceSearchItem, "_get_allowed_bk_biz_ids", return_value=[]),
        mock.patch("monitor_web.overview.search.api.apm_api.search_service_names") as backend,
        mock.patch.object(ApmServiceSearchItem, "_list_applications") as list_apps,
        mock.patch("monitor_web.overview.search.filter_data_by_permission") as permission,
    ):
        assert ApmServiceSearchItem.search("tenant", "user", "demo") is None
    backend.assert_not_called()
    list_apps.assert_not_called()
    permission.assert_not_called()


def test_already_stopped_does_not_query_services():
    stop = threading.Event()
    stop.set()
    with (
        mock.patch.object(ApmServiceSearchItem, "_get_allowed_bk_biz_ids") as allowed_biz,
        mock.patch("monitor_web.overview.search.api.apm_api.search_service_names") as backend,
    ):
        assert ApmServiceSearchItem.search("tenant", "user", "demo", stop_event=stop) is None
    allowed_biz.assert_not_called()
    backend.assert_not_called()


def test_more_than_100_businesses_omit_biz_filter():
    with (
        mock.patch.object(ApmServiceSearchItem, "_get_allowed_bk_biz_ids", return_value=list(range(1, 102))),
        mock.patch("monitor_web.overview.search.api.apm_api.search_service_names", return_value=[]) as backend,
        mock.patch.object(ApmServiceSearchItem, "_list_applications") as list_apps,
    ):
        assert ApmServiceSearchItem.search("tenant", "user", "demo") is None
    backend.assert_called_once_with(bk_biz_ids=[], query="demo", limit=5)
    list_apps.assert_not_called()


def test_empty_service_hits_skip_application_lookup():
    with (
        mock.patch.object(ApmServiceSearchItem, "_get_allowed_bk_biz_ids", return_value=[2, 3]),
        mock.patch("monitor_web.overview.search.api.apm_api.search_service_names", return_value=[]) as backend,
        mock.patch.object(ApmServiceSearchItem, "_list_applications") as list_apps,
        mock.patch("monitor_web.overview.search.filter_data_by_permission") as permission,
    ):
        assert ApmServiceSearchItem.search("tenant", "user", "demo") is None
    backend.assert_called_once_with(bk_biz_ids=[2, 3], query="demo", limit=5)
    list_apps.assert_not_called()
    permission.assert_not_called()


def test_search_ranks_allowed_applications_first_and_keeps_denied():
    services = [
        service(2, "denied", "svc_b"),
        service(2, "allowed", "svc_a"),
        service(3, "other", "svc_c"),
        service(3, "other", "svc_d"),
    ]
    applications = [app(2, "allowed", 1), app(2, "denied", 2), app(3, "other", 3)]
    with (
        mock.patch.object(ApmServiceSearchItem, "_get_allowed_bk_biz_ids", return_value=[2, 3]),
        mock.patch("monitor_web.overview.search.api.apm_api.search_service_names", return_value=services) as backend,
        mock.patch.object(ApmServiceSearchItem, "_list_applications", return_value=applications) as list_apps,
        mock.patch(
            "monitor_web.overview.search.filter_data_by_permission",
            return_value=[applications[0], applications[2]],
        ) as permission,
        mock.patch.object(ApmServiceSearchItem, "_get_biz_name", side_effect=str),
    ):
        result = ApmServiceSearchItem.search("tenant", "user", "svc", limit=3)
    backend.assert_called_once_with(bk_biz_ids=[2, 3], query="svc", limit=3)
    list_apps.assert_called_once_with("tenant", services)
    assert permission.call_args.kwargs["data"] == applications
    assert permission.call_args.kwargs["actions"] == [ActionEnum.VIEW_APM_APPLICATION]
    assert permission.call_args.kwargs["username"] == "user"
    assert permission.call_args.kwargs["bk_tenant_id"] == "tenant"
    assert result[0]["type"] == "apm_service"
    assert [
        (item["bk_biz_id"], item["app_name"], item["service_name"], item["application_id"], item["name"])
        for item in result[0]["items"]
    ] == [
        (2, "allowed", "svc_a", 1, "svc_a"),
        (3, "other", "svc_c", 3, "svc_c"),
        (3, "other", "svc_d", 3, "svc_d"),
    ]
    assert result[0]["items"][0]["bk_biz_name"] == "2"


def test_permission_denied_services_are_kept_after_allowed():
    services = [service(2, "denied", "svc_b"), service(2, "allowed", "svc_a")]
    applications = [app(2, "allowed", 1), app(2, "denied", 2)]
    with (
        mock.patch.object(ApmServiceSearchItem, "_get_allowed_bk_biz_ids", return_value=[2]),
        mock.patch("monitor_web.overview.search.api.apm_api.search_service_names", return_value=services),
        mock.patch.object(ApmServiceSearchItem, "_list_applications", return_value=applications),
        mock.patch("monitor_web.overview.search.filter_data_by_permission", return_value=[applications[0]]),
        mock.patch.object(ApmServiceSearchItem, "_get_biz_name", side_effect=str),
    ):
        result = ApmServiceSearchItem.search("tenant", "user", "svc", limit=2)
    assert [(item["app_name"], item["service_name"], item["application_id"]) for item in result[0]["items"]] == [
        ("allowed", "svc_a", 1),
        ("denied", "svc_b", 2),
    ]


def test_only_denied_applications_are_still_returned():
    with (
        mock.patch.object(ApmServiceSearchItem, "_get_allowed_bk_biz_ids", return_value=[2]),
        mock.patch("monitor_web.overview.search.api.apm_api.search_service_names", return_value=[service()]),
        mock.patch.object(ApmServiceSearchItem, "_list_applications", return_value=[app()]),
        mock.patch("monitor_web.overview.search.filter_data_by_permission", return_value=[]),
        mock.patch.object(ApmServiceSearchItem, "_get_biz_name", side_effect=str),
    ):
        result = ApmServiceSearchItem.search("tenant", "user", "demo")
    assert [(item["app_name"], item["service_name"], item["application_id"]) for item in result[0]["items"]] == [
        ("app", "demo", 1)
    ]


def test_failed_service_search_does_not_block_other_categories():
    class OtherItem:
        match = staticmethod(lambda query: True)
        search = staticmethod(lambda *args, **kwargs: [{"type": "other", "items": []}])

    with (
        mock.patch.object(Searcher, "search_items", [ApmServiceSearchItem, OtherItem]),
        mock.patch.object(ApmServiceSearchItem, "_get_allowed_bk_biz_ids", side_effect=RuntimeError("unavailable")),
    ):
        assert list(Searcher("tenant", "user").search("demo_v4")) == [{"type": "other", "items": []}]
