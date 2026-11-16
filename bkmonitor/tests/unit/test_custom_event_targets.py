"""Isolated real-module regression tests. Run directly; TARGET_TEST_BASE=1 tests bk-monitor-base."""

import copy
import importlib
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "bk-monitor-base/src"), str(ROOT / "bkmonitor"), str(ROOT / "bkmonitor/packages")]
BASE = os.environ.get("TARGET_TEST_BASE") == "1"
if BASE:
    from bk_monitor_base.django_setup import django_setup

    django_setup()
    PREFIX = "bk_monitor_base.metadata"
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    os.environ.setdefault("DJANGO_CONF_MODULE", "conf.worker.development.community")
    os.environ.setdefault("BKAPP_DEPLOY_PLATFORM", "community")
    os.environ.setdefault("USE_DYNAMIC_SETTINGS", "0")
    import django
    from django.conf import settings

    settings.INSTALLED_APPS = [*settings.INSTALLED_APPS, "monitor_web"]
    django.setup()
    PREFIX = "metadata"

storage = importlib.import_module(f"{PREFIX}.models.storage")
result_table = importlib.import_module(f"{PREFIX}.models.result_table")
resources = importlib.import_module(f"{PREFIX}.resources.resources")


class TestTargetValues(unittest.TestCase):
    def make_storage(self, version=7, indices=None):
        client = Mock()
        client.indices.get.return_value = {"events_a": {}, "events_b": {}} if indices is None else indices
        return SimpleNamespace(es_client=client, index_name="events", es_version=version)

    def test_composite_pages_exceed_terms_limit_and_preserve_cursor(self):
        instance = self.make_storage()
        calls = []
        values = [f"target-{i:05}" for i in range(11001)]

        def search(**kwargs):
            calls.append(copy.deepcopy(kwargs))
            composite = kwargs["body"]["aggs"]["field_values"]["composite"]
            offset = composite.get("after", {}).get("cursor", 0)
            page = values[offset : offset + composite["size"]]
            return {
                "aggregations": {
                    "field_values": {
                        "buckets": [{"key": {"value": value}} for value in page],
                        "after_key": {"cursor": offset + len(page)},
                    }
                }
            }

        instance.es_client.search.side_effect = search
        actual = storage.ESStorage.get_tag_values(instance, "target", 100, 200, "event_time")
        self.assertEqual(actual, values)
        self.assertEqual(len(calls), 12)
        instance.es_client.indices.get.assert_not_called()
        for call in calls:
            self.assertEqual(call["index"], "events*")
            self.assertEqual(
                call["body"]["query"], {"range": {"event_time": {"gte": 100, "lte": 200, "format": "epoch_second"}}}
            )
        self.assertEqual(calls[1]["body"]["aggs"]["field_values"]["composite"]["after"], {"cursor": 1000})

    def test_small_window_uses_one_search_even_with_after_key(self):
        instance = self.make_storage()
        instance.es_client.search.return_value = {
            "aggregations": {
                "field_values": {
                    "buckets": [{"key": {"value": "only-target"}}],
                    "after_key": {"value": "only-target"},
                }
            }
        }
        self.assertEqual(storage.ESStorage.get_tag_values(instance, "target", 1, 2), ["only-target"])
        instance.es_client.search.assert_called_once()
        instance.es_client.indices.get.assert_not_called()

    def test_no_window_keeps_per_index_results_including_duplicates(self):
        instance = self.make_storage()
        instance.es_client.search.return_value = {"aggregations": {"field_values": {"buckets": [{"key": "same"}]}}}
        self.assertEqual(storage.ESStorage.get_tag_values(instance, "target"), ["same", "same"])
        for call in instance.es_client.search.call_args_list:
            self.assertNotIn("query", call.kwargs["body"])
            self.assertEqual(call.kwargs["body"]["aggs"]["field_values"], {"terms": {"field": "target", "size": 10000}})

    def test_old_es_keeps_terms_and_filters_time(self):
        for version in (5, 6):
            instance = self.make_storage(version)
            instance.es_client.search.return_value = {"aggregations": {"field_values": {"buckets": []}}}
            self.assertEqual(storage.ESStorage.get_tag_values(instance, "target", 0, 10), [])
            for call in instance.es_client.search.call_args_list:
                self.assertIn("terms", call.kwargs["body"]["aggs"]["field_values"])
                self.assertEqual(call.kwargs["body"]["query"]["range"]["time"]["gte"], 0)

    def test_empty_indices_and_empty_results(self):
        instance = self.make_storage(indices={})
        self.assertEqual(storage.ESStorage.get_tag_values(instance, "target"), [])
        instance.es_client.search.assert_not_called()
        instance.es_client.search.return_value = {"hits": {"hits": []}}
        self.assertEqual(storage.ESStorage.get_tag_values(instance, "target", 1, 2), [])
        self.assertTrue(instance.es_client.search.call_args.kwargs["allow_no_indices"])
        instance = self.make_storage()
        instance.es_client.search.return_value = {"aggregations": {"field_values": {"buckets": []}}}
        self.assertEqual(storage.ESStorage.get_tag_values(instance, "target", 1, 2), [])

    def test_invalid_storage_time_window(self):
        for start, end in ((1, None), (None, 2), (3, 2)):
            with self.assertRaises(ValueError):
                storage.ESStorage.get_tag_values(self.make_storage(), "target", start, end)

    def test_serializers_and_resource_forwarding(self):
        serializer_classes = [resources.QueryTagValuesResource.RequestSerializer]
        if not BASE:
            from api.metadata.default import QueryTagValuesResource

            serializer_classes.append(QueryTagValuesResource.RequestSerializer)
        for cls in serializer_classes:
            for window in ({}, {"start_time": 0, "end_time": 0}, {"start_time": "1", "end_time": "2"}):
                serializer = cls(data={"table_id": "events", "tag_name": "target", "bk_tenant_id": "tenant", **window})
                self.assertTrue(serializer.is_valid(), serializer.errors)
            for window in ({"start_time": 1}, {"end_time": 2}, {"start_time": 3, "end_time": 2}):
                serializer = cls(data={"table_id": "events", "tag_name": "target", **window})
                self.assertFalse(serializer.is_valid())
        rt = Mock()
        rt.get_tag_values.return_value = ["a"]
        with patch.object(resources.models.ResultTable.objects, "get", return_value=rt):
            response = resources.QueryTagValuesResource.perform_request(
                None,
                {"bk_tenant_id": "tenant", "table_id": "events", "tag_name": "target", "start_time": 1, "end_time": 2},
            )
        self.assertEqual(response, {"tag_values": ["a"]})
        rt.get_tag_values.assert_called_once_with(tag_name="target", start_time=1, end_time=2)

    def test_result_table_uses_configured_time_field_and_tenant(self):
        es = Mock(spec=storage.ESStorage)
        instance = SimpleNamespace(real_storage_list=[es], table_id="events", bk_tenant_id="tenant")
        option = Mock()
        option.to_json.return_value = {"time_field": {"name": "event_time"}}
        with patch.object(result_table.ResultTableOption.objects, "filter") as query:
            query.return_value.first.return_value = option
            result_table.ResultTable.get_tag_values(instance, "target", 1, 2)
            query.assert_called_once_with(table_id="events", bk_tenant_id="tenant", name="time_field")
        es.get_tag_values.assert_called_once_with("target", start_time=1, end_time=2, time_field="event_time")
        other = Mock()
        instance.real_storage_list = [other]
        result_table.ResultTable.get_tag_values(instance, "target")
        other.get_tag_values.assert_called_once_with("target")
        with self.assertRaises(NotImplementedError):
            result_table.ResultTable.get_tag_values(instance, "target", 1, 2)

    @unittest.skipIf(BASE, "web only")
    def test_web_entry_forwards_window_and_deduplicates(self):
        # Load the actual module without unrelated scene resource package imports.
        path = ROOT / "bkmonitor/packages/monitor_web/scene_view/resources/custom_event.py"
        spec = importlib.util.spec_from_file_location("custom_event_target_test_module", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        resource = module.GetCustomEventTargetListResource
        serializer = resource.RequestSerializer(data={"bk_biz_id": 2, "id": 3, "start_time": "1", "end_time": "2"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        for window in ({"start_time": 1}, {"end_time": 2}, {"start_time": 3, "end_time": 2}):
            serializer_invalid = resource.RequestSerializer(data={"bk_biz_id": 2, "id": 3, **window})
            self.assertFalse(serializer_invalid.is_valid())
        config = Mock()
        config.query_target.return_value = ["a", "a"]
        with (
            patch.object(module.CustomEventGroup.objects, "get", return_value=config),
            patch.object(module, "get_request_tenant_id", return_value="tenant"),
        ):
            self.assertEqual(resource.perform_request(None, serializer.validated_data), [{"id": "a", "name": "a"}])
        config.query_target.assert_called_once_with(start_time=1, end_time=2)
        from monitor_web.models import custom_report

        with patch.object(custom_report.api.metadata, "query_tag_values", return_value={"tag_values": ["a"]}) as query:
            self.assertEqual(
                custom_report.CustomEventGroup.query_target(SimpleNamespace(table_id="events"), 1, 2), ["a"]
            )
            query.assert_called_once_with(table_id="events", tag_name="target", start_time=1, end_time=2)


if __name__ == "__main__":
    unittest.main()
