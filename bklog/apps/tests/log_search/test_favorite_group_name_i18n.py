# -*- coding: utf-8 -*-
"""
"个人收藏" / "未分组" 名称返回值的本地化兜底单元测试。

覆盖：
- DB 存了英文 literal (历史脏数据) 时,list 接口返回本地化中文
- DB 存了中文时,list 接口保持不变
- 自定义公开组的 name 不被改写
"""
from unittest.mock import patch

from django.test import TestCase
from django.utils.translation import gettext as _

from apps.log_search.constants import FavoriteGroupType, FavoriteSourceType
from apps.log_search.handlers.search.favorite_handlers import FavoriteGroupHandler
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


@_patch_username
class TestFavoriteGroupNameI18n(TestCase):
    def test_legacy_english_literal_name_is_normalized(self):
        # 模拟历史脏数据:DB 里 name 存的是英文 literal
        FavoriteGroup.objects.create(
            name="private",
            group_type=FavoriteGroupType.PRIVATE.value,
            space_uid=SPACE_UID,
            created_by=USERNAME,
            source_type=FavoriteSourceType.INDEX_SET.value,
        )
        FavoriteGroup.objects.create(
            name="unknown",
            group_type=FavoriteGroupType.UNGROUPED.value,
            space_uid=SPACE_UID,
            source_type=FavoriteSourceType.INDEX_SET.value,
        )

        groups = FavoriteGroupHandler(space_uid=SPACE_UID).list(
            source_type=FavoriteSourceType.INDEX_SET.value
        )

        # 按 group_type 兜底,无视 DB 存的字面值
        name_by_type = {g["group_type"]: g["name"] for g in groups}
        self.assertEqual(name_by_type[FavoriteGroupType.PRIVATE.value], _("个人收藏"))
        self.assertEqual(name_by_type[FavoriteGroupType.UNGROUPED.value], _("未分组"))

    def test_correct_chinese_name_unchanged(self):
        FavoriteGroup.objects.create(
            name=_("个人收藏"),
            group_type=FavoriteGroupType.PRIVATE.value,
            space_uid=SPACE_UID,
            created_by=USERNAME,
            source_type=FavoriteSourceType.INDEX_SET.value,
        )
        FavoriteGroup.objects.create(
            name=_("未分组"),
            group_type=FavoriteGroupType.UNGROUPED.value,
            space_uid=SPACE_UID,
            source_type=FavoriteSourceType.INDEX_SET.value,
        )

        groups = FavoriteGroupHandler(space_uid=SPACE_UID).list(
            source_type=FavoriteSourceType.INDEX_SET.value
        )

        name_by_type = {g["group_type"]: g["name"] for g in groups}
        self.assertEqual(name_by_type[FavoriteGroupType.PRIVATE.value], _("个人收藏"))
        self.assertEqual(name_by_type[FavoriteGroupType.UNGROUPED.value], _("未分组"))

    def test_public_group_name_not_normalized(self):
        # 先 lazy 出 private / ungrouped 占位
        FavoriteGroupHandler(space_uid=SPACE_UID).list(
            source_type=FavoriteSourceType.INDEX_SET.value
        )
        FavoriteGroupHandler(space_uid=SPACE_UID).create_or_update(
            name="自定义业务组", source_type=FavoriteSourceType.INDEX_SET.value
        )

        groups = FavoriteGroupHandler(space_uid=SPACE_UID).list(
            source_type=FavoriteSourceType.INDEX_SET.value
        )

        public_groups = [g for g in groups if g["group_type"] == FavoriteGroupType.PUBLIC.value]
        self.assertEqual([g["name"] for g in public_groups], ["自定义业务组"])

    def tearDown(self):
        Favorite.objects.all().delete()
        FavoriteGroup.objects.all().delete()
