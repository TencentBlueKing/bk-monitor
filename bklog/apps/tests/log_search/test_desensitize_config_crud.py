"""
Real-DB integration tests for desensitize config CRUD on IndexSetHandler.

Covers the full lifecycle (create → retrieve → update → delete) with a
real LogIndexSet (scenario_id='es') and real database records.  No mocks,
no external API calls, no IAM dependency.

Test strategy
  LogIndexSet is created via bulk_create (bypassing the buggy save() that
  accesses self.objects on model instances).  Inline rules (operator / params
  / match_pattern directly in the request body, no rule_id) avoid any
  dependency on DesensitizeRule records.  Handler methods are called directly;
  they only do DB queries and do not invoke IAM or external services.
"""

from django.test import TestCase

from apps.log_desensitize.models import DesensitizeConfig, DesensitizeFieldConfig
from apps.log_search.handlers.index_set import IndexSetHandler
from apps.log_search.models import LogIndexSet

SPACE_UID = "bkcc__2"

_DESENSITIZE_PAYLOAD = {
    "field_configs": [
        {
            "field_name": "message",
            "rules": [
                {
                    "operator": "mask_shield",
                    "params": {
                        "preserve_head": 2,
                        "preserve_tail": 2,
                        "replace_mark": "*",
                    },
                    "match_pattern": ".*",
                    "state": "add",
                },
            ],
        }
    ],
    "text_fields": ["log"],
}

_UPDATED_PAYLOAD = {
    "field_configs": [
        {
            "field_name": "server_id",
            "rules": [
                {
                    "operator": "text_replace",
                    "params": {"template_string": "[FILTERED]"},
                    "match_pattern": ".*",
                    "state": "add",
                },
            ],
        }
    ],
    "text_fields": [],
}


class DesensitizeConfigCRUDTest(TestCase):
    """Full CRUD lifecycle for desensitize config on a third-party ES index set."""

    def setUp(self):
        self.index_set = LogIndexSet.objects.create(
            index_set_name="test-desensitize-es-1010158081138539923",
            space_uid=SPACE_UID,
            scenario_id="es",
            storage_cluster_id=1,
        )
        self.handler = IndexSetHandler(index_set_id=self.index_set.index_set_id)
        self._clean()

    def tearDown(self):
        self._clean()

    def _clean(self):
        DesensitizeConfig.objects.filter(index_set_id=self.index_set.index_set_id).delete()
        DesensitizeFieldConfig.objects.filter(index_set_id=self.index_set.index_set_id).delete()

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def test_create_inserts_desensitize_config(self):
        """update_or_create_desensitize_config creates DB records for
        a third-party ES index set (no collector_config_id)."""
        self.handler.update_or_create_desensitize_config(_DESENSITIZE_PAYLOAD)

        saved = DesensitizeConfig.objects.filter(index_set_id=self.index_set.index_set_id)
        self.assertEqual(saved.count(), 1)
        self.assertEqual(saved.first().text_fields, ["log"])

        fields = DesensitizeFieldConfig.objects.filter(index_set_id=self.index_set.index_set_id)
        self.assertEqual(fields.count(), 1)
        self.assertEqual(fields.first().field_name, "message")

    # ------------------------------------------------------------------
    # Retrieve
    # ------------------------------------------------------------------

    def test_retrieve_returns_saved_config(self):
        """desensitize_config_retrieve returns the config previously saved."""
        self.handler.update_or_create_desensitize_config(_DESENSITIZE_PAYLOAD)
        result = self.handler.desensitize_config_retrieve(raise_exception=False)

        self.assertEqual(result["index_set_id"], self.index_set.index_set_id)
        self.assertEqual(result["text_fields"], ["log"])
        self.assertEqual(len(result["field_configs"]), 1)
        self.assertEqual(result["field_configs"][0]["field_name"], "message")
        self.assertEqual(len(result["field_configs"][0]["rules"]), 1)
        self.assertEqual(
            result["field_configs"][0]["rules"][0]["operator"], "mask_shield"
        )

    def test_retrieve_returns_empty_for_no_config(self):
        """desensitize_config_retrieve returns {} when raise_exception=False
        and no config exists."""
        result = self.handler.desensitize_config_retrieve(raise_exception=False)
        self.assertEqual(result, {})

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def test_update_modifies_existing_config(self):
        """Calling update_or_create_desensitize_config again with different
        data updates the existing records (idempotent)."""
        self.handler.update_or_create_desensitize_config(_DESENSITIZE_PAYLOAD)
        self.handler.update_or_create_desensitize_config(_UPDATED_PAYLOAD)

        fields = DesensitizeFieldConfig.objects.filter(index_set_id=self.index_set.index_set_id)
        field_names = list(fields.values_list("field_name", flat=True))
        self.assertIn("server_id", field_names)
        self.assertNotIn("message", field_names)

        config = DesensitizeConfig.objects.get(index_set_id=self.index_set.index_set_id)
        self.assertEqual(config.text_fields, [])

    # ------------------------------------------------------------------
    # State (list-level bulk check)
    # ------------------------------------------------------------------

    def test_get_desensitize_config_state_reflects_config(self):
        """get_desensitize_config_state returns True for index sets
        that have desensitize field configs."""
        self.handler.update_or_create_desensitize_config(_DESENSITIZE_PAYLOAD)

        states = IndexSetHandler.get_desensitize_config_state(
            [self.index_set.index_set_id, 999999]
        )
        self.assertTrue(states[self.index_set.index_set_id]["is_desensitize"])
        self.assertFalse(states[999999]["is_desensitize"])

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def test_delete_removes_config(self):
        """desensitize_config_delete removes all desensitize records
        for the index set."""
        self.handler.update_or_create_desensitize_config(_DESENSITIZE_PAYLOAD)
        self.handler.desensitize_config_delete()

        self.assertEqual(
            DesensitizeConfig.objects.filter(index_set_id=self.index_set.index_set_id).count(), 0
        )
        self.assertEqual(
            DesensitizeFieldConfig.objects.filter(index_set_id=self.index_set.index_set_id).count(), 0
        )

    def test_delete_on_empty_config_does_not_raise(self):
        """desensitize_config_delete on an index set with no config is
        a no-op (DELETE FROM returns 0 rows, no error)."""
        self.handler.desensitize_config_delete()
        self.handler.desensitize_config_delete()

    # ------------------------------------------------------------------
    # Scenario: third-party ES (scenario_id='es')
    # ------------------------------------------------------------------

    def test_handler_works_with_es_scenario(self):
        """The handler does not reject or behave differently for
        scenario_id='es' index sets (no collector_config_id)."""
        self.assertEqual(self.index_set.scenario_id, "es")
        self.assertIsNone(self.index_set.collector_config_id)
        self.handler.update_or_create_desensitize_config(_DESENSITIZE_PAYLOAD)

        saved = DesensitizeConfig.objects.filter(index_set_id=self.index_set.index_set_id)
        self.assertEqual(saved.count(), 1)

    # ------------------------------------------------------------------
    # End of #9923 test cases
    # ------------------------------------------------------------------
