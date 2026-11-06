"""RPC diagnostics cannot query a protocol disabled by the common process mode."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from core.drf_resource.exceptions import CustomException
from bkmonitor.iam.permission import Permission
from iam_engine.core.config import AuthMode
from iam_engine.core.exceptions import InvalidAuthModeError
from kernel_api.rpc.functions.admin.permission import _v3, _v4


@pytest.mark.parametrize("mode,entry", [
    (AuthMode.V3, _v4.query_user_permissions_v4),
    (AuthMode.V3, _v4.query_user_sub_resources_v4),
    (AuthMode.V4, _v3.query_user_permissions),
])
def test_disabled_protocol_stops_before_provider_or_iam(monkeypatch, mode, entry):
    fw = Permission(username="alice", bk_tenant_id="system")
    fw.mode_provider = SimpleNamespace(get_mode=Mock(return_value=mode))
    fw.get_provider = Mock(side_effect=AssertionError("disabled provider must not be assembled"))
    module = _v3 if entry is _v3.query_user_permissions else _v4
    monkeypatch.setattr(module, "Permission", lambda **kwargs: fw)
    params = {"username": "alice", "bk_tenant_id": "system", "bk_biz_id": "2", "resource_type": "apm_application"}
    with pytest.raises(CustomException, match="disabled"):
        entry(params)
    fw.get_provider.assert_not_called()
    fw.mode_provider.get_mode.assert_called_once()


@pytest.mark.parametrize("mode", [AuthMode.V3, AuthMode.V4, AuthMode.UNION])
def test_enabled_provider_uses_common_targets_and_one_snapshot(mode):
    from kernel_api.rpc.functions.admin.permission._shared import _get_enabled_provider
    fw = SimpleNamespace(mode_provider=SimpleNamespace(get_mode=Mock(return_value=mode)), get_provider=Mock())
    protocols = ("v3", "v4") if mode is AuthMode.UNION else (mode.value,)
    for protocol in protocols:
        fw.mode_provider.get_mode.reset_mock()
        assert _get_enabled_provider(fw, protocol) is fw.get_provider.return_value
        fw.mode_provider.get_mode.assert_called_once()


@pytest.mark.parametrize("invalid_mode", [
    "unknown",
    InvalidAuthModeError("unknown", "Invalid IAM permission mode"),
])
def test_invalid_mode_is_handled_without_provider_or_iam(invalid_mode):
    from kernel_api.rpc.functions.admin.permission._shared import _get_enabled_provider
    get_mode = Mock(side_effect=invalid_mode) if isinstance(invalid_mode, Exception) else Mock(return_value=invalid_mode)
    fw = SimpleNamespace(mode_provider=SimpleNamespace(get_mode=get_mode), get_provider=Mock())
    with pytest.raises(CustomException, match="Invalid IAM mode"):
        _get_enabled_provider(fw, "v3")
    fw.get_provider.assert_not_called()
    get_mode.assert_called_once()
