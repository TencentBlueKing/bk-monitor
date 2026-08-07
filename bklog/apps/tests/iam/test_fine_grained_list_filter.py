from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.response import Response

from apps.iam.handlers.actions import ActionEnum
from apps.iam.handlers.drf import insert_permission_field
from apps.iam.handlers.resources import ResourceEnum


class FineGrainedListAnnotateTest(SimpleTestCase):
    """列表默认只标注 permission，不剔除无权限行（与历史口径一致）。"""

    @override_settings(IGNORE_IAM_PERMISSION=False)
    @patch("apps.iam.handlers.drf.Permission")
    def test_insert_permission_field_keeps_unauthorized_rows(self, permission_cls):
        permission_cls.return_value.batch_is_allowed.return_value = {
            "1": {ActionEnum.VIEW_COLLECTION.id: True, ActionEnum.MANAGE_COLLECTION.id: False},
            "2": {ActionEnum.VIEW_COLLECTION.id: False, ActionEnum.MANAGE_COLLECTION.id: False},
        }

        @insert_permission_field(
            actions=[ActionEnum.VIEW_COLLECTION, ActionEnum.MANAGE_COLLECTION],
            resource_meta=ResourceEnum.COLLECTION,
            id_field=lambda item: item["collector_config_id"],
            data_field=lambda data: data["list"],
        )
        def fake_list(_request):
            return Response(
                {
                    "count": 2,
                    "list": [
                        {"collector_config_id": 1, "bk_biz_id": 2, "name": "a"},
                        {"collector_config_id": 2, "bk_biz_id": 2, "name": "b"},
                    ],
                }
            )

        response = fake_list(SimpleNamespace())
        self.assertEqual(len(response.data["list"]), 2)
        self.assertEqual(response.data["count"], 2)
        self.assertTrue(response.data["list"][0]["permission"][ActionEnum.VIEW_COLLECTION.id])
        self.assertFalse(response.data["list"][1]["permission"][ActionEnum.VIEW_COLLECTION.id])

    @override_settings(IGNORE_IAM_PERMISSION=False)
    @patch("apps.iam.handlers.drf.Permission")
    def test_always_allowed_forces_permission_true(self, permission_cls):
        permission_cls.return_value.batch_is_allowed.return_value = {
            "10": {ActionEnum.MANAGE_ES_SOURCE.id: False},
        }

        @insert_permission_field(
            actions=[ActionEnum.MANAGE_ES_SOURCE],
            resource_meta=ResourceEnum.ES_SOURCE,
            id_field=lambda item: item["storage_cluster_id"],
            always_allowed=lambda item: item.get("bk_biz_id") == 0,
        )
        def fake_list(_request):
            return Response([{"storage_cluster_id": 10, "bk_biz_id": 0}])

        response = fake_list(SimpleNamespace())
        self.assertEqual(len(response.data), 1)
        self.assertTrue(response.data[0]["permission"][ActionEnum.MANAGE_ES_SOURCE.id])

    @override_settings(IGNORE_IAM_PERMISSION=True)
    def test_ignore_permission_annotates_all_true(self):
        @insert_permission_field(
            actions=[ActionEnum.VIEW_COLLECTION],
            resource_meta=ResourceEnum.COLLECTION,
            id_field=lambda item: item["collector_config_id"],
        )
        def fake_list(_request):
            return Response([{"collector_config_id": 1, "bk_biz_id": 2}])

        response = fake_list(SimpleNamespace())
        self.assertTrue(response.data[0]["permission"][ActionEnum.VIEW_COLLECTION.id])

    @override_settings(IGNORE_IAM_PERMISSION=False)
    @patch("apps.iam.handlers.drf.Permission")
    def test_items_without_id_are_kept(self, permission_cls):
        permission_cls.return_value.batch_is_allowed.return_value = {
            "1": {ActionEnum.VIEW_COLLECTION.id: True},
        }

        @insert_permission_field(
            actions=[ActionEnum.VIEW_COLLECTION],
            resource_meta=ResourceEnum.COLLECTION,
            id_field=lambda item: item.get("collector_config_id"),
        )
        def fake_list(_request):
            return Response(
                [
                    {"collector_config_id": None, "name": "group"},
                    {"collector_config_id": 1, "bk_biz_id": 2},
                ]
            )

        response = fake_list(SimpleNamespace())
        self.assertEqual(len(response.data), 2)

    def test_instance_action_permission_rejects_missing_local_resource(self):
        from apps.iam.handlers.drf import InstanceActionPermission
        from iam import Resource

        permission = InstanceActionPermission([ActionEnum.MANAGE_INDICES], ResourceEnum.INDICES)
        with patch.object(
            ResourceEnum.INDICES,
            "create_instance",
            return_value=Resource(ResourceEnum.INDICES.system_id, ResourceEnum.INDICES.id, "1", None),
        ):
            view = SimpleNamespace(kwargs={"pk": "1"}, lookup_url_kwarg=None, lookup_field="pk")
            self.assertFalse(permission.has_permission(SimpleNamespace(), view))

    def test_instance_action_for_data_permission_rejects_missing_local_resource(self):
        from apps.iam.handlers.drf import InstanceActionForDataPermission
        from iam import Resource

        permission = InstanceActionForDataPermission(
            "index_set_id",
            [ActionEnum.MANAGE_INDICES],
            ResourceEnum.INDICES,
        )
        with patch.object(
            ResourceEnum.INDICES,
            "create_instance",
            return_value=Resource(ResourceEnum.INDICES.system_id, ResourceEnum.INDICES.id, "1", None),
        ):
            request = SimpleNamespace(method="GET", query_params={"index_set_id": "1"}, data={})
            view = SimpleNamespace(kwargs={}, lookup_url_kwarg=None, lookup_field="pk")
            self.assertFalse(permission.has_permission(request, view))

    @override_settings(IGNORE_IAM_PERMISSION=False)
    @patch("apps.iam.handlers.drf.Permission")
    def test_ownership_filter_drops_cross_space_before_iam(self, permission_cls):
        from apps.iam.handlers.scope import resolve_collection_bk_biz_id, resolve_request_bk_biz_id

        permission_cls.return_value.batch_is_allowed.return_value = {
            "1": {ActionEnum.VIEW_COLLECTION.id: True},
        }

        @insert_permission_field(
            actions=[ActionEnum.VIEW_COLLECTION],
            resource_meta=ResourceEnum.COLLECTION,
            id_field=lambda item: item["collector_config_id"],
            data_field=lambda data: data["list"],
            ownership_resolve=lambda item: resolve_collection_bk_biz_id(bk_biz_id=item.get("bk_biz_id")),
            ownership_expected=resolve_request_bk_biz_id,
        )
        def fake_list(_request):
            return Response(
                {
                    "count": 3,
                    "list": [
                        {"collector_config_id": 1, "bk_biz_id": 2},
                        {"collector_config_id": 2, "bk_biz_id": 3},
                        {"collector_config_id": 3, "bk_biz_id": None},
                    ],
                }
            )

        request = SimpleNamespace(query_params={"bk_biz_id": 2})
        response = fake_list(request)
        self.assertEqual([item["collector_config_id"] for item in response.data["list"]], [1])
        self.assertEqual(response.data["count"], 1)
        permission_cls.return_value.batch_is_allowed.assert_called_once()
        resources = permission_cls.return_value.batch_is_allowed.call_args[0][1]
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0][0].id, "1")

    @override_settings(IGNORE_IAM_PERMISSION=False)
    @patch("apps.iam.handlers.drf.Permission")
    def test_ownership_filter_supports_non_bkcc_space_uid(self, permission_cls):
        from apps.iam.handlers.scope import resolve_indices_bk_biz_id, resolve_request_bk_biz_id

        permission_cls.return_value.batch_is_allowed.return_value = {
            "11": {ActionEnum.MANAGE_INDICES.id: True},
        }

        @insert_permission_field(
            actions=[ActionEnum.MANAGE_INDICES],
            resource_meta=ResourceEnum.INDICES,
            id_field=lambda item: item["index_set_id"],
            ownership_resolve=lambda item: resolve_indices_bk_biz_id(space_uid=item.get("space_uid", "")),
            ownership_expected=resolve_request_bk_biz_id,
        )
        def fake_list(_request):
            return Response(
                [
                    {"index_set_id": 11, "space_uid": "bkci__demo"},
                    {"index_set_id": 12, "space_uid": "bkcc__2"},
                ]
            )

        mapping = {"bkci__demo": -5000001, "bkcc__2": 2}

        def fake_space_uid_to_bk_biz_id(space_uid, id=None):
            return mapping[space_uid]

        with (
            patch("apps.iam.handlers.scope.space_uid_to_bk_biz_id", side_effect=fake_space_uid_to_bk_biz_id),
            patch("apps.iam.handlers.resources.space_uid_to_bk_biz_id", side_effect=fake_space_uid_to_bk_biz_id),
        ):
            request = SimpleNamespace(query_params={"space_uid": "bkci__demo"})
            response = fake_list(request)

        self.assertEqual([item["index_set_id"] for item in response.data], [11])

    @override_settings(IGNORE_IAM_PERMISSION=False)
    @patch("apps.iam.handlers.drf.Permission")
    def test_ownership_filter_keeps_always_allowed_and_missing_id(self, permission_cls):
        from apps.iam.handlers.scope import resolve_es_source_bk_biz_id, resolve_request_bk_biz_id

        permission_cls.return_value.batch_is_allowed.return_value = {
            "10": {ActionEnum.MANAGE_ES_SOURCE.id: True},
        }

        @insert_permission_field(
            actions=[ActionEnum.MANAGE_ES_SOURCE],
            resource_meta=ResourceEnum.ES_SOURCE,
            id_field=lambda item: item.get("storage_cluster_id"),
            always_allowed=lambda item: item.get("bk_biz_id") == 0,
            ownership_resolve=lambda item: resolve_es_source_bk_biz_id(bk_biz_id=item.get("bk_biz_id")),
            ownership_expected=resolve_request_bk_biz_id,
            ownership_allow_platform=True,
        )
        def fake_list(_request):
            return Response(
                [
                    {"storage_cluster_id": None, "name": "group"},
                    {"storage_cluster_id": 10, "bk_biz_id": 0},
                    {"storage_cluster_id": 11, "bk_biz_id": 9},
                ]
            )

        response = fake_list(SimpleNamespace(query_params={"bk_biz_id": 2}))
        self.assertEqual(len(response.data), 2)
        self.assertIsNone(response.data[0]["storage_cluster_id"])
        self.assertEqual(response.data[1]["storage_cluster_id"], 10)

    @override_settings(IGNORE_IAM_PERMISSION=False)
    @patch("apps.iam.handlers.drf.Permission")
    def test_ownership_filter_on_single_object_and_empty_candidates(self, permission_cls):
        from apps.iam.handlers.scope import resolve_collection_bk_biz_id, resolve_request_bk_biz_id

        permission_cls.return_value.batch_is_allowed.return_value = {
            "1": {ActionEnum.VIEW_COLLECTION.id: True},
        }

        @insert_permission_field(
            actions=[ActionEnum.VIEW_COLLECTION],
            resource_meta=ResourceEnum.COLLECTION,
            id_field=lambda item: item["collector_config_id"],
            many=False,
            ownership_resolve=lambda item: resolve_collection_bk_biz_id(bk_biz_id=item.get("bk_biz_id")),
            ownership_expected=resolve_request_bk_biz_id,
        )
        def fake_retrieve(_request):
            return Response({"collector_config_id": 1, "bk_biz_id": 2})

        response = fake_retrieve(SimpleNamespace(query_params={"bk_biz_id": 2}))
        self.assertEqual(response.data["collector_config_id"], 1)
        permission_cls.return_value.batch_is_allowed.assert_called_once()
        permission_cls.return_value.batch_is_allowed.reset_mock()

        @insert_permission_field(
            actions=[ActionEnum.VIEW_COLLECTION],
            resource_meta=ResourceEnum.COLLECTION,
            id_field=lambda item: item["collector_config_id"],
            data_field=lambda data: data["list"],
            ownership_resolve=lambda item: resolve_collection_bk_biz_id(bk_biz_id=item.get("bk_biz_id")),
            ownership_expected=resolve_request_bk_biz_id,
        )
        def fake_list_all_cross_space(_request):
            return Response({"count": 1, "list": [{"collector_config_id": 2, "bk_biz_id": 9}]})

        empty_response = fake_list_all_cross_space(SimpleNamespace(query_params={"bk_biz_id": 2}))
        self.assertEqual(empty_response.data["list"], [])
        self.assertEqual(empty_response.data["count"], 0)
        permission_cls.return_value.batch_is_allowed.assert_not_called()

    def test_extract_request_supports_kwargs_and_missing(self):
        from apps.iam.handlers.drf import _extract_request

        request = SimpleNamespace(query_params={"bk_biz_id": 1})
        self.assertIs(_extract_request((), {"request": request}), request)
        self.assertIsNone(_extract_request((), {}))


class OptionalDenyFilterCapabilityTest(SimpleTestCase):
    """deny_filter 仍保留为可选能力，默认列表不启用。"""

    @override_settings(IGNORE_IAM_PERMISSION=False)
    @patch("apps.iam.handlers.drf.Permission")
    def test_optional_deny_filter_can_remove_unauthorized_rows(self, permission_cls):
        permission_cls.return_value.batch_is_allowed.return_value = {
            "1": {ActionEnum.VIEW_COLLECTION.id: True},
            "2": {ActionEnum.VIEW_COLLECTION.id: False},
        }

        @insert_permission_field(
            actions=[ActionEnum.VIEW_COLLECTION],
            resource_meta=ResourceEnum.COLLECTION,
            id_field=lambda item: item["collector_config_id"],
            data_field=lambda data: data["list"],
            deny_filter=True,
        )
        def fake_list(_request):
            return Response(
                {
                    "count": 2,
                    "list": [
                        {"collector_config_id": 1, "bk_biz_id": 2},
                        {"collector_config_id": 2, "bk_biz_id": 2},
                    ],
                }
            )

        response = fake_list(SimpleNamespace())
        self.assertEqual([item["collector_config_id"] for item in response.data["list"]], [1])
        self.assertEqual(response.data["count"], 1)

    @override_settings(IGNORE_IAM_PERMISSION=False)
    @patch("apps.iam.handlers.drf.Permission")
    def test_optional_deny_filter_rewrites_when_ownership_empties_candidates(self, permission_cls):
        from apps.iam.handlers.scope import resolve_collection_bk_biz_id, resolve_request_bk_biz_id

        @insert_permission_field(
            actions=[ActionEnum.VIEW_COLLECTION],
            resource_meta=ResourceEnum.COLLECTION,
            id_field=lambda item: item["collector_config_id"],
            data_field=lambda data: data["list"],
            deny_filter=True,
            ownership_resolve=lambda item: resolve_collection_bk_biz_id(bk_biz_id=item.get("bk_biz_id")),
            ownership_expected=resolve_request_bk_biz_id,
        )
        def fake_list(_request):
            return Response({"count": 1, "list": [{"collector_config_id": 2, "bk_biz_id": 9}]})

        response = fake_list(SimpleNamespace(query_params={"bk_biz_id": 2}))
        self.assertEqual(response.data["list"], [])
        self.assertEqual(response.data["count"], 0)
        permission_cls.return_value.batch_is_allowed.assert_not_called()
