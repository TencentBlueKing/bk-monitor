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

from apps.exceptions import ApiResultError, ValidationError
from apps.iam import ActionEnum
from apps.iam.exceptions import PermissionDeniedError
from apps.iam.handlers.drf import ViewBusinessPermission
from apps.log_databus.constants import (
    CleanTemplateStatus,
    CleanTemplateSyncMessage,
    CleanTemplateSyncStatus,
    ContainerCollectorType,
    Environment,
)
from apps.log_databus.exceptions import (
    CleanTemplateNotExistException,
    CleanTemplateRepeatException,
    EtlPreviewException,
)
from apps.log_databus.handlers.clean import CleanTemplateHandler
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.handlers.etl.transfer import TransferEtlHandler
from apps.log_databus.handlers.etl_storage.bk_log_json import BkLogJsonEtlStorage
from apps.log_databus.models import CleanStash, CleanTemplate, CollectorConfig, ContainerCollectorConfig
from apps.log_databus.serializers import (
    CleanTemplateSerializer,
    CleanStashSerializer,
    CollectorEtlStorageSerializer,
    FastCollectorUpdateSerializer,
    FastContainerCollectorUpdateSerializer,
)
from apps.log_databus.views.clean_views import CleanTemplateViewSet
from apps.log_search.constants import IndexSetDataType, LogAccessTypeEnum
from apps.log_search.models import LogIndexSet, LogIndexSetData, Space

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

    def test_clean_stash_serializer_preserves_clean_template_id_tristate(self):
        base_data = {
            "clean_type": "bk_log_text",
            "etl_params": {},
            "etl_fields": [],
            "bk_biz_id": 706,
        }
        cases = (
            ("omitted", {}, False, None),
            ("specified", {"clean_template_id": 1}, True, 1),
            ("explicit-null", {"clean_template_id": None}, True, None),
        )
        for name, template_data, field_present, expected in cases:
            with self.subTest(case=name):
                serializer = CleanStashSerializer(data={**base_data, **template_data})
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertEqual("clean_template_id" in serializer.validated_data, field_present)
                if field_present:
                    self.assertEqual(serializer.validated_data["clean_template_id"], expected)


class CleanTemplateSerializerTestCase(SimpleTestCase):
    """模板保存路径切换到 CollectorEtlFieldsSerializer 后的 serializer 层测试。"""

    FRONTEND_ETL_FIELDS = [
        {
            "field_name": "message",
            "alias_name": "",
            "description": "",
            "field_type": "string",
            "is_case_sensitive": False,
            "is_analyzed": True,
            "is_built_in": False,
            "is_delete": False,
            "is_dimension": False,
            "is_time": False,
            "value": "",
            "option": {"time_format": "", "time_zone": ""},
            "tokenize_on_chars": "",
        }
    ]

    FRONTEND_ETL_PARAMS = {
        "separator_regexp": "",
        "separator": "",
        "retain_original_text": True,
        "original_text_is_case_sensitive": False,
        "original_text_tokenize_on_chars": "",
        "retain_extra_json": False,
        "enable_retain_content": True,
        "path_regexp": "",
        "metadata_fields": [],
    }

    def base_data(self, **overrides):
        data = {
            "name": "模板",
            "description": "模板描述",
            "clean_type": "bk_log_json",
            "etl_params": copy.deepcopy(self.FRONTEND_ETL_PARAMS),
            "etl_fields": copy.deepcopy(self.FRONTEND_ETL_FIELDS),
        }
        data.update(overrides)
        return data

    def test_frontend_payload_passes_validation(self):
        # 现网前端「另存为模板」payload（rowTemplate 全量默认键，未传 record_parse_failure）
        # 应能通过校验
        serializer = CleanTemplateSerializer(data={**self.base_data(), "bk_biz_id": 706})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_missing_is_delete_field_raises(self):
        serializer = CleanTemplateSerializer(
            data={
                **self.base_data(etl_fields=[{"field_name": "message", "field_type": "string", "is_analyzed": False}]),
                "bk_biz_id": 706,
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("is_delete", serializer.errors["etl_fields"][0])

    def test_is_add_in_default_injected_and_round_trip(self):
        serializer = CleanTemplateSerializer(data={**self.base_data(), "bk_biz_id": 706})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertFalse(serializer.data["etl_fields"][0]["is_add_in"])

        data = self.base_data(etl_fields=[{**self.FRONTEND_ETL_FIELDS[0], "is_add_in": True}])
        serializer = CleanTemplateSerializer(data={**data, "bk_biz_id": 706})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertTrue(serializer.data["etl_fields"][0]["is_add_in"])

    def test_missing_etl_params_keys_get_defaults(self):
        # 用户未配置的 etl_params 键会被注入默认值并持久化到模板
        serializer = CleanTemplateSerializer(data={**self.base_data(etl_params={}), "bk_biz_id": 706})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        etl_params = serializer.data["etl_params"]
        self.assertTrue(etl_params["record_parse_failure"])
        self.assertTrue(etl_params["enable_retain_content"])
        self.assertTrue(etl_params["retain_original_text"])
        self.assertFalse(etl_params["retain_extra_json"])

    def test_is_dimension_aligned_with_is_analyzed(self):
        # 非内置字段保存时 is_dimension 与 is_analyzed 对齐（与采集项路径一致），
        # 前端 rowTemplate 默认 false 会被改写为 not is_analyzed
        cases = ((False, True), (True, False))
        for is_analyzed, expected in cases:
            with self.subTest(is_analyzed=is_analyzed):
                field = {**self.FRONTEND_ETL_FIELDS[0], "is_analyzed": is_analyzed, "is_dimension": False}
                serializer = CleanTemplateSerializer(data={**self.base_data(etl_fields=[field]), "bk_biz_id": 706})
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertEqual(serializer.data["etl_fields"][0]["is_dimension"], expected)


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

        self.assertEqual(result["status"], CleanTemplateStatus.PUBLISHED.value)
        self.assertIsNone(result["snapshot"])
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

    def test_retrieve_returns_template_stats(self):
        template = self.create_template()

        request = APIRequestFactory().get(f"/databus/clean_template/{template['clean_template_id']}/")
        view = CleanTemplateViewSet()
        view.action_map = {"get": "retrieve"}
        view.args = ()
        view.kwargs = {"clean_template_id": template["clean_template_id"]}
        view.format_kwarg = None
        view.request = view.initialize_request(request)

        response = view.retrieve(view.request, clean_template_id=template["clean_template_id"])

        self.assertEqual(response.data["field_count"], 1)
        self.assertEqual(response.data["active_collector_count"], 0)
        self.assertEqual(response.data["related_index_set_count"], 0)

    def test_list_uses_draft_fields_for_field_count(self):
        template = self.create_template()
        self.create_collector(clean_template_id=template["clean_template_id"])
        changed = copy.deepcopy(CREATE_PARAMS)
        changed.pop("bk_biz_id")
        changed["etl_fields"].append({"field_name": "draft_field", "is_delete": False})
        CleanTemplateHandler(template["clean_template_id"]).create_or_update(changed)

        response = self.list_templates(bk_biz_id=706)

        self.assertEqual(response.data[0]["status"], CleanTemplateStatus.DRAFT.value)
        self.assertEqual(response.data[0]["field_count"], 2)

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

    def test_update_without_collectors_is_published_immediately(self):
        result = self.create_template()
        handler = CleanTemplateHandler(result["clean_template_id"])

        changed = copy.deepcopy(CREATE_PARAMS)
        changed.pop("bk_biz_id")
        changed["etl_params"]["separator"] = "|"
        updated = handler.create_or_update(changed)

        self.assertEqual(updated["status"], CleanTemplateStatus.PUBLISHED.value)
        self.assertIsNone(updated["snapshot"])
        self.assertEqual(updated["etl_params"]["separator"], "|")
        self.assertEqual(updated["bk_biz_id"], 706)

    def test_update_with_collectors_saves_draft_snapshot(self):
        result = self.create_template()
        self.create_collector(clean_template_id=result["clean_template_id"])
        changed = copy.deepcopy(CREATE_PARAMS)
        changed.pop("bk_biz_id")
        changed.update(name="draft-name", description="draft-description")
        changed["etl_params"]["separator"] = "|"

        updated = CleanTemplateHandler(result["clean_template_id"]).create_or_update(changed)

        self.assertEqual(updated["status"], CleanTemplateStatus.DRAFT.value)
        self.assertEqual(updated["name"], "draft-name")
        self.assertEqual(updated["description"], "draft-description")
        self.assertEqual(updated["etl_params"], CREATE_PARAMS["etl_params"])
        self.assertEqual(set(updated["snapshot"]), {"clean_type", "etl_params", "etl_fields"})
        self.assertEqual(updated["snapshot"]["etl_params"]["separator"], "|")

    def test_update_with_only_inactive_collectors_is_published_immediately(self):
        result = self.create_template()
        self.create_collector(clean_template_id=result["clean_template_id"], is_active=False)
        changed = copy.deepcopy(CREATE_PARAMS)
        changed.pop("bk_biz_id")
        changed["etl_params"]["separator"] = "|"

        updated = CleanTemplateHandler(result["clean_template_id"]).create_or_update(changed)

        self.assertEqual(updated["status"], CleanTemplateStatus.PUBLISHED.value)
        self.assertIsNone(updated["snapshot"])
        self.assertEqual(updated["etl_params"]["separator"], "|")

    def test_update_metadata_with_collectors_is_published_immediately(self):
        result = self.create_template()
        self.create_collector(clean_template_id=result["clean_template_id"])
        metadata_only = copy.deepcopy(CREATE_PARAMS)
        metadata_only.pop("bk_biz_id")
        metadata_only.update(name="renamed", description="new description")

        updated = CleanTemplateHandler(result["clean_template_id"]).create_or_update(metadata_only)

        self.assertEqual(updated["status"], CleanTemplateStatus.PUBLISHED.value)
        self.assertIsNone(updated["snapshot"])
        self.assertEqual(updated["name"], "renamed")
        self.assertEqual(updated["description"], "new description")

    def test_reverting_clean_config_keeps_draft_until_sync(self):
        result = self.create_template()
        self.create_collector(clean_template_id=result["clean_template_id"])
        handler = CleanTemplateHandler(result["clean_template_id"])
        changed = copy.deepcopy(CREATE_PARAMS)
        changed.pop("bk_biz_id")
        changed["etl_params"]["separator"] = "|"
        self.assertEqual(handler.create_or_update(changed)["status"], CleanTemplateStatus.DRAFT.value)

        reverted = copy.deepcopy(CREATE_PARAMS)
        reverted.pop("bk_biz_id")
        updated = handler.create_or_update(reverted)

        self.assertEqual(updated["status"], CleanTemplateStatus.DRAFT.value)
        self.assertEqual(updated["snapshot"]["etl_params"], CREATE_PARAMS["etl_params"])

        handler.sync_collectors([])
        handler.data.refresh_from_db()
        self.assertEqual(handler.data.status, CleanTemplateStatus.PUBLISHED.value)
        self.assertIsNone(handler.data.snapshot)

    def test_update_metadata_keeps_existing_draft(self):
        result = self.create_template()
        self.create_collector(clean_template_id=result["clean_template_id"])
        handler = CleanTemplateHandler(result["clean_template_id"])
        changed = copy.deepcopy(CREATE_PARAMS)
        changed.pop("bk_biz_id")
        changed["etl_params"]["separator"] = "|"
        handler.create_or_update(changed)

        changed.update(name="renamed", description="new description")
        updated = handler.create_or_update(changed)

        self.assertEqual(updated["status"], CleanTemplateStatus.DRAFT.value)
        self.assertEqual(updated["snapshot"]["etl_params"]["separator"], "|")
        self.assertEqual(updated["etl_params"], CREATE_PARAMS["etl_params"])
        self.assertEqual(updated["name"], "renamed")
        self.assertEqual(updated["description"], "new description")

    def test_update_does_not_restore_deleted_template(self):
        result = self.create_template()
        template_id = result["clean_template_id"]
        stale_handler = CleanTemplateHandler(template_id)
        CleanTemplateHandler(template_id).destroy()

        changed = copy.deepcopy(CREATE_PARAMS)
        changed.pop("bk_biz_id")
        changed["name"] = "renamed"
        with self.assertRaises(CleanTemplateNotExistException):
            stale_handler.create_or_update(changed)

        self.assertFalse(CleanTemplate.objects.filter(clean_template_id=template_id).exists())

    def test_list_collectors_returns_active_collectors_with_related_index_sets(self):
        template = self.create_template()
        template_id = template["clean_template_id"]
        index_set = LogIndexSet.objects.create(
            index_set_name="collector-index-set",
            space_uid="bkcc__706",
            scenario_id="log",
        )
        parent_index_sets = [
            LogIndexSet.objects.create(
                index_set_name=f"parent-{index}",
                space_uid="bkcc__706",
                scenario_id="log",
                is_group=True,
            )
            for index in range(2)
        ]
        for parent_index_set in reversed(parent_index_sets):
            LogIndexSetData.objects.create(
                index_set_id=parent_index_set.index_set_id,
                result_table_id=str(index_set.index_set_id),
                type=IndexSetDataType.INDEX_SET.value,
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
        self.assertEqual(result[0]["log_access_type"], LogAccessTypeEnum.LINUX.value)
        self.assertEqual(result[1]["log_access_type"], LogAccessTypeEnum.LINUX.value)
        self.assertNotIn("index_set_id", result[0])
        self.assertNotIn("index_set_name", result[0])
        self.assertEqual(
            result[0]["related_index_set_list"],
            [
                {"index_set_id": parent.index_set_id, "index_set_name": parent.index_set_name}
                for parent in parent_index_sets
            ],
        )
        self.assertNotIn("index_set_id", result[1])
        self.assertNotIn("index_set_name", result[1])
        self.assertEqual(result[1]["related_index_set_list"], [])
        self.assertNotIn("bk_biz_name", result[0])

        template_data = self.list_templates(bk_biz_id=706).data[0]
        self.assertEqual(template_data["related_index_set_count"], 2)

    def test_list_collectors_returns_container_log_access_type(self):
        template_id = self.create_template()["clean_template_id"]
        container_file = self.create_collector(
            collector_config_name="container-file",
            clean_template_id=template_id,
            environment=Environment.CONTAINER,
        )
        container_stdout = self.create_collector(
            collector_config_name="container-stdout",
            clean_template_id=template_id,
            environment=Environment.CONTAINER,
        )
        ContainerCollectorConfig.objects.create(
            collector_config_id=container_file.collector_config_id,
            collector_type=ContainerCollectorType.CONTAINER,
        )
        ContainerCollectorConfig.objects.create(
            collector_config_id=container_stdout.collector_config_id,
            collector_type=ContainerCollectorType.STDOUT,
        )

        result = CleanTemplateHandler(template_id).list_collectors()

        self.assertEqual(
            {item["collector_config_name"]: item["log_access_type"] for item in result},
            {
                "container-file": LogAccessTypeEnum.CONTAINER_FILE.value,
                "container-stdout": LogAccessTypeEnum.CONTAINER_STDOUT.value,
            },
        )


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
            )
            for index in range(3)
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
    def test_sync_collector_uses_async_result_table_update(self):
        template = self.create_template()
        template_id = template["clean_template_id"]
        table_id = CollectorHandler.build_result_table_id(706, "collector")
        collector = self.create_collector(
            clean_template_id=template_id,
            table_id=table_id,
            etl_config="bk_log_text",
        )
        handler = CleanTemplateHandler(template_id)
        clean_config = {
            "etl_config": template["clean_type"],
            "etl_params": copy.deepcopy(template["etl_params"]),
            "fields": copy.deepcopy(template["etl_fields"]),
        }
        database_fields = copy.deepcopy(template["etl_fields"])
        database_fields[0]["field_name"] = "database_only"
        CleanTemplate.objects.filter(clean_template_id=template_id).update(etl_fields=database_fields)
        result_table = {
            "cluster_config": {"cluster_id": 11},
            "storage_config": {
                "retention": 14,
                "warm_phase_days": 3,
                "index_settings": {
                    "number_of_shards": 4,
                    "number_of_replicas": 2,
                },
            },
        }
        cluster_info = {
            "cluster_type": "elasticsearch",
            "cluster_config": {
                "version": "7.x",
                "custom_option": {
                    "hot_warm_config": {
                        "is_enabled": True,
                        "hot_attr_name": "temperature",
                        "hot_attr_value": "hot",
                        "warm_attr_name": "temperature",
                        "warm_attr_value": "warm",
                    }
                },
            },
        }

        with (
            patch(
                "apps.log_databus.handlers.collector.base.TransferApi.get_result_table_storage",
                return_value={table_id: result_table},
            ),
            patch("apps.log_databus.handlers.collector.base.StorageHandler") as collector_storage_handler,
            patch("apps.log_databus.handlers.etl.transfer.StorageHandler") as transfer_storage_handler,
            patch(
                "apps.log_databus.handlers.etl_storage.base.get_es_config",
                return_value={"ES_DATE_FORMAT": "%Y%m%d", "ES_SHARDS_SIZE": 30, "ES_SLICE_GAP": 1440},
            ),
            patch(
                "apps.log_databus.handlers.etl_storage.base.TransferApi.get_result_table",
                return_value={"table_id": table_id},
            ),
            patch("apps.log_databus.tasks.collector.modify_result_table.delay") as modify_result_table_delay,
            patch.object(
                TransferEtlHandler,
                "_update_or_create_index_set",
                return_value={"index_set_id": 1, "scenario_id": "log"},
            ),
            patch("apps.log_databus.handlers.etl.transfer.user_operation_record.delay"),
        ):
            collector_storage_handler.return_value.get_cluster_info_by_id.return_value = cluster_info
            transfer_storage_handler.return_value.get_cluster_info_by_id.return_value = cluster_info

            result = handler._sync_collector(collector, clean_config=clean_config)

            self.assertEqual(result["status"], CleanTemplateSyncStatus.SUCCESS.value)
            modify_result_table_delay.assert_called_once()
            result_table_params = modify_result_table_delay.call_args.args[0]
            self.assertEqual(result_table_params["table_id"], table_id)
            self.assertEqual(result_table_params["default_storage_config"]["cluster_id"], 11)
            self.assertEqual(result_table_params["default_storage_config"]["retention"], 14)
            self.assertEqual(result_table_params["default_storage_config"]["warm_phase_days"], 3)
            self.assertEqual(
                result_table_params["default_storage_config"]["index_settings"]["number_of_shards"],
                4,
            )
            self.assertEqual(
                result_table_params["default_storage_config"]["index_settings"]["number_of_replicas"],
                2,
            )
            result_field_names = {field["field_name"] for field in result_table_params["field_list"]}
            self.assertIn("user", result_field_names)
            self.assertNotIn("database_only", result_field_names)

    def test_sync_collector_returns_async_submission_success(self):
        template = self.create_template()
        handler = CleanTemplateHandler(template["clean_template_id"])
        collector = self.create_collector(clean_template_id=template["clean_template_id"])
        clean_config = {
            "etl_config": "bk_log_text",
            "etl_params": {},
            "fields": [],
        }

        collector_handler = MagicMock()
        with patch("apps.log_databus.handlers.clean.CollectorHandler.get_instance", return_value=collector_handler):
            result = handler._sync_collector(collector, clean_config=clean_config)

        self.assertEqual(
            result,
            {
                "id": collector.collector_config_id,
                "name": collector.collector_config_name,
                "status": CleanTemplateSyncStatus.SUCCESS.value,
                "message": str(CleanTemplateSyncMessage.SUCCESS.value),
            },
        )
        collector_handler.create_or_update_clean_config.assert_called_once_with(
            is_update=True,
            params={
                **clean_config,
                "use_provided_clean_config": True,
            },
        )

    def test_sync_collector_does_not_restore_changed_association(self):
        template = self.create_template()
        template_id = template["clean_template_id"]
        handler = CleanTemplateHandler(template_id)
        collector = self.create_collector(clean_template_id=template_id)
        clean_config = {
            "etl_config": "bk_log_text",
            "etl_params": {},
            "fields": [],
        }

        collector_handler = MagicMock()

        def unbind_collector(*args, **kwargs):
            CollectorConfig.objects.filter(collector_config_id=collector.collector_config_id).update(
                clean_template_id=None
            )

        collector_handler.create_or_update_clean_config.side_effect = unbind_collector
        with patch("apps.log_databus.handlers.clean.CollectorHandler.get_instance", return_value=collector_handler):
            result = handler._sync_collector(collector, clean_config=clean_config)

        collector.refresh_from_db()
        self.assertIsNone(collector.clean_template_id)
        self.assertEqual(result["status"], CleanTemplateSyncStatus.FAILED.value)
        self.assertEqual(result["message"], str(CleanTemplateSyncMessage.ASSOCIATION_CHANGED.value))
        collector_handler.create_or_update_clean_config.assert_called_once_with(
            is_update=True,
            params={
                **clean_config,
                "use_provided_clean_config": True,
            },
        )

    def test_sync_collector_returns_failed_when_association_check_raises(self):
        template = self.create_template()
        handler = CleanTemplateHandler(template["clean_template_id"])
        collector = self.create_collector(clean_template_id=template["clean_template_id"])

        with (
            patch(
                "apps.log_databus.handlers.clean.CollectorConfig.objects.filter",
                side_effect=RuntimeError("database unavailable"),
            ),
            patch("apps.log_databus.handlers.clean.CollectorHandler.get_instance") as get_instance,
        ):
            result = handler._sync_collector(collector, clean_config={})

        self.assertEqual(result["status"], CleanTemplateSyncStatus.FAILED.value)
        self.assertEqual(result["message"], str(CleanTemplateSyncMessage.FAILED.value))
        get_instance.assert_not_called()

    def test_sync_collector_skips_changed_association(self):
        template = self.create_template()
        template_id = template["clean_template_id"]
        handler = CleanTemplateHandler(template_id)
        collector = self.create_collector(clean_template_id=template_id)
        clean_config = {
            "etl_config": "bk_log_text",
            "etl_params": {},
            "fields": [],
        }
        CollectorConfig.objects.filter(collector_config_id=collector.collector_config_id).update(
            clean_template_id=None,
        )

        with patch("apps.log_databus.handlers.clean.CollectorHandler.get_instance") as get_instance:
            result = handler._sync_collector(collector, clean_config=clean_config)

        self.assertEqual(result["status"], CleanTemplateSyncStatus.FAILED.value)
        self.assertEqual(result["message"], str(CleanTemplateSyncMessage.ASSOCIATION_CHANGED.value))
        get_instance.assert_not_called()

    def test_sync_collectors_publishes_snapshot_and_returns_individual_results(self):
        template = self.create_template()
        template_id = template["clean_template_id"]
        collectors = [
            self.create_collector(collector_config_name=f"collector-{index}", clean_template_id=template_id)
            for index in range(3)
        ]
        changed = copy.deepcopy(CREATE_PARAMS)
        changed.pop("bk_biz_id")
        changed["etl_params"]["separator"] = "|"
        CleanTemplateHandler(template_id).create_or_update(changed)
        handler = CleanTemplateHandler(template_id)
        collector_handler = MagicMock()
        collector_handler.create_or_update_clean_config.side_effect = RuntimeError("submit failed")

        class InlineExecutor:
            def __init__(self):
                self.tasks = []

            def append(self, result_key, func, params, multi_func_params):
                self.tasks.append((result_key, func, params))

            def run(self):
                return {result_key: func(**params) for result_key, func, params in self.tasks}

        with (
            patch("apps.log_databus.handlers.clean.MultiExecuteFunc", return_value=InlineExecutor()),
            patch("apps.log_databus.handlers.clean.CollectorHandler.get_instance", return_value=collector_handler),
        ):
            result = handler.sync_collectors([collector.collector_config_id for collector in collectors])

        handler.data.refresh_from_db()
        self.assertEqual(handler.data.status, CleanTemplateStatus.PUBLISHED.value)
        self.assertIsNone(handler.data.snapshot)
        self.assertEqual(handler.data.etl_params["separator"], "|")
        self.assertEqual([item["id"] for item in result], [collector.collector_config_id for collector in collectors])
        self.assertTrue(all(item["status"] == CleanTemplateSyncStatus.FAILED.value for item in result))

    def test_sync_collectors_does_not_publish_deleted_template(self):
        template = self.create_template()
        template_id = template["clean_template_id"]
        stale_handler = CleanTemplateHandler(template_id)
        CleanTemplateHandler(template_id).destroy()

        with self.assertRaises(CleanTemplateNotExistException):
            stale_handler.sync_collectors([])

    def test_sync_collectors_only_schedules_active_authorized_collectors(self):
        template = self.create_template()
        template_id = template["clean_template_id"]
        allowed = self.create_collector(collector_config_name="allowed", clean_template_id=template_id)
        self.create_collector(collector_config_name="not-authorized", clean_template_id=template_id)
        self.create_collector(collector_config_name="inactive", clean_template_id=template_id, is_active=False)
        executor = MagicMock()
        executor.run.return_value = {
            allowed.collector_config_id: {
                "id": allowed.collector_config_id,
                "name": allowed.collector_config_name,
                "status": CleanTemplateSyncStatus.SUCCESS.value,
                "message": str(CleanTemplateSyncMessage.SUCCESS.value),
            }
        }

        with patch("apps.log_databus.handlers.clean.MultiExecuteFunc", return_value=executor):
            result = CleanTemplateHandler(template_id).sync_collectors([allowed.collector_config_id])

        self.assertEqual(result, [executor.run.return_value[allowed.collector_config_id]])
        self.assertEqual(executor.append.call_count, 1)
        self.assertEqual(executor.append.call_args.kwargs["result_key"], allowed.collector_config_id)

    def test_sync_collectors_returns_failed_when_executor_result_is_missing(self):
        template = self.create_template()
        collector = self.create_collector(clean_template_id=template["clean_template_id"])
        executor = MagicMock()
        executor.run.return_value = {}

        with patch("apps.log_databus.handlers.clean.MultiExecuteFunc", return_value=executor):
            result = CleanTemplateHandler(template["clean_template_id"]).sync_collectors(
                [collector.collector_config_id]
            )

        self.assertEqual(
            result,
            [
                {
                    "id": collector.collector_config_id,
                    "name": collector.collector_config_name,
                    "status": CleanTemplateSyncStatus.FAILED.value,
                    "message": str(CleanTemplateSyncMessage.FAILED.value),
                }
            ],
        )


class TestCleanTemplatePreview(CleanTemplateTestCase):
    PREVIEW_ERROR_MESSAGE = "字段提取预览失败，模板与日志样例格式不匹配，请切换模板或手动清洗"

    @patch("apps.log_databus.handlers.etl.EtlHandler.etl_preview", return_value={"fields": "raw log"})
    def test_text_preview_has_no_template_fields(self, mock_etl_preview):
        template = self.create_template(clean_type="bk_log_text", etl_fields=[])

        result = CleanTemplateHandler(template["clean_template_id"]).preview(data="raw log")

        self.assertEqual(
            result,
            {
                "fields": [],
                "match_rate": 100.0,
                "normal_count": 0,
                "abnormal_count": 0,
            },
        )
        mock_etl_preview.assert_called_once()

    def test_preview_raises_user_friendly_error_when_etl_preview_fails(self):
        template = self.create_template(clean_type="bk_log_json", etl_fields=[])

        with patch(
            "apps.log_databus.handlers.etl.EtlHandler.etl_preview",
            side_effect=EtlPreviewException(),
        ):
            with self.assertRaises(EtlPreviewException) as context:
                CleanTemplateHandler(template["clean_template_id"]).preview(data="not-json")

        self.assertEqual(context.exception.message, self.PREVIEW_ERROR_MESSAGE)
        self.assertEqual(
            EtlPreviewException().message,
            "字段提取预览失败，请检查提取规则与数据是否匹配",
        )

    def test_preview_converts_validation_error_to_user_friendly_error(self):
        template = self.create_template(clean_type="bk_log_regexp", etl_fields=[])

        with patch(
            "apps.log_databus.handlers.etl.EtlHandler.etl_preview",
            side_effect=ValidationError("无法匹配正则表达式"),
        ):
            with self.assertRaises(EtlPreviewException) as context:
                CleanTemplateHandler(template["clean_template_id"]).preview(data="not-matched")

        self.assertEqual(context.exception.message, self.PREVIEW_ERROR_MESSAGE)

    def test_preview_propagates_unexpected_etl_preview_errors(self):
        # 非预期异常（如数据平台 API 故障）不应被当作样例解析失败吞掉，
        # 保持原样抛出，由框架记录并返回 500。
        template = self.create_template(clean_type="bk_log_json", etl_fields=[])

        with patch(
            "apps.log_databus.handlers.etl.EtlHandler.etl_preview",
            side_effect=ApiResultError("数据平台不可用"),
        ):
            with self.assertRaises(ApiResultError):
                CleanTemplateHandler(template["clean_template_id"]).preview(data="not-json")

    def test_numeric_field_type_boundaries(self):
        normal_cases = (
            (-(2**31), "int"),
            (2**31 - 1, "int"),
            ("12.0", "int"),
            (-(2**63), "long"),
            (2**63 - 1, "long"),
            ("1.5", "double"),
        )
        for value, field_type in normal_cases:
            with self.subTest(value=value, field_type=field_type):
                self.assertIsNone(CleanTemplateHandler._get_field_error_type(value, field_type))

        mismatch_cases = (
            (-(2**31) - 1, "int"),
            (2**31, "int"),
            (-(2**63) - 1, "long"),
            (2**63, "long"),
            ("NaN", "double"),
            ("Infinity", "double"),
            ("-Infinity", "float"),
        )
        for value, field_type in mismatch_cases:
            with self.subTest(value=value, field_type=field_type):
                self.assertEqual(
                    CleanTemplateHandler._get_field_error_type(value, field_type),
                    "TYPE_MISMATCH",
                )

        self.assertEqual(CleanTemplateHandler._infer_field_type(-(2**31) - 1), "long")

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

        self.assertEqual([item["error_type"] for item in result], [None, "TYPE_MISMATCH", "EMPTY_VALUE"])
        self.assertTrue(all("status" not in item for item in result))
        self.assertEqual(result[1]["error_type"], "TYPE_MISMATCH")
        self.assertEqual(result[1]["inferred_field_type"], "string")
        self.assertEqual(result[2]["error_type"], "EMPTY_VALUE")


class TestCleanTemplateAssociation(CleanTemplateTestCase):
    def test_destroy_unlinks_collectors(self):
        template = self.create_template()
        collector = self.create_collector(
            clean_template_id=template["clean_template_id"],
        )
        clean_stash = CleanStash.objects.create(
            clean_template_id=template["clean_template_id"],
            clean_type="bk_log_text",
            etl_params={},
            etl_fields=[],
            collector_config_id=collector.collector_config_id,
            bk_biz_id=collector.bk_biz_id,
        )

        result = CleanTemplateHandler(template["clean_template_id"]).destroy()

        collector.refresh_from_db()
        self.assertEqual(result, template["clean_template_id"])
        self.assertFalse(CleanTemplate.objects.filter(clean_template_id=result).exists())
        self.assertIsNone(collector.clean_template_id)
        clean_stash.refresh_from_db()
        self.assertIsNone(clean_stash.clean_template_id)

    def test_destroy_refreshes_stale_template_before_soft_delete(self):
        template = self.create_template()
        template_id = template["clean_template_id"]
        stale_handler = CleanTemplateHandler(template_id)
        changed = copy.deepcopy(CREATE_PARAMS)
        changed.pop("bk_biz_id")
        changed["etl_params"]["separator"] = "|"
        CleanTemplateHandler(template_id).create_or_update(changed)

        stale_handler.destroy()

        deleted_template = CleanTemplate.origin_objects.get(clean_template_id=template_id)
        self.assertTrue(deleted_template.is_deleted)
        self.assertEqual(deleted_template.etl_params["separator"], "|")

    def test_prepare_clean_template_config_normalizes_legacy_fields(self):
        template = self.create_template(
            etl_fields=[
                {"field_name": "analyzed", "is_analyzed": True},
                {"field_name": "not_analyzed", "is_analyzed": False},
            ]
        )
        collector = self.create_collector()

        _, _, _, fields = TransferEtlHandler(collector.collector_config_id)._prepare_clean_template_config(
            template["clean_template_id"], "bk_log_text", {}, []
        )

        by_name = {field["field_name"]: field for field in fields}
        self.assertEqual(
            sorted(by_name["analyzed"]),
            ["field_name", "field_type", "is_analyzed", "is_built_in", "is_delete", "is_dimension", "is_time"],
        )
        self.assertEqual(by_name["analyzed"]["field_type"], "string")
        self.assertFalse(by_name["analyzed"]["is_delete"])
        self.assertFalse(by_name["analyzed"]["is_time"])
        self.assertFalse(by_name["analyzed"]["is_built_in"])
        self.assertFalse(by_name["analyzed"]["is_dimension"])
        self.assertTrue(by_name["not_analyzed"]["is_dimension"])

    def test_prepare_clean_template_config_normalizes_fixed_fields(self):
        template = self.create_template()
        collector = self.create_collector(clean_template_id=template["clean_template_id"])
        fixed_fields = [{"field_name": "fixed", "is_analyzed": True}]

        _, etl_config, etl_params, fields = TransferEtlHandler(
            collector.collector_config_id
        )._prepare_clean_template_config(
            template["clean_template_id"],
            "bk_log_json",
            {"source": "fixed"},
            fixed_fields,
            use_provided_clean_config=True,
        )

        self.assertEqual(etl_config, "bk_log_json")
        self.assertEqual(etl_params, {"source": "fixed"})
        self.assertEqual(fields[0]["field_name"], "fixed")
        self.assertEqual(fields[0]["field_type"], "string")
        self.assertFalse(fields[0]["is_delete"])
        self.assertFalse(fields[0]["is_dimension"])
        self.assertNotIn("field_type", fixed_fields[0])

    def test_update_or_create_legacy_template_fields_no_key_error(self):
        # 历史模板字段整体不完整，走真实 EtlStorage 链路（get_result_table_fields 会硬下标
        # is_delete/is_analyzed/is_time/is_dimension/field_type），验证统一规范化后不再 KeyError。
        template = self.create_template(
            clean_type="bk_log_json",
            etl_params={"retain_original_text": True},
            etl_fields=[
                {"field_name": "level", "is_analyzed": False},
                {"field_name": "message", "is_analyzed": True},
            ],
        )
        collector = self.create_collector()

        storage_handler = MagicMock()
        storage_handler.get_cluster_info_by_id.return_value = {
            "cluster_type": "elasticsearch",
            "cluster_config": {"version": "7.x", "custom_option": {}},
        }
        with (
            patch("apps.log_databus.handlers.etl.transfer.StorageHandler", return_value=storage_handler),
            patch.object(TransferEtlHandler, "check_es_storage_capacity"),
            patch(
                "apps.log_databus.handlers.etl.transfer.EtlStorage.get_instance",
                return_value=BkLogJsonEtlStorage(),
            ),
            patch.object(
                TransferEtlHandler,
                "_update_or_create_index_set",
                return_value={"index_set_id": 1, "scenario_id": "log"},
            ),
            patch("apps.log_databus.handlers.etl.transfer.CollectorHandler.create_clean_stash"),
            patch("apps.log_databus.handlers.etl.transfer.user_operation_record.delay"),
            patch("apps.api.TransferApi.get_result_table", side_effect=ApiResultError("")),
            patch(
                "apps.api.TransferApi.create_result_table",
                return_value={"table_id": "biz_706_clean_table"},
            ) as create_rt,
        ):
            TransferEtlHandler(collector.collector_config_id).update_or_create(
                table_id="clean_table",
                etl_config="bk_log_json",
                storage_cluster_id=1,
                retention=7,
                allocation_min_days=0,
                storage_replies=1,
                clean_template_id=template["clean_template_id"],
            )

        field_list = create_rt.call_args.args[0]["field_list"]
        user_fields = [field for field in field_list if field["field_name"] in {"level", "message"}]
        self.assertEqual(len(user_fields), 2)
        by_name = {field["field_name"]: field for field in user_fields}
        self.assertEqual(by_name["level"]["field_type"], "string")
        self.assertEqual(by_name["message"]["field_type"], "string")
        # is_dimension 会落到 es_doc_values / tag：非分词字段为维度，分词字段为指标
        self.assertEqual(by_name["level"]["tag"], "dimension")
        self.assertEqual(by_name["message"]["tag"], "metric")

    def test_update_or_create_handles_clean_template_id_tristate(self):
        template = self.create_template(clean_type="bk_log_json", etl_params={"retain_original_text": True})
        request_config = {
            "etl_config": "bk_log_text",
            "etl_params": {"request": "params"},
            "fields": [{"field_name": "request_field"}],
        }
        cases = (
            ("specified", None, True, template["clean_template_id"], "bk_log_json", template["clean_template_id"]),
            (
                "omitted",
                template["clean_template_id"],
                False,
                None,
                "bk_log_json",
                template["clean_template_id"],
            ),
            ("explicit-null", template["clean_template_id"], True, None, "bk_log_text", None),
        )

        storage_handler = MagicMock()
        storage_handler.get_cluster_info_by_id.return_value = {
            "cluster_type": "elasticsearch",
            "cluster_config": {"version": "7.x", "custom_option": {}},
        }
        etl_storage = MagicMock()
        with (
            patch("apps.log_databus.handlers.etl.transfer.StorageHandler", return_value=storage_handler),
            patch.object(TransferEtlHandler, "check_es_storage_capacity"),
            patch(
                "apps.log_databus.handlers.etl.transfer.EtlStorage.get_instance", return_value=etl_storage
            ) as get_etl_storage,
            patch.object(
                TransferEtlHandler,
                "_update_or_create_index_set",
                return_value={"index_set_id": 1, "scenario_id": "log"},
            ),
            patch.object(
                TransferEtlHandler,
                "_update_clean_template",
                autospec=True,
                side_effect=TransferEtlHandler._update_clean_template,
            ) as update_clean_template,
            patch("apps.log_databus.handlers.etl.transfer.CollectorHandler.create_clean_stash") as create_clean_stash,
            patch("apps.log_databus.handlers.etl.transfer.user_operation_record.delay"),
        ):
            for index, case in enumerate(cases):
                name, current_template_id, include_template_id, supplied_template_id, etl_config, expected_id = case
                with self.subTest(case=name):
                    collector = self.create_collector(
                        collector_config_name=f"collector-{name}",
                        clean_template_id=current_template_id,
                    )
                    params = {
                        **request_config,
                        "table_id": f"table_{index}",
                        "storage_cluster_id": 1,
                        "retention": 7,
                        "allocation_min_days": 0,
                        "storage_replies": 1,
                    }
                    if include_template_id:
                        params["clean_template_id"] = supplied_template_id

                    TransferEtlHandler(collector.collector_config_id).update_or_create(**params)

                    update_params = etl_storage.update_or_create_result_table.call_args.kwargs
                    expected_fields = copy.deepcopy(CREATE_PARAMS["etl_fields"])
                    for field in expected_fields:
                        field.setdefault("is_built_in", False)
                    self.assertEqual(
                        update_params["etl_params"],
                        {"retain_original_text": True} if expected_id else request_config["etl_params"],
                    )
                    self.assertEqual(
                        update_params["fields"],
                        expected_fields if expected_id else request_config["fields"],
                    )
                    collector.refresh_from_db()
                    self.assertEqual(collector.clean_template_id, expected_id)
                    self.assertEqual(
                        create_clean_stash.call_args.args[0]["clean_template_id"],
                        expected_id,
                    )
                    if include_template_id:
                        update_clean_template.assert_called_once()
                    else:
                        update_clean_template.assert_not_called()
                    get_etl_storage.assert_called_once_with(etl_config=etl_config)
                    get_etl_storage.reset_mock()
                    etl_storage.reset_mock()
                    update_clean_template.reset_mock()

    def test_etl_does_not_associate_deleted_template(self):
        template = self.create_template()
        collector = self.create_collector()
        handler = TransferEtlHandler(collector.collector_config_id)
        clean_template = CleanTemplate.objects.get(clean_template_id=template["clean_template_id"])

        clean_template.delete()
        with self.assertRaises(CleanTemplateNotExistException):
            handler._update_clean_template(clean_template)

        collector.refresh_from_db()
        self.assertIsNone(collector.clean_template_id)

    def test_etl_rejects_template_from_another_business(self):
        template = self.create_template()
        collector = self.create_collector(bk_biz_id=999)

        with self.assertRaises(CleanTemplateNotExistException):
            TransferEtlHandler(collector.collector_config_id)._validate_clean_template(template["clean_template_id"])
