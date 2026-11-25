"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company. All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

from unittest.mock import patch

from django.test import TestCase

from apps.api import BkDataAccessApi, TransferApi
from apps.exceptions import ApiResultError
from apps.feature_toggle.handlers.toggle import FeatureToggleObject, Toggle
from apps.log_databus.constants import ETLProcessorChoices
from apps.log_databus.handlers.collector_plugin.bkbase import BKBaseCollectorPluginHandler
from apps.log_databus.models import CollectorPlugin


class TestCollectorPluginDataId(TestCase):
    def setUp(self):
        self.get_data_id = self.enterContext(patch.object(TransferApi, "get_data_id", side_effect=ApiResultError))
        self.create_data_id = self.enterContext(
            patch.object(TransferApi, "create_data_id", return_value={"bk_data_id": 1001})
        )
        self.modify_data_id = self.enterContext(patch.object(TransferApi, "modify_data_id"))
        self.deploy_post = self.enterContext(
            patch.object(BkDataAccessApi, "deploy_plan_post", return_value={"raw_data_id": 1001})
        )
        self.deploy_put = self.enterContext(patch.object(BkDataAccessApi, "deploy_plan_put"))
        self.enterContext(patch("apps.models.get_request_username", return_value="test_operator"))
        self.get_toggle = self.enterContext(
            patch.object(
                FeatureToggleObject,
                "toggle",
                return_value=Toggle(name="log_v4_data_link", status="debug", biz_id_white_list=[1, -1]),
            )
        )
        self.params = {
            "bk_biz_id": 1,
            "collector_plugin_name": "审计日志",
            "collector_plugin_name_en": "audit_log",
            "description": "审计日志",
            "collector_scenario_id": "row",
            "category_id": "application",
            "etl_processor": ETLProcessorChoices.BKBASE.value,
            "is_display_collector": False,
            "is_allow_alone_data_id": True,
            "is_allow_alone_etl_config": True,
            "is_allow_alone_storage": True,
            "is_create_storage": False,
            "is_create_public_data_id": True,
        }

    def create_plugin(self, **params):
        handler = BKBaseCollectorPluginHandler()
        self.assertTrue(handler._update_or_create(dict(self.params, **params)))
        plugin = CollectorPlugin.objects.get(pk=handler.collector_plugin.pk)
        self.assertEqual(plugin.bk_data_id, 1001)
        return plugin

    def test_create_v4_public_data_id_uses_metadata_only(self):
        self.create_plugin()

        self.assertEqual(self.create_data_id.call_args.args[0]["created_from"], "bkdata")
        self.deploy_post.assert_not_called()
        self.deploy_put.assert_not_called()

    def test_create_non_v4_public_data_id_registers_v3_with_metadata_id(self):
        self.create_plugin(bk_biz_id=2)

        self.assertNotIn("created_from", self.create_data_id.call_args.args[0])
        self.assertEqual(self.deploy_post.call_args.args[0]["access_raw_data"]["preassigned_data_id"], 1001)
        self.deploy_put.assert_not_called()

    def test_create_and_update_use_data_business_for_v4_rollout(self):
        for index, (bk_biz_id, bkdata_biz_id, use_v4) in enumerate(
            [(2, 1, True), (1, 2, False), (0, 1, True), (-1, None, True)]
        ):
            with self.subTest(bk_biz_id=bk_biz_id, bkdata_biz_id=bkdata_biz_id):
                self.create_data_id.reset_mock()
                self.deploy_post.reset_mock()
                plugin = self.create_plugin(
                    bk_biz_id=bk_biz_id,
                    bkdata_biz_id=bkdata_biz_id,
                    collector_plugin_name_en=f"audit_log_{index}",
                )
                self.assertEqual("created_from" in self.create_data_id.call_args.args[0], use_v4)
                self.assertEqual(self.deploy_post.called, not use_v4)
                self.modify_data_id.reset_mock()
                self.deploy_put.reset_mock()

                self.assertFalse(BKBaseCollectorPluginHandler(plugin.pk)._update_or_create(self.params))

                self.assertEqual(self.modify_data_id.called, use_v4)
                self.assertEqual(self.deploy_put.called, not use_v4)

    def test_update_v4_public_data_id_updates_metadata(self):
        plugin = self.create_plugin()
        self.get_data_id.side_effect = None
        self.get_data_id.return_value = {"bk_data_id": 1001}
        self.create_data_id.reset_mock()

        self.assertFalse(BKBaseCollectorPluginHandler(plugin.pk)._update_or_create(self.params))

        plugin.refresh_from_db()
        self.assertEqual(plugin.bk_data_id, 1001)
        self.assertEqual(self.modify_data_id.call_args.args[0]["data_id"], 1001)
        self.create_data_id.assert_not_called()
        self.deploy_post.assert_not_called()
        self.deploy_put.assert_not_called()

    def test_update_non_v4_public_data_id_keeps_v3_put(self):
        plugin = self.create_plugin(bk_biz_id=2)
        self.modify_data_id.reset_mock()

        self.assertFalse(BKBaseCollectorPluginHandler(plugin.pk)._update_or_create(self.params))

        self.assertEqual(self.deploy_put.call_args.args[0]["raw_data_id"], 1001)
        self.modify_data_id.assert_not_called()

    def test_retry_after_v3_failure_reuses_metadata_id_on_v4(self):
        self.get_toggle.return_value.status = "off"
        self.deploy_post.side_effect = ApiResultError
        with self.assertRaises(ApiResultError):
            self.create_plugin()
        self.assertFalse(CollectorPlugin.objects.exists())
        self.get_toggle.return_value.status = "debug"
        self.get_data_id.side_effect = None
        self.get_data_id.return_value = {"bk_data_id": 1001}
        self.create_data_id.reset_mock()
        self.deploy_post.reset_mock()

        self.create_plugin()

        self.assertEqual(self.get_data_id.call_args.args[0]["data_name"], "1_bklog_audit_log")
        self.assertEqual(self.modify_data_id.call_args.args[0]["data_id"], 1001)
        self.create_data_id.assert_not_called()
        self.deploy_post.assert_not_called()
        self.deploy_put.assert_not_called()

    def test_metadata_failure_does_not_save_plugin_or_register_v3(self):
        self.create_data_id.side_effect = ApiResultError

        with self.assertRaises(ApiResultError):
            self.create_plugin()

        self.assertFalse(CollectorPlugin.objects.exists())
        self.deploy_post.assert_not_called()
        self.deploy_put.assert_not_called()

    def test_independent_data_id_without_public_id_does_not_register(self):
        handler = BKBaseCollectorPluginHandler()
        self.assertTrue(handler._update_or_create(dict(self.params, is_create_public_data_id=False)))
        self.assertIsNone(handler.collector_plugin.bk_data_id)
        self.create_data_id.assert_not_called()
        self.deploy_post.assert_not_called()
