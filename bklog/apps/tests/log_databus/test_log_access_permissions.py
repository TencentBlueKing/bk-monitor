"""日志接入列表接口的业务访问权限校验。"""

import json
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlencode

from django.test import TestCase, override_settings
from iam import Resource
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.iam import ActionEnum
from apps.iam.exceptions import PermissionDeniedError
from apps.iam.handlers.resources import ResourceEnum
from apps.log_databus.models import CollectorConfig
from apps.log_databus.views.log_access_views import LogAccessViewSet
from bkm_space.middleware import ParamInjectMiddleware


@override_settings(
    IGNORE_IAM_PERMISSION=False,
    ESQUERY_WHITE_LIST=["bk_monitorv3"],
    BKM_SPACE_INJECT_REQUEST_ENABLED=True,
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
                for collector_id, bk_biz_id in ((90, 2), (91, 3), (92, 2), (93, -7))
            ]
        )

    def call_view(self, method, params, allowed=False, action=None, get_body=None, allowed_biz_ids=()):
        factory = APIRequestFactory()
        action = action or ("get_collector_field_enums" if method == "GET" else "collector")
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
        request.app = SimpleNamespace(bk_app_code="bk_monitorv3")
        force_authenticate(request, user=SimpleNamespace(username="test_user", is_active=True))
        ParamInjectMiddleware(lambda request: None).process_request(request)

        with (
            patch.object(ResourceEnum.BUSINESS, "create_instance") as create_instance,
            patch("apps.iam.handlers.drf.Permission") as permission_class,
            patch("apps.log_databus.views.log_access_views.LogCollectorHandler") as handler,
        ):
            create_instance.side_effect = lambda bk_biz_id: Resource(
                ResourceEnum.BUSINESS.system_id, ResourceEnum.BUSINESS.id, str(bk_biz_id), {}
            )
            client = permission_class.return_value

            def check_permission(*, action, resources, raise_exception):
                self.assertEqual(action, ActionEnum.VIEW_BUSINESS)
                self.assertTrue(raise_exception)
                self.assertEqual(len(resources), 1)
                if allowed or int(resources[0].id) in allowed_biz_ids:
                    return True
                raise PermissionDeniedError(action_name=ActionEnum.VIEW_BUSINESS.name, permission={"actions": []})

            client.is_allowed.side_effect = check_permission
            handler.return_value.get_log_collectors.return_value = {"total": 0, "list": []}
            handler.return_value.get_collector_field_enums.return_value = {"created_by": []}
            handler.get_collector_status.return_value = []

            response = LogAccessViewSet.as_view({method.lower(): action})(request)
            payload = response.data if hasattr(response, "data") else json.loads(response.content)

        return payload, client, create_instance, handler

    def test_denied_space_cannot_be_bypassed_by_request_biz_id(self):
        for method in ("GET", "POST"):
            extras = [{}, {"bk_biz_id": 0}, {"bk_biz_id": ""}, {"bk_biz_id": 1}]
            if method == "POST":
                extras.append({"bk_biz_id": None})
            for extra in extras:
                with self.subTest(method=method, extra=extra):
                    payload, client, create_instance, handler = self.call_view(
                        method, {"space_uid": "bkcc__2", **extra}
                    )

                    self.assertFalse(payload["result"])
                    create_instance.assert_called_once_with(2)
                    client.is_allowed.assert_called_once()
                    self.assertEqual(client.is_allowed.call_args.kwargs["resources"][0].id, "2")
                    handler.assert_not_called()

    def test_authorized_space_can_be_queried(self):
        for method in ("GET", "POST"):
            with self.subTest(method=method):
                payload, client, create_instance, handler = self.call_view(
                    method, {"space_uid": " bkcc__2 ", "bk_biz_id": 1}, allowed=True
                )

                self.assertTrue(payload["result"])
                create_instance.assert_called_once_with(2)
                client.is_allowed.assert_called_once()
                handler.assert_called_once_with("bkcc__2")

    def test_get_permission_uses_query_space_instead_of_body(self):
        payload, client, create_instance, handler = self.call_view(
            "GET", {"space_uid": "bkcc__2"}, get_body={"space_uid": "bkcc__1", "bk_biz_id": 1}
        )

        self.assertFalse(payload["result"])
        create_instance.assert_called_once_with(2)
        client.is_allowed.assert_called_once()
        handler.assert_not_called()

    def test_invalid_space_is_rejected_before_permission_or_query(self):
        for method in ("GET", "POST"):
            for params in ({}, {"space_uid": ""}, {"space_uid": "invalid"}, {"space_uid": "bkcc__0"}):
                with self.subTest(method=method, params=params):
                    payload, client, create_instance, handler = self.call_view(method, params)

                    self.assertFalse(payload["result"])
                    create_instance.assert_not_called()
                    client.is_allowed.assert_not_called()
                    handler.assert_not_called()

    @patch("bkm_space.api.SpaceApi.get_space_detail", return_value=SimpleNamespace(id=7))
    def test_non_business_space_uses_negative_id(self, _get_space_detail):
        payload, client, create_instance, handler = self.call_view(
            "POST", {"space_uid": "bcs__project", "bk_biz_id": 1}, allowed=True
        )

        self.assertTrue(payload["result"])
        create_instance.assert_called_once_with(-7)
        client.is_allowed.assert_called_once()
        handler.assert_called_once_with("bcs__project")

    @override_settings(IGNORE_IAM_PERMISSION=True)
    def test_ignore_permission_setting_is_preserved(self):
        payload, client, _create_instance, handler = self.call_view("POST", {"space_uid": "bkcc__2"})

        self.assertTrue(payload["result"])
        client.is_allowed.assert_not_called()
        handler.assert_called_once_with("bkcc__2")

    def test_collector_status_without_space_checks_actual_business(self):
        payload, client, create_instance, handler = self.call_view(
            "POST", {"collector_config_id_list": [90]}, action="get_collector_status"
        )

        self.assertFalse(payload["result"])
        create_instance.assert_called_once_with(2)
        client.is_allowed.assert_called_once()
        handler.get_collector_status.assert_not_called()

    def test_collector_status_rejects_batch_containing_denied_business(self):
        payload, client, create_instance, handler = self.call_view(
            "POST",
            {"collector_config_id_list": [90, 91]},
            action="get_collector_status",
            allowed_biz_ids={2},
        )

        self.assertFalse(payload["result"])
        self.assertEqual([call.args[0] for call in create_instance.call_args_list], [2, 3])
        self.assertEqual([call.kwargs["resources"][0].id for call in client.is_allowed.call_args_list], ["2", "3"])
        handler.get_collector_status.assert_not_called()

    def test_collector_status_checks_each_business_once_before_query(self):
        payload, client, create_instance, handler = self.call_view(
            "POST",
            {"collector_config_id_list": [90, 91, 92]},
            action="get_collector_status",
            allowed=True,
        )

        self.assertTrue(payload["result"])
        self.assertEqual([call.args[0] for call in create_instance.call_args_list], [2, 3])
        self.assertEqual([call.kwargs["resources"][0].id for call in client.is_allowed.call_args_list], ["2", "3"])
        handler.get_collector_status.assert_called_once_with([90, 91, 92])

    def test_collector_status_does_not_trust_request_business(self):
        payload, client, create_instance, handler = self.call_view(
            "POST",
            {"collector_config_id_list": [90], "space_uid": "bkcc__1", "bk_biz_id": 1},
            action="get_collector_status",
            allowed_biz_ids={1},
        )

        self.assertFalse(payload["result"])
        create_instance.assert_called_once_with(2)
        client.is_allowed.assert_called_once()
        handler.get_collector_status.assert_not_called()

    def test_collector_status_supports_non_business_space(self):
        payload, client, create_instance, handler = self.call_view(
            "POST", {"collector_config_id_list": [93]}, action="get_collector_status", allowed=True
        )

        self.assertTrue(payload["result"])
        create_instance.assert_called_once_with(-7)
        client.is_allowed.assert_called_once()
        handler.get_collector_status.assert_called_once_with([93])

    @override_settings(IGNORE_IAM_PERMISSION=True)
    def test_collector_status_preserves_ignore_permission_setting(self):
        payload, client, _create_instance, handler = self.call_view(
            "POST", {"collector_config_id_list": [90, 91]}, action="get_collector_status"
        )

        self.assertTrue(payload["result"])
        client.is_allowed.assert_not_called()
        handler.get_collector_status.assert_called_once_with([90, 91])

    def test_collector_status_validates_ids_before_permission_or_query(self):
        payload, client, create_instance, handler = self.call_view(
            "POST", {"collector_config_id_list": ["invalid"]}, action="get_collector_status"
        )

        self.assertFalse(payload["result"])
        create_instance.assert_not_called()
        client.is_allowed.assert_not_called()
        handler.get_collector_status.assert_not_called()
