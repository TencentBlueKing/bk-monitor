from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.log_admin_resource.handlers.platform_source import (
    FUNCTIONS,
    OPERATIONS,
    OperationSpec,
    PlatformSourceError,
    _data_age_seconds,
    _kafka_time_row,
    _validate_operation_params,
    query_platform_source,
)
from apps.log_admin_resource.registry import AdminResourceRegistry
from apps.log_admin_resource.schema import validate_params


class PlatformSourceHandlerTest(SimpleTestCase):
    def test_discover_exposes_only_fixed_readonly_domains(self):
        result = query_platform_source({"mode": "discover"})

        validate_params(result, FUNCTIONS["bklog.platform_source.query"]["response_schema"], "response")
        self.assertEqual(result["kind"], "domain_catalog")
        self.assertEqual([item["id"] for item in result["result"]["domains"]], ["cmdb", "metadata", "nodeman"])
        self.assertNotIn("status", result)
        self.assertTrue(result["catalog_revision"])
        self.assertTrue(result["observed_at"])

    def test_discover_and_describe_support_progressive_disclosure(self):
        discovered = query_platform_source({"mode": "discover", "domain": "cmdb"})
        described = query_platform_source({"mode": "describe", "domain": "cmdb", "operation": "resolve_host"})

        schema = FUNCTIONS["bklog.platform_source.query"]["response_schema"]
        validate_params(discovered, schema, "response")
        validate_params(described, schema, "response")
        self.assertEqual([item["id"] for item in discovered["result"]["operations"]], ["resolve_host"])
        self.assertEqual(described["result"]["params_schema"]["required"], ["ip"])
        self.assertEqual(described["result"]["safety_level"], "read")
        self.assertEqual(described["result"]["projection"]["mode"], "field_allowlist_and_recursive_redaction")
        self.assertEqual(described["result"]["limits"]["timeout_seconds"], 10)
        self.assertEqual(described["next_call"]["mode"], "invoke")

    def test_every_registered_operation_declares_a_fixed_nonempty_response_projection(self):
        for key, spec in OPERATIONS.items():
            with self.subTest(operation=key):
                self.assertEqual(spec.projection["mode"], "field_allowlist_and_recursive_redaction")
                self.assertTrue(spec.projection["fields"])

    def test_invalid_mode_domain_operation_and_invoke_envelope_return_stable_errors(self):
        cases = (
            ({"mode": "delete"}, "INVALID_ARGUMENT"),
            ({"mode": "discover", "domain": "job"}, "DOMAIN_NOT_FOUND"),
            ({"mode": "describe", "domain": "nodeman", "operation": "delete"}, "OPERATION_NOT_FOUND"),
            (
                {
                    "mode": "invoke",
                    "domain": "nodeman",
                    "operation": "get_subscription_summary",
                    "params": [],
                },
                "INVALID_ARGUMENT",
            ),
            ({"mode": "invoke", "domain": "nodeman", "operation": "delete", "params": {}}, "OPERATION_NOT_ALLOWED"),
        )
        for params, code in cases:
            with self.subTest(params=params), self.assertRaises(PlatformSourceError) as raised:
                query_platform_source(params)
            self.assertEqual(raised.exception.code, code)

        with self.assertRaises(PlatformSourceError) as raised:
            query_platform_source({"mode": "invoke", "domain": "job", "operation": "execute", "params": {}})
        self.assertEqual(raised.exception.code, "DOMAIN_NOT_FOUND")

    def test_operation_param_validation_covers_required_integer_and_array_boundaries(self):
        cases = (
            ("get_subscription_summary", {}, "missing required params"),
            ("get_subscription_task_instances", {"subscription_id": True}, "must be an integer"),
            ("get_subscription_task_instances", {"subscription_id": "invalid"}, "must be an integer"),
            ("get_subscription_task_instances", {"subscription_id": 0}, "below the minimum"),
            ("get_subscription_task_instances", {"subscription_id": 1, "pagesize": 1001}, "exceeds the maximum"),
            ("get_subscription_task_instances", {"subscription_id": 1, "task_id_list": []}, "non-empty array"),
            (
                "get_subscription_task_instances",
                {"subscription_id": 1, "task_id_list": list(range(1, 102))},
                "more than 100 items",
            ),
            (
                "get_subscription_task_instances",
                {"subscription_id": 1, "task_id_list": ["invalid"]},
                "items must be integers",
            ),
            (
                "get_subscription_task_instances",
                {"subscription_id": 1, "task_id_list": [True]},
                "items must be positive integers",
            ),
            (
                "get_subscription_task_instances",
                {"subscription_id": 1, "task_id_list": [0]},
                "items must be positive integers",
            ),
        )
        for operation, params, message in cases:
            with self.subTest(operation=operation, params=params):
                with self.assertRaises(PlatformSourceError) as raised:
                    query_platform_source(
                        {"mode": "invoke", "domain": "nodeman", "operation": operation, "params": params}
                    )
                self.assertEqual(raised.exception.code, "INVALID_ARGUMENT")
                self.assertIn(message, raised.exception.message)

    def test_operation_param_validator_ignores_unsupported_internal_schema_types(self):
        spec = OperationSpec(
            "test",
            "schema-branches",
            "schema branch coverage",
            {
                "type": "object",
                "properties": {
                    "flags": {"type": "array", "items": {"type": "boolean"}},
                    "enabled": {"type": "boolean"},
                },
            },
            {},
            lambda _params: {},
            lambda raw, _params: raw,
        )

        self.assertEqual(
            _validate_operation_params(spec, {"flags": [True], "enabled": True}),
            {"flags": [True], "enabled": True},
        )

    def test_string_and_string_array_validation_rejects_empty_or_wrong_items(self):
        cases = (
            ("get_result_table", {"result_table_id": "   "}, "must be a non-empty string"),
            (
                "get_result_table_storage_status",
                {"result_table_ids": [1]},
                "items must be non-empty strings",
            ),
        )
        for operation, params, message in cases:
            with self.subTest(operation=operation):
                with self.assertRaises(PlatformSourceError) as raised:
                    query_platform_source(
                        {"mode": "invoke", "domain": "metadata", "operation": operation, "params": params}
                    )
                self.assertEqual(raised.exception.code, "INVALID_ARGUMENT")
                self.assertIn(message, raised.exception.message)

    @patch("apps.log_admin_resource.handlers.platform_source.get_request_tenant_id", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.platform_source.TransferApi.get_result_table_storage_status")
    def test_string_array_items_are_trimmed_and_request_tenant_is_forwarded(self, mock_api, _tenant):
        mock_api.return_value = []

        query_platform_source(
            {
                "mode": "invoke",
                "domain": "metadata",
                "operation": "get_result_table_storage_status",
                "params": {"result_table_ids": [" 2_bklog.demo "]},
            }
        )

        self.assertEqual(mock_api.call_args.kwargs["params"]["table_ids"], ["2_bklog.demo"])
        self.assertEqual(mock_api.call_args.kwargs["bk_tenant_id"], "tenant-a")

    @patch("apps.log_admin_resource.handlers.platform_source.NodeApi.get_subscription_info")
    def test_unknown_or_extra_params_are_rejected_before_provider_call(self, mock_api):
        with self.assertRaises(PlatformSourceError) as unknown_operation:
            query_platform_source(
                {"mode": "invoke", "domain": "nodeman", "operation": "delete_subscription", "params": {}}
            )
        with self.assertRaises(PlatformSourceError) as extra_param:
            query_platform_source(
                {
                    "mode": "invoke",
                    "domain": "nodeman",
                    "operation": "get_subscription_summary",
                    "params": {"subscription_id_list": [1], "bk_username": "admin"},
                }
            )

        self.assertEqual(unknown_operation.exception.code, "OPERATION_NOT_ALLOWED")
        self.assertEqual(extra_param.exception.code, "INVALID_ARGUMENT")
        mock_api.assert_not_called()

    @patch("apps.log_admin_resource.handlers.platform_source.NodeApi.get_subscription_info")
    def test_subscription_summary_uses_service_identity_and_projects_sensitive_detail(self, mock_api):
        mock_api.return_value = [
            {
                "id": 11,
                "name": "collector",
                "scope": {"bk_biz_id": 2, "nodes": [{"bk_inst_id": 1}]},
                "target_hosts": [{"bk_host_id": 1}],
                "steps": [
                    {
                        "id": 3,
                        "type": "PLUGIN",
                        "params": {"password": "should-not-return"},
                        "config": {
                            "plugin_name": "bkunifylogbeat",
                            "plugin_version": "latest",
                            "config_templates": [{"name": "main", "version": "v1", "content": "secret config"}],
                        },
                    }
                ],
            }
        ]

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "nodeman",
                "operation": "get_subscription_summary",
                "params": {"subscription_id_list": [11]},
            }
        )

        validate_params(result, FUNCTIONS["bklog.platform_source.query"]["response_schema"], "response")
        called_params = mock_api.call_args.kwargs["params"]
        self.assertTrue(called_params["no_request"])
        self.assertNotIn("bk_username", called_params)
        self.assertEqual(result["result"][0]["scope"]["node_count"], 1)
        self.assertEqual(result["result"][0]["target_host_count"], 1)
        self.assertNotIn("nodes", result["result"][0]["scope"])
        self.assertNotIn("params", result["result"][0]["steps"][0])
        self.assertNotIn("content", result["result"][0]["steps"][0]["config"]["config_templates"][0])

    @patch("apps.log_admin_resource.handlers.platform_source.NodeApi.get_subscription_info")
    def test_subscription_summary_skips_malformed_rows_and_steps(self, mock_api):
        mock_api.return_value = ["invalid", {"id": 11, "steps": ["invalid"]}]

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "nodeman",
                "operation": "get_subscription_summary",
                "params": {"subscription_id_list": [11]},
            }
        )

        self.assertEqual(
            result["result"], [{"id": 11, "scope": {"node_count": 0}, "target_host_count": 0, "steps": []}]
        )

    @patch("apps.log_admin_resource.handlers.platform_source.NodeApi.subscription_statistic")
    def test_subscription_statistic_forces_log_plugin_and_projects_rows(self, mock_api):
        mock_api.return_value = [
            "invalid",
            {
                "subscription_id": 11,
                "instances": 2,
                "status": [{"status": "SUCCESS", "count": 2}, "invalid"],
                "versions": [{"name": "bkunifylogbeat", "version": "1.0", "count": 2}, "invalid"],
            },
        ]

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "nodeman",
                "operation": "fetch_subscription_statistic",
                "params": {"subscription_id_list": [11]},
            }
        )

        self.assertEqual(mock_api.call_args.kwargs["params"]["plugin_name"], "bkunifylogbeat")
        self.assertEqual(result["result"][0]["status"], [{"status": "SUCCESS", "count": 2}])

    @patch("apps.log_admin_resource.handlers.platform_source.NodeApi.get_subscription_instance_status")
    def test_subscription_instance_status_forces_no_task_detail_and_projects_response(self, mock_api):
        mock_api.return_value = [
            {
                "subscription_id": 11,
                "instances": [
                    {
                        "instance_id": 22,
                        "status": "SUCCESS",
                        "instance_info": {"host": {"bk_host_id": 33, "bk_host_innerip": "127.0.0.1"}},
                        "steps": [{"log": "sensitive"}],
                        "host_statuses": [{"name": "bkunifylogbeat", "status": "RUNNING", "version": "1.0"}],
                    }
                ],
            }
        ]

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "nodeman",
                "operation": "get_subscription_instance_status",
                "params": {"subscription_id_list": [11]},
            }
        )

        called_params = mock_api.call_args.kwargs["params"]
        self.assertFalse(called_params["show_task_detail"])
        self.assertTrue(called_params["no_request"])
        instance = result["result"][0]["instances"][0]
        self.assertEqual(instance["instance_info"]["host"]["bk_host_id"], 33)
        self.assertNotIn("steps", instance)

    @patch("apps.log_admin_resource.handlers.platform_source.NodeApi.get_subscription_instance_status")
    def test_subscription_instance_projection_skips_malformed_rows_and_normalizes_cloud(self, mock_api):
        mock_api.return_value = [
            "invalid",
            {
                "subscription_id": 11,
                "instances": [
                    "invalid",
                    {
                        "instance_id": 22,
                        "instance_info": {"host": {"bk_host_id": 33, "bk_cloud_id": [{"id": 0}]}},
                    },
                ],
            },
        ]

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "nodeman",
                "operation": "get_subscription_instance_status",
                "params": {"subscription_id_list": [11]},
            }
        )

        self.assertEqual(result["result"][0]["instances"][0]["instance_info"]["host"]["bk_cloud_id"], 0)

    @patch("apps.log_admin_resource.handlers.platform_source.NodeApi.get_subscription_task_status")
    def test_task_instances_force_readonly_detail_flags(self, mock_api):
        mock_api.return_value = {"total": 0, "list": [], "status_counter": {}}

        query_platform_source(
            {
                "mode": "invoke",
                "domain": "nodeman",
                "operation": "get_subscription_task_instances",
                "params": {"subscription_id": 11, "page": 2, "pagesize": 20},
            }
        )

        called_params = mock_api.call_args.kwargs["params"]
        self.assertFalse(called_params["need_detail"])
        self.assertTrue(called_params["need_aggregate_all_tasks"])
        self.assertFalse(called_params["need_out_of_scope_snapshots"])
        self.assertEqual((called_params["page"], called_params["pagesize"]), (2, 20))

    @patch("apps.log_admin_resource.handlers.platform_source.NodeApi.get_subscription_task_status")
    def test_task_instances_use_defaults_and_accept_explicit_task_ids(self, mock_api):
        mock_api.return_value = {"total": 1, "list": [], "status_counter": {}}

        query_platform_source(
            {
                "mode": "invoke",
                "domain": "nodeman",
                "operation": "get_subscription_task_instances",
                "params": {"subscription_id": 11, "task_id_list": [22]},
            }
        )

        called_params = mock_api.call_args.kwargs["params"]
        self.assertEqual((called_params["page"], called_params["pagesize"]), (1, 100))
        self.assertFalse(called_params["need_aggregate_all_tasks"])
        self.assertEqual(called_params["task_id_list"], [22])

    @patch("apps.log_admin_resource.handlers.platform_source.NodeApi.plugin_search")
    def test_host_plugin_status_projects_only_bounded_fields(self, mock_api):
        mock_api.return_value = {
            "total": 1,
            "list": [
                "invalid",
                {
                    "bk_host_id": 33,
                    "status": "RUNNING",
                    "password": "hidden",
                    "plugin_status": [{"name": "bkunifylogbeat", "status": "RUNNING"}, "invalid"],
                },
            ],
        }

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "nodeman",
                "operation": "search_host_plugin_status",
                "params": {"bk_host_id": [33]},
            }
        )

        self.assertEqual(result["result"]["list"][0]["bk_host_id"], 33)
        self.assertNotIn("password", result["result"]["list"][0])

    @patch("apps.log_admin_resource.handlers.platform_source.NodeApi.plugin_search")
    def test_host_plugin_status_treats_non_object_provider_payload_as_empty(self, mock_api):
        mock_api.return_value = []

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "nodeman",
                "operation": "search_host_plugin_status",
                "params": {"bk_host_id": [33]},
            }
        )

        self.assertEqual(result["result"], {"total": 0, "list": []})

    @patch("apps.log_admin_resource.handlers.platform_source.TransferApi.get_result_table_storage")
    def test_metadata_storage_params_are_mapped_and_response_is_allowlisted(self, mock_api):
        mock_api.return_value = {
            "2_bklog.demo": {
                "storage_cluster_id": 1,
                "retention": 7,
                "auth_info": {"username": "admin", "password": "top-secret"},
                "cluster_config": {
                    "cluster_id": 1,
                    "cluster_name": "es-one",
                    "domain_name": "secret.example.com",
                    "port": 9200,
                    "custom_option": {"admin": ["operator"]},
                    "raw_ssl_certificate": "secret-certificate",
                },
                "unexpected": "drop-me",
            },
            "malformed": "drop-me",
        }

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "metadata",
                "operation": "get_result_table_storage",
                "params": {"result_table_id": "2_bklog.demo", "storage_type": "elasticsearch"},
            }
        )

        called_params = mock_api.call_args.kwargs["params"]
        self.assertEqual(called_params["result_table_list"], "2_bklog.demo")
        self.assertEqual(called_params["storage_type"], "elasticsearch")
        self.assertTrue(called_params["no_request"])
        self.assertEqual(
            result["result"],
            {
                "items": [
                    {
                        "table_id": "2_bklog.demo",
                        "storage_type": "elasticsearch",
                        "storage_cluster_id": 1,
                        "retention": 7,
                        "cluster_id": 1,
                        "cluster_name": "es-one",
                    }
                ]
            },
        )

    @patch("apps.log_admin_resource.handlers.platform_source.TransferApi.get_data_id")
    def test_data_source_projection_drops_token_mq_and_arbitrary_configs(self, mock_api):
        mock_api.return_value = {
            "bk_data_id": 1500001,
            "bk_tenant_id": "tenant-a",
            "bk_biz_id": 2,
            "data_name": "bklog_demo",
            "token": "secret-token",
            "mq_config": {"bootstrap_servers": "kafka.example.com:9092", "auth_info": {"password": "secret"}},
            "option": {"credential": "secret"},
            "result_table_list": [{"result_table": "2_bklog.demo", "shipper_list": [{"password": "secret"}]}],
        }

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "metadata",
                "operation": "get_data_source",
                "params": {"bk_data_id": 1500001},
            }
        )

        self.assertEqual(
            result["result"],
            {
                "bk_data_id": 1500001,
                "bk_tenant_id": "tenant-a",
                "bk_biz_id": 2,
                "data_name": "bklog_demo",
            },
        )

    @patch("apps.log_admin_resource.handlers.platform_source.TransferApi.get_result_table")
    def test_result_table_projection_drops_options_and_allowlists_fields(self, mock_api):
        mock_api.return_value = {
            "table_id": "2_bklog.demo",
            "bk_tenant_id": "tenant-a",
            "bk_biz_id": 2,
            "default_storage": "elasticsearch",
            "option": {"password": "secret"},
            "query_alias_settings": {"raw": "drop-me"},
            "field_list": [
                {"field_name": "log", "field_type": "string", "tag": "dimension", "raw": "drop-me"},
                "malformed",
            ],
        }

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "metadata",
                "operation": "get_result_table",
                "params": {"result_table_id": "2_bklog.demo"},
            }
        )

        self.assertEqual(
            result["result"],
            {
                "table_id": "2_bklog.demo",
                "bk_tenant_id": "tenant-a",
                "bk_biz_id": 2,
                "default_storage": "elasticsearch",
                "field_list": [{"field_name": "log", "field_type": "string", "tag": "dimension"}],
            },
        )

    @patch("apps.log_admin_resource.handlers.platform_source.TransferApi.get_result_table_storage_status")
    def test_storage_status_projection_keeps_runtime_evidence_without_raw_provider_fields(self, mock_api):
        mock_api.return_value = {
            "items": [
                {
                    "table_id": "2_bklog.demo",
                    "data": {
                        "result_table": {
                            "table_id": "2_bklog.demo",
                            "default_storage": "elasticsearch",
                            "creator": "drop-me",
                        },
                        "storage_configs": {
                            "elasticsearch": {
                                "table_id": "2_bklog.demo",
                                "storage_cluster_id": 11,
                                "retention": 7,
                                "index_settings": {"secret": "drop-me"},
                            },
                            "kafka": {"bootstrap_servers": "drop-me"},
                        },
                        "segments": [
                            {"id": 1, "cluster_id": 11, "storage_type": "elasticsearch", "creator": "drop-me"},
                            "malformed",
                        ],
                        "cluster_results": {
                            "11": {
                                "storage_type": "elasticsearch",
                                "cluster": {
                                    "cluster_id": 11,
                                    "cluster_name": "es-one",
                                    "domain_name": "drop-me",
                                },
                                "connectivity": {"is_connected": True, "error": "drop-me"},
                                "runtime": {
                                    "indices": {
                                        "items": [
                                            {
                                                "index": "2_bklog_demo_20260830_0",
                                                "health": "green",
                                                "docs_count": 3,
                                                "raw": "drop-me",
                                            },
                                            "malformed",
                                        ]
                                    },
                                    "raw_backend_response": {"secret": "drop-me"},
                                },
                                "warnings": [{"code": "DEGRADED", "message": "raw provider warning"}],
                                "errors": ["raw provider error"],
                            },
                            "malformed": "drop-me",
                        },
                        "warnings": [{"code": "PARTIAL", "message": "raw provider warning"}],
                        "errors": [{"message": "raw provider error", "password": "secret"}],
                    },
                    "error": None,
                },
                {
                    "table_id": "missing",
                    "data": None,
                    "error": {"code": "RESULT_TABLE_NOT_FOUND", "message": "raw provider error"},
                },
                "malformed",
            ]
        }

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "metadata",
                "operation": "get_result_table_storage_status",
                "params": {"result_table_ids": ["2_bklog.demo", "missing"]},
            }
        )["result"]

        first = result["items"][0]
        self.assertEqual(
            first["data"]["storage_configs"],
            {"elasticsearch": {"table_id": "2_bklog.demo", "storage_cluster_id": 11, "retention": 7}},
        )
        self.assertEqual(first["data"]["segments"], [{"id": 1, "cluster_id": 11, "storage_type": "elasticsearch"}])
        cluster = first["data"]["cluster_results"]["11"]
        self.assertEqual(cluster["cluster"], {"cluster_id": 11, "cluster_name": "es-one"})
        self.assertEqual(
            cluster["runtime"]["indices"]["items"],
            [{"index": "2_bklog_demo_20260830_0", "health": "green", "docs_count": 3}],
        )
        self.assertEqual(cluster["warnings"][0]["message"], "metadata storage status warning")
        self.assertEqual(cluster["errors"][0]["code"], "METADATA_STATUS_ERROR")
        self.assertEqual(result["items"][1]["error"]["message"], "metadata storage status query failed")
        self.assertNotIn("raw provider", str(result))
        self.assertNotIn("drop-me", str(result))
        self.assertNotIn("secret", str(result))

    @patch("apps.log_admin_resource.handlers.platform_source.TransferApi.get_cluster_info")
    def test_storage_cluster_projection_drops_endpoints_auth_and_certificates(self, mock_api):
        mock_api.return_value = [
            {
                "cluster_type": "elasticsearch",
                "auth_info": {"username": "admin", "password": "secret"},
                "cluster_config": {
                    "cluster_id": 11,
                    "cluster_name": "es-one",
                    "display_name": "ES One",
                    "version": "7.10",
                    "registered_system": "bklog",
                    "domain_name": "secret.example.com",
                    "port": 9200,
                    "schema": "https",
                    "raw_ssl_certificate": "secret-certificate",
                    "custom_option": {"admin": ["operator"]},
                },
            },
            "malformed",
        ]

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "metadata",
                "operation": "get_storage_cluster",
                "params": {"cluster_id": 11},
            }
        )

        self.assertEqual(
            result["result"],
            [
                {
                    "cluster_type": "elasticsearch",
                    "cluster_id": 11,
                    "cluster_name": "es-one",
                    "display_name": "ES One",
                    "version": "7.10",
                    "registered_system": "bklog",
                }
            ],
        )

    @patch("apps.log_admin_resource.handlers.platform_source.TransferApi.get_cluster_status")
    def test_storage_cluster_status_projection_excludes_broker_url_node_and_raw_error(self, mock_api):
        mock_api.return_value = [
            {
                "cluster_id": 11,
                "cluster_type": "kafka",
                "status": "available",
                "is_connected": True,
                "is_available": True,
                "nodes": {"total": 3, "available": 3, "items": [{"ip": "secret"}]},
                "capacity": {"total_bytes": 10, "used_bytes": 2, "raw": "drop-me"},
                "details": {
                    "broker_count": 3,
                    "topic_count": 20,
                    "bootstrap_servers": "secret.example.com:9092",
                    "url": "https://secret.example.com",
                    "response": "drop-me",
                    "node_details": [{"ip": "secret"}],
                },
                "error": {"code": "PROBE_WARNING", "message": "raw provider error"},
            },
            "malformed",
        ]

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "metadata",
                "operation": "get_storage_cluster_status",
                "params": {"bk_biz_id": 2, "cluster_ids": [11]},
            }
        )["result"]

        self.assertEqual(result[0]["nodes"], {"total": 3, "available": 3})
        self.assertEqual(result[0]["capacity"], {"total_bytes": 10, "used_bytes": 2})
        self.assertEqual(result[0]["details"], {"broker_count": 3, "topic_count": 20})
        self.assertEqual(result[0]["error"]["message"], "metadata cluster probe failed")
        self.assertNotIn("secret", str(result))
        self.assertNotIn("drop-me", str(result))

    @patch("apps.log_admin_resource.handlers.platform_source.TransferApi.list_kafka_tail")
    def test_kafka_sample_is_bounded_and_does_not_expose_credentials(self, mock_api):
        mock_api.return_value = [
            {
                "items": [
                    {
                        "data": f"line-{index} password=top-secret authorization: Bearer bearer-secret "
                        "https://user:pass@example.com/path"
                    }
                ],
                "authorization": "secret",
            }
            for index in range(5)
        ]

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "metadata",
                "operation": "kafka_sample",
                "params": {"bk_data_id": 1500001, "sample_limit": 2},
            }
        )

        self.assertEqual(mock_api.call_args.kwargs["params"]["namespace"], "bklog")
        self.assertEqual(result["result"]["count"], 2)
        self.assertEqual(len(result["result"]["items"]), 2)
        self.assertEqual(result["result"]["items"][0]["authorization"], "***")
        sample_text = result["result"]["items"][0]["items"][0]["data"]
        self.assertIn("line-0", sample_text)
        self.assertIn("password=***", sample_text)
        self.assertIn("authorization: ***", sample_text)
        self.assertIn("https://***:***@example.com/path", sample_text)
        self.assertNotIn("top-secret", sample_text)
        self.assertNotIn("bearer-secret", sample_text)
        self.assertNotIn("user:pass", sample_text)
        self.assertEqual(result["warnings"][0]["code"], "SAMPLE_TRUNCATED")

    @patch("apps.log_admin_resource.handlers.platform_source.TransferApi.list_kafka_tail")
    def test_kafka_sample_reports_business_time_age_and_normal_empty(self, mock_api):
        mock_api.return_value = [{"items": [{"data": '{"timestamp": "2026-08-30T00:00:00Z"}'}]}]

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "metadata",
                "operation": "kafka_sample",
                "params": {"bk_data_id": 1500001},
            }
        )

        self.assertTrue(result["result"]["has_data"])
        self.assertEqual(result["result"]["latest_business_time"], "2026-08-30T00:00:00+00:00")
        self.assertGreaterEqual(result["result"]["data_age_seconds"], 0)

        mock_api.return_value = []
        empty = query_platform_source(
            {
                "mode": "invoke",
                "domain": "metadata",
                "operation": "kafka_sample",
                "params": {"bk_data_id": 1500001},
            }
        )
        self.assertEqual(
            empty["result"],
            {"has_data": False, "count": 0, "items": [], "latest_business_time": None, "data_age_seconds": None},
        )
        self.assertEqual(empty["warnings"], [])

    @patch("apps.log_admin_resource.handlers.platform_source.CCApi.list_hosts_without_biz")
    def test_resolve_host_uses_exact_ipv6_filter_and_reports_ambiguity(self, mock_api):
        mock_api.return_value = {
            "count": 2,
            "info": [
                {"bk_host_id": 1, "bk_biz_id": 2, "bk_host_innerip_v6": "2001:db8::1"},
                {"bk_host_id": 2, "bk_biz_id": 3, "bk_host_innerip_v6": "2001:db8::1"},
            ],
        }

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "cmdb",
                "operation": "resolve_host",
                "params": {"ip": "2001:db8::1"},
            }
        )

        rules = mock_api.call_args.kwargs["params"]["host_property_filter"]["rules"]
        self.assertEqual(rules, [{"field": "bk_host_innerip_v6", "operator": "equal", "value": "2001:db8::1"}])
        self.assertEqual(result["result"]["resolution_status"], "ambiguous")
        self.assertIsNone(result["result"]["host"])
        self.assertEqual(result["result"]["candidate_count"], 2)

    @patch("apps.log_admin_resource.handlers.platform_source.CCApi.list_hosts_without_biz")
    def test_resolve_host_adds_exact_cloud_filter(self, mock_api):
        mock_api.return_value = {"count": 0, "info": []}

        query_platform_source(
            {
                "mode": "invoke",
                "domain": "cmdb",
                "operation": "resolve_host",
                "params": {"ip": "127.0.0.1", "bk_cloud_id": 0},
            }
        )

        rules = mock_api.call_args.kwargs["params"]["host_property_filter"]["rules"]
        self.assertEqual(rules[-1], {"field": "bk_cloud_id", "operator": "equal", "value": 0})

    @patch("apps.log_admin_resource.handlers.platform_source.get_request_tenant_id", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.platform_source.CCApi.list_hosts_without_biz")
    def test_resolve_host_carries_current_tenant_context(self, mock_api, _tenant):
        mock_api.return_value = {"count": 1, "info": [{"bk_host_id": 1, "bk_biz_id": 2}]}

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "cmdb",
                "operation": "resolve_host",
                "params": {"ip": "127.0.0.1"},
            }
        )

        self.assertEqual(result["result"]["query"]["bk_tenant_id"], "tenant-a")

    @patch("apps.log_admin_resource.handlers.platform_source.CCApi.find_host_biz_relations")
    @patch("apps.log_admin_resource.handlers.platform_source.CCApi.list_hosts_without_biz")
    def test_resolve_host_enriches_business_from_host_relation(self, mock_hosts, mock_relations):
        mock_hosts.return_value = {
            "count": 1,
            "info": [{"bk_host_id": 101, "bk_host_innerip": "127.0.0.1", "bk_cloud_id": 0}],
        }
        mock_relations.return_value = [
            {"bk_host_id": 101, "bk_biz_id": 2, "bk_module_id": 3},
            {"bk_host_id": 101, "bk_biz_id": 2, "bk_module_id": 4},
        ]

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "cmdb",
                "operation": "resolve_host",
                "params": {"ip": "127.0.0.1"},
            }
        )

        self.assertEqual(result["result"]["resolution_status"], "resolved")
        self.assertEqual(result["result"]["host"]["bk_biz_id"], 2)
        mock_relations.assert_called_once()
        self.assertEqual(mock_relations.call_args.kwargs["params"]["bk_host_id"], [101])

    @patch("apps.log_admin_resource.handlers.platform_source.CCApi.find_host_biz_relations")
    @patch("apps.log_admin_resource.handlers.platform_source.CCApi.list_hosts_without_biz")
    def test_resolve_host_reports_multiple_business_relations_as_ambiguous(self, mock_hosts, mock_relations):
        mock_hosts.return_value = {
            "count": 1,
            "info": [{"bk_host_id": 101, "bk_host_innerip": "127.0.0.1", "bk_cloud_id": 0}],
        }
        mock_relations.return_value = [
            {"bk_host_id": 101, "bk_biz_id": 2},
            {"bk_host_id": 101, "bk_biz_id": 3},
        ]

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "cmdb",
                "operation": "resolve_host",
                "params": {"ip": "127.0.0.1"},
            }
        )

        self.assertEqual(result["result"]["resolution_status"], "ambiguous")
        self.assertIsNone(result["result"]["host"])
        self.assertEqual([item["bk_biz_id"] for item in result["result"]["candidates"]], [2, 3])

    @patch("apps.log_admin_resource.handlers.platform_source.CCApi.list_hosts_without_biz")
    def test_resolve_host_never_calls_cmdb_for_invalid_ip(self, mock_api):
        with self.assertRaises(PlatformSourceError) as raised:
            query_platform_source(
                {
                    "mode": "invoke",
                    "domain": "cmdb",
                    "operation": "resolve_host",
                    "params": {"ip": "not-an-ip"},
                }
            )

        self.assertEqual(raised.exception.code, "INVALID_ARGUMENT")
        mock_api.assert_not_called()

    @patch("apps.log_admin_resource.handlers.platform_source.TransferApi.get_data_id")
    def test_provider_error_is_logged_but_not_returned_to_caller(self, mock_api):
        mock_api.side_effect = RuntimeError("upstream password=should-not-leak")

        with self.assertRaises(PlatformSourceError) as raised:
            query_platform_source(
                {
                    "mode": "invoke",
                    "domain": "metadata",
                    "operation": "get_data_source",
                    "params": {"bk_data_id": 1},
                }
            )

        self.assertEqual(raised.exception.code, "PROVIDER_UNAVAILABLE")
        self.assertNotIn("password", raised.exception.message)

    @patch("apps.log_admin_resource.handlers.platform_source.TransferApi.get_data_id")
    def test_provider_timeout_has_distinct_stable_error(self, mock_api):
        mock_api.side_effect = TimeoutError("provider timed out")

        with self.assertRaises(PlatformSourceError) as raised:
            query_platform_source(
                {
                    "mode": "invoke",
                    "domain": "metadata",
                    "operation": "get_data_source",
                    "params": {"bk_data_id": 1},
                }
            )

        self.assertEqual(raised.exception.code, "PROVIDER_TIMEOUT")

    @patch("apps.log_admin_resource.handlers.platform_source.MAX_RESPONSE_BYTES", 64)
    @patch("apps.log_admin_resource.handlers.platform_source.TransferApi.get_data_id")
    def test_large_projected_response_has_explicit_truncation_warning(self, mock_api):
        mock_api.return_value = {"data_name": "x" * 1000}

        result = query_platform_source(
            {
                "mode": "invoke",
                "domain": "metadata",
                "operation": "get_data_source",
                "params": {"bk_data_id": 1},
            }
        )

        self.assertTrue(result["truncation"]["truncated"])
        self.assertEqual(result["warnings"][0]["code"], "RESPONSE_TRUNCATED")

    @patch("apps.log_admin_resource.handlers.platform_source.OPERATIONS")
    def test_projection_failure_has_distinct_stable_error(self, mock_operations):
        from apps.log_admin_resource.handlers.platform_source import OperationSpec

        spec = OperationSpec(
            "metadata",
            "broken",
            "broken projection",
            {"type": "object", "properties": {}, "additionalProperties": False},
            {},
            lambda _params: {"ok": True},
            lambda _raw, _params: (_ for _ in ()).throw(RuntimeError("projection secret")),
        )
        mock_operations.__iter__.side_effect = None
        mock_operations.values.return_value = [spec]
        mock_operations.get.side_effect = lambda key: spec if key == ("metadata", "broken") else None

        with self.assertRaises(PlatformSourceError) as raised:
            query_platform_source({"mode": "invoke", "domain": "metadata", "operation": "broken", "params": {}})

        self.assertEqual(raised.exception.code, "RESPONSE_PROJECTION_FAILED")

    def test_kafka_time_helpers_cover_malformed_rows_and_timezone_boundaries(self):
        self.assertEqual(_kafka_time_row("raw"), "raw")
        self.assertEqual(
            _kafka_time_row({"items": ["raw", {"data": "not-json"}]}), {"items": ["raw", {"data": "not-json"}]}
        )
        self.assertEqual(
            _kafka_time_row({"items": [{"data": {"timestamp": 1}}]}),
            {"items": [{"data": {"timestamp": 1}}]},
        )
        self.assertIsNone(_data_age_seconds("not-a-time"))
        self.assertGreaterEqual(_data_age_seconds("2026-08-30T00:00:00"), 0)


@override_settings(
    RESOURCE_CALL_APP_CODE_WHITE_LIST=[],
)
class PlatformSourceRegistryTest(SimpleTestCase):
    def test_registry_exposes_platform_source_metadata_to_read_app(self):
        detail = AdminResourceRegistry.call(
            "__meta__",
            {"action": "detail", "target_func_name": "bklog.platform_source.query"},
            app_code="resource-reader",
        )

        self.assertEqual(detail["safety_level"], "inspect")
        self.assertEqual(detail["params_schema"]["properties"]["mode"]["enum"], ["discover", "describe", "invoke"])
