"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import copy
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.log_databus.constants import CleanTemplateSyncStatus
from apps.log_databus.exceptions import CleanTemplateNotExistException, CleanTemplateRepeatException
from apps.log_databus.handlers.clean import CleanTemplateHandler
from apps.log_databus.handlers.etl import EtlHandler
from apps.log_databus.models import CleanTemplate, CollectorConfig
from apps.log_search.models import Space


CREATE_PARAMS = {
    "name": "test",
    "description": "模板描述",
    "clean_type": "bk_log_text",
    "etl_params": {"retain_original_text": True, "separator": " "},
    "etl_fields": [
        {
            "field_name": "user",
            "alias_name": "",
            "field_type": "long",
            "description": "字段描述",
            "is_analyzed": True,
            "is_dimension": True,
            "is_time": True,
            "is_delete": False,
        }
    ],
    "bk_biz_id": 706,
}


class TestCleanTemplate(TestCase):
    def setUp(self):
        Space.objects.create(
            space_uid="bkcc__706",
            bk_biz_id=706,
            space_type_id="bkcc",
            space_type_name="业务",
            space_id="706",
            space_name="test",
        )
        lock = MagicMock()
        self.lock_patcher = patch.object(CleanTemplateHandler, "_acquire_operation_lock", return_value=lock)
        self.lock_patcher.start()
        self.addCleanup(self.lock_patcher.stop)

    @staticmethod
    def create_template(**overrides):
        params = copy.deepcopy(CREATE_PARAMS)
        params.update(overrides)
        return CleanTemplateHandler().create_or_update(params=params)

    @staticmethod
    def create_collector(**overrides):
        params = {
            "collector_config_name": "collector",
            "collector_scenario_id": "row",
            "category_id": "application",
            "bk_biz_id": 706,
            "is_active": True,
        }
        params.update(overrides)
        return CollectorConfig.objects.create(**params)

    def test_create_and_duplicate_name(self):
        result = self.create_template()

        self.assertEqual(result["config_version"], 1)
        self.assertEqual(result["description"], CREATE_PARAMS["description"])
        self.assertNotIn("visible_type", result)
        with self.assertRaisesRegex(CleanTemplateRepeatException, r"\[706\]test.*test"):
            self.create_template()

    def test_update_only_increments_version_when_clean_config_changes(self):
        result = self.create_template()
        handler = CleanTemplateHandler(result["clean_template_id"])

        metadata_only = copy.deepcopy(CREATE_PARAMS)
        metadata_only.update(name="renamed", description="new description")
        metadata_only.pop("bk_biz_id")
        self.assertEqual(handler.create_or_update(metadata_only)["config_version"], 1)

        changed = copy.deepcopy(metadata_only)
        changed["etl_params"]["separator"] = "|"
        updated = handler.create_or_update(changed)
        self.assertEqual(updated["config_version"], 2)
        self.assertEqual(updated["bk_biz_id"], 706)

    def test_list_collectors_marks_only_active_outdated_collectors(self):
        template = self.create_template()
        template_id = template["clean_template_id"]
        outdated = self.create_collector(
            collector_config_name="outdated",
            clean_template_id=template_id,
            clean_template_version=None,
        )
        self.create_collector(
            collector_config_name="current",
            clean_template_id=template_id,
            clean_template_version=1,
            clean_template_sync_status=CleanTemplateSyncStatus.SUCCESS.value,
        )
        self.create_collector(
            collector_config_name="inactive",
            clean_template_id=template_id,
            is_active=False,
        )

        result = CleanTemplateHandler(template_id).list_collectors()

        self.assertEqual([item["collector_config_name"] for item in result], ["outdated", "current"])
        self.assertEqual(result[0]["collector_config_id"], outdated.collector_config_id)
        self.assertTrue(result[0]["is_outdated"])
        self.assertFalse(result[1]["is_outdated"])
        self.assertEqual(result[0]["bk_biz_name"], "test")

    def test_sync_collector_records_success_and_failure(self):
        template = self.create_template()
        handler = CleanTemplateHandler(template["clean_template_id"])
        collector = self.create_collector(clean_template_id=template["clean_template_id"])
        clean_config = {
            "etl_config": "bk_log_text",
            "etl_params": {},
            "fields": [],
            "clean_template_id": template["clean_template_id"],
        }

        collector_handler = MagicMock()
        with patch("apps.log_databus.handlers.clean.CollectorHandler.get_instance", return_value=collector_handler):
            result = handler._sync_collector(collector, template_version=1, clean_config=clean_config)
        collector.refresh_from_db()
        self.assertEqual(result["status"], CleanTemplateSyncStatus.SUCCESS.value)
        self.assertEqual(collector.clean_template_version, 1)
        self.assertEqual(collector.clean_template_sync_status, CleanTemplateSyncStatus.SUCCESS.value)
        collector_handler.create_or_update_clean_config.assert_called_once_with(
            is_update=True,
            params=clean_config,
            sync_modify_result_table=True,
        )

        collector_handler.create_or_update_clean_config.side_effect = RuntimeError("boom")
        with patch("apps.log_databus.handlers.clean.CollectorHandler.get_instance", return_value=collector_handler):
            result = handler._sync_collector(collector, template_version=2, clean_config=clean_config)
        collector.refresh_from_db()
        self.assertEqual(result["status"], CleanTemplateSyncStatus.FAILED.value)
        self.assertEqual(collector.clean_template_version, 1)
        self.assertEqual(collector.clean_template_sync_status, CleanTemplateSyncStatus.FAILED.value)
        self.assertEqual(collector.clean_template_sync_message, "boom")

    def test_sync_collectors_only_selects_active_collectors_needing_sync(self):
        template = self.create_template()
        CleanTemplate.objects.filter(clean_template_id=template["clean_template_id"]).update(config_version=2)
        handler = CleanTemplateHandler(template["clean_template_id"])
        handler.data.refresh_from_db()

        failed = self.create_collector(
            collector_config_name="failed",
            clean_template_id=template["clean_template_id"],
            clean_template_version=2,
            clean_template_sync_status=CleanTemplateSyncStatus.FAILED.value,
        )
        never_synced = self.create_collector(
            collector_config_name="never-synced",
            clean_template_id=template["clean_template_id"],
            clean_template_version=None,
        )
        outdated = self.create_collector(
            collector_config_name="outdated",
            clean_template_id=template["clean_template_id"],
            clean_template_version=1,
            clean_template_sync_status=CleanTemplateSyncStatus.SUCCESS.value,
        )
        self.create_collector(
            collector_config_name="current",
            clean_template_id=template["clean_template_id"],
            clean_template_version=2,
            clean_template_sync_status=CleanTemplateSyncStatus.SUCCESS.value,
        )
        self.create_collector(
            collector_config_name="inactive",
            clean_template_id=template["clean_template_id"],
            clean_template_version=1,
            is_active=False,
        )
        other_template = self.create_template(name="other")
        self.create_collector(
            collector_config_name="other-template",
            clean_template_id=other_template["clean_template_id"],
            clean_template_version=None,
        )

        class InlineExecutor:
            def __init__(self, max_workers):
                self.tasks = []

            def append(self, result_key, func, params, multi_func_params):
                self.tasks.append((result_key, func, params))

            def run(self, return_exception):
                return {result_key: func(**params) for result_key, func, params in self.tasks}

        def sync_result(collector, template_version, clean_config):
            return {"id": collector.collector_config_id, "status": CleanTemplateSyncStatus.SUCCESS.value}

        with (
            patch("apps.log_databus.handlers.clean.MultiExecuteFunc", InlineExecutor),
            patch.object(handler, "_sync_collector", side_effect=sync_result) as mock_sync,
        ):
            results = handler._sync_collectors()

        expected_ids = [failed.collector_config_id, never_synced.collector_config_id, outdated.collector_config_id]
        self.assertEqual([result["id"] for result in results], expected_ids)
        self.assertEqual(
            [call.kwargs["collector"].collector_config_id for call in mock_sync.call_args_list],
            expected_ids,
        )
        self.assertTrue(all(call.kwargs["template_version"] == 2 for call in mock_sync.call_args_list))

    def test_preview_fields_reports_empty_and_type_mismatch(self):
        fields = [
            {"field_name": "count", "field_type": "int", "is_delete": False},
            {"field_name": "meta", "field_type": "object", "is_delete": False},
            {"field_name": "missing", "field_type": "string", "is_delete": False},
            {"field_name": "ignored", "field_type": "string", "is_delete": True},
        ]
        template = self.create_template(clean_type="bk_log_json", etl_fields=fields)
        handler = CleanTemplateHandler(template["clean_template_id"])

        result = handler._build_preview_fields(
            [
                {"field_name": "count", "value": "12"},
                {"field_name": "meta", "value": "not-an-object"},
            ]
        )

        self.assertEqual([item["status"] for item in result], ["NORMAL", "ABNORMAL", "ABNORMAL"])
        self.assertEqual(result[1]["error_type"], "TYPE_MISMATCH")
        self.assertEqual(result[1]["inferred_field_type"], "string")
        self.assertEqual(result[2]["error_type"], "EMPTY_VALUE")

    def test_destroy_unlinks_collectors(self):
        template = self.create_template()
        collector = self.create_collector(
            clean_template_id=template["clean_template_id"],
            clean_template_version=1,
            clean_template_sync_status=CleanTemplateSyncStatus.FAILED.value,
            clean_template_sync_message="failed",
        )

        result = CleanTemplateHandler(template["clean_template_id"]).destroy()

        collector.refresh_from_db()
        self.assertEqual(result, template["clean_template_id"])
        self.assertFalse(CleanTemplate.objects.filter(clean_template_id=result).exists())
        self.assertIsNone(collector.clean_template_id)
        self.assertIsNone(collector.clean_template_version)
        self.assertIsNone(collector.clean_template_sync_status)
        self.assertEqual(collector.clean_template_sync_message, "")

    def test_etl_uses_template_snapshot_and_updates_association(self):
        template = self.create_template(clean_type="bk_log_json", etl_params={"retain_original_text": True})
        collector = self.create_collector()
        handler = EtlHandler(collector.collector_config_id)

        clean_template, etl_config, etl_params, fields = handler._prepare_clean_template_config(
            template["clean_template_id"],
            "bk_log_text",
            {"request": "params"},
            [{"field_name": "request_field"}],
        )
        etl_params["mutated"] = True
        fields.append({"field_name": "mutated"})

        clean_template.refresh_from_db()
        self.assertEqual(etl_config, "bk_log_json")
        self.assertEqual(clean_template.etl_params, {"retain_original_text": True})
        self.assertEqual(clean_template.etl_fields, CREATE_PARAMS["etl_fields"])

        handler._update_clean_template(template["clean_template_id"], clean_template)
        collector.refresh_from_db()
        self.assertEqual(collector.clean_template_id, template["clean_template_id"])
        self.assertEqual(collector.clean_template_version, 1)
        self.assertEqual(collector.clean_template_sync_status, CleanTemplateSyncStatus.SUCCESS.value)

    def test_etl_does_not_associate_deleted_template(self):
        template = self.create_template()
        collector = self.create_collector()
        handler = EtlHandler(collector.collector_config_id)
        clean_template = CleanTemplate.objects.get(clean_template_id=template["clean_template_id"])

        clean_template.delete()
        with self.assertRaises(CleanTemplateNotExistException):
            handler._update_clean_template(template["clean_template_id"], clean_template)

        collector.refresh_from_db()
        self.assertIsNone(collector.clean_template_id)
        self.assertIsNone(collector.clean_template_version)
        self.assertIsNone(collector.clean_template_sync_status)

    def test_etl_rejects_template_from_another_business(self):
        template = self.create_template()
        collector = self.create_collector(bk_biz_id=999)

        with self.assertRaises(CleanTemplateNotExistException):
            EtlHandler(collector.collector_config_id)._validate_clean_template(template["clean_template_id"])
