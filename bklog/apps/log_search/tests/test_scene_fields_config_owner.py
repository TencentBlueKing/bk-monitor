"""
Unit tests for SceneFieldsConfigHandler ownership validation.

按 config_id 取字段模板时必须校验归属，避免枚举 config_id 越权读取/删除/应用
其他业务 / 其他 SaaS 应用的模板（P1: scene_fields_config.py config_id 越权）。
"""

from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from apps.log_search.exceptions import SceneFieldsConfigNotExistException
from apps.log_search.handlers.search.scene_fields_config import SceneFieldsConfigHandler


def _bare_handler(source_app_code="bk_log_search", bk_biz_id=None, scene_id=None, scope="default"):
    """构造不走 __init__ 的裸 handler，仅用于校验逻辑单测。"""
    handler = SceneFieldsConfigHandler.__new__(SceneFieldsConfigHandler)
    handler.source_app_code = source_app_code
    handler.bk_biz_id = bk_biz_id
    handler.scene_id = scene_id
    handler.scope = scope
    return handler


def _config_obj(source_app_code="bk_log_search", bk_biz_id=2, scene_id="k8s"):
    obj = Mock()
    obj.source_app_code = source_app_code
    obj.bk_biz_id = bk_biz_id
    obj.scene_id = scene_id
    return obj


@override_settings(IGNORE_IAM_PERMISSION=True)
class TestSceneFieldsConfigOwnership(TestCase):
    """覆盖 _validate_ownership 的归属隔离逻辑（IAM 关闭以专注归属判定）。"""

    def test_cross_source_app_code_denied(self):
        handler = _bare_handler(source_app_code="other_app")
        handler.data = _config_obj(source_app_code="bk_log_search")
        with self.assertRaises(SceneFieldsConfigNotExistException):
            handler._validate_ownership()

    def test_mismatched_bk_biz_id_denied(self):
        handler = _bare_handler(bk_biz_id=999)
        handler.data = _config_obj(bk_biz_id=2)
        with self.assertRaises(SceneFieldsConfigNotExistException):
            handler._validate_ownership()

    def test_mismatched_scene_id_denied(self):
        handler = _bare_handler(scene_id="host")
        handler.data = _config_obj(scene_id="k8s")
        with self.assertRaises(SceneFieldsConfigNotExistException):
            handler._validate_ownership()

    def test_same_owner_passes(self):
        handler = _bare_handler(source_app_code="bk_log_search", bk_biz_id=2, scene_id="k8s")
        handler.data = _config_obj(source_app_code="bk_log_search", bk_biz_id=2, scene_id="k8s")
        # 不抛异常即通过
        handler._validate_ownership()

    def test_config_id_only_path_passes_when_same_app(self):
        """retrieve/delete/apply 仅传 config_id（bk_biz_id/scene_id 为 None），
        归属校验只比 source_app_code，并走业务级 IAM（此处 IGNORE 关闭跳过）。"""
        handler = _bare_handler(bk_biz_id=None, scene_id=None)
        handler.data = _config_obj()
        handler._validate_ownership()


@override_settings(IGNORE_IAM_PERMISSION=False)
class TestSceneFieldsConfigBusinessPermission(TestCase):
    """覆盖归属一致时仍需对模板所属业务做 VIEW_BUSINESS 鉴权。"""

    def test_business_permission_denied_propagates(self):
        handler = _bare_handler(bk_biz_id=None, scene_id=None)
        handler.data = _config_obj(bk_biz_id=2)
        with patch(
            "apps.iam.handlers.permission.Permission"
        ) as m_perm_cls:
            m_perm_cls.return_value.is_allowed.side_effect = PermissionError("denied")
            with self.assertRaises(PermissionError):
                handler._validate_ownership()
            m_perm_cls.return_value.is_allowed.assert_called_once()

    def test_business_permission_allowed_passes(self):
        handler = _bare_handler(bk_biz_id=None, scene_id=None)
        handler.data = _config_obj(bk_biz_id=2)
        with patch(
            "apps.iam.handlers.permission.Permission"
        ) as m_perm_cls:
            m_perm_cls.return_value.is_allowed.return_value = True
            handler._validate_ownership()
            m_perm_cls.return_value.is_allowed.assert_called_once()
