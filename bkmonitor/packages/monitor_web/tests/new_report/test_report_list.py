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

from bkmonitor.iam import ActionEnum
from core.drf_resource.exceptions import CustomException
from core.errors.iam import PermissionDeniedError
from monitor_web.new_report import resources


@pytest.fixture
def report_list(mocker):
    report_resource = resources.GetReportListResource()
    all_reports = mocker.patch.object(resources.Report.objects, "all").return_value.order_by.return_value
    business_reports = all_reports.filter.return_value
    business_reports.values.return_value = [
        {"id": 1, "bk_biz_id": 2, "is_manager_created": False},
        {"id": 2, "bk_biz_id": 2, "is_manager_created": True},
    ]
    business_reports.values_list.return_value = [1, 2]
    mocker.patch.object(report_resource, "filter_by_query_type", side_effect=lambda qs, query_type: qs)
    mocker.patch.object(report_resource, "fill_external_info", side_effect=lambda reports, *args: reports)
    mocker.patch.object(resources, "get_last_send_record_map", return_value={})
    mocker.patch.object(resources.ReportChannel.objects, "filter").return_value.values.return_value = []
    permission = mocker.patch.object(resources, "Permission").return_value
    business = mocker.patch.object(resources.ResourceEnum.BUSINESS, "create_instance").return_value
    return report_resource, all_reports, business_reports, permission, business


def test_user_report_list_checks_management_permission_and_keeps_business_scope(report_list):
    report_resource, all_reports, business_reports, permission, business = report_list

    result = report_resource.request(bk_biz_id=2, create_type="user")

    permission.is_allowed.assert_called_once_with(ActionEnum.MANAGE_REPORT, [business], raise_exception=True)
    resources.ResourceEnum.BUSINESS.create_instance.assert_called_once_with(2)
    assert permission.skip_check is False
    all_reports.filter.assert_called_once_with(bk_biz_id=2)
    business_reports.filter.assert_not_called()
    assert result == {"report_list": business_reports.values.return_value, "total": 2}


def test_user_report_list_denies_missing_management_permission(report_list):
    report_resource, all_reports, _, permission, business = report_list
    permission.is_allowed.side_effect = PermissionDeniedError(context={"action_name": "manage_report"})

    with pytest.raises(PermissionDeniedError):
        report_resource.request(bk_biz_id=2, create_type="user")

    permission.is_allowed.assert_called_once_with(ActionEnum.MANAGE_REPORT, [business], raise_exception=True)
    all_reports.filter.assert_not_called()


def test_self_report_list_keeps_personal_scope_across_businesses(report_list, mocker):
    report_resource, all_reports, _, permission, _ = report_list
    personal_reports = mocker.Mock()
    personal_reports.values.return_value = [{"id": 3, "bk_biz_id": 3}]
    personal_reports.values_list.return_value = [3]
    filter_by_user = mocker.patch.object(
        resources.GetReportListResource, "filter_by_user", return_value=personal_reports
    )

    result = report_resource.request(bk_biz_id=2, create_type="self")

    filter_by_user.assert_called_once_with(all_reports)
    permission.is_allowed.assert_not_called()
    all_reports.filter.assert_not_called()
    assert result == {"report_list": personal_reports.values.return_value, "total": 1}


def test_report_list_rejects_unknown_create_type(report_list):
    report_resource, all_reports, _, permission, _ = report_list

    with pytest.raises(CustomException, match="unsupported create_type unknown"):
        report_resource.request(bk_biz_id=2, create_type="unknown")

    permission.is_allowed.assert_not_called()
    all_reports.filter.assert_not_called()


@pytest.mark.parametrize("is_superuser", [False, True])
def test_management_permission_distinguishes_superuser_from_skip_check(mocker, is_superuser):
    request = SimpleNamespace(
        user=SimpleNamespace(username="operator", tenant_id="default", is_superuser=is_superuser),
        skip_check=True,
    )
    permission = mocker.patch.object(resources, "Permission")
    permission.return_value.is_allowed.return_value = False
    mocker.patch.object(resources.ResourceEnum.BUSINESS, "create_instance")

    assert resources.GetReportListResource.check_permission(2, request=request) is is_superuser

    if is_superuser:
        permission.assert_not_called()
    else:
        assert permission.return_value.skip_check is False
        permission.return_value.is_allowed.assert_called_once()


@pytest.mark.parametrize("raise_exception", [False, True])
def test_superuser_management_cannot_cross_tenant(mocker, settings, raise_exception):
    settings.ENABLE_MULTI_TENANT_MODE = True
    mocker.patch("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", return_value="tenant-b")
    permission = mocker.patch.object(resources, "Permission")
    request = SimpleNamespace(user=SimpleNamespace(tenant_id="tenant-a", is_superuser=True))

    with pytest.raises(CustomException, match="current tenant"):
        resources.GetReportListResource.check_permission(2, raise_exception=raise_exception, request=request)

    permission.assert_not_called()
