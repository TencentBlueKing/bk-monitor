from types import SimpleNamespace
from unittest import mock

import pytest

from apm_web.llm.views import LLMViewSet
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission
from core.errors.iam import PermissionDeniedError


def build_viewset() -> LLMViewSet:
    viewset = LLMViewSet()
    viewset.request = SimpleNamespace(
        method="POST",
        data={"bk_biz_id": 2, "app_name": "demo"},
        query_params={},
    )
    return viewset


def test_get_permissions_uses_apm_application_permission():
    permission = build_viewset().get_permissions()[0]

    assert isinstance(permission, InstanceActionForDataPermission)
    assert permission.actions == [ActionEnum.VIEW_APM_APPLICATION]
    assert permission.resource_meta == ResourceEnum.APM_APPLICATION


@pytest.mark.parametrize("allowed", [True, False])
@mock.patch("bkmonitor.iam.drf.Permission")
@mock.patch("apm_web.llm.views.Application.get_application_id_by_app_name", return_value=9)
def test_apm_application_permission_result(get_application_id, permission_mock, allowed):
    if allowed:
        permission_mock.return_value.is_allowed.return_value = True
    else:
        permission_mock.return_value.is_allowed.side_effect = PermissionDeniedError(
            context={"action_name": ActionEnum.VIEW_APM_APPLICATION.name}
        )

    viewset = build_viewset()
    permission = viewset.get_permissions()[0]

    with mock.patch.object(
        ResourceEnum.APM_APPLICATION,
        "_get_app_simple_info_by_id_or_none",
        return_value={"application_id": 9, "app_name": "demo", "bk_biz_id": 2},
    ):
        if allowed:
            assert permission.has_permission(viewset.request, viewset) is True
        else:
            with pytest.raises(PermissionDeniedError):
                permission.has_permission(viewset.request, viewset)

    get_application_id.assert_called_once_with("demo")
