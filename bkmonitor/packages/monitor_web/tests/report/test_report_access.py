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
import datetime
from types import SimpleNamespace
from unittest import TestCase, mock

from monitor_web.report.resources import (
    ReportCloneResource,
    ReportCreateOrUpdateResource,
    ReportDeleteResource,
    _is_report_manager,
)


def _request(username="alice", is_superuser=False):
    return SimpleNamespace(user=SimpleNamespace(username=username, is_superuser=is_superuser))


class TestReportManagerCheck(TestCase):
    @mock.patch("monitor_web.report.resources.get_request")
    def test_superuser_or_report_manager(self, get_request):
        report_item = SimpleNamespace(format_managers=["bob"])

        get_request.return_value = _request(is_superuser=True)
        self.assertTrue(_is_report_manager(report_item))
        get_request.return_value = _request("bob")
        self.assertTrue(_is_report_manager(report_item))
        get_request.return_value = _request("alice")
        self.assertFalse(_is_report_manager(report_item))


class TestReportCloneAndDelete(TestCase):
    @mock.patch("monitor_web.report.resources.ReportItems.objects.create")
    @mock.patch("monitor_web.report.resources._is_report_manager", return_value=False)
    @mock.patch("monitor_web.report.resources.ReportItems.objects.filter")
    def test_clone_requires_manager(self, item_filter, is_manager, item_create):
        item_filter.return_value.values.return_value = [{"id": 1, "mail_title": "report", "managers": []}]
        with self.assertRaises(PermissionError):
            ReportCloneResource().perform_request({"report_item_id": 1})
        is_manager.assert_called_once()
        item_create.assert_not_called()

    @mock.patch("monitor_web.report.resources.ReportContents.objects.filter")
    @mock.patch("monitor_web.report.resources._is_report_manager", return_value=False)
    @mock.patch("monitor_web.report.resources.ReportItems.objects.filter")
    def test_delete_requires_manager(self, item_filter, is_manager, content_filter):
        report_item = SimpleNamespace(id=1)
        item_filter.return_value.first.return_value = report_item
        with self.assertRaises(PermissionError):
            ReportDeleteResource().perform_request({"report_item_id": 1})
        is_manager.assert_called_once_with(report_item)
        item_filter.return_value.delete.assert_not_called()
        content_filter.assert_not_called()

    @mock.patch("monitor_web.report.resources.ReportContents.objects.filter")
    @mock.patch("monitor_web.report.resources._is_report_manager", return_value=True)
    @mock.patch("monitor_web.report.resources.ReportItems.objects.filter")
    def test_delete_by_manager(self, item_filter, is_manager, content_filter):
        item_filter.return_value.first.return_value = SimpleNamespace(id=1)
        self.assertEqual(ReportDeleteResource().perform_request({"report_item_id": 1}), "success")
        item_filter.return_value.delete.assert_called_once_with()
        content_filter.assert_called_once_with(report_item=1)
        content_filter.return_value.delete.assert_called_once_with()

    @mock.patch("monitor_web.report.resources.ReportContents.objects.filter")
    @mock.patch("monitor_web.report.resources._is_report_manager")
    @mock.patch("monitor_web.report.resources.ReportItems.objects.filter")
    def test_delete_missing_report_keeps_original_behavior(self, item_filter, is_manager, content_filter):
        item_filter.return_value.first.return_value = None
        self.assertEqual(ReportDeleteResource().perform_request({"report_item_id": 1}), "success")
        is_manager.assert_not_called()
        item_filter.return_value.delete.assert_called_once_with()
        content_filter.return_value.delete.assert_called_once_with()


class TestReportEdit(TestCase):
    def setUp(self):
        self.report_item = SimpleNamespace(receivers=[])
        patchers = [
            mock.patch("monitor_web.report.resources.get_request", return_value=_request("alice")),
            mock.patch("monitor_web.report.resources._is_report_manager", return_value=False),
            mock.patch("monitor_web.report.resources.ReportItems.objects.filter"),
            mock.patch("monitor_web.report.resources.resource"),
        ]
        mocks = []
        for patcher in patchers:
            mocks.append(patcher.start())
            self.addCleanup(patcher.stop)
        _, self.is_manager, self.item_filter, self.resource = mocks
        self.item_filter.return_value.__getitem__.return_value = self.report_item
        self.resource.report.group_list.return_value = []

    def edit(self, **data):
        return ReportCreateOrUpdateResource().perform_request(dict(data, report_item_id=1))

    def test_manager_keeps_full_update(self):
        self.is_manager.return_value = True
        with mock.patch("monitor_web.report.resources.transaction"):
            self.assertEqual(self.edit(mail_title="changed", is_enabled=False, is_link_enabled=True), "success")
        self.item_filter.return_value.update.assert_called_once_with(
            mail_title="changed", is_enabled=False, is_link_enabled=True, last_send_time=None
        )

    def test_non_manager_only_changes_own_receiver(self):
        self.report_item.receivers = [
            {"id": "alice", "type": "user", "is_enabled": True, "create_time": "2024-01-01T00:00:00"},
            {"id": "bob", "type": "user", "is_enabled": True},
        ]
        result = self.edit(
            mail_title="changed",
            is_enabled=False,
            is_link_enabled=True,
            receivers=[
                {"id": "alice", "type": "user", "is_enabled": False},
                {"id": "bob", "type": "user", "is_enabled": False},
                {"id": "carol", "type": "user", "is_enabled": True},
            ],
        )
        self.assertEqual(result, "success")
        self.item_filter.return_value.update.assert_called_once_with(
            receivers=[
                {"id": "alice", "type": "user", "is_enabled": False, "create_time": "2024-01-01T00:00:00"},
                {"id": "bob", "type": "user", "is_enabled": True},
            ]
        )
        self.resource.report.group_list.assert_not_called()

    def test_cancelled_receiver_can_resubscribe(self):
        self.report_item.receivers = [{"id": "alice", "type": "user", "is_enabled": False}]
        self.edit(receivers=[{"id": "alice", "type": "user", "is_enabled": True}])
        self.item_filter.return_value.update.assert_called_once_with(
            receivers=[{"id": "alice", "type": "user", "is_enabled": True}]
        )

    def test_group_member_appends_own_receiver(self):
        self.report_item.receivers = [{"id": "bk_biz_maintainer", "type": "group", "is_enabled": True}]
        self.resource.report.group_list.return_value = [{"id": "bk_biz_maintainer", "children": ["alice"]}]
        self.edit(
            receivers=[
                {"id": "bk_biz_maintainer", "type": "group", "is_enabled": True},
                {"id": "alice", "type": "user", "is_enabled": False},
            ]
        )
        receivers = self.item_filter.return_value.update.call_args[1]["receivers"]
        self.assertEqual(len(receivers), 2)
        appended = dict(receivers[1])
        datetime.datetime.strptime(appended.pop("create_time"), "%Y-%m-%dT%H:%M:%S")
        self.assertEqual(appended, {"id": "alice", "name": "alice", "type": "user", "is_enabled": False})

    def test_unrelated_user_is_rejected(self):
        self.report_item.receivers = [
            {"id": "bob", "type": "user", "is_enabled": True},
            {"id": "bk_biz_tester", "type": "group", "is_enabled": True},
        ]
        self.resource.report.group_list.return_value = [{"id": "bk_biz_tester", "children": ["bob"]}]
        with self.assertRaises(PermissionError):
            self.edit(receivers=[{"id": "alice", "type": "user", "is_enabled": True}])
        self.item_filter.return_value.update.assert_not_called()

    def test_request_without_own_receiver_is_rejected(self):
        self.report_item.receivers = [{"id": "alice", "type": "user", "is_enabled": True}]
        with self.assertRaises(PermissionError):
            self.edit(is_enabled=False)
        self.item_filter.return_value.update.assert_not_called()
