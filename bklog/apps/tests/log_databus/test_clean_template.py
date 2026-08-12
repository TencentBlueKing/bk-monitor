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

from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIRequestFactory

from apps.iam import ActionEnum
from apps.iam.exceptions import PermissionDeniedError
from apps.iam.handlers.drf import ViewBusinessPermission
from apps.log_databus.constants import CleanTemplateSyncStatus
from apps.log_databus.exceptions import (
    CleanTemplateNotExistException,
    CleanTemplateRepeatException,
)
from apps.log_databus.handlers.clean import CleanTemplateHandler
from apps.log_databus.handlers.etl.transfer import TransferEtlHandler
from apps.log_databus.models import CleanTemplate, CollectorConfig
from apps.log_databus.serializers import (
    CollectorEtlStorageSerializer,
    FastCollectorUpdateSerializer,
    FastContainerCollectorUpdateSerializer,
)
from apps.log_databus.views.clean_views import CleanTemplateViewSet
from apps.log_search.models import LogIndexSet, Space


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


class CleanTemplateAssociationSerializerTestCase(SimpleTestCase):
    serializer_cases = (
        (
            CollectorEtlStorageSerializer,
            {
                "table_id": "test_table",
                "etl_config": "bk_log_text",
                "storage_cluster_id": 1,
                "retention": 7,
                "allocation_min_days": 0,
            },
        ),
        (FastCollectorUpdateSerializer, {}),
        (FastContainerCollectorUpdateSerializer, {}),
    )

    def test_omitted_clean_template_id_is_not_added_to_validated_data(self):
        for serializer_class, data in self.serializer_cases:
            with self.subTest(serializer=serializer_class.__name__):
                serializer = serializer_class(data=data)
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertNotIn("clean_template_id", serializer.validated_data)

    def test_explicit_null_clean_template_id_is_preserved(self):
        for serializer_class, data in self.serializer_cases:
            with self.subTest(serializer=serializer_class.__name__):
                serializer = serializer_class(data={**data, "clean_template_id": None})
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertIsNone(serializer.validated_data["clean_template_id"])


class CleanTemplateTestCase(TestCase):
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

    @staticmethod
    def list_templates(**params):
        request = APIRequestFactory().get("/databus/clean_template/", params)
        view = CleanTemplateViewSet()
        view.action_map = {"get": "list"}
        view.args = ()
        view.kwargs = {}
        view.format_kwarg = None
        view.request = view.initialize_request(request)
        return view.list(view.request)


class TestCleanTemplateCrudAndList(CleanTemplateTestCase):
    def test_create_and_duplicate_name(self):
        result = self.create_template()

        self.assertEqual(result["config_version"], 1)
        self.assertEqual(result["description"], CREATE_PARAMS["description"])
        with self.assertRaisesRegex(CleanTemplateRepeatException, r"\[706\]test.*test"):
            self.create_template()

    def test_list_paginates_before_filling_template_stats_by_default(self):
        for index in range(3):
            self.create_template(name=f"template-{index}")

        fill_template_stats = CleanTemplateHandler.fill_template_stats
        with patch.object(CleanTemplateHandler, "fill_template_stats", wraps=fill_template_stats) as fill_stats:
            response = self.list_templates(bk_biz_id=706, page=1, pagesize=1)

        self.assertEqual(response.data["total"], 3)
        self.assertEqual(len(response.data["list"]), 1)
        self.assertEqual(response.data["list"][0]["name"], "template-2")
        stats_input = fill_stats.call_args.args[0]
        self.assertIsInstance(stats_input, list)
        self.assertEqual([template.name for template in stats_input], ["template-2"])

    def test_list_without_pagination_keeps_full_list_response(self):
        for index in range(2):
            self.create_template(name=f"template-{index}")

        response = self.list_templates(bk_biz_id=706)

        self.assertIsInstance(response.data, list)
        self.assertEqual([template["name"] for template in response.data], ["template-1", "template-0"])

    def test_list_fills_all_template_stats_before_ordering_and_pagination(self):
        for index, field_count in enumerate((3, 1, 2)):
            fields = [{"field_name": f"field-{field_index}", "is_delete": False} for field_index in range(field_count)]
            self.create_template(name=f"template-{index}", etl_fields=fields)

        fill_template_stats = CleanTemplateHandler.fill_template_stats
        with patch.object(CleanTemplateHandler, "fill_template_stats", wraps=fill_template_stats) as fill_stats:
            response = self.list_templates(
                bk_biz_id=706,
                ordering="field_count",
                page=1,
                pagesize=1,
            )

        self.assertEqual(response.data["total"], 3)
        self.assertEqual(response.data["list"][0]["name"], "template-1")
        self.assertEqual(response.data["list"][0]["field_count"], 1)
        self.assertEqual(len(list(fill_stats.call_args.args[0])), 3)

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

    def test_list_collectors_returns_active_collectors_with_index_set(self):
        template = self.create_template()
        template_id = template["clean_template_id"]
        index_set = LogIndexSet.objects.create(
            index_set_name="collector-index-set",
            space_uid="bkcc__706",
            scenario_id="log",
        )
        collector = self.create_collector(
            collector_config_name="with-index-set",
            clean_template_id=template_id,
            index_set_id=index_set.index_set_id,
        )
        self.create_collector(
            collector_config_name="without-index-set",
            clean_template_id=template_id,
        )
        self.create_collector(
            collector_config_name="inactive",
            clean_template_id=template_id,
            is_active=False,
        )

        result = CleanTemplateHandler(template_id).list_collectors()

        self.assertEqual(
            [item["collector_config_name"] for item in result],
            ["with-index-set", "without-index-set"],
        )
        self.assertEqual(result[0]["collector_config_id"], collector.collector_config_id)
        self.assertEqual(result[0]["index_set_id"], index_set.index_set_id)
        self.assertEqual(result[0]["index_set_name"], "collector-index-set")
        self.assertIsNone(result[1]["index_set_id"])
        self.assertIsNone(result[1]["index_set_name"])
        self.assertNotIn("bk_biz_name", result[0])


@override_settings(IGNORE_IAM_PERMISSION=False)
class TestCleanTemplateSyncPermission(CleanTemplateTestCase):
    @staticmethod
    def _request():
        return APIRequestFactory().post("/databus/clean_template/1/sync/")

    def test_view_uses_business_permission_by_default(self):
        self.assertEqual(CleanTemplateViewSet.permission_classes, (ViewBusinessPermission,))

    def test_all_collectors_allowed_returns_authorized_ids(self):
        template_data = self.create_template()
        template = CleanTemplate.objects.get(clean_template_id=template_data["clean_template_id"])
        collectors = [
            self.create_collector(
                collector_config_name=f"collector-{index}",
                clean_template_id=template.clean_template_id,
                clean_template_version=None,
            )
            for index in range(2)
        ]
        permission_result = {
            str(collector.collector_config_id): {ActionEnum.MANAGE_COLLECTION.id: True} for collector in collectors
        }

        request = self._request()
        with patch("apps.log_databus.views.clean_views.Permission") as permission_class:
            permission_class.return_value.batch_is_allowed.return_value = permission_result
            collector_ids = CleanTemplateViewSet._get_authorized_sync_collector_ids(request, template)

        self.assertEqual(collector_ids, [collector.collector_config_id for collector in collectors])
        permission_class.assert_called_once_with(request=request)
        actions, resources = permission_class.return_value.batch_is_allowed.call_args.args
        self.assertEqual(actions, [ActionEnum.MANAGE_COLLECTION])
        self.assertEqual([resource[0].id for resource in resources], [str(item) for item in collector_ids])
        self.assertTrue(all(resource[0].attribute.get("_bk_iam_path_") == "/space,706/" for resource in resources))
        permission_class.return_value.get_apply_data.assert_not_called()

    def test_denied_collectors_are_aggregated_into_one_permission_error(self):
        template_data = self.create_template()
        template = CleanTemplate.objects.get(clean_template_id=template_data["clean_template_id"])
        collectors = [
            self.create_collector(
                collector_config_name=f"denied-{index}",
                clean_template_id=template.clean_template_id,
                clean_template_version=None,
            )
            for index in range(2)
        ]
        permission_result = {
            str(collector.collector_config_id): {ActionEnum.MANAGE_COLLECTION.id: False} for collector in collectors
        }

        with patch("apps.log_databus.views.clean_views.Permission") as permission_class:
            permission = permission_class.return_value
            permission.batch_is_allowed.return_value = permission_result
            permission.get_apply_data.return_value = ({"actions": []}, "http://apply")
            with self.assertRaises(PermissionDeniedError) as context:
                CleanTemplateViewSet._get_authorized_sync_collector_ids(self._request(), template)

        self.assertEqual(context.exception.code, "9900403")
        self.assertEqual(context.exception.data["apply_url"], "http://apply")
        actions, denied_resources = permission.get_apply_data.call_args.args
        self.assertEqual(actions, [ActionEnum.MANAGE_COLLECTION])
        self.assertEqual(
            [resource.id for resource in denied_resources],
            [str(collector.collector_config_id) for collector in collectors],
        )
        self.assertEqual([resource.attribute["name"] for resource in denied_resources], ["denied-0", "denied-1"])

    def test_empty_sync_target_skips_iam(self):
        template_data = self.create_template()
        template = CleanTemplate.objects.get(clean_template_id=template_data["clean_template_id"])

        with patch("apps.log_databus.views.clean_views.Permission") as permission_class:
            collector_ids = CleanTemplateViewSet._get_authorized_sync_collector_ids(self._request(), template)

        self.assertEqual(collector_ids, [])
        permission_class.assert_not_called()


class TestCleanTemplateSync(CleanTemplateTestCase):
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

    def test_sync_collector_does_not_restore_manually_removed_association(self):
        template = self.create_template()
        template_id = template["clean_template_id"]
        handler = CleanTemplateHandler(template_id)
        collector = self.create_collector(clean_template_id=template_id)
        clean_config = {
            "etl_config": "bk_log_text",
            "etl_params": {},
            "fields": [],
            "clean_template_id": template_id,
        }

        collector_handler = MagicMock()
        collector_handler.create_or_update_clean_config.side_effect = lambda **kwargs: CollectorConfig.objects.filter(
            collector_config_id=collector.collector_config_id
        ).update(
            clean_template_id=None,
            clean_template_version=None,
            clean_template_sync_status=None,
            clean_template_sync_at=None,
            clean_template_sync_message="",
        )

        with patch("apps.log_databus.handlers.clean.CollectorHandler.get_instance", return_value=collector_handler):
            result = handler._sync_collector(collector, template_version=1, clean_config=clean_config)

        collector.refresh_from_db()
        self.assertIsNone(result)
        self.assertIsNone(collector.clean_template_id)
        self.assertIsNone(collector.clean_template_version)
        self.assertIsNone(collector.clean_template_sync_status)

    def test_sync_collector_does_not_overwrite_rebound_association_on_failure(self):
        template = self.create_template()
        other_template = self.create_template(name="other")
        template_id = template["clean_template_id"]
        other_template_id = other_template["clean_template_id"]
        handler = CleanTemplateHandler(template_id)
        collector = self.create_collector(clean_template_id=template_id)
        clean_config = {
            "etl_config": "bk_log_text",
            "etl_params": {},
            "fields": [],
            "clean_template_id": template_id,
        }

        def rebind_then_fail(**kwargs):
            CollectorConfig.objects.filter(collector_config_id=collector.collector_config_id).update(
                clean_template_id=other_template_id,
                clean_template_version=1,
                clean_template_sync_status=CleanTemplateSyncStatus.SUCCESS.value,
                clean_template_sync_message="",
            )
            raise RuntimeError("stale sync failed")

        collector_handler = MagicMock()
        collector_handler.create_or_update_clean_config.side_effect = rebind_then_fail
        with patch("apps.log_databus.handlers.clean.CollectorHandler.get_instance", return_value=collector_handler):
            result = handler._sync_collector(collector, template_version=1, clean_config=clean_config)

        collector.refresh_from_db()
        self.assertEqual(result["status"], CleanTemplateSyncStatus.FAILED.value)
        self.assertEqual(collector.clean_template_id, other_template_id)
        self.assertEqual(collector.clean_template_version, 1)
        self.assertEqual(collector.clean_template_sync_status, CleanTemplateSyncStatus.SUCCESS.value)
        self.assertEqual(collector.clean_template_sync_message, "")

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
        interrupted = self.create_collector(
            collector_config_name="interrupted",
            clean_template_id=template["clean_template_id"],
            clean_template_version=2,
            clean_template_sync_status=CleanTemplateSyncStatus.RUNNING.value,
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
            def __init__(self):
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

        expected_ids = [
            failed.collector_config_id,
            interrupted.collector_config_id,
            never_synced.collector_config_id,
            outdated.collector_config_id,
        ]
        self.assertEqual([result["id"] for result in results], expected_ids)
        self.assertEqual(
            [call.kwargs["collector"].collector_config_id for call in mock_sync.call_args_list],
            expected_ids,
        )
        self.assertTrue(all(call.kwargs["template_version"] == 2 for call in mock_sync.call_args_list))


class TestCleanTemplatePreview(CleanTemplateTestCase):
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


class TestCleanTemplateAssociation(CleanTemplateTestCase):
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
        handler = TransferEtlHandler(collector.collector_config_id)

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

    def test_etl_uses_current_template_when_template_id_is_omitted(self):
        template = self.create_template(clean_type="bk_log_json", etl_params={"retain_original_text": True})
        collector = self.create_collector(clean_template_id=template["clean_template_id"])
        handler = TransferEtlHandler(collector.collector_config_id)

        clean_template_id = handler._resolve_clean_template_id()
        clean_template, etl_config, etl_params, fields = handler._prepare_clean_template_config(
            clean_template_id,
            "bk_log_text",
            {"request": "params"},
            [{"field_name": "request_field"}],
        )

        self.assertEqual(clean_template_id, template["clean_template_id"])
        self.assertEqual(clean_template.clean_template_id, template["clean_template_id"])
        self.assertEqual(etl_config, "bk_log_json")
        self.assertEqual(etl_params, {"retain_original_text": True})
        self.assertEqual(fields, CREATE_PARAMS["etl_fields"])

    def test_explicit_null_template_id_does_not_reuse_current_template(self):
        template = self.create_template()
        collector = self.create_collector(clean_template_id=template["clean_template_id"])
        handler = TransferEtlHandler(collector.collector_config_id)

        self.assertIsNone(handler._resolve_clean_template_id(None))

    def test_etl_does_not_associate_deleted_template(self):
        template = self.create_template()
        collector = self.create_collector()
        handler = TransferEtlHandler(collector.collector_config_id)
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
            TransferEtlHandler(collector.collector_config_id)._validate_clean_template(template["clean_template_id"])
