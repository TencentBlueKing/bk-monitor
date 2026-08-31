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
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.feature_toggle.models import FeatureToggle
from apps.feature_toggle.plugins.constants import SCENE_SEARCH
from apps.log_databus.constants import (
    SCENE_SEARCH_DIMENSIONS,
    ContainerCollectorType,
)
from apps.log_databus.handlers.collector.base import CollectorHandler
from apps.log_databus.handlers.collector.k8s import K8sCollectorHandler
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

    @staticmethod
    def _get_scene_tags(index_set: LogIndexSet) -> set[tuple[str, str]]:
        index_set.refresh_from_db()
        return set(
            IndexSetTag.objects.filter(
                tag_id__in=index_set.tag_ids,
                tag_type=TAG_TYPE_SCENE,
            ).values_list("name", "value")
        )

    @patch("apps.log_databus.management.commands.refresh_result_table_labels.TransferApi.switch_result_table")
    def test_skip_refresh_when_scene_search_is_already_enabled(self, mock_switch_result_table):
        FeatureToggle.objects.update_or_create(name=SCENE_SEARCH, defaults={"status": "on"})
        self._create_collector("already_enabled")
        output = StringIO()

        call_command("refresh_result_table_labels", enable_scene_search=True, sleep=0, stdout=output)

        mock_switch_result_table.assert_not_called()
        self.assertIn("already enabled", output.getvalue())

    @patch("apps.log_databus.management.commands.refresh_result_table_labels.TransferApi.switch_result_table")
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
        index_set = LogIndexSet.objects.create(
            index_set_name="regular",
            space_uid="bkcc__2",
            scenario_id="log",
            is_active=True,
        )
        regular = self._create_collector(
            "regular",
            collector_scenario_id="client",
            index_set_id=index_set.index_set_id,
        )
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
        self.assertEqual(self._get_scene_tags(index_set), {("scene", "client")})

    @patch(
        "apps.log_databus.management.commands.refresh_result_table_labels.TransferApi.switch_result_table",
        side_effect=RuntimeError("metadata unavailable"),
    )
    def test_backfill_fails_without_updating_local_tags(self, _mock_switch_result_table):
        old_scene_tag_id = IndexSetTag.get_tag_id("scene", value="host", tag_type=TAG_TYPE_SCENE)
        index_set = LogIndexSet.objects.create(
            index_set_name="failed_backfill",
            space_uid="bkcc__2",
            scenario_id="log",
            tag_ids=[str(old_scene_tag_id)],
            is_active=True,
        )
        self._create_collector(
            "failed_backfill",
            collector_scenario_id="client",
            index_set_id=index_set.index_set_id,
        )

        call_command(
            "refresh_result_table_labels",
            sleep=0,
            stdout=StringIO(),
        )

        self.assertEqual(self._get_scene_tags(index_set), {("scene", "host")})


class TestSyncSceneTagsToIndexSet(TestCase):
    def test_sync_replaces_old_scene_tags_and_preserves_other_types(self):
        user_tag_id = IndexSetTag.get_tag_id("team", value="blue", tag_type=TAG_TYPE_USER)
        inner_tag_id = IndexSetTag.get_tag_id("trace", tag_type=TAG_TYPE_INNER)
        old_scene_tag_id = IndexSetTag.get_tag_id("scene", value="k8s", tag_type=TAG_TYPE_SCENE)
        old_cluster_tag_id = IndexSetTag.get_tag_id("cluster_id", value="BCS-OLD", tag_type=TAG_TYPE_SCENE)
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


class TestSyncBcsSceneLabels(TestCase):
    @staticmethod
    def _create_collector(name: str, collector_type: str) -> CollectorConfig:
        collector = CollectorConfig.objects.create(
            collector_config_name=name,
            collector_config_name_en=name,
            bk_biz_id=2,
            category_id="os",
            collector_scenario_id="row",
            custom_type="log",
            environment="container",
            bcs_cluster_id="BCS-NEW",
            table_id=f"2_bklog.{name}",
        )
        ContainerCollectorConfig.objects.create(
            collector_config_id=collector.collector_config_id,
            collector_type=collector_type,
        )
        return collector

    @patch.object(K8sCollectorHandler, "_sync_scene_tags_to_index_set")
    @patch("apps.log_databus.handlers.collector.k8s.TransferApi.switch_result_table")
    def test_sync_updates_result_tables_and_index_sets(self, mock_switch_result_table, mock_sync_tags):
        path_collector = self._create_collector("bcs_path", ContainerCollectorType.CONTAINER)
        std_collector = self._create_collector("bcs_std", ContainerCollectorType.STDOUT)

        K8sCollectorHandler._sync_bcs_scene_labels(path_collector, std_collector)

        expected_labels = {
            path_collector.table_id: {"scene": "k8s", "cluster_id": "BCS-NEW", "stream": "file"},
            std_collector.table_id: {"scene": "k8s", "cluster_id": "BCS-NEW", "stream": "stdout"},
        }
        self.assertEqual(
            {call.args[0]["table_id"]: call.args[0]["labels"] for call in mock_switch_result_table.call_args_list},
            expected_labels,
        )
        self.assertEqual(
            [call.args[0] for call in mock_sync_tags.call_args_list],
            list(expected_labels.values()),
        )

    @patch("apps.log_databus.handlers.collector.k8s.IndexSetHandler")
    def test_update_syncs_existing_and_new_collectors(self, _mock_index_set_handler):
        rule_id = 100
        handler = K8sCollectorHandler()
        names = handler._generate_collector_config_name("BCS-NEW", "rule", "rule")
        path_name = names["bcs_path_collector"]
        path_collector = CollectorConfig.objects.create(
            collector_config_name=path_name["collector_config_name"],
            collector_config_name_en=path_name["collector_config_name_en"],
            bk_biz_id=2,
            category_id="os",
            collector_scenario_id="row",
            custom_type="log",
            environment="container",
            bcs_cluster_id="BCS-OLD",
            table_id="2_bklog.rule_path",
            index_set_id=1,
            rule_id=rule_id,
            is_active=False,
        )
        ContainerCollectorConfig.objects.create(
            collector_config_id=path_collector.collector_config_id,
            collector_type=ContainerCollectorType.CONTAINER,
            rule_id=rule_id,
        )

        std_name = names["bcs_std_collector"]

        def create_stdout_collector(params, **_kwargs):
            return CollectorConfig.objects.create(
                collector_config_name=std_name["collector_config_name"],
                collector_config_name_en=std_name["collector_config_name_en"],
                bk_biz_id=2,
                category_id="os",
                collector_scenario_id="row",
                custom_type="log",
                environment="container",
                bcs_cluster_id=params["bcs_cluster_id"],
                table_id="2_bklog.rule_std",
                index_set_id=2,
                rule_id=rule_id,
                is_active=False,
            )

        data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-NEW",
            "collector_config_name": "rule",
            "collector_config_name_en": "rule",
            "custom_type": "log",
            "category_id": "os",
            "description": "updated",
            "add_pod_label": False,
            "extra_labels": [],
            "config": [
                {
                    "paths": ["/var/log/app.log"],
                    "enable_stdout": True,
                    "namespaces": [],
                    "namespaces_exclude": [],
                    "data_encoding": "UTF-8",
                    "conditions": {},
                    "container": {},
                    "label_selector": {},
                    "annotation_selector": {},
                }
            ],
        }
        with patch.object(handler, "_sync_bcs_scene_labels") as mock_sync_labels:
            with (
                patch.object(handler, "_get_bcs_config", return_value={"data_link_id": 0, "storage_cluster_id": 1}),
                patch.object(handler, "_create_bcs_collector", side_effect=create_stdout_collector),
                patch.object(handler, "compare_config"),
                patch.object(handler, "_send_create_notify"),
            ):
                handler.update_bcs_container_config(data, rule_id)

        path_collector.refresh_from_db()
        std_collector = CollectorConfig.objects.get(
            rule_id=rule_id,
            collector_config_name_en=std_name["collector_config_name_en"],
        )
        self.assertEqual(path_collector.bcs_cluster_id, "BCS-NEW")
        mock_sync_labels.assert_called_once_with(path_collector, std_collector)


class TestPaasSceneDimensions(TestCase):
    def test_paas_stream_choices_match_table_name_convention(self):
        stream_dimension = next(
            dimension for dimension in SCENE_SEARCH_DIMENSIONS["bk_paas"] if dimension["key"] == "stream"
        )

        self.assertEqual(
            [choice["id"] for choice in stream_dimension["choices"]],
            ["stdout", "json"],
        )
