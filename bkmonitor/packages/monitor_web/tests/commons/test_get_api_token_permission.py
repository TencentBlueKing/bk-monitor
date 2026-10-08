from types import SimpleNamespace

import pytest

from bkmonitor.iam import ActionEnum
from monitor_web.commons.token import resources


@pytest.mark.parametrize("target_biz_id,allowed", [(2, True), (3, False)])
def test_grafana_token_checks_target_business(mocker, target_biz_id, allowed):
    request = SimpleNamespace(biz_id="2")
    mocker.patch.object(resources, "get_request", return_value=request)
    mocker.patch.object(resources, "get_request_username", return_value="editor")
    dashboard_permission = mocker.patch.object(
        resources.DashboardPermission,
        "has_permission",
        side_effect=lambda request, view, bk_biz_id: (
            True,
            resources.GrafanaRole.Editor if int(bk_biz_id) == 2 else resources.GrafanaRole.Anonymous,
            {},
        ),
    )
    permission = mocker.patch.object(resources, "Permission").return_value
    permission.is_allowed_by_biz.side_effect = PermissionError("permission denied")
    create_token = mocker.patch.object(
        resources, "get_or_create_business_token", return_value=(SimpleNamespace(token="token"), True)
    )
    params = {"bk_tenant_id": "system", "bk_biz_id": target_biz_id, "type": "grafana"}

    if allowed:
        assert resources.GetApiTokenResource().perform_request(params) == "token"
        create_token.assert_called_once_with(
            bk_tenant_id="system", bk_biz_id=target_biz_id, token_type="grafana", operator="editor"
        )
        permission.is_allowed_by_biz.assert_not_called()
    else:
        with pytest.raises(PermissionError):
            resources.GetApiTokenResource().perform_request(params)
        create_token.assert_not_called()
        permission.is_allowed_by_biz.assert_called_once_with(
            target_biz_id, ActionEnum.MANAGE_RULE, raise_exception=True
        )
    dashboard_permission.assert_called_once_with(request, None, target_biz_id)


def test_user_token_does_not_require_business(mocker):
    mocker.patch.object(resources, "get_request_username", return_value="user")
    create_token = mocker.patch.object(resources.GetApiTokenResource, "get_or_create_user_token", return_value="token")
    check_business = mocker.patch.object(resources.GetApiTokenResource, "_assert_business_token_allowed")

    assert resources.GetApiTokenResource().perform_request({"bk_tenant_id": "system", "type": "user"}) == "token"
    create_token.assert_called_once_with(bk_tenant_id="system", username="user")
    check_business.assert_not_called()
