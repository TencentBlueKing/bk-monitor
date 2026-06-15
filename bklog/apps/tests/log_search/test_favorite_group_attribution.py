# -*- coding: utf-8 -*-
"""
收藏组属主校验 + 列表渲染兜底单元测试。

覆盖 create_or_update 的三重校验：
- 跨 space_uid 传 group_id → FavoriteGroupNotExistException
- 跨 source_type 传 group_id (scene 收藏挂 index_set 组) → FavoriteGroupNotExistException
- 传别人的 private 组 → FavoriteGroupNotExistException

以及 list_group_favorites / list_favorites 渲染兜底：
- 历史孤儿 fav 的 group_id 不在当前 source_type groups 时，归到 ungrouped 桶展示，不再被静默吞掉，
  且 list_favorites 不会 KeyError 500。
"""
from unittest.mock import patch

from django.test import TestCase

from apps.log_search.constants import (
    FavoriteGroupType,
    FavoriteSourceType,
    FavoriteVisibleType,
    SearchMode,
)
from apps.log_search.exceptions import FavoriteGroupNotExistException
from apps.log_search.handlers.search.favorite_handlers import (
    FavoriteGroupHandler,
    FavoriteHandler,
)
from apps.log_search.models import Favorite, FavoriteGroup

SPACE_UID = "test_space_uid"
OTHER_SPACE_UID = "other_space_uid"
USERNAME = "test_user"
OTHER_USERNAME = "other_user"


def _patch_username(func, username=USERNAME):
    func = patch(
        "apps.log_search.handlers.search.favorite_handlers.get_request_username",
        lambda *args, **kwargs: username,
    )(func)
    func = patch(
        "apps.log_search.handlers.search.favorite_handlers.get_request_external_username",
        lambda *args, **kwargs: "",
    )(func)
    func = patch("apps.models.get_request_username", lambda *args, **kwargs: username)(func)
    return func


@_patch_username
class TestCreateFavoriteAttributionValidation(TestCase):
    """create_or_update 的三重属主校验"""

    def _make_create_kwargs(self, **overrides):
        defaults = dict(
            name="scene_fav",
            ip_chooser={},
            addition=[],
            keyword="*",
            visible_type=FavoriteVisibleType.PUBLIC.value,
            search_fields=[],
            is_enable_display_fields=False,
            display_fields=[],
            search_mode=SearchMode.UI.value,
            source_type=FavoriteSourceType.SCENE.value,
            scene_id="host",
            table_id_conditions=[],
            scene_filter_values=[],
        )
        defaults.update(overrides)
        return defaults

    def test_reject_cross_source_type_group(self):
        """传 source_type=scene 但 group_id 是 index_set 桶的组 → 拒绝"""
        index_set_public_group = FavoriteGroupHandler(space_uid=SPACE_UID).create_or_update(
            name="index_set_pub", source_type=FavoriteSourceType.INDEX_SET.value
        )

        with self.assertRaises(FavoriteGroupNotExistException):
            FavoriteHandler(space_uid=SPACE_UID).create_or_update(
                **self._make_create_kwargs(group_id=index_set_public_group["id"])
            )

    def test_reject_cross_space_group(self):
        """传别的 space 的 group_id → 拒绝"""
        other_space_public_group = FavoriteGroupHandler(space_uid=OTHER_SPACE_UID).create_or_update(
            name="other_space_pub", source_type=FavoriteSourceType.SCENE.value
        )

        with self.assertRaises(FavoriteGroupNotExistException):
            FavoriteHandler(space_uid=SPACE_UID).create_or_update(
                **self._make_create_kwargs(group_id=other_space_public_group["id"])
            )

    def test_reject_others_private_group(self):
        """传别人的 private 组 → 拒绝（即便 source_type / space_uid 全对）"""
        # 用 OTHER_USERNAME 上下文 lazy 创建一条 scene private 组
        with patch(
            "apps.log_search.handlers.search.favorite_handlers.get_request_username",
            lambda *args, **kwargs: OTHER_USERNAME,
        ), patch(
            "apps.log_search.handlers.search.favorite_handlers.get_request_external_username",
            lambda *args, **kwargs: "",
        ):
            other_groups = FavoriteGroupHandler(space_uid=SPACE_UID).list(
                source_type=FavoriteSourceType.SCENE.value
            )
        other_private = next(
            g for g in other_groups if g["group_type"] == FavoriteGroupType.PRIVATE.value
        )

        with self.assertRaises(FavoriteGroupNotExistException):
            FavoriteHandler(space_uid=SPACE_UID).create_or_update(
                **self._make_create_kwargs(group_id=other_private["id"])
            )

    def test_accept_legit_scene_public_group(self):
        """传合法 scene 公共组 → 正常落库，visible_type=public"""
        scene_public_group = FavoriteGroupHandler(space_uid=SPACE_UID).create_or_update(
            name="scene_pub", source_type=FavoriteSourceType.SCENE.value
        )

        favorite = FavoriteHandler(space_uid=SPACE_UID).create_or_update(
            **self._make_create_kwargs(group_id=scene_public_group["id"])
        )

        self.assertEqual(favorite["group_id"], scene_public_group["id"])
        self.assertEqual(favorite["visible_type"], FavoriteVisibleType.PUBLIC.value)
        self.assertEqual(favorite["source_type"], FavoriteSourceType.SCENE.value)

    def tearDown(self):
        Favorite.objects.all().delete()
        FavoriteGroup.objects.all().delete()


@_patch_username
class TestListByGroupOrphanFallback(TestCase):
    """list_group_favorites / list_favorites 渲染兜底：孤儿 fav 归到 ungrouped"""

    def _make_orphan_favorite(self):
        """构造一条 source_type=scene 但 group_id 指向 index_set 桶 private 组的孤儿 fav。

        旁路 create_or_update 的属主校验，直接 ORM 写库模拟历史脏数据。
        """
        index_set_private = FavoriteGroup.get_or_create_private_group(
            space_uid=SPACE_UID, username=USERNAME, source_type=FavoriteSourceType.INDEX_SET.value
        )
        return Favorite.objects.create(
            space_uid=SPACE_UID,
            name="orphan_scene_fav",
            group_id=index_set_private.id,
            params={"ip_chooser": {}, "addition": [], "keyword": "*", "search_fields": []},
            visible_type=FavoriteVisibleType.PRIVATE.value,
            search_mode=SearchMode.UI.value,
            is_enable_display_fields=False,
            display_fields=[],
            source_type=FavoriteSourceType.SCENE.value,
            scene_id="host",
            table_id_conditions=[],
            scene_filter_values=[],
            created_by=USERNAME,
        )

    def test_list_by_group_orphan_falls_back_to_ungrouped(self):
        orphan = self._make_orphan_favorite()

        result = FavoriteHandler(space_uid=SPACE_UID).list_group_favorites(
            source_type=FavoriteSourceType.SCENE.value
        )

        ungrouped_buckets = [
            g for g in result if g["group_type"] == FavoriteGroupType.UNGROUPED.value
        ]
        self.assertEqual(len(ungrouped_buckets), 1)
        ungrouped = ungrouped_buckets[0]
        self.assertEqual([f["id"] for f in ungrouped["favorites"]], [orphan.id])

        # 孤儿 fav 不会出现在 index_set 桶里（list 按 source_type=scene 过滤了 favorites）
        for g in result:
            if g["group_type"] != FavoriteGroupType.UNGROUPED.value:
                self.assertEqual(g["favorites"], [])

    def test_list_favorites_orphan_does_not_raise_keyerror(self):
        orphan = self._make_orphan_favorite()

        favs = FavoriteHandler(space_uid=SPACE_UID).list_favorites(
            source_type=FavoriteSourceType.SCENE.value
        )

        self.assertEqual([f["id"] for f in favs], [orphan.id])
        # 渲染时 group_id 已被重定向到当前 source_type 的 ungrouped
        scene_ungrouped = FavoriteGroup.objects.get(
            space_uid=SPACE_UID,
            source_type=FavoriteSourceType.SCENE.value,
            group_type=FavoriteGroupType.UNGROUPED.value,
        )
        self.assertEqual(favs[0]["group_id"], scene_ungrouped.id)

    def tearDown(self):
        Favorite.objects.all().delete()
        FavoriteGroup.objects.all().delete()
