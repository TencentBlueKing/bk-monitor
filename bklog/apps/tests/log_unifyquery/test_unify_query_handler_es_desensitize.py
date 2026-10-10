"""
Real-DB integration tests: UnifyQueryHandler desensitize for third-party ES
index sets.

Covers scenario_id='es' (third-party ES) with and without desensitize config
through the UnifyQueryHandler._deal_query_result path.

This is a separate file (not merged into test_unify_query_handler_desensitize.py)
to keep the existing log-scenario tests untouched.
"""

import copy
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from apps.log_desensitize.models import DesensitizeConfig, DesensitizeFieldConfig
from apps.log_search.models import LogIndexSet, LogIndexSetData
from apps.log_unifyquery.handler.base import UnifyQueryHandler

SPACE_UID = "bkcc__2"

INDEX_SET_ID = 1001

SEARCH_PARAMS = {
    "index_set_ids": [INDEX_SET_ID],
    "bk_biz_id": 2,
    "keyword": "test",
    "start_time": "2026-09-27 00:00:00",
    "end_time": "2026-09-28 00:00:00",
    "sort_list": [["dtEventTimeStamp", "desc"]],
    "size": 50,
    "search_mode": "sql",
    "is_desensitize": True,
}

MASK_CONFIG = {
    "field_name": "message",
    "rule_id": 0,
    "operator": "mask_shield",
    "params": {"preserve_head": 2, "preserve_tail": 2, "replace_mark": "*"},
    "match_pattern": ".*",
    "sort_index": 0,
}


def fake_unify_result(*, message="plain message"):
    """Return a result_dict shaped like a UnifyQuery response."""
    return {
        "total": 1,
        "took": 10,
        "list": [
            {
                "__index": "v2_2_bklog_test_es_20260927_0",
                "__doc_id": "abc123",
                "dtEventTimeStamp": 1727452800000,
                "message": message,
                "log": "plain log",
            }
        ],
    }


class TestUnifyQueryHandlerEsDesensitize(TestCase):
    """UnifyQueryHandler desensitize with scenario_id='es'."""

    def setUp(self):
        # Real model records
        self.index_set = LogIndexSet.objects.create(
            index_set_id=INDEX_SET_ID,
            index_set_name="test-es-unify-desensitize",
            space_uid=SPACE_UID,
            scenario_id="es",
            storage_cluster_id=1,
            time_field="dtEventTimeStamp",
            time_field_type="date",
            time_field_unit="millisecond",
        )

        LogIndexSetData.objects.create(
            index_set_id=INDEX_SET_ID,
            bk_biz_id=2,
            result_table_id="2_bklog.test_es_unify_desensitize",
            apply_status="normal",
            scenario_id="es",
            storage_cluster_id=1,
            time_field="dtEventTimeStamp",
        )

        self._clean()

    def tearDown(self):
        self._clean()

    def _clean(self):
        DesensitizeConfig.objects.filter(index_set_id=INDEX_SET_ID).delete()
        DesensitizeFieldConfig.objects.filter(index_set_id=INDEX_SET_ID).delete()

    def _put_config(self, field_configs, text_fields=None):
        """Create a desensitize config + field configs in DB."""
        DesensitizeConfig.objects.create(
            index_set_id=INDEX_SET_ID,
            text_fields=text_fields or [],
        )
        for fc in field_configs:
            DesensitizeFieldConfig.objects.create(
                index_set_id=INDEX_SET_ID,
                field_name=fc["field_name"],
                rule_id=fc.get("rule_id", 0),
                operator=fc["operator"],
                params=fc.get("params", {}),
                match_pattern=fc.get("match_pattern", ""),
                sort_index=fc.get("sort_index", 0),
            )

    def _build_handler(self, params_extra=None):
        """Build UnifyQueryHandler with external dependencies mocked."""
        p = copy.deepcopy(SEARCH_PARAMS)
        if params_extra:
            p.update(params_extra)

        with (
            patch.object(UnifyQueryHandler, "init_base_dict", return_value={}),
            patch(
                "apps.log_unifyquery.handler.base.get_request",
                return_value=Mock(),
            ),
            patch(
                "apps.log_unifyquery.handler.base.get_request_username",
                return_value="test_user",
            ),
            patch(
                "apps.log_unifyquery.handler.base.get_request_external_username",
                return_value=None,
            ),
            patch(
                "apps.log_search.permission.Permission.get_auth_info",
                return_value={"bk_app_code": "bk_log", "bk_username": "test_user"},
            ),
            patch(
                "apps.log_unifyquery.handler.base.FeatureToggleObject.toggle",
                return_value=None,
            ),
            patch(
                "apps.utils.core.cache.cmdb_host.CmdbHostCache.get",
                return_value={},
            ),
        ):
            return UnifyQueryHandler(p)

    # ------------------------------------------------------------------
    # Test: ES index set with config → masked
    # ------------------------------------------------------------------

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_es_with_config_message_desensitized(self):
        """scenario_id='es' + desensitize config: message masked."""
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_unify_result(message="Hello World1234")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # mask_shield(2, 2) on 15-char string
        self.assertEqual(logs[0]["message"], "He***********34")

    # ------------------------------------------------------------------
    # Test: ES index set without config → unchanged
    # ------------------------------------------------------------------

    def test_es_without_config_message_unchanged(self):
        """scenario_id='es' + NO config: message unchanged."""
        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_unify_result(message="something secret")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "something secret")

    # ------------------------------------------------------------------
    # Test: ES index set, is_desensitize=False → original (whitelisted)
    # ------------------------------------------------------------------

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_es_is_desensitize_false_skips_desensitize(self):
        """is_desensitize=False with whitelisted caller: no masking."""
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler({"is_desensitize": False})
        result = handler._deal_query_result(
            fake_unify_result(message="Hello World1234")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "Hello World1234")

    # ------------------------------------------------------------------
    # Test: original_search=True → original text
    # ------------------------------------------------------------------

    def test_es_original_search_short_circuits_desensitize(self):
        """original_search=True returns original even with config."""
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler({"original_search": True})
        result = handler._deal_query_result(
            fake_unify_result(message="Hello World1234")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "Hello World1234")

    # ------------------------------------------------------------------
    # Test: _init_desensitize returns expected bool
    # ------------------------------------------------------------------

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_es_init_desensitize_default_true(self):
        """Default is_desensitize is True for ES index set."""
        handler = self._build_handler()
        self.assertIsInstance(handler.is_desensitize, bool)
        self.assertTrue(handler.is_desensitize)

    def test_es_init_desensitize_original_search_false(self):
        """original_search=True makes is_desensitize=False."""
        handler = self._build_handler({"original_search": True})
        self.assertFalse(handler.is_desensitize)
