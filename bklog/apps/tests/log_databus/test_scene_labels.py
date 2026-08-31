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

from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from apps.log_databus.constants import (
    SCENE_SEARCH_DIMENSIONS,
    ContainerCollectorType,
)
from apps.log_databus.handlers.collector.base import CollectorHandler
from apps.log_databus.models import CollectorConfig, ContainerCollectorConfig
from apps.log_search.models import (
    TAG_TYPE_INNER,
    TAG_TYPE_SCENE,
    TAG_TYPE_USER,
    IndexSetTag,
    LogIndexSet,
)


class TestCollectorHandlerSceneLabels(TestCase):
    @staticmethod
    def _new_handler(**overrides):
        data = {
            "collector_config_id": 1,
            "collector_scenario_id": "row",
            "custom_type": "log",
            "environment": "linux",
            "is_container_collector": False,
            "bcs_cluster_id": "",
            "bk_app_code": "bk_log_search",
            "table_id": "2_bklog.demo_collector",
            "collector_config_name_en": "demo_collector",
        }
        data.update(overrides)
        handler = CollectorHandler.__new__(CollectorHandler)
        handler.data = SimpleNamespace(**data)
        return handler

    def test_paas_collectors_build_expected_labels(self):
        cases = [
            (
                {
                    "bk_app_code": "bk_paas3",
                    "table_id": "space_4336327_bklog.fusion_system_mcp__default__stdout",
                },
                {
                    "scene": "bk_paas",
                    "app_code": "fusion_system_mcp",
                    "module_name": "default",
                    "stream": "stdout",
                },
            ),
            (
                {
                    "bk_app_code": "paasv3cli",
                    "table_id": "space_10438_bklog.bkai_cli__default__json",
                },
                {
                    "scene": "bk_paas",
                    "app_code": "bkai_cli",
                    "module_name": "default",
                    "stream": "json",
                },
            ),
            (
                {
                    "bk_app_code": "bk_paas3",
                    "table_id": "",
                    "collector_config_name_en": "my_app__api__json",
                },
                {
                    "scene": "bk_paas",
                    "app_code": "my_app",
                    "module_name": "api",
                    "stream": "json",
                },
            ),
        ]

        for attrs, expected in cases:
            with self.subTest(attrs=attrs):
                self.assertEqual(self._new_handler(**attrs)._build_scene_labels(), expected)

    def test_paas_precedes_custom_container_judgement(self):
        handler = self._new_handler(
            bk_app_code="bk_paas3",
            table_id="space_185_bklog.ai_harako_test__default__stdout",
            collector_scenario_id="custom",
            custom_type="log",
            is_container_collector=True,
        )

        with patch.object(handler, "_detect_container_stream") as mock_detect:
            self.assertEqual(handler._build_scene_labels()["scene"], "bk_paas")

        mock_detect.assert_not_called()

    def test_unparsable_or_untrusted_paas_name_falls_back(self):
        cases = [
            (
                {
                    "bk_app_code": "bk_paas3",
                    "table_id": "space_1_bklog.legacy_table",
                    "collector_scenario_id": "custom",
                    "is_container_collector": True,
                },
                "k8s",
            ),
            (
                {
                    "bk_app_code": "bk_log_search",
                    "table_id": "2_bklog.some_app__default__stdout",
                    "collector_scenario_id": "syslog",
                },
                "host",
            ),
        ]

        for attrs, expected_scene in cases:
            with self.subTest(attrs=attrs):
                self.assertEqual(self._new_handler(**attrs)._build_scene_labels()["scene"], expected_scene)


class TestRefreshResultTableLabelsCommand(TestCase):
    @staticmethod
    def _create_collector(name: str, **overrides) -> CollectorConfig:
        fields = {
            "collector_config_name": name,
            "collector_config_name_en": name,
            "bk_biz_id": 2,
            "category_id": "os",
            "collector_scenario_id": "row",
            "custom_type": "log",
            "environment": "linux",
            "bk_app_code": "bk_log_search",
            "table_id": f"2_bklog.{name}",
        }
        fields.update(overrides)
        return CollectorConfig.objects.create(**fields)

    @patch(
        "apps.log_databus.management.commands.refresh_result_table_labels.TransferApi.switch_result_table"
    )
    def test_backfill_reuses_all_scene_branches_without_n_plus_one(self, mock_switch_result_table):
        paas = self._create_collector(
            "paas",
            collector_scenario_id="custom",
            bk_app_code="bk_paas3",
            table_id="space_10438_bklog.bkai_cli__default__json",
        )
        otlp = self._create_collector(
            "otlp",
            collector_scenario_id="custom",
            custom_type="otlp_log",
            environment="container",
        )
        custom_container = self._create_collector(
            "custom_container",
            collector_scenario_id="custom",
            custom_type="log",
        )
        regular = self._create_collector("regular", collector_scenario_id="client")
        ContainerCollectorConfig.objects.create(
            collector_config_id=custom_container.collector_config_id,
            collector_type=ContainerCollectorType.CONTAINER,
        )
        ContainerCollectorConfig.objects.create(
            collector_config_id=custom_container.collector_config_id,
            collector_type=ContainerCollectorType.STDOUT,
        )

        with CaptureQueriesContext(connection) as queries:
            call_command(
                "refresh_result_table_labels",
                batch_size=2,
                sleep=0,
                stdout=StringIO(),
            )

        labels_by_table = {
            call.args[0]["table_id"]: call.args[0]["labels"] for call in mock_switch_result_table.call_args_list
        }
        self.assertEqual(
            labels_by_table[paas.table_id],
            {
                "scene": "bk_paas",
                "app_code": "bkai_cli",
                "module_name": "default",
                "stream": "json",
            },
        )
        self.assertEqual(labels_by_table[otlp.table_id], {"scene": "trpc"})
        self.assertEqual(labels_by_table[custom_container.table_id], {"scene": "k8s", "stream": "stdout"})
        self.assertEqual(labels_by_table[regular.table_id], {"scene": "client"})

        container_table = ContainerCollectorConfig._meta.db_table.lower()
        container_queries = [query for query in queries if container_table in query["sql"].lower()]
        self.assertEqual(len(container_queries), 2)


class TestSyncSceneTagsToIndexSet(TestCase):
    def test_sync_replaces_old_scene_tags_and_preserves_other_types(self):
        user_tag_id = IndexSetTag.get_tag_id("team", value="blue", tag_type=TAG_TYPE_USER)
        inner_tag_id = IndexSetTag.get_tag_id("trace", tag_type=TAG_TYPE_INNER)
        old_scene_tag_id = IndexSetTag.get_tag_id("scene", value="k8s", tag_type=TAG_TYPE_SCENE)
        old_cluster_tag_id = IndexSetTag.get_tag_id(
            "cluster_id", value="BCS-OLD", tag_type=TAG_TYPE_SCENE
        )
        index_set = LogIndexSet.objects.create(
            index_set_name="replace_scene_tags",
            space_uid="bkcc__2",
            scenario_id="log",
            tag_ids=[
                str(user_tag_id),
                str(inner_tag_id),
                str(old_scene_tag_id),
                str(old_cluster_tag_id),
            ],
            is_active=True,
        )
        handler = CollectorHandler.__new__(CollectorHandler)
        handler.data = SimpleNamespace(index_set_id=index_set.index_set_id)

        handler._sync_scene_tags_to_index_set(
            {
                "scene": "bk_paas",
                "app_code": "bkai_cli",
                "module_name": "default",
                "stream": "json",
            }
        )

        index_set.refresh_from_db()
        tag_ids = {str(tag_id) for tag_id in index_set.tag_ids}
        self.assertIn(str(user_tag_id), tag_ids)
        self.assertIn(str(inner_tag_id), tag_ids)
        self.assertNotIn(str(old_scene_tag_id), tag_ids)
        self.assertNotIn(str(old_cluster_tag_id), tag_ids)
        scene_tags = set(
            IndexSetTag.objects.filter(tag_id__in=tag_ids, tag_type=TAG_TYPE_SCENE).values_list("name", "value")
        )
        self.assertEqual(
            scene_tags,
            {
                ("scene", "bk_paas"),
                ("app_code", "bkai_cli"),
                ("module_name", "default"),
                ("stream", "json"),
            },
        )


class TestSyncSceneLabels(TestCase):
    @staticmethod
    def _new_handler(**overrides):
        data = {
            "collector_config_id": 1,
            "collector_scenario_id": "row",
            "custom_type": "log",
            "environment": "container",
            "is_container_collector": True,
            "bcs_cluster_id": "BCS-K8S-27158",
            "bk_app_code": "bk_log_search",
            "table_id": "space_4283579_bklog.demo_collector",
            "collector_config_name_en": "demo_collector",
            "index_set_id": None,
        }
        data.update(overrides)
        handler = CollectorHandler.__new__(CollectorHandler)
        handler.data = SimpleNamespace(**data)
        return handler

    @patch("apps.log_databus.handlers.collector.base.TransferApi.switch_result_table")
    def test_sync_pushes_labels_to_result_table_and_index_set(self, mock_switch_result_table):
        index_set = LogIndexSet.objects.create(
            index_set_name="scene_labels_sync",
            space_uid="bkcc__2",
            scenario_id="log",
            is_active=True,
        )
        handler = self._new_handler(index_set_id=index_set.index_set_id)

        with patch.object(handler, "_detect_container_stream", return_value="file"):
            handler.sync_scene_labels()

        expected_labels = {"scene": "k8s", "cluster_id": "BCS-K8S-27158", "stream": "file"}
        params = mock_switch_result_table.call_args.args[0]
        self.assertEqual(params["table_id"], "space_4283579_bklog.demo_collector")
        self.assertEqual(params["labels"], expected_labels)

        index_set.refresh_from_db()
        scene_tags = set(
            IndexSetTag.objects.filter(tag_id__in=index_set.tag_ids, tag_type=TAG_TYPE_SCENE).values_list(
                "name", "value"
            )
        )
        self.assertEqual(scene_tags, set(expected_labels.items()))

    @patch("apps.log_databus.handlers.collector.base.TransferApi.switch_result_table")
    def test_sync_skipped_before_result_table_created(self, mock_switch_result_table):
        handler = self._new_handler(table_id="")

        handler.sync_scene_labels()

        mock_switch_result_table.assert_not_called()


class TestCleanConfigEntryBuildsLabels(SimpleTestCase):
    """清洗配置 HTTP 入口必须复用 CollectorHandler 封装，否则会漏掉场景标签。"""

    @staticmethod
    def _call_view(table_id):
        from apps.log_databus.views.collector_views import CollectorViewSet

        view = CollectorViewSet()
        params = {"table_id": "demo_collector", "need_assessment": False, "assessment_config": None}
        view.params_valid = MagicMock(return_value=params)

        with (
            patch("apps.log_databus.views.collector_views.EtlHandler.get_instance") as mock_etl_handler,
            patch("apps.log_databus.views.collector_views.CollectorHandler.get_instance") as mock_get_instance,
        ):
            mock_etl_handler.return_value.itsm_pre_hook.side_effect = lambda data, _: (data, True)
            collector_handler = mock_get_instance.return_value
            collector_handler.data = SimpleNamespace(table_id=table_id)
            view.update_or_create_clean_config(SimpleNamespace(), collector_config_id=1)

        return mock_etl_handler.return_value, collector_handler

    def test_entry_delegates_to_collector_handler(self):
        etl_handler, collector_handler = self._call_view("2_bklog.demo_collector")

        etl_handler.update_or_create.assert_not_called()
        collector_handler.create_or_update_clean_config.assert_called_once_with(
            is_update=True, params={"table_id": "demo_collector"}
        )

    def test_entry_treats_collector_without_result_table_as_create(self):
        _etl_handler, collector_handler = self._call_view("")

        self.assertIs(collector_handler.create_or_update_clean_config.call_args.kwargs["is_update"], False)


class TestPaasSceneDimensions(TestCase):
    def test_paas_stream_choices_match_table_name_convention(self):
        stream_dimension = next(
            dimension for dimension in SCENE_SEARCH_DIMENSIONS["bk_paas"] if dimension["key"] == "stream"
        )

        self.assertEqual(
            [choice["id"] for choice in stream_dimension["choices"]],
            ["stdout", "json"],
        )
