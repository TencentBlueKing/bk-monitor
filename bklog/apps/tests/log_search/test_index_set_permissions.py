from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from apps.iam import ActionEnum
from apps.iam.exceptions import PermissionDeniedError
from apps.iam.handlers.drf import BusinessActionPermission, InstanceActionPermission, ViewBusinessPermission
from apps.log_search.models import LogIndexSet
from apps.log_search.views.index_set_views import DesensitizeConfigWritePermission, IndexSetViewSet


@override_settings(ESQUERY_WHITE_LIST=["bk_monitor"])
class IndexSetPermissionTests(SimpleTestCase):
    """get_permissions() 返回正确的权限类（白名单/非白名单各 action 的分发逻辑）。"""

    @staticmethod
    def build_view(action: str, enforce_permission: bool):
        view = IndexSetViewSet()
        view.action = action
        view.request = SimpleNamespace(
            query_params={},
            data={"enforce_permission": enforce_permission},
        )
        return view

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_white_list_keeps_legacy_bypass_without_enforcement(self, get_auth_info):
        """白名单内未强制鉴权的 action 返回空列表。"""
        get_auth_info.return_value = {"bk_app_code": "bk_monitor", "bk_username": "alice"}
        self.assertEqual(self.build_view("update", False).get_permissions(), [])

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_white_list_can_enforce_create_permission(self, get_auth_info):
        """白名单内强制鉴权时 create 返回 BusinessActionPermission。"""
        get_auth_info.return_value = {"bk_app_code": "bk_monitor", "bk_username": "alice"}
        permissions = self.build_view("create", True).get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], BusinessActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.CREATE_INDICES])

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_white_list_can_enforce_update_permission(self, get_auth_info):
        """白名单内强制鉴权时 update 返回 InstanceActionPermission([MANAGE_INDICES])。"""
        get_auth_info.return_value = {"bk_app_code": "bk_monitor", "bk_username": "alice"}
        permissions = self.build_view("update", True).get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.MANAGE_INDICES])

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_destroy_returns_manage_indices(self, get_auth_info):
        """destroy（删除索引集）返回 InstanceActionPermission([MANAGE_INDICES])。"""
        get_auth_info.return_value = {"bk_app_code": "untrusted_app", "bk_username": "alice"}
        permissions = self.build_view("destroy", True).get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.MANAGE_INDICES])

    # Desensitize config write endpoints — normal auth path

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_desensitize_config_create_returns_write_permission(self, get_auth_info):
        """desensitize_config_create 返回 DesensitizeConfigWritePermission。"""
        get_auth_info.return_value = {"bk_app_code": "untrusted_app", "bk_username": "alice"}
        permissions = self.build_view("desensitize_config_create", True).get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], DesensitizeConfigWritePermission)

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_desensitize_config_update_returns_write_permission(self, get_auth_info):
        """desensitize_config_update 返回 DesensitizeConfigWritePermission。"""
        get_auth_info.return_value = {"bk_app_code": "untrusted_app", "bk_username": "alice"}
        permissions = self.build_view("desensitize_config_update", True).get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], DesensitizeConfigWritePermission)

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_desensitize_config_delete_returns_write_permission(self, get_auth_info):
        """desensitize_config_delete 返回 DesensitizeConfigWritePermission。"""
        get_auth_info.return_value = {"bk_app_code": "untrusted_app", "bk_username": "alice"}
        permissions = self.build_view("desensitize_config_delete", True).get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], DesensitizeConfigWritePermission)

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_desensitize_config_retrieve_falls_to_view_business(self, get_auth_info):
        """desensitize_config_retrieve（读操作）返回 ViewBusinessPermission。"""
        get_auth_info.return_value = {"bk_app_code": "untrusted_app", "bk_username": "alice"}
        permissions = self.build_view("desensitize_config_retrieve", True).get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], ViewBusinessPermission)

    # Whitelist bypass paths for desensitize config endpoints

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_desensitize_config_create_whitelist_no_longer_bypass(self, get_auth_info):
        """白名单应用创建脱敏配置未强制鉴权时不再 bypass，仍走实例鉴权。"""
        get_auth_info.return_value = {"bk_app_code": "bk_monitor", "bk_username": "alice"}
        permissions = self.build_view("desensitize_config_create", False).get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], DesensitizeConfigWritePermission)

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_desensitize_config_update_whitelist_no_longer_bypass(self, get_auth_info):
        """白名单应用更新脱敏配置未强制鉴权时不再 bypass，仍走实例鉴权。"""
        get_auth_info.return_value = {"bk_app_code": "bk_monitor", "bk_username": "alice"}
        permissions = self.build_view("desensitize_config_update", False).get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], DesensitizeConfigWritePermission)

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_desensitize_config_delete_whitelist_no_longer_bypass(self, get_auth_info):
        """白名单应用删除脱敏配置未强制鉴权时不再 bypass，仍走实例鉴权。"""
        get_auth_info.return_value = {"bk_app_code": "bk_monitor", "bk_username": "alice"}
        permissions = self.build_view("desensitize_config_delete", False).get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], DesensitizeConfigWritePermission)

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_desensitize_config_retrieve_whitelist_bypass(self, get_auth_info):
        """白名单应用读取脱敏配置未强制鉴权时 bypass。"""
        get_auth_info.return_value = {"bk_app_code": "bk_monitor", "bk_username": "alice"}
        self.assertEqual(self.build_view("desensitize_config_retrieve", False).get_permissions(), [])

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_non_whitelist_must_enforce(self, get_auth_info):
        """非白名单应用即使未传 enforce_permission 也在 get_permissions 中正常鉴权。"""
        get_auth_info.return_value = {"bk_app_code": "untrusted_app", "bk_username": "alice"}
        permissions = self.build_view("desensitize_config_create", False).get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], DesensitizeConfigWritePermission)

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_non_whitelist_not_in_white_list(self, get_auth_info):
        """非白名单应用 always 鉴权，即使不传 enforce_permission 也正常。"""
        get_auth_info.return_value = {"bk_app_code": "untrusted_app", "bk_username": "alice"}
        permissions = self.build_view("update", False).get_permissions()
        self.assertNotEqual(permissions, [])

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_exception_in_get_auth_info_does_not_crash(self, get_auth_info):
        """get_auth_info 异常时降级为正常鉴权。"""
        get_auth_info.side_effect = Exception("unexpected")
        # 应不会抛异常，而是正常返回权限类（update 仍走白名单路径）
        permissions = self.build_view("update", False).get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)


@override_settings(IGNORE_IAM_PERMISSION=False, ESQUERY_WHITE_LIST=[])
class DesensitizeConfigWritePermissionHasPermissionTests(TestCase):
    """
    验证 DesensitizeConfigWritePermission.has_permission 按索引集类型
    正确选择 action/resource 并调用 IAM 鉴权。

    用真实 model 记录 + mock Permission.is_allowed（正确层级的 mock），
    确保整个 has_permission → super().has_permission → Permission.is_allowed
    调用链被覆盖。
    """

    SPACE_UID = "bkcc__2"

    @classmethod
    def setUpTestData(cls):
        # 索引集 A: 有 collector_config_id（采集项类型）
        cls.index_set_with_collection = LogIndexSet.objects.create(
            index_set_name="with_collection",
            space_uid=cls.SPACE_UID,
            scenario_id="log",
            collector_config_id=999001,
        )
        # 索引集 B: 无 collector_config_id（第三方 ES 类型）
        cls.index_set_without_collection = LogIndexSet.objects.create(
            index_set_name="without_collection",
            space_uid=cls.SPACE_UID,
            scenario_id="es",
            collector_config_id=None,
        )
        # 索引集 C: collector_config_id=0（边界情况，应视同无采集项）
        cls.index_set_zero_collector = LogIndexSet.objects.create(
            index_set_name="zero_collector",
            space_uid=cls.SPACE_UID,
            scenario_id="log",
            collector_config_id=0,
        )

    @staticmethod
    def build_view(index_set_id):
        view = IndexSetViewSet()
        view.action = "desensitize_config_create"
        view.kwargs = {"index_set_id": index_set_id}
        view.request = SimpleNamespace(
            query_params={},
            data={},
            META={},
        )
        return view

    @patch("apps.iam.handlers.permission.Permission.is_allowed")
    def test_collection_index_set_uses_manage_collection(self, mock_is_allowed):
        """有采集项的索引集 → is_allowed 被调用时传 MANAGE_COLLECTION@collector_config_id. """
        mock_is_allowed.return_value = True

        perm = DesensitizeConfigWritePermission()
        view = self.build_view(self.index_set_with_collection.index_set_id)
        result = perm.has_permission(view.request, view)

        self.assertTrue(result)
        self.assertEqual(perm.actions, [ActionEnum.MANAGE_COLLECTION])
        self.assertEqual(len(perm.resources), 1)
        self.assertEqual(perm.resources[0].id, "999001")
        self.assertEqual(perm.resources[0].type, "collection")
        # 验证 is_allowed 被用正确的参数调用
        mock_is_allowed.assert_called_once()
        self.assertEqual(mock_is_allowed.call_args.kwargs["action"], ActionEnum.MANAGE_COLLECTION)
        self.assertEqual(mock_is_allowed.call_args.kwargs["resources"][0].id, "999001")

    @patch("apps.iam.handlers.permission.Permission.is_allowed")
    def test_standalone_index_set_uses_manage_indices(self, mock_is_allowed):
        """无采集项的索引集 → is_allowed 被调用时传 MANAGE_INDICES@index_set_id."""
        mock_is_allowed.return_value = True

        perm = DesensitizeConfigWritePermission()
        view = self.build_view(self.index_set_without_collection.index_set_id)
        result = perm.has_permission(view.request, view)

        self.assertTrue(result)
        self.assertEqual(perm.actions, [ActionEnum.MANAGE_INDICES])
        self.assertEqual(len(perm.resources), 1)
        self.assertEqual(perm.resources[0].id, str(self.index_set_without_collection.index_set_id))
        self.assertEqual(perm.resources[0].type, "indices")
        mock_is_allowed.assert_called_once()
        self.assertEqual(mock_is_allowed.call_args.kwargs["action"], ActionEnum.MANAGE_INDICES)

    @patch("apps.iam.handlers.permission.Permission.is_allowed")
    def test_zero_collector_config_id_treated_as_no_collection(self, mock_is_allowed):
        """collector_config_id=0 应视同无采集项，校验 MANAGE_INDICES."""
        mock_is_allowed.return_value = True

        perm = DesensitizeConfigWritePermission()
        view = self.build_view(self.index_set_zero_collector.index_set_id)
        result = perm.has_permission(view.request, view)

        self.assertTrue(result)
        self.assertEqual(perm.actions, [ActionEnum.MANAGE_INDICES])
        self.assertEqual(perm.resources[0].type, "indices")
        self.assertEqual(
            perm.resources[0].id, str(self.index_set_zero_collector.index_set_id)
        )

    @patch("apps.iam.handlers.permission.Permission.is_allowed")
    def test_nonexistent_index_set_id_uses_indices(self, mock_is_allowed):
        """不存在的 index_set_id → collector_config_id 为 None → 校验 MANAGE_INDICES."""
        mock_is_allowed.return_value = True

        perm = DesensitizeConfigWritePermission()
        view = self.build_view(9999999)
        result = perm.has_permission(view.request, view)

        # 不存在的 ID 不会导致异常，应走 MANAGE_INDICES 分支（兜底行为）
        self.assertTrue(result)
        self.assertEqual(perm.actions, [ActionEnum.MANAGE_INDICES])
        self.assertEqual(perm.resources[0].id, "9999999")

    @patch("apps.iam.handlers.permission.Permission.is_allowed")
    def test_ignores_iam_permission_setting_overrides_during_test(self, mock_is_allowed):
        """IGNORE_IAM_PERMISSION=True 时 has_permission 直接返回 True，不调 is_allowed. """
        with self.settings(IGNORE_IAM_PERMISSION=True):
            perm = DesensitizeConfigWritePermission()
            view = self.build_view(self.index_set_with_collection.index_set_id)
            result = perm.has_permission(view.request, view)
            self.assertTrue(result)
            mock_is_allowed.assert_not_called()


@override_settings(IGNORE_IAM_PERMISSION=False, ESQUERY_WHITE_LIST=[])
class DesensitizeConfigWritePermissionEndToEndTests(TestCase):
    """
    端到端鉴权验证：mock IAM 引擎 is_allowed，验证不同权限用户保存脱敏规则的真实结果。

    - 有 MANAGE_COLLECTION 权限的用户对采集项索引集可保存（不 403）
    - 有 MANAGE_INDICES 权限的用户对第三方 ES 索引集可保存（不 403）
    - 两者都没有的用户返回 403
    - 交叉鉴权：有 MANAGE_INDICES 但对采集项索引集保存 → 403
    - 交叉鉴权：有 MANAGE_COLLECTION 但对第三方 ES 索引集保存 → 403
    """

    SPACE_UID = "bkcc__2"

    @classmethod
    def setUpTestData(cls):
        cls.collector_index_set = LogIndexSet.objects.create(
            index_set_name="e2e_collector_index_set",
            space_uid=cls.SPACE_UID,
            scenario_id="log",
            collector_config_id=888001,
        )
        cls.es_index_set = LogIndexSet.objects.create(
            index_set_name="e2e_es_index_set",
            space_uid=cls.SPACE_UID,
            scenario_id="es",
            collector_config_id=None,
        )

    @staticmethod
    def build_view(index_set_id):
        view = IndexSetViewSet()
        view.action = "desensitize_config_create"
        view.kwargs = {"index_set_id": index_set_id}
        view.request = SimpleNamespace(
            query_params={},
            data={},
            META={},
        )
        return view

    # === 正面用例：正确的权限走通 ===

    @patch("apps.iam.handlers.permission.Permission.is_allowed")
    def test_collector_user_passes_desensitize_save(self, mock_is_allowed):
        """有 MANAGE_COLLECTION 的用户保存采集项脱敏规则应通过。"""
        mock_is_allowed.return_value = True

        perm = DesensitizeConfigWritePermission()
        view = self.build_view(self.collector_index_set.index_set_id)

        result = perm.has_permission(view.request, view)

        self.assertTrue(result)
        self.assertEqual(perm.actions, [ActionEnum.MANAGE_COLLECTION])
        self.assertEqual(perm.resources[0].id, "888001")

    @patch("apps.iam.handlers.permission.Permission.is_allowed")
    def test_es_user_passes_desensitize_save(self, mock_is_allowed):
        """有 MANAGE_INDICES 的用户保存第三方 ES 脱敏规则应通过。"""
        mock_is_allowed.return_value = True

        perm = DesensitizeConfigWritePermission()
        view = self.build_view(self.es_index_set.index_set_id)

        result = perm.has_permission(view.request, view)

        self.assertTrue(result)
        self.assertEqual(perm.actions, [ActionEnum.MANAGE_INDICES])

    # === 负面用例：无权限被拒 ===

    @patch("apps.iam.handlers.permission.Permission.is_allowed")
    def test_no_permission_user_gets_403_on_collector(self, mock_is_allowed):
        """对采集项索引集无任何权限的用户应被拒。"""
        mock_is_allowed.side_effect = PermissionDeniedError(
            action_name="manage_collection", permission={}
        )

        perm = DesensitizeConfigWritePermission()
        view = self.build_view(self.collector_index_set.index_set_id)

        with self.assertRaises(PermissionDeniedError):
            perm.has_permission(view.request, view)

    @patch("apps.iam.handlers.permission.Permission.is_allowed")
    def test_no_permission_user_gets_403_on_es(self, mock_is_allowed):
        """对第三方 ES 索引集无任何权限的用户应被拒。"""
        mock_is_allowed.side_effect = PermissionDeniedError(
            action_name="manage_indices", permission={}
        )

        perm = DesensitizeConfigWritePermission()
        view = self.build_view(self.es_index_set.index_set_id)

        with self.assertRaises(PermissionDeniedError):
            perm.has_permission(view.request, view)

    # === 交叉鉴权：错误的权限类型被拒 ===

    @patch("apps.iam.handlers.permission.Permission.is_allowed")
    def test_indices_permission_denied_for_collector_index_set(self, mock_is_allowed):
        """有 MANAGE_INDICES 但无 MANAGE_COLLECTION → 保存采集项脱敏规则应被拒。"""
        mock_is_allowed.side_effect = PermissionDeniedError(
            action_name="manage_collection", permission={}
        )

        perm = DesensitizeConfigWritePermission()
        view = self.build_view(self.collector_index_set.index_set_id)

        with self.assertRaises(PermissionDeniedError):
            perm.has_permission(view.request, view)
        # 验证 is_allowed 被用正确的参数调用
        self.assertEqual(mock_is_allowed.call_args.kwargs["action"], ActionEnum.MANAGE_COLLECTION)

    @patch("apps.iam.handlers.permission.Permission.is_allowed")
    def test_collection_permission_denied_for_es_index_set(self, mock_is_allowed):
        """有 MANAGE_COLLECTION 但无 MANAGE_INDICES → 保存第三方 ES 脱敏规则应被拒。"""
        mock_is_allowed.side_effect = PermissionDeniedError(
            action_name="manage_indices", permission={}
        )

        perm = DesensitizeConfigWritePermission()
        view = self.build_view(self.es_index_set.index_set_id)

        with self.assertRaises(PermissionDeniedError):
            perm.has_permission(view.request, view)
        # 验证 is_allowed 被用正确的参数调用
        self.assertEqual(mock_is_allowed.call_args.kwargs["action"], ActionEnum.MANAGE_INDICES)

    # === gRPC-style: 验证 get_permissions + has_permission 串联 ===

    @patch("apps.iam.handlers.permission.Permission.is_allowed")
    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_get_permissions_returns_permission_then_desensitize_perm_works(
        self, get_auth_info, mock_is_allowed
    ):
        """
        验证 get_permissions 返回的 DesensitizeConfigWritePermission 实际可执行
        has_permission（串联测试）。
        """
        get_auth_info.return_value = {"bk_app_code": "untrusted_app", "bk_username": "alice"}
        mock_is_allowed.return_value = True

        view = self.build_view(self.collector_index_set.index_set_id)
        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], DesensitizeConfigWritePermission)

        # 实际执行 has_permission
        result = permissions[0].has_permission(view.request, view)
        self.assertTrue(result)
        self.assertEqual(permissions[0].actions, [ActionEnum.MANAGE_COLLECTION])


@override_settings(IGNORE_IAM_PERMISSION=False, ESQUERY_WHITE_LIST=["bk_monitor"])
class WhitelistWriteFailClosedTests(TestCase):
    """
    白名单应用调脱敏写操作不再免鉴权（fail-closed）。

    - get_permissions 返回 DesensitizeConfigWritePermission（非空列表）
    - is_allowed 被实际调用（未被短路）
    - 匿名/无权限 → deny → PermissionDeniedError
    """

    SPACE_UID = "bkcc__2"

    @classmethod
    def setUpTestData(cls):
        cls.es_index_set = LogIndexSet.objects.create(
            index_set_name="whitelist_fail_closed_es",
            space_uid=cls.SPACE_UID,
            scenario_id="es",
            collector_config_id=None,
        )

    @staticmethod
    def build_view(index_set_id, enforce_permission=False):
        view = IndexSetViewSet()
        view.action = "desensitize_config_delete"
        view.kwargs = {"index_set_id": index_set_id}
        view.request = SimpleNamespace(
            query_params={},
            data={"enforce_permission": enforce_permission},
            META={},
        )
        return view

    @patch("apps.iam.handlers.permission.Permission.is_allowed")
    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_whitelist_app_write_still_requires_permission(self, get_auth_info, mock_is_allowed):
        """白名单应用未强制鉴权时 get_permissions 返回 DesensitizeConfigWritePermission。"""
        get_auth_info.return_value = {"bk_app_code": "bk_monitor", "bk_username": "alice"}
        mock_is_allowed.return_value = True

        view = self.build_view(self.es_index_set.index_set_id, enforce_permission=False)
        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], DesensitizeConfigWritePermission)

    @patch("apps.iam.handlers.permission.Permission.is_allowed")
    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_whitelist_app_anonymous_write_gets_403(self, get_auth_info, mock_is_allowed):
        """白名单应用匿名调写操作 → is_allowed 被调用 → deny → 403。"""
        get_auth_info.return_value = {"bk_app_code": "bk_monitor", "bk_username": ""}
        mock_is_allowed.side_effect = PermissionDeniedError(
            action_name="manage_indices", permission={}
        )

        perm = DesensitizeConfigWritePermission()
        view = self.build_view(self.es_index_set.index_set_id)

        with self.assertRaises(PermissionDeniedError):
            perm.has_permission(view.request, view)

        # 验证 is_allowed 确实被调用（未被短路）
        mock_is_allowed.assert_called_once()

    @patch("apps.iam.handlers.permission.Permission.is_allowed")
    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_whitelist_app_retrieve_still_bypasses(self, get_auth_info, mock_is_allowed):
        """白名单应用读取脱敏配置（读操作）仍走 bypass，返回空列表。"""
        get_auth_info.return_value = {"bk_app_code": "bk_monitor", "bk_username": "alice"}

        view = self.build_view(self.es_index_set.index_set_id)
        view.action = "desensitize_config_retrieve"
        permissions = view.get_permissions()

        self.assertEqual(permissions, [])
        mock_is_allowed.assert_not_called()
