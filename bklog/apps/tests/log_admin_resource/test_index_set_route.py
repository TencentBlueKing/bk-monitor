from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.index_set_route import (
    _build_expected_routes,
    get_index_set_route_snapshot,
    get_index_set_storage_route_snapshot,
)


def build_index_set(**overrides):
    values = {
        "index_set_id": 16462,
        "query_alias_settings": [],
        "is_group": False,
        "space_uid": "bkcc__2",
        "index_set_name": "demo",
        "scenario_id": "log",
        "get_child_index_set_ids": MagicMock(return_value=[]),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@override_settings(ENVIRONMENT="bkte")
class IndexSetStorageRouteSnapshotTest(SimpleTestCase):
    def test_index_set_id_validation_rejects_bool_non_integer_and_zero(self):
        for value, message in (
            (True, "must be an integer"),
            ("invalid", "must be an integer"),
            (0, "must be positive"),
        ):
            with self.subTest(value=value), self.assertRaisesRegex(ValidationError, message):
                get_index_set_storage_route_snapshot({"index_set_id": value})

    @patch("apps.log_admin_resource.handlers.index_set_route.BaseIndexSetHandler.sync_router")
    @patch("apps.log_admin_resource.handlers.index_set_route.StorageHandler.get_result_table_indices")
    @patch("apps.log_admin_resource.handlers.index_set_route.TransferApi.get_result_table")
    @patch("apps.log_admin_resource.handlers.index_set_route.BaseIndexSetHandler.get_index_set_table_info_list")
    @patch("apps.log_admin_resource.handlers.index_set_route.get_index_set_detail")
    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSet.objects.get")
    def test_snapshot_uses_builder_and_read_apis_without_syncing_router(
        self,
        mock_get,
        mock_detail,
        mock_build,
        mock_metadata,
        mock_physical,
        mock_sync_router,
    ):
        mock_get.return_value = build_index_set()
        mock_detail.return_value = {"index_set": {"index_set_id": 16462}}
        mock_build.side_effect = [
            [
                {
                    "table_id": "bklog_index_set_16462_2_bklog_demo.__default__",
                    "cluster_id": 11,
                    "source_type": "log",
                }
            ],
            [],
        ]
        mock_metadata.return_value = {"table_id": "bklog_index_set_16462_2_bklog_demo.__default__"}
        mock_physical.return_value = [{"index": "2_bklog_demo_20260829"}]

        result = get_index_set_storage_route_snapshot({"index_set_id": 16462})

        self.assertEqual(result["source_env"], "bkte")
        self.assertEqual(result["expected_route"]["probe_status"], "success")
        route = result["expected_route"]["data"][0]
        self.assertEqual(route["data_label"], "bklog_index_set_16462")
        self.assertTrue(route["table_info"][0]["is_enable"])
        self.assertEqual(result["metadata_route"]["probe_status"], "success")
        self.assertEqual(result["physical_storage"]["probe_status"], "success")
        mock_sync_router.assert_not_called()
        called_params = mock_metadata.call_args.kwargs["params"]
        self.assertTrue(called_params["no_request"])
        self.assertEqual(called_params["table_id"], route["table_info"][0]["table_id"])

    @patch("apps.log_admin_resource.handlers.index_set_route.StorageHandler.get_result_table_indices")
    @patch("apps.log_admin_resource.handlers.index_set_route.TransferApi.get_result_table")
    @patch("apps.log_admin_resource.handlers.index_set_route.BaseIndexSetHandler.get_index_set_table_info_list")
    @patch("apps.log_admin_resource.handlers.index_set_route.get_index_set_detail")
    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSet.objects.get")
    def test_metadata_failure_does_not_hide_physical_storage(
        self, mock_get, mock_detail, mock_build, mock_metadata, mock_physical
    ):
        mock_get.return_value = build_index_set()
        mock_detail.return_value = {"index_set": {"index_set_id": 16462}}
        mock_build.side_effect = [[{"table_id": "virtual.rt"}], []]
        mock_metadata.side_effect = RuntimeError("metadata unavailable")
        mock_physical.return_value = [{"index": "physical-1"}]

        result = get_index_set_storage_route_snapshot({"index_set_id": 16462})

        metadata_item = result["metadata_route"]["data"]["items"][0]
        physical_item = result["physical_storage"]["data"]["items"][0]
        self.assertEqual(metadata_item["probe"]["probe_status"], "failed")
        self.assertEqual(physical_item["probe"]["probe_status"], "success")
        self.assertEqual(result["consistency_warnings"][0]["code"], "METADATA_ROUTE_MISSING")

    @patch("apps.log_admin_resource.handlers.index_set_route.StorageHandler.get_result_table_indices")
    @patch("apps.log_admin_resource.handlers.index_set_route.TransferApi.get_result_table")
    @patch("apps.log_admin_resource.handlers.index_set_route.BaseIndexSetHandler.get_index_set_table_info_list")
    @patch("apps.log_admin_resource.handlers.index_set_route.get_index_set_detail")
    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSet.objects.get")
    def test_empty_physical_result_is_reported_as_observed_inconsistency(
        self, mock_get, mock_detail, mock_build, mock_metadata, mock_physical
    ):
        mock_get.return_value = build_index_set()
        mock_detail.return_value = {"index_set": {"index_set_id": 16462}}
        mock_build.side_effect = [[{"table_id": "virtual.rt"}], []]
        mock_metadata.return_value = {"table_id": "virtual.rt"}
        mock_physical.return_value = []

        result = get_index_set_storage_route_snapshot({"index_set_id": 16462})

        codes = [warning["code"] for warning in result["consistency_warnings"]]
        self.assertEqual(codes, ["PHYSICAL_STORAGE_EMPTY"])

    @patch("apps.log_admin_resource.handlers.index_set_route.StorageHandler.get_result_table_indices")
    @patch("apps.log_admin_resource.handlers.index_set_route.TransferApi.get_result_table")
    @patch("apps.log_admin_resource.handlers.index_set_route.BaseIndexSetHandler.get_index_set_table_info_list")
    @patch("apps.log_admin_resource.handlers.index_set_route.get_index_set_detail")
    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSet.objects.get")
    def test_physical_failure_does_not_hide_metadata_route(
        self, mock_get, mock_detail, mock_build, mock_metadata, mock_physical
    ):
        mock_get.return_value = build_index_set()
        mock_detail.return_value = {"index_set": {"index_set_id": 16462}}
        mock_build.side_effect = [[{"table_id": "virtual.rt"}], []]
        mock_metadata.return_value = {"table_id": "virtual.rt"}
        mock_physical.side_effect = RuntimeError("storage unavailable")

        result = get_index_set_storage_route_snapshot({"index_set_id": 16462})

        self.assertEqual(result["metadata_route"]["data"]["items"][0]["probe"]["probe_status"], "success")
        self.assertEqual(result["physical_storage"]["data"]["items"][0]["probe"]["probe_status"], "failed")

    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSet.objects.get")
    def test_missing_index_set_skips_all_route_probes(self, mock_get):
        mock_get.side_effect = RuntimeError("not found")

        result = get_index_set_storage_route_snapshot({"index_set_id": 16462})

        self.assertEqual(result["database"]["probe_status"], "failed")
        self.assertEqual(result["expected_route"]["probe_status"], "skipped")
        self.assertEqual(result["metadata_route"]["probe_status"], "skipped")
        self.assertEqual(result["physical_storage"]["probe_status"], "skipped")

    @patch("apps.log_admin_resource.handlers.index_set_route._build_expected_routes")
    @patch("apps.log_admin_resource.handlers.index_set_route.get_index_set_detail")
    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSet.objects.get")
    def test_expected_route_failure_skips_dependent_probes(self, mock_get, mock_detail, mock_expected):
        mock_get.return_value = build_index_set()
        mock_detail.return_value = {"index_set": {"index_set_id": 16462}}
        mock_expected.side_effect = RuntimeError("builder unavailable")

        result = get_index_set_storage_route_snapshot({"index_set_id": 16462})

        self.assertEqual(result["database"]["probe_status"], "success")
        self.assertEqual(result["expected_route"]["probe_status"], "failed")
        self.assertEqual(result["metadata_route"]["probe_status"], "skipped")

    @patch("apps.log_admin_resource.handlers.index_set_route.BaseIndexSetHandler.get_index_set_table_info_list")
    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSet.objects.filter")
    def test_group_route_uses_parent_index_set_for_each_child(self, mock_filter, mock_build):
        child_one = build_index_set(index_set_id=1)
        child_two = build_index_set(index_set_id=2)
        parent = build_index_set(
            index_set_id=99,
            is_group=True,
            get_child_index_set_ids=MagicMock(return_value=[2, 1]),
        )
        mock_filter.return_value = [child_one, child_two]
        mock_build.side_effect = [
            [{"table_id": "parent.child-2"}],
            [{"table_id": "parent.child-1"}],
            [],
            [],
        ]

        routes = _build_expected_routes(parent)

        self.assertEqual([item["table_id"] for item in routes[0]["table_info"]], ["parent.child-2", "parent.child-1"])
        first_call = mock_build.call_args_list[0].kwargs
        self.assertEqual(first_call["index_set"].index_set_id, 2)
        self.assertIs(first_call["parent_index_set"], parent)

    @patch("apps.log_admin_resource.handlers.index_set_route.BaseIndexSetHandler.get_index_set_table_info_list")
    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSet.objects.filter")
    def test_group_route_skips_missing_child_record(self, mock_filter, mock_build):
        child = build_index_set(index_set_id=1)
        parent = build_index_set(
            index_set_id=99,
            is_group=True,
            get_child_index_set_ids=MagicMock(return_value=[1, 2]),
        )
        mock_filter.return_value = [child]
        mock_build.side_effect = [[{"table_id": "parent.child-1"}], []]

        routes = _build_expected_routes(parent)

        self.assertEqual([item["table_id"] for item in routes[0]["table_info"]], ["parent.child-1"])
        self.assertEqual(mock_build.call_count, 2)

    @patch("apps.log_admin_resource.handlers.index_set_route.BaseIndexSetHandler.get_index_set_table_info_list")
    @patch("apps.log_admin_resource.handlers.index_set_route.IndexSetHandler.get_rt_alias_settings")
    def test_alias_settings_are_resolved_before_route_build(self, mock_alias, mock_build):
        index_set = build_index_set(query_alias_settings=[{"field_name": "service"}])
        mock_alias.return_value = ({"virtual.rt": "alias.rt"}, [])
        mock_build.side_effect = [[{"table_id": "virtual.rt"}], []]

        _build_expected_routes(index_set)

        mock_alias.assert_called_once_with(index_set.index_set_id, index_set.query_alias_settings)
        self.assertEqual(mock_build.call_args_list[0].kwargs["rt_alias_mappings"], {"virtual.rt": "alias.rt"})

    @patch("apps.log_admin_resource.handlers.index_set_route.BaseIndexSetHandler.get_index_set_table_info_list")
    def test_route_builder_explicitly_truncates_more_than_one_hundred_tables(self, mock_build):
        mock_build.return_value = [{"table_id": f"virtual.{index}"} for index in range(101)]

        routes = _build_expected_routes(build_index_set())

        self.assertTrue(routes[0]["truncated"])
        self.assertEqual(routes[0]["original_table_count"], 101)
        self.assertEqual(routes[0]["returned_table_count"], 100)


def runtime_item(table_id, storage_type="elasticsearch", cluster_id=11, **overrides):
    item = {
        "table_id": table_id,
        "error": None,
        "data": {
            "result_table": {"default_storage": storage_type},
            "storage_configs": {storage_type: {"storage_cluster_id": cluster_id}},
            "cluster_results": {str(cluster_id): {"runtime": {}, "warnings": [], "errors": []}},
        },
    }
    item.update(overrides)
    return item


@override_settings(ENVIRONMENT="bkte")
class IndexSetRouteSnapshotTest(SimpleTestCase):
    def _snapshot(self, expected, runtime):
        with (
            patch(
                "apps.log_admin_resource.handlers.index_set_route.get_request_tenant_id",
                return_value="tenant-a",
            ),
            patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSet.objects.get") as mock_get,
            patch("apps.log_admin_resource.handlers.index_set_route.get_index_set_detail") as mock_detail,
            patch("apps.log_admin_resource.handlers.index_set_route._build_expected_routes") as mock_expected,
            patch(
                "apps.log_admin_resource.handlers.index_set_route.TransferApi.get_result_table_storage_status"
            ) as mock_runtime,
        ):
            mock_get.return_value = build_index_set()
            mock_detail.return_value = {"index_set": {"index_set_id": 16462}}
            mock_expected.return_value = expected
            mock_runtime.return_value = runtime
            result = get_index_set_route_snapshot({"index_set_id": 16462})
        return result, mock_runtime

    def test_es_route_is_consistent_and_uses_monitor_runtime_api(self):
        expected = [
            {
                "data_label": "bklog_index_set_16462",
                "route_kind": "default",
                "table_info": [{"table_id": "virtual.es", "cluster_id": 11, "is_enable": True}],
                "original_table_count": 1,
                "truncated": False,
            }
        ]

        result, mock_runtime = self._snapshot(expected, {"items": [runtime_item("virtual.es")]})

        self.assertEqual(result["status"], "consistent")
        self.assertEqual(result["routes"][0]["status"], "consistent")
        mock_runtime.assert_called_once_with(
            params={"table_ids": ["virtual.es"], "no_request": True},
            timeout=10,
            request_cookies=False,
            bk_tenant_id="tenant-a",
        )
        self.assertEqual(result["bk_tenant_id"], "tenant-a")

    def test_es_and_manual_doris_analysis_routes_are_compared_independently(self):
        expected = [
            {
                "data_label": "bklog_index_set_16462",
                "route_kind": "default",
                "table_info": [{"table_id": "virtual.es", "cluster_id": 11}],
                "original_table_count": 1,
                "truncated": False,
            },
            {
                "data_label": "bklog_index_set_16462_analysis",
                "route_kind": "analysis",
                "table_info": [{"table_id": "virtual.doris", "storage_type": "doris", "cluster_id": 22}],
                "original_table_count": 1,
                "truncated": False,
            },
        ]
        runtime = {"items": [runtime_item("virtual.es"), runtime_item("virtual.doris", "doris", 22)]}

        result, _ = self._snapshot(expected, runtime)

        self.assertEqual(result["status"], "consistent")
        self.assertEqual(
            [(route["route_kind"], route["status"]) for route in result["routes"]],
            [("default", "consistent"), ("analysis", "consistent")],
        )

    def test_route_mismatch_preserves_expected_and_actual_evidence(self):
        expected = [
            {
                "data_label": "bklog_index_set_16462",
                "route_kind": "default",
                "table_info": [{"table_id": "virtual.es", "cluster_id": 11}],
                "original_table_count": 1,
                "truncated": False,
            }
        ]

        result, _ = self._snapshot(expected, {"items": [runtime_item("virtual.es", cluster_id=12)]})

        route = result["routes"][0]
        self.assertEqual(result["status"], "route_mismatch")
        self.assertEqual(route["expected"]["cluster_id"], 11)
        self.assertEqual(route["actual"]["data"]["storage_configs"]["elasticsearch"]["storage_cluster_id"], 12)
        self.assertEqual(route["warnings"][0]["code"], "ROUTE_MISMATCH")

    def test_missing_runtime_item_is_route_missing(self):
        expected = [
            {
                "data_label": "bklog_index_set_16462",
                "route_kind": "default",
                "table_info": [{"table_id": "virtual.es", "cluster_id": 11}],
                "original_table_count": 1,
                "truncated": False,
            }
        ]

        result, _ = self._snapshot(expected, {"items": []})

        self.assertEqual(result["status"], "route_missing")
        self.assertEqual(result["routes"][0]["warnings"][0]["code"], "RUNTIME_ROUTE_MISSING")

    def test_non_object_runtime_response_is_bounded_as_unavailable_evidence(self):
        expected = [
            {
                "data_label": "bklog_index_set_16462",
                "route_kind": "default",
                "table_info": [{"table_id": "virtual.es", "cluster_id": 11}],
                "original_table_count": 1,
                "truncated": False,
            }
        ]

        result, _ = self._snapshot(expected, ["unexpected-response"])

        self.assertEqual(result["runtime_route"]["data"], ["unexpected-response"])
        self.assertEqual(result["status"], "route_missing")

        result, _ = self._snapshot(expected, {"items": "unexpected-response"})

        self.assertEqual(result["runtime_route"]["data"], {"items": "unexpected-response"})
        self.assertEqual(result["status"], "route_missing")

    def test_monitor_runtime_failure_marks_each_route_unavailable(self):
        expected = [
            {
                "data_label": "bklog_index_set_16462",
                "route_kind": "default",
                "table_info": [{"table_id": "virtual.es", "cluster_id": 11}],
                "original_table_count": 1,
                "truncated": False,
            }
        ]
        with (
            patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSet.objects.get") as mock_get,
            patch("apps.log_admin_resource.handlers.index_set_route.get_index_set_detail") as mock_detail,
            patch("apps.log_admin_resource.handlers.index_set_route._build_expected_routes") as mock_expected,
            patch(
                "apps.log_admin_resource.handlers.index_set_route.TransferApi.get_result_table_storage_status"
            ) as mock_runtime,
        ):
            mock_get.return_value = build_index_set()
            mock_detail.return_value = {}
            mock_expected.return_value = expected
            mock_runtime.side_effect = RuntimeError("monitor unavailable token=must-not-leak")

            result = get_index_set_route_snapshot({"index_set_id": 16462})

        self.assertEqual(result["status"], "runtime_unavailable")
        self.assertEqual(result["runtime_route"]["probe_status"], "failed")
        self.assertIsNone(result["runtime_route"]["error"]["upstream_message"])
        self.assertEqual(result["routes"][0]["errors"][0]["code"], "RUNTIME_PROVIDER_UNAVAILABLE")
        self.assertNotIn("must-not-leak", str(result))

    @patch("apps.log_admin_resource.handlers.index_set_route.TransferApi.get_result_table_storage_status")
    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSet.objects.filter")
    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSetData.objects.filter")
    def test_result_table_ambiguity_returns_candidates_without_runtime_call(
        self, mock_data_filter, mock_index_filter, mock_runtime
    ):
        mock_data_filter.return_value.values_list.return_value = [1, 2]
        mock_index_filter.return_value.order_by.return_value = [
            build_index_set(index_set_id=1, index_set_name="one"),
            build_index_set(index_set_id=2, index_set_name="two"),
        ]

        result = get_index_set_route_snapshot({"result_table_id": "2_bklog.demo"})

        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(result["resolution"]["candidate_count"], 2)
        mock_runtime.assert_not_called()

    @patch("apps.log_admin_resource.handlers.index_set_route.TransferApi.get_result_table_storage_status")
    @patch("apps.log_admin_resource.handlers.index_set_route._build_expected_routes")
    @patch("apps.log_admin_resource.handlers.index_set_route.get_index_set_detail")
    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSet.objects.filter")
    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSetData.objects.filter")
    def test_unique_result_table_resolves_to_same_snapshot_path(
        self, mock_data_filter, mock_index_filter, mock_detail, mock_expected, mock_runtime
    ):
        index_set = build_index_set()
        mock_data_filter.return_value.values_list.return_value = [16462]
        mock_index_filter.return_value.order_by.return_value = [index_set]
        mock_detail.return_value = {}
        mock_expected.return_value = []

        result = get_index_set_route_snapshot({"result_table_id": "2_bklog.demo"})

        self.assertEqual(result["resolution"]["status"], "resolved")
        self.assertEqual(result["index_set_id"], 16462)
        self.assertEqual(result["status"], "route_missing")
        mock_expected.assert_called_once_with(index_set)
        mock_runtime.assert_not_called()

    def test_exactly_one_lookup_key_is_required(self):
        for params in ({}, {"index_set_id": 1, "result_table_id": "2_bklog.demo"}):
            with self.subTest(params=params), self.assertRaisesRegex(ValidationError, "exactly one"):
                get_index_set_route_snapshot(params)

    @patch("apps.log_admin_resource.handlers.index_set_route.TransferApi.get_result_table_storage_status")
    @patch("apps.log_admin_resource.handlers.index_set_route._build_expected_routes")
    @patch("apps.log_admin_resource.handlers.index_set_route.get_index_set_detail")
    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSet.objects.get")
    def test_database_failure_does_not_block_runtime_comparison(
        self, mock_get, mock_detail, mock_expected, mock_runtime
    ):
        mock_get.return_value = build_index_set()
        mock_detail.side_effect = RuntimeError("database detail unavailable")
        mock_expected.return_value = [
            {
                "data_label": "bklog_index_set_16462",
                "route_kind": "default",
                "table_info": [{"table_id": "virtual.es", "cluster_id": 11}],
            }
        ]
        mock_runtime.return_value = {"items": [runtime_item("virtual.es")]}

        result = get_index_set_route_snapshot({"index_set_id": 16462})

        self.assertEqual(result["database"]["probe_status"], "failed")
        self.assertEqual(result["status"], "consistent")

    @patch("apps.log_admin_resource.handlers.index_set_route._build_expected_routes")
    @patch("apps.log_admin_resource.handlers.index_set_route.get_index_set_detail", return_value={})
    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSet.objects.get")
    def test_route_builder_failure_is_runtime_unavailable(self, mock_get, _detail, mock_expected):
        mock_get.return_value = build_index_set()
        mock_expected.side_effect = RuntimeError("builder unavailable")

        result = get_index_set_route_snapshot({"index_set_id": 16462})

        self.assertEqual(result["status"], "runtime_unavailable")
        self.assertEqual(result["expected_route"]["probe_status"], "failed")

    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSet.objects.get")
    def test_missing_index_set_is_route_missing(self, mock_get):
        from apps.log_search.models import LogIndexSet

        mock_get.side_effect = LogIndexSet.DoesNotExist

        result = get_index_set_route_snapshot({"index_set_id": 999})

        self.assertEqual(result["status"], "route_missing")
        self.assertEqual(result["warnings"][0]["code"], "INDEX_SET_NOT_FOUND")

    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSet.objects.filter")
    @patch("apps.log_admin_resource.handlers.index_set_route.LogIndexSetData.objects.filter")
    def test_result_table_not_found_and_invalid_values_are_explicit(self, mock_data_filter, mock_index_filter):
        mock_data_filter.return_value.values_list.return_value = []
        mock_index_filter.return_value.order_by.return_value = []

        missing = get_index_set_route_snapshot({"result_table_id": "2_bklog.missing"})

        self.assertEqual(missing["status"], "route_missing")
        self.assertEqual(missing["warnings"][0]["code"], "RESULT_TABLE_ROUTE_NOT_FOUND")
        with self.assertRaisesRegex(ValidationError, "exactly one"):
            get_index_set_route_snapshot({"result_table_id": ""})
        for value in ("   ", 123):
            with self.subTest(value=value), self.assertRaisesRegex(ValidationError, "non-empty string"):
                get_index_set_route_snapshot({"result_table_id": value})

    def test_runtime_item_error_storage_missing_default_inference_and_runtime_skip(self):
        expected = [
            {
                "data_label": "bklog_index_set_16462",
                "route_kind": "default",
                "table_info": [
                    {"table_id": "error", "cluster_id": 11},
                    {"table_id": "string-error", "cluster_id": 11},
                    {"table_id": "missing", "cluster_id": 11},
                    {"table_id": "inferred", "cluster_id": 11},
                    {"table_id": "skipped", "cluster_id": 11},
                ],
            }
        ]
        inferred = runtime_item("inferred")
        inferred["data"]["result_table"]["default_storage"] = None
        skipped = runtime_item("skipped")
        skipped["data"]["cluster_results"]["11"]["runtime_skipped"] = True
        skipped["data"]["cluster_results"]["invalid"] = "unexpected-result"
        runtime = {
            "items": [
                {
                    "table_id": "error",
                    "error": {
                        "code": "UPSTREAM_ERROR",
                        "message": "token=must-not-leak",
                        "request_id": "request-1",
                    },
                },
                {"table_id": "string-error", "error": "upstream token=must-not-leak"},
                runtime_item("missing", storage_type="doris", cluster_id=22),
                inferred,
                skipped,
            ]
        }

        result, _ = self._snapshot(expected, runtime)

        statuses = {route["table_id"]: route["status"] for route in result["routes"]}
        self.assertEqual(
            statuses,
            {
                "error": "runtime_unavailable",
                "string-error": "runtime_unavailable",
                "missing": "route_missing",
                "inferred": "consistent",
                "skipped": "runtime_unavailable",
            },
        )
        error_route = next(route for route in result["routes"] if route["table_id"] == "error")
        self.assertEqual(
            error_route["errors"],
            [
                {
                    "code": "UPSTREAM_ERROR",
                    "message": "Monitor runtime route probe failed",
                    "request_id": "request-1",
                    "retryable": False,
                }
            ],
        )
        self.assertNotIn("must-not-leak", str(result))
