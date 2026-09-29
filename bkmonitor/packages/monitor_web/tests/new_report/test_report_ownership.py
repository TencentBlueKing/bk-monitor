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
from unittest import TestCase, mock

import pytest

from core.drf_resource.exceptions import CustomException
from core.errors.iam import PermissionDeniedError
from monitor_web.new_report import resources
from monitor_web.new_report.resources import CreateOrUpdateReportResource, SendReportResource


class TestReportOwnership(TestCase):
    def test_edit_denies_cross_business_report(self):
        resource = CreateOrUpdateReportResource()
        report = SimpleNamespace(id=8, bk_biz_id=2, scenario_config={"index_set_id": 11})
        with self.assertRaises(CustomException):
            resource._assert_report_ownership(report, {"bk_biz_id": 3, "scenario_config": {"index_set_id": 11}})

    def test_edit_denies_mismatched_index_set(self):
        resource = CreateOrUpdateReportResource()
        report = SimpleNamespace(id=8, bk_biz_id=2, scenario_config={"index_set_id": 11})
        with self.assertRaises(CustomException):
            resource._assert_report_ownership(report, {"bk_biz_id": 2, "scenario_config": {"index_set_id": 99}})

    def test_edit_allows_matching_business_and_index_set(self):
        resource = CreateOrUpdateReportResource()
        report = SimpleNamespace(id=8, bk_biz_id=2, scenario_config={"index_set_id": 11})
        resource._assert_report_ownership(report, {"bk_biz_id": 2, "scenario_config": {"index_set_id": 11}})

    def test_send_denies_mismatched_report(self):
        resource = SendReportResource()
        with mock.patch("monitor_web.new_report.resources.Report.objects.get") as getter:
            getter.return_value = SimpleNamespace(id=8, bk_biz_id=2, scenario_config={"index_set_id": 11})
            with self.assertRaises(CustomException):
                resource.perform_request({"report_id": 8, "bk_biz_id": 2, "scenario_config": {"index_set_id": 99}})


@pytest.fixture
def resend_report(mocker):
    report = SimpleNamespace(id=8, bk_biz_id=3, create_user="manager", scenario_config={"index_set_id": 11})
    mocker.patch.object(resources.Report.objects, "get", return_value=report)
    username = mocker.patch.object(resources, "get_request_username", return_value="receiver")
    subscribers = [{"id": "receiver", "type": "user", "is_enabled": True}]
    mocker.patch.object(resources.ReportChannel.objects, "filter").return_value.first.return_value = SimpleNamespace(
        subscribers=subscribers
    )
    records = mocker.patch.object(resources.ReportSendRecord.objects, "filter")
    records.return_value.exclude.return_value.order_by.return_value.values_list.return_value = [[{"id": "receiver"}]]
    check_management = mocker.patch.object(resources.GetReportListResource, "check_permission", return_value=False)
    permission = mocker.patch.object(resources, "Permission").return_value
    permission.is_allowed_by_biz.return_value = False
    send = mocker.patch.object(resources.api.monitor, "send_report")
    params = {
        "report_id": report.id,
        "bk_biz_id": 2,
        "channels": [{"channel_name": "user", "is_enabled": True, "subscribers": subscribers}],
    }
    return params, username, check_management, permission, send


@pytest.mark.parametrize("id_field", ["report_id", "id"])
def test_resend_uses_subscription_access_and_normalizes_report_id(resend_report, id_field):
    params, _, check_management, permission, send = resend_report
    params[id_field] = params.pop("report_id")

    assert SendReportResource().request(params) == "success"

    check_management.assert_called_once_with(3)
    permission.is_allowed_by_biz.assert_not_called()
    assert send.call_args.kwargs["report_id"] == 8
    assert "id" not in send.call_args.kwargs
    assert send.call_args.kwargs["channels"] == params["channels"]


def test_resend_denies_users_outside_subscription(resend_report):
    params, username, check_management, _, send = resend_report
    username.return_value = "outsider"
    check_management.side_effect = PermissionDeniedError(context={"action_name": "manage_report"})

    with pytest.raises(PermissionDeniedError):
        SendReportResource().request(params)

    check_management.assert_called_once_with(3, raise_exception=True)
    send.assert_not_called()


def test_resend_denies_recipients_outside_send_history(resend_report):
    params, _, _, _, send = resend_report
    params["channels"][0]["subscribers"] = [{"id": "new-receiver", "type": "user", "is_enabled": True}]

    with pytest.raises(CustomException, match="not in the send records"):
        SendReportResource().request(params)

    send.assert_not_called()


@pytest.mark.parametrize("report_tenant", ["tenant-a", "tenant-b"])
def test_cross_business_resend_preserves_tenant_boundary(resend_report, mocker, settings, report_tenant):
    params, _, _, permission, send = resend_report
    settings.ENABLE_MULTI_TENANT_MODE = True
    mocker.patch.object(resources, "get_request_tenant_id", return_value="tenant-a")
    tenant_lookup = mocker.patch("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", return_value=report_tenant)

    if report_tenant == "tenant-a":
        assert SendReportResource().request(params) == "success"
        send.assert_called_once()
    else:
        with pytest.raises(CustomException, match="current tenant"):
            SendReportResource().request(params)
        send.assert_not_called()

    tenant_lookup.assert_called_once_with(3)
    permission.is_allowed_by_biz.assert_not_called()
