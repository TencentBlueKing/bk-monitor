from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.exceptions import PermissionError as BklogPermissionError
from apps.log_admin_resource.handlers.collector import get_collector_detail, list_collectors
from apps.log_admin_resource.handlers.index_set import get_index_set_detail, list_index_sets
from apps.log_admin_resource.handlers.inspection import require_biz_in_request_tenant
from apps.log_admin_resource.handlers.platform_source import query_platform_source
from apps.log_databus.models import CollectorConfig
from apps.log_search.models import LogIndexSet, Scenario, Space


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APP_TENANT_ID="tenant-a")
class ResourceTenantIsolationSecurityTest(TestCase):
    def setUp(self):
        for bk_biz_id, tenant_id in ((2, "tenant-a"), (3, "tenant-b")):
            Space.objects.create(
                space_uid=f"bkcc__{bk_biz_id}",
                bk_biz_id=bk_biz_id,
                space_type_id="bkcc",
                space_type_name="business",
                space_id=str(bk_biz_id),
                space_name=f"biz-{bk_biz_id}",
                bk_tenant_id=tenant_id,
            )
            CollectorConfig.objects.create(
                collector_config_id=1000 + bk_biz_id,
                collector_config_name=f"collector-{bk_biz_id}",
                collector_config_name_en=f"collector_{bk_biz_id}",
                bk_biz_id=bk_biz_id,
                category_id="os",
                collector_scenario_id="row",
                custom_type="log",
                environment="linux",
            )
            LogIndexSet.objects.create(
                index_set_id=2000 + bk_biz_id,
                index_set_name=f"index-{bk_biz_id}",
                space_uid=f"bkcc__{bk_biz_id}",
                category_id="host",
                scenario_id=Scenario.LOG,
            )

    @patch("apps.log_admin_resource.handlers.inspection.get_request_tenant_id", return_value="tenant-a")
    def test_legacy_management_handlers_keep_historical_cross_tenant_semantics(self, _tenant):
        self.assertCountEqual(
            [item["bk_biz_id"] for item in list_collectors({"page_size": 100})["items"]],
            [2, 3],
        )
        self.assertEqual(
            [item["space_uid"] for item in list_index_sets({"page_size": 100, "ordering": "index_set_id"})["items"]],
            ["bkcc__2", "bkcc__3"],
        )
        self.assertEqual(get_collector_detail({"collector_config_id": 1003})["collector"]["bk_biz_id"], 3)
        self.assertEqual(get_index_set_detail({"index_set_id": 2003})["index_set"]["space_uid"], "bkcc__3")

    @patch("apps.log_admin_resource.handlers.inspection.get_request_tenant_id", return_value="tenant-a")
    def test_caller_selected_business_must_belong_to_request_tenant(self, _tenant):
        self.assertEqual(require_biz_in_request_tenant(2), 2)
        with self.assertRaises(BklogPermissionError):
            require_biz_in_request_tenant(3)

    @patch("apps.log_admin_resource.handlers.inspection.get_request_tenant_id", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.platform_source.TransferApi.get_cluster_status")
    def test_platform_source_rejects_other_tenant_business_before_provider_call(self, mock_api, _tenant):
        with self.assertRaises(BklogPermissionError):
            query_platform_source(
                {
                    "mode": "invoke",
                    "domain": "metadata",
                    "operation": "get_storage_cluster_status",
                    "params": {"bk_biz_id": 3, "cluster_ids": [11]},
                }
            )
        mock_api.assert_not_called()

    @patch("apps.log_admin_resource.handlers.inspection.get_request_tenant_id", return_value="")
    def test_missing_trusted_tenant_fails_closed(self, _tenant):
        with self.assertRaises(BklogPermissionError):
            require_biz_in_request_tenant(2)
