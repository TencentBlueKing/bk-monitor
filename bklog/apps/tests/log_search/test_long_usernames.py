"""第一期长用户名字段及收藏归属回归测试。"""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.response import Response

from apps.constants import UserOperationActionEnum, UserOperationTypeEnum
from apps.decorators import user_operation_record
from apps.log_audit.models import UserOperationRecord
from apps.log_extract.models import Tasks
from apps.log_search.constants import FavoriteGroupType, FavoriteSourceType, FavoriteVisibleType, SearchMode
from apps.log_search.decorators import search_history_record
from apps.log_search.exceptions import ConcurrentExportLimitException, FavoriteNotAllowedAccessException
from apps.log_search.handlers.search.favorite_handlers import FavoriteGroupHandler, FavoriteHandler
from apps.log_search.models import (
    AsyncTask,
    Favorite,
    FavoriteGroup,
    Scenario,
    UserIndexSetFieldsConfig,
    UserIndexSetSearchHistory,
    UserMetaConf,
)
from apps.models import OperateRecordModel, SoftDeleteModel

SPACE_UID = "test_space_uid"
SOURCE_APP_CODE = "test_app"
USERNAME_33 = "u" * 33
USERNAME_64 = "u" * 64
PHASE_ONE_FIELDS = {
    FavoriteGroup: ("created_by", "updated_by"),
    Favorite: ("created_by", "updated_by"),
    AsyncTask: ("created_by", "updated_by"),
    UserIndexSetSearchHistory: ("created_by", "updated_by", "deleted_by"),
    UserMetaConf: ("username",),
    UserIndexSetFieldsConfig: ("username",),
    Tasks: ("created_by", "updated_by"),
    UserOperationRecord: ("created_by",),
}


@contextmanager
def _request_context(external_username, source_app_code=SOURCE_APP_CODE, username="admin"):
    request = SimpleNamespace(
        user=SimpleNamespace(username=username),
        external_user=external_username,
        META={"HTTP_BK_APP_CODE": source_app_code},
    )
    with patch("apps.utils.local.get_request", return_value=request):
        yield


def _favorite_params(**overrides):
    params = {
        "name": "long_username_private_favorite",
        "ip_chooser": {},
        "addition": [],
        "keyword": "*",
        "visible_type": FavoriteVisibleType.PRIVATE.value,
        "search_fields": [],
        "is_enable_display_fields": False,
        "display_fields": [],
        "search_mode": SearchMode.UI.value,
        "source_type": FavoriteSourceType.SCENE.value,
        "scene_id": "host",
        "table_id_conditions": [],
        "scene_filter_values": [],
    }
    params.update(overrides)
    return params


class TestPhaseOneUsernameFields(SimpleTestCase):
    def test_target_fields_accept_33_and_64_characters_and_reject_65(self):
        for model, field_names in PHASE_ONE_FIELDS.items():
            for field_name in field_names:
                field = model._meta.get_field(field_name)
                with self.subTest(model=model._meta.label, field=field_name):
                    for username in (USERNAME_33, USERNAME_64):
                        self.assertEqual(field.clean(username, None), username)
                    with self.assertRaises(ValidationError):
                        field.clean("u" * 65, None)

    def test_base_and_other_audit_models_keep_32_character_limit(self):
        models = (OperateRecordModel, SoftDeleteModel, *apps.get_models())
        for model in models:
            if model in PHASE_ONE_FIELDS or not issubclass(model, OperateRecordModel):
                continue
            field_names = ["created_by", "updated_by"]
            if issubclass(model, SoftDeleteModel):
                field_names.append("deleted_by")
            for field_name in field_names:
                field = model._meta.get_field(field_name)
                with self.subTest(model=model._meta.label, field=field_name):
                    self.assertEqual(field.clean("u" * 32, None), "u" * 32)
                    with self.assertRaises(ValidationError):
                        field.clean(USERNAME_33, None)


class TestFavoriteLongUsernames(TestCase):
    def assert_complete_owner(self, instance, username, operator="admin"):
        instance.refresh_from_db()
        self.assertEqual(instance.created_by, username)
        self.assertEqual(instance.updated_by, operator)
        # SQLite 不限制 VARCHAR 长度，额外校验字段约束以覆盖生产截断问题。
        self.assertEqual(instance._meta.get_field("created_by").clean(instance.created_by, instance), username)

    def test_private_group_reuses_full_username_at_supported_lengths(self):
        for username in (USERNAME_33, USERNAME_64):
            with self.subTest(username_length=len(username)), _request_context(username):
                group = FavoriteGroup.get_or_create_private_group(space_uid=SPACE_UID, username=username)
                repeated = FavoriteGroup.get_or_create_private_group(space_uid=SPACE_UID, username=username)

                self.assertEqual(repeated.pk, group.pk)
                self.assert_complete_owner(group, username)
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
        usernames = (USERNAME_33, USERNAME_33[:32] + "v")
        groups_by_username = {}
        for username in usernames:
            with _request_context(username):
                group = FavoriteGroup.get_or_create_private_group(space_uid=SPACE_UID, username=username)
                groups_by_username[username] = group.pk
                self.assert_complete_owner(group, username)

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
            ("other_space_uid", SOURCE_APP_CODE, FavoriteSourceType.INDEX_SET.value),
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
                    self.assert_complete_owner(group, USERNAME_64)
                    group_ids.add(group.pk)

        self.assertEqual(len(group_ids), len(contexts))

    def test_private_favorites_preserve_full_username_and_owner_visibility(self):
        favorites_by_username = {}
        for username in (USERNAME_33, USERNAME_64):
            with _request_context(username):
                created = FavoriteHandler(space_uid=SPACE_UID).create_or_update(**_favorite_params())
                favorite = Favorite.objects.get(pk=created["id"])
                self.assert_complete_owner(favorite, username)
                self.assert_complete_owner(FavoriteGroup.objects.get(pk=favorite.group_id), username)
                favorites_by_username[username] = favorite.pk

        self.assertEqual(Favorite.objects.count(), 2)
        for username, favorite_id in favorites_by_username.items():
            with _request_context(username):
                handler = FavoriteHandler(space_uid=SPACE_UID)
                favorites = handler.list_favorites(source_type=FavoriteSourceType.SCENE.value)
                self.assertEqual([item["id"] for item in favorites], [favorite_id])
                self.assertEqual(favorites[0]["created_by"], username)
                self.assertEqual(favorites[0]["updated_by"], "admin")
                groups = handler.list_group_favorites(source_type=FavoriteSourceType.SCENE.value)
                private_group = next(
                    group for group in groups if group["group_type"] == FavoriteGroupType.PRIVATE.value
                )
                self.assertEqual([item["id"] for item in private_group["favorites"]], [favorite_id])
                self.assertEqual(FavoriteHandler(favorite_id=favorite_id).retrieve()["created_by"], username)
                other_favorite_id = next(pk for owner, pk in favorites_by_username.items() if owner != username)
                with self.assertRaises(FavoriteNotAllowedAccessException):
                    FavoriteHandler(favorite_id=other_favorite_id)

    def test_long_operator_updates_favorite_without_changing_external_owner(self):
        with _request_context(USERNAME_33):
            created = FavoriteHandler(space_uid=SPACE_UID).create_or_update(**_favorite_params())
        with _request_context(USERNAME_33, username=USERNAME_64):
            FavoriteHandler(favorite_id=created["id"]).create_or_update(**_favorite_params(name="renamed"))

        self.assert_complete_owner(Favorite.objects.get(pk=created["id"]), USERNAME_33, operator=USERNAME_64)


class TestHistoryLongUsernameAudit(TestCase):
    def test_external_history_keeps_authorizer_as_update_and_delete_operator(self):
        @search_history_record
        def search():
            return Response(
                {
                    "history_obj": {
                        "index_set_id": 1,
                        "params": {},
                        "search_type": "default",
                        "search_mode": SearchMode.UI.value,
                        "from_favorite_id": 0,
                    }
                }
            )

        with _request_context(USERNAME_64):
            search()
            history = UserIndexSetSearchHistory.objects.get()
            self.assertEqual(history.created_by, USERNAME_64)
            self.assertEqual(history.updated_by, "admin")
            history.delete()

        deleted = UserIndexSetSearchHistory.origin_objects.get(pk=history.pk)
        self.assertTrue(deleted.is_deleted)
        self.assertEqual(deleted.created_by, USERNAME_64)
        self.assertEqual(deleted.updated_by, "admin")
        self.assertEqual(deleted.deleted_by, "admin")

    def test_instance_and_queryset_deletion_record_full_long_operator(self):
        for delete_by_queryset in (False, True):
            with self.subTest(delete_by_queryset=delete_by_queryset):
                with _request_context(USERNAME_33, username=USERNAME_64):
                    history = UserIndexSetSearchHistory.objects.create(created_by=USERNAME_33, params={})
                    if delete_by_queryset:
                        UserIndexSetSearchHistory.objects.filter(pk=history.pk).delete()
                    else:
                        history.delete()

                deleted = UserIndexSetSearchHistory.origin_objects.get(pk=history.pk)
                self.assertTrue(deleted.is_deleted)
                self.assertEqual(deleted.created_by, USERNAME_33)
                self.assertEqual(deleted.updated_by, USERNAME_64)
                self.assertEqual(deleted.deleted_by, USERNAME_64)
                for field_name in ("updated_by", "deleted_by"):
                    self.assertEqual(
                        deleted._meta.get_field(field_name).clean(getattr(deleted, field_name), deleted), USERNAME_64
                    )


class TestExportAndOperationRecordLongUsernames(TestCase):
    @override_settings(USE_REDIS=False, MAX_CONCURRENT_EXPORT_TASKS=1)
    def test_export_running_limit_isolates_users_with_same_32_character_prefix(self):
        task_ids = set()
        for username in (USERNAME_33, USERNAME_64):
            with self.subTest(length=len(username)), _request_context(username):
                task = AsyncTask.async_export_task_create_with_running_limit(
                    username=username, request_param={}, scenario_id=Scenario.LOG
                )
                task.refresh_from_db()
                self.assertEqual(task.created_by, username)
                self.assertEqual(task.updated_by, "admin")
                self.assertEqual(
                    list(AsyncTask.objects.filter(created_by=username).values_list("pk", flat=True)), [task.pk]
                )
                with self.assertRaises(ConcurrentExportLimitException):
                    AsyncTask.async_export_task_create_with_running_limit(
                        username=username, request_param={}, scenario_id=Scenario.LOG
                    )
                task_ids.add(task.pk)

        self.assertEqual(len(task_ids), 2)
        self.assertEqual(AsyncTask.objects.count(), 2)

    def test_operation_record_task_preserves_full_external_username(self):
        for username in (USERNAME_33, USERNAME_64):
            with self.subTest(length=len(username)), _request_context(username):
                user_operation_record.run(
                    {
                        "username": username,
                        "biz_id": 1,
                        "record_type": UserOperationTypeEnum.SEARCH,
                        "record_object_id": 1,
                        "action": UserOperationActionEnum.CREATE,
                        "params": {"keyword": "*"},
                    }
                )
                record = UserOperationRecord.objects.get(created_by=username)
                self.assertEqual(record.created_by, username)
                self.assertEqual(record.record_type, UserOperationTypeEnum.SEARCH.value)
                self.assertEqual(record.action, UserOperationActionEnum.CREATE.value)

        self.assertEqual(UserOperationRecord.objects.count(), 2)
