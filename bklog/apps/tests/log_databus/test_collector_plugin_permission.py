# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from apps.generic import ModelViewSet
from apps.iam import ActionEnum
from apps.log_databus.views.collector_plugin_views import (
    CollectorPluginViewSet,
    RequireBizActionPermission,
)


class _QuerySet(object):
    def __init__(self, items=None):
        self.items = list(items or [])

    def none(self):
        return _QuerySet([])

    def filter(self, **kwargs):
        return _QuerySet([item for item in self.items if item.bk_biz_id == kwargs.get("bk_biz_id")])

    def __eq__(self, other):
        return isinstance(other, _QuerySet) and self.items == other.items

    def __len__(self):
        return len(self.items)


class TestRequireBizActionPermission(TestCase):
    def test_deny_without_biz_id(self):
        perm = RequireBizActionPermission([ActionEnum.CREATE_COLLECTION])
        request = SimpleNamespace(data={}, query_params={}, user=SimpleNamespace(is_superuser=False))
        self.assertFalse(perm.has_permission(request, None))

    def test_deny_zero_biz_id(self):
        perm = RequireBizActionPermission([ActionEnum.CREATE_COLLECTION])
        request = SimpleNamespace(data={"bk_biz_id": 0}, query_params={}, user=SimpleNamespace(is_superuser=False))
        self.assertFalse(perm.has_permission(request, None))

    def test_deny_null_biz_id(self):
        perm = RequireBizActionPermission([ActionEnum.CREATE_COLLECTION])
        request = SimpleNamespace(data={"bk_biz_id": None}, query_params={}, user=SimpleNamespace(is_superuser=False))
        self.assertFalse(perm.has_permission(request, None))

    def test_deny_object_with_zero_biz_id(self):
        perm = RequireBizActionPermission([ActionEnum.MANAGE_COLLECTION])
        request = SimpleNamespace(data={}, query_params={}, user=SimpleNamespace(is_superuser=False))
        obj = SimpleNamespace(bk_biz_id=0)
        self.assertFalse(perm.has_object_permission(request, None, obj))

    def test_superuser_can_access_zero_biz_id(self):
        perm = RequireBizActionPermission([ActionEnum.CREATE_COLLECTION])
        request = SimpleNamespace(data={"bk_biz_id": 0}, query_params={}, user=SimpleNamespace(is_superuser=True))
        self.assertTrue(perm.has_permission(request, None))

    def test_positive_biz_id_calls_iam(self):
        perm = RequireBizActionPermission([ActionEnum.VIEW_BUSINESS])
        request = SimpleNamespace(data={"bk_biz_id": 2}, query_params={}, user=SimpleNamespace(is_superuser=False))
        with patch("apps.iam.handlers.drf.settings") as settings, patch("apps.iam.handlers.drf.Permission") as perm_cls:
            settings.IGNORE_IAM_PERMISSION = False
            perm_cls.return_value.is_allowed.return_value = True
            self.assertTrue(perm.has_permission(request, None))
            self.assertEqual(len(perm.resources), 1)


class TestCollectorPluginViewSetQueryset(TestCase):
    def test_list_without_biz_id_returns_empty(self):
        view = CollectorPluginViewSet()
        view.action = "list"
        view.request = SimpleNamespace(query_params={}, data={})
        qs = _QuerySet([SimpleNamespace(bk_biz_id=2), SimpleNamespace(bk_biz_id=0)])
        with patch.object(ModelViewSet, "get_queryset", return_value=qs):
            result = view.get_queryset()
        self.assertEqual(len(result), 0)

    def test_list_filters_by_biz_id(self):
        view = CollectorPluginViewSet()
        view.action = "list"
        view.request = SimpleNamespace(query_params={"bk_biz_id": "2"}, data={})
        qs = _QuerySet([SimpleNamespace(bk_biz_id=2), SimpleNamespace(bk_biz_id=3)])
        with patch.object(ModelViewSet, "get_queryset", return_value=qs):
            result = view.get_queryset()
        self.assertEqual(len(result), 1)
        self.assertEqual(result.items[0].bk_biz_id, 2)
