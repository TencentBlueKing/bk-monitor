from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from apps.iam.handlers.actions import ActionEnum
from apps.iam.handlers.drf import BatchIAMPermission, IAMPermission, InstanceActionPermission, insert_permission_field


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
    def test_batch_permission_builds_all_resources_and_uses_permission_facade(self, permission_class):
        resources = [Mock(), Mock()]
        resource_meta = Mock()
        resource_meta.create_instance.side_effect = resources
        batch_permission = BatchIAMPermission("instance_ids", [ActionEnum.VIEW_COLLECTION], resource_meta)
        request = Mock(method="POST", data={"instance_ids": ["1", "2"]})

        result = batch_permission.has_permission(request, Mock())

        self.assertTrue(result)
        self.assertEqual(resource_meta.create_instance.call_count, 2)
        permission_class.return_value.is_allowed.assert_called_once_with(
            action=ActionEnum.VIEW_COLLECTION,
            resources=resources,
            raise_exception=True,
        )

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
