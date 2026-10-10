"""
Real-DB integration tests: SearchHandler desensitize for third-party ES index sets.

Covers scenario_id='es' (third-party ES) with and without desensitize config
through the legacy SearchHandler (search_handlers_esquery) _deal_query_result path.

Test strategy
  - Real LogIndexSet + LogIndexSetData + DesensitizeConfig + DesensitizeFieldConfig
    in SQLite (Django TestCase transaction isolation).
  - Only external / network dependencies are mocked:
    * request context (get_request, get_request_username, auth_info)
    * feature toggle (FeatureToggleObject.toggle)
    * CMDB host cache (CmdbHostCache.get)
    * mapping nested-field check (MappingHandlers.is_nested_field)
  - SearchHandler constructor runs with pre_check_enable=False and sort_list
    to avoid mapping_handler / PreSearchHandlers dependencies.
  - _deal_query_result is called directly with fabricated ES-hit-shaped dicts.
"""

from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from apps.log_desensitize.models import DesensitizeConfig, DesensitizeFieldConfig
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.models import LogIndexSet, LogIndexSetData

SPACE_UID = "bkcc__2"

BASE_SEARCH_DICT = {
    "bk_biz_id": 2,
    "keyword": "test",
    "start_time": "2026-09-27 00:00:00",
    "end_time": "2026-09-28 00:00:00",
    "sort_list": [],
    "size": 50,
}

# ---- desensitize payload helpers -------------------------------------------

MASK_CONFIG = {
    "field_name": "message",
    "rule_id": 0,
    "operator": "mask_shield",
    "params": {"preserve_head": 2, "preserve_tail": 2, "replace_mark": "*"},
    "match_pattern": ".*",
    "sort_index": 0,
}

TEXT_REPLACE_CONFIG = {
    "field_name": "log",
    "rule_id": 0,
    "operator": "text_replace",
    "params": {"template_string": "[FILTERED]"},
    "match_pattern": ".*",
    "sort_index": 0,
}


def fake_hits(*, message="plain message", log="plain log"):
    """Return a result_dict shaped like a legacy ES query response."""
    return {
        "took": 10,
        "hits": {
            "total": 1,
            "hits": [
                {
                    "_index": "v2_2_bklog_test_es_20260927_0",
                    "_source": {
                        "dtEventTimeStamp": 1727452800000,
                        "message": message,
                        "log": log,
                    },
                }
            ],
        },
    }


@override_settings(ESQUERY_WHITE_LIST=["bk_log"])
class TestSearchHandlerDesensitize(TestCase):
    """
    SearchHandler desensitize with scenario_id='es'.

    ESQUERY_WHITE_LIST contains the mocked caller app code so that an explicit
    is_desensitize=False is honoured (non-whitelisted callers are force-masked
    by _init_desensitize, which is tested implicitly elsewhere).
    """

    def setUp(self):
        # Real model records (shared across all test methods)
        self.index_set = LogIndexSet.objects.create(
            index_set_name="test-es-desensitize-search",
            space_uid=SPACE_UID,
            scenario_id="es",
            storage_cluster_id=1,
            time_field="dtEventTimeStamp",
            time_field_type="date",
            time_field_unit="millisecond",
        )
        self.index_set_id = self.index_set.index_set_id

        LogIndexSetData.objects.create(
            index_set_id=self.index_set_id,
            bk_biz_id=2,
            result_table_id="2_bklog.test_es_desensitize",
            apply_status="normal",
            scenario_id="es",
            storage_cluster_id=1,
            time_field="dtEventTimeStamp",
        )

        self._clean()

    def tearDown(self):
        self._clean()

    # ---- helpers -----------------------------------------------------------

    def _clean(self):
        DesensitizeConfig.objects.filter(index_set_id=self.index_set_id).delete()
        DesensitizeFieldConfig.objects.filter(index_set_id=self.index_set_id).delete()

    def _put_config(self, field_configs, text_fields=None):
        """Create a desensitize config + field configs in DB."""
        DesensitizeConfig.objects.create(
            index_set_id=self.index_set_id,
            text_fields=text_fields or [],
        )
        for fc in field_configs:
            DesensitizeFieldConfig.objects.create(
                index_set_id=self.index_set_id,
                field_name=fc["field_name"],
                rule_id=fc.get("rule_id", 0),
                operator=fc["operator"],
                params=fc.get("params", {}),
                match_pattern=fc.get("match_pattern", ""),
                sort_index=fc.get("sort_index", 0),
            )

    def _build_handler(self, search_dict_extra=None, **constructor_kw):
        """Build a SearchHandler with request-context mocks.

        ``search_dict_extra`` is merged into the base search dict.
        Extra keyword arguments (e.g. ``export_fields=[...]``) are
        forwarded to the SearchHandler constructor.
        """
        sd = dict(BASE_SEARCH_DICT)
        sd.update(search_dict_extra or {})

        with (
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.get_request",
                return_value=Mock(),
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.get_request_username",
                return_value="test_user",
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.get_request_external_username",
                return_value=None,
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.Permission.get_auth_info",
                return_value={"bk_app_code": "bk_log", "bk_username": "test_user"},
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.FeatureToggleObject.toggle",
                return_value=None,
            ),
            patch(
                "apps.log_search.handlers.search.mapping_handlers.MappingHandlers.is_nested_field",
                return_value=False,
            ),
            patch(
                "apps.utils.core.cache.cmdb_host.CmdbHostCache.get",
                return_value={},
            ),
        ):
            return SearchHandler(
                index_set_id=self.index_set_id,
                search_dict=sd,
                pre_check_enable=False,
                **constructor_kw,
            )

    # ------------------------------------------------------------------
    # Test: with desensitize config → fields are masked
    # ------------------------------------------------------------------

    def test_with_config_message_desensitized(self):
        """scenario_id='es' + desensitize config: message field is masked."""
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler()
        # "Hello World1234" = 15 chars; mask_shield(2,2) → "He" + 11×"*" + "34"
        result = handler._deal_query_result(
            fake_hits(message="Hello World1234")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "He***********34")
        self.assertEqual(logs[0]["__index_set_id__"], self.index_set_id)

    # ------------------------------------------------------------------
    # Test: without desensitize config → plain text
    # ------------------------------------------------------------------

    def test_without_config_message_unchanged(self):
        """scenario_id='es' + NO desensitize config: message unchanged."""
        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_hits(message="plain message content")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "plain message content")

    # ------------------------------------------------------------------
    # Test: is_desensitize=False → plain text
    # ------------------------------------------------------------------

    def test_is_desensitize_false_skips_desensitize(self):
        """is_desensitize=False on a configured index set: no masking."""
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler({"is_desensitize": False})
        result = handler._deal_query_result(
            fake_hits(message="Hello World1234")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "Hello World1234")

    # ------------------------------------------------------------------
    # Test: original_search=True → plain text
    # ------------------------------------------------------------------

    def test_original_search_short_circuits_desensitize(self):
        """original_search=True returns plain text even with config."""
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler({"original_search": True})
        result = handler._deal_query_result(
            fake_hits(message="Hello World1234")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "Hello World1234")

    # ------------------------------------------------------------------
    # Test: export_fields path with desensitize
    # ------------------------------------------------------------------

    def test_export_fields_preserves_desensitize(self):
        """
        export_fields filters origin_log_list but desensitize still applies
        to the log_list entries.
        """
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler(
            export_fields=["message", "dtEventTimeStamp"],
        )
        # Mock the fields() call inside _deal_query_result so it returns the
        # export fields as valid (avoids real mapping_handler dependency).
        with patch.object(handler, "fields", return_value={
            "fields": [{"field_name": "message"}, {"field_name": "dtEventTimeStamp"}],
        }):
            result = handler._deal_query_result(
                fake_hits(message="Hello World1234")
            )

        # origin_log_list is the export-filtered output
        logs = result["origin_log_list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "He***********34")
        # non-exported fields are removed in origin_log_list
        self.assertNotIn("log", logs[0])

    # ------------------------------------------------------------------
    # Test: text_fields — log field gets text-field desensitize
    # ------------------------------------------------------------------

    def test_text_fields_are_desensitized(self):
        """text_fields config causes the 'log' field to be masked."""
        self._put_config(
            field_configs=[TEXT_REPLACE_CONFIG],
            text_fields=["log"],
        )

        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_hits(log="sensitive data here")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["log"], "[FILTERED]")

    # ------------------------------------------------------------------
    # Test: _init_desensitize returns expected boolean
    # ------------------------------------------------------------------

    def test_init_desensitize_default_true(self):
        """Default is_desensitize is True when not specified."""
        handler = self._build_handler()
        self.assertIsInstance(handler.is_desensitize, bool)
        self.assertTrue(handler.is_desensitize)

    def test_init_desensitize_original_search_false(self):
        """original_search=True makes is_desensitize=False."""
        handler = self._build_handler({"original_search": True})
        self.assertFalse(handler.is_desensitize)

    # ------------------------------------------------------------------
    # End-to-end: IndexSetHandler (CRUD) → SearchHandler (query)
    # ------------------------------------------------------------------

    def test_end_to_end_via_index_set_handler(self):
        """
        Real CRUD through IndexSetHandler.update_or_create_desensitize_config,
        then query through SearchHandler._deal_query_result.
        Validates that the same payload saved by the config page is correctly
        applied by the search pipeline (linkage between Phase 2 CRUD tests
        and Phase 2 search tests).
        """
        from apps.log_search.handlers.index_set import IndexSetHandler

        INDEX_SET_ID = self.index_set_id

        # ---- Save config via IndexSetHandler (real production code) ----
        handler_instance = IndexSetHandler(index_set_id=INDEX_SET_ID)
        payload = {
            "field_configs": [
                {
                    "field_name": "message",
                    "rules": [
                        {
                            "operator": "mask_shield",
                            "params": {"preserve_head": 2, "preserve_tail": 2, "replace_mark": "*"},
                            "match_pattern": ".*",
                            "state": "add",
                        },
                    ],
                }
            ],
            "text_fields": [],
        }
        handler_instance.update_or_create_desensitize_config(payload)

        # ---- Verify config landed in DB ----
        self.assertEqual(
            DesensitizeConfig.objects.filter(index_set_id=INDEX_SET_ID).count(), 1
        )
        self.assertEqual(
            DesensitizeFieldConfig.objects.filter(index_set_id=INDEX_SET_ID).count(), 1
        )

        # ---- Now run SearchHandler to verify the saved config takes effect ----
        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_hits(message="Hello World1234")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # mask_shield(2, 2) on 15-char string
        self.assertEqual(logs[0]["message"], "He***********34")

    # ------------------------------------------------------------------
    # Phase 4: field selection for ES scenario (V1)
    # ------------------------------------------------------------------

    def test_fields_returns_field_type_for_es_scenario(self):
        """
        The field list built for scenario_id='es' must include a non-empty
        field_type for every entry, since the desensitize operators
        (e.g. mask_shield) are only meaningful for string/text fields.

        BkLogApi.mapping is mocked (external ES call) while all other data
        (index set, field snapshot) uses real model records.
        """
        from apps.log_search.handlers.search.mapping_handlers import MappingHandlers

        # Fabricated ES mapping response — real BkLogApi.mapping shape.
        fake_mapping = [
            {
                "2_bklog.test_es_desensitize": {
                    "mappings": {
                        "properties": {
                            "message": {"type": "text"},
                            "log": {"type": "text"},
                            "server_ip": {"type": "keyword"},
                            "dtEventTimeStamp": {"type": "date"},
                            "bytes": {"type": "long"},
                        }
                    }
                }
            }
        ]

        mapping_handlers = MappingHandlers(
            indices="2_bklog.test_es_desensitize",
            index_set_id=self.index_set_id,
            scenario_id="es",
            storage_cluster_id=1,
            time_field="dtEventTimeStamp",
            start_time="2026-09-27 00:00:00",
            end_time="2026-09-28 00:00:00",
        )

        with patch(
            "apps.log_search.handlers.search.mapping_handlers.BkLogApi.mapping",
            return_value=fake_mapping,
        ):
            fields = mapping_handlers.final_fields

        # Every field must carry a non-empty string field_type.
        self.assertGreater(len(fields), 0)
        expected_types = {
            "message": "text",
            "log": "text",
            "server_ip": "keyword",
            "dtEventTimeStamp": "date",
            "bytes": "long",
        }
        actual_types = {f["field_name"]: f["field_type"] for f in fields}
        for field_name, expected_type in expected_types.items():
            self.assertEqual(actual_types[field_name], expected_type)

        # Explicit: type must be a non-empty string for each entry.
        for field in fields:
            self.assertIsInstance(field["field_type"], str)
            self.assertNotEqual(field["field_type"], "")

    # ------------------------------------------------------------------
    # Test: scroll_search path also applies desensitize
    # ------------------------------------------------------------------

    @patch("apps.log_search.handlers.search.search_handlers_esquery.BkLogApi.scroll")
    def test_scroll_search_desensitized(self, mock_scroll):
        """
        scroll_search() with an existing scroll_id goes through
        BkLogApi.scroll → _deal_query_result.  Verify the desensitize
        transform is applied on that path too.
        """
        self._put_config(field_configs=[MASK_CONFIG])

        mock_scroll.return_value = fake_hits(message="Hello World1234")

        handler = self._build_handler({"scroll_id": "dummy_scroll_id"})
        result = handler.scroll_search()

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # mask_shield(2, 2) on 15-char string
        self.assertEqual(logs[0]["message"], "He***********34")
        self.assertEqual(logs[0]["__index_set_id__"], self.index_set_id)

        mock_scroll.assert_called_once()

    # ------------------------------------------------------------------
    # Test: collector-based (scenario_id='log') regression
    # ------------------------------------------------------------------

    def test_collector_scenario_no_regression(self):
        """
        Regression: collector-based index sets (scenario_id='log') with
        an existing desensitize config must still produce masked results.
        This ensures the ES-focused changes do not break the original path.
        """
        collector_index_set = LogIndexSet.objects.create(
            index_set_name="test-collector-desensitize",
            space_uid=SPACE_UID,
            scenario_id="log",
            collector_config_id=999,
            storage_cluster_id=1,
            time_field="dtEventTimeStamp",
            time_field_type="date",
            time_field_unit="millisecond",
        )
        collector_index_set_id = collector_index_set.index_set_id
        self.addCleanup(lambda: LogIndexSet.objects.filter(index_set_id=collector_index_set_id).delete())

        LogIndexSetData.objects.create(
            index_set_id=collector_index_set_id,
            bk_biz_id=2,
            result_table_id="2_bklog.test_collector_desensitize",
            apply_status="normal",
            scenario_id="log",
            storage_cluster_id=1,
            time_field="dtEventTimeStamp",
        )

        # Put config on the collector index set
        DesensitizeConfig.objects.create(
            index_set_id=collector_index_set_id,
            text_fields=[],
        )
        DesensitizeFieldConfig.objects.create(
            index_set_id=collector_index_set_id,
            field_name="message",
            rule_id=0,
            operator="mask_shield",
            params={"preserve_head": 2, "preserve_tail": 2, "replace_mark": "*"},
            match_pattern=".*",
            sort_index=0,
        )

        sd = dict(BASE_SEARCH_DICT)
        with (
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.SearchHandler._init_indices_str",
                return_value="2_bklog.test_collector_desensitize",
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.get_request",
                return_value=Mock(),
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.get_request_username",
                return_value="test_user",
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.get_request_external_username",
                return_value=None,
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.Permission.get_auth_info",
                return_value={"bk_app_code": "bk_log", "bk_username": "test_user"},
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.FeatureToggleObject.toggle",
                return_value=None,
            ),
            patch(
                "apps.log_search.handlers.search.mapping_handlers.MappingHandlers.is_nested_field",
                return_value=False,
            ),
            patch(
                "apps.utils.core.cache.cmdb_host.CmdbHostCache.get",
                return_value={},
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.SearchHandler.init_time_field",
                return_value=("dtEventTimeStamp", "time", "s"),
            ),
        ):
            handler = SearchHandler(
                index_set_id=collector_index_set_id,
                search_dict=sd,
                pre_check_enable=False,
            )

        result = handler._deal_query_result(fake_hits(message="Hello World1234"))

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "He***********34")

    # ------------------------------------------------------------------
    # End of #9923 test cases
    # ------------------------------------------------------------------
