"""日志接入接口的业务访问权限校验。"""

import json
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock, patch
from urllib.parse import urlencode

from django.test import TestCase, override_settings
from iam import Resource
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.iam import ActionEnum
from apps.iam.exceptions import PermissionDeniedError
from apps.iam.handlers.resources import ResourceEnum
from apps.log_databus.handlers.collector_handler.log import LogCollectorHandler
from apps.log_databus.models import CollectorConfig
from apps.log_databus.views.log_access_views import LogAccessViewSet

CURRENT_BIZ_ID = 2
RELATED_BIZ_ID = -1001
OTHER_BIZ_ID = 3


@override_settings(
    IGNORE_IAM_PERMISSION=False,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class LogAccessViewSetPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        CollectorConfig.objects.bulk_create(
            [
                CollectorConfig(
                    collector_config_id=collector_id,
                    collector_config_name=f"collector_{collector_id}",
                    collector_scenario_id="row",
                    category_id="os",
                    bk_biz_id=bk_biz_id,
                )
                # 90/92 属于当前空间，94 属于关联空间，91 属于其他业务，93 属于无关空间
                for collector_id, bk_biz_id in (
                    (90, CURRENT_BIZ_ID),
                    (91, OTHER_BIZ_ID),
                    (92, CURRENT_BIZ_ID),
                    (93, -7),
                    (94, RELATED_BIZ_ID),
                )
            ]
        )

    def build_request(self, method, params, action, headers=None, get_body=None):
        factory = APIRequestFactory()
        path = f"/api/v1/databus/log_access/{action.removeprefix('get_')}/"
        if method == "GET":
            if get_body is None:
                request = factory.get(path, params)
            else:
                request = factory.generic(
                    "GET", f"{path}?{urlencode(params)}", json.dumps(get_body), content_type="application/json"
                )
        else:
            request = factory.post(path, {"page": 1, "pagesize": 10, **params}, format="json")

        for key, value in (headers or {}).items():
            request.META[f"HTTP_{key.upper().replace('-', '_')}"] = value

        request.app = SimpleNamespace(bk_app_code="bk_monitorv3")
        force_authenticate(request, user=SimpleNamespace(username="test_user", is_active=True))
        return request

    def check_permission(self, allowed):
        client = Mock()
        client.batch_is_allowed.return_value = {}

        def is_allowed(action, resources=None, raise_exception=False):
            self.assertEqual([action], [ActionEnum.VIEW_BUSINESS])
            self.assertTrue(raise_exception)
            self.assertEqual(len(resources), 1)
            if not allowed:
                raise PermissionDeniedError(action_name=ActionEnum.VIEW_BUSINESS.name, permission={"actions": []})
            return True

        client.is_allowed.side_effect = is_allowed
        return client

    def call_view(self, method, params, allowed=True, action=None, headers=None, get_body=None):
        action = action or ("get_collector_field_enums" if method == "GET" else "collector")
        request = self.build_request(method, params, action, headers=headers, get_body=get_body)
        client = self.check_permission(allowed)

        with (
            patch.object(ResourceEnum.BUSINESS, "create_instance") as create_instance,
            patch("apps.iam.handlers.drf.Permission", return_value=client),
            patch("apps.log_databus.views.log_access_views.LogCollectorHandler") as handler,
        ):
            create_instance.side_effect = lambda bk_biz_id: Resource(
                ResourceEnum.BUSINESS.system_id, ResourceEnum.BUSINESS.id, str(bk_biz_id), {}
            )
            handler.return_value.get_log_collectors.return_value = {"total": 0, "list": []}
            handler.return_value.get_collector_field_enums.return_value = {"created_by": []}
            handler.get_collector_status.return_value = []

            response = LogAccessViewSet.as_view({method.lower(): action})(request)

        payload = response.data if hasattr(response, "data") else json.loads(response.content)
        return payload, client, create_instance, handler

    def test_collector_checks_request_space_instead_of_request_biz_id(self):
        payload, client, create_instance, handler = self.call_view(
            "POST", {"space_uid": "bkcc__2", "bk_biz_id": 1}, allowed=False
        )

        self.assertFalse(payload["result"])
        create_instance.assert_called_once_with(CURRENT_BIZ_ID)
        client.is_allowed.assert_called_once()
        handler.assert_not_called()

    def test_collector_allows_authorized_space(self):
        payload, _client, create_instance, handler = self.call_view("POST", {"space_uid": " bkcc__2 "})

        self.assertTrue(payload["result"])
        create_instance.assert_called_once_with(CURRENT_BIZ_ID)
        handler.assert_called_once_with("bkcc__2")
        handler.return_value.get_log_collectors.assert_called_once()

    def test_collector_field_enums_uses_query_space_instead_of_body(self):
        payload, _client, create_instance, handler = self.call_view(
            "GET", {"space_uid": "bkcc__2"}, get_body={"space_uid": "bkcc__1", "bk_biz_id": 1}
        )

        self.assertTrue(payload["result"])
        create_instance.assert_called_once_with(CURRENT_BIZ_ID)
        handler.assert_called_once_with("bkcc__2")

    def test_missing_or_invalid_space_is_rejected(self):
        cases = [
            ("POST", {}, "collector"),
            ("GET", {}, "get_collector_field_enums"),
            ("POST", {"space_uid": ""}, "collector"),
            ("GET", {"space_uid": "invalid"}, "get_collector_field_enums"),
            ("POST", {"space_uid": "bkcc__0"}, "collector"),
        ]
        for method, params, action in cases:
            with self.subTest(method=method, params=params):
                payload, client, create_instance, handler = self.call_view(method, params, action=action)

                self.assertFalse(payload["result"])
                create_instance.assert_not_called()
                client.is_allowed.assert_not_called()
                handler.assert_not_called()

    @patch("bkm_space.api.SpaceApi.get_space_detail", return_value=SimpleNamespace(id=7))
    def test_non_business_space_uses_negative_biz_id(self, _get_space_detail):
        payload, _client, create_instance, handler = self.call_view("POST", {"space_uid": "bcs__project"})

        self.assertTrue(payload["result"])
        create_instance.assert_called_once_with(-7)
        handler.assert_called_once_with("bcs__project")

    @override_settings(IGNORE_IAM_PERMISSION=True)
    def test_ignore_permission_setting_is_preserved(self):
        payload, client, _create_instance, handler = self.call_view("POST", {"space_uid": "bkcc__2"})

        self.assertTrue(payload["result"])
        client.is_allowed.assert_not_called()
        handler.assert_called_once_with("bkcc__2")

    def call_status_view(self, params, allowed=True, headers=None, related_bk_biz_ids=(CURRENT_BIZ_ID, RELATED_BIZ_ID)):
        request = self.build_request("POST", params, "get_collector_status", headers=headers)
        client = self.check_permission(allowed)

        with (
            patch.object(ResourceEnum.BUSINESS, "create_instance") as create_instance,
            patch("apps.iam.handlers.drf.Permission", return_value=client),
            patch.object(
                LogCollectorHandler,
                "all_related_bk_biz_ids",
                new_callable=PropertyMock,
                return_value=list(related_bk_biz_ids),
            ),
            patch.object(LogCollectorHandler, "get_collector_status", return_value=[]) as get_collector_status,
        ):
            create_instance.side_effect = lambda bk_biz_id: Resource(
                ResourceEnum.BUSINESS.system_id, ResourceEnum.BUSINESS.id, str(bk_biz_id), {}
            )

            response = LogAccessViewSet.as_view({"post": "get_collector_status"})(request)

        payload = response.data if hasattr(response, "data") else json.loads(response.content)
        return payload, client, create_instance, get_collector_status

    def test_collector_status_limits_scope_to_request_space(self):
        payload, client, create_instance, get_collector_status = self.call_status_view(
            {"collector_config_id_list": [90, 91, 92, 93, 94]}, headers={"X-Bk-Space-Uid": "bkcc__2"}
        )

        self.assertTrue(payload["result"])
        # 整个批次只按请求空间鉴权一次，不再逐业务校验
        create_instance.assert_called_once_with(CURRENT_BIZ_ID)
        client.is_allowed.assert_called_once()
        # 关联空间（-1001）的采集项保留，其他业务/无关空间的采集项被过滤
        self.assertEqual(sorted(get_collector_status.call_args.args[0]), [90, 92, 94])

    def test_collector_status_does_not_query_other_business(self):
        payload, _client, _create_instance, get_collector_status = self.call_status_view(
            {"collector_config_id_list": [91, 93]}, headers={"X-Bk-Space-Uid": "bkcc__2"}
        )

        self.assertTrue(payload["result"])
        self.assertEqual(get_collector_status.call_args.args[0], [])

    def test_collector_status_requires_space(self):
        payload, client, create_instance, get_collector_status = self.call_status_view(
            {"collector_config_id_list": [90]}
        )

        self.assertFalse(payload["result"])
        create_instance.assert_not_called()
        client.is_allowed.assert_not_called()
        get_collector_status.assert_not_called()

    def test_collector_status_denied_space_skips_query(self):
        payload, client, create_instance, get_collector_status = self.call_status_view(
            {"collector_config_id_list": [90]}, allowed=False, headers={"X-Bk-Space-Uid": "bkcc__2"}
        )

        self.assertFalse(payload["result"])
        create_instance.assert_called_once_with(CURRENT_BIZ_ID)
        client.is_allowed.assert_called_once()
        get_collector_status.assert_not_called()

    def test_collector_status_validates_ids_before_query(self):
        payload, _client, _create_instance, get_collector_status = self.call_status_view(
            {"collector_config_id_list": ["invalid"]}, headers={"X-Bk-Space-Uid": "bkcc__2"}
        )

        self.assertFalse(payload["result"])
        get_collector_status.assert_not_called()

    @override_settings(IGNORE_IAM_PERMISSION=True)
    def test_collector_status_preserves_ignore_permission_setting(self):
        payload, client, _create_instance, get_collector_status = self.call_status_view(
            {"collector_config_id_list": [90, 91]}, headers={"X-Bk-Space-Uid": "bkcc__2"}
        )

        self.assertTrue(payload["result"])
        client.is_allowed.assert_not_called()
        self.assertEqual(sorted(get_collector_status.call_args.args[0]), [90])
