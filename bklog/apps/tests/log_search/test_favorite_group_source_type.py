# -*- coding: utf-8 -*-
"""
FavoriteGroup 按 source_type 隔离的单元测试。

覆盖：
- index_set / scene 两个 source_type 下各自独立的 private / ungrouped 组
- list 接口按 source_type 过滤
- 创建场景化收藏时自动 lazy 出 source_type=scene 的 private 组
- 同名组在不同 source_type 下可共存（unique_together 含 source_type）
"""
from unittest.mock import patch

from django.test import TestCase

from apps.log_search.constants import (
    FavoriteGroupType,
    FavoriteSourceType,
    FavoriteVisibleType,
    SearchMode,
)
from apps.log_search.handlers.search.favorite_handlers import (
    FavoriteGroupHandler,
    FavoriteHandler,
)
from apps.log_search.models import Favorite, FavoriteGroup

SPACE_UID = "test_space_uid"
USERNAME = "test_user"
INDEX_SET_ID = 1


def _patch_username(func):
    func = patch(
        "apps.log_search.handlers.search.favorite_handlers.get_request_username",
        lambda *args, **kwargs: USERNAME,
    )(func)
    func = patch("apps.models.get_request_username", lambda *args, **kwargs: USERNAME)(func)
    return func


@_patch_username
class TestFavoriteGroupSourceTypeIsolation(TestCase):
    def test_lazy_groups_isolated_per_source_type(self):
        # 拉 index_set 组：自动 lazy 出 private + ungrouped
        index_set_groups = FavoriteGroupHandler(space_uid=SPACE_UID).list(
            source_type=FavoriteSourceType.INDEX_SET.value
        )
        self.assertEqual(len(index_set_groups), 2)
        self.assertEqual(
            {g["group_type"] for g in index_set_groups},
            {FavoriteGroupType.PRIVATE.value, FavoriteGroupType.UNGROUPED.value},
        )
        for g in index_set_groups:
            self.assertEqual(g["source_type"], FavoriteSourceType.INDEX_SET.value)

        # 拉 scene 组：再 lazy 出独立的一套（DB 应有 4 条）
        scene_groups = FavoriteGroupHandler(space_uid=SPACE_UID).list(
            source_type=FavoriteSourceType.SCENE.value
        )
        self.assertEqual(len(scene_groups), 2)
        for g in scene_groups:
            self.assertEqual(g["source_type"], FavoriteSourceType.SCENE.value)

        self.assertEqual(FavoriteGroup.objects.filter(space_uid=SPACE_UID).count(), 4)
        self.assertEqual(
            FavoriteGroup.objects.filter(
                space_uid=SPACE_UID, source_type=FavoriteSourceType.INDEX_SET.value
            ).count(),
            2,
        )
        self.assertEqual(
            FavoriteGroup.objects.filter(
                space_uid=SPACE_UID, source_type=FavoriteSourceType.SCENE.value
            ).count(),
            2,
        )

    def test_scene_favorite_lazy_creates_scene_private_group(self):
        favorite = FavoriteHandler(space_uid=SPACE_UID).create_or_update(
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
            table_id_conditions=[[{"field_name": "scene", "op": "eq", "value": ["host"]}]],
            scene_filter_values=[{"field": "cluster_id", "operator": "eq", "value": "demo"}],
        )

        group = FavoriteGroup.objects.get(pk=favorite["group_id"])
        self.assertEqual(group.group_type, FavoriteGroupType.PRIVATE.value)
        self.assertEqual(group.source_type, FavoriteSourceType.SCENE.value)

        # 创建的收藏走的是 scene 桶，index_set 桶仍然空
        self.assertFalse(
            FavoriteGroup.objects.filter(
                space_uid=SPACE_UID,
                source_type=FavoriteSourceType.INDEX_SET.value,
                group_type=FavoriteGroupType.PRIVATE.value,
            ).exists()
        )

    def test_list_filters_favorites_by_source_type(self):
        # 同名 + 同 group_id 不允许，所以分别创建两个不同名的收藏
        FavoriteHandler(space_uid=SPACE_UID).create_or_update(
            name="index_set_fav",
            index_set_id=INDEX_SET_ID,
            ip_chooser={},
            addition=[],
            keyword="*",
            visible_type=FavoriteVisibleType.PRIVATE.value,
            search_fields=[],
            is_enable_display_fields=False,
            display_fields=[],
            search_mode=SearchMode.UI.value,
            source_type=FavoriteSourceType.INDEX_SET.value,
        )
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
            table_id_conditions=[],
            scene_filter_values=[],
        )

        scene_favs = FavoriteHandler(space_uid=SPACE_UID).list_favorites(
            source_type=FavoriteSourceType.SCENE.value
        )
        index_set_favs = FavoriteHandler(space_uid=SPACE_UID).list_favorites(
            source_type=FavoriteSourceType.INDEX_SET.value
        )

        self.assertEqual([f["name"] for f in scene_favs], ["scene_fav"])
        self.assertEqual([f["name"] for f in index_set_favs], ["index_set_fav"])

    def test_public_groups_same_name_can_coexist_across_source_types(self):
        index_set_group = FavoriteGroupHandler(space_uid=SPACE_UID).create_or_update(
            name="同名公开组", source_type=FavoriteSourceType.INDEX_SET.value
        )
        scene_group = FavoriteGroupHandler(space_uid=SPACE_UID).create_or_update(
            name="同名公开组", source_type=FavoriteSourceType.SCENE.value
        )

        self.assertNotEqual(index_set_group["id"], scene_group["id"])
        self.assertEqual(
            FavoriteGroup.objects.filter(space_uid=SPACE_UID, name="同名公开组").count(), 2
        )

    def tearDown(self):
        Favorite.objects.all().delete()
        FavoriteGroup.objects.all().delete()
