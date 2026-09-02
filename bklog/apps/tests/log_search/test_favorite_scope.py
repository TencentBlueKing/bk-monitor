"""收藏及收藏组作用域的写入、增量更新和查询测试。"""

import json
from unittest.mock import patch

from django.http import QueryDict
from django.test import TestCase
from rest_framework import serializers

from apps.log_search.constants import (
    FavoriteGroupType,
    FavoriteSourceType,
    FavoriteVisibleType,
    SearchMode,
)
from apps.log_search.exceptions import FavoriteAlreadyExistException, FavoriteGroupAlreadyExistException
from apps.log_search.handlers.search.favorite_handlers import FavoriteGroupHandler, FavoriteHandler
from apps.log_search.models import Favorite, FavoriteGroup
from apps.log_search.serializers import (
    CreateFavoriteGroupSerializer,
    FavoriteGroupListSerializer,
    FavoriteListSerializer,
    FavoriteScopeField,
    UpdateFavoriteGroupSerializer,
    UpdateFavoriteSerializer,
)

SPACE_UID = "bkcc__999999999"
USERNAME = "scope_user"
OTHER_USERNAME = "other_scope_user"
SOURCE_APP_CODE = "scope_test"
SOURCE_TYPE = FavoriteSourceType.SCENE.value


def _start_request_context_patches(test_case: TestCase) -> None:
    patchers: list = [
        patch(
            "apps.log_search.handlers.search.favorite_handlers.get_request_external_username",
            lambda *args, **kwargs: "",
        ),
        patch(
            "apps.log_search.handlers.search.favorite_handlers.get_request_username",
            lambda *args, **kwargs: USERNAME,
        ),
        patch(
            "apps.log_search.handlers.search.favorite_handlers.get_request_app_code",
            lambda *args, **kwargs: SOURCE_APP_CODE,
        ),
        patch("apps.models.get_request_username", lambda *args, **kwargs: USERNAME),
        patch("apps.log_search.models.get_request_app_code", lambda *args, **kwargs: SOURCE_APP_CODE),
    ]
    for patcher in patchers:
        patcher.start()
        test_case.addCleanup(patcher.stop)


class TestFavoriteScopeField(TestCase):
    def test_legacy_requests_keep_scope_optional(self):
        list_serializer = FavoriteListSerializer(data={"space_uid": SPACE_UID})
        update_serializer = UpdateFavoriteSerializer(data={})
        group_list_serializer = FavoriteGroupListSerializer(data={"space_uid": SPACE_UID})
        group_create_serializer = CreateFavoriteGroupSerializer(data={"space_uid": SPACE_UID, "name": "demo"})
        group_update_serializer = UpdateFavoriteGroupSerializer(data={"name": "demo"})

        self.assertTrue(list_serializer.is_valid(), list_serializer.errors)
        self.assertEqual(list_serializer.validated_data["scope"], {})
        self.assertTrue(update_serializer.is_valid(), update_serializer.errors)
        self.assertNotIn("scope", update_serializer.validated_data)
        self.assertTrue(group_list_serializer.is_valid(), group_list_serializer.errors)
        self.assertEqual(group_list_serializer.validated_data["scope"], {})
        self.assertTrue(group_create_serializer.is_valid(), group_create_serializer.errors)
        self.assertEqual(group_create_serializer.validated_data["scope"], {})
        self.assertTrue(group_update_serializer.is_valid(), group_update_serializer.errors)
        self.assertNotIn("scope", group_update_serializer.validated_data)

    def test_parse_scope_from_get_query(self):
        query = QueryDict(mutable=True)
        query.update(
            {
                "space_uid": SPACE_UID,
                "scope": json.dumps({"app_name": "demo", "service_name": "api"}),
            }
        )

        serializer = FavoriteListSerializer(data=query)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["scope"],
            {"app_name": "demo", "service_name": "api"},
        )

    def test_accept_flat_string_mapping(self):
        scope = FavoriteScopeField().run_validation({"app_name": "demo", "bcs_cluster_id": "cluster-1"})

        self.assertEqual(scope, {"app_name": "demo", "bcs_cluster_id": "cluster-1"})

    def test_reject_nested_scope_and_orm_lookup_key(self):
        nested_field = FavoriteScopeField()
        lookup_field = FavoriteScopeField()

        with self.assertRaisesMessage(serializers.ValidationError, "scope 参数值必须是字符串"):
            nested_field.run_validation({"app_name": {"name": "demo"}})
        with self.assertRaisesMessage(serializers.ValidationError, "scope 参数名必须以小写字母开头"):
            lookup_field.run_validation({"app_name__contains": "demo"})


class TestFavoriteScope(TestCase):
    def setUp(self):
        _start_request_context_patches(self)
        groups: list[dict] = FavoriteGroupHandler(space_uid=SPACE_UID).list(source_type=SOURCE_TYPE)
        self.private_group: FavoriteGroup = FavoriteGroup.objects.get(
            id=next(group["id"] for group in groups if group["group_type"] == FavoriteGroupType.PRIVATE.value)
        )
        self.ungrouped_group: FavoriteGroup = FavoriteGroup.objects.get(
            id=next(group["id"] for group in groups if group["group_type"] == FavoriteGroupType.UNGROUPED.value)
        )
        public_group = FavoriteGroupHandler(space_uid=SPACE_UID).create_or_update(
            name="scope_public_group",
            source_type=SOURCE_TYPE,
            scope={"app_name": "demo", "service_name": "api"},
        )
        self.public_group: FavoriteGroup = FavoriteGroup.objects.get(id=public_group["id"])

    @staticmethod
    def _favorite_params(**overrides) -> dict:
        params: dict = {
            "name": "scope_favorite",
            "ip_chooser": {},
            "addition": [],
            "keyword": "*",
            "visible_type": FavoriteVisibleType.PUBLIC.value,
            "search_fields": [],
            "is_enable_display_fields": False,
            "display_fields": [],
            "search_mode": SearchMode.UI.value,
            "source_type": SOURCE_TYPE,
            "scene_id": "host",
            "table_id_conditions": [],
            "scene_filter_values": [],
        }
        params.update(overrides)
        return params

    def _create_favorite(
        self,
        name: str,
        group: FavoriteGroup,
        visible_type: str,
        created_by: str,
        scope: dict[str, str],
    ) -> Favorite:
        return Favorite.objects.create(
            space_uid=SPACE_UID,
            name=name,
            group_id=group.id,
            params={"ip_chooser": {}, "addition": [], "keyword": "*", "search_fields": []},
            visible_type=visible_type,
            search_mode=SearchMode.UI.value,
            is_enable_display_fields=False,
            display_fields=[],
            source_app_code=SOURCE_APP_CODE,
            source_type=SOURCE_TYPE,
            scene_id="host",
            table_id_conditions=[],
            scene_filter_values=[],
            scope=scope,
            created_by=created_by,
        )

    def test_create_and_update_merge_scope(self):
        created: dict = FavoriteHandler(space_uid=SPACE_UID).create_or_update(
            **self._favorite_params(
                group_id=self.public_group.id,
                scope={"app_name": "demo", "service_name": "api"},
            )
        )

        updated: dict = FavoriteHandler(favorite_id=created["id"]).create_or_update(
            **self._favorite_params(
                group_id=self.public_group.id,
                scope={"service_name": "worker", "bcs_cluster_id": "cluster-1"},
            )
        )

        self.assertEqual(
            updated["scope"],
            {
                "app_name": "demo",
                "service_name": "worker",
                "bcs_cluster_id": "cluster-1",
            },
        )

        unchanged: dict = FavoriteHandler(favorite_id=created["id"]).create_or_update(
            **self._favorite_params(group_id=self.public_group.id)
        )
        self.assertEqual(unchanged["scope"], updated["scope"])

        app_updated: dict = FavoriteHandler(favorite_id=created["id"]).create_or_update(
            **self._favorite_params(
                group_id=self.public_group.id,
                scope={"app_name": "demo"},
            )
        )
        self.assertEqual(app_updated["scope"]["service_name"], "worker")

    def test_group_scope_query_and_incremental_update(self):
        worker_group = FavoriteGroupHandler(space_uid=SPACE_UID).create_or_update(
            name="worker_group",
            source_type=SOURCE_TYPE,
            scope={"app_name": "demo", "service_name": "worker"},
        )
        other_app_group = FavoriteGroupHandler(space_uid=SPACE_UID).create_or_update(
            name="other_app_group",
            source_type=SOURCE_TYPE,
            scope={"app_name": "other-app", "service_name": "api"},
        )
        legacy_group = FavoriteGroupHandler(space_uid=SPACE_UID).create_or_update(
            name="legacy_group",
            source_type=SOURCE_TYPE,
        )

        app_groups: list[dict] = FavoriteGroupHandler(space_uid=SPACE_UID).list(
            source_type=SOURCE_TYPE,
            scope={"app_name": "demo"},
        )
        service_groups: list[dict] = FavoriteGroupHandler(space_uid=SPACE_UID).list(
            source_type=SOURCE_TYPE,
            scope={"app_name": "demo", "service_name": "api"},
        )
        legacy_groups: list[dict] = FavoriteGroupHandler(space_uid=SPACE_UID).list(source_type=SOURCE_TYPE)

        self.assertEqual(
            {group["id"] for group in app_groups},
            {
                self.private_group.id,
                self.ungrouped_group.id,
                self.public_group.id,
                worker_group["id"],
            },
        )
        self.assertEqual(
            {group["id"] for group in service_groups},
            {
                self.private_group.id,
                self.ungrouped_group.id,
                self.public_group.id,
            },
        )
        self.assertEqual(
            {group["id"] for group in legacy_groups},
            {
                self.private_group.id,
                self.ungrouped_group.id,
                self.public_group.id,
                worker_group["id"],
                other_app_group["id"],
                legacy_group["id"],
            },
        )
        self.assertTrue(all("scope" in group for group in legacy_groups))

        updated_group = FavoriteGroupHandler(group_id=self.public_group.id).create_or_update(
            name="renamed_scope_public_group",
            scope={"app_name": "demo"},
        )
        self.assertEqual(
            updated_group["scope"],
            {"app_name": "demo", "service_name": "api"},
        )
        unchanged_group = FavoriteGroupHandler(group_id=self.public_group.id).create_or_update(
            name="renamed_scope_public_group"
        )
        self.assertEqual(unchanged_group["scope"], updated_group["scope"])

    def test_scoped_group_create_reports_hidden_name_conflict(self):
        FavoriteGroupHandler(space_uid=SPACE_UID).create_or_update(
            name="same_name_group",
            source_type=SOURCE_TYPE,
            scope={"app_name": "demo", "service_name": "api"},
        )

        with self.assertRaisesMessage(
            FavoriteGroupAlreadyExistException,
            "在范围（app_name=demo, service_name=worker）创建分组失败，范围外存在同名分组",
        ):
            FavoriteGroupHandler(space_uid=SPACE_UID).create_or_update(
                name="same_name_group",
                source_type=SOURCE_TYPE,
                scope={"app_name": "demo", "service_name": "worker"},
            )

        with self.assertRaisesMessage(FavoriteGroupAlreadyExistException, "收藏组已存在"):
            FavoriteGroupHandler(space_uid=SPACE_UID).create_or_update(
                name="same_name_group",
                source_type=SOURCE_TYPE,
                scope={"app_name": "demo"},
            )

    def test_favorite_name_remains_unique_across_scope(self):
        FavoriteHandler(space_uid=SPACE_UID).create_or_update(
            **self._favorite_params(
                name="same_name_favorite",
                group_id=self.public_group.id,
                scope={"app_name": "demo", "service_name": "api"},
            )
        )

        with self.assertRaises(FavoriteAlreadyExistException):
            FavoriteHandler(space_uid=SPACE_UID).create_or_update(
                **self._favorite_params(
                    name="same_name_favorite",
                    group_id=self.public_group.id,
                    scope={"app_name": "demo", "service_name": "worker"},
                )
            )

    def test_favorite_scope_does_not_depend_on_group_scope(self):
        legacy_group = FavoriteGroupHandler(space_uid=SPACE_UID).create_or_update(
            name="legacy_public_group",
            source_type=SOURCE_TYPE,
        )
        favorite = self._create_favorite(
            "scoped_favorite_in_legacy_group",
            FavoriteGroup.objects.get(id=legacy_group["id"]),
            FavoriteVisibleType.PUBLIC.value,
            OTHER_USERNAME,
            {"app_name": "demo", "service_name": "api"},
        )

        favorites: list[dict] = FavoriteHandler(space_uid=SPACE_UID).list_favorites(
            source_type=SOURCE_TYPE,
            scope={"app_name": "demo", "service_name": "api"},
        )
        grouped_favorites: list[dict] = FavoriteHandler(space_uid=SPACE_UID).list_group_favorites(
            source_type=SOURCE_TYPE,
            scope={"app_name": "demo", "service_name": "api"},
        )
        ungrouped = next(
            group for group in grouped_favorites if group["group_type"] == FavoriteGroupType.UNGROUPED.value
        )

        self.assertEqual([item["id"] for item in favorites], [favorite.id])
        self.assertEqual(favorites[0]["group_id"], self.ungrouped_group.id)
        self.assertEqual([item["id"] for item in ungrouped["favorites"]], [favorite.id])

    def test_lookup_name_scope_key_is_matched_as_literal_key(self):
        literal_group = FavoriteGroupHandler(space_uid=SPACE_UID).create_or_update(
            name="literal_lookup_name_group",
            source_type=SOURCE_TYPE,
            scope={"contains": "literal-value"},
        )

        groups: list[dict] = FavoriteGroupHandler(space_uid=SPACE_UID).list(
            source_type=SOURCE_TYPE,
            scope={"contains": "literal-value"},
        )

        self.assertIn(literal_group["id"], {group["id"] for group in groups})

    def test_scope_query_filters_public_but_keeps_all_personal_favorites(self):
        self._create_favorite(
            "own_private",
            self.private_group,
            FavoriteVisibleType.PRIVATE.value,
            USERNAME,
            {"app_name": "other-app"},
        )
        self._create_favorite(
            "other_private",
            self.private_group,
            FavoriteVisibleType.PRIVATE.value,
            OTHER_USERNAME,
            {"app_name": "demo"},
        )
        self._create_favorite(
            "app_public",
            self.public_group,
            FavoriteVisibleType.PUBLIC.value,
            OTHER_USERNAME,
            {"app_name": "demo"},
        )
        self._create_favorite(
            "api_public",
            self.public_group,
            FavoriteVisibleType.PUBLIC.value,
            OTHER_USERNAME,
            {"app_name": "demo", "service_name": "api"},
        )
        self._create_favorite(
            "api_cluster_public",
            self.public_group,
            FavoriteVisibleType.PUBLIC.value,
            OTHER_USERNAME,
            {"app_name": "demo", "service_name": "api", "bcs_cluster_id": "cluster-1"},
        )
        self._create_favorite(
            "worker_public",
            self.public_group,
            FavoriteVisibleType.PUBLIC.value,
            OTHER_USERNAME,
            {"app_name": "demo", "service_name": "worker"},
        )
        self._create_favorite(
            "other_app_public",
            self.public_group,
            FavoriteVisibleType.PUBLIC.value,
            OTHER_USERNAME,
            {"app_name": "other-app", "service_name": "api"},
        )
        self._create_favorite(
            "legacy_public",
            self.ungrouped_group,
            FavoriteVisibleType.PUBLIC.value,
            OTHER_USERNAME,
            {},
        )

        app_favorites: list[dict] = FavoriteHandler(space_uid=SPACE_UID).list_favorites(
            source_type=SOURCE_TYPE,
            scope={"app_name": "demo"},
        )
        service_groups: list[dict] = FavoriteHandler(space_uid=SPACE_UID).list_group_favorites(
            source_type=SOURCE_TYPE,
            scope={"app_name": "demo", "service_name": "api"},
        )
        service_favorites: list[dict] = [favorite for group in service_groups for favorite in group["favorites"]]
        legacy_favorites: list[dict] = FavoriteHandler(space_uid=SPACE_UID).list_favorites(source_type=SOURCE_TYPE)

        self.assertEqual(
            {favorite["name"] for favorite in app_favorites},
            {"own_private", "app_public", "api_public", "api_cluster_public", "worker_public"},
        )
        self.assertEqual(
            {favorite["name"] for favorite in service_favorites},
            {"own_private", "api_public", "api_cluster_public"},
        )
        self.assertEqual(
            {favorite["name"] for favorite in legacy_favorites},
            {
                "own_private",
                "app_public",
                "api_public",
                "api_cluster_public",
                "worker_public",
                "other_app_public",
                "legacy_public",
            },
        )
        self.assertTrue(all("scope" in favorite for favorite in app_favorites))
