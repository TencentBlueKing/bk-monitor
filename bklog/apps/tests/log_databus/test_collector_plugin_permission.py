# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

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
        if "bk_biz_id__in" in kwargs:
            allowed = set(kwargs["bk_biz_id__in"])
            return _QuerySet([item for item in self.items if item.bk_biz_id in allowed])
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

    def test_update_business_plugin_without_request_biz_calls_iam(self):
        perm = RequireBizActionPermission([ActionEnum.CREATE_COLLECTION])
        request = SimpleNamespace(data={}, query_params={}, user=SimpleNamespace(is_superuser=False))
        view = SimpleNamespace(action="update")
        obj = SimpleNamespace(bk_biz_id=2)
        self.assertTrue(perm.has_permission(request, view))
        with patch("apps.iam.handlers.drf.settings") as settings, patch("apps.iam.handlers.drf.Permission") as perm_cls:
            settings.IGNORE_IAM_PERMISSION = False
            perm_cls.return_value.is_allowed.side_effect = RuntimeError("iam denied")
            with self.assertRaises(RuntimeError):
                perm.has_object_permission(request, view, obj)
            perm_cls.return_value.is_allowed.assert_called_once()
            self.assertEqual(perm.resources[0].id, "2")

    def test_destroy_business_plugin_without_request_biz_allows_when_iam_grants(self):
        perm = RequireBizActionPermission([ActionEnum.CREATE_COLLECTION])
        request = SimpleNamespace(data={}, query_params={}, user=SimpleNamespace(is_superuser=False))
        view = SimpleNamespace(action="destroy")
        obj = SimpleNamespace(bk_biz_id=2)
        with patch("apps.iam.handlers.drf.settings") as settings, patch("apps.iam.handlers.drf.Permission") as perm_cls:
            settings.IGNORE_IAM_PERMISSION = False
            perm_cls.return_value.is_allowed.return_value = True
            self.assertTrue(perm.has_object_permission(request, view, obj))
            perm_cls.return_value.is_allowed.assert_called_once()
            self.assertEqual(perm.resources[0].id, "2")

    def test_deny_zero_biz_id(self):
        perm = RequireBizActionPermission([ActionEnum.CREATE_COLLECTION])
        request = SimpleNamespace(data={"bk_biz_id": 0}, query_params={}, user=SimpleNamespace(is_superuser=False))
        self.assertFalse(perm.has_permission(request, None))

    def test_deny_null_biz_id(self):
        perm = RequireBizActionPermission([ActionEnum.CREATE_COLLECTION])
        request = SimpleNamespace(data={"bk_biz_id": None}, query_params={}, user=SimpleNamespace(is_superuser=False))
        self.assertFalse(perm.has_permission(request, None))

    def test_deny_object_with_zero_biz_id(self):
        perm = RequireBizActionPermission([ActionEnum.CREATE_COLLECTION])
        request = SimpleNamespace(data={}, query_params={}, user=SimpleNamespace(is_superuser=False))
        obj = SimpleNamespace(bk_biz_id=0)
        self.assertFalse(perm.has_object_permission(request, None, obj))

    def test_public_object_uses_request_biz_for_instances(self):
        perm = RequireBizActionPermission(
            [ActionEnum.CREATE_COLLECTION],
            allow_public_object_via_request_biz=True,
        )
        request = SimpleNamespace(
            data={"bk_biz_id": 2},
            query_params={},
            user=SimpleNamespace(is_superuser=False),
        )
        obj = SimpleNamespace(bk_biz_id=0)
        with patch("apps.iam.handlers.drf.settings") as settings, patch("apps.iam.handlers.drf.Permission") as perm_cls:
            settings.IGNORE_IAM_PERMISSION = False
            perm_cls.return_value.is_allowed.return_value = True
            self.assertTrue(perm.has_object_permission(request, None, obj))
            self.assertEqual(perm.resources[0].id, "2")

    def test_public_object_instances_deny_without_request_biz(self):
        perm = RequireBizActionPermission(
            [ActionEnum.CREATE_COLLECTION],
            allow_public_object_via_request_biz=True,
        )
        request = SimpleNamespace(data={}, query_params={}, user=SimpleNamespace(is_superuser=False))
        obj = SimpleNamespace(bk_biz_id=0)
        self.assertFalse(perm.has_object_permission(request, None, obj))

    def test_instances_deny_other_business_plugin(self):
        perm = RequireBizActionPermission(
            [ActionEnum.CREATE_COLLECTION],
            allow_public_object_via_request_biz=True,
        )
        request = SimpleNamespace(
            data={"bk_biz_id": 2},
            query_params={},
            user=SimpleNamespace(is_superuser=False),
        )
        obj = SimpleNamespace(bk_biz_id=3)
        self.assertFalse(perm.has_object_permission(request, None, obj))

    def test_superuser_can_update_public_plugin(self):
        perm = RequireBizActionPermission([ActionEnum.CREATE_COLLECTION])
        request = SimpleNamespace(data={}, query_params={}, user=SimpleNamespace(is_superuser=True))
        obj = SimpleNamespace(bk_biz_id=0)
        self.assertTrue(perm.has_object_permission(request, None, obj))

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
    def _list_view(self, query_params, is_superuser=False):
        view = CollectorPluginViewSet()
        view.action = "list"
        view.request = SimpleNamespace(
            query_params=query_params,
            data={},
            user=SimpleNamespace(is_superuser=is_superuser),
        )
        return view

    def test_list_without_biz_id_returns_empty(self):
        view = self._list_view({})
        qs = _QuerySet([SimpleNamespace(bk_biz_id=2), SimpleNamespace(bk_biz_id=0)])
        with patch.object(ModelViewSet, "get_queryset", return_value=qs):
            result = view.get_queryset()
        self.assertEqual(len(result), 0)

    def test_normal_user_list_zero_returns_empty(self):
        view = self._list_view({"bk_biz_id": "0"})
        qs = _QuerySet([SimpleNamespace(bk_biz_id=0), SimpleNamespace(bk_biz_id=2)])
        with patch.object(ModelViewSet, "get_queryset", return_value=qs):
            result = view.get_queryset()
        self.assertEqual(len(result), 0)

    def test_superuser_list_zero_returns_global_plugins(self):
        view = self._list_view({"bk_biz_id": "0"}, is_superuser=True)
        qs = _QuerySet(
            [
                SimpleNamespace(bk_biz_id=0),
                SimpleNamespace(bk_biz_id=2),
                SimpleNamespace(bk_biz_id=3),
            ]
        )
        with patch.object(ModelViewSet, "get_queryset", return_value=qs):
            result = view.get_queryset()
        self.assertEqual([item.bk_biz_id for item in result.items], [0])

    def test_business_list_includes_global_plugins(self):
        view = self._list_view({"bk_biz_id": "2"})
        qs = _QuerySet(
            [
                SimpleNamespace(bk_biz_id=0),
                SimpleNamespace(bk_biz_id=2),
                SimpleNamespace(bk_biz_id=3),
            ]
        )
        with patch.object(ModelViewSet, "get_queryset", return_value=qs):
            result = view.get_queryset()
        self.assertEqual(sorted(item.bk_biz_id for item in result.items), [0, 2])

    def test_list_filters_by_biz_id(self):
        view = self._list_view({"bk_biz_id": "2"})
        qs = _QuerySet([SimpleNamespace(bk_biz_id=2), SimpleNamespace(bk_biz_id=3)])
        with patch.object(ModelViewSet, "get_queryset", return_value=qs):
            result = view.get_queryset()
        self.assertEqual(len(result), 1)
        self.assertEqual(result.items[0].bk_biz_id, 2)

    def test_list_query_and_body_use_the_same_biz_id(self):
        view = CollectorPluginViewSet()
        view.action = "list"
        view.request = SimpleNamespace(
            query_params={"bk_biz_id": "3"},
            data={"bk_biz_id": 2},
            user=SimpleNamespace(is_superuser=False),
        )
        qs = _QuerySet(
            [
                SimpleNamespace(bk_biz_id=0),
                SimpleNamespace(bk_biz_id=2),
                SimpleNamespace(bk_biz_id=3),
            ]
        )
        with patch.object(ModelViewSet, "get_queryset", return_value=qs):
            result = view.get_queryset()
        self.assertEqual(sorted(item.bk_biz_id for item in result.items), [0, 2])

        perm = view.get_permissions()[0]
        with patch("apps.iam.handlers.drf.settings") as settings, patch("apps.iam.handlers.drf.Permission") as perm_cls:
            settings.IGNORE_IAM_PERMISSION = False
            perm_cls.return_value.is_allowed.return_value = True
            self.assertTrue(perm.has_permission(view.request, view))
            self.assertEqual(perm.resources[0].id, "2")

    def test_instances_uses_create_collection_on_request_biz(self):
        view = CollectorPluginViewSet()
        view.action = "instances"
        view.request = SimpleNamespace(data={}, query_params={}, user=SimpleNamespace(is_superuser=False))
        perms = view.get_permissions()
        self.assertEqual(len(perms), 1)
        self.assertEqual(perms[0].actions, [ActionEnum.CREATE_COLLECTION])
        self.assertTrue(perms[0].allow_public_object_via_request_biz)

    def test_update_uses_create_collection_without_public_object_bypass(self):
        view = CollectorPluginViewSet()
        view.action = "update"
        view.request = SimpleNamespace(data={}, query_params={}, user=SimpleNamespace(is_superuser=False))
        perms = view.get_permissions()
        self.assertEqual(len(perms), 1)
        self.assertEqual(perms[0].actions, [ActionEnum.CREATE_COLLECTION])
        self.assertFalse(perms[0].allow_public_object_via_request_biz)

    def test_retrieve_allows_public_plugin_via_request_biz(self):
        view = CollectorPluginViewSet()
        view.action = "retrieve"
        view.request = SimpleNamespace(data={}, query_params={}, user=SimpleNamespace(is_superuser=False))
        perms = view.get_permissions()
        self.assertEqual(len(perms), 1)
        self.assertEqual(perms[0].actions, [ActionEnum.VIEW_BUSINESS])
        self.assertTrue(perms[0].allow_public_object_via_request_biz)

    def test_list_then_instances_object_permission_for_global_plugin(self):
        view = self._list_view({"bk_biz_id": "2"})
        qs = _QuerySet(
            [
                SimpleNamespace(bk_biz_id=0, collector_plugin_id=9),
                SimpleNamespace(bk_biz_id=2, collector_plugin_id=8),
            ]
        )
        with patch.object(ModelViewSet, "get_queryset", return_value=qs):
            listed = view.get_queryset()
        public_plugin = [item for item in listed.items if item.bk_biz_id == 0][0]

        view.action = "instances"
        view.request = SimpleNamespace(
            data={"bk_biz_id": 2},
            query_params={"bk_biz_id": "2"},
            user=SimpleNamespace(is_superuser=False),
            authenticators=None,
            successful_authenticator=None,
        )
        with patch("apps.iam.handlers.drf.settings") as settings, patch("apps.iam.handlers.drf.Permission") as perm_cls:
            settings.IGNORE_IAM_PERMISSION = False
            perm_cls.return_value.is_allowed.return_value = True
            view.check_permissions(view.request)
            view.check_object_permissions(view.request, public_plugin)

        view.action = "update"
        view.request = SimpleNamespace(
            data={"bk_biz_id": 2},
            query_params={"bk_biz_id": "2"},
            user=SimpleNamespace(is_superuser=False),
            authenticators=None,
            successful_authenticator=None,
        )
        with self.assertRaises(PermissionDenied):
            view.check_object_permissions(view.request, public_plugin)
