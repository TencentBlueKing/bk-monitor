from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils.translation import override

from apps.log_clustering.handlers.regex_template import RegexTemplateHandler
from apps.log_clustering.models import ClusteringConfig, RegexTemplate
from apps.log_search.constants import FavoriteVisibleType, IndexSetDataType, IndexSetType
from apps.log_search.handlers.index_set import IndexSetHandler
from apps.log_search.handlers.search.favorite_handlers import FavoriteHandler
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.index_set_name import display_index_set_name
from apps.log_search.models import (
    Favorite,
    LogIndexSet,
    LogIndexSetData,
    Scenario,
    UserIndexSetSearchHistory,
)


class DisplayIndexSetNameTest(SimpleTestCase):
    def test_stored_prefix_is_rendered_in_current_language(self):
        for language, prefix in (("zh-cn", "[采集项]"), ("en", "[collection item]")):
            with override(language):
                for stored_prefix in ("[采集项]", "[collection item]"):
                    with self.subTest(language=language, stored_prefix=stored_prefix):
                        self.assertEqual(
                            display_index_set_name(stored_prefix + "[采集项]服务", 1), prefix + "[采集项]服务"
                        )

    def test_only_known_leading_prefix_of_collector_is_changed(self):
        with override("en"):
            for name, collector_id in (
                ("[采集项]自定义索引", None),
                ("[采集项]自定义索引", 0),
                ("前缀[采集项]服务", 1),
                ("[采集项其他]服务", 1),
                ("服务", 1),
                ("", 1),
            ):
                with self.subTest(name=name, collector_id=collector_id):
                    self.assertEqual(display_index_set_name(name, collector_id), name)


class IndexSetNameI18nIntegrationTest(TestCase):
    SPACE = "bkcc__2"
    USER = "admin"

    def setUp(self):
        self.collector = LogIndexSet.objects.create(
            index_set_name="[采集项]服务", collector_config_id=1001, space_uid=self.SPACE, scenario_id=Scenario.LOG
        )
        self.custom = LogIndexSet.objects.create(
            index_set_name="[采集项]自定义", space_uid=self.SPACE, scenario_id=Scenario.LOG
        )
        for index_set in (self.collector, self.custom):
            LogIndexSetData.objects.create(
                index_set_id=index_set.index_set_id,
                result_table_id=f"2_bklog.test_{index_set.index_set_id}",
                type=IndexSetDataType.RESULT_TABLE.value,
                apply_status=LogIndexSetData.Status.NORMAL,
                scenario_id=Scenario.LOG,
                bk_biz_id=2,
            )
        for target, value in (
            ("apps.log_search.handlers.index_set.IndexSetHandler.get_all_related_space_uids", [self.SPACE]),
            ("apps.log_search.models.space_uid_to_bk_biz_id", 2),
            ("apps.log_search.models.fetch_request_username", self.USER),
            ("apps.log_search.models.LogIndexSet.no_data_check_time", None),
            ("apps.log_search.models.LogIndexSet.batch_get_is_native_doris", {}),
        ):
            patcher = patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_selector_and_rename_keep_database_name(self):
        with override("en"):
            result = IndexSetHandler.get_user_index_set(self.SPACE)
            names = {item["index_set_id"]: item["index_set_name"] for item in result}
            self.assertEqual(names[self.collector.index_set_id], "[collection item]服务")
            self.assertEqual(names[self.custom.index_set_id], "[采集项]自定义")
            self.assertIn("服务", names[self.collector.index_set_id])
        self.collector.refresh_from_db()
        self.assertEqual(self.collector.index_set_name, "[采集项]服务")

        LogIndexSet.objects.filter(pk=self.collector.pk).update(index_set_name="[collection item]改名")
        with override("zh-cn"):
            result = IndexSetHandler.get_user_index_set(self.SPACE)
            names = {item["index_set_id"]: item["index_set_name"] for item in result}
            self.assertEqual(names[self.collector.index_set_id], "[采集项]改名")
        self.collector.refresh_from_db()
        self.assertEqual(self.collector.index_set_name, "[collection item]改名")

    def test_clustering_template_related_index_set_display(self):
        template = RegexTemplate.objects.create(space_uid=self.SPACE, template_name="template", predefined_varibles="")
        ClusteringConfig.objects.create(
            index_set_id=self.collector.index_set_id,
            regex_template_id=template.id,
            min_members=1,
            max_dist_list="",
            predefined_varibles="",
            delimeter="",
            max_log_length=100,
            clustering_fields="",
            bk_biz_id=2,
        )
        with override("en"):
            result = RegexTemplateHandler().list_templates(self.SPACE)
        self.assertEqual(
            result[0]["related_index_set_list"],
            [{"index_set_id": self.collector.index_set_id, "index_set_name": "[collection item]服务"}],
        )
        self.collector.refresh_from_db()
        self.assertEqual(self.collector.index_set_name, "[采集项]服务")

    def test_option_history_single_and_union(self):
        for index_set_type, fields in (
            (IndexSetType.SINGLE.value, {"index_set_id": self.collector.index_set_id}),
            (IndexSetType.UNION.value, {"index_set_ids": [self.collector.index_set_id, self.custom.index_set_id]}),
        ):
            history = UserIndexSetSearchHistory.objects.create(index_set_type=index_set_type, **fields)
            UserIndexSetSearchHistory.objects.filter(pk=history.pk).update(created_by=self.USER)
        with (
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.get_request_external_username", return_value=""
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.get_request_username", return_value=self.USER
            ),
            override("en"),
        ):
            single = SearchHandler.search_option_history(self.SPACE, IndexSetType.SINGLE.value)
            union = SearchHandler.search_option_history(self.SPACE, IndexSetType.UNION.value)
        self.assertEqual(single[0]["index_set_name"], "[collection item]服务")
        self.assertEqual(union[0]["index_set_names"], ["[collection item]服务", "[采集项]自定义"])
        self.collector.refresh_from_db()
        self.assertEqual(self.collector.index_set_name, "[采集项]服务")

    def test_search_favorite_list_and_detail_single_and_union(self):
        single = Favorite.objects.create(
            space_uid=self.SPACE,
            index_set_id=self.collector.index_set_id,
            name="single",
            group_id=1,
            visible_type=FavoriteVisibleType.PRIVATE.value,
            created_by=self.USER,
            display_fields=[],
            params={},
        )
        union = Favorite.objects.create(
            space_uid=self.SPACE,
            index_set_ids=[self.collector.index_set_id, self.custom.index_set_id],
            name="union",
            index_set_type=IndexSetType.UNION.value,
            group_id=1,
            visible_type=FavoriteVisibleType.PRIVATE.value,
            created_by=self.USER,
            display_fields=[],
            params={},
        )
        with override("en"):
            favorites = {item["name"]: item for item in Favorite.get_user_favorite(self.SPACE, self.USER)}
            handler = FavoriteHandler(space_uid=self.SPACE)
            handler.data = single
            single_detail = handler.retrieve()
            handler.data = union
            union_detail = handler.retrieve()
        self.assertEqual(favorites["single"]["index_set_name"], "[collection item]服务")
        self.assertEqual(favorites["union"]["index_set_names"], ["[collection item]服务", "[采集项]自定义"])
        self.assertEqual(single_detail["index_set_name"], "[collection item]服务")
        self.assertEqual(union_detail["index_set_names"], ["[collection item]服务", "[采集项]自定义"])
        self.collector.refresh_from_db()
        self.assertEqual(self.collector.index_set_name, "[采集项]服务")
