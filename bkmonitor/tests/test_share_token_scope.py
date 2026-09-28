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

from rest_framework.exceptions import ValidationError

from bkmonitor.iam import ActionEnum
from bkmonitor.models.token import ApiAuthToken
from monitor_web.commons.token import views as token_views
from monitor_web.search.handlers.base import SearchScope
from monitor_web.search.handlers.host import HostSearchHandler
from monitor_web.share.resources import check_share_permission, get_token_type


def _view(cls_name, actions=None, module="monitor_web.scene_view.views"):
    return SimpleNamespace(cls=type(cls_name, (), {"__module__": module}), actions=actions or {})


class TestSceneTokenViewScope(TestCase):
    """观测场景令牌的视图适用范围"""

    def test_read_action_is_allowed(self):
        token = ApiAuthToken(type="host")
        self.assertTrue(token.is_allowed_view(_view("SceneViewViewSet", {"get": "get_scene_view"})))

    def test_scene_view_write_actions_are_not_allowed(self):
        token = ApiAuthToken(type="host")
        for action in ("update_scene_view", "delete_scene_view"):
            self.assertFalse(token.is_allowed_view(_view("SceneViewViewSet", {"post": action})))

    def test_share_management_is_not_allowed(self):
        token = ApiAuthToken(type="kubernetes")
        self.assertFalse(token.is_allowed_view(_view("ShareViewSet", {"post": "create_share_token"})))

    def test_host_list_views_are_not_allowed(self):
        token = ApiAuthToken(type="host")
        for name in ("SearchHostInfoViewSet", "SearchHostMetricViewSet"):
            self.assertFalse(token.is_allowed_view(_view(name, {"post": "list"})))

    def test_type_matched_exactly(self):
        # 类型按精确值区分，大小写变体按场景令牌处理
        token = ApiAuthToken(type="Grafana")
        self.assertFalse(token.is_allowed_view(_view("ShareViewSet")))

    def test_grafana_token_scope_unchanged(self):
        token = ApiAuthToken(type="grafana")
        self.assertTrue(token.is_allowed_view(_view("DashboardViewSet", module="monitor_web.grafana.views")))
        self.assertFalse(token.is_allowed_view(_view("SceneViewViewSet", {"get": "get_scene"})))


class TestShareTokenType(TestCase):
    """分享类型解析"""

    def test_scene_types_are_resolved(self):
        self.assertEqual(get_token_type("host"), "host")
        self.assertEqual(get_token_type("scene_plugin_abc"), "scene_collect")
        self.assertEqual(get_token_type("apm_app"), "apm")

    def test_unregistered_types_are_rejected(self):
        for token_type in ("grafana", "as_code", "Grafana", "unknown"):
            with self.assertRaises(ValidationError):
                get_token_type(token_type)

    @mock.patch("monitor_web.share.resources.Permission")
    def test_share_requires_scene_view_action(self, perm_cls):
        check_share_permission(2, "host")
        perm_cls.return_value.is_allowed_by_biz.assert_called_once_with(
            bk_biz_id=2, action=ActionEnum.VIEW_HOST, raise_exception=True
        )

    @mock.patch("monitor_web.share.resources.Permission")
    def test_instance_level_action_is_not_checked_by_business(self, perm_cls):
        # APM 应用查看按应用实例授权，不以业务资源校验
        check_share_permission(2, "apm")
        perm_cls.return_value.is_allowed_by_biz.assert_not_called()


class TestApiTokenPermission(TestCase):
    """长期 API 令牌的获取权限"""

    def _permissions(self, query_params):
        view = token_views.TokenManagerViewSet()
        view.request = SimpleNamespace(query_params=query_params)
        return view.get_permissions()

    def test_grafana_token_keeps_dashboard_editor_path(self):
        permissions = self._permissions({"type": "grafana"})
        self.assertIsInstance(permissions[0], token_views.GrafanaWritePermission)
        self.assertEqual(permissions[0].permission.actions, [ActionEnum.MANAGE_RULE])

    def test_as_code_token_requires_manage_rule(self):
        for query_params in ({"type": "as_code"}, {}):
            permissions = self._permissions(query_params)
            self.assertIsInstance(permissions[0], token_views.BusinessActionPermission)
            self.assertEqual(permissions[0].actions, [ActionEnum.MANAGE_RULE])


class TestHostSearchShareLink(TestCase):
    """全局搜索仅为具备主机查看权限的业务生成分享链接"""

    @mock.patch.object(HostSearchHandler, "collect_results_by_biz", side_effect=lambda results, **kwargs: results)
    @mock.patch.object(HostSearchHandler, "get_enabled_token", return_value="token-xxx")
    @mock.patch("monitor_web.search.handlers.host.Permission")
    @mock.patch("monitor_web.search.handlers.host.api.cmdb.get_host_without_biz")
    def test_token_only_for_permitted_biz(self, get_hosts, perm_cls, get_enabled_token, _collect):
        own = SimpleNamespace(bk_biz_id=2, bk_cloud_id=0, ip="127.0.0.1", bk_host_id=1)
        other = SimpleNamespace(bk_biz_id=3, bk_cloud_id=0, ip="127.0.0.2", bk_host_id=2)
        get_hosts.return_value = {"hosts": [own, other]}
        perm_cls.return_value.filter_biz_ids_by_action.return_value = [2]

        results = HostSearchHandler(scope=SearchScope.GLOBAL, username="tester").search("127.0.0")

        get_enabled_token.assert_called_once_with(own)
        share_urls = {item.bk_biz_id: item.temp_share_url for item in results}
        self.assertIsNotNone(share_urls[2])
        self.assertIsNone(share_urls[3])

    @mock.patch.object(HostSearchHandler, "collect_results_by_biz", side_effect=lambda results, **kwargs: results)
    @mock.patch("monitor_web.search.handlers.host.Permission")
    @mock.patch("monitor_web.search.handlers.host.api.cmdb.get_host_without_biz", return_value={"hosts": []})
    def test_no_hosts_does_not_query_all_biz(self, _get_hosts, perm_cls, _collect):
        HostSearchHandler(scope=SearchScope.GLOBAL, username="tester").search("127.0.0")
        perm_cls.return_value.filter_biz_ids_by_action.assert_not_called()
