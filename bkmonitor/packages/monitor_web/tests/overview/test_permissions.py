from types import SimpleNamespace
from unittest import mock

import pytest

from bkmonitor.iam.action import ActionEnum
from monitor_web.overview.permissions import filter_viewable_apm_applications


@pytest.mark.parametrize("username", [None, "specified_user"])
@pytest.mark.parametrize("allowed", [True, False])
def test_application_filter_preserves_user_and_request_context(username: str | None, allowed: bool) -> None:
    request = SimpleNamespace(user=SimpleNamespace(username="request_user"))
    application = {"application_id": 1, "bk_biz_id": 2, "app_name": "demo"}

    with (
        mock.patch("bkmonitor.iam.drf.get_request", return_value=request) as get_request,
        mock.patch("bkmonitor.iam.drf.check_iam_batch_preflight", return_value=None) as preflight,
        mock.patch("bkmonitor.iam.drf.Permission") as permission_class,
    ):
        permission_class.return_value.batch_is_allowed.return_value = {
            "1": {ActionEnum.VIEW_APM_APPLICATION.id: allowed}
        }
        result = filter_viewable_apm_applications("tenant", [application], username=username)

    assert result == ([application] if allowed else [])
    permission_class.assert_called_once_with(
        username=username or request.user.username,
        bk_tenant_id="tenant",
        request=request if username is None else None,
    )
    preflight.assert_called_once_with(request if username is None else None, [ActionEnum.VIEW_APM_APPLICATION])
    if username is None:
        get_request.assert_called_once_with(peaceful=True)
    else:
        get_request.assert_not_called()
