"""Isolated routing regressions using production methods and constructed ORM rows."""

import ast
import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[3]
TENANT = "tenant-a"
APPLICATION_LABEL = "apm_application_name"


class DatabaseError(Exception):
    pass


def _load_definitions(path, names, namespace):
    tree = ast.parse((ROOT / path).read_text())
    nodes = [node for node in tree.body if getattr(node, "name", None) in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)


def _model(rows):
    def filter_rows(**filters):
        selected = [
            row
            for row in rows
            if all(
                row.get(key[:-4]) in value if key.endswith("__in") else row.get(key) == value
                for key, value in filters.items()
            )
        ]
        query = Mock()
        query.values.side_effect = lambda *fields: [{field: row[field] for field in fields} for row in selected]
        query.values_list.side_effect = lambda field, flat: [row[field] for row in selected]
        return query

    manager = Mock()
    manager.filter.side_effect = filter_rows
    manager.annotate.return_value = manager
    return SimpleNamespace(objects=manager)


def metric_source(data_id, name="Shop-API", **changes):
    return {
        "bk_data_id": data_id,
        "app_name": name,
        "result_table_id": "apm.default",
        "shared_datasource_id": None,
        "apm_tenant_matches": True,
        "data_source_tenant_matches": True,
        **changes,
    }


class TestApmApplicationRouting(unittest.TestCase):
    def setUp(self):
        self.result_tables = []
        self.relations = []
        self.metric_sources = []
        self.metric_model = _model(self.metric_sources)
        self.application_model = SimpleNamespace(origin_objects=Mock())
        self.models = SimpleNamespace(
            ResultTable=_model(self.result_tables),
            DataSourceResultTable=_model(self.relations),
            DataSource=_model([]),
            ESStorage=_model([]),
            DorisStorage=_model([]),
            ClusterInfo=SimpleNamespace(TYPE_ES="elasticsearch", TYPE_DORIS="doris"),
        )
        self.redis = Mock()
        self.outer_ref = Mock(side_effect=lambda field: ("outer", field))
        self.namespace = {
            "models": self.models,
            "QuerySet": object,
            "ModelBase": object,
            "DEFAULT_FILTER_PAGE_SIZE": 500,
            "DatabaseError": DatabaseError,
            "Exists": Mock(side_effect=lambda query: query),
            "OuterRef": self.outer_ref,
            "get_measurement_type_by_table_id": Mock(return_value={}),
            "get_table_id_cluster_id": Mock(return_value={}),
            "get_table_info_for_influxdb_and_vm": self.storage_routes,
            "settings": SimpleNamespace(ENABLE_MULTI_TENANT_MODE=True),
            "RedisTools": self.redis,
            "RESULT_TABLE_DETAIL_KEY": "result_table_detail",
            "RESULT_TABLE_DETAIL_CHANNEL": "result_table_detail:channel",
            "logger": Mock(),
            "json": json,
        }
        _load_definitions(
            "metadata/utils/db.py",
            {"_filter_value", "filter_model_by_in_page", "filter_query_set_by_in_page"},
            self.namespace,
        )
        tree = ast.parse((ROOT / "metadata/models/space/space_table_id_redis.py").read_text())
        router_class = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        methods = {
            "_compose_metric_table_id_detail",
            "_compose_apm_application_names",
            "push_table_id_detail",
            "_write_table_id_detail",
        }
        router_class.body = [node for node in router_class.body if getattr(node, "name", None) in methods]
        exec(
            compile(ast.Module(body=[router_class], type_ignores=[]), "space_table_id_redis.py", "exec"), self.namespace
        )
        self.router = self.namespace["SpaceTableIDRedis"]()
        self.router.APM_APPLICATION_NAME_LABEL = APPLICATION_LABEL
        self.router.TABLE_ID_DETAIL_BATCH_SIZE = 500
        self.router._compose_table_id_fields = Mock(return_value={})
        self.router._compose_record_rule_table_id_detail = Mock(return_value={})
        self.router._compose_log_table_id_detail = Mock(return_value=({}, set()))
        self.apm_patch = patch.dict(
            "sys.modules",
            {"apm.models": SimpleNamespace(ApmApplication=self.application_model, MetricDataSource=self.metric_model)},
        )
        self.apm_patch.start()
        self.addCleanup(self.apm_patch.stop)

    def storage_routes(self, *, table_id_list, bk_tenant_id):
        return {
            row["table_id"]: {"storage_type": "victoria_metrics", "vm_rt": row["table_id"].replace(".", "_")}
            for row in self.result_tables
            if row["bk_tenant_id"] == bk_tenant_id and (not table_id_list or row["table_id"] in table_id_list)
        }

    def table(self, table_id, data_ids, labels=None, tenant=TENANT):
        self.result_tables.append(
            {
                "table_id": table_id,
                "bk_tenant_id": tenant,
                "schema_type": "free",
                "data_label": "apm",
                "labels": labels or {},
            }
        )
        self.relations.extend(
            {"table_id": table_id, "bk_data_id": data_id, "bk_tenant_id": tenant} for data_id in data_ids
        )

    def compose(self, table_id_list=None):
        return self.router._compose_metric_table_id_detail(bk_tenant_id=TENANT, table_id_list=table_id_list)

    def test_existing_and_independent_metric_tables_keep_raw_application_name(self):
        self.table("apm.default", [101], {"scene": "metrics"})
        self.table("apm.request_count", [101])
        self.table("apm.secondary", [102])
        self.metric_sources.extend([metric_source(101), metric_source(102)])
        result = self.compose()
        self.assertEqual(set(result), {"apm.default", "apm.request_count", "apm.secondary"})
        for detail in result.values():
            self.assertEqual(detail["labels"][APPLICATION_LABEL], "Shop-API")
        self.assertEqual(result["apm.default"]["labels"]["scene"], "metrics")

    def test_duplicate_mappings_to_same_name_are_supported(self):
        self.metric_sources.extend([metric_source(101), metric_source(101)])
        self.assertEqual(
            self.router._compose_apm_application_names(bk_tenant_id=TENANT, data_ids={101}), {101: "Shop-API"}
        )

    def test_conflicting_application_mappings_do_not_publish_single_value(self):
        self.table("apm.default", [101], {APPLICATION_LABEL: "Shop-API", "scene": "metrics"})
        self.metric_sources.extend([metric_source(101), metric_source(101, "Billing-API")])
        self.assertEqual(self.compose()["apm.default"]["labels"], {"scene": "metrics"})

    def test_unknown_or_shared_mapping_invalidates_otherwise_known_data_id(self):
        invalid_rows = [
            {"apm_tenant_matches": False},
            {"data_source_tenant_matches": False},
            {"app_name": ""},
            {"app_name": "  "},
            {"result_table_id": ""},
            {"result_table_id": "  "},
            {"shared_datasource_id": 7},
        ]
        for changes in invalid_rows:
            with self.subTest(changes=changes):
                self.metric_sources[:] = [metric_source(101), metric_source(101, **changes)]
                self.assertEqual(self.router._compose_apm_application_names(bk_tenant_id=TENANT, data_ids={101}), {})

    def test_all_data_ids_must_have_same_known_application(self):
        self.table("apm.same", [101, 102])
        self.table("apm.unknown", [101, 103])
        self.table("apm.different", [101, 104])
        self.metric_sources.extend([metric_source(101), metric_source(102), metric_source(104, "Billing-API")])
        result = self.compose()
        self.assertEqual(result["apm.same"]["labels"], {APPLICATION_LABEL: "Shop-API"})
        self.assertEqual(result["apm.unknown"]["labels"], {})
        self.assertEqual(result["apm.different"]["labels"], {})

    def test_refresh_removes_stale_label_without_mutating_stored_labels(self):
        labels = {APPLICATION_LABEL: "stale", "scene": "metrics"}
        self.table("apm.default", [101], labels)
        self.metric_sources.append(metric_source(101))
        self.assertEqual(self.compose()["apm.default"]["labels"][APPLICATION_LABEL], "Shop-API")
        self.metric_sources.clear()
        self.assertEqual(self.compose()["apm.default"]["labels"], {"scene": "metrics"})
        self.assertEqual(labels, {APPLICATION_LABEL: "stale", "scene": "metrics"})

    def test_tenant_scopes_tables_relations_and_application_join(self):
        self.table("apm.default", [101])
        self.table("apm.default", [102], tenant="tenant-b")
        self.metric_sources.extend([metric_source(101), metric_source(102, "Other-API")])
        self.assertEqual(self.compose()["apm.default"]["labels"], {APPLICATION_LABEL: "Shop-API"})
        self.application_model.origin_objects.filter.assert_called_once_with(
            bk_tenant_id=TENANT, bk_biz_id=("outer", "bk_biz_id"), app_name=("outer", "app_name")
        )
        self.metric_model.objects.filter.assert_called_once_with(bk_data_id__in=[101])
        self.models.DataSource.objects.filter.assert_called_once_with(
            bk_tenant_id=TENANT, bk_data_id=("outer", "bk_data_id")
        )

    def test_queries_are_bounded_and_empty_input_does_not_read_models(self):
        self.assertEqual(self.router._compose_apm_application_names(bk_tenant_id=TENANT, data_ids=set()), {})
        self.metric_model.objects.annotate.assert_not_called()
        self.metric_sources.extend(metric_source(data_id) for data_id in range(1, 1002))
        result = self.router._compose_apm_application_names(bk_tenant_id=TENANT, data_ids=set(range(1, 1002)))
        self.assertEqual(len(result), 1001)
        batches = [call.kwargs["bk_data_id__in"] for call in self.metric_model.objects.filter.call_args_list]
        self.assertEqual(sorted(map(len, batches)), [1, 500, 500])

    def test_full_refresh_publishes_existing_tables_without_backfill(self):
        self.table("apm.default", [101])
        self.table("apm.request_count", [101])
        self.metric_sources.append(metric_source(101))
        self.router.push_table_id_detail(bk_tenant_id=TENANT, is_publish=True)
        payload = self.redis.hmset_to_redis.call_args.args[1]
        self.assertEqual(set(payload), {"apm.default|tenant-a", "apm.request_count|tenant-a"})
        for serialized in payload.values():
            self.assertEqual(json.loads(serialized)["labels"], {APPLICATION_LABEL: "Shop-API"})
        self.redis.publish.assert_called_once_with("result_table_detail:channel", list(payload))

    def test_missing_relation_and_non_apm_table_preserve_other_labels(self):
        self.table("custom.metrics", [], {"scene": "custom", APPLICATION_LABEL: "stale"})
        self.assertEqual(self.compose()["custom.metrics"]["labels"], {"scene": "custom"})

    def test_record_rule_route_keeps_existing_override(self):
        self.table("apm.default", [101])
        self.metric_sources.append(metric_source(101))
        record_rule = {"storage_type": "victoria_metrics", "labels": {"scene": "precomputed"}}
        self.router._compose_record_rule_table_id_detail.return_value = {"apm.default": copy.deepcopy(record_rule)}
        self.assertEqual(self.compose()["apm.default"], record_rule)

    def test_application_query_failure_publishes_base_route_without_stale_label(self):
        self.table("apm.default", [101], {"scene": "metrics", APPLICATION_LABEL: "stale"})
        self.metric_model.objects.filter.side_effect = DatabaseError("database unavailable")
        self.router.push_table_id_detail(bk_tenant_id=TENANT, is_publish=True)
        payload = self.redis.hmset_to_redis.call_args.args[1]
        self.assertEqual(json.loads(payload["apm.default|tenant-a"])["labels"], {"scene": "metrics"})
        self.namespace["logger"].exception.assert_called_once()

    def test_existing_route_query_failure_still_propagates(self):
        self.table("apm.default", [101])
        self.models.ResultTable.objects.filter.side_effect = RuntimeError("database unavailable")
        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            self.router.push_table_id_detail(bk_tenant_id=TENANT, is_publish=True)
        self.redis.hmset_to_redis.assert_not_called()


if __name__ == "__main__":
    unittest.main()
