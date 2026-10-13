"""Actual product denial boundary; no simulated exception-handler branches."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.iam import drf
from core.errors.iam import PermissionDeniedError
from core.drf_resource.exceptions import custom_exception_handler
from iam_engine.core.config import AuthMode
from iam_engine.core.requests import ResourceInstance
from iam_engine.exceptions import ProviderUnavailable


@pytest.mark.parametrize("mode", [AuthMode.V3, AuthMode.V4, AuthMode.UNION])
def test_real_drf_denial_keeps_original_business_response(monkeypatch, mode):
    permission = Permission(username="alice", bk_tenant_id="system")
    permission.mode_provider = SimpleNamespace(get_mode=lambda resources=(): mode)
    permission._is_allowed_request = Mock(return_value=False)
    permission.prepare_apply_for_saas = Mock(return_value=([], []))
    data = {"system": "bk_monitorv3", "actions": [{"id": "view_event_v2"}]}
    permission._apply_data_request = Mock(return_value=data)
    permission._apply_url_request = Mock(return_value="https://iam.example.test/apply")
    monkeypatch.setattr(drf, "Permission", lambda **kwargs: permission)
    request = SimpleNamespace(token=None, skip_check=False, user=SimpleNamespace(username="alice", tenant_id="system"))
    with pytest.raises(PermissionDeniedError) as error:
        drf._fw_check_any(request, [ActionEnum.VIEW_EVENT], [ResourceInstance("space", "2")])
    response = custom_exception_handler(error.value, {})
    assert response.data["result"] is False
    assert response.data["code"] == error.value.code
    assert response.data["data"]["apply_url"] == "https://iam.example.test/apply"
    assert response.data["permission"] == data


@pytest.mark.parametrize("mode", [AuthMode.V4, AuthMode.UNION])
def test_apply_failure_is_still_a_handled_product_denial(monkeypatch, mode):
    permission = Permission(username="alice", bk_tenant_id="system")
    permission.mode_provider = SimpleNamespace(get_mode=lambda resources=(): mode)
    permission._is_allowed_request = Mock(return_value=False)
    permission.prepare_apply_for_saas = Mock(return_value=([], []))
    permission._apply_data_request = Mock(return_value={})
    permission._apply_url_request = Mock(side_effect=ProviderUnavailable("V4 apply unavailable"))
    monkeypatch.setattr(drf, "Permission", lambda **kwargs: permission)
    request = SimpleNamespace(token=None, skip_check=False, user=SimpleNamespace(username="alice", tenant_id="system"))
    with pytest.raises(PermissionDeniedError) as error:
        drf._fw_check_any(request, [ActionEnum.VIEW_EVENT], [ResourceInstance("space", "2")])
    response = custom_exception_handler(error.value, {})
    assert response.data["result"] is False
    assert response.data["data"]["apply_url"] == ""
