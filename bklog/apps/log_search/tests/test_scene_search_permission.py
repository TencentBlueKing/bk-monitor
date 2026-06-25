"""
Unit tests for SceneSearchViewSet permission converge.

Covers:
- _SceneViewBusinessPermission.fetch_biz_id_by_request:
  bk_biz_id > space_uid fallback > zero (invalid / missing)
- SceneSearchViewSet.get_permissions returns the converged perm list
- user_custom_config serializers do NOT expose username (anti-spoof)
"""

from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from apps.log_search.serializers import (
    SceneUserCustomConfigDeleteSerializer,
    SceneUserCustomConfigGetSerializer,
    SceneUserCustomConfigUpsertSerializer,
)
from apps.log_search.views.scene_search_views import (
    SceneSearchViewSet,
    _SceneFeatureTogglePermission,
    _SceneViewBusinessPermission,
)


SPACE_UID = "bkcc__2"


def _drf_request(method, path, *, data=None, query=None):
    """Build a DRF Request with both body and query_params populated as needed."""
    from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
    from rest_framework.request import Request

    factory = APIRequestFactory()
    if method == "post":
        raw = factory.post(path, data=data or {}, format="json")
    elif method == "get":
        raw = factory.get(path, data=query or {})
    elif method == "delete":
        raw = factory.delete(path, data=query or {})
    else:
        raise ValueError(method)
    return Request(raw, parsers=[JSONParser(), FormParser(), MultiPartParser()])


# =========================================================================
# 1. fetch_biz_id_by_request resolution
# =========================================================================


class TestSceneViewBusinessPermissionResolution(TestCase):
    """覆盖 _SceneViewBusinessPermission.fetch_biz_id_by_request 的解析优先级。"""

    def test_explicit_bk_biz_id_in_body_takes_precedence(self):
        """body 里 bk_biz_id 显式时不再走 space_uid 反查。"""
        req = _drf_request("post", "/x/", data={"bk_biz_id": 2, "space_uid": "bkcc__999"})
        with patch(
            "apps.log_search.views.scene_search_views.space_uid_to_bk_biz_id"
        ) as m_resolve:
            biz_id = _SceneViewBusinessPermission.fetch_biz_id_by_request(req)
        self.assertEqual(biz_id, 2)
        m_resolve.assert_not_called()

    def test_explicit_bk_biz_id_in_query_takes_precedence(self):
        """query_params 里 bk_biz_id 显式时同样不走 space_uid。"""
        req = _drf_request("get", "/x/", query={"bk_biz_id": 3, "space_uid": "bkcc__999"})
        with patch(
            "apps.log_search.views.scene_search_views.space_uid_to_bk_biz_id"
        ) as m_resolve:
            biz_id = _SceneViewBusinessPermission.fetch_biz_id_by_request(req)
        self.assertEqual(int(biz_id), 3)
        m_resolve.assert_not_called()

    def test_space_uid_fallback_in_body_resolves_to_bk_biz_id(self):
        """body 里只传 space_uid 时，应通过 space_uid_to_bk_biz_id 反查。"""
        req = _drf_request("post", "/x/", data={"space_uid": SPACE_UID})
        with patch(
            "apps.log_search.views.scene_search_views.space_uid_to_bk_biz_id",
            return_value=2,
        ) as m_resolve:
            biz_id = _SceneViewBusinessPermission.fetch_biz_id_by_request(req)
        self.assertEqual(biz_id, 2)
        m_resolve.assert_called_once_with(SPACE_UID)

    def test_space_uid_fallback_in_query_resolves_to_bk_biz_id(self):
        """query 里只传 space_uid 时同样反查。"""
        req = _drf_request("get", "/x/", query={"space_uid": SPACE_UID})
        with patch(
            "apps.log_search.views.scene_search_views.space_uid_to_bk_biz_id",
            return_value=2,
        ):
            biz_id = _SceneViewBusinessPermission.fetch_biz_id_by_request(req)
        self.assertEqual(biz_id, 2)

    def test_space_uid_resolve_failure_returns_zero(self):
        """space_uid_to_bk_biz_id 抛异常时返回 0（回退到基类原逻辑 short-circuit）。"""
        req = _drf_request("post", "/x/", data={"space_uid": "invalid"})
        with patch(
            "apps.log_search.views.scene_search_views.space_uid_to_bk_biz_id",
            side_effect=Exception("boom"),
        ):
            biz_id = _SceneViewBusinessPermission.fetch_biz_id_by_request(req)
        self.assertEqual(biz_id, 0)

    def test_space_uid_resolve_returns_none_falls_back_to_zero(self):
        """space_uid_to_bk_biz_id 返回 None/0 时本方法应返回 0。"""
        req = _drf_request("post", "/x/", data={"space_uid": "bksaas__unknown"})
        with patch(
            "apps.log_search.views.scene_search_views.space_uid_to_bk_biz_id",
            return_value=0,
        ):
            biz_id = _SceneViewBusinessPermission.fetch_biz_id_by_request(req)
        self.assertEqual(biz_id, 0)

    def test_no_input_returns_zero(self):
        """body / query 都不带 bk_biz_id / space_uid 时返回 0。"""
        req = _drf_request("post", "/x/", data={})
        biz_id = _SceneViewBusinessPermission.fetch_biz_id_by_request(req)
        self.assertEqual(biz_id, 0)


# =========================================================================
# 2. ViewSet.get_permissions wiring
# =========================================================================


class TestSceneSearchViewSetGetPermissions(TestCase):
    """SceneSearchViewSet.get_permissions 必须同时挂上灰度开关与业务级校验。"""

    def test_get_permissions_returns_toggle_then_business_permission(self):
        from apps.iam.handlers.actions import ActionEnum

        vs = SceneSearchViewSet(**{"format_kwarg": None})
        perms = vs.get_permissions()
        self.assertEqual(len(perms), 2)
        # 开关在前，先拦截
        self.assertIsInstance(perms[0], _SceneFeatureTogglePermission)
        self.assertIsInstance(perms[1], _SceneViewBusinessPermission)
        # action 必须是 VIEW_BUSINESS，不能引入新 ActionEnum
        self.assertEqual(perms[1].actions, [ActionEnum.VIEW_BUSINESS])

    def test_get_permissions_applies_to_all_actions(self):
        """不同 action 都应返回灰度开关 + 业务级两层权限（短期统一收敛策略）。"""
        for action_name in ("scenes", "search", "scene_async_export", "create_config"):
            vs = SceneSearchViewSet(**{"format_kwarg": None})
            vs.action = action_name
            perms = vs.get_permissions()
            self.assertEqual(len(perms), 2, action_name)
            self.assertIsInstance(perms[0], _SceneFeatureTogglePermission, action_name)
            self.assertIsInstance(perms[1], _SceneViewBusinessPermission, action_name)


# =========================================================================
# 2b. _SceneFeatureTogglePermission 灰度开关后端拦截
# =========================================================================


class TestSceneFeatureTogglePermission(TestCase):
    """覆盖 SCENE_SEARCH 灰度开关后端拦截：开关关闭拒绝、白名单业务放行。"""

    def test_toggle_off_for_biz_raises_permission_denied(self):
        from rest_framework.exceptions import PermissionDenied

        req = _drf_request("post", "/x/", data={"bk_biz_id": 2})
        perm = _SceneFeatureTogglePermission()
        with patch(
            "apps.log_search.views.scene_search_views.FeatureToggleObject.switch",
            return_value=False,
        ) as m_switch:
            with self.assertRaises(PermissionDenied):
                perm.has_permission(req, view=None)
            m_switch.assert_called_once_with("scene_search", 2)

    def test_toggle_on_for_whitelisted_biz_passes(self):
        req = _drf_request("post", "/x/", data={"bk_biz_id": 2})
        perm = _SceneFeatureTogglePermission()
        with patch(
            "apps.log_search.views.scene_search_views.FeatureToggleObject.switch",
            return_value=True,
        ) as m_switch:
            self.assertTrue(perm.has_permission(req, view=None))
            m_switch.assert_called_once_with("scene_search", 2)

    def test_toggle_resolves_biz_from_space_uid(self):
        """只传 space_uid 时按反查的 bk_biz_id 校验开关。"""
        req = _drf_request("post", "/x/", data={"space_uid": SPACE_UID})
        perm = _SceneFeatureTogglePermission()
        with patch(
            "apps.log_search.views.scene_search_views.space_uid_to_bk_biz_id",
            return_value=2,
        ), patch(
            "apps.log_search.views.scene_search_views.FeatureToggleObject.switch",
            return_value=True,
        ) as m_switch:
            self.assertTrue(perm.has_permission(req, view=None))
            m_switch.assert_called_once_with("scene_search", 2)

    def test_no_biz_id_does_not_block(self):
        """解析不到业务 ID 时不在开关层拦截，交由后续业务级权限处理。"""
        req = _drf_request("post", "/x/", data={})
        perm = _SceneFeatureTogglePermission()
        with patch(
            "apps.log_search.views.scene_search_views.FeatureToggleObject.switch"
        ) as m_switch:
            self.assertTrue(perm.has_permission(req, view=None))
            m_switch.assert_not_called()


# =========================================================================
# 3. has_permission end-to-end with IAM mocked
# =========================================================================


@override_settings(IGNORE_IAM_PERMISSION=False)
class TestSceneViewBusinessPermissionHasPermission(TestCase):
    """覆盖 has_permission 走完 fetch -> BUSINESS resource -> IAM.is_allowed。"""

    def test_has_permission_with_space_uid_only_calls_iam_with_resolved_biz(self):
        from apps.iam.handlers.actions import ActionEnum

        req = _drf_request(
            "post",
            "/api/v1/search/scene/search/",
            data={"space_uid": SPACE_UID, "table_id_conditions": [[]]},
        )
        perm = _SceneViewBusinessPermission([ActionEnum.VIEW_BUSINESS])

        with patch(
            "apps.log_search.views.scene_search_views.space_uid_to_bk_biz_id",
            return_value=2,
        ), patch(
            "apps.iam.handlers.drf.Permission"
        ) as m_perm_cls:
            m_perm_cls.return_value.is_allowed.return_value = True
            ok = perm.has_permission(req, view=None)
            self.assertTrue(ok)
            m_perm_cls.return_value.is_allowed.assert_called_once()
            kwargs = m_perm_cls.return_value.is_allowed.call_args.kwargs
            self.assertEqual(kwargs["action"], ActionEnum.VIEW_BUSINESS)
            self.assertEqual(len(kwargs["resources"]), 1)

    def test_has_permission_no_biz_short_circuits_true(self):
        """既无 bk_biz_id 又无 space_uid 时，回退到基类的 short-circuit 行为 (return True)。

        这是基类 BusinessActionPermission 的现有语义，本次不修改；
        覆盖该行为以避免后续基类升级时被静默改坏。
        """
        from apps.iam.handlers.actions import ActionEnum

        req = _drf_request("post", "/x/", data={})
        perm = _SceneViewBusinessPermission([ActionEnum.VIEW_BUSINESS])
        with patch("apps.iam.handlers.drf.Permission") as m_perm_cls:
            ok = perm.has_permission(req, view=None)
            self.assertTrue(ok)
            m_perm_cls.return_value.is_allowed.assert_not_called()

    def test_has_permission_iam_denied_propagates(self):
        """IAM 拒绝时 Permission.is_allowed 会 raise，has_permission 让异常透出。"""
        from apps.iam.handlers.actions import ActionEnum

        req = _drf_request("post", "/x/", data={"space_uid": SPACE_UID})
        perm = _SceneViewBusinessPermission([ActionEnum.VIEW_BUSINESS])

        with patch(
            "apps.log_search.views.scene_search_views.space_uid_to_bk_biz_id",
            return_value=2,
        ), patch(
            "apps.iam.handlers.drf.Permission"
        ) as m_perm_cls:
            m_perm_cls.return_value.is_allowed.side_effect = PermissionError("denied")
            with self.assertRaises(PermissionError):
                perm.has_permission(req, view=None)


# =========================================================================
# 4. user_custom_config serializers do not expose username
# =========================================================================


class TestUserCustomConfigSerializersAntiSpoof(TestCase):
    """user_custom_config 的入参序列化器不能暴露 username 字段，
    避免调用方通过请求体伪造 username 写入/读取他人偏好。
    """

    def test_get_serializer_does_not_accept_username(self):
        s = SceneUserCustomConfigGetSerializer(
            data={"bk_biz_id": 2, "scene_id": "k8s", "username": "attacker"}
        )
        s.is_valid(raise_exception=True)
        self.assertNotIn("username", s.validated_data)

    def test_delete_serializer_does_not_accept_username(self):
        s = SceneUserCustomConfigDeleteSerializer(
            data={"bk_biz_id": 2, "scene_id": "k8s", "username": "attacker"}
        )
        s.is_valid(raise_exception=True)
        self.assertNotIn("username", s.validated_data)

    def test_upsert_serializer_does_not_accept_username(self):
        s = SceneUserCustomConfigUpsertSerializer(
            data={
                "bk_biz_id": 2,
                "scene_id": "k8s",
                "scene_config": {"displayFields": ["log"]},
                "username": "attacker",
            }
        )
        s.is_valid(raise_exception=True)
        self.assertNotIn("username", s.validated_data)


# =========================================================================
# 5. SceneUnifyQueryHandler.verify_result_table_search_permission
#    结果表级 SEARCH_LOG 检索权限校验（ts/raw 返回后）
# =========================================================================


def _bare_scene_handler():
    """构造一个不走 __init__ 的 SceneUnifyQueryHandler 裸实例，仅用于校验逻辑单测。

    场景检索鉴权构造 INDICES 资源时依赖 self.space_uid / self.bk_biz_id 注入
    _bk_iam_path_，这里预置一个业务空间，保证资源属性可被确定性生成。
    """
    from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler

    handler = SceneUnifyQueryHandler.__new__(SceneUnifyQueryHandler)
    handler.space_uid = "bkcc__2"
    handler.bk_biz_id = 2
    return handler


class TestMapResultTablesToIndexSets(TestCase):
    """覆盖 result_table_id -> index_set_id 的两种形态映射。"""

    def test_data_label_form_parsed_without_db(self):
        from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler

        with patch("apps.log_search.models.LogIndexSetData") as m_model:
            result = SceneUnifyQueryHandler._map_result_tables_to_index_sets(
                ["bklog_index_set_123", "bklog_index_set_456"]
            )
            # 纯 data_label 形式不应触发 DB 查询
            m_model.objects.filter.assert_not_called()
        self.assertEqual(set(result), {123, 456})

    def test_rt_id_form_queries_db(self):
        from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler

        with patch("apps.log_search.models.LogIndexSetData") as m_model:
            qs = m_model.objects.filter.return_value.values_list.return_value.distinct
            qs.return_value = [789]
            result = SceneUnifyQueryHandler._map_result_tables_to_index_sets(
                ["2_bklog.my_collector"]
            )
            m_model.objects.filter.assert_called_once_with(
                result_table_id__in=["2_bklog.my_collector"]
            )
        self.assertEqual(set(result), {789})

    def test_mixed_form(self):
        from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler

        with patch("apps.log_search.models.LogIndexSetData") as m_model:
            qs = m_model.objects.filter.return_value.values_list.return_value.distinct
            qs.return_value = [789]
            result = SceneUnifyQueryHandler._map_result_tables_to_index_sets(
                ["bklog_index_set_123", "2_bklog.my_collector"]
            )
        self.assertEqual(set(result), {123, 789})


@override_settings(IGNORE_IAM_PERMISSION=False)
class TestVerifyResultTableSearchPermission(TestCase):
    """覆盖 verify_result_table_search_permission 的放行 / 拒绝 / 幂等路径。"""

    def test_empty_result_table_ids_skips_iam(self):
        handler = _bare_scene_handler()
        with patch("apps.iam.handlers.permission.Permission") as m_perm_cls:
            handler.verify_result_table_search_permission([])
            m_perm_cls.assert_not_called()
        self.assertTrue(handler._rt_perm_verified)

    @override_settings(IGNORE_IAM_PERMISSION=True)
    def test_ignore_iam_permission_skips(self):
        handler = _bare_scene_handler()
        with patch("apps.iam.handlers.permission.Permission") as m_perm_cls:
            handler.verify_result_table_search_permission(["2_bklog.xxx"])
            m_perm_cls.assert_not_called()
        self.assertTrue(handler._rt_perm_verified)

    def test_no_index_set_mapped_skips_iam(self):
        handler = _bare_scene_handler()
        with patch(
            "apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler."
            "_map_result_tables_to_index_sets",
            return_value=[],
        ), patch("apps.iam.handlers.permission.Permission") as m_perm_cls:
            handler.verify_result_table_search_permission(["2_bklog.xxx"])
            m_perm_cls.assert_not_called()
        self.assertTrue(handler._rt_perm_verified)

    def test_all_allowed_passes(self):
        from apps.iam.handlers.actions import ActionEnum

        handler = _bare_scene_handler()
        with patch(
            "apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler."
            "_map_result_tables_to_index_sets",
            return_value=[123, 456],
        ), patch("apps.iam.handlers.permission.Permission") as m_perm_cls:
            m_perm_cls.return_value.batch_is_allowed.return_value = {
                "123": {ActionEnum.SEARCH_LOG.id: True},
                "456": {ActionEnum.SEARCH_LOG.id: True},
            }
            handler.verify_result_table_search_permission(["2_bklog.a", "2_bklog.b"])
            m_perm_cls.return_value.batch_is_allowed.assert_called_once()
            m_perm_cls.return_value.get_apply_data.assert_not_called()
        self.assertTrue(handler._rt_perm_verified)

    def test_denied_raises_permission_denied(self):
        from apps.iam.exceptions import PermissionDeniedError
        from apps.iam.handlers.actions import ActionEnum

        handler = _bare_scene_handler()
        with patch(
            "apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler."
            "_map_result_tables_to_index_sets",
            return_value=[123, 456],
        ), patch("apps.iam.handlers.permission.Permission") as m_perm_cls:
            m_perm_cls.return_value.batch_is_allowed.return_value = {
                "123": {ActionEnum.SEARCH_LOG.id: True},
                "456": {ActionEnum.SEARCH_LOG.id: False},
            }
            m_perm_cls.return_value.get_apply_data.return_value = ({}, "http://apply")
            with self.assertRaises(PermissionDeniedError):
                handler.verify_result_table_search_permission(["2_bklog.a", "2_bklog.b"])
            m_perm_cls.return_value.get_apply_data.assert_called_once()
        # 拒绝路径不应标记已校验
        self.assertFalse(getattr(handler, "_rt_perm_verified", False))

    def test_idempotent_second_call_skips_iam(self):
        from apps.iam.handlers.actions import ActionEnum

        handler = _bare_scene_handler()
        with patch(
            "apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler."
            "_map_result_tables_to_index_sets",
            return_value=[123],
        ), patch("apps.iam.handlers.permission.Permission") as m_perm_cls:
            m_perm_cls.return_value.batch_is_allowed.return_value = {
                "123": {ActionEnum.SEARCH_LOG.id: True},
            }
            handler.verify_result_table_search_permission(["2_bklog.a"])
            handler.verify_result_table_search_permission(["2_bklog.a"])
            # 第二次命中缓存，IAM 只被调用一次
            m_perm_cls.return_value.batch_is_allowed.assert_called_once()

    def test_resources_carry_bk_iam_path_attribute(self):
        """回归：空间级 SEARCH_LOG 策略含 indices._bk_iam_path_ 条件，

        每个 INDICES 资源必须显式携带 _bk_iam_path_，否则 IAM SDK 本地
        策略求值（含 expr.render 的 debug 日志）会 KeyError 整批 500。
        """
        from apps.iam.handlers.actions import ActionEnum

        handler = _bare_scene_handler()
        with patch(
            "apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler."
            "_map_result_tables_to_index_sets",
            return_value=[123, 456],
        ), patch("apps.log_search.models.LogIndexSet") as m_index_set, patch(
            "apps.iam.handlers.permission.Permission"
        ) as m_perm_cls:
            m_index_set.objects.filter.return_value.values_list.return_value = []
            m_perm_cls.return_value.batch_is_allowed.return_value = {
                "123": {ActionEnum.SEARCH_LOG.id: True},
                "456": {ActionEnum.SEARCH_LOG.id: True},
            }
            handler.verify_result_table_search_permission(["2_bklog.a", "2_bklog.b"])
            # 取实际传给 IAM 的 resources，逐个断言带 _bk_iam_path_
            _actions, resources = m_perm_cls.return_value.batch_is_allowed.call_args[0]
            self.assertEqual(len(resources), 2)
            for resource_group in resources:
                resource = resource_group[0]
                self.assertIn("_bk_iam_path_", resource.attribute)
                self.assertEqual(resource.attribute["_bk_iam_path_"], "/space,2/")

    def test_denied_resources_carry_index_set_name(self):
        """回归：拒绝时申请数据需展示索引集名称。

        _bk_iam_path_ 修复给 create_simple_instance 传了非空 attribute，会让
        Indices 提前返回、跳过反查 name。这里批量查名塞进 attribute，确保
        传给 get_apply_data 的资源带上 name。
        """
        from apps.iam.exceptions import PermissionDeniedError
        from apps.iam.handlers.actions import ActionEnum

        handler = _bare_scene_handler()
        with patch(
            "apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler."
            "_map_result_tables_to_index_sets",
            return_value=[123, 456],
        ), patch("apps.log_search.models.LogIndexSet") as m_index_set, patch(
            "apps.iam.handlers.permission.Permission"
        ) as m_perm_cls:
            m_index_set.objects.filter.return_value.values_list.return_value = [
                (123, "idx-123"),
                (456, "idx-456"),
            ]
            m_perm_cls.return_value.batch_is_allowed.return_value = {
                "123": {ActionEnum.SEARCH_LOG.id: True},
                "456": {ActionEnum.SEARCH_LOG.id: False},
            }
            m_perm_cls.return_value.get_apply_data.return_value = ({}, "http://apply")
            with self.assertRaises(PermissionDeniedError):
                handler.verify_result_table_search_permission(["2_bklog.a", "2_bklog.b"])
            # get_apply_data 收到的 denied_resources 必须带 name
            _actions, denied_resources = m_perm_cls.return_value.get_apply_data.call_args[0]
            self.assertEqual(len(denied_resources), 1)
            self.assertEqual(denied_resources[0].attribute["name"], "idx-456")
            self.assertEqual(denied_resources[0].attribute["_bk_iam_path_"], "/space,2/")


# =========================================================================
# 6. SceneUnifyQueryHandler._init_scene_desensitize
#    场景化检索按命中索引集懒加载并应用脱敏（ts/raw 返回后）
# =========================================================================


def _desensitize_field_obj(field_name, rule_id=1, operator="mask_shield", sort_index=0):
    """构造一个 DesensitizeFieldConfig 风格的轻量对象。"""
    from unittest.mock import Mock

    obj = Mock()
    obj.field_name = field_name
    obj.rule_id = rule_id
    obj.operator = operator
    obj.params = {}
    obj.match_pattern = ""
    obj.sort_index = sort_index
    return obj


class TestInitSceneDesensitize(TestCase):
    """覆盖 _init_scene_desensitize 的跳过 / 加载合并 / 幂等路径。"""

    def _handler(self, is_desensitize=True):
        handler = _bare_scene_handler()
        handler.is_desensitize = is_desensitize
        handler._desensitize_initialized = False
        handler.field_configs = []
        handler.text_fields = []
        handler.text_fields_field_configs = []
        return handler

    def test_skip_when_not_desensitize(self):
        handler = self._handler(is_desensitize=False)
        with patch(
            "apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler."
            "_map_result_tables_to_index_sets"
        ) as m_map:
            handler._init_scene_desensitize(["2_bklog.a"])
            m_map.assert_not_called()
        self.assertTrue(handler._desensitize_initialized)
        self.assertEqual(handler.field_configs, [])

    def test_skip_when_empty_result_table_ids(self):
        handler = self._handler()
        with patch(
            "apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler."
            "_map_result_tables_to_index_sets"
        ) as m_map:
            handler._init_scene_desensitize([])
            m_map.assert_not_called()
        self.assertTrue(handler._desensitize_initialized)

    def test_skip_when_no_index_set_mapped(self):
        handler = self._handler()
        with patch(
            "apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler."
            "_map_result_tables_to_index_sets",
            return_value=[],
        ), patch("apps.log_desensitize.models.DesensitizeFieldConfig") as m_field:
            handler._init_scene_desensitize(["2_bklog.a"])
            m_field.objects.filter.assert_not_called()
        self.assertTrue(handler._desensitize_initialized)

    def test_load_and_merge_configs_across_index_sets(self):
        handler = self._handler()
        cfg = type("C", (), {"text_fields": ["log"]})()
        field_objs = [
            _desensitize_field_obj("password"),
            _desensitize_field_obj("log"),  # 命中 text_fields -> text_fields_field_configs
        ]
        with patch(
            "apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler."
            "_map_result_tables_to_index_sets",
            return_value=[123, 456],
        ), patch("apps.log_desensitize.models.DesensitizeConfig") as m_cfg, patch(
            "apps.log_desensitize.models.DesensitizeFieldConfig"
        ) as m_field:
            m_cfg.objects.filter.return_value = [cfg]
            m_field.objects.filter.return_value = field_objs
            handler._init_scene_desensitize(["2_bklog.a", "2_bklog.b"])

        self.assertEqual(handler.text_fields, ["log"])
        self.assertEqual([c["field_name"] for c in handler.field_configs], ["password"])
        self.assertEqual(
            [c["field_name"] for c in handler.text_fields_field_configs], ["log"]
        )
        self.assertTrue(handler._desensitize_initialized)

    def test_dedupe_identical_rules(self):
        handler = self._handler()
        cfg = type("C", (), {"text_fields": []})()
        # 两个索引集返回完全相同的规则，应被去重为 1 条
        field_objs = [
            _desensitize_field_obj("password", rule_id=1, sort_index=0),
            _desensitize_field_obj("password", rule_id=1, sort_index=0),
        ]
        with patch(
            "apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler."
            "_map_result_tables_to_index_sets",
            return_value=[123, 456],
        ), patch("apps.log_desensitize.models.DesensitizeConfig") as m_cfg, patch(
            "apps.log_desensitize.models.DesensitizeFieldConfig"
        ) as m_field:
            m_cfg.objects.filter.return_value = [cfg]
            m_field.objects.filter.return_value = field_objs
            handler._init_scene_desensitize(["2_bklog.a", "2_bklog.b"])
        self.assertEqual(len(handler.field_configs), 1)

    def test_idempotent_second_call_skips_db(self):
        handler = self._handler()
        cfg = type("C", (), {"text_fields": []})()
        with patch(
            "apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler."
            "_map_result_tables_to_index_sets",
            return_value=[123],
        ), patch("apps.log_desensitize.models.DesensitizeConfig") as m_cfg, patch(
            "apps.log_desensitize.models.DesensitizeFieldConfig"
        ) as m_field:
            m_cfg.objects.filter.return_value = [cfg]
            m_field.objects.filter.return_value = [_desensitize_field_obj("password")]
            handler._init_scene_desensitize(["2_bklog.a"])
            handler._init_scene_desensitize(["2_bklog.a"])
            # 第二次命中幂等，不再查询 DB
            m_field.objects.filter.assert_called_once()


# =========================================================================
# 7. 查询原语层后置鉴权（单一卡点）
#    ts/raw、ts、ts/reference、scroll 出数后自动按命中结果表校验 SEARCH_LOG
# =========================================================================


@override_settings(IGNORE_IAM_PERMISSION=False)
class TestQueryPrimitivesPostAuth(TestCase):
    """覆盖 query_ts / query_ts_reference / query_ts_raw / query_ts_raw_with_scroll
    四个原语：super() 取数后必须触发 verify_result_table_search_permission。"""

    def _assert_primitive_verifies(self, method_name, parent_attr):
        handler = _bare_scene_handler()
        response = {"series": [], "list": [], "result_table_id": ["2_bklog.a", "2_bklog.b"]}
        with patch(
            f"apps.log_unifyquery.handler.base.UnifyQueryHandler.{parent_attr}",
            return_value=response,
        ), patch.object(handler, "verify_result_table_search_permission") as m_verify:
            result = getattr(handler, method_name)({"foo": 1})
            m_verify.assert_called_once_with(["2_bklog.a", "2_bklog.b"])
            self.assertIs(result, response)

    def test_query_ts_triggers_verify(self):
        self._assert_primitive_verifies("query_ts", "query_ts")

    def test_query_ts_reference_triggers_verify(self):
        self._assert_primitive_verifies("query_ts_reference", "query_ts_reference")

    def test_query_ts_raw_triggers_verify(self):
        self._assert_primitive_verifies("query_ts_raw", "query_ts_raw")

    def test_query_ts_raw_with_scroll_triggers_verify(self):
        self._assert_primitive_verifies("query_ts_raw_with_scroll", "query_ts_raw_with_scroll")

    def test_no_result_table_id_skips_iam(self):
        """响应不含 result_table_id（如 ts_reference 失败兜底）时不应触发 IAM、不抛异常。"""
        handler = _bare_scene_handler()
        with patch("apps.iam.handlers.permission.Permission") as m_perm:
            handler._verify_scene_permission({"series": []})
            m_perm.assert_not_called()
        self.assertTrue(handler._rt_perm_verified)
