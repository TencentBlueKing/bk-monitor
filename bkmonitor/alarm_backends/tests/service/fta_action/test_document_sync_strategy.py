from unittest.mock import patch

from django.db.models import TextField, Value
from django.test import TestCase

from alarm_backends.service.fta_action.tasks.action_tasks import _actions_for_document_sync
from alarm_backends.service.fta_action.utils import get_target_info_from_ctx
from bkmonitor.models import ActionInstance
from constants.action import ActionSignal


class TestDocumentSyncStrategy(TestCase):
    def test_strategy_name_matches_snapshot_without_fetching_deferred_items(self):
        snapshots = [{"name": '历史名称 "A"', "items": [{"target": ["sample"]}]}, {}, {"name": None}, {"name": ""}]
        actions = [
            ActionInstance.objects.create(strategy=snapshot, strategy_id=1, signal=ActionSignal.ABNORMAL)
            for snapshot in snapshots
        ]
        with patch("alarm_backends.service.fta_action.utils.ActionContext"):
            expected = {a.id: get_target_info_from_ctx(a, [])["strategy_name"] for a in actions}
            with self.assertNumQueries(1, using=ActionInstance.objects.db):
                projected = list(_actions_for_document_sync(expected))
                self.assertCountEqual([a.id for a in projected], expected)
                for action in projected:
                    self.assertIn("strategy", action.get_deferred_fields())
                    self.assertNotIn("items", action.document_strategy)
                    self.assertEqual(get_target_info_from_ctx(action, [])["strategy_name"], expected[action.id])

    def test_legacy_empty_text_keeps_original_null_value(self):
        action = ActionInstance.objects.create(strategy_id=1, signal=ActionSignal.ABNORMAL)
        ActionInstance.objects.filter(pk=action.pk).update(strategy=Value("", output_field=TextField()))
        self.assertIsNone(ActionInstance.objects.get(pk=action.pk).strategy)
        self.assertIsNone(_actions_for_document_sync([action.pk]).get().document_strategy)
