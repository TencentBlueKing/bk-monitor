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

import pytest

from bkmonitor.documents import AlertDocument, EventDocument
from bkmonitor.iam import ActionEnum
from core.errors.alert import AlertNotFoundError
from core.errors.iam import PermissionDeniedError
from fta_web.action.resources import backend_resources, frontend_resources
from fta_web.action.views import ActionInstanceViewSet


@pytest.mark.parametrize("allowed_action", [ActionEnum.VIEW_RULE, ActionEnum.MANAGE_EVENT, ActionEnum.MANAGE_RULE])
def test_preview_requires_manage_rule(mocker, allowed_action):
    def is_allowed(action, **kwargs):
        if action != allowed_action:
            raise PermissionDeniedError(action_name=action.name)
        return True

    mocker.patch("bkmonitor.iam.drf.is_biz_in_tenant", return_value=True)
    mocker.patch("bkmonitor.iam.drf.Permission").return_value.is_allowed.side_effect = is_allowed
    view = ActionInstanceViewSet()
    view.action = "preview_demo_action_context"
    request = SimpleNamespace(biz_id=2, user=SimpleNamespace(tenant_id="default"))

    if allowed_action == ActionEnum.MANAGE_RULE:
        view.check_permissions(request)
    else:
        with pytest.raises(PermissionDeniedError):
            view.check_permissions(request)


@pytest.mark.parametrize("can_manage", [False, True])
def test_preview_checks_validated_business_permission(mocker, can_manage):
    request = SimpleNamespace(biz_id=2, user=SimpleNamespace(username="operator", tenant_id="default"))
    mocker.patch.object(frontend_resources, "get_request", return_value=request)
    mocker.patch.object(frontend_resources.resource.space, "get_bk_biz_ids_by_user", return_value=[2, 3])
    permission = mocker.patch("bkmonitor.iam.Permission.is_allowed_by_biz", return_value=True)
    if not can_manage:
        permission.side_effect = PermissionDeniedError(action_name=ActionEnum.MANAGE_RULE.name)
    backend = mocker.patch.object(frontend_resources.api.monitor, "get_demo_action_context_backend")
    data = {"bk_biz_id": 3, "alert_id": "alert-1", "variables": {}}

    if can_manage:
        assert frontend_resources.PreviewDemoActionContextResource().perform_request(data) == backend.return_value
        backend.assert_called_once_with(**data)
    else:
        with pytest.raises(PermissionDeniedError):
            frontend_resources.PreviewDemoActionContextResource().perform_request(data)
        backend.assert_not_called()
    permission.assert_called_once_with(bk_biz_id=3, action=ActionEnum.MANAGE_RULE, raise_exception=True)


@pytest.mark.parametrize("event", [None, EventDocument(), EventDocument(bk_biz_id=3)])
def test_preview_rejects_alert_outside_business_before_loading_context(mocker, event):
    mocker.patch.object(AlertDocument, "mget", return_value=[AlertDocument(id="alert-1", event=event)])
    build_action = mocker.patch.object(backend_resources.GetDemoActionContextResource, "build_fake_action")
    render = mocker.patch.object(backend_resources, "jinja_render")

    with pytest.raises(AlertNotFoundError):
        backend_resources.GetDemoActionContextResource().perform_request(
            {"bk_biz_id": 2, "alert_id": "alert-1", "variables": {"title": "{{ alert.alert_name }}"}}
        )
    build_action.assert_not_called()
    render.assert_not_called()


def test_preview_rejects_missing_alert(mocker):
    mocker.patch.object(AlertDocument, "mget", return_value=[])
    with pytest.raises(AlertNotFoundError):
        backend_resources.GetDemoActionContextResource().perform_request({"bk_biz_id": 2, "alert_id": "alert-1"})


@pytest.mark.parametrize("bk_biz_id", [2, "2", -2, "-2"])
def test_preview_renders_alert_in_requested_business(mocker, bk_biz_id):
    alert = AlertDocument(id="alert-1", event=EventDocument(bk_biz_id=bk_biz_id))
    mocker.patch.object(AlertDocument, "mget", return_value=[alert])
    build_action = mocker.patch.object(backend_resources.GetDemoActionContextResource, "build_fake_action")
    context = mocker.patch.object(backend_resources, "ActionContext")
    context.return_value.get_dictionary.return_value = {"alert": {"alert_name": "test alert"}}

    result = backend_resources.GetDemoActionContextResource().perform_request(
        {"bk_biz_id": int(bk_biz_id), "alert_id": "alert-1", "variables": {"title": "{{ alert.alert_name }}"}}
    )

    assert result == {"variables": {"title": "test alert"}}
    build_action.assert_called_once_with(alert, int(bk_biz_id))
