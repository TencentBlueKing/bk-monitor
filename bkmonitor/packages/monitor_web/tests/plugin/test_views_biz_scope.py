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

from core.errors.plugin import BizChangedError, PluginIDNotExist, RelatedItemsExist
from monitor_web.plugin.views import CollectorPluginViewSet

MODULE = "monitor_web.plugin.views"


class Denied(Exception):
    pass


def _plugin(bk_biz_id, plugin_id="p1"):
    return SimpleNamespace(plugin_id=plugin_id, bk_biz_id=bk_biz_id, delete_allowed=True)


@mock.patch(f"{MODULE}.api")
@mock.patch(f"{MODULE}.transaction")
@mock.patch(f"{MODULE}.PluginVersionHistory.origin_objects")
@mock.patch(f"{MODULE}.CollectorPluginMeta.origin_objects")
@mock.patch(f"{MODULE}.CollectorPluginMeta.objects")
@mock.patch(f"{MODULE}.assert_manage_pub_plugin_permission")
class TestDeletePluginBizScope(TestCase):
    def test_limited_to_request_biz_and_global(self, assert_pub, plugin_objects, origin_objects, *_):
        plugin_objects.filter.return_value = [_plugin(2)]

        CollectorPluginViewSet().delete(SimpleNamespace(data={"plugin_ids": ["p1"]}, biz_id=2))

        plugin_objects.filter.assert_called_once_with(plugin_id__in=["p1"], bk_biz_id__in=[0, 2])
        origin_objects.filter.assert_called_once_with(plugin_id="p1", bk_biz_id__in=[0, 2])
        assert_pub.assert_not_called()

    def test_without_request_biz_not_filtered(self, assert_pub, plugin_objects, origin_objects, *_):
        plugin_objects.filter.return_value = []

        CollectorPluginViewSet().delete(SimpleNamespace(data={"plugin_ids": ["p1"]}, biz_id=None))

        plugin_objects.filter.assert_called_once_with(plugin_id__in=["p1"])
        origin_objects.filter.assert_called_once_with(plugin_id="p1")

    def test_global_plugin_requires_public_permission(self, assert_pub, plugin_objects, origin_objects, *_):
        plugin_objects.filter.return_value = [_plugin(0)]
        assert_pub.side_effect = Denied

        with self.assertRaises(Denied):
            CollectorPluginViewSet().delete(SimpleNamespace(data={"plugin_ids": ["p1"]}, biz_id=2))
        origin_objects.filter.assert_not_called()


@mock.patch(f"{MODULE}.CollectConfigMeta.objects")
@mock.patch(f"{MODULE}.assert_manage_pub_plugin_permission")
class TestCheckBizChange(TestCase):
    def test_switch_between_biz_rejected(self, assert_pub, collect_objects):
        with self.assertRaises(BizChangedError):
            CollectorPluginViewSet.check_biz_change(_plugin(2), {"bk_biz_id": 3})
        assert_pub.assert_not_called()

    def test_same_biz_skips_public_permission(self, assert_pub, collect_objects):
        CollectorPluginViewSet.check_biz_change(_plugin(2), {"bk_biz_id": "2"})
        assert_pub.assert_not_called()

    def test_biz_to_global_requires_public_permission(self, assert_pub, collect_objects):
        CollectorPluginViewSet.check_biz_change(_plugin(2), {})
        assert_pub.assert_called_once_with()
        collect_objects.filter.assert_not_called()

    def test_global_to_biz_with_other_biz_collect_rejected(self, assert_pub, collect_objects):
        collect_objects.filter.return_value = [SimpleNamespace(bk_biz_id=3)]

        with self.assertRaises(RelatedItemsExist):
            CollectorPluginViewSet.check_biz_change(_plugin(0), {"bk_biz_id": 2})
        assert_pub.assert_called_once_with()
        collect_objects.filter.assert_called_once_with(plugin__plugin_id="p1")


@mock.patch(f"{MODULE}.PluginManagerFactory")
@mock.patch.object(CollectorPluginViewSet, "check_biz_change")
@mock.patch(f"{MODULE}.CollectorPluginMeta.objects")
class TestReplacePluginBizScope(TestCase):
    def test_plugin_outside_request_biz_not_found(self, plugin_objects, check_biz_change, manager_factory):
        plugin_objects.filter.return_value.first.return_value = None

        with self.assertRaises(PluginIDNotExist):
            CollectorPluginViewSet().replace_plugin(SimpleNamespace(data={"plugin_id": "p1"}, biz_id=2))

        plugin_objects.filter.assert_called_once_with(plugin_id="p1", bk_biz_id__in=[0, 2])
        check_biz_change.assert_not_called()
        manager_factory.get_manager.assert_not_called()

    def test_checks_biz_change_before_replace(self, plugin_objects, check_biz_change, manager_factory):
        instance = _plugin(0)
        plugin_objects.filter.return_value.first.return_value = instance
        check_biz_change.side_effect = Denied
        request = SimpleNamespace(data={"plugin_id": "p1", "bk_biz_id": 2}, biz_id=2)

        with self.assertRaises(Denied):
            CollectorPluginViewSet().replace_plugin(request)

        check_biz_change.assert_called_once_with(instance, request.data)
        manager_factory.get_manager.assert_not_called()

    def test_without_request_biz_not_filtered(self, plugin_objects, check_biz_change, manager_factory):
        plugin_objects.filter.return_value.first.return_value = None

        with self.assertRaises(PluginIDNotExist):
            CollectorPluginViewSet().replace_plugin(SimpleNamespace(data={"plugin_id": "p1"}, biz_id=None))
        plugin_objects.filter.assert_called_once_with(plugin_id="p1")
