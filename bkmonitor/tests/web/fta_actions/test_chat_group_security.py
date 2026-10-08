"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from bkm_space.api import SpaceApi
from bkmonitor.action.serializers.action import CreateChatGroupSerializer
from bkmonitor.documents import AlertDocument, EventDocument
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.models.fta import ActionPlugin
from bkmonitor.utils.local import local
from constants.action import ChatMessageType
from core.drf_resource.exceptions import CustomException
from core.errors.iam import PermissionDeniedError
from fta_web.action.resources import backend_resources, frontend_resources


@pytest.fixture
def chat_security(mocker, monkeypatch, settings):
    settings.SAAS_APP_CODE = "monitor-web"
    # API services default to IAM exemption; chat must still authorize every business.
    settings.SKIP_IAM_PERMISSION_CHECK = True
    request = SimpleNamespace(
        user=SimpleNamespace(username="operator"),
        jwt=SimpleNamespace(
            is_valid=True,
            user=SimpleNamespace(username="operator", verified=True),
            app=SimpleNamespace(app_code="monitor-web", verified=True),
        ),
        META={},
        skip_check=True,
    )
    monkeypatch.setattr(local, "current_request", request, raising=False)

    def get_space(bk_biz_id=None, space_uid=None, **kwargs):
        biz_id = int(bk_biz_id if bk_biz_id is not None else space_uid.split("__")[-1])
        if space_uid and space_uid.startswith("bkci__"):
            biz_id = -biz_id
        space_type = "bkci" if biz_id < 0 else "bkcc"
        return SimpleNamespace(
            id=abs(biz_id),
            space_uid=f"{space_type}__{abs(biz_id)}",
            space_type_id=space_type,
            space_name=f"business-{biz_id}",
        )

    mocker.patch.object(SpaceApi, "get_space_detail", side_effect=get_space)
    allowed_biz_ids = {2, 3}
    iam = mocker.Mock()
    iam.is_allowed_with_cache.side_effect = lambda data: int(data.resources[0].id) in allowed_biz_ids
    iam_factory = mocker.patch.object(Permission, "get_iam_client", return_value=iam)
    # Stub only the permission-application UI data; use the real IAM decision/denial path.
    mocker.patch.object(Permission, "get_apply_data", return_value=({}, "https://iam.invalid/apply"))
    alerts = [
        AlertDocument(
            id=f"alert-{biz_id}",
            event=EventDocument(bk_biz_id=biz_id),
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
    config_get = mocker.patch.object(backend_resources.ActionConfig.objects, "get", return_value=config)
    plugin = ActionPlugin(id=9, name="chat-plugin", plugin_type="chat", plugin_key="chat")
    plugins = mocker.MagicMock()
    plugins.__iter__.side_effect = lambda: iter([plugin])
    plugins.values.return_value = [{"id": 9, "name": "chat-plugin", "plugin_type": "chat", "plugin_key": "chat"}]
    mocker.patch.object(ActionPlugin.objects, "all", return_value=plugins)
    mocker.patch.object(ActionPlugin.objects, "get", return_value=plugin)
    mocker.patch.object(
        plugin,
        "perform_resource_request",
        return_value=[{"key": key} for key in ("chat_owner", "chat_name", "chat_members", "message")],
    )
    mocker.patch.object(backend_resources.GlobalConfig, "get", return_value="蓝鲸监控")
    create_action = mocker.patch.object(
        backend_resources.ActionInstance.objects,
        "create",
        side_effect=lambda **kwargs: SimpleNamespace(id=301, create_time=datetime.now(timezone.utc), **kwargs),
    )
    queue = mocker.patch.object(backend_resources, "PushActionProcessor", create=True)
    queue.push_actions_to_queue.return_value = [301]
    alert_write = mocker.patch.object(AlertDocument, "bulk_create")
    log_write = mocker.patch.object(backend_resources.AlertLog, "bulk_create")
    forward = mocker.patch.object(frontend_resources.CreateChatGroupActionBackendResource, "request")
    return SimpleNamespace(
        request=request,
        allowed_biz_ids=allowed_biz_ids,
        iam=iam,
        iam_factory=iam_factory,
        alerts=alerts,
        mget=mget,
        config_get=config_get,
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

    checked = [int(call[0][0].resources[0].id) for call in state.iam.is_allowed_with_cache.call_args_list]
    assert denied_biz_id in checked
    assert all(
        call[0][0].action.id == ActionEnum.VIEW_EVENT.id for call in state.iam.is_allowed_with_cache.call_args_list
    )
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


@pytest.mark.parametrize(
    "identity",
    [
        "invalid_jwt",
        "unverified_jwt_user",
        "missing_jwt_username",
        "missing_jwt_app",
        "unverified_jwt_app",
        "missing_legacy_username",
        "wrong_legacy_app",
        "missing_legacy_app",
        "empty_saas_app_setting",
        "missing_request_user",
        "empty_request_username",
    ],
)
def test_chat_requires_original_authenticated_identity(chat_security, settings, monkeypatch, identity):
    state = chat_security
    state.request.user.username = "admin"
    monkeypatch.setattr(local, "username", "fallback-admin", raising=False)
    if identity == "invalid_jwt":
        state.request.jwt.is_valid = False
    elif identity == "unverified_jwt_user":
        state.request.jwt.user.verified = False
    elif identity == "missing_jwt_username":
        state.request.jwt.user.username = ""
    elif identity == "missing_jwt_app":
        state.request.jwt.app.app_code = ""
    elif identity == "unverified_jwt_app":
        state.request.jwt.app.verified = False
    elif identity == "missing_request_user":
        del state.request.user
    elif identity == "empty_request_username":
        state.request.user.username = ""
    else:
        del state.request.jwt
        state.request.META.update(HTTP_BK_USERNAME="admin", HTTP_BK_APP_CODE="monitor-web")
        if identity == "missing_legacy_username":
            state.request.META.pop("HTTP_BK_USERNAME")
        elif identity == "wrong_legacy_app":
            state.request.META["HTTP_BK_APP_CODE"] = "other-app"
        elif identity == "missing_legacy_app":
            state.request.META.pop("HTTP_BK_APP_CODE")
        else:
            settings.SAAS_APP_CODE = ""
            state.request.META["HTTP_BK_APP_CODE"] = ""

    with pytest.raises(PermissionDenied):
        backend_resources.CreateChatGroupActionResource().request(
            dict(state.data, creator="admin", bk_username="admin")
        )

    state.mget.assert_not_called()
    state.iam.is_allowed_with_cache.assert_not_called()
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
    state.iam_factory.assert_called_once_with()
    assert {call[0][0].subject.id for call in state.iam.is_allowed_with_cache.call_args_list} == {"operator"}
    state.mget.assert_called_once_with(ids=["alert-2", "alert-3"])
    state.create_action.assert_called_once()
    action = state.create_action.call_args[1]
    assert action["assignee"] == ["operator"]
    assert action["alerts"] == ["alert-2", "alert-3"]
    assert action["bk_biz_id"] == "2"
    assert action["action_config_id"] == 101
    assert action["action_config"]["plugin_id"] == 9
    assert action["action_config"]["execute_config"]["template_detail"]["chat_owner"] == "operator"
    state.queue.assert_called_once()
    assert state.queue.call_args[0][1] == state.alerts


@pytest.mark.parametrize("actual_biz_id", [3, -3])
def test_chat_uses_single_alert_business_instead_of_current_page_business(chat_security, actual_biz_id):
    state = chat_security
    state.request.biz_id = 2
    state.allowed_biz_ids.remove(2)
    state.allowed_biz_ids.add(actual_biz_id)
    state.alerts[1].event.bk_biz_id = actual_biz_id
    state.mget.return_value = [state.alerts[1]]

    result = backend_resources.CreateChatGroupActionResource().request(
        dict(state.data, alert_ids=["alert-3"], bk_biz_id=2, chat_members=[])
    )

    assert result == {"actions": [301], "alert_ids": ["alert-3"]}
    assert [call[0][0].resources[0].id for call in state.iam.is_allowed_with_cache.call_args_list] == [
        str(actual_biz_id)
    ]
    state.create_action.assert_called_once()
    action = state.create_action.call_args[1]
    assert action["bk_biz_id"] == str(actual_biz_id)
    assert action["alerts"] == ["alert-3"]
    template = action["action_config"]["execute_config"]["template_detail"]
    assert template["chat_owner"] == "operator"
    assert template["chat_members"] == ""
    state.queue.assert_called_once()
    assert state.queue.call_args[0][1] == [state.alerts[1]]


def test_chat_deduplicates_alerts_and_creates_one_group_for_both_businesses(chat_security):
    state = chat_security
    state.mget.return_value = state.alerts[::-1]

    result = backend_resources.CreateChatGroupActionResource().request(
        dict(state.data, alert_ids=["alert-2", "alert-3", "alert-2", "alert-3"])
    )

    assert result == {"actions": [301], "alert_ids": ["alert-2", "alert-3"]}
    state.mget.assert_called_once_with(ids=["alert-2", "alert-3"])
    state.create_action.assert_called_once()
    assert state.create_action.call_args[1]["alerts"] == ["alert-2", "alert-3"]
    state.queue.assert_called_once()
    assert state.queue.call_args[0][1] == state.alerts
    state.alert_write.assert_called_once()
    assert [alert.id for alert in state.alert_write.call_args[0][0]] == ["alert-2", "alert-3"]
    assert len(state.log_write.call_args[0][0]) == 1


def test_ordinary_batch_keeps_requested_business_filter_for_builtin_chat_config(chat_security):
    state = chat_security
    action_data = backend_resources.CreateChatGroupActionResource.convert_action_data(dict(state.data, bk_biz_id="2"))
    action_data.update(allow_cross_business=True, alert_groups=[state.alerts], alerts_groups=[state.alerts])

    result = backend_resources.BatchCreateActionResource().request(action_data)

    assert result == {"actions": [301], "alert_ids": ["alert-2"]}
    state.create_action.assert_called_once()
    assert state.create_action.call_args[1]["alerts"] == ["alert-2"]
    state.queue.assert_called_once()
    assert state.queue.call_args[0][1] == [state.alerts[0]]
    assert [alert.id for alert in state.alert_write.call_args[0][0]] == ["alert-2"]


def test_chat_accepts_authenticated_legacy_user_and_application_headers(chat_security):
    state = chat_security
    del state.request.jwt
    state.request.META.update(HTTP_BK_USERNAME="operator", HTTP_BK_APP_CODE="monitor-web")

    result = backend_resources.CreateChatGroupActionResource().request(state.data)

    assert result == {"actions": [301], "alert_ids": ["alert-2", "alert-3"]}
    assert {call[0][0].subject.id for call in state.iam.is_allowed_with_cache.call_args_list} == {"operator"}
    assert {call[0][0].resources[0].id for call in state.iam.is_allowed_with_cache.call_args_list} == {"2", "3"}
    state.create_action.assert_called_once()
    assert state.create_action.call_args[1]["assignee"] == ["operator"]
    state.queue.assert_called_once()


def test_web_forwards_only_chat_fields(chat_security):
    state = chat_security
    result = frontend_resources.CreateChatGroupResource().request(
        dict(state.data, bk_biz_id=999, bk_username="admin", bk_tenant_id="tenant-other", action_configs=[{}])
    )
    assert result == state.forward.return_value
    state.forward.assert_called_once_with(**state.data)
