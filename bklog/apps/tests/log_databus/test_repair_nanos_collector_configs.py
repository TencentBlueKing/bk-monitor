from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.log_databus.models import CollectorConfig
from apps.log_search.models import LogIndexSet, Scenario


class TestRepairNanosCollectorConfigs(TestCase):
    def test_repair_non_nanos_result_table_and_sync_router(self):
        collector_config = CollectorConfig.objects.create(
            bk_biz_id=2,
            collector_config_name="nanos_collector",
            collector_scenario_id="log",
            category_id="other_rt",
            table_id="2_nanos_collector",
            is_nanos=True,
        )
        index_set = LogIndexSet.objects.create(
            index_set_name="nanos_index_set",
            space_uid="bkcc__2",
            scenario_id=Scenario.LOG,
            collector_config_id=collector_config.collector_config_id,
        )
        collector_config.index_set_id = index_set.index_set_id
        collector_config.save(update_fields=["index_set_id"])

        stdout = StringIO()
        with patch(
            "apps.log_databus.management.commands.repair_nanos_collector_configs.TransferApi.get_result_table",
            return_value={"field_list": [{"field_name": "dtEventTimeStamp"}]},
        ):
            with patch(
                "apps.log_databus.management.commands.repair_nanos_collector_configs.BaseIndexSetHandler.sync_router"
            ) as mock_sync_router:
                call_command("repair_nanos_collector_configs", stdout=stdout)

        collector_config.refresh_from_db()
        self.assertFalse(collector_config.is_nanos)
        mock_sync_router.assert_called_once_with(index_set)
        self.assertIn("repaired=1", stdout.getvalue())

    def test_dry_run_does_not_change_collector_config(self):
        collector_config = CollectorConfig.objects.create(
            bk_biz_id=2,
            collector_config_name="nanos_collector_dry_run",
            collector_scenario_id="log",
            category_id="other_rt",
            table_id="2_nanos_collector_dry_run",
            is_nanos=True,
        )

        with patch(
            "apps.log_databus.management.commands.repair_nanos_collector_configs.TransferApi.get_result_table",
            return_value={"field_list": [{"field_name": "dtEventTimeStamp"}]},
        ):
            call_command("repair_nanos_collector_configs", "--dry-run")

        collector_config.refresh_from_db()
        self.assertTrue(collector_config.is_nanos)
