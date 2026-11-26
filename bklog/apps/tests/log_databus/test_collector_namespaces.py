"""采集项 Data ID 授权与回填。"""

import json
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from apps.api.modules import bkdata_access
from apps.iam import ActionEnum, ResourceEnum
from apps.iam.exceptions import PermissionDeniedError
from apps.log_databus.exceptions import CollectorConfigDataIdNotExistException, CollectorConfigNotExistException
from apps.log_databus.handlers.collector import base
from apps.log_databus.serializers import CollectorNamespaceSerializer
from apps.log_search.models import SpaceApi

PATH = "/api/v1/databus/collectors/7/authorized_namespaces/"


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
class CollectorNamespaceTests(SimpleTestCase):
    def setUp(self):
        self.handler = base.CollectorHandler(
            data=SimpleNamespace(bk_biz_id=2, bk_data_id=123, storage_cluster_type="es")
        )
        self.tenant = self.enterContext(mock.patch.object(base.Space, "get_tenant_id", return_value="example"))
        self.enterContext(mock.patch.object(base, "get_request_tenant_id", return_value="example"))
        self.list_projects = self.enterContext(mock.patch.object(base.BkDataAccessApi, "list_namespaces"))
        self.list_projects.return_value = [
            {"metadata": {"name": "orders"}, "spec": {"alias": "订单", "bk_biz_id": 2}},
            {"metadata": {"name": "other"}, "spec": {"bk_biz_id": 2}},
            {"metadata": {"name": "foreign"}, "spec": {"bk_biz_id": 3}},
            {"metadata": {"name": "unbound"}, "spec": {"bk_biz_id": None}},
            {"metadata": {"name": "default_2"}, "spec": {}},
            {"metadata": {"name": "bklog"}, "spec": {"bk_biz_id": 2}},
            {"metadata": {"name": "bkmonitor"}, "spec": {"bk_biz_id": 2}},
        ]
        self.metadata = self.enterContext(mock.patch.object(base, "TransferApi"))

    def test_list_matches_registration_by_namespace_even_when_phase_is_empty(self):
        self.metadata.list_data_source_namespaces.return_value = [
            {"namespace": "orders", "name": "bkm_datasource_123", "status": ""},
        ]
        self.assertEqual(
            self.handler.list_authorized_namespaces(),
            [
                {"name": "orders", "alias": "订单", "bk_biz_id": 2, "is_authorized": True},
                {"name": "other", "alias": None, "bk_biz_id": 2, "is_authorized": False},
            ],
        )
        self.list_projects.assert_called_once_with({"tenant": "example"}, bk_tenant_id="example")
        self.metadata.list_data_source_namespaces.assert_called_once_with({"bk_data_id": 123}, bk_tenant_id="example")

    @override_settings(ENABLE_MULTI_TENANT_MODE=False)
    def test_single_tenant_uses_default_bkbase_tenant(self):
        self.list_projects.return_value = []
        self.metadata.list_data_source_namespaces.return_value = []
        self.assertEqual(self.handler.list_authorized_namespaces(), [])
        self.list_projects.assert_called_once_with({"tenant": "default"}, bk_tenant_id="example")

    def test_registration_lookup_failure_is_propagated(self):
        self.metadata.list_data_source_namespaces.side_effect = RuntimeError("metadata unavailable")
        with self.assertRaisesRegex(RuntimeError, "metadata unavailable"):
            self.handler.list_authorized_namespaces()

    def test_apply_uses_collector_data_id_and_returns_registration(self):
        self.metadata.apply_data_source.return_value = {
            "target_namespace": "orders",
            "bk_data_id": 123,
            "name": "bkm_datasource_123",
        }
        self.assertEqual(
            self.handler.authorize_namespace("orders"),
            {"name": "orders", "bk_data_id": 123, "data_source_name": "bkm_datasource_123", "is_authorized": True},
        )
        self.metadata.apply_data_source.assert_called_once_with(
            {"bk_data_id": 123, "target_namespace": "orders", "bk_biz_id": 2},
            bk_tenant_id="example",
            request_cookies=False,
        )
        self.list_projects.assert_called_once_with({"tenant": "example"}, bk_tenant_id="example")

    def test_post_rejects_names_outside_the_business_namespace_list(self):
        for name in ("foreign", "unbound", "default_2", "missing", "bklog", "bkmonitor"):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                self.handler.authorize_namespace(name)
        self.metadata.apply_data_source.assert_not_called()

    def test_post_rechecks_business_after_listing(self):
        self.assertIn("orders", [row["name"] for row in self.handler.list_authorized_namespaces()])
        self.list_projects.return_value[0]["spec"]["bk_biz_id"] = 3
        with self.assertRaises(ValidationError):
            self.handler.authorize_namespace("orders")
        self.metadata.apply_data_source.assert_not_called()

    def test_container_project_uses_its_related_cmdb_business(self):
        self.handler.data.bk_biz_id = -7
        container = SimpleNamespace(
            space_uid="bcs__orders",
            extend={
                "resources": [
                    {"resource_type": "bkcc", "resource_id": "2"},
                ]
            },
        )
        business = SimpleNamespace(bk_biz_id=2)

        def get_space(space_uid="", id=0):
            if id == 7:
                return container
            return {"bcs__orders": container, "bkcc__2": business}[space_uid]

        with mock.patch.object(SpaceApi, "get_space_detail", side_effect=get_space):
            self.assertEqual([row["name"] for row in self.handler.list_authorized_namespaces()], ["orders", "other"])
            self.handler.authorize_namespace("orders")
            self.metadata.apply_data_source.assert_called_once()
            self.metadata.apply_data_source.reset_mock()
            container.extend["resources"] = []
            self.assertEqual(self.handler.list_authorized_namespaces(), [])
            with self.assertRaises(ValidationError):
                self.handler.authorize_namespace("orders")
            self.metadata.apply_data_source.assert_not_called()

    def test_post_propagates_namespace_lookup_failure_before_writing(self):
        self.list_projects.side_effect = RuntimeError("bkbase unavailable")
        with self.assertRaisesRegex(RuntimeError, "bkbase unavailable"):
            self.handler.authorize_namespace("orders")
        self.metadata.apply_data_source.assert_not_called()

    def test_rejects_cross_tenant_or_missing_data_id_before_upstream_calls(self):
        for tenant, data_id, error in [
            ("other", 123, CollectorConfigNotExistException),
            ("example", None, CollectorConfigDataIdNotExistException),
        ]:
            self.tenant.return_value = tenant
            self.handler.data.bk_data_id = data_id
            with self.subTest(tenant=tenant), self.assertRaises(error):
                self.handler.list_authorized_namespaces()
            with self.subTest(tenant=tenant), self.assertRaises(error):
                self.handler.authorize_namespace("orders")
        self.list_projects.assert_not_called()
        self.assertEqual(self.metadata.mock_calls, [])

    def test_post_input_accepts_only_namespace_as_source_of_target(self):
        serializer = CollectorNamespaceSerializer(data={"name": "orders", "bk_data_id": 456})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(dict(serializer.validated_data), {"name": "orders"})
        for invalid in ["", "x" * 65]:
            self.assertFalse(CollectorNamespaceSerializer(data={"name": invalid}).is_valid())

    @override_settings(IGNORE_IAM_PERMISSION=False)
    def test_manager_can_apply_and_read_back_authorization(self):
        match = resolve(PATH)
        factory = APIRequestFactory()
        self.metadata.apply_data_source.return_value = {
            "target_namespace": "orders",
            "bk_data_id": 123,
            "name": "bkm_datasource_123",
        }
        self.list_projects.return_value = [{"metadata": {"name": "orders"}, "spec": {"bk_biz_id": 2}}]
        self.metadata.list_data_source_namespaces.return_value = [{"namespace": "orders"}]
        with (
            mock.patch.object(ResourceEnum.COLLECTION, "create_instance"),
            mock.patch("apps.iam.handlers.drf.Permission.is_allowed", return_value=True),
            mock.patch.object(base.CollectorConfig.objects, "get", return_value=self.handler.data),
        ):
            rejected = match.func(
                factory.post(PATH, {"name": "foreign", "bk_biz_id": 2}, format="json"), **match.kwargs
            )
            self.assertFalse(json.loads(rejected.content)["result"])
            self.metadata.apply_data_source.assert_not_called()
            applied = match.func(
                factory.post(PATH, {"name": "orders", "bk_data_id": 456}, format="json"), **match.kwargs
            )
            listed = match.func(factory.get(PATH), **match.kwargs)
        self.assertTrue(applied.data["result"])
        self.assertEqual(applied.data["data"]["bk_data_id"], 123)
        self.assertEqual(
            listed.data["data"], [{"name": "orders", "alias": None, "bk_biz_id": 2, "is_authorized": True}]
        )
        self.metadata.apply_data_source.assert_called_once_with(
            {"bk_data_id": 123, "target_namespace": "orders", "bk_biz_id": 2},
            bk_tenant_id="example",
            request_cookies=False,
        )

    @override_settings(IGNORE_IAM_PERMISSION=False)
    def test_route_checks_manage_permission_on_the_collector_before_access(self):
        match = resolve(PATH)
        factory = APIRequestFactory()
        with (
            mock.patch.object(ResourceEnum.COLLECTION, "create_instance") as instance,
            mock.patch(
                "apps.iam.handlers.drf.Permission.is_allowed", side_effect=PermissionDeniedError("管理采集项", {})
            ) as check,
            mock.patch("apps.log_databus.views.collector_views.CollectorHandler") as handler,
        ):
            for request in (factory.get(PATH), factory.post(PATH, {"name": "orders"})):
                with self.subTest(method=request.method):
                    response = match.func(request, **match.kwargs)
                    payload = json.loads(response.content)
                    self.assertFalse(payload["result"])
                    self.assertEqual(str(payload["code"]), "9900403")
                instance.assert_called_with("7")
                check.assert_called_with(
                    action=ActionEnum.MANAGE_COLLECTION,
                    resources=[instance.return_value],
                    raise_exception=True,
                )
            handler.assert_not_called()


class NamespaceListGatewayTests(SimpleTestCase):
    @override_settings(PAAS_API_HOST="https://gateway.example.test", ENVIRONMENT="prod", ENABLE_MULTI_TENANT_MODE=True)
    def test_gateway_and_legacy_routes(self):
        gateway = "https://gateway.example.test/api/bk-base/prod"
        legacy = "https://legacy.example.test/v3/access/"
        with mock.patch.object(bkdata_access, "ACCESS_APIGATEWAY_ROOT", legacy):
            for use_apigw in (True, False):
                with self.subTest(use_apigw=use_apigw), self.settings(USE_APIGW=use_apigw):
                    api = bkdata_access._BkDataAccessApi()
                    self.assertEqual(
                        api.list_raw_data.url, f"{gateway}/v3/access/rawdata/" if use_apigw else f"{legacy}rawdata/"
                    )
                    self.assertEqual(
                        api.list_namespaces.build_actual_url({"tenant": "default"}),
                        f"{gateway}/v4/tenants/default/namespaces",
                    )
                    self.assertEqual(
                        api.get_datalink_resource.url,
                        f"{gateway}/v4/tenants/{{tenant}}/namespaces/{{namespace}}/{{kind}}/{{name}}/",
                    )

    @override_settings(PAAS_API_HOST="http://gateway.example.test", ENVIRONMENT="stage", OAUTH_COOKIES_PARAMS={})
    def test_login_ticket_only_sent_in_header(self):
        api = bkdata_access._BkDataAccessApi().list_namespaces
        with (
            mock.patch.object(
                bkdata_access, "get_request", return_value=SimpleNamespace(COOKIES={"bk_ticket": "sample"})
            ),
            mock.patch("apps.api.base.requests.session") as session_factory,
        ):
            session = session_factory.return_value
            session.headers = {}
            api._send({"tenant": "example"}, 5, "req", True, "example")
        self.assertEqual(json.loads(session.headers["X-Bkapi-Authorization"]), {"bk_ticket": "sample"})
        session.request.assert_called_once_with(
            method="GET",
            url="http://gateway.example.test/api/bk-base/stage/v4/tenants/example/namespaces",
            params={},
            verify=True,
            timeout=5,
        )
