"""长外部用户名的收藏分组和个人收藏归属回归测试。"""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from apps.log_search.constants import FavoriteGroupType, FavoriteSourceType, FavoriteVisibleType, SearchMode
from apps.log_search.exceptions import FavoriteNotAllowedAccessException
from apps.log_search.handlers.search.favorite_handlers import FavoriteGroupHandler, FavoriteHandler
from apps.log_search.models import Favorite, FavoriteGroup

SPACE_UID = "bkcc__100729"
SOURCE_APP_CODE = "bklog"
USERNAME_33 = "menglihong.janaa_shengqugames@tai"
USERNAME_64 = USERNAME_33.ljust(64, "x")


@contextmanager
def _request_context(username, source_app_code=SOURCE_APP_CODE):
    request = SimpleNamespace(
        user=SimpleNamespace(username=username),
        external_user=username,
        META={"HTTP_BK_APP_CODE": source_app_code},
    )
    with patch("apps.utils.local.get_request", return_value=request):
        yield


class TestFavoriteLongUsernames(TestCase):
    def assert_complete_audit_usernames(self, instance, username):
        instance.refresh_from_db()
        for field_name in ("created_by", "updated_by"):
            value = getattr(instance, field_name)
            self.assertEqual(value, username)
            # SQLite 不限制 VARCHAR 长度，额外校验字段约束才能覆盖生产截断问题。
            self.assertEqual(instance._meta.get_field(field_name).clean(value, instance), username)

    def test_private_group_reuses_full_username_at_supported_lengths(self):
        for username in (USERNAME_33, USERNAME_64):
            with self.subTest(username_length=len(username)), _request_context(username):
                group = FavoriteGroup.get_or_create_private_group(space_uid=SPACE_UID, username=username)
                repeated = FavoriteGroup.get_or_create_private_group(space_uid=SPACE_UID, username=username)

                self.assertEqual(repeated.pk, group.pk)
                self.assert_complete_audit_usernames(group, username)
                self.assertEqual(
                    FavoriteGroup.objects.filter(
                        space_uid=SPACE_UID,
                        created_by=username,
                        group_type=FavoriteGroupType.PRIVATE.value,
                        source_app_code=SOURCE_APP_CODE,
                        source_type=FavoriteSourceType.INDEX_SET.value,
                    ).count(),
                    1,
                )
                for _ in range(2):
                    groups = FavoriteGroupHandler(space_uid=SPACE_UID).list()
                    self.assertEqual(
                        [item["id"] for item in groups if item["group_type"] == FavoriteGroupType.PRIVATE.value],
                        [group.pk],
                    )

    def test_private_groups_separate_usernames_with_same_32_character_prefix(self):
        usernames = (USERNAME_33, USERNAME_33[:32] + "z")
        groups_by_username = {}
        for username in usernames:
            with _request_context(username):
                group = FavoriteGroup.get_or_create_private_group(space_uid=SPACE_UID, username=username)
                groups_by_username[username] = group.pk
                self.assert_complete_audit_usernames(group, username)

        self.assertEqual(len(set(groups_by_username.values())), 2)
        for username in usernames:
            with _request_context(username):
                groups = FavoriteGroupHandler(space_uid=SPACE_UID).list()
                self.assertEqual(
                    [item["id"] for item in groups if item["group_type"] == FavoriteGroupType.PRIVATE.value],
                    [groups_by_username[username]],
                )

    def test_private_group_isolates_space_app_and_source_type(self):
        contexts = (
            (SPACE_UID, SOURCE_APP_CODE, FavoriteSourceType.INDEX_SET.value),
            ("bkcc__100730", SOURCE_APP_CODE, FavoriteSourceType.INDEX_SET.value),
            (SPACE_UID, "other_app", FavoriteSourceType.INDEX_SET.value),
            (SPACE_UID, SOURCE_APP_CODE, FavoriteSourceType.SCENE.value),
        )
        group_ids = set()
        for space_uid, source_app_code, source_type in contexts:
            with self.subTest(space_uid=space_uid, app=source_app_code, source_type=source_type):
                with _request_context(USERNAME_64, source_app_code):
                    group = FavoriteGroup.get_or_create_private_group(
                        space_uid=space_uid, username=USERNAME_64, source_type=source_type
                    )
                    repeated = FavoriteGroup.get_or_create_private_group(
                        space_uid=space_uid, username=USERNAME_64, source_type=source_type
                    )

                    self.assertEqual(repeated.pk, group.pk)
                    self.assertEqual(
                        (group.space_uid, group.source_app_code, group.source_type),
                        (space_uid, source_app_code, source_type),
                    )
                    self.assert_complete_audit_usernames(group, USERNAME_64)
                    group_ids.add(group.pk)

        self.assertEqual(len(group_ids), len(contexts))

    def test_private_favorites_preserve_full_username_and_owner_visibility(self):
        favorites_by_username = {}
        for username in (USERNAME_33, USERNAME_64):
            with _request_context(username):
                created = FavoriteHandler(space_uid=SPACE_UID).create_or_update(
                    name="long_username_private_favorite",
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
                favorite = Favorite.objects.get(pk=created["id"])
                self.assert_complete_audit_usernames(favorite, username)
                self.assert_complete_audit_usernames(FavoriteGroup.objects.get(pk=favorite.group_id), username)
                favorites_by_username[username] = favorite.pk

        self.assertEqual(Favorite.objects.count(), 2)
        for username, favorite_id in favorites_by_username.items():
            with _request_context(username):
                handler = FavoriteHandler(space_uid=SPACE_UID)
                favorites = handler.list_favorites(source_type=FavoriteSourceType.SCENE.value)
                self.assertEqual([item["id"] for item in favorites], [favorite_id])
                self.assertEqual(favorites[0]["created_by"], username)
                self.assertEqual(favorites[0]["updated_by"], username)

                groups = handler.list_group_favorites(source_type=FavoriteSourceType.SCENE.value)
                private_group = next(
                    group for group in groups if group["group_type"] == FavoriteGroupType.PRIVATE.value
                )
                self.assertEqual([item["id"] for item in private_group["favorites"]], [favorite_id])
                self.assertEqual(FavoriteHandler(favorite_id=favorite_id).retrieve()["created_by"], username)

                other_favorite_id = next(pk for owner, pk in favorites_by_username.items() if owner != username)
                with self.assertRaises(FavoriteNotAllowedAccessException):
                    FavoriteHandler(favorite_id=other_favorite_id)
