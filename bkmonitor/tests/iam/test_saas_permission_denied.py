"""SaaS 无权限分支使用真实资源构造器和申请 Provider 验证响应协议。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.conf import settings

from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.iam import definitions, drf
from bkmonitor.iam import permission as permission_module
from bkmonitor.iam.action import MINI_ACTION_IDS, canonicalize_action_id
from bkmonitor.iam.backends.config import build_provider
from bkmonitor.iam.backends.v3.client import V3Client
from core.drf_resource.exceptions import custom_exception_handler
from core.errors.iam import PermissionDeniedError
from iam_engine.core.config import AuthMode
from monitor_web.iam import views


@pytest.fixture(params=[AuthMode.V3, AuthMode.V4, AuthMode.UNION])
def permission_context(monkeypatch, request):
    mode = request.param
    monkeypatch.setattr(settings, "SKIP_IAM_PERMISSION_CHECK", False)
    permission = Permission(username="alice", bk_tenant_id="system")
    permission.mode_provider = SimpleNamespace(get_mode=lambda resources=(): mode)
    clients: dict[str, V3Client | Mock] = {}
    providers = {}
    for name in ("v3", "v4"):
        provider = build_provider(name, username="alice")
        if name == "v3":
            client = V3Client("offline", "offline", "https://iam.example.test", provider.system_id, provider.codec)
            client.is_allowed_with_cache = Mock(return_value=False)
            client.get_apply_url = Mock(return_value=(True, "", "https://iam.example.test/apply"))
        else:
            client = Mock()
            client.direct_auth.return_value = False
            client.generate_perm_apply_url.return_value = "https://iam.example.test/apply"
        provider._get_client = Mock(return_value=client)
        providers[name] = provider
        clients[name] = client
    permission._providers = providers
    monkeypatch.setattr(drf, "Permission", lambda **kwargs: permission)
    return permission, clients, mode


@pytest.mark.parametrize("is_saas", [True, False], ids=["saas", "business"])
@pytest.mark.parametrize("allowed", [False, True], ids=["denied", "allowed"])
def test_business_permission_keeps_response_contract(monkeypatch, permission_context, is_saas, allowed):
    permission, clients, mode = permission_context
    biz_id = "-42" if is_saas else "2"
    space_uid = "bksaas__demo" if is_saas else "bkcc__2"
    space_type = "bksaas" if is_saas else "bkcc"
    space = SimpleNamespace(
        id=42 if is_saas else 2,
        space_uid=space_uid,
        space_type_id=space_type,
        space_name="Demo",
        bk_tenant_id="system",
    )
    monkeypatch.setattr(permission_module, "bk_biz_id_to_space_uid", lambda value: space_uid)
    monkeypatch.setattr(views, "bk_biz_id_to_space_uid", lambda value: space_uid)
    monkeypatch.setattr(views.space_api.SpaceApi, "get_space_detail", lambda **kwargs: space)
    monkeypatch.setattr(drf, "is_biz_in_tenant", lambda *args: True)
    request = SimpleNamespace(
        method="GET",
        biz_id=biz_id,
        query_params={"bk_biz_id": biz_id, "type": "trace"},
        user=SimpleNamespace(username="alice", tenant_id="system"),
        token=None,
        skip_check=False,
    )

    if allowed:
        clients["v3"].is_allowed_with_cache.return_value = True
        clients["v4"].direct_auth.return_value = True
        assert drf.BusinessActionPermission([ActionEnum.EXPLORE_METRIC]).has_permission(request, None)
        clients["v3"].get_apply_url.assert_not_called()
        clients["v4"].generate_perm_apply_url.assert_not_called()
        return

    with pytest.raises(PermissionDeniedError) as error:
        drf.BusinessActionPermission([ActionEnum.EXPLORE_METRIC]).has_permission(request, None)

    response = custom_exception_handler(error.value, {})
    assert response.data["result"] is False
    assert response.data["code"] == PermissionDeniedError.code
    assert response.data["data"]["apply_url"] == "https://iam.example.test/apply"
    payload = response.data["permission"]
    assert payload["system_id" if mode is AuthMode.V3 else "system"] == settings.BK_IAM_SYSTEM_ID
    actions = payload["actions"]
    expected = {canonicalize_action_id(a) for a in MINI_ACTION_IDS} if is_saas else {"explore_metric"}
    assert {canonicalize_action_id(a["id"]) for a in actions} == expected
    for action in actions:
        if definitions.actions[canonicalize_action_id(action["id"])].resource_type != "space":
            assert action["related_resource_types"] == []
            continue
        resource = action["related_resource_types"][0]
        assert resource["type" if mode is AuthMode.V3 else "id"] == "space"
        assert len(resource["instances"]) == 1
        assert len(resource["instances"][0]) == 1
        instance = resource["instances"][0][0]
        assert {key: instance[key] for key in ("type", "id", "name")} == {
            "type": "space",
            "id": biz_id,
            "name": f"[{space_type}] Demo",
        }
    application_client = clients["v3" if mode is AuthMode.V3 else "v4"]
    if mode is AuthMode.V3:
        assert application_client.get_apply_url.call_count == 2
        clients["v4"].generate_perm_apply_url.assert_not_called()
    else:
        assert application_client.generate_perm_apply_url.call_count == 2
        clients["v3"].get_apply_url.assert_not_called()
