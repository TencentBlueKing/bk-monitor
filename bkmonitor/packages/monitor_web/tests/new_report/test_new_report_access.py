# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from types import SimpleNamespace
from unittest import TestCase, mock

from constants.new_report import SendStatusEnum
from core.drf_resource.exceptions import CustomException
from monitor_web.new_report.resources import (
    CancelOrResubscribeReportResource,
    CreateOrUpdateReportResource,
    GetReportListResource,
    GetReportResource,
    GetSendRecordsResource,
    SendReportResource,
    _assert_report_access,
)

GROUP_ID = "bk_biz_maintainer"


def _start_patches(test_case, patchers):
    mocks = []
    for patcher in patchers:
        mocks.append(patcher.start())
        test_case.addCleanup(patcher.stop)
    return mocks


class TestAssertReportAccess(TestCase):
    def setUp(self):
        _, self.channel_filter, self.resource, self.check_permission = _start_patches(
            self,
            [
                mock.patch("monitor_web.new_report.resources.get_request_username", return_value="alice"),
                mock.patch("monitor_web.new_report.resources.ReportChannel.objects.filter"),
                mock.patch("monitor_web.new_report.resources.resource"),
                mock.patch("monitor_web.new_report.resources.GetReportListResource.check_permission"),
            ],
        )
        self.resource.report.group_list.return_value = []

    def set_subscribers(self, subscribers):
        self.channel_filter.return_value.first.return_value = SimpleNamespace(subscribers=subscribers)

    def test_creator_is_allowed(self):
        _assert_report_access(8, 2, "alice")
        self.channel_filter.assert_not_called()
        self.check_permission.assert_not_called()

    def test_listed_subscriber_is_allowed_after_cancel(self):
        self.set_subscribers([{"id": "alice", "type": "user", "is_enabled": False}])
        _assert_report_access(8, 2, "bob")
        self.channel_filter.assert_called_once_with(report_id=8, channel_name="user")
        self.check_permission.assert_not_called()

    def test_group_member_is_resolved_with_report_business(self):
        self.set_subscribers([{"id": GROUP_ID, "type": "group", "is_enabled": True}])
        self.resource.report.group_list.return_value = [{"id": GROUP_ID, "children": ["alice"]}]
        _assert_report_access(8, 2, "bob")
        self.resource.report.group_list.assert_called_once_with(bk_biz_id=2)
        self.check_permission.assert_not_called()

    def test_unrelated_user_requires_manage_permission_of_report_business(self):
        self.set_subscribers(
            [{"id": "bob", "type": "user", "is_enabled": True}, {"id": GROUP_ID, "type": "group", "is_enabled": True}]
        )
        self.resource.report.group_list.return_value = [{"id": GROUP_ID, "children": ["bob"]}]
        self.check_permission.side_effect = CustomException("denied")
        with self.assertRaises(CustomException):
            _assert_report_access(8, 2, "bob")
        self.check_permission.assert_called_once_with(2, raise_exception=True)

    def test_report_without_user_channel_requires_manage_permission(self):
        self.channel_filter.return_value.first.return_value = None
        _assert_report_access(8, 2, "bob")
        self.check_permission.assert_called_once_with(2, raise_exception=True)
        self.resource.report.group_list.assert_not_called()


class TestReportReadAccess(TestCase):
    @mock.patch("monitor_web.new_report.resources._assert_report_access", side_effect=CustomException("denied"))
    @mock.patch("monitor_web.new_report.resources.ReportChannel.objects.filter")
    @mock.patch("monitor_web.new_report.resources.Report.objects.values")
    def test_get_report_checks_access(self, report_values, channel_filter, assert_access):
        report_values.return_value.get.return_value = {"id": 8, "bk_biz_id": 2, "create_user": "bob"}
        with self.assertRaises(CustomException):
            GetReportResource().perform_request({"report_id": 8})
        assert_access.assert_called_once_with(8, 2, "bob")
        channel_filter.assert_not_called()

    @mock.patch("monitor_web.new_report.resources._assert_report_access", side_effect=CustomException("denied"))
    @mock.patch("monitor_web.new_report.resources.ReportSendRecord.objects.filter")
    @mock.patch("monitor_web.new_report.resources.Report.objects.filter")
    def test_get_send_records_checks_access(self, report_filter, record_filter, assert_access):
        report_filter.return_value.first.return_value = SimpleNamespace(id=8, bk_biz_id=2, create_user="bob")
        with self.assertRaises(CustomException):
            GetSendRecordsResource().perform_request({"report_id": 8})
        report_filter.assert_called_once_with(id=8)
        assert_access.assert_called_once_with(8, 2, "bob")
        record_filter.assert_not_called()

    @mock.patch("monitor_web.new_report.resources._assert_report_access")
    @mock.patch("monitor_web.new_report.resources.ReportSendRecord.objects.filter")
    @mock.patch("monitor_web.new_report.resources.Report.objects.filter")
    def test_get_send_records_missing_report_returns_empty(self, report_filter, record_filter, assert_access):
        report_filter.return_value.first.return_value = None
        self.assertEqual(GetSendRecordsResource().perform_request({"report_id": 8}), [])
        assert_access.assert_not_called()
        record_filter.assert_not_called()


class TestCancelOrResubscribe(TestCase):
    def setUp(self):
        (
            _,
            self.channel_get,
            self.report_get,
            self.resource,
            _,
            self.channel_filter,
            self.check_permission,
        ) = _start_patches(
            self,
            [
                mock.patch(
                    "monitor_web.new_report.resources.get_request",
                    return_value=SimpleNamespace(user=SimpleNamespace(username="alice")),
                ),
                mock.patch("monitor_web.new_report.resources.ReportChannel.objects.get"),
                mock.patch("monitor_web.new_report.resources.Report.objects.get"),
                mock.patch("monitor_web.new_report.resources.resource"),
                mock.patch("monitor_web.new_report.resources.get_request_username", return_value="alice"),
                mock.patch("monitor_web.new_report.resources.ReportChannel.objects.filter"),
                mock.patch("monitor_web.new_report.resources.GetReportListResource.check_permission"),
            ],
        )
        self.report_get.return_value = SimpleNamespace(id=8, bk_biz_id=2, create_user="bob")
        self.resource.report.group_list.return_value = [{"id": GROUP_ID, "children": ["alice"]}]
        self.check_permission.side_effect = CustomException("denied")

    def set_channel(self, subscribers):
        self.channel = SimpleNamespace(report_id=8, subscribers=subscribers, save=mock.Mock())
        self.channel_get.return_value = self.channel
        self.channel_filter.return_value.first.return_value = self.channel

    def change(self, is_enabled):
        return CancelOrResubscribeReportResource().perform_request({"report_id": 8, "is_enabled": is_enabled})

    def test_listed_subscriber_changes_only_own_state(self):
        self.set_channel(
            [{"id": "alice", "type": "user", "is_enabled": True}, {"id": "bob", "type": "user", "is_enabled": True}]
        )
        self.assertEqual(self.change(False), "success")
        self.assertEqual(
            self.channel.subscribers,
            [{"id": "alice", "type": "user", "is_enabled": False}, {"id": "bob", "type": "user", "is_enabled": True}],
        )
        self.channel.save.assert_called_once_with()
        self.resource.report.group_list.assert_not_called()

    def test_group_member_appends_own_entry(self):
        self.set_channel([{"id": GROUP_ID, "type": "group", "is_enabled": True}])
        self.assertEqual(self.change(False), "success")
        self.assertEqual(self.channel.subscribers[-1], {"id": "alice", "type": "user", "is_enabled": False})
        self.report_get.assert_called_once_with(id=8)
        self.resource.report.group_list.assert_called_once_with(bk_biz_id=2)
        self.channel.save.assert_called_once_with()

    def test_non_subscriber_cannot_append_entry(self):
        self.set_channel(
            [{"id": "bob", "type": "user", "is_enabled": True}, {"id": GROUP_ID, "type": "group", "is_enabled": True}]
        )
        self.resource.report.group_list.return_value = [{"id": GROUP_ID, "children": ["bob"]}]
        with self.assertRaises(CustomException):
            self.change(True)
        self.assertEqual(len(self.channel.subscribers), 2)
        self.channel.save.assert_not_called()
        self.check_permission.assert_called_once_with(2, raise_exception=True)

    def test_creator_not_in_list_appends_own_entry(self):
        self.report_get.return_value.create_user = "alice"
        self.set_channel([{"id": "bob", "type": "user", "is_enabled": True}])
        self.assertEqual(self.change(False), "success")
        self.assertEqual(self.channel.subscribers[-1], {"id": "alice", "type": "user", "is_enabled": False})
        self.check_permission.assert_not_called()
        self.channel_filter.assert_not_called()

    def test_manager_not_in_list_appends_own_entry(self):
        self.check_permission.side_effect = None
        self.set_channel([{"id": "bob", "type": "user", "is_enabled": True}])
        self.assertEqual(self.change(True), "success")
        self.assertEqual(self.channel.subscribers[-1], {"id": "alice", "type": "user", "is_enabled": True})
        self.check_permission.assert_called_once_with(2, raise_exception=True)


class TestSendReportAccess(TestCase):
    def setUp(self):
        _, self.assert_access, self.check_permission, self.record_filter, self.api = _start_patches(
            self,
            [
                mock.patch(
                    "monitor_web.new_report.resources.Report.objects.get",
                    return_value=SimpleNamespace(id=8, bk_biz_id=2, create_user="bob", scenario_config={}),
                ),
                mock.patch("monitor_web.new_report.resources._assert_report_access"),
                mock.patch(
                    "monitor_web.new_report.resources.GetReportListResource.check_permission", return_value=False
                ),
                mock.patch("monitor_web.new_report.resources.ReportSendRecord.objects.filter"),
                mock.patch("monitor_web.new_report.resources.api"),
            ],
        )
        self.records = (
            self.record_filter.return_value.exclude.return_value.order_by.return_value.values_list.return_value
        )
        self.records.__getitem__.return_value = [
            [{"id": "alice", "type": "user", "result": True, "message": ""}],
            [{"id": "carol", "type": "user", "result": False, "message": "error"}],
        ]

    @staticmethod
    def user_channel(*ids):
        return {
            "channel_name": "user",
            "is_enabled": True,
            "subscribers": [{"id": i, "type": "user", "is_enabled": True} for i in ids],
        }

    def send(self, **data):
        return SendReportResource().perform_request(dict(data, report_id=8))

    def test_subscriber_resends_to_recorded_recipients_from_other_business(self):
        channels = [self.user_channel("alice", "carol")]
        self.assertEqual(self.send(bk_biz_id=3, channels=channels), "success")
        self.assert_access.assert_called_once_with(8, 2, "bob")
        self.check_permission.assert_called_once_with(2)
        self.record_filter.assert_called_once_with(report_id=8, channel_name="user")
        self.record_filter.return_value.exclude.assert_called_once_with(send_status=SendStatusEnum.NO_STATUS.value)
        self.record_filter.return_value.exclude.return_value.order_by.assert_called_once_with("-send_time")
        self.records.__getitem__.assert_called_once_with(slice(None, 100, None))
        self.api.monitor.send_report.assert_called_once_with(report_id=8, bk_biz_id=3, channels=channels)

    def test_non_manager_cannot_add_recipients(self):
        with self.assertRaises(CustomException):
            self.send(channels=[self.user_channel("alice", "dave")])
        self.api.monitor.send_report.assert_not_called()

    def test_non_manager_must_specify_channels(self):
        with self.assertRaises(CustomException):
            self.send()
        self.record_filter.assert_not_called()
        self.api.monitor.send_report.assert_not_called()

    def test_manager_is_not_limited_to_send_records(self):
        self.check_permission.return_value = True
        channels = [self.user_channel("dave")]
        self.send(channels=channels)
        self.record_filter.assert_not_called()
        self.api.monitor.send_report.assert_called_once_with(report_id=8, channels=channels)

    def test_access_check_failure_stops_sending(self):
        self.assert_access.side_effect = CustomException("denied")
        with self.assertRaises(CustomException):
            self.send(channels=[self.user_channel("alice")])
        self.check_permission.assert_not_called()
        self.api.monitor.send_report.assert_not_called()


class TestReportListAccess(TestCase):
    @mock.patch("monitor_web.new_report.resources.Report.objects.all")
    @mock.patch(
        "monitor_web.new_report.resources.GetReportListResource.check_permission",
        side_effect=CustomException("denied"),
    )
    def test_non_self_view_requires_manage_permission(self, check_permission, _report_all):
        for create_type in ("manager", "user", "other"):
            with self.assertRaises(CustomException):
                GetReportListResource().perform_request({"create_type": create_type, "bk_biz_id": 2})
        self.assertEqual(check_permission.call_count, 3)
        check_permission.assert_called_with(2, raise_exception=True)


class TestReportEditable(TestCase):
    def setUp(self):
        _, self.permission_cls = _start_patches(
            self,
            [
                mock.patch("monitor_web.new_report.resources.get_request_username", return_value="alice"),
                mock.patch("monitor_web.new_report.resources.Permission"),
            ],
        )
        self.permission_cls.return_value.skip_check = False

    def test_manager_can_edit(self):
        CreateOrUpdateReportResource._assert_report_editable(SimpleNamespace(id=8, create_user="bob"), True)

    def test_creator_can_edit(self):
        CreateOrUpdateReportResource._assert_report_editable(SimpleNamespace(id=8, create_user="alice"), False)

    def test_other_user_cannot_edit(self):
        with self.assertRaises(CustomException):
            CreateOrUpdateReportResource._assert_report_editable(SimpleNamespace(id=8, create_user="bob"), False)

    def test_api_process_keeps_existing_behavior(self):
        self.permission_cls.return_value.skip_check = True
        CreateOrUpdateReportResource._assert_report_editable(SimpleNamespace(id=8, create_user="bob"), False)
