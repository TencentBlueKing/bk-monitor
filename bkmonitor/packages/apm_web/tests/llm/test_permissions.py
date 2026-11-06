from types import SimpleNamespace
from unittest import mock

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apm_web.decorators import user_visit_record
from apm_web.llm.views import LLMViewSet
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission
from core.errors.iam import PermissionDeniedError


def build_viewset() -> LLMViewSet:
    viewset = LLMViewSet()
    viewset.request = SimpleNamespace(
        method="POST",
        data={"bk_biz_id": 2, "app_name": "demo"},
        query_params={},
        user=SimpleNamespace(username="alice", tenant_id="system"),
        token=None,
        skip_check=False,
    )
    return viewset


def test_get_permissions_uses_apm_application_permission():
    permission = build_viewset().get_permissions()[0]

    assert isinstance(permission, InstanceActionForDataPermission)
    assert permission.actions == [ActionEnum.VIEW_APM_APPLICATION]
    assert permission.resource_meta == ResourceEnum.APM_APPLICATION


def test_list_traces_and_calculate_by_range_record_user_visits():
    routes = {route.endpoint: route for route in LLMViewSet.resource_routes}

    assert routes["list_traces"].decorators == [user_visit_record]
    assert len(routes["list_flows"].decorators) == 1
    assert routes["calculate_by_range"].decorators == [user_visit_record]
    assert routes["list_spans"].decorators is None
    assert routes["token_statistics"].decorators is None
    assert routes["time_series"].decorators is None


@pytest.mark.parametrize("allowed", [True, False])
@mock.patch("bkmonitor.iam.drf.Permission")
@mock.patch("apm_web.llm.views.Application.get_application_id_by_app_name", return_value=9)
def test_apm_application_permission_result(get_application_id, permission_mock, allowed):
    if allowed:
        permission_mock.return_value._is_allowed_request.return_value = True
    else:
        permission_mock.return_value._is_allowed_request.side_effect = PermissionDeniedError(
            context={"action_name": ActionEnum.VIEW_APM_APPLICATION.name}
        )

    viewset = build_viewset()
    permission = viewset.get_permissions()[0]

    if allowed:
        assert permission.has_permission(viewset.request, viewset) is True
    else:
        with pytest.raises(PermissionDeniedError):
            permission.has_permission(viewset.request, viewset)

    get_application_id.assert_called_once_with("demo")
    assert permission_mock.return_value._is_allowed_request.call_args.args[0].resource.id == "9"


@pytest.mark.parametrize(
    ("prefix", "result", "recorded"),
    [
        ("/apm/llm/", {"traces": [{"flow": [{"span_id": "llm-span"}]}]}, True),
        ("/apm/llm/", {"traces": []}, False),
        ("/apm/llm/", {"traces": [{"flow": []}]}, False),
        ("/api/v4/apm/llm/", {"traces": [{"flow": [{"span_id": "llm-span"}]}]}, False),
    ],
)
def test_list_flows_records_browser_visits_only_for_nonempty_llm_flow(prefix, result, recorded):
    LLMViewSet.generate_endpoint()
    request = APIRequestFactory().post(
        f"{prefix}list_flows/",
        {"bk_biz_id": 2, "app_name": "demo", "group_field": "trace_id", "group_id": "trace-id"},
        format="json",
    )
    request.biz_id = 2
    force_authenticate(request, user=SimpleNamespace(username="alice", is_authenticated=True))
    with (
        mock.patch.object(LLMViewSet, "get_permissions", return_value=[]),
        mock.patch("apm_web.decorators.UserVisitRecord.objects.create") as create,
        mock.patch("apm_web.llm.resources.ListFlowsResource.perform_request", return_value=result),
    ):
        response = LLMViewSet.as_view({"post": "list_flows"})(request)
    assert response.status_code == 200
    assert response.data == result
    if recorded:
        create.assert_called_once_with(
            bk_biz_id=2, app_name="demo", func_name="/apm/llm/list_flows/", created_by="alice"
        )
    else:
        create.assert_not_called()


def test_list_flows_visit_failure_does_not_fail_the_request():
    LLMViewSet.generate_endpoint()
    request = APIRequestFactory().post(
        "/apm/llm/list_flows/",
        {"bk_biz_id": 2, "app_name": "demo", "group_field": "trace_id", "group_id": "trace-id"},
        format="json",
    )
    request.biz_id = 2
    force_authenticate(request, user=SimpleNamespace(username="alice", is_authenticated=True))
    result = {"traces": [{"flow": [{"span_id": "llm-span"}]}]}
    with (
        mock.patch.object(LLMViewSet, "get_permissions", return_value=[]),
        mock.patch("apm_web.decorators.UserVisitRecord.objects.create", side_effect=RuntimeError("write failed")),
        mock.patch("apm_web.llm.resources.ListFlowsResource.perform_request", return_value=result),
    ):
        response = LLMViewSet.as_view({"post": "list_flows"})(request)
    assert response.status_code == 200
    assert response.data == result


@pytest.mark.parametrize("valid", [True, False])
def test_failed_list_flows_requests_do_not_record_visits(valid):
    LLMViewSet.generate_endpoint()
    request = APIRequestFactory().post(
        "/apm/llm/list_flows/",
        {"bk_biz_id": 2, "app_name": "demo"},
        format="json",
    )
    request.biz_id = 2
    force_authenticate(request, user=SimpleNamespace(username="alice", is_authenticated=True))
    permission = mock.Mock()
    permission.has_permission.return_value = valid
    with (
        mock.patch.object(LLMViewSet, "get_permissions", return_value=[permission]),
        mock.patch("apm_web.decorators.UserVisitRecord.objects.create") as create,
    ):
        response = LLMViewSet.as_view({"post": "list_flows"})(request)
    assert response.status_code >= 400
    create.assert_not_called()


@pytest.mark.parametrize("endpoint", ["list_traces", "calculate_by_range"])
def test_existing_visit_routes_keep_recording_without_a_response_condition(endpoint):
    LLMViewSet.generate_endpoint()
    route = next(route for route in LLMViewSet.resource_routes if route.endpoint == endpoint)
    request = APIRequestFactory().post(f"/apm/llm/{endpoint}/", {"bk_biz_id": 2, "app_name": "demo"}, format="json")
    request.biz_id = 2
    force_authenticate(request, user=SimpleNamespace(username="alice", is_authenticated=True))
    with (
        mock.patch.object(LLMViewSet, "get_permissions", return_value=[]),
        mock.patch.object(route.resource_class, "request", return_value={}) as perform,
        mock.patch("apm_web.decorators.UserVisitRecord.objects.create") as create,
    ):
        response = LLMViewSet.as_view({"post": endpoint})(request)
    assert response.status_code == 200
    perform.assert_called_once()
    create.assert_called_once_with(bk_biz_id=2, app_name="demo", func_name=f"/apm/llm/{endpoint}/", created_by="alice")
