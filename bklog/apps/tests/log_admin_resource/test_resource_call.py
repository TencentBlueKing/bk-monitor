"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings
from django.utils.deprecation import MiddlewareMixin

from apps.api import TransferApi
from apps.log_admin_resource.permissions import AdminResourceAppWhiteListPermission
from apps.log_admin_resource.registry import FUNCTIONS, HANDLERS, AdminResourceRegistry, _object_schema
from apps.log_admin_resource.schema import validate_params
from apps.log_admin_resource.views import AdminResourceViewSet
from apps.log_databus.constants import STORAGE_CLUSTER_TYPE, ContainerCollectorType
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_databus.models import (
    BKDataClean,
    CollectorConfig,
    CollectorPlugin,
    ContainerCollectorConfig,
    DataLinkConfig,
)
from apps.log_search.constants import IndexSetDataType
from apps.log_search.models import LogIndexSet, LogIndexSetData, Scenario
from apps.utils.local import _local, activate_request
from bkm_space.middleware import ParamInjectMiddleware


APIGW_MIDDLEWARE = "apps.tests.log_admin_resource.test_resource_call.AdminApiGatewayMiddleware"
NON_WHITE_LIST_APIGW_MIDDLEWARE = (
    "apps.tests.log_admin_resource.test_resource_call.NonWhiteListAdminApiGatewayMiddleware"
)
READ_ONLY_APIGW_MIDDLEWARE = "apps.tests.log_admin_resource.test_resource_call.ReadOnlyAdminApiGatewayMiddleware"
WRITE_ONLY_APIGW_MIDDLEWARE = "apps.tests.log_admin_resource.test_resource_call.WriteOnlyAdminApiGatewayMiddleware"
NON_SUPERUSER_MIDDLEWARE = "apps.tests.log_admin_resource.test_resource_call.NonSuperuserMiddleware"
SPACE_INJECT_MIDDLEWARE = "bkm_space.middleware.ParamInjectMiddleware"
REQUEST_LOCAL_APIGW_MIDDLEWARE = (
    "apps.tests.log_admin_resource.test_resource_call.RequestLocalAdminApiGatewayMiddleware"
)
METADATA_STORAGE = {
    "2_bklog.bcs_checkinsvr": {
        "cluster_config": {"cluster_id": 88, "cluster_name": "metadata-es"},
        "storage_config": {
            "retention": 30,
            "warm_phase_days": 0,
            "index_settings": {"number_of_shards": 9, "number_of_replicas": 2},
        },
    }
}
HOT_WARM_METADATA_STORAGE = {
    "2_bklog.bcs_checkinsvr": {
        "cluster_config": {"cluster_id": 88, "cluster_name": "metadata-hot-warm-es"},
        "storage_config": {
            "retention": 30,
            "warm_phase_days": 5,
            "index_settings": {"number_of_shards": 9, "number_of_replicas": 2},
        },
    }
}
NORMAL_CLUSTER_INFO = {
    "cluster_config": {
        "cluster_id": 25,
        "custom_option": {"hot_warm_config": {"is_enabled": False}},
    }
}
HOT_WARM_CLUSTER_INFO = {
    "cluster_config": {
        "cluster_id": 25,
        "custom_option": {"hot_warm_config": {"is_enabled": True}},
    }
}


class AdminApiGatewayMiddleware(MiddlewareMixin):
    bk_app_code = "bkmonitorv3"

    def process_request(self, request):
        class Base:
            pass

        request.user = Base()
        request.user.username = "admin"
        request.user.is_superuser = True
        request.user.is_authenticated = True
        request.user.is_active = True
        request.permission_exempt = True
        request.jwt = SimpleNamespace(gateway_name="bk-log-search", payload={})
        request.app = SimpleNamespace(
            bk_app_code=self.bk_app_code, verified=True, tenant_mode="global", tenant_id="system"
        )
        request.META.update({"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"})


class NonWhiteListAdminApiGatewayMiddleware(AdminApiGatewayMiddleware):
    bk_app_code = "not-white-list-app"


class ReadOnlyAdminApiGatewayMiddleware(AdminApiGatewayMiddleware):
    bk_app_code = "resource-read-app"


class WriteOnlyAdminApiGatewayMiddleware(AdminApiGatewayMiddleware):
    bk_app_code = "resource-write-app"


class RequestLocalAdminApiGatewayMiddleware(AdminApiGatewayMiddleware):
    def process_view(self, request, view, args, kwargs):
        activate_request(request)


class NonSuperuserMiddleware(MiddlewareMixin):
    def process_request(self, request):
        class Base:
            pass

        request.user = Base()
        request.user.username = "operator"
        request.user.is_superuser = False
        request.user.is_authenticated = True
        request.user.is_active = True
        request.META.update({"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"})


class ClearRequestLocalMixin:
    def tearDown(self):
        if hasattr(_local, "request"):
            delattr(_local, "request")
        super().tearDown()


class AdminResourceCallViewTest(ClearRequestLocalMixin, TestCase):
    def _call(self, func_name, params=None):
        response = self.client.post(
            "/api/v1/admin/resource/call/",
            data=json.dumps({"func_name": func_name, "params": params or {}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    def test_meta_list_returns_registered_functions(self):
        content = self._call("__meta__", {"action": "list"})

        self.assertTrue(content["result"])
        self.assertEqual(content["data"]["func_name"], "__meta__")
        self.assertEqual(content["data"]["protocol"], "bklog.admin_resource.v1")
        self.assertIn("bklog.collector.list", content["data"]["result"]["functions"])
        self.assertIn("bklog.collector.storage.snapshot", content["data"]["result"]["functions"])
        self.assertIn("bklog.collector.storage.preview", content["data"]["result"]["functions"])
        self.assertIn("bklog.collector.storage.apply", content["data"]["result"]["functions"])
        self.assertIn("bklog.storage_cluster.list", content["data"]["result"]["functions"])
        self.assertIn("bklog.platform_source.query", content["data"]["result"]["functions"])
        self.assertIn("bklog.index_set.route_snapshot", content["data"]["result"]["functions"])
        self.assertIn("bklog.model.query", content["data"]["result"]["functions"])

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    def test_meta_detail_returns_storage_snapshot_schema(self):
        content = self._call(
            "__meta__",
            {"action": "detail", "target_func_name": "bklog.collector.storage.snapshot"},
        )

        self.assertTrue(content["result"])
        function = content["data"]["result"]
        self.assertEqual(function["safety_level"], "read")
        self.assertEqual(function["params_schema"]["properties"]["collector_config_ids"]["maxItems"], 30)

    def test_viewset_uses_drf_permission_for_entry_auth(self):
        permission_class_names = {
            permission_class.__name__ for permission_class in AdminResourceViewSet.permission_classes
        }

        self.assertIn("AdminResourceAppWhiteListPermission", permission_class_names)

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    def test_unknown_func_name_returns_stable_error(self):
        content = self._call("bklog.unknown.list")

        self.assertFalse(content["result"])
        self.assertIn("unknown func_name", content["message"])

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    def test_success_and_error_return_request_id_header_without_changing_body_protocol(self):
        success = self.client.post(
            "/api/v1/admin/resource/call/",
            data=json.dumps({"func_name": "__meta__", "params": {"action": "list"}}),
            content_type="application/json",
        )
        failure = self.client.post(
            "/api/v1/admin/resource/call/",
            data=json.dumps({"func_name": "bklog.unknown.list", "params": {}}),
            content_type="application/json",
        )

        self.assertTrue(success.headers["X-Request-Id"])
        self.assertTrue(failure.headers["X-Request-Id"])
        self.assertNotIn("request_id", json.loads(success.content)["data"])
        self.assertNotIn("request_id", json.loads(failure.content))

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    def test_platform_source_error_reuses_outer_resource_error_envelope(self):
        content = self._call(
            "bklog.platform_source.query",
            {"mode": "discover", "domain": "job"},
        )

        self.assertFalse(content["result"])
        self.assertEqual(content["code"], "DOMAIN_NOT_FOUND")
        self.assertIn("unknown domain", content["message"])
        self.assertEqual(content["data"]["next_call"], {"mode": "discover"})

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE, SPACE_INJECT_MIDDLEWARE))
    def test_resource_call_params_are_not_mutated_by_global_space_injection(self):
        func_name = "bklog.test.strict.biz"
        function = {
            "func_name": func_name,
            "description": "strict business parameter test function",
            "safety_level": "read",
            "validate_params": True,
            "params_schema": {
                "type": "object",
                "properties": {"bk_biz_id": {"type": "integer"}},
                "required": ["bk_biz_id"],
                "additionalProperties": False,
            },
        }
        received = []

        with (
            patch.dict(FUNCTIONS, {func_name: function}),
            patch.dict(HANDLERS, {func_name: lambda params: received.append(params) or params}),
        ):
            content = self._call(func_name, {"bk_biz_id": 2})

        self.assertTrue(content["result"])
        self.assertEqual(received, [{"bk_biz_id": 2}])
        self.assertEqual(content["data"]["result"], {"bk_biz_id": 2})

    def test_space_injection_remains_enabled_for_other_paths(self):
        request = RequestFactory().post(
            "/api/v1/another/",
            data=json.dumps({"params": {"bk_biz_id": 2}}),
            content_type="application/json",
        )

        ParamInjectMiddleware(lambda _request: None).process_request(request)

        self.assertEqual(json.loads(request.body)["params"]["space_uid"], "bkcc__2")

    @override_settings(
        MIDDLEWARE=(REQUEST_LOCAL_APIGW_MIDDLEWARE,),
        BK_APP_TENANT_ID="tenant-a",
    )
    def test_verified_app_identity_reaches_host_and_k8s_inspection_handlers(self):
        from apps.log_admin_resource.handlers.host_inspection import _request_identity as host_request_identity
        from apps.log_admin_resource.handlers.k8s_inspection import _request_identity as k8s_request_identity

        func_name = "bklog.test.inspection.identity"
        function = {
            "func_name": func_name,
            "description": "inspection identity propagation test function",
            "safety_level": "inspect",
        }

        with (
            patch.dict(FUNCTIONS, {func_name: function}),
            patch.dict(
                HANDLERS,
                {
                    func_name: lambda _params: {
                        "host": host_request_identity(),
                        "k8s": k8s_request_identity(),
                    }
                },
            ),
        ):
            content = self._call(func_name)

        self.assertTrue(content["result"])
        self.assertEqual(content["data"]["result"]["host"], ["bkmonitorv3", "tenant-a"])
        self.assertEqual(content["data"]["result"]["k8s"], ["bkmonitorv3", "tenant-a"])

    @override_settings(MIDDLEWARE=(NON_SUPERUSER_MIDDLEWARE,))
    def test_call_rejects_non_apigw_request(self):
        content = self._call("__meta__", {"action": "list"})

        self.assertFalse(content["result"])
        self.assertEqual(content["code"], "3600403")
        self.assertIn("APIGW", content["message"])

    @override_settings(
        MIDDLEWARE=(NON_WHITE_LIST_APIGW_MIDDLEWARE,),
        RESOURCE_CALL_APP_CODE_WHITE_LIST=["bkmonitorv3"],
    )
    def test_non_management_app_with_api_permission_gets_readonly_capabilities(self):
        content = self._call("__meta__", {"action": "list"})

        self.assertTrue(content["result"])
        functions = content["data"]["result"]["functions"]
        self.assertIn("bklog.collector.list", functions)
        self.assertNotIn("bklog.collector.storage.apply", functions)

    @override_settings(
        MIDDLEWARE=(READ_ONLY_APIGW_MIDDLEWARE,),
        RESOURCE_CALL_APP_CODE_WHITE_LIST=[],
    )
    def test_non_management_app_meta_hides_write_and_destructive_functions(self):
        content = self._call("__meta__", {"action": "list"})

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        self.assertEqual(result["protocol"], "bklog.admin_resource.v1")
        self.assertIn("bklog.collector.list", result["functions"])
        self.assertNotIn("bklog.collector.storage.apply", result["functions"])
        self.assertNotIn("bklog.clustering_config.pipeline.skip", result["functions"])
        self.assertTrue(result["capabilities"])
        self.assertTrue(all(item["safety_level"] in {"read", "inspect"} for item in result["capabilities"]))
        self.assertTrue(all("params_schema" not in item for item in result["capabilities"]))

    @override_settings(
        MIDDLEWARE=(READ_ONLY_APIGW_MIDDLEWARE,),
        RESOURCE_CALL_APP_CODE_WHITE_LIST=[],
    )
    def test_non_management_app_cannot_describe_or_invoke_write_function(self):
        detail = self._call(
            "__meta__",
            {"action": "detail", "target_func_name": "bklog.collector.storage.apply"},
        )
        invoke = self._call("bklog.collector.storage.apply", {"collector_config_ids": [1], "target": {}})

        self.assertFalse(detail["result"])
        self.assertIn("unknown target_func_name", detail["message"])
        self.assertFalse(invoke["result"])
        self.assertEqual(invoke["code"], "3600403")
        self.assertIn("management allowlist", invoke["message"])

    @override_settings(
        MIDDLEWARE=(APIGW_MIDDLEWARE,),
        RESOURCE_CALL_APP_CODE_WHITE_LIST=["bkmonitorv3"],
    )
    def test_management_allowlist_meta_keeps_existing_write_functions(self):
        content = self._call("__meta__", {"action": "list"})

        self.assertTrue(content["result"])
        functions = content["data"]["result"]["functions"]
        self.assertIn("bklog.collector.storage.apply", functions)
        self.assertIn("bklog.clustering_config.pipeline.skip", functions)

    @override_settings(
        MIDDLEWARE=(WRITE_ONLY_APIGW_MIDDLEWARE,),
        RESOURCE_CALL_APP_CODE_WHITE_LIST=["resource-write-app"],
    )
    def test_management_allowlist_includes_read_and_write_capabilities(self):
        content = self._call("__meta__", {"action": "list"})

        self.assertTrue(content["result"])
        functions = content["data"]["result"]["functions"]
        self.assertIn("bklog.collector.list", functions)
        self.assertIn("bklog.collector.storage.apply", functions)


class AdminResourceRegistryContractTest(TestCase):
    def test_object_schema_without_required_fields_remains_open_by_default(self):
        self.assertEqual(
            _object_schema(),
            {"type": "object", "properties": {}, "additionalProperties": True},
        )

    @patch("apps.log_admin_resource.permissions.Permission.get_auth_info", return_value={})
    def test_permission_rejects_apigw_request_without_trusted_app_identity(self, mock_get_auth_info):
        request = SimpleNamespace(jwt=SimpleNamespace(gateway_name="bk-log-search"))

        with self.assertRaisesRegex(Exception, "trusted APIGW app identity"):
            AdminResourceAppWhiteListPermission().has_permission(request, None)

        mock_get_auth_info.assert_called_once_with(request, raise_exception=False)

    @patch(
        "apps.log_admin_resource.permissions.Permission.get_auth_info",
        return_value={"bk_app_code": "resource-read-app"},
    )
    def test_permission_accepts_authorized_app_from_any_verified_apigw(self, mock_get_auth_info):
        raw_request = SimpleNamespace()
        request = SimpleNamespace(
            jwt=SimpleNamespace(gateway_name="another-verified-gateway"),
            _request=raw_request,
        )

        self.assertTrue(AdminResourceAppWhiteListPermission().has_permission(request, None))
        self.assertEqual(request.resource_app_code, "resource-read-app")
        self.assertEqual(raw_request.resource_app_code, "resource-read-app")
        mock_get_auth_info.assert_called_once_with(request, raise_exception=False)

    @override_settings(
        RESOURCE_CALL_APP_CODE_WHITE_LIST=["reader"],
    )
    def test_registry_rejects_missing_app_identity_without_view_layer(self):
        with self.assertRaisesRegex(Exception, "trusted APIGW app identity"):
            AdminResourceRegistry.call("__meta__", {"action": "list"})

    @override_settings(
        RESOURCE_CALL_APP_CODE_WHITE_LIST=[],
    )
    def test_registry_rejects_unknown_meta_action(self):
        with self.assertRaisesRegex(Exception, "unknown meta action"):
            AdminResourceRegistry.call("__meta__", {"action": "unknown"}, app_code="reader")

    @override_settings(
        RESOURCE_CALL_APP_CODE_WHITE_LIST=["writer"],
    )
    def test_registry_enforces_write_boundary_without_view_layer(self):
        with self.assertRaisesRegex(Exception, "management allowlist"):
            AdminResourceRegistry.call(
                "bklog.collector.storage.apply",
                {"collector_config_ids": [1], "target": {}},
                app_code="reader",
            )

    @override_settings(
        RESOURCE_CALL_APP_CODE_WHITE_LIST=[],
    )
    def test_opt_in_schema_validation_rejects_unknown_fields_before_handler(self):
        func_name = "bklog.test.strict"
        function = {
            "func_name": func_name,
            "description": "strict test function",
            "safety_level": "read",
            "validate_params": True,
            "params_schema": {
                "type": "object",
                "properties": {"id": {"type": "integer", "minimum": 1}},
                "required": ["id"],
                "additionalProperties": False,
            },
        }
        called = []

        with (
            patch.dict(FUNCTIONS, {func_name: function}),
            patch.dict(HANDLERS, {func_name: lambda params: called.append(params) or params}),
        ):
            with self.assertRaisesRegex(Exception, "unsupported fields"):
                AdminResourceRegistry.call(func_name, {"id": 1, "extra": True}, app_code="reader")

        self.assertEqual(called, [])

    @override_settings(
        RESOURCE_CALL_APP_CODE_WHITE_LIST=[],
    )
    def test_legacy_handler_schema_remains_non_strict_without_opt_in(self):
        func_name = "bklog.test.legacy"
        function = {
            "func_name": func_name,
            "description": "legacy test function",
            "safety_level": "read",
            "params_schema": {
                "type": "object",
                "properties": {"id": {"type": "integer"}},
                "additionalProperties": False,
            },
        }

        with patch.dict(FUNCTIONS, {func_name: function}), patch.dict(HANDLERS, {func_name: lambda params: params}):
            result = AdminResourceRegistry.call(func_name, {"legacy_extra": True}, app_code="reader")

        self.assertEqual(result, {"legacy_extra": True})


class TransferApiTenantGetterTest(TestCase):
    @patch("apps.log_search.models.Space.get_tenant_id", return_value="tenant-19078")
    def test_result_table_getter_uses_table_id_biz_id(self, mock_get_tenant_id):
        tenant_id = TransferApi.get_result_table.bk_tenant_id({"table_id": "19078_bklog.test_migrate_app"})

        self.assertEqual(tenant_id, "tenant-19078")
        mock_get_tenant_id.assert_called_once_with(bk_biz_id=19078)

    @patch("apps.log_search.models.Space.get_tenant_id", return_value="tenant-2")
    def test_result_table_storage_getter_uses_result_table_list_biz_id(self, mock_get_tenant_id):
        tenant_id = TransferApi.get_result_table_storage.bk_tenant_id(
            {"result_table_list": "2_bklog.bcs_checkinsvr,2_bklog.other", "storage_type": "elasticsearch"}
        )

        self.assertEqual(tenant_id, "tenant-2")
        mock_get_tenant_id.assert_called_once_with(bk_biz_id=2)

    @patch("apps.log_search.models.Space.get_tenant_id", return_value="tenant-space-1")
    def test_result_table_storage_getter_supports_space_result_table_id(self, mock_get_tenant_id):
        tenant_id = TransferApi.get_result_table_storage.bk_tenant_id(
            {"result_table_list": "space_1_bklog.stag_20", "storage_type": "elasticsearch"}
        )

        self.assertEqual(tenant_id, "tenant-space-1")
        mock_get_tenant_id.assert_called_once_with(bk_biz_id=-1)

    @patch("apps.log_search.models.Space.get_tenant_id", return_value="tenant-space-1")
    def test_snapshot_state_getter_uses_first_table_id(self, mock_get_tenant_id):
        tenant_id = TransferApi.get_result_table_snapshot_state.bk_tenant_id(
            {"table_ids": ["space_1_bklog.stag_20", "space_2_bklog.other"]}
        )

        self.assertEqual(tenant_id, "tenant-space-1")
        mock_get_tenant_id.assert_called_once_with(bk_biz_id=-1)

    @patch("apps.log_search.models.Space.get_tenant_id", return_value="tenant-bkcc-18996")
    def test_create_or_update_log_router_getter_uses_space_params(self, mock_get_tenant_id):
        tenant_id = TransferApi.create_or_update_log_router.bk_tenant_id({"space_type": "bkcc", "space_id": "18996"})

        self.assertEqual(tenant_id, "tenant-bkcc-18996")
        mock_get_tenant_id.assert_called_once_with(space_uid="bkcc__18996")

    @patch("apps.log_search.models.Space.get_tenant_id", return_value="tenant-bkcc-18996")
    def test_bulk_create_or_update_log_router_getter_uses_space_params(self, mock_get_tenant_id):
        tenant_id = TransferApi.bulk_create_or_update_log_router.bk_tenant_id(
            {"space_type": "bkcc", "space_id": "18996", "table_info": [{"table_id": "x"}]}
        )

        self.assertEqual(tenant_id, "tenant-bkcc-18996")
        mock_get_tenant_id.assert_called_once_with(space_uid="bkcc__18996")


class CollectorFixtureMixin:
    def setUp(self):
        self.plugin = CollectorPlugin.objects.create(
            collector_plugin_id=50001,
            bk_biz_id=2,
            collector_plugin_name="container file plugin",
            collector_plugin_name_en="container_file_plugin",
            collector_scenario_id="row",
            description="container file plugin",
            category_id="container",
            storage_cluster_id=25,
            retention=14,
            storage_replies=1,
            storage_shards_nums=6,
            storage_shards_size=30,
        )
        self.collector = CollectorConfig.objects.create(
            collector_config_id=10402,
            collector_config_name="bcs-checkinsvr-container",
            collector_plugin_id=self.plugin.collector_plugin_id,
            bk_biz_id=2,
            collector_scenario_id="row",
            category_id="container",
            target_object_type="CONTAINER",
            target_nodes=[{"cluster_id": "BCS-K8S-40002", "namespace": "checkinsvr"}],
            data_link_id=57,
            bk_data_id=150089,
            table_id="2_bklog.bcs_checkinsvr",
            etl_config="bk_log_text",
            subscription_id=9112,
            params={
                "paths": ["/data/logs/*.log"],
                "password": "plain-password",
                "nested": {"bearer_token": "token-value", "api_key": "api-key-value"},
                "endpoint": "https://user:pass@example.com/path",
            },
            task_id_list=[9881, 9882],
            storage_shards_nums=6,
            storage_shards_size=30,
            storage_replies=1,
            environment="container",
            bcs_cluster_id="BCS-K8S-40002",
            yaml_config_enabled=True,
            rule_id=5801,
            enable_v4=True,
        )
        ContainerCollectorConfig.objects.create(
            collector_config_id=self.collector.collector_config_id,
            collector_type=ContainerCollectorType.CONTAINER,
            params=self.collector.params,
        )
        DataLinkConfig.objects.create(
            data_link_id=57,
            link_group_name="bcs-log-v4",
            bk_biz_id=0,
            kafka_cluster_id=8,
            transfer_cluster_id="2",
            es_cluster_ids=[25],
            is_active=True,
        )
        self.index_set = LogIndexSet.objects.create(
            index_set_id=755,
            index_set_name="bcs-checkinsvr-container",
            space_uid="bkcc__2",
            category_id="container",
            collector_config_id=self.collector.collector_config_id,
            scenario_id=Scenario.LOG,
            storage_cluster_id=25,
            time_field="dtEventTimeStamp",
            time_field_type="date",
            time_field_unit="millisecond",
            target_fields=["serverIp"],
            sort_fields=["dtEventTimeStamp"],
            created_by="index-creator",
        )
        LogIndexSetData.objects.create(
            index_id=1755,
            index_set_id=self.index_set.index_set_id,
            bk_biz_id=2,
            result_table_id=self.collector.table_id,
            result_table_name="CheckinSvr 容器文件日志",
            scenario_id=Scenario.LOG,
            storage_cluster_id=25,
            time_field="dtEventTimeStamp",
            time_field_type="date",
            time_field_unit="millisecond",
            apply_status=LogIndexSetData.Status.NORMAL,
        )
        LogIndexSet.objects.create(
            index_set_id=901,
            index_set_name="checkinsvr-all-logs",
            space_uid="bkcc__2",
            category_id="container",
            scenario_id=Scenario.LOG,
            is_group=True,
        )
        LogIndexSetData.objects.create(
            index_id=1901,
            index_set_id=901,
            bk_biz_id=2,
            result_table_id=str(self.index_set.index_set_id),
            result_table_name=self.index_set.index_set_name,
            scenario_id=Scenario.LOG,
            apply_status=LogIndexSetData.Status.NORMAL,
            type=IndexSetDataType.INDEX_SET.value,
        )
        LogIndexSet.objects.create(
            index_set_id=950,
            index_set_name="bcs-checkinsvr-clean-bkbase",
            space_uid="bkcc__2",
            category_id="platform",
            scenario_id=Scenario.BKDATA,
        )
        BKDataClean.objects.create(
            status="success",
            status_en="success",
            result_table_id="591_bkbase.bcs_checkinsvr_clean",
            result_table_name="CheckinSvr 高级清洗",
            raw_data_id=590089,
            data_name="bcs_checkinsvr",
            data_type="log",
            storage_type="bkbase",
            storage_cluster="bkbase",
            collector_config_id=self.collector.collector_config_id,
            bk_biz_id=2,
            log_index_set_id=950,
            etl_config="bk_log_text",
            is_authorized=True,
        )

    def _call(self, func_name, params=None):
        response = self.client.post(
            "/api/v1/admin/resource/call/",
            data=json.dumps({"func_name": func_name, "params": params or {}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)


class CollectorResourceCallTest(CollectorFixtureMixin, ClearRequestLocalMixin, TestCase):
    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.log_admin_resource.handlers.collector._get_primary_index_set", return_value=(None, None))
    def test_collector_list_filters_by_storage_cluster_without_biz_filter(self, mock_get_primary_index_set):
        content = self._call(
            "bklog.collector.list",
            {"storage_cluster_id": 25, "page": 1, "page_size": 20},
        )

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        validate_params(result, FUNCTIONS["bklog.collector.list"]["response_schema"], "response")
        self.assertEqual(result["total"], 1)
        item = result["items"][0]
        self.assertEqual(item["collector_config_id"], 10402)
        self.assertEqual(item["storage_cluster_id"], 25)
        self.assertEqual(item["storage_shards_nums"], 6)
        self.assertEqual(item["storage_shards_size"], 30)
        self.assertEqual(item["storage_replies"], 1)
        self.assertEqual(item["log_access_type"], "container_file")
        self.assertEqual(item["log_access_type_name"], "容器文件采集")
        mock_get_primary_index_set.assert_not_called()

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.log_admin_resource.handlers.collector._get_primary_index_set", return_value=(None, None))
    def test_collector_list_filters_by_log_access_type_without_per_row_index_lookup(self, mock_get_primary_index_set):
        content = self._call(
            "bklog.collector.list",
            {"log_access_type": "container_file", "page": 1, "page_size": 20},
        )

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["collector_config_id"], 10402)
        self.assertEqual(result["items"][0]["log_access_type"], "container_file")
        mock_get_primary_index_set.assert_not_called()

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.log_admin_resource.handlers.collector._get_primary_index_set", return_value=(None, None))
    def test_collector_list_paginates_without_per_row_index_lookup(self, mock_get_primary_index_set):
        CollectorConfig.objects.create(
            collector_config_id=10403,
            collector_config_name="host-access-log",
            collector_plugin_id=self.plugin.collector_plugin_id,
            bk_biz_id=3,
            collector_scenario_id="row",
            category_id="host",
            target_object_type="HOST",
            bk_data_id=150090,
            table_id="3_bklog.host_access_log",
            etl_config="bk_log_text",
            environment="host",
        )

        content = self._call(
            "bklog.collector.list",
            {"page": 1, "page_size": 1, "ordering": "collector_config_id"},
        )

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        self.assertEqual(result["total"], 2)
        self.assertEqual([item["collector_config_id"] for item in result["items"]], [10402])
        mock_get_primary_index_set.assert_not_called()

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.api.TransferApi.get_result_table_storage", return_value=METADATA_STORAGE)
    def test_collector_detail_returns_chain_relations_and_masked_raw_params(self, mock_get_result_table_storage):
        content = self._call("bklog.collector.detail", {"collector_config_id": 10402})

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        validate_params(result, FUNCTIONS["bklog.collector.detail"]["response_schema"], "response")
        self.assertEqual(result["chain"]["primary_index_set_id"], 755)
        self.assertEqual(result["storage"]["storage_cluster_id"], 88)
        self.assertEqual(result["storage"]["retention"], 30)
        self.assertEqual(result["storage"]["allocation_min_days"], 0)
        self.assertEqual(result["storage"]["storage_shards_nums"], 9)
        self.assertEqual(result["storage"]["storage_replies"], 2)
        self.assertEqual(result["collector"]["storage_shards_nums"], 6)
        self.assertEqual(result["collector"]["storage_shards_size"], 30)
        self.assertEqual(result["collector"]["storage_replies"], 1)
        mock_get_result_table_storage.assert_called_once_with(
            {"result_table_list": "2_bklog.bcs_checkinsvr", "storage_type": "elasticsearch"}
        )
        self.assertEqual(result["relations"]["data_link"]["data_link_id"], 57)
        self.assertEqual(
            [(item["relation_type"], item["index_set_id"]) for item in result["relations"]["index_sets"]],
            [("primary", 755), ("parent_group", 901), ("bkdata_clean", 950)],
        )
        self.assertEqual(result["raw"]["params"]["password"], "******")
        self.assertEqual(result["raw"]["params"]["nested"]["bearer_token"], "******")
        self.assertEqual(result["raw"]["params"]["nested"]["api_key"], "******")
        self.assertEqual(result["raw"]["params"]["endpoint"], "https://***:***@example.com/path")

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    def test_index_set_list_returns_result_tables_and_collector_relation(self):
        content = self._call(
            "bklog.index_set.list",
            {"result_table_id": "bcs_checkinsvr", "page": 1, "page_size": 20},
        )

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        self.assertEqual(result["total"], 2)
        by_id = {item["index_set_id"]: item for item in result["items"]}
        self.assertEqual(by_id[755]["collector_config_id"], 10402)
        self.assertIsNotNone(by_id[755]["created_at"])
        self.assertEqual(by_id[755]["created_by"], "index-creator")
        self.assertEqual(by_id[755]["result_table_ids"], ["2_bklog.bcs_checkinsvr"])
        self.assertEqual(by_id[755]["index_count"], 1)
        self.assertEqual(by_id[901]["result_table_ids"], ["2_bklog.bcs_checkinsvr"])
        self.assertEqual(by_id[901]["index_count"], 1)

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.log_admin_resource.handlers.index_set._get_visible_indexes", return_value=[])
    def test_index_set_list_paginates_without_per_row_index_lookup(self, mock_get_visible_indexes):
        LogIndexSet.objects.create(
            index_set_id=990,
            index_set_name="host-access-log",
            space_uid="bkcc__3",
            category_id="host",
            scenario_id=Scenario.LOG,
        )

        content = self._call(
            "bklog.index_set.list",
            {"page": 1, "page_size": 1, "ordering": "index_set_id"},
        )

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        self.assertEqual(result["total"], 4)
        self.assertEqual([item["index_set_id"] for item in result["items"]], [755])
        mock_get_visible_indexes.assert_not_called()

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.log_admin_resource.handlers.index_set._get_visible_indexes", return_value=[])
    def test_index_set_list_filters_result_table_without_per_row_index_lookup(self, mock_get_visible_indexes):
        content = self._call(
            "bklog.index_set.list",
            {"result_table_id": "bcs_checkinsvr", "page": 1, "page_size": 20},
        )

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        self.assertEqual(result["total"], 2)
        by_id = {item["index_set_id"]: item for item in result["items"]}
        self.assertEqual(by_id[755]["result_table_ids"], ["2_bklog.bcs_checkinsvr"])
        self.assertEqual(by_id[901]["result_table_ids"], ["2_bklog.bcs_checkinsvr"])
        mock_get_visible_indexes.assert_not_called()

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    def test_index_set_detail_resolves_collectors_from_index_set_to_collector_config(self):
        content = self._call("bklog.index_set.detail", {"index_set_id": 755})

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        self.assertEqual(result["index_set"]["collector_config_id"], 10402)
        self.assertIsNotNone(result["index_set"]["created_at"])
        self.assertEqual(result["index_set"]["created_by"], "index-creator")
        self.assertEqual([item["result_table_id"] for item in result["indexes"]], ["2_bklog.bcs_checkinsvr"])
        self.assertEqual([item["collector_config_id"] for item in result["collectors"]], [10402])

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    def test_index_group_detail_resolves_collectors_from_member_index_sets(self):
        content = self._call("bklog.index_set.detail", {"index_set_id": 901})

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        self.assertTrue(result["index_set"]["is_group"])
        self.assertEqual([item["result_table_id"] for item in result["indexes"]], ["2_bklog.bcs_checkinsvr"])
        self.assertEqual([item["collector_config_id"] for item in result["collectors"]], [10402])

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("bkm_space.api.SpaceApi.get_space_detail")
    def test_index_set_bk_biz_id_uses_space_uid_not_index_data_biz_id(self, mock_get_space_detail):
        mock_get_space_detail.return_value = SimpleNamespace(id=66)
        index_set = LogIndexSet.objects.create(
            index_set_id=971,
            index_set_name="pipeline-external-log",
            space_uid="bkci__pipeline-demo",
            category_id="platform",
            scenario_id=Scenario.LOG,
        )
        LogIndexSetData.objects.create(
            index_id=1971,
            index_set_id=index_set.index_set_id,
            bk_biz_id=2,
            result_table_id="2_bklog.pipeline_external_log",
            result_table_name="Pipeline 外部日志",
            scenario_id=Scenario.LOG,
            apply_status=LogIndexSetData.Status.NORMAL,
        )

        content = self._call("bklog.index_set.detail", {"index_set_id": 971})

        self.assertTrue(content["result"])
        self.assertEqual(content["data"]["result"]["index_set"]["bk_biz_id"], -66)

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("bkm_space.api.SpaceApi.batch_get_space_detail")
    def test_index_set_list_batch_resolves_bk_biz_id_without_per_row_space_lookup(self, mock_batch):
        mock_batch.return_value = {
            "bkci__pipeline-a": SimpleNamespace(id=66),
            "bkci__pipeline-b": SimpleNamespace(id=77),
        }
        LogIndexSet.objects.create(
            index_set_id=981,
            index_set_name="pipeline-a-log",
            space_uid="bkci__pipeline-a",
            category_id="platform",
            scenario_id=Scenario.LOG,
        )
        LogIndexSet.objects.create(
            index_set_id=982,
            index_set_name="pipeline-b-log",
            space_uid="bkci__pipeline-b",
            category_id="platform",
            scenario_id=Scenario.LOG,
        )
        LogIndexSet.objects.create(
            index_set_id=983,
            index_set_name="pipeline-c-log",
            space_uid="bkcc__9",
            category_id="platform",
            scenario_id=Scenario.LOG,
        )

        content = self._call(
            "bklog.index_set.list",
            {"index_set_name": "pipeline", "page": 1, "page_size": 20, "ordering": "index_set_id"},
        )

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        self.assertEqual(result["total"], 3)
        by_id = {item["index_set_id"]: item for item in result["items"]}
        self.assertEqual(by_id[981]["bk_biz_id"], -66)
        self.assertEqual(by_id[982]["bk_biz_id"], -77)
        # BKCC 业务空间直接解析，无需查询
        self.assertEqual(by_id[983]["bk_biz_id"], 9)
        # 整页非业务空间只触发一次批量查询，消除 N+1；BKCC 空间不进入批量集合
        mock_batch.assert_called_once()
        called_space_uids = mock_batch.call_args.args[0]
        self.assertEqual(set(called_space_uids), {"bkci__pipeline-a", "bkci__pipeline-b"})


class CollectorStorageResourceCallTest(CollectorFixtureMixin, ClearRequestLocalMixin, TestCase):
    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.api.TransferApi.get_result_table_storage", return_value=HOT_WARM_METADATA_STORAGE)
    def test_storage_snapshot_returns_current_metadata_values(self, mock_get_result_table_storage):
        content = self._call(
            "bklog.collector.storage.snapshot",
            {"collector_config_ids": [10402]},
        )

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        validate_params(result, FUNCTIONS["bklog.collector.storage.snapshot"]["response_schema"], "response")
        self.assertEqual(result["summary"]["total"], 1)
        item = result["items"][0]
        self.assertEqual(item["before"]["storage_cluster_id"], 88)
        self.assertEqual(item["before"]["retention"], 30)
        self.assertEqual(item["before"]["allocation_min_days"], 5)
        self.assertEqual(item["before"]["storage_shards_nums"], 9)
        self.assertEqual(item["before"]["storage_replies"], 2)
        self.assertEqual(item["before"]["storage_shards_size"], 30)
        self.assertEqual(item["after"], item["before"])
        self.assertEqual(item["diff"], [])
        mock_get_result_table_storage.assert_called_once()

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.api.TransferApi.get_result_table_storage", side_effect=RuntimeError("transfer unavailable"))
    def test_storage_snapshot_returns_warning_when_storage_query_fails(self, mock_get_result_table_storage):
        content = self._call(
            "bklog.collector.storage.snapshot",
            {"collector_config_ids": [10402]},
        )

        self.assertTrue(content["result"])
        item = content["data"]["result"]["items"][0]
        self.assertEqual(item["status"], "blocked")
        self.assertEqual(item["before"]["retention"], None)
        self.assertEqual(item["before"]["allocation_min_days"], None)
        self.assertEqual(item["before"]["storage_shards_nums"], 6)
        self.assertEqual(item["before"]["storage_replies"], 1)
        self.assertEqual(item["warnings"][0]["code"], "result_table_storage_query_failed")
        mock_get_result_table_storage.assert_called_once()

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    def test_storage_snapshot_rejects_more_than_thirty_collectors(self):
        content = self._call(
            "bklog.collector.storage.snapshot",
            {"collector_config_ids": list(range(1, 32))},
        )

        self.assertFalse(content["result"])
        self.assertIn("at most 30 items", content["message"])

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.api.TransferApi.get_result_table_storage", return_value=METADATA_STORAGE)
    @patch("apps.log_admin_resource.handlers.collector_storage.StorageHandler")
    def test_storage_preview_returns_diff_for_selected_collectors(
        self, mock_storage_handler, mock_get_result_table_storage
    ):
        mock_storage_handler.return_value.get_cluster_info_by_id.return_value = NORMAL_CLUSTER_INFO
        content = self._call(
            "bklog.collector.storage.preview",
            {
                "collector_config_ids": [10402],
                "target": {
                    "storage_cluster_id": 25,
                    "retention": 7,
                    "storage_shards_nums": 3,
                    "storage_replies": 0,
                },
            },
        )

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        validate_params(result, FUNCTIONS["bklog.collector.storage.preview"]["response_schema"], "response")
        self.assertEqual(result["summary"]["total"], 1)
        self.assertEqual(result["summary"]["changeable"], 1)
        item = result["items"][0]
        self.assertEqual(item["collector_config_id"], 10402)
        self.assertEqual(item["before"]["storage_cluster_id"], 88)
        self.assertEqual(item["before"]["retention"], 30)
        self.assertEqual(item["before"]["allocation_min_days"], 0)
        self.assertEqual(item["before"]["storage_shards_nums"], 9)
        self.assertEqual(item["before"]["storage_replies"], 2)
        self.assertEqual(item["after"]["storage_cluster_id"], 25)
        self.assertEqual(item["after"]["retention"], 7)
        self.assertIn("storage_cluster_id", [diff["field"] for diff in item["diff"]])
        self.assertIn("retention", [diff["field"] for diff in item["diff"]])
        mock_get_result_table_storage.assert_called_once()

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    def test_storage_preview_rejects_empty_target(self):
        content = self._call(
            "bklog.collector.storage.preview",
            {"collector_config_ids": [10402], "target": {}},
        )

        self.assertFalse(content["result"])
        self.assertIn("target must include", content["message"])

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    def test_storage_preview_rejects_storage_shards_size_as_a_write_target(self):
        content = self._call(
            "bklog.collector.storage.preview",
            {"collector_config_ids": [10402], "target": {"storage_shards_size": 30}},
        )

        self.assertFalse(content["result"])
        self.assertIn("unsupported target fields: storage_shards_size", content["message"])

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    def test_storage_preview_rejects_zero_hot_data_days(self):
        content = self._call(
            "bklog.collector.storage.preview",
            {"collector_config_ids": [10402], "target": {"allocation_min_days": 0}},
        )

        self.assertFalse(content["result"])
        self.assertIn("allocation_min_days must be greater than or equal to 1", content["message"])

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.api.TransferApi.get_result_table_storage", return_value=METADATA_STORAGE)
    @patch("apps.log_admin_resource.handlers.collector_storage.StorageHandler")
    def test_storage_preview_does_not_query_cluster_for_unrelated_storage_changes(
        self, mock_storage_handler, mock_get_result_table_storage
    ):
        content = self._call(
            "bklog.collector.storage.preview",
            {"collector_config_ids": [10402], "target": {"storage_shards_nums": 3}},
        )

        self.assertTrue(content["result"])
        self.assertEqual(content["data"]["result"]["items"][0]["status"], "changeable")
        mock_storage_handler.assert_not_called()

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.api.TransferApi.get_result_table_storage", return_value=METADATA_STORAGE)
    @patch("apps.log_admin_resource.handlers.collector_storage.StorageHandler")
    def test_storage_preview_requires_hot_data_days_when_switching_to_hot_warm_cluster(
        self, mock_storage_handler, mock_get_result_table_storage
    ):
        mock_storage_handler.return_value.get_cluster_info_by_id.return_value = HOT_WARM_CLUSTER_INFO

        content = self._call(
            "bklog.collector.storage.preview",
            {
                "collector_config_ids": [10402],
                "target": {"storage_cluster_id": 25, "retention": 7},
            },
        )

        self.assertTrue(content["result"])
        item = content["data"]["result"]["items"][0]
        self.assertEqual(item["status"], "blocked")
        self.assertIn("hot_data_days_required", [warning["code"] for warning in item["warnings"]])

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.api.TransferApi.get_result_table_storage", return_value=METADATA_STORAGE)
    @patch("apps.log_admin_resource.handlers.collector_storage.StorageHandler")
    def test_storage_preview_requires_hot_data_days_to_be_less_than_retention(
        self, mock_storage_handler, mock_get_result_table_storage
    ):
        mock_storage_handler.return_value.get_cluster_info_by_id.return_value = HOT_WARM_CLUSTER_INFO

        content = self._call(
            "bklog.collector.storage.preview",
            {
                "collector_config_ids": [10402],
                "target": {
                    "storage_cluster_id": 25,
                    "retention": 7,
                    "allocation_min_days": 7,
                },
            },
        )

        self.assertTrue(content["result"])
        item = content["data"]["result"]["items"][0]
        self.assertEqual(item["status"], "blocked")
        self.assertIn("invalid_hot_data_days", [warning["code"] for warning in item["warnings"]])

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.api.TransferApi.get_result_table_storage", return_value=HOT_WARM_METADATA_STORAGE)
    @patch("apps.log_admin_resource.handlers.collector_storage.StorageHandler")
    def test_storage_preview_preserves_existing_hot_data_days(
        self, mock_storage_handler, mock_get_result_table_storage
    ):
        mock_storage_handler.return_value.get_cluster_info_by_id.return_value = HOT_WARM_CLUSTER_INFO

        content = self._call(
            "bklog.collector.storage.preview",
            {"collector_config_ids": [10402], "target": {"retention": 20}},
        )

        self.assertTrue(content["result"])
        item = content["data"]["result"]["items"][0]
        self.assertEqual(item["status"], "changeable")
        self.assertEqual(item["after"]["allocation_min_days"], 5)

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.api.TransferApi.get_result_table_storage", return_value=METADATA_STORAGE)
    @patch("apps.log_admin_resource.handlers.collector_storage.StorageHandler")
    def test_storage_preview_rejects_hot_data_days_for_normal_cluster(
        self, mock_storage_handler, mock_get_result_table_storage
    ):
        mock_storage_handler.return_value.get_cluster_info_by_id.return_value = NORMAL_CLUSTER_INFO

        content = self._call(
            "bklog.collector.storage.preview",
            {"collector_config_ids": [10402], "target": {"allocation_min_days": 5}},
        )

        self.assertTrue(content["result"])
        item = content["data"]["result"]["items"][0]
        self.assertEqual(item["status"], "blocked")
        self.assertIn("hot_data_days_not_supported", [warning["code"] for warning in item["warnings"]])

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.api.TransferApi.get_result_table_storage", return_value=HOT_WARM_METADATA_STORAGE)
    @patch("apps.log_admin_resource.handlers.collector_storage.StorageHandler")
    def test_storage_preview_clears_hot_data_days_when_switching_to_normal_cluster(
        self, mock_storage_handler, mock_get_result_table_storage
    ):
        mock_storage_handler.return_value.get_cluster_info_by_id.return_value = NORMAL_CLUSTER_INFO

        content = self._call(
            "bklog.collector.storage.preview",
            {"collector_config_ids": [10402], "target": {"storage_cluster_id": 25}},
        )

        self.assertTrue(content["result"])
        item = content["data"]["result"]["items"][0]
        self.assertEqual(item["status"], "changeable")
        self.assertEqual(item["after"]["allocation_min_days"], 0)
        self.assertIn("allocation_min_days", [diff["field"] for diff in item["diff"]])

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.api.TransferApi.get_result_table_storage", return_value=METADATA_STORAGE)
    @patch("apps.log_admin_resource.handlers.collector_storage.TransferEtlHandler.patch_update")
    @patch("apps.log_admin_resource.handlers.collector_storage.StorageHandler")
    def test_storage_apply_uses_existing_patch_update_after_expected_before_check(
        self, mock_storage_handler, mock_patch_update, mock_get_result_table_storage
    ):
        mock_storage_handler.return_value.get_cluster_info_by_id.return_value = HOT_WARM_CLUSTER_INFO
        mock_patch_update.return_value = {"storage_cluster_id": 25, "retention": 7, "es_shards": 3}
        content = self._call(
            "bklog.collector.storage.apply",
            {
                "collector_config_ids": [10402],
                "target": {
                    "storage_cluster_id": 25,
                    "retention": 7,
                    "allocation_min_days": 6,
                    "storage_shards_nums": 3,
                    "storage_replies": 0,
                },
                "expected_before": {
                    "10402": {
                        "storage_cluster_id": 88,
                        "retention": 30,
                        "allocation_min_days": 0,
                        "storage_shards_nums": 9,
                        "storage_replies": 2,
                    }
                },
                "remark": "批量调整采集项存储配置",
            },
        )

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        validate_params(result, FUNCTIONS["bklog.collector.storage.apply"]["response_schema"], "response")
        self.assertEqual(result["summary"]["success"], 1)
        self.assertEqual(result["items"][0]["status"], "success")
        mock_patch_update.assert_called_once_with(
            storage_cluster_id=25,
            retention=7,
            allocation_min_days=6,
            storage_replies=0,
            es_shards=3,
        )
        mock_get_result_table_storage.assert_called_once()

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.api.TransferApi.get_result_table_storage", return_value=METADATA_STORAGE)
    @patch("apps.log_admin_resource.handlers.collector_storage.TransferEtlHandler.patch_update")
    @patch("apps.log_admin_resource.handlers.collector_storage.StorageHandler")
    def test_storage_apply_blocks_when_expected_before_is_stale(
        self, mock_storage_handler, mock_patch_update, mock_get_result_table_storage
    ):
        mock_storage_handler.return_value.get_cluster_info_by_id.return_value = NORMAL_CLUSTER_INFO
        content = self._call(
            "bklog.collector.storage.apply",
            {
                "collector_config_ids": [10402],
                "target": {"retention": 7},
                "expected_before": {"10402": {"retention": 14}},
            },
        )

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        self.assertEqual(result["summary"]["blocked"], 1)
        self.assertEqual(result["items"][0]["status"], "blocked")
        self.assertIn("expected_before", result["items"][0]["execution_message"])
        mock_patch_update.assert_not_called()
        mock_get_result_table_storage.assert_called_once()

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.log_admin_resource.handlers.storage_cluster.StorageHandler")
    def test_storage_cluster_list_returns_business_visible_es_clusters(self, mock_storage_handler):
        mock_storage_handler.return_value.get_cluster_groups.return_value = [
            {
                "storage_cluster_id": 25,
                "storage_cluster_name": "public-hot-es",
                "registered_system": "_default",
                "enable_hot_warm": True,
            },
            {
                "storage_cluster_id": 26,
                "storage_cluster_name": "business-es",
                "registered_system": "bk_log_search",
                "enable_hot_warm": False,
            },
        ]

        content = self._call("bklog.storage_cluster.list", {"bk_biz_id": 2, "page": 1, "page_size": 20})

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        validate_params(result, FUNCTIONS["bklog.storage_cluster.list"]["response_schema"], "response")
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["items"][0]["storage_cluster_id"], 25)
        self.assertEqual(result["items"][0]["storage_cluster_name"], "public-hot-es")
        self.assertTrue(result["items"][0]["is_public"])
        self.assertTrue(result["items"][0]["hot_warm_enabled"])
        self.assertFalse(result["items"][1]["is_public"])
        mock_storage_handler.return_value.get_cluster_groups.assert_called_once_with(bk_biz_id=2, cluster_id=None)
        mock_storage_handler.return_value.list.assert_not_called()

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    @patch("apps.log_admin_resource.handlers.storage_cluster.StorageHandler")
    def test_storage_cluster_list_filters_visible_clusters_by_id(self, mock_storage_handler):
        mock_storage_handler.return_value.get_cluster_groups.return_value = [
            {
                "storage_cluster_id": 25,
                "storage_cluster_name": "public-es",
                "registered_system": "_default",
            },
            {
                "storage_cluster_id": 26,
                "storage_cluster_name": "business-es",
                "registered_system": "bk_log_search",
            },
        ]

        content = self._call(
            "bklog.storage_cluster.list",
            {"bk_biz_id": 2, "storage_cluster_id": 25, "page": 1, "page_size": 20},
        )

        self.assertTrue(content["result"])
        result = content["data"]["result"]
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["storage_cluster_id"], 25)
        self.assertTrue(result["items"][0]["is_public"])
        mock_storage_handler.return_value.get_cluster_groups.assert_called_once_with(bk_biz_id=2, cluster_id=25)


class StorageClusterHandlerTest(TestCase):
    @patch("apps.log_databus.handlers.storage.MultiExecuteFunc")
    def test_get_cluster_groups_pushes_cluster_id_to_transfer_query(self, mock_multi_execute):
        mock_multi_execute.return_value.run.return_value = {STORAGE_CLUSTER_TYPE: []}

        result = StorageHandler().get_cluster_groups(bk_biz_id=2, cluster_id=25)

        self.assertEqual(result, [])
        mock_multi_execute.return_value.append.assert_called_once_with(
            STORAGE_CLUSTER_TYPE,
            TransferApi.get_cluster_info,
            {"cluster_type": STORAGE_CLUSTER_TYPE, "cluster_id": 25},
        )
