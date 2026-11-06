"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import importlib.util
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from django.urls import include, path
from rest_framework.exceptions import PermissionDenied, ValidationError

from api.monitor.default import CreateChatGroupActionBackendResource
from bkm_space.api import SpaceApi
from bkmonitor.action.serializers.action import CreateChatGroupSerializer
from bkmonitor.documents import AlertDocument, EventDocument
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.models.fta import ActionPlugin
from bkmonitor.utils.local import local
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from constants.action import ChatMessageType
from core.drf_resource.exceptions import CustomException
from core.drf_resource.contrib import api as api_client, nested_api
from core.drf_resource.routers import ResourceRouter
from core.errors.iam import PermissionDeniedError
from fta_web.action.resources import backend_resources, frontend_resources
from kernel_api.middlewares import authentication


@pytest.fixture
def chat_security(mocker, monkeypatch, settings):
    settings.ENABLE_MULTI_TENANT_MODE = True
    # A global/request exemption must not bypass this operation's per-business checks.
    settings.SKIP_IAM_PERMISSION_CHECK = True
    request = SimpleNamespace(
        user=SimpleNamespace(username="operator", tenant_id="tenant-a"),
        jwt=SimpleNamespace(user={"username": "operator", "verified": True}, app={"app_code": "monitor-web"}),
        META={},
        skip_check=True,
    )
    monkeypatch.setattr(local, "current_request", request, raising=False)
    tenants = {2: "tenant-a", 3: "tenant-a"}

    def get_space(bk_biz_id=None, space_uid=None, **kwargs):
        biz_id = int(bk_biz_id if bk_biz_id is not None else space_uid.split("__")[-1])
        return SimpleNamespace(
            id=biz_id,
            space_uid=f"bkcc__{biz_id}",
            space_type_id="bkcc",
            space_name=f"business-{biz_id}",
            bk_tenant_id=tenants.get(biz_id, "tenant-other"),
        )

    mocker.patch.object(SpaceApi, "get_space_detail", side_effect=get_space)
    bk_biz_id_to_bk_tenant_id.cache_clear()
    monkeypatch.setattr(authentication, "APP_CODE_TOKENS", {"tenant-a": {"monitor-web": ["biz#all"]}})
    monkeypatch.setattr(authentication, "APP_CODE_UPDATE_TIME", {"tenant-a": time.time()})
    token_query = mocker.patch.object(authentication.ApiAuthToken.objects, "filter")

    allowed_biz_ids = {2, 3}
    iam = mocker.Mock()
    iam.is_allowed_with_cache.side_effect = lambda data: int(data.resources[0].id) in allowed_biz_ids
    iam_factory = mocker.patch.object(Permission, "get_iam_client", return_value=iam)
    # Only permission-application UI data is stubbed; the IAM decision and raise path are real.
    mocker.patch.object(Permission, "get_apply_data", return_value=({}, "https://iam.invalid/apply"))
    alerts = [
        AlertDocument(
            id=f"alert-{biz_id}",
            event=EventDocument(bk_biz_id=biz_id, bk_tenant_id="tenant-a"),
            bk_tenant_id="tenant-a",
            strategy_id=0,
            severity=1,
            assignee=["responder"],
        )
        for biz_id in (2, 3)
    ]
    mget = mocker.patch.object(AlertDocument, "mget", return_value=alerts)

    config = SimpleNamespace(
        id=101,
        name="「快捷」一键拉群",
        plugin_id=9,
        is_enabled=True,
        bk_biz_id=0,
        execute_config={"template_id": 11, "timeout": 60},
    )
    config_get = mocker.patch.object(backend_resources.ActionConfig, "objects").get
    config_get.return_value = config
    plugin = ActionPlugin(id=9, name="chat-plugin", plugin_type="chat", plugin_key="chat")
    plugins = mocker.MagicMock()
    plugins.__iter__.side_effect = lambda: iter([plugin])
    plugins.values.return_value = [{"id": 9, "name": "chat-plugin", "plugin_type": "chat", "plugin_key": "chat"}]
    plugin_manager = mocker.patch.object(ActionPlugin, "objects")
    plugin_manager.all.return_value = plugins
    plugin_manager.get.return_value = plugin
    mocker.patch.object(
        plugin,
        "perform_resource_request",
        return_value=[{"key": key} for key in ("chat_owner", "chat_name", "chat_members", "message")],
    )
    mocker.patch.object(backend_resources.GlobalConfig, "get", return_value="蓝鲸监控")
    mocker.patch.object(backend_resources, "get_user_display_name", side_effect=lambda name: name)
    create_action = mocker.patch.object(backend_resources.ActionInstance, "objects").create
    create_action.side_effect = lambda **kwargs: SimpleNamespace(
        id=301, create_time=datetime.now(timezone.utc), **kwargs
    )
    queue = mocker.patch.object(backend_resources, "PushActionProcessor", create=True)
    queue.push_actions_to_queue.return_value = [301]
    alert_write = mocker.patch.object(AlertDocument, "bulk_create")
    log_write = mocker.patch.object(backend_resources.AlertLog, "bulk_create")
    forward = mocker.patch.object(frontend_resources.CreateChatGroupActionBackendResource, "request")
    state = SimpleNamespace(
        request=request,
        tenants=tenants,
        allowed_biz_ids=allowed_biz_ids,
        iam=iam,
        iam_factory=iam_factory,
        alerts=alerts,
        mget=mget,
        config_get=config_get,
        token_query=token_query,
        create_action=create_action,
        queue=queue.push_actions_to_queue,
        alert_write=alert_write,
        log_write=log_write,
        forward=forward,
        data={
            "alert_ids": ["alert-2", "alert-3"],
            "chat_members": ["responder"],
            "content_type": [ChatMessageType.DETAIL_URL],
        },
    )
    yield state
    bk_biz_id_to_bk_tenant_id.cache_clear()


def assert_no_side_effects(state):
    state.create_action.assert_not_called()
    state.queue.assert_not_called()
    state.alert_write.assert_not_called()
    state.log_write.assert_not_called()


@pytest.mark.parametrize("denied_biz_id", [2, 3])
def test_chat_requires_permission_on_every_alert_business(chat_security, denied_biz_id):
    state = chat_security
    state.allowed_biz_ids.remove(denied_biz_id)

    with pytest.raises(PermissionDeniedError):
        backend_resources.CreateChatGroupActionResource().request(state.data)

    checked = [int(call.args[0].resources[0].id) for call in state.iam.is_allowed_with_cache.call_args_list]
    assert denied_biz_id in checked
    assert all(
        call.args[0].action.id == ActionEnum.VIEW_EVENT.id for call in state.iam.is_allowed_with_cache.call_args_list
    )
    assert_no_side_effects(state)


@pytest.mark.parametrize("denied_biz_id", [2, 3])
def test_chat_rejects_another_tenant_before_writing(chat_security, denied_biz_id):
    state = chat_security
    state.tenants[denied_biz_id] = "tenant-other"

    with pytest.raises(PermissionDenied):
        backend_resources.CreateChatGroupActionResource().request(state.data)

    assert_no_side_effects(state)


def test_chat_rejects_platform_business(chat_security):
    state = chat_security
    state.alerts[1].event.bk_biz_id = 0

    with pytest.raises(PermissionDenied):
        backend_resources.CreateChatGroupActionResource().request(state.data)

    assert_no_side_effects(state)


@pytest.mark.parametrize("found_count", [0, 1])
def test_chat_rejects_missing_alerts_without_partial_actions(chat_security, found_count):
    state = chat_security
    state.mget.return_value = state.alerts[:found_count]

    with pytest.raises(ValidationError):
        backend_resources.CreateChatGroupActionResource().request(state.data)

    state.iam.is_allowed_with_cache.assert_not_called()
    assert_no_side_effects(state)


@pytest.mark.parametrize(
    "resource_class", [frontend_resources.CreateChatGroupResource, backend_resources.CreateChatGroupActionResource]
)
def test_chat_rejects_empty_alert_list(chat_security, resource_class):
    state = chat_security

    with pytest.raises(CustomException):
        resource_class().request(dict(state.data, alert_ids=[]))

    state.mget.assert_not_called()
    state.forward.assert_not_called()
    assert_no_side_effects(state)


@pytest.mark.parametrize("cached", [False, True])
def test_chat_enforces_application_business_scope(chat_security, cached):
    state = chat_security
    # A forged legacy header must not override the authenticated JWT application.
    state.request.META["HTTP_BK_APP_CODE"] = "unrestricted-app"
    if cached:
        authentication.APP_CODE_TOKENS["tenant-a"]["monitor-web"] = ["biz#2"]
    else:
        authentication.APP_CODE_TOKENS.clear()
        state.token_query.return_value = [SimpleNamespace(params={"app_code": "monitor-web"}, namespaces=["biz#2"])]

    with pytest.raises(PermissionDenied):
        backend_resources.CreateChatGroupActionResource().request(state.data)

    if cached:
        state.token_query.assert_not_called()
    else:
        state.token_query.assert_called_once_with(type=authentication.AuthType.API, bk_tenant_id="tenant-a")
    assert [call.args[0].resources[0].id for call in state.iam.is_allowed_with_cache.call_args_list] == ["2"]
    assert_no_side_effects(state)


@pytest.mark.parametrize(
    "resource_class", [frontend_resources.CreateChatGroupResource, backend_resources.CreateChatGroupActionResource]
)
def test_chat_rejects_share_token_before_forwarding_or_writing(chat_security, resource_class):
    state = chat_security
    state.request.token = "event-share-token"

    with pytest.raises(PermissionDenied):
        resource_class().request(state.data)

    state.mget.assert_not_called()
    state.forward.assert_not_called()
    assert_no_side_effects(state)


@pytest.mark.parametrize("identity", ["unverified", "missing_jwt_username", "missing_legacy_username", "missing_app"])
def test_chat_rejects_missing_original_identity_even_when_request_user_is_admin(chat_security, identity):
    state = chat_security
    state.request.user.username = "admin"
    if identity == "unverified":
        state.request.jwt.user["verified"] = False
    elif identity == "missing_jwt_username":
        state.request.jwt.user.pop("username")
    elif identity == "missing_legacy_username":
        del state.request.jwt
        state.request.META["HTTP_BK_APP_CODE"] = "monitor-web"
    else:
        state.request.jwt.app.clear()

    with pytest.raises(PermissionDenied):
        backend_resources.CreateChatGroupActionResource().request(state.data)

    state.mget.assert_not_called()
    assert_no_side_effects(state)


def test_chat_ignores_forged_identity_action_and_authorized_alert_fields(chat_security):
    state = chat_security
    data = dict(
        state.data,
        creator="admin",
        bk_username="admin",
        bk_tenant_id="tenant-other",
        bk_biz_id=999,
        action_configs=[{"config_id": 999, "plugin_id": 999}],
        alerts_groups=[["alert-outside-request"]],
        alert_groups=[["alert-outside-request"]],
        allow_cross_business=True,
    )
    serializer = CreateChatGroupSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    assert serializer.validated_data == state.data

    result = backend_resources.CreateChatGroupActionResource().request(data)

    assert result == {"actions": [301], "alert_ids": ["alert-2", "alert-3"]}
    state.iam_factory.assert_called_once_with("tenant-a")
    assert {call.args[0].subject.id for call in state.iam.is_allowed_with_cache.call_args_list} == {"operator"}
    state.mget.assert_called_once_with(ids=["alert-2", "alert-3"])
    state.create_action.assert_called_once()
    action = state.create_action.call_args.kwargs
    assert action["assignee"] == ["operator"]
    assert action["alerts"] == ["alert-2", "alert-3"]
    assert action["bk_biz_id"] == "2"
    assert action["action_config_id"] == 101
    assert action["action_config"]["plugin_id"] == 9
    assert action["action_config"]["execute_config"]["template_detail"]["chat_owner"] == "operator"
    state.queue.assert_called_once()
    assert state.queue.call_args.args[1] == state.alerts


def test_chat_uses_single_alert_business_instead_of_current_page_business(chat_security):
    state = chat_security
    state.request.biz_id = 2
    state.allowed_biz_ids.remove(2)
    authentication.APP_CODE_TOKENS["tenant-a"]["monitor-web"] = ["biz#3"]
    state.mget.return_value = [state.alerts[1]]

    result = backend_resources.CreateChatGroupActionResource().request(
        dict(state.data, alert_ids=["alert-3"], bk_biz_id=2, chat_members=[])
    )

    assert result == {"actions": [301], "alert_ids": ["alert-3"]}
    assert [call.args[0].resources[0].id for call in state.iam.is_allowed_with_cache.call_args_list] == ["3"]
    state.create_action.assert_called_once()
    action = state.create_action.call_args.kwargs
    assert action["bk_biz_id"] == "3"
    assert action["alerts"] == ["alert-3"]
    template = action["action_config"]["execute_config"]["template_detail"]
    assert template["chat_owner"] == "operator"
    assert template["chat_members"] == ""
    state.queue.assert_called_once()
    assert state.queue.call_args.args[1] == [state.alerts[1]]


def test_chat_deduplicates_alerts_and_creates_one_group_for_both_businesses(chat_security):
    state = chat_security
    state.mget.return_value = state.alerts[::-1]

    result = backend_resources.CreateChatGroupActionResource().request(
        dict(state.data, alert_ids=["alert-2", "alert-3", "alert-2", "alert-3"])
    )

    assert result == {"actions": [301], "alert_ids": ["alert-2", "alert-3"]}
    state.mget.assert_called_once_with(ids=["alert-2", "alert-3"])
    state.create_action.assert_called_once()
    assert state.create_action.call_args.kwargs["alerts"] == ["alert-2", "alert-3"]
    state.queue.assert_called_once()
    assert state.queue.call_args.args[1] == state.alerts
    state.alert_write.assert_called_once()
    assert [alert.id for alert in state.alert_write.call_args.args[0]] == ["alert-2", "alert-3"]
    assert len(state.log_write.call_args.args[0]) == 1


def test_ordinary_batch_keeps_requested_business_filter_for_builtin_chat_config(chat_security):
    state = chat_security
    action_data = backend_resources.CreateChatGroupActionResource.convert_action_data(dict(state.data, bk_biz_id="2"))
    action_data.update(allow_cross_business=True, alert_groups=[state.alerts], alerts_groups=[state.alerts])

    result = backend_resources.BatchCreateActionResource().request(action_data)

    assert result == {"actions": [301], "alert_ids": ["alert-2"]}
    state.create_action.assert_called_once()
    assert state.create_action.call_args.kwargs["alerts"] == ["alert-2"]
    state.queue.assert_called_once()
    assert state.queue.call_args.args[1] == [state.alerts[0]]
    assert [alert.id for alert in state.alert_write.call_args.args[0]] == ["alert-2"]


def test_chat_accepts_authenticated_legacy_user_and_application_headers(chat_security):
    state = chat_security
    del state.request.jwt
    state.request.META.update(HTTP_BK_USERNAME="operator", HTTP_BK_APP_CODE="monitor-web")

    result = backend_resources.CreateChatGroupActionResource().request(state.data)

    assert result == {"actions": [301], "alert_ids": ["alert-2", "alert-3"]}
    assert {call.args[0].subject.id for call in state.iam.is_allowed_with_cache.call_args_list} == {"operator"}
    assert {call.args[0].resources[0].id for call in state.iam.is_allowed_with_cache.call_args_list} == {"2", "3"}
    state.create_action.assert_called_once()
    assert state.create_action.call_args.kwargs["assignee"] == ["operator"]
    state.queue.assert_called_once()


def test_web_forwards_only_chat_fields(chat_security):
    state = chat_security
    result = frontend_resources.CreateChatGroupResource().request(
        dict(state.data, bk_biz_id=999, bk_username="admin", bk_tenant_id="tenant-other", action_configs=[{}])
    )
    assert result == state.forward.return_value
    state.forward.assert_called_once_with(**state.data)


def test_chat_client_preserves_user_login_ticket(chat_security, settings, mocker):
    settings.APP_CODE = "monitor-web"
    settings.SECRET_KEY = "test-only-secret"
    ticket = mocker.patch.object(api_client, "get_bk_login_ticket", return_value={"bk_token": "test-only-ticket"})
    client = CreateChatGroupActionBackendResource()
    assert client.full_request_data(dict(chat_security.data)) == chat_security.data
    headers = client.get_headers()
    assert json.loads(headers["x-bkapi-authorization"]) == {
        "bk_app_code": "monitor-web",
        "bk_app_secret": "test-only-secret",
        "bk_username": "operator",
        "bk_token": "test-only-ticket",
    }
    assert headers["X-Bk-Tenant-Id"] == "tenant-a"
    ticket.assert_called_once_with(chat_security.request)


def test_chat_gateway_and_direct_route_keep_original_authenticated_context(
    chat_security, settings, monkeypatch, tmp_path
):
    # Load the real gateway mapping and execute the real DRF route without an HTTP hop.
    settings.BASE_DIR = str(Path(__file__).resolve().parents[3])
    monkeypatch.setattr(nested_api, "API_DEFINE", {})
    nested_api.load_api_yaml()
    client = CreateChatGroupActionBackendResource()
    gateway_dir = Path(settings.BASE_DIR) / "support-files/apigw"
    spec = importlib.util.spec_from_file_location("merge_gateway_resources", gateway_dir / "scripts/merge_resources.py")
    merger = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(merger)
    shutil.copytree(gateway_dir / "resources", tmp_path / "resources")
    merger.merge_resources(tmp_path / "resources")
    # Assert the deployed definition, including directory-based auth overrides and unique operation IDs.
    route = yaml.safe_load((tmp_path / "resources.yaml").read_text())["paths"][client.action]["post"][
        "x-bk-apigateway-resource"
    ]
    assert route["authConfig"] == {
        "appVerifiedRequired": True,
        "userVerifiedRequired": True,
        "resourcePermissionRequired": True,
    }
    assert route["isPublic"] is False
    # Import this route alone: the kernel views package also boots unrelated worker dependencies.
    spec = importlib.util.spec_from_file_location(
        "chat_action_routes", Path(settings.BASE_DIR) / "kernel_api/views/v4/action.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # config/role/api.py has no default permissions; the outer middleware already authenticated the request.
    monkeypatch.setattr(module.ActionInstanceViewSet, "permission_classes", ())
    router = ResourceRouter()
    router.register("action_instance", module.ActionInstanceViewSet)
    settings.ROOT_URLCONF = (path("api/v4/", include(router.urls)),)

    result = client.direct_request(chat_security.data)

    assert result == {"actions": [301], "alert_ids": ["alert-2", "alert-3"]}
    assert local.current_request is chat_security.request
    assert {call.args[0].subject.id for call in chat_security.iam.is_allowed_with_cache.call_args_list} == {"operator"}
    chat_security.create_action.assert_called_once()
