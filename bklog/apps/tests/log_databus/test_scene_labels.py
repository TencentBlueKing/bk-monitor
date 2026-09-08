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

from apps.exceptions import ApiResultError
from apps.feature_toggle.models import FeatureToggle
from apps.feature_toggle.plugins.constants import SCENE_SEARCH
from apps.log_databus.constants import (
    SCENE_SEARCH_DIMENSIONS,
    ContainerCollectorType,
)
from apps.log_databus.handlers.collector.base import CollectorHandler
from apps.log_databus.handlers.collector.k8s import K8sCollectorHandler
from apps.log_databus.handlers.scene import (
    is_scene_search_released,
    refresh_scene_labels,
    release_scene_search,
    run_scene_search_sync,
)
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
                self.assertEqual(self._new_handler(**attrs).build_scene_labels(), expected)

    def test_paas_precedes_custom_container_judgement(self):
        handler = self._new_handler(
            bk_app_code="bk_paas3",
            table_id="space_185_bklog.ai_harako_test__default__stdout",
            collector_scenario_id="custom",
            custom_type="log",
            is_container_collector=True,
        )

        with patch.object(handler, "_detect_container_stream") as mock_detect:
            self.assertEqual(handler.build_scene_labels()["scene"], "bk_paas")

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
                self.assertEqual(self._new_handler(**attrs).build_scene_labels()["scene"], expected_scene)


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
    def _create_index_set(name: str) -> LogIndexSet:
        return LogIndexSet.objects.create(
            index_set_name=name,
            space_uid="bkcc__2",
            scenario_id="log",
            is_active=True,
        )

    @staticmethod
    def _get_scene_tags(index_set: LogIndexSet) -> set[tuple[str, str]]:
        index_set.refresh_from_db()
        return set(
            IndexSetTag.objects.filter(
                tag_id__in=index_set.tag_ids,
                tag_type=TAG_TYPE_SCENE,
            ).values_list("name", "value")
        )

    @patch("apps.log_databus.handlers.scene.TransferApi.switch_result_table")
    def test_backfill_reuses_all_scene_branches_without_n_plus_one(self, mock_switch_result_table):
        paas_index_set = self._create_index_set("paas")
        paas = self._create_collector(
            "paas",
            collector_scenario_id="custom",
            bk_app_code="bk_paas3",
            table_id="space_10438_bklog.bkai_cli__default__json",
            index_set_id=paas_index_set.index_set_id,
        )
        otlp_index_set = self._create_index_set("otlp")
        otlp = self._create_collector(
            "otlp",
            collector_scenario_id="custom",
            custom_type="otlp_log",
            environment="container",
            index_set_id=otlp_index_set.index_set_id,
        )
        custom_container_index_set = self._create_index_set("custom_container")
        custom_container = self._create_collector(
            "custom_container",
            collector_scenario_id="custom",
            custom_type="log",
            index_set_id=custom_container_index_set.index_set_id,
        )
        index_set = self._create_index_set("regular")
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

    @patch("apps.log_databus.handlers.scene.TransferApi.switch_result_table")
    def test_backfill_skips_collector_without_index_set(self, mock_switch_result_table):
        self._create_collector("without_index_set", collector_scenario_id="client")

        call_command("refresh_result_table_labels", sleep=0, stdout=StringIO())

        mock_switch_result_table.assert_not_called()

    @patch(
        "apps.log_databus.handlers.scene.TransferApi.get_result_table",
        return_value={"table_id": "2_bklog.failed_backfill"},
    )
    @patch(
        "apps.log_databus.handlers.scene.TransferApi.switch_result_table",
        side_effect=RuntimeError("metadata unavailable"),
    )
    def test_backfill_fails_without_updating_local_tags(self, _mock_switch_result_table, _mock_get_result_table):
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


class TestRefreshSceneLabelsHandler(TestCase):
    """场景标签回填公共函数与转正逻辑的单元测试。"""

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
    def _create_index_set(name: str, scene_tags: dict) -> LogIndexSet:
        tag_ids = [
            str(IndexSetTag.get_tag_id(name=key, value=value, tag_type=TAG_TYPE_SCENE))
            for key, value in scene_tags.items()
        ]
        return LogIndexSet.objects.create(
            index_set_name=name,
            space_uid="bkcc__2",
            scenario_id="log",
            tag_ids=tag_ids,
            is_active=True,
        )

    def test_refresh_records_missing_result_table_as_failure(self):
        """RT 不存在同样记录为失败，由人工通过远端比较命令处理。"""
        index_set = self._create_index_set("missing_rt", {"scene": "host"})
        collector = self._create_collector(
            "missing_rt", collector_scenario_id="client", index_set_id=index_set.index_set_id
        )

        with patch(
            "apps.log_databus.handlers.scene.TransferApi.switch_result_table",
            side_effect=ApiResultError("result table not exist", code="RESULT_TABLE_NOT_FOUND"),
        ):
            result = refresh_scene_labels(sleep=0)

        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["failed_result_table_ids"], [collector.table_id])

    def test_scene_refresh_task_is_registered(self):
        from django.conf import settings

        self.assertIn("apps.log_databus.tasks.scene", settings.CELERY_IMPORTS)

    def test_steady_mode_skips_when_local_tags_match(self):
        """稳态：本地已一致则跳过，不写远端。"""
        index_set = self._create_index_set("steady_match", {"scene": "client"})
        self._create_collector("steady_match", collector_scenario_id="client", index_set_id=index_set.index_set_id)

        with patch("apps.log_databus.handlers.scene.TransferApi.switch_result_table") as mock_switch:
            result = refresh_scene_labels(sleep=0)

        mock_switch.assert_not_called()
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["success"], 0)

    def test_steady_mode_writes_when_local_tags_differ(self):
        """稳态：本地不一致才写远端。"""
        index_set = self._create_index_set("steady_diff", {"scene": "host"})
        self._create_collector("steady_diff", collector_scenario_id="client", index_set_id=index_set.index_set_id)

        with patch("apps.log_databus.handlers.scene.TransferApi.switch_result_table") as mock_switch:
            result = refresh_scene_labels(sleep=0)

        self.assertEqual(mock_switch.call_count, 1)
        self.assertEqual(result["success"], 1)
        self.assertEqual(result["skipped"], 0)

    def test_refresh_uses_cursor_pagination_for_new_configs(self):
        """刷新期间新增的采集项只要 ID 更大，也应在本轮被游标分页处理。"""
        first_index_set = self._create_index_set("cursor_first", {"scene": "host"})
        first_collector = self._create_collector(
            "cursor_first", collector_scenario_id="client", index_set_id=first_index_set.index_set_id
        )
        created_second = False

        def switch_result_table(params):
            nonlocal created_second
            if not created_second:
                second_index_set = self._create_index_set("cursor_second", {"scene": "host"})
                self._create_collector(
                    "cursor_second",
                    collector_scenario_id="client",
                    index_set_id=second_index_set.index_set_id,
                )
                created_second = True

        with patch(
            "apps.log_databus.handlers.scene.TransferApi.switch_result_table",
            side_effect=switch_result_table,
        ) as mock_switch:
            result = refresh_scene_labels(batch_size=1, sleep=0)

        self.assertEqual(result["success"], 2)
        self.assertEqual(mock_switch.call_count, 2)
        self.assertEqual(
            [call.args[0]["table_id"] for call in mock_switch.call_args_list],
            [first_collector.table_id, "2_bklog.cursor_second"],
        )

    def test_manual_remote_compare_skips_when_result_table_labels_match(self):
        """手动命令可用远端 RT 标签判断，无须依赖本地标签是否已修复。"""
        index_set = self._create_index_set("remote_match", {"scene": "host"})
        collector = self._create_collector(
            "remote_match", collector_scenario_id="client", index_set_id=index_set.index_set_id
        )

        with (
            patch(
                "apps.log_databus.handlers.scene.TransferApi.get_result_table",
                return_value={"table_id": collector.table_id, "labels": {"scene": "client"}},
            ),
            patch("apps.log_databus.handlers.scene.TransferApi.switch_result_table") as mock_switch,
        ):
            call_command("refresh_result_table_labels", compare_remote=True, sleep=0, stdout=StringIO())

        mock_switch.assert_not_called()

    def test_first_sync_uses_remote_compare(self):
        """首次定时任务以远端 ResultTable.labels 为校正基准。"""
        FeatureToggle.objects.update_or_create(name=SCENE_SEARCH, defaults={"status": "debug"})
        index_set = self._create_index_set("first_local_match", {"scene": "client"})
        collector = self._create_collector(
            "first_local_match", collector_scenario_id="client", index_set_id=index_set.index_set_id
        )

        with (
            patch("apps.log_databus.handlers.scene.TransferApi.switch_result_table") as mock_switch,
            patch(
                "apps.log_databus.handlers.scene.TransferApi.get_result_table",
                return_value={"table_id": collector.table_id, "labels": {}},
            ) as mock_get_result_table,
        ):
            run_scene_search_sync()

        mock_get_result_table.assert_called_once_with({"table_id": collector.table_id})
        mock_switch.assert_called_once()
        self.assertEqual(FeatureToggle.objects.get(name=SCENE_SEARCH).status, "on")

    def test_release_scene_search_sets_status_and_mark(self):
        FeatureToggle.objects.update_or_create(name=SCENE_SEARCH, defaults={"status": "debug"})

        self.assertTrue(release_scene_search())

        toggle = FeatureToggle.objects.get(name=SCENE_SEARCH)
        self.assertEqual(toggle.status, "on")
        self.assertTrue(toggle.feature_config.get("scene_search_released"))
        self.assertTrue(is_scene_search_released())

    def test_release_scene_search_preserves_existing_feature_config(self):
        FeatureToggle.objects.update_or_create(
            name=SCENE_SEARCH,
            defaults={"status": "debug", "feature_config": {"existing_option": "keep"}},
        )

        self.assertTrue(release_scene_search())

        toggle = FeatureToggle.objects.get(name=SCENE_SEARCH)
        self.assertEqual(
            toggle.feature_config,
            {"existing_option": "keep", "scene_search_released": True},
        )

    def test_run_first_sync_releases_when_no_failure(self):
        """周期任务首次：全量校正无失败 → 翻开关并打标记。"""
        FeatureToggle.objects.update_or_create(name=SCENE_SEARCH, defaults={"status": "debug"})
        index_set = self._create_index_set("first_sync", {"scene": "host"})
        self._create_collector("first_sync", collector_scenario_id="client", index_set_id=index_set.index_set_id)

        with (
            patch("apps.log_databus.handlers.scene.TransferApi.switch_result_table"),
            patch(
                "apps.log_databus.handlers.scene.TransferApi.get_result_table",
                return_value={"table_id": "2_bklog.first_sync", "labels": {}},
            ),
        ):
            run_scene_search_sync()

        toggle = FeatureToggle.objects.get(name=SCENE_SEARCH)
        self.assertEqual(toggle.status, "on")
        self.assertTrue(toggle.feature_config.get("scene_search_released"))

    def test_run_first_sync_defers_release_when_failures(self):
        """首次校正有失败项时不翻开关、不打 released 标记，留给下一轮重试。"""
        FeatureToggle.objects.update_or_create(name=SCENE_SEARCH, defaults={"status": "debug"})
        index_set = self._create_index_set("first_sync_defer_failure", {"scene": "host"})
        self._create_collector(
            "first_sync_defer_failure", collector_scenario_id="client", index_set_id=index_set.index_set_id
        )

        with (
            patch(
                "apps.log_databus.handlers.scene.TransferApi.switch_result_table",
                side_effect=RuntimeError("metadata unavailable"),
            ),
            patch(
                "apps.log_databus.handlers.scene.TransferApi.get_result_table",
                return_value={"table_id": "2_bklog.first_sync_defer_failure"},
            ),
        ):
            result = run_scene_search_sync()

        toggle = FeatureToggle.objects.get(name=SCENE_SEARCH)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["failed_result_table_ids"], ["2_bklog.first_sync_defer_failure"])
        self.assertEqual(toggle.status, "debug")
        self.assertFalse((toggle.feature_config or {}).get("scene_search_released"))

    def test_run_first_sync_retries_and_releases_after_recovery(self):
        """失败项下一轮重试成功后自动转正，验证自愈路径。"""
        FeatureToggle.objects.update_or_create(name=SCENE_SEARCH, defaults={"status": "debug"})
        index_set = self._create_index_set("first_sync_retry", {"scene": "host"})
        self._create_collector("first_sync_retry", collector_scenario_id="client", index_set_id=index_set.index_set_id)

        with (
            patch(
                "apps.log_databus.handlers.scene.TransferApi.switch_result_table",
                side_effect=RuntimeError("metadata unavailable"),
            ),
            patch(
                "apps.log_databus.handlers.scene.TransferApi.get_result_table",
                return_value={"table_id": "2_bklog.first_sync_retry"},
            ),
        ):
            run_scene_search_sync()

        self.assertEqual(FeatureToggle.objects.get(name=SCENE_SEARCH).status, "debug")

        with (
            patch("apps.log_databus.handlers.scene.TransferApi.switch_result_table"),
            patch(
                "apps.log_databus.handlers.scene.TransferApi.get_result_table",
                return_value={"table_id": "2_bklog.first_sync_retry", "labels": {}},
            ),
        ):
            run_scene_search_sync()

        toggle = FeatureToggle.objects.get(name=SCENE_SEARCH)
        self.assertEqual(toggle.status, "on")
        self.assertTrue((toggle.feature_config or {}).get("scene_search_released"))

    def test_run_first_sync_does_not_override_manual_off(self):
        """首次校正完成也必须保留人工 off 的止血语义。"""
        FeatureToggle.objects.update_or_create(name=SCENE_SEARCH, defaults={"status": "off"})
        index_set = self._create_index_set("first_sync_manual_off", {"scene": "host"})
        self._create_collector(
            "first_sync_manual_off",
            collector_scenario_id="client",
            index_set_id=index_set.index_set_id,
        )

        with (
            patch("apps.log_databus.handlers.scene.TransferApi.switch_result_table"),
            patch(
                "apps.log_databus.handlers.scene.TransferApi.get_result_table",
                return_value={"table_id": "2_bklog.first_sync_manual_off", "labels": {}},
            ),
        ):
            run_scene_search_sync()

        toggle = FeatureToggle.objects.get(name=SCENE_SEARCH)
        self.assertEqual(toggle.status, "off")
        self.assertFalse((toggle.feature_config or {}).get("scene_search_released"))

    def test_first_sync_marks_existing_on_toggle_as_released(self):
        """已处于 on 的环境首次校正完成后补写发布标记。"""
        FeatureToggle.objects.update_or_create(name=SCENE_SEARCH, defaults={"status": "on"})
        index_set = self._create_index_set("first_sync_existing_on", {"scene": "client"})
        collector = self._create_collector(
            "first_sync_existing_on", collector_scenario_id="client", index_set_id=index_set.index_set_id
        )

        with (
            patch("apps.log_databus.handlers.scene.TransferApi.switch_result_table"),
            patch(
                "apps.log_databus.handlers.scene.TransferApi.get_result_table",
                return_value={"table_id": collector.table_id, "labels": {"scene": "client"}},
            ),
        ):
            run_scene_search_sync()

        toggle = FeatureToggle.objects.get(name=SCENE_SEARCH)
        self.assertEqual(toggle.status, "on")
        self.assertTrue((toggle.feature_config or {}).get("scene_search_released"))

        toggle.status = "debug"
        toggle.save(update_fields=["status"])
        with patch("apps.log_databus.handlers.scene.TransferApi.switch_result_table"):
            run_scene_search_sync()

        self.assertEqual(FeatureToggle.objects.get(name=SCENE_SEARCH).status, "debug")

    def test_run_steady_uses_local_compare_after_release(self):
        """周期任务已 released：走稳态本地对比，不再翻开关。"""
        FeatureToggle.objects.update_or_create(
            name=SCENE_SEARCH,
            defaults={"status": "on", "feature_config": {"scene_search_released": True}},
        )
        index_set = self._create_index_set("steady_released", {"scene": "client"})
        self._create_collector("steady_released", collector_scenario_id="client", index_set_id=index_set.index_set_id)

        with patch("apps.log_databus.handlers.scene.TransferApi.switch_result_table") as mock_switch:
            run_scene_search_sync()

        mock_switch.assert_not_called()


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

        K8sCollectorHandler._sync_bcs_scene_labels(
            path_collector.collector_config_id,
            std_collector.collector_config_id,
        )

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

    def test_sync_metadata_failure_does_not_propagate_or_update_local_tags(self):
        collector = self._create_collector("bcs_failed", ContainerCollectorType.CONTAINER)

        with patch(
            "apps.log_databus.handlers.collector.k8s.TransferApi.switch_result_table",
            side_effect=RuntimeError("metadata unavailable"),
        ):
            with patch.object(K8sCollectorHandler, "_sync_scene_tags_to_index_set") as mock_sync_tags:
                K8sCollectorHandler._sync_bcs_scene_labels(collector.collector_config_id)

        mock_sync_tags.assert_not_called()

    def test_schedule_defers_bcs_sync_until_transaction_commit(self):
        handler = K8sCollectorHandler()
        collector = self._create_collector("bcs_deferred", ContainerCollectorType.CONTAINER)

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            handler._schedule_bcs_scene_label_sync(collector)

        self.assertEqual(len(callbacks), 1)
        with patch.object(K8sCollectorHandler, "_sync_bcs_scene_labels") as mock_sync_labels:
            callbacks[0]()
        mock_sync_labels.assert_called_once_with(collector.collector_config_id)

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
        with patch.object(handler, "_schedule_bcs_scene_label_sync") as mock_sync_labels:
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
