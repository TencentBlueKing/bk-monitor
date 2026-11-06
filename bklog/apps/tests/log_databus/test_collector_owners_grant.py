"""owners 授权范围：采集项、索引集之外还要补业务访问，否则 owner 进不了这个业务。"""

from unittest.mock import Mock, patch

from django.test import TestCase

from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.models import CollectorConfig
from apps.log_search.models import LogIndexSet

BK_BIZ_ID = 2


class CollectorOwnersGrantTest(TestCase):
    def setUp(self):
        self.collector_config = CollectorConfig.objects.create(
            bk_biz_id=BK_BIZ_ID,
            collector_config_name="owners-grant",
            collector_config_name_en="owners_grant",
            collector_scenario_id="custom",
            category_id="os",
            custom_type="log",
            bk_app_code="bk_log_search",
            table_id=f"{BK_BIZ_ID}_bklog.owners_grant",
        )
        self.permission = Mock()
        self.permission.bk_tenant_id = "tenant-1"
        self.permission.grant_space_access_batch.return_value = []
        permission_patcher = patch("apps.log_databus.handlers.collector.base.Permission", return_value=self.permission)
        permission_patcher.start()
        self.addCleanup(permission_patcher.stop)

    def test_owners_get_space_access_besides_instance_permissions(self):
        LogIndexSet.objects.create(
            index_set_name="owners-grant",
            space_uid=f"bkcc__{BK_BIZ_ID}",
            scenario_id="log",
            collector_config_id=self.collector_config.collector_config_id,
        )

        CollectorHandler._authorization_owners(self.collector_config, ["owner1", "owner2"])

        granted_resource_types = [
            call.kwargs["resource"].type for call in self.permission.grant_creator_action_batch.call_args_list
        ]
        self.assertEqual(granted_resource_types, ["collection", "indices"])
        self.permission.grant_space_access_batch.assert_called_once_with(BK_BIZ_ID, ["owner1", "owner2"])

    def test_space_access_is_granted_even_without_index_set(self):
        """清洗未创建时没有索引集，业务访问授权不能被索引集分支带跑。"""
        CollectorHandler._authorization_owners(self.collector_config, ["owner1"])

        self.permission.grant_space_access_batch.assert_called_once_with(BK_BIZ_ID, ["owner1"])

    def test_idempotent_hit_keeps_space_access_untouched(self):
        """幂等分支只校验业务级新建权限，不得再扩大授权范围。"""
        CollectorHandler._authorization_owners(self.collector_config, ["owner1"], grant_space_access=False)

        self.permission.grant_creator_action_batch.assert_called_once()
        self.permission.grant_space_access_batch.assert_not_called()

    def test_no_owners_touches_no_iam(self):
        CollectorHandler._authorization_owners(self.collector_config, None)

        self.permission.grant_creator_action_batch.assert_not_called()
        self.permission.grant_space_access_batch.assert_not_called()

    def test_failed_space_access_is_logged_without_breaking_the_caller(self):
        self.permission.grant_space_access_batch.return_value = ["owner2"]

        with self.assertLogs(level="WARNING") as captured:
            CollectorHandler._authorization_owners(self.collector_config, ["owner1", "owner2"])

        self.assertTrue(any("grant space access to owners ['owner2'] failed" in line for line in captured.output))

    def test_custom_create_idempotent_branch_skips_space_access(self):
        handler = CollectorHandler()

        with (
            patch.object(CollectorHandler, "get_data_link_id", return_value=0),
            patch.object(CollectorHandler, "_pre_check_collector_config_en", return_value=True),
            patch.object(CollectorHandler, "_authorization_owners") as authorization_owners,
        ):
            result = handler.custom_create(
                bk_biz_id=BK_BIZ_ID,
                collector_config_name="owners-grant",
                collector_config_name_en="owners_grant",
                custom_type="log",
                ignore_exists=True,
                owners=["owner1"],
            )

        self.assertFalse(result["created"])
        authorization_owners.assert_called_once_with(self.collector_config, ["owner1"], grant_space_access=False)
