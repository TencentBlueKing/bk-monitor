# -*- coding: utf-8 -*-
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
from unittest import mock

from django.test import TestCase

from core.drf_resource.exceptions import CustomException
from bkmonitor.iam import ActionEnum
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

    def test_send_denies_report_id_when_iam_denies(self):
        resource = SendReportResource()
        with mock.patch("monitor_web.new_report.resources.Report.objects.get") as getter, mock.patch(
            "monitor_web.new_report.resources.Permission"
        ) as perm_cls:
            getter.return_value = SimpleNamespace(id=8, bk_biz_id=2, scenario_config={"index_set_id": 11})
            perm_cls.return_value.is_allowed_by_biz.return_value = False
            with self.assertRaises(CustomException):
                resource.perform_request({"report_id": 8})

    def test_send_denies_id_field_when_iam_denies(self):
        resource = SendReportResource()
        with mock.patch("monitor_web.new_report.resources.Report.objects.get") as getter, mock.patch(
            "monitor_web.new_report.resources.Permission"
        ) as perm_cls:
            getter.return_value = SimpleNamespace(id=8, bk_biz_id=2, scenario_config={"index_set_id": 11})
            perm_cls.return_value.is_allowed_by_biz.return_value = False
            with self.assertRaises(CustomException):
                resource.perform_request({"id": 8})

    def test_send_allows_report_id_when_iam_grants(self):
        resource = SendReportResource()
        with mock.patch("monitor_web.new_report.resources.Report.objects.get") as getter, mock.patch(
            "monitor_web.new_report.resources.Permission"
        ) as perm_cls, mock.patch("monitor_web.new_report.resources.api.monitor.send_report"):
            getter.return_value = SimpleNamespace(id=8, bk_biz_id=2, scenario_config={"index_set_id": 11})
            perm_cls.return_value.is_allowed_by_biz.return_value = True
            self.assertEqual(resource.perform_request({"report_id": 8}), "success")
            perm_cls.return_value.is_allowed_by_biz.assert_called_once_with(2, ActionEnum.VIEW_BUSINESS)
