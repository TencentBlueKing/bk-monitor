# -*- coding: utf-8 -*-
"""
场景化收藏详情 query_string 拼装的单元测试。

覆盖：
- source_type=scene 的 retrieve 返回 query_string 包含 table_id_conditions / scene_filter_values
- source_type=index_set 的 retrieve 不受影响（回归保护）
- list_favorites/list_group_favorites 返回结构包含 scene 字段
"""
from unittest.mock import patch

from django.test import TestCase

from apps.log_search.constants import (
    FavoriteSourceType,
    FavoriteVisibleType,
    SearchMode,
)
from apps.log_search.handlers.search.favorite_handlers import FavoriteHandler
from apps.log_search.models import Favorite, FavoriteGroup

SPACE_UID = "test_space_uid"
USERNAME = "test_user"


def _patch_username(func):
    func = patch(
        "apps.log_search.handlers.search.favorite_handlers.get_request_username",
        lambda *args, **kwargs: USERNAME,
    )(func)
    func = patch("apps.models.get_request_username", lambda *args, **kwargs: USERNAME)(func)
    return func


SCENE_TABLE_ID_CONDITIONS = [
    [
        {"field_name": "scene", "op": "eq", "value": ["host"]},
        {"field_name": "cluster_id", "op": "eq", "value": ["demo-cluster"]},
    ]
]
SCENE_FILTER_VALUES = [
    {"field": "host_ip", "operator": "eq", "value": "127.0.0.1"},
]


@_patch_username
class TestFavoriteSceneQueryString(TestCase):
    @patch(
        "apps.utils.scene_lucene._collect_scene_dimension_keys",
        lambda: {"host_ip"},
    )
    def test_scene_retrieve_query_string_contains_scene_conditions(self):
        created = FavoriteHandler(space_uid=SPACE_UID).create_or_update(
            name="scene_fav",
            ip_chooser={},
            addition=[],
            keyword="error",
            visible_type=FavoriteVisibleType.PRIVATE.value,
            search_fields=[],
            is_enable_display_fields=False,
            display_fields=[],
            search_mode=SearchMode.UI.value,
            source_type=FavoriteSourceType.SCENE.value,
            scene_id="host",
            table_id_conditions=SCENE_TABLE_ID_CONDITIONS,
            scene_filter_values=SCENE_FILTER_VALUES,
        )

        detail = FavoriteHandler(favorite_id=created["id"]).retrieve()
        qs = detail["query_string"]

        # table_id_conditions: 跳过 scene 路由维度,保留 cluster_id
        self.assertIn("cluster_id", qs)
        self.assertIn("demo-cluster", qs)
        # scene_filter_values 必须出现在 query_string 中
        self.assertIn("host_ip", qs)
        self.assertIn("127.0.0.1", qs)
        # 关键字也要拼进去
        self.assertIn("error", qs)

    def test_index_set_retrieve_query_string_unaffected(self):
        # 直接用 ORM 创建 index_set 收藏(避免 LogIndexSet 依赖)
        group = FavoriteGroup.get_or_create_private_group(
            space_uid=SPACE_UID, username=USERNAME, source_type=FavoriteSourceType.INDEX_SET.value
        )
        favorite = Favorite.objects.create(
            space_uid=SPACE_UID,
            name="index_set_fav",
            group_id=group.id,
            params={
                "ip_chooser": {},
                "addition": [{"field": "level", "operator": "is", "value": "error"}],
                "keyword": "trace_id: abc",
                "search_fields": [],
                "chart_params": {},
            },
            visible_type=FavoriteVisibleType.PRIVATE.value,
            search_mode=SearchMode.UI.value,
            is_enable_display_fields=False,
            display_fields=[],
            source_type=FavoriteSourceType.INDEX_SET.value,
            index_set_id=1,
            created_by=USERNAME,
        )

        with patch(
            "apps.log_search.handlers.search.favorite_handlers.LogIndexSet.objects.filter"
        ) as mock_filter:
            mock_filter.return_value.exists.return_value = False
            detail = FavoriteHandler(favorite_id=favorite.id).retrieve()

        qs = detail["query_string"]
        # 普通检索应当走 generate_query_string,不拼场景路由条件
        self.assertNotIn("cluster_id", qs)
        self.assertIn("trace_id", qs)
        self.assertIn("level", qs)

    def test_scene_list_favorites_contains_scene_fields(self):
        FavoriteHandler(space_uid=SPACE_UID).create_or_update(
            name="scene_fav",
            ip_chooser={},
            addition=[],
            keyword="*",
            visible_type=FavoriteVisibleType.PRIVATE.value,
            search_fields=[],
            is_enable_display_fields=False,
            display_fields=[],
            search_mode=SearchMode.UI.value,
            source_type=FavoriteSourceType.SCENE.value,
            scene_id="host",
            table_id_conditions=SCENE_TABLE_ID_CONDITIONS,
            scene_filter_values=SCENE_FILTER_VALUES,
        )

        favorites = FavoriteHandler(space_uid=SPACE_UID).list_favorites(
            source_type=FavoriteSourceType.SCENE.value
        )
        self.assertEqual(len(favorites), 1)
        fav = favorites[0]
        self.assertEqual(fav["source_type"], FavoriteSourceType.SCENE.value)
        self.assertEqual(fav["scene_id"], "host")
        self.assertEqual(fav["table_id_conditions"], SCENE_TABLE_ID_CONDITIONS)
        self.assertEqual(fav["scene_filter_values"], SCENE_FILTER_VALUES)

    def tearDown(self):
        Favorite.objects.all().delete()
        FavoriteGroup.objects.all().delete()
