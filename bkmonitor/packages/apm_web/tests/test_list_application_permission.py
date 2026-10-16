"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace
from unittest import mock

from bkmonitor.iam.handlers.resolver import MonitorResourceResolver
from iam_engine.core.requests import ResourceInstance

import pytest
from rest_framework.response import Response

from apm_web.meta.resources import ListApplicationResource
from apm_web.meta.views import ApplicationViewSet
from apm_web.models import Application
from bkmonitor.iam import ActionEnum, Permission, ResourceEnum
from bkmonitor.iam.drf import sort_result_list_allowed_first


ACTIONS = [ActionEnum.MANAGE_APM_APPLICATION, ActionEnum.VIEW_APM_APPLICATION]


@pytest.fixture(autouse=True)
def product_request(monkeypatch):
    request = SimpleNamespace(user=SimpleNamespace(username="alice", tenant_id="system"), token=None, skip_check=False)
    monkeypatch.setattr("bkmonitor.iam.drf.get_request", lambda **kwargs: request)


def init_permission(instance, *args, **kwargs):
    instance.username = "alice"
    instance.bk_tenant_id = "system"
    instance.request = kwargs.get("request")
    instance.skip_check = False


def expected_permissions(row):
    return dict(row)


def serialize_applications():
    applications = [
        Application(
            application_id=1001,
            bk_biz_id=2,
            app_name="alpha",
            app_alias="Alpha",
            description="",
            trace_result_table_id="trace",
            metric_result_table_id="metric",
        ),
        Application(
            application_id=1002,
            bk_biz_id=2,
            app_name="beta",
            app_alias="Beta",
            description="description",
            trace_result_table_id="",
            metric_result_table_id="",
        ),
    ]
    return list(ListApplicationResource.ApplicationSerializer(applications, many=True).data)


def decorate_response(response_data):
    route = next(route for route in ApplicationViewSet.resource_routes if route.endpoint == "list_application")
    return route.decorators[0](lambda: Response(response_data))


def create_old_and_new_resources(item):
    with mock.patch("monitor_web.iam.views.ApmApplicationProvider._get_app_simple_info_by_id_or_none", return_value=item):
        old_resource = ResourceEnum.APM_APPLICATION.create_simple_instance(item["application_id"])
    new_resource = ResourceEnum.APM_APPLICATION.create_instance_by_info(item)
    from bkmonitor.iam.resource import to_resource_instance
    return to_resource_instance(old_resource), to_resource_instance(new_resource)


def test_list_application_permission_reuses_response_metadata():
    applications = serialize_applications()
    assert {"application_id", "app_name", "bk_biz_id"} <= applications[0].keys()

    response_data = {"columns": [], "total": len(applications), "data": applications}
    decorated_view = decorate_response(response_data)
    permission_result = {
        "1001": {
            ActionEnum.VIEW_APM_APPLICATION.id: True,
            ActionEnum.MANAGE_APM_APPLICATION.id: False,
        },
        "1002": {
            ActionEnum.VIEW_APM_APPLICATION.id: False,
            ActionEnum.MANAGE_APM_APPLICATION.id: True,
        },
    }

    with (
        mock.patch.object(Permission, "__init__", autospec=True, side_effect=init_permission),
        mock.patch(
            "bkmonitor.iam.handlers.resolver.catalog.fetch_instance_info",
            side_effect=AssertionError("list metadata must skip lookup"),
        ) as application_lookup,
        mock.patch.object(Permission, "batch_is_allowed", return_value=permission_result) as batch_is_allowed,
    ):
        response = decorated_view()

    application_lookup.assert_not_called()
    assert response.data["data"][0]["permission"] == expected_permissions(permission_result["1001"])
    assert response.data["data"][1]["permission"] == expected_permissions(permission_result["1002"])
    assert response.data["total"] == 2
    assert [item["application_id"] for item in response.data["data"]] == [1001, 1002]

    batch_is_allowed.assert_called_once()
    assert batch_is_allowed.call_args.args[0] == ACTIONS
    resources = [group[0] for group in batch_is_allowed.call_args.args[1]]
    assert len(resources) == 2
    assert resources[0].id == "1001"
    assert resources[0].attributes == {
        "id": 1001,
        "name": "alpha",
        "bk_biz_id": "2",
        "_bk_iam_path_": "/space,2/",
    }
    assert resources[0].ancestor_chain == (ResourceInstance(type="space", id="2"),)
    assert resources[1].id == "1002"
    assert resources[1].attributes["name"] == "beta"


def test_list_application_permission_keeps_empty_response():
    response_data = {"columns": [], "total": 0, "data": []}
    decorated_view = decorate_response(response_data)

    with mock.patch.object(Permission, "__init__", side_effect=AssertionError("empty response must skip IAM")):
        response = decorated_view()

    assert response.data == response_data


@pytest.mark.parametrize("missing_field", ["application_id", "app_name", "bk_biz_id"])
def test_list_application_permission_fails_when_resource_field_is_missing(missing_field):
    application = serialize_applications()[0]
    application.pop(missing_field)
    decorated_view = decorate_response({"columns": [], "total": 1, "data": [application]})

    with pytest.raises(KeyError, match=missing_field):
        decorated_view()


def test_list_application_resources_are_equivalent_for_normal_iam():
    resolver = MonitorResourceResolver()
    for item in serialize_applications():
        old_resource, new_resource = create_old_and_new_resources(item)
        with mock.patch.object(resolver, "_get_apm_app_info", return_value=item) as lookup:
            resolved = resolver.resolve(old_resource, tenant_id="system")
            assert resolved.id == new_resource.id
            assert resolved.name == new_resource.name
            assert resolved.ancestor_chain == new_resource.ancestor_chain
            lookup.assert_not_called()
        with mock.patch.object(resolver, "_get_apm_app_info", side_effect=AssertionError("metadata is complete")):
            assert resolver.resolve(new_resource, tenant_id="system") is new_resource


def test_list_application_resources_are_equivalent_when_permission_check_is_skipped():
    old_resources = []
    new_resources = []
    for item in serialize_applications():
        old_resource, new_resource = create_old_and_new_resources(item)
        old_resources.append([old_resource])
        new_resources.append([new_resource])

    permission = Permission.__new__(Permission)
    permission.request = None
    permission.skip_check = True

    old_result = permission.batch_is_allowed(ACTIONS, old_resources)
    new_result = permission.batch_is_allowed(ACTIONS, new_resources)

    assert old_result == new_result
    assert all(all(allowed for allowed in actions.values()) for actions in new_result.values())


def test_list_application_resources_are_equivalent_for_share_token():
    old_resources = []
    new_resources = []
    for item in serialize_applications():
        old_resource, new_resource = create_old_and_new_resources(item)
        old_resources.append([old_resource])
        new_resources.append([new_resource])

    permission = Permission.__new__(Permission)
    permission.request = SimpleNamespace(
        token="synthetic-token",
        user=SimpleNamespace(tenant_id="default"),
    )
    permission.skip_check = False

    with mock.patch(
        "bkmonitor.iam.permission.ApiAuthToken.objects.get",
        return_value=SimpleNamespace(type="apm"),
    ):
        old_result = permission.batch_is_allowed(ACTIONS, old_resources)
        new_result = permission.batch_is_allowed(ACTIONS, new_resources)

    assert old_result == new_result
    for actions in new_result.values():
        assert actions["view_apm_application_v2"] is True
        assert actions["manage_apm_application_v2"] is False


def _build_application(application_id: int, app_name: str) -> Application:
    return Application(
        application_id=application_id,
        bk_biz_id=2,
        app_name=app_name,
        app_alias=app_name,
        description="",
        trace_result_table_id="trace",
        metric_result_table_id="metric",
    )


def test_sort_result_list_allowed_first_keeps_relative_order():
    result_list = [
        {"id": "A", "permission": {ActionEnum.VIEW_APM_APPLICATION.id: False}},
        {"id": "B", "permission": {ActionEnum.VIEW_APM_APPLICATION.id: True}},
        {"id": "C", "permission": {ActionEnum.VIEW_APM_APPLICATION.id: False}},
        {"id": "D", "permission": {ActionEnum.VIEW_APM_APPLICATION.id: True}},
    ]

    sort_result_list_allowed_first(
        result_list,
        ACTIONS,
        ActionEnum.VIEW_APM_APPLICATION,
    )

    assert [item["id"] for item in result_list] == ["B", "D", "A", "C"]


def test_sort_result_list_allowed_first_uses_view_action_by_default():
    result_list = [
        {
            "id": "A",
            "permission": {
                ActionEnum.VIEW_APM_APPLICATION.id: False,
                ActionEnum.MANAGE_APM_APPLICATION.id: True,
            },
        },
        {
            "id": "B",
            "permission": {
                ActionEnum.VIEW_APM_APPLICATION.id: True,
                ActionEnum.MANAGE_APM_APPLICATION.id: False,
            },
        },
    ]

    sort_result_list_allowed_first(result_list, ACTIONS)

    assert [item["id"] for item in result_list] == ["B", "A"]


def test_list_application_permission_sorts_allowed_apps_first():
    applications = list(
        ListApplicationResource.ApplicationSerializer(
            [
                _build_application(1001, "alpha"),
                _build_application(1002, "beta"),
                _build_application(1003, "gamma"),
                _build_application(1004, "delta"),
            ],
            many=True,
        ).data
    )
    response_data = {"columns": [], "total": len(applications), "data": applications}
    decorated_view = decorate_response(response_data)
    permission_result = {
        "1001": {
            ActionEnum.VIEW_APM_APPLICATION.id: False,
            ActionEnum.MANAGE_APM_APPLICATION.id: False,
        },
        "1002": {
            ActionEnum.VIEW_APM_APPLICATION.id: True,
            ActionEnum.MANAGE_APM_APPLICATION.id: False,
        },
        "1003": {
            ActionEnum.VIEW_APM_APPLICATION.id: False,
            ActionEnum.MANAGE_APM_APPLICATION.id: True,
        },
        "1004": {
            ActionEnum.VIEW_APM_APPLICATION.id: True,
            ActionEnum.MANAGE_APM_APPLICATION.id: True,
        },
    }

    with (
        mock.patch.object(Permission, "__init__", autospec=True, side_effect=init_permission),
        mock.patch.object(Permission, "batch_is_allowed", return_value=permission_result),
    ):
        response = decorated_view()

    assert [item["application_id"] for item in response.data["data"]] == [1002, 1004, 1001, 1003]
    assert response.data["total"] == 4
