from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from iam import Resource

from apps.iam.exceptions import PermissionDeniedError
from apps.iam.handlers.actions import ActionEnum
from apps.iam.handlers.drf import (
    BatchIAMPermission,
    IAMPermission,
    InstanceActionForDataPermission,
    InstanceActionPermission,
    insert_permission_field,
)
from apps.iam.handlers.resources import ResourceEnum


@override_settings(IGNORE_IAM_PERMISSION=False)
class IAMPermissionCompatibilityTest(SimpleTestCase):
    @patch("apps.iam.handlers.drf.Permission")
    def test_drf_permission_keeps_using_permission_facade(self, permission_class):
        permission_client = permission_class.return_value
        drf_permission = IAMPermission(actions=[ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE])

        result = drf_permission.has_permission(Mock(), Mock())

        self.assertTrue(result)
        permission_client.is_allowed.assert_called_once_with(
            action=ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE,
            resources=[],
            raise_exception=True,
        )

    @override_settings(IGNORE_IAM_PERMISSION=True)
    @patch("apps.iam.handlers.drf.Permission")
    def test_global_ignore_switch_still_short_circuits_facade(self, permission_class):
        drf_permission = IAMPermission(actions=[ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE])

        self.assertTrue(drf_permission.has_permission(Mock(), Mock()))
        permission_class.assert_not_called()

    @patch("apps.iam.handlers.drf.Permission")
    def test_instance_permission_builds_resource_and_uses_permission_facade(self, permission_class):
        resource = Mock()
        resource_meta = Mock()
        resource_meta.create_instance.return_value = resource
        instance_permission = InstanceActionPermission([ActionEnum.MANAGE_COLLECTION], resource_meta)
        view = Mock(lookup_url_kwarg=None, lookup_field="pk", kwargs={"pk": "42"})

        result = instance_permission.has_permission(Mock(), view)

        self.assertTrue(result)
        resource_meta.create_instance.assert_called_once_with("42")
        permission_class.return_value.is_allowed.assert_called_once_with(
            action=ActionEnum.MANAGE_COLLECTION,
            resources=[resource],
            raise_exception=True,
        )

    @patch("apps.iam.handlers.drf.Permission")
    def test_instance_permission_delegates_missing_local_resource_to_iam(self, permission_class):
        permission = InstanceActionPermission([ActionEnum.MANAGE_INDICES], ResourceEnum.INDICES)
        resource = Resource(ResourceEnum.INDICES.system_id, ResourceEnum.INDICES.id, "1", None)
        with patch.object(ResourceEnum.INDICES, "create_instance", return_value=resource):
            view = SimpleNamespace(kwargs={"pk": "1"}, lookup_url_kwarg=None, lookup_field="pk")

            result = permission.has_permission(SimpleNamespace(), view)

        self.assertTrue(result)
        permission_class.return_value.is_allowed.assert_called_once()
        self.assertEqual(permission.resources[0].id, "1")

    @patch("apps.iam.handlers.drf.Permission")
    def test_data_permission_delegates_missing_local_resource_to_iam(self, permission_class):
        permission = InstanceActionForDataPermission(
            "index_set_id",
            [ActionEnum.MANAGE_INDICES],
            ResourceEnum.INDICES,
        )
        resource = Resource(ResourceEnum.INDICES.system_id, ResourceEnum.INDICES.id, "1", None)
        with patch.object(ResourceEnum.INDICES, "create_instance", return_value=resource):
            request = SimpleNamespace(method="GET", query_params={"index_set_id": "1"}, data={})
            view = SimpleNamespace(kwargs={}, lookup_url_kwarg=None, lookup_field="pk")

            result = permission.has_permission(request, view)

        self.assertTrue(result)
        permission_class.return_value.is_allowed.assert_called_once()
        self.assertEqual(permission.resources[0].id, "1")

    @patch("apps.iam.handlers.drf.Permission")
    def test_batch_permission_checks_every_resource_separately(self, permission_class):
        resources = [Mock(id="1"), Mock(id="2")]
        resource_meta = Mock()
        resource_meta.create_instance.side_effect = resources
        permission_class.return_value.batch_is_allowed.return_value = {
            "1": {ActionEnum.VIEW_COLLECTION.id: True},
            "2": {ActionEnum.VIEW_COLLECTION.id: True},
        }
        batch_permission = BatchIAMPermission("instance_ids", [ActionEnum.VIEW_COLLECTION], resource_meta)
        request = Mock(method="POST", data={"instance_ids": ["1", "2"]})

        result = batch_permission.has_permission(request, Mock())

        self.assertTrue(result)
        self.assertEqual(resource_meta.create_instance.call_count, 2)
        # 同类型多实例必须每个实例单独成组，单点 is_allowed 只会对其中一个求值
        permission_class.return_value.batch_is_allowed.assert_called_once_with(
            [ActionEnum.VIEW_COLLECTION],
            [[resources[0]], [resources[1]]],
        )
        permission_class.return_value.is_allowed.assert_not_called()

    @patch("apps.iam.handlers.drf.Permission")
    def test_batch_permission_denies_unauthorized_instance_in_any_position(self, permission_class):
        """无权限实例无论排在列表哪一位都必须被拦下。

        历史实现把整份列表塞进单点 is_allowed：V3 只对最后一个求值，V4 只取第一个，
        用户把自己有权限的实例放到被校验的那一位就能读到无权实例的数据。
        """
        for instance_ids in (["denied", "allowed"], ["allowed", "denied"]):
            with self.subTest(instance_ids=instance_ids):
                permission_class.reset_mock()
                resource_meta = Mock()
                resource_meta.create_instance.side_effect = lambda instance_id: Mock(id=instance_id)
                permission_client = permission_class.return_value
                permission_client.batch_is_allowed.return_value = {
                    "allowed": {ActionEnum.VIEW_COLLECTION.id: True},
                    "denied": {ActionEnum.VIEW_COLLECTION.id: False},
                }
                permission_client.get_apply_data.return_value = ({"actions": []}, "https://apply.example.com")
                batch_permission = BatchIAMPermission("instance_ids", [ActionEnum.VIEW_COLLECTION], resource_meta)
                request = Mock(method="POST", data={"instance_ids": instance_ids})

                with self.assertRaises(PermissionDeniedError):
                    batch_permission.has_permission(request, Mock())

                actions, denied_resources = permission_client.get_apply_data.call_args.args
                self.assertEqual(actions, [ActionEnum.VIEW_COLLECTION])
                self.assertEqual([resource.id for resource in denied_resources], ["denied"])

    @patch("apps.iam.handlers.drf.Permission")
    def test_batch_permission_denies_when_result_misses_resource(self, permission_class):
        """批量结果缺少某个实例时按拒绝处理，不能因为查不到就放行。"""
        resource_meta = Mock()
        resource_meta.create_instance.side_effect = lambda instance_id: Mock(id=instance_id)
        permission_client = permission_class.return_value
        permission_client.batch_is_allowed.return_value = {"1": {ActionEnum.VIEW_COLLECTION.id: True}}
        permission_client.get_apply_data.return_value = ({"actions": []}, "https://apply.example.com")
        batch_permission = BatchIAMPermission("instance_ids", [ActionEnum.VIEW_COLLECTION], resource_meta)
        request = Mock(method="POST", data={"instance_ids": ["1", "2"]})

        with self.assertRaises(PermissionDeniedError):
            batch_permission.has_permission(request, Mock())

        _actions, denied_resources = permission_client.get_apply_data.call_args.args
        self.assertEqual([resource.id for resource in denied_resources], ["2"])

    @patch("apps.iam.handlers.drf.Permission")
    def test_batch_permission_requires_every_action_on_every_resource(self, permission_class):
        actions = [ActionEnum.VIEW_COLLECTION, ActionEnum.MANAGE_COLLECTION]
        resource_meta = Mock()
        resource_meta.create_instance.side_effect = lambda instance_id: Mock(id=instance_id)
        permission_client = permission_class.return_value
        permission_client.batch_is_allowed.return_value = {
            "1": {ActionEnum.VIEW_COLLECTION.id: True, ActionEnum.MANAGE_COLLECTION.id: True},
            "2": {ActionEnum.VIEW_COLLECTION.id: True, ActionEnum.MANAGE_COLLECTION.id: False},
        }
        permission_client.get_apply_data.return_value = ({"actions": []}, "https://apply.example.com")
        batch_permission = BatchIAMPermission("instance_ids", actions, resource_meta)
        request = Mock(method="POST", data={"instance_ids": ["1", "2"]})

        with self.assertRaises(PermissionDeniedError):
            batch_permission.has_permission(request, Mock())

        called_actions, denied_resources = permission_client.get_apply_data.call_args.args
        self.assertEqual(called_actions, [ActionEnum.MANAGE_COLLECTION])
        self.assertEqual([resource.id for resource in denied_resources], ["2"])

    @patch("apps.iam.handlers.drf.Permission")
    def test_batch_permission_without_actions_skips_iam_call(self, permission_class):
        resource_meta = Mock()
        resource_meta.create_instance.side_effect = lambda instance_id: Mock(id=instance_id)
        batch_permission = BatchIAMPermission("instance_ids", [], resource_meta)
        request = Mock(method="POST", data={"instance_ids": ["1"]})

        self.assertTrue(batch_permission.has_permission(request, Mock()))

        permission_class.return_value.batch_is_allowed.assert_not_called()

    @patch("apps.iam.handlers.drf.Permission")
    def test_batch_permission_reads_instance_ids_from_query_params_on_get(self, permission_class):
        resource_meta = Mock()
        resource_meta.create_instance.side_effect = lambda instance_id: Mock(id=instance_id)
        permission_class.return_value.batch_is_allowed.return_value = {"1": {ActionEnum.VIEW_COLLECTION.id: True}}
        batch_permission = BatchIAMPermission("instance_ids", [ActionEnum.VIEW_COLLECTION], resource_meta)
        request = Mock(method="GET", query_params={"instance_ids": ["1"]})

        self.assertTrue(batch_permission.has_permission(request, Mock()))

    @patch("apps.iam.handlers.drf.Permission")
    def test_insert_permission_field_uses_batch_facade_and_keeps_response_shape(self, permission_class):
        action = ActionEnum.VIEW_COLLECTION
        resources = [Mock(), Mock()]
        resource_meta = Mock()
        resource_meta.create_simple_instance.side_effect = resources
        permission_class.return_value.batch_is_allowed.return_value = {
            "1": {action.id: True},
            "2": {action.id: False},
        }
        response = Mock(data=[{"id": 1, "bk_biz_id": 10}, {"id": 2}])
        view_func = Mock(return_value=response)
        wrapped_view = insert_permission_field([action], resource_meta)(view_func)

        result = wrapped_view()

        self.assertIs(result, response)
        self.assertEqual(
            response.data,
            [
                {"id": 1, "bk_biz_id": 10, "permission": {action.id: True}},
                {"id": 2, "permission": {action.id: False}},
            ],
        )
        permission_class.return_value.batch_is_allowed.assert_called_once_with(
            [action],
            [[resources[0]], [resources[1]]],
        )

    @patch("apps.iam.handlers.drf.Permission")
    def test_insert_permission_field_keeps_items_without_id(self, permission_class):
        action = ActionEnum.VIEW_COLLECTION
        resource = Mock()
        resource_meta = Mock()
        resource_meta.create_simple_instance.return_value = resource
        permission_class.return_value.batch_is_allowed.return_value = {"1": {action.id: True}}
        response = Mock(data=[{"id": None, "name": "group"}, {"id": 1, "bk_biz_id": 2}])
        wrapped_view = insert_permission_field([action], resource_meta, id_field=lambda item: item.get("id"))(
            Mock(return_value=response)
        )

        result = wrapped_view()

        self.assertIs(result, response)
        self.assertEqual(len(response.data), 2)
        self.assertNotIn("permission", response.data[0])
        self.assertTrue(response.data[1]["permission"][action.id])

    @patch("apps.iam.handlers.drf.Permission")
    def test_insert_permission_field_applies_always_allowed(self, permission_class):
        action = ActionEnum.MANAGE_ES_SOURCE
        resource_meta = Mock()
        resource_meta.create_simple_instance.return_value = Mock()
        permission_class.return_value.batch_is_allowed.return_value = {"10": {action.id: False}}
        response = Mock(data=[{"id": 10, "bk_biz_id": 0}])
        wrapped_view = insert_permission_field(
            [action],
            resource_meta,
            always_allowed=lambda item: item.get("bk_biz_id") == 0,
        )(Mock(return_value=response))

        wrapped_view()

        self.assertTrue(response.data[0]["permission"][action.id])

    @override_settings(IGNORE_IAM_PERMISSION=True)
    @patch("apps.iam.handlers.drf.Permission")
    def test_insert_permission_field_global_ignore_annotates_all_actions_allowed(self, permission_class):
        action = ActionEnum.VIEW_COLLECTION
        resource_meta = Mock()
        resource_meta.create_simple_instance.return_value = Mock()
        response = Mock(data=[{"id": 1, "bk_biz_id": 2}])
        wrapped_view = insert_permission_field([action], resource_meta)(Mock(return_value=response))

        wrapped_view()

        self.assertTrue(response.data[0]["permission"][action.id])
        permission_class.assert_not_called()
