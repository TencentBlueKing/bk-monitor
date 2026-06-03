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
    """SceneSearchViewSet.get_permissions 不再返回空列表，必须挂上业务级校验。"""

    def test_get_permissions_returns_scene_view_business_permission(self):
        from apps.iam.handlers.actions import ActionEnum

        vs = SceneSearchViewSet(**{"format_kwarg": None})
        perms = vs.get_permissions()
        self.assertEqual(len(perms), 1)
        self.assertIsInstance(perms[0], _SceneViewBusinessPermission)
        # action 必须是 VIEW_BUSINESS，不能引入新 ActionEnum
        self.assertEqual(perms[0].actions, [ActionEnum.VIEW_BUSINESS])

    def test_get_permissions_applies_to_all_actions(self):
        """不同 action 都应返回同一权限实例类型（短期统一收敛策略）。"""
        for action_name in ("scenes", "search", "scene_async_export", "create_config"):
            vs = SceneSearchViewSet(**{"format_kwarg": None})
            vs.action = action_name
            perms = vs.get_permissions()
            self.assertEqual(len(perms), 1, action_name)
            self.assertIsInstance(perms[0], _SceneViewBusinessPermission, action_name)


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
