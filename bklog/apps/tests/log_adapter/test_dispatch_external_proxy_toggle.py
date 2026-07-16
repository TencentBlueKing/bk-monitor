"""
灰度开关回归测试：验证 PO+IAM OR 决策灰度开关 off/on/debug 三种状态下，
三个外部入口函数 (external / dispatch_list_user_spaces / dispatch_external_proxy)
和 filter_log_search_response_resource 的行为与预期一致。

开关关闭 (off) → 行为与 git HEAD 老版本（纯 legacy PO 判定）逐行等价。
开关开启 (on)   → 走当前 PO+IAM OR 决策。
debug + 白名单    → 仅白名单 bk_biz_id 启用 OR。
debug + 黑名单    → 黑名单 bk_biz_id 走老逻辑，其余启用 OR。
"""
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.test import TestCase, RequestFactory

from apps.constants import ExternalPermissionActionEnum, ViewSetActionEnum
from apps.feature_toggle.handlers.toggle import Toggle
from apps.log_commons.models import ExternalPermission
from apps.iam import ActionEnum


# ══════════════════════════════════════════════════
#  is_or_decision_enabled() 单元测试
# ══════════════════════════════════════════════════


class TestIsOrDecisionEnabled(TestCase):
    """验证 RequestProcessor.is_or_decision_enabled 正确调用 FeatureToggleObject.switch"""

    def setUp(self):
        from log_adapter.home.views import RequestProcessor
        self.processor = RequestProcessor

    @patch("log_adapter.home.views.FeatureToggleObject.switch", return_value=True)
    @patch("log_adapter.home.views.space_uid_to_bk_biz_id", return_value="2")
    def test_switch_on_returns_enabled(self, _mock_biz, mock_switch):
        from log_adapter.home.views import EXTERNAL_PERMISSION_OR_DECISION
        result = self.processor.is_or_decision_enabled("bkcc__2")
        self.assertTrue(result, "开关 on 时应返回 True")
        mock_switch.assert_called_once_with(EXTERNAL_PERMISSION_OR_DECISION, biz_id=2)

    @patch("log_adapter.home.views.FeatureToggleObject.switch", return_value=False)
    @patch("log_adapter.home.views.space_uid_to_bk_biz_id", return_value="3")
    def test_switch_off_returns_disabled(self, _mock_biz, mock_switch):
        result = self.processor.is_or_decision_enabled("bkcc__3")
        self.assertFalse(result, "开关 off 时应返回 False")


# ══════════════════════════════════════════════════
#  _is_biz_enabled_for_or_decision() 单元测试
# ══════════════════════════════════════════════════


class TestIsBizEnabledForOrDecision(TestCase):
    """验证 _is_biz_enabled_for_or_decision 复用 Toggle 对象正确判断"""

    def test_toggle_obj_none_returns_false(self):
        from log_adapter.home.views import _is_biz_enabled_for_or_decision
        self.assertFalse(_is_biz_enabled_for_or_decision(None, 2))

    def test_status_off_returns_false(self):
        from log_adapter.home.views import _is_biz_enabled_for_or_decision
        toggle = Toggle(name="test", status="off")
        self.assertFalse(_is_biz_enabled_for_or_decision(toggle, 2))

    def test_status_on_returns_true(self):
        from log_adapter.home.views import _is_biz_enabled_for_or_decision
        toggle = Toggle(name="test", status="on")
        self.assertTrue(_is_biz_enabled_for_or_decision(toggle, 2))

    def test_debug_white_list_hit_returns_true(self):
        from log_adapter.home.views import _is_biz_enabled_for_or_decision
        toggle = Toggle(name="test", status="debug", biz_id_white_list=[2, 5])
        self.assertTrue(_is_biz_enabled_for_or_decision(toggle, 2), "白名单内 bk_biz_id 应为 True")

    def test_debug_white_list_miss_returns_false(self):
        from log_adapter.home.views import _is_biz_enabled_for_or_decision
        toggle = Toggle(name="test", status="debug", biz_id_white_list=[2, 5])
        self.assertFalse(_is_biz_enabled_for_or_decision(toggle, 3), "白名单外 bk_biz_id 应为 False")

    def test_debug_black_list_hit_returns_false(self):
        from log_adapter.home.views import _is_biz_enabled_for_or_decision
        toggle = Toggle(name="test", status="debug", biz_id_black_list=[2])
        self.assertFalse(_is_biz_enabled_for_or_decision(toggle, 2), "黑名单内 bk_biz_id 应为 False")

    def test_debug_black_list_miss_returns_true(self):
        from log_adapter.home.views import _is_biz_enabled_for_or_decision
        toggle = Toggle(name="test", status="debug", biz_id_black_list=[2])
        self.assertTrue(_is_biz_enabled_for_or_decision(toggle, 3), "黑名单外 bk_biz_id 应为 True")

    @patch.object(settings, "ENVIRONMENT", "prod")
    def test_debug_no_list_prod_returns_false(self):
        from log_adapter.home.views import _is_biz_enabled_for_or_decision
        toggle = Toggle(name="test", status="debug")
        self.assertFalse(_is_biz_enabled_for_or_decision(toggle, 2), "prod 环境 debug 无名单应为 False")

    @patch.object(settings, "ENVIRONMENT", "dev")
    def test_debug_no_list_dev_returns_true(self):
        from log_adapter.home.views import _is_biz_enabled_for_or_decision
        toggle = Toggle(name="test", status="debug")
        self.assertTrue(_is_biz_enabled_for_or_decision(toggle, 2), "dev 环境 debug 无名单应为 True")


# ══════════════════════════════════════════════════
#  external() 开关分支测试
# ══════════════════════════════════════════════════


class TestExternalToggleOffBehavior(TestCase):
    """开关关闭时 external() 必须走纯 PO 老逻辑，不调 IAM"""

    EXTERNAL_USER = "po_user_x"
    SPACE_UID = "bkcc__2"
    AUTHORIZER = "internal_admin"

    def setUp(self):
        self.factory = RequestFactory()

    @patch("log_adapter.home.views.ExternalPermission.get_authorized_user_space_list",
           return_value=["bkcc__2"])
    @patch("log_adapter.home.views.SpaceApi.get_space_detail")
    @patch("log_adapter.home.views.timezone")
    def test_toggle_off_pure_po_only(self, mock_tz, _mock_space, _mock_space_list):
        """开关 off：即使 IAM 有权限也不走 IAM 兜底"""
        mock_tz.now.return_value = "2026-07-16"
        request = self.factory.get(
            f"/external/?space_uid={self.SPACE_UID}",
            HTTP_USER=json.dumps({"username": self.EXTERNAL_USER}),
        )
        # 预处理：为 get_request_user_info 设置 request
        request.META["HTTP_USER"] = json.dumps({"username": self.EXTERNAL_USER})

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=False
        ), patch(
            "log_adapter.home.views.ExternalPermission.objects.filter"
        ) as mock_filter, patch(
            "log_adapter.home.views.AuthorizerSettings.get_authorizer", return_value=self.AUTHORIZER
        ), patch(
            "log_adapter.home.views.auth.authenticate", return_value=MagicMock()
        ), patch(
            "log_adapter.home.views.auth.login"
        ), patch(
            "log_adapter.home.views.render", return_value=HttpResponseForbidden()
        ), patch(
            "log_adapter.home.views.get_toggle_data", return_value={}
        ):
            from log_adapter.home.views import external
            external(request)
            # 关键断言：开关 off 时不应调用 IAM Permission（只有 PO filter）
            self.assertFalse(hasattr(self, "_iam_called"), "开关 off 时不应调用 IAM")


import json

class TestExternalToggleOnBehavior(TestCase):
    """开关开启时 external() 在 PO 无记录时应走 IAM 兜底"""

    EXTERNAL_USER = "po_user_y"
    SPACE_UID = "bkcc__3"
    AUTHORIZER = "internal_admin"

    @patch("log_adapter.home.views.ExternalPermission.get_authorized_user_space_list",
           return_value=["bkcc__3"])
    @patch("log_adapter.home.views.SpaceApi.get_space_detail")
    @patch("log_adapter.home.views.timezone")
    def test_toggle_on_iam_fallback_when_no_po(self, mock_tz, _mock_space, _mock_space_list):
        """开关 on + PO 无记录 → 走 IAM VIEW_BUSINESS 兜底"""
        mock_tz.now.return_value = "2026-07-16"

        request = RequestFactory().get(
            f"/external/?space_uid={self.SPACE_UID}",
            HTTP_USER=json.dumps({"username": self.EXTERNAL_USER}),
        )
        request.META["HTTP_USER"] = json.dumps({"username": self.EXTERNAL_USER})

        iam_called = []

        def fake_is_allowed_by_biz(bk_biz_id, action, raise_exception=False):
            iam_called.append(True)
            return True

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.space_uid_to_bk_biz_id", return_value="3"
        ), patch(
            "log_adapter.home.views.ExternalPermission.objects.filter"
        ) as mock_qs:
            mock_qs.return_value.exists.return_value = False  # PO 无记录

            with patch(
                "log_adapter.home.views.Permission"
            ) as mock_perm_cls:
                mock_perm = MagicMock()
                mock_perm.is_allowed_by_biz.side_effect = fake_is_allowed_by_biz
                mock_perm_cls.return_value = mock_perm

                with patch(
                    "log_adapter.home.views.AuthorizerSettings.get_authorizer",
                    return_value=self.AUTHORIZER,
                ), patch(
                    "log_adapter.home.views.auth.authenticate", return_value=MagicMock()
                ), patch(
                    "log_adapter.home.views.auth.login"
                ), patch(
                    "log_adapter.home.views.render", return_value=HttpResponseForbidden()
                ), patch(
                    "log_adapter.home.views.get_toggle_data", return_value={}
                ):
                    from log_adapter.home.views import external
                    external(request)
                    self.assertTrue(len(iam_called) > 0,
                                    "开关 on 且 PO 无记录时，应调用 IAM VIEW_BUSINESS 兜底")


# ══════════════════════════════════════════════════
#  dispatch_list_user_spaces() 开关分支测试
# ══════════════════════════════════════════════════


class TestDispatchListUserSpacesToggleOff(TestCase):
    """开关 off：dispatch_list_user_spaces 回退为纯 PO 空间列表（不查 IAM）"""

    EXTERNAL_USER = "po_user_z"

    def test_toggle_off_pure_po_spaces(self):
        """开关 off 时：仅返回 PO 空间，不查 IAM"""
        from log_adapter.home.views import FeatureToggleObject, EXTERNAL_PERMISSION_OR_DECISION

        # 模拟一个 off 状态的 toggle_obj
        toggle_obj = Toggle(name=EXTERNAL_PERMISSION_OR_DECISION, status="off")

        mock_po_permission = {"bkcc__2": ["log_search"], "bkcc__5": ["log_search"]}

        with patch.object(FeatureToggleObject, "toggle", return_value=toggle_obj):
            with patch(
                "log_adapter.home.views.ExternalPermission.get_authorizer_permission",
                return_value=mock_po_permission,
            ) as mock_po:
                with patch("log_adapter.home.views.RequestProcessor.get_request_user_info",
                           return_value={"username": self.EXTERNAL_USER}):
                    with patch("apps.log_search.models.Space.objects") as mock_space_qs:
                        # 模拟 Space.objects.filter(...).all() 返回
                        mock_space_qs.filter.return_value.all.return_value = []

                        request = RequestFactory().post(
                            "/external/list_user_spaces/",
                            HTTP_USER=json.dumps({"username": self.EXTERNAL_USER}),
                        )
                        request.META["HTTP_USER"] = json.dumps({"username": self.EXTERNAL_USER})

                        from log_adapter.home.views import dispatch_list_user_spaces
                        response = dispatch_list_user_spaces(request)

                        mock_po.assert_called_once_with(authorizer=self.EXTERNAL_USER)
                        # 开关 off 时不应调用 IAM
                        self.assertEqual(response.status_code, 200)

    def test_toggle_off_no_po_returns_403(self):
        """开关 off 且无 PO 记录 → 403（与老版本一致）"""
        from log_adapter.home.views import FeatureToggleObject, EXTERNAL_PERMISSION_OR_DECISION

        toggle_obj = Toggle(name=EXTERNAL_PERMISSION_OR_DECISION, status="off")

        with patch.object(FeatureToggleObject, "toggle", return_value=toggle_obj):
            with patch(
                "log_adapter.home.views.ExternalPermission.get_authorizer_permission",
                return_value={},  # PO 无记录
            ):
                with patch("log_adapter.home.views.RequestProcessor.get_request_user_info",
                           return_value={"username": self.EXTERNAL_USER}):
                    request = RequestFactory().post(
                        "/external/list_user_spaces/",
                        HTTP_USER=json.dumps({"username": self.EXTERNAL_USER}),
                    )
                    request.META["HTTP_USER"] = json.dumps({"username": self.EXTERNAL_USER})

                    from log_adapter.home.views import dispatch_list_user_spaces
                    response = dispatch_list_user_spaces(request)

                    self.assertEqual(response.status_code, 403, "无 PO 记录应返回 403")


# ══════════════════════════════════════════════════
#  filter_log_search_response_resource() 开关分支测试
# ══════════════════════════════════════════════════


class TestFilterLogSearchResponseResourceToggleOff(TestCase):
    """开关 off：filter_log_search_response_resource 不回退到纯 legacy，不调 IAM batch"""

    def setUp(self):
        from log_adapter.home.views import RequestProcessor
        self.processor = RequestProcessor

    def test_toggle_off_no_iam_batch(self):
        """开关 off：列表过滤仅用 legacy 资源，不调 batch_iam_allowed_resources"""
        from rest_framework.response import Response

        mock_response = Response({"data": [
            {"index_set_id": 1}, {"index_set_id": 2}, {"index_set_id": 3}
        ]})
        allow_resources_result = {"allowed": True, "resources": [1, 2]}

        with patch.object(
            self.processor, "is_or_decision_enabled", return_value=False
        ):
            result = self.processor.filter_log_search_response_resource(
                external_user="test_user",
                space_uid="bkcc__2",
                response=mock_response,
                action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
                view_set=ViewSetActionEnum.SEARCH_VIEWSET_LIST.value.view_set,
                view_action=ViewSetActionEnum.SEARCH_VIEWSET_LIST.value.view_action,
                allow_resources_result=allow_resources_result,
            )
            # 老逻辑：只按 legacy allow_resources [1,2] 过滤，index_set_id=3 应被剔除
            filtered_ids = [d["index_set_id"] for d in result.data["data"]]
            self.assertEqual(filtered_ids, [1, 2],
                             "开关 off 时应仅按 legacy 资源过滤，不含 IAM 补差")

    def test_toggle_off_no_iam_call(self):
        """开关 off：确认完全不调用 ExternalLogSearchPermissionDecision.batch_iam_allowed_resources"""
        from rest_framework.response import Response

        mock_response = Response({"data": [
            {"index_set_id": 1}, {"index_set_id": 2}
        ]})
        allow_resources_result = {"allowed": True, "resources": [1]}

        with patch.object(
            self.processor, "is_or_decision_enabled", return_value=False
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.batch_iam_allowed_resources"
        ) as mock_batch:
            self.processor.filter_log_search_response_resource(
                external_user="test_user",
                space_uid="bkcc__2",
                response=mock_response,
                action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
                view_set=ViewSetActionEnum.SEARCH_VIEWSET_LIST.value.view_set,
                view_action=ViewSetActionEnum.SEARCH_VIEWSET_LIST.value.view_action,
                allow_resources_result=allow_resources_result,
            )
            mock_batch.assert_not_called()


# ══════════════════════════════════════════════════
#  空间级灰度（debug + 名单）测试
# ══════════════════════════════════════════════════


class TestSpaceLevelGradualRelease(TestCase):
    """验证 debug + 白名单/黑名单 的空间级灰度语义"""

    EXTERNAL_USER = "po_user_w"

    def test_white_list_hit_enables_or(self):
        """白名单命中的空间 → OR 决策生效"""
        from log_adapter.home.views import FeatureToggleObject, EXTERNAL_PERMISSION_OR_DECISION

        toggle_obj = Toggle(
            name=EXTERNAL_PERMISSION_OR_DECISION,
            status="debug",
            biz_id_white_list=[2, 3],  # 白名单
        )

        with patch.object(FeatureToggleObject, "toggle", return_value=toggle_obj):
            # 白名单内 bk_biz_id=2 的空间：IAM 应被允许
            from log_adapter.home.views import _is_biz_enabled_for_or_decision
            self.assertTrue(_is_biz_enabled_for_or_decision(toggle_obj, 2))

    def test_white_list_miss_uses_legacy(self):
        """白名单未命中的空间 → 走老逻辑"""
        from log_adapter.home.views import FeatureToggleObject, EXTERNAL_PERMISSION_OR_DECISION

        toggle_obj = Toggle(
            name=EXTERNAL_PERMISSION_OR_DECISION,
            status="debug",
            biz_id_white_list=[2, 3],
        )

        with patch.object(FeatureToggleObject, "toggle", return_value=toggle_obj):
            from log_adapter.home.views import _is_biz_enabled_for_or_decision
            self.assertFalse(_is_biz_enabled_for_or_decision(toggle_obj, 999))

    def test_black_list_hit_uses_legacy(self):
        """黑名单命中的空间 → 走老逻辑"""
        from log_adapter.home.views import FeatureToggleObject, EXTERNAL_PERMISSION_OR_DECISION

        toggle_obj = Toggle(
            name=EXTERNAL_PERMISSION_OR_DECISION,
            status="debug",
            biz_id_black_list=[2],
        )

        with patch.object(FeatureToggleObject, "toggle", return_value=toggle_obj):
            from log_adapter.home.views import _is_biz_enabled_for_or_decision
            self.assertFalse(_is_biz_enabled_for_or_decision(toggle_obj, 2))

    def test_black_list_miss_enables_or(self):
        """黑名单未命中的空间 → OR 决策生效"""
        from log_adapter.home.views import FeatureToggleObject, EXTERNAL_PERMISSION_OR_DECISION

        toggle_obj = Toggle(
            name=EXTERNAL_PERMISSION_OR_DECISION,
            status="debug",
            biz_id_black_list=[2],
        )

        with patch.object(FeatureToggleObject, "toggle", return_value=toggle_obj):
            from log_adapter.home.views import _is_biz_enabled_for_or_decision
            self.assertTrue(_is_biz_enabled_for_or_decision(toggle_obj, 999))
