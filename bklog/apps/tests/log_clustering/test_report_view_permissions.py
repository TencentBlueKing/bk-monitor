# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""
from types import SimpleNamespace

from django.test import TestCase

from apps.iam.handlers.drf import BusinessActionPermission, InstanceActionForDataPermission
from apps.log_clustering.views.report_views import ReportViewSet


class TestReportViewPermissions(TestCase):
    def test_send_without_index_set_or_biz_denies(self):
        view = ReportViewSet()
        view.action = "send"
        view.request = SimpleNamespace(data={}, query_params={})
        permissions = view.get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertFalse(isinstance(permissions[0], BusinessActionPermission))
        self.assertFalse(permissions[0].has_permission(view.request, view))

    def test_send_without_index_set_uses_manage_indices_when_biz_present(self):
        view = ReportViewSet()
        view.action = "send"
        view.request = SimpleNamespace(data={"bk_biz_id": 2}, query_params={})
        permissions = view.get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], BusinessActionPermission)

    def test_send_with_index_set_uses_instance_permission(self):
        view = ReportViewSet()
        view.action = "send"
        view.request = SimpleNamespace(data={"scenario_config": {"index_set_id": 11}}, query_params={})
        permissions = view.get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionForDataPermission)
