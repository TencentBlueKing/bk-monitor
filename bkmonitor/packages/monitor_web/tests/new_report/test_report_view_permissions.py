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

from bkmonitor.iam import ActionEnum
from core.errors.iam import PermissionDeniedError
from monitor_web.new_report.views import NewReportViewSet, ReportManagePermission, ReportSendPermission


class TestNewReportViewSetPermissions(TestCase):
    def test_clone_and_delete_require_manage_report(self):
        view = NewReportViewSet()
        for action in ("clone_report", "delete_report"):
            view.action = action
            permissions = view.get_permissions()
            self.assertEqual(len(permissions), 1)
            self.assertIsInstance(permissions[0], ReportManagePermission)
            self.assertEqual(permissions[0].actions, [ActionEnum.MANAGE_REPORT])

    def test_self_service_write_actions_do_not_require_manage_report(self):
        view = NewReportViewSet()
        view.action = "create_or_update_report"
        self.assertEqual(view.get_permissions(), [])

    def test_send_report_uses_report_send_permission(self):
        view = NewReportViewSet()
        view.action = "send_report"
        permissions = view.get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], ReportSendPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.VIEW_BUSINESS])
        self.assertNotEqual(permissions[0].actions, [ActionEnum.MANAGE_REPORT])

    def test_manage_permission_denies_invalid_report_id(self):
        perm = ReportManagePermission()
        for data in ({}, [], {"report_id": "invalid"}, {"report_id": 0}):
            self.assertFalse(perm.has_permission(SimpleNamespace(data=data), None))

    @mock.patch("monitor_web.new_report.views.ResourceEnum.BUSINESS.create_instance")
    @mock.patch("monitor_web.new_report.views.Report.objects.filter")
    @mock.patch("monitor_web.new_report.resources.Permission")
    def test_manage_permission_uses_report_business(self, perm_cls, report_filter, create_instance):
        report_filter.return_value.values_list.return_value.first.return_value = 2
        resource = create_instance.return_value
        perm = ReportManagePermission()
        request = SimpleNamespace(data={"report_id": 100, "bk_biz_id": 1})

        perm_cls.return_value.is_allowed.return_value = True
        self.assertTrue(perm.has_permission(request, None))

        report_filter.assert_called_once_with(id=100)
        create_instance.assert_called_once_with(2)
        perm_cls.return_value.is_allowed.assert_called_once_with(
            ActionEnum.MANAGE_REPORT,
            [resource],
            raise_exception=True,
        )

    @mock.patch("monitor_web.new_report.views.Report.objects.filter")
    @mock.patch("monitor_web.new_report.resources.Permission")
    def test_superuser_can_manage_report_without_iam_grant(self, perm_cls, report_filter):
        report_filter.return_value.values_list.return_value.first.return_value = 2
        request = SimpleNamespace(
            data={"report_id": 100, "bk_biz_id": 1},
            user=SimpleNamespace(username="superuser", tenant_id="default", is_superuser=True),
        )
        for action in ("clone_report", "delete_report"):
            with self.subTest(action=action):
                view = NewReportViewSet()
                view.action = action
                self.assertTrue(view.get_permissions()[0].has_permission(request, view))
        perm_cls.assert_not_called()

    @mock.patch("monitor_web.new_report.views.Report.objects.filter")
    def test_manage_permission_denies_unknown_report(self, report_filter):
        report_filter.return_value.values_list.return_value.first.return_value = None
        perm = ReportManagePermission()
        request = SimpleNamespace(data={"report_id": 100})

        self.assertFalse(perm.has_permission(request, None))

    def test_send_permission_denies_missing_report_and_biz(self):
        perm = ReportSendPermission()
        self.assertFalse(perm.has_permission(SimpleNamespace(data={}), None))
        self.assertFalse(perm.has_permission(SimpleNamespace(data={"report_id": 0}), None))

    @mock.patch("monitor_web.new_report.views.Report.objects.filter")
    @mock.patch("bkmonitor.iam.drf.Permission")
    def test_existing_report_defers_access_check_to_resource(self, perm_cls, report_filter):
        report_filter.return_value.values_list.return_value.first.return_value = 2
        perm = ReportSendPermission()
        for id_field in ("report_id", "id"):
            with self.subTest(id_field=id_field):
                request = SimpleNamespace(data={id_field: 100, "bk_biz_id": 1})
                self.assertTrue(perm.has_permission(request, None))
        perm_cls.assert_not_called()

    @mock.patch("monitor_web.new_report.views.Report.objects.filter")
    def test_existing_report_requires_real_object_and_nonzero_business(self, report_filter):
        for bk_biz_id in (None, 0):
            with self.subTest(bk_biz_id=bk_biz_id):
                report_filter.return_value.values_list.return_value.first.return_value = bk_biz_id
                self.assertFalse(ReportSendPermission().has_permission(SimpleNamespace(data={"report_id": 100}), None))

    @mock.patch("monitor_web.new_report.views.ResourceEnum.BUSINESS.create_instance")
    @mock.patch("bkmonitor.iam.drf.Permission")
    def test_draft_send_still_requires_business_permission(self, perm_cls, create_instance):
        resource = create_instance.return_value
        request = SimpleNamespace(data={"bk_biz_id": 2})
        perm_cls.return_value.is_allowed.side_effect = PermissionDeniedError(context={"action_name": "view_business"})
        with self.assertRaises(PermissionDeniedError):
            ReportSendPermission().has_permission(request, None)
        create_instance.assert_called_once_with(2)
        perm_cls.return_value.is_allowed.assert_called_once_with(
            action=ActionEnum.VIEW_BUSINESS,
            resources=[resource],
            raise_exception=True,
        )

    @mock.patch("monitor_web.new_report.views.GetReportListResource.check_permission", return_value=True)
    @mock.patch("bkmonitor.iam.drf.Permission")
    def test_superuser_draft_uses_tenant_scoped_management_permission(self, perm_cls, check_permission):
        for bk_biz_id in (2, -2):
            with self.subTest(bk_biz_id=bk_biz_id):
                request = SimpleNamespace(
                    data={"bk_biz_id": bk_biz_id},
                    user=SimpleNamespace(username="superuser", tenant_id="default", is_superuser=True),
                )
                self.assertTrue(ReportSendPermission().has_permission(request, None))
                check_permission.assert_called_with(bk_biz_id, raise_exception=True, request=request)
        perm_cls.assert_not_called()
