"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace
from unittest import mock

import pytest

from apm_web.meta.views import ApplicationViewSet
from bkmonitor.iam import ActionEnum


def build_viewset(action: str, data: dict):
    viewset = ApplicationViewSet()
    viewset.action = action
    viewset.kwargs = {}
    viewset.request = SimpleNamespace(method="POST", data=data, query_params={}, biz_id=data.get("bk_biz_id"))
    return viewset


@pytest.mark.parametrize(
    ("action", "data"),
    [
        ("modify_metric", {"bk_biz_id": 2, "application_id": 1}),
        ("delete_application", {"bk_biz_id": 2, "app_name": "demo"}),
        ("custom_service_config", {"bk_biz_id": 2, "app_name": "demo"}),
        ("delete_custom_service", {"bk_biz_id": 2, "id": 1}),
    ],
)
def test_application_write_actions_require_manage_permission(action, data):
    permissions = build_viewset(action, data).get_permissions()

    assert len(permissions) == 1
    assert [item.id for item in permissions[0].actions] == [ActionEnum.MANAGE_APM_APPLICATION.id]


@mock.patch("bkmonitor.iam.drf.Permission")
@mock.patch("apm_web.meta.views.Application.objects")
@mock.patch("apm_web.meta.views.ApplicationCustomService")
def test_delete_custom_service_permission_resolves_owning_application(
    custom_service_model, application_objects, permission_mock
):
    custom_service_model.objects.only.return_value.filter.return_value.first.return_value = SimpleNamespace(
        bk_biz_id=2, app_name="demo"
    )
    application_objects.only.return_value.filter.return_value.first.return_value = SimpleNamespace(application_id=9)
    permission_mock.return_value.is_allowed.return_value = True
    viewset = build_viewset("delete_custom_service", {"bk_biz_id": 2, "id": 1})
    permission = viewset.get_permissions()[0]

    assert permission.has_permission(viewset.request, viewset) is True

    custom_service_model.objects.only.return_value.filter.assert_called_once_with(id=1, bk_biz_id=2)
    checked_resource = permission_mock.return_value.is_allowed.call_args[1]["resources"][0]
    assert str(checked_resource.id) == "9"
