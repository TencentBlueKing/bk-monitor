from unittest import mock

import pytest
from django.test import override_settings

from apps.iam import ActionEnum, ResourceEnum
from apps.iam.handlers.drf import BatchIAMPermission


@override_settings(IGNORE_IAM_PERMISSION=False)
@mock.patch("apps.iam.handlers.drf.Permission")
def test_batch_permission_checks_every_index_set(permission_mock):
    request = mock.Mock(method="POST", data={"index_set_ids": [11, 22]})
    permission = BatchIAMPermission("index_set_ids", [ActionEnum.SEARCH_LOG], ResourceEnum.INDICES)

    assert permission.has_permission(request, mock.Mock()) is True

    checked_resources = [call[1]["resources"] for call in permission_mock.return_value.is_allowed.call_args_list]
    assert [[str(resource.id) for resource in resources] for resources in checked_resources] == [["11"], ["22"]]


@override_settings(IGNORE_IAM_PERMISSION=False)
@mock.patch("apps.iam.handlers.drf.Permission")
def test_batch_permission_rejects_when_any_index_set_is_denied(permission_mock):
    request = mock.Mock(method="POST", data={"index_set_ids": [11, 22]})
    permission = BatchIAMPermission("index_set_ids", [ActionEnum.SEARCH_LOG], ResourceEnum.INDICES)
    permission_mock.return_value.is_allowed.side_effect = [True, RuntimeError("denied")]

    with pytest.raises(RuntimeError, match="denied"):
        permission.has_permission(request, mock.Mock())
