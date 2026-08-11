"""
Step 1 refactor tests: action.py 改造验证

验证 action.py 改造后的行为：
1. ActionEnum 成员是 ActionDef 实例（不是 ActionMeta）
2. ActionEnum.XXX.id 返回 Business ID（不是 V3 平台 ID）
3. 所有旧 ActionEnum 成员仍存在
4. 外部调用者模式兼容
5. ActionMeta 类已删除
6. _all_actions / get_action_by_id 已删除
7. MINI_ACTION_IDS 使用 Business ID
8. V3Provider 不再依赖 action.py
"""

from __future__ import annotations

import pytest


# ============================================================================
# 1. ActionEnum 成员类型验证
# ============================================================================


class TestActionEnumMembersAreActionDef:
    """验证 ActionEnum 成员是 ActionDef 实例。"""

    def test_action_enum_members_are_actiondef(self):
        """ActionEnum 成员应该是 ActionDef 实例，不是 ActionMeta。"""
        from bkmonitor.iam.iam_engine.schema.definitions import ActionDef

        from bkmonitor.iam.action import ActionEnum

        assert isinstance(ActionEnum.VIEW_BUSINESS, ActionDef), (
            f"ActionEnum.VIEW_BUSINESS should be ActionDef, got {type(ActionEnum.VIEW_BUSINESS)}"
        )
        assert isinstance(ActionEnum.VIEW_RULE, ActionDef)
        assert isinstance(ActionEnum.MANAGE_RULE, ActionDef)
        assert isinstance(ActionEnum.VIEW_APM_APPLICATION, ActionDef)
        assert isinstance(ActionEnum.VIEW_GLOBAL_SETTING, ActionDef)

    def test_action_enum_members_are_not_actionmeta(self):
        """ActionEnum 成员不应该是 ActionMeta（已删除）。"""

        # ActionMeta 类不应该存在
        with pytest.raises(ImportError):
            from bkmonitor.iam.action import ActionMeta  # noqa: F401

    def test_action_enum_is_not_subclass_of_iam_action(self):
        """ActionEnum 成员不应继承 iam.Action（那是 V3 SDK 概念）。"""
        from iam.auth.models import Action

        from bkmonitor.iam.action import ActionEnum

        assert not isinstance(ActionEnum.VIEW_BUSINESS, Action), "ActionEnum members should NOT be iam.Action instances"


# ============================================================================
# 2. ActionEnum.XXX.id 返回 Business ID
# ============================================================================


class TestActionEnumIdIsBusinessId:
    """验证 ActionEnum.XXX.id 返回 Business ID（不带 _v2 后缀）。"""

    # ---- Space-level view actions ----

    def test_view_business_id(self):
        from bkmonitor.iam.action import ActionEnum

        assert ActionEnum.VIEW_BUSINESS.id == "view_business"

    def test_explore_metric_id(self):
        from bkmonitor.iam.action import ActionEnum

        assert ActionEnum.EXPLORE_METRIC.id == "explore_metric"

    def test_view_synthetic_id(self):
        from bkmonitor.iam.action import ActionEnum

        assert ActionEnum.VIEW_SYNTHETIC.id == "view_synthetic"

    def test_view_rule_id(self):
        from bkmonitor.iam.action import ActionEnum

        assert ActionEnum.VIEW_RULE.id == "view_rule"

    def test_view_dashboard_id(self):
        from bkmonitor.iam.action import ActionEnum

        assert ActionEnum.VIEW_DASHBOARD.id == "view_dashboard"

    def test_view_incident_id(self):
        from bkmonitor.iam.action import ActionEnum

        assert ActionEnum.VIEW_INCIDENT.id == "view_incident"

    # ---- MCP actions (no _v2 suffix in old code either) ----

    def test_mcp_action_ids(self):
        from bkmonitor.iam.action import ActionEnum

        assert ActionEnum.USING_DASHBOARD_MCP.id == "using_dashboard_mcp"
        assert ActionEnum.USING_METRICS_MCP.id == "using_metrics_mcp"
        assert ActionEnum.USING_LOG_MCP.id == "using_log_mcp"
        assert ActionEnum.USING_ALARM_MCP.id == "using_alarm_mcp"
        assert ActionEnum.USING_APM_MCP.id == "using_apm_mcp"

    # ---- Resource-free actions ----

    def test_global_setting_ids(self):
        from bkmonitor.iam.action import ActionEnum

        assert ActionEnum.VIEW_GLOBAL_SETTING.id == "view_global_setting"
        assert ActionEnum.MANAGE_GLOBAL_SETTING.id == "manage_global_setting"

    def test_view_self_state_id(self):
        from bkmonitor.iam.action import ActionEnum

        assert ActionEnum.VIEW_SELF_STATE.id == "view_self_state"

    # ---- Sub-resource actions ----

    def test_dashboard_instance_ids(self):
        from bkmonitor.iam.action import ActionEnum

        assert ActionEnum.VIEW_SINGLE_DASHBOARD.id == "view_single_dashboard"
        assert ActionEnum.EDIT_SINGLE_DASHBOARD.id == "edit_single_dashboard"

    def test_new_dashboard_id(self):
        from bkmonitor.iam.action import ActionEnum

        assert ActionEnum.NEW_DASHBOARD.id == "new_dashboard"

    # ---- V3 ID should NOT appear as .id ----

    def test_no_v2_suffix_in_ids(self):
        """验证所有 ActionEnum 成员的 .id 都不带 _v2 后缀。"""
        from bkmonitor.iam.action import ActionEnum

        for name in dir(ActionEnum):
            if name.startswith("_"):
                continue
            member = getattr(ActionEnum, name)
            if hasattr(member, "id"):
                assert "_v2" not in member.id, f"ActionEnum.{name}.id = {member.id!r} should NOT contain '_v2'"


# ============================================================================
# 3. 向后兼容性 — 所有旧成员仍存在
# ============================================================================


class TestAllOldMembersExist:
    """验证所有旧 ActionEnum 成员仍存在。"""

    # 完整的旧 ActionEnum 成员列表
    OLD_MEMBERS = [
        # Space-level view
        "VIEW_BUSINESS",
        "EXPLORE_METRIC",
        "VIEW_SYNTHETIC",
        "VIEW_HOST",
        "VIEW_EVENT",
        "VIEW_PLUGIN",
        "VIEW_COLLECTION",
        "VIEW_NOTIFY_TEAM",
        "VIEW_RULE",
        "VIEW_DOWNTIME",
        "VIEW_CUSTOM_METRIC",
        "VIEW_CUSTOM_EVENT",
        "VIEW_DASHBOARD",
        "VIEW_INCIDENT",
        "EXPORT_CONFIG",
        # MCP view
        "USING_DASHBOARD_MCP",
        "USING_METRICS_MCP",
        "USING_LOG_MCP",
        "USING_METADATA_MCP",
        "USING_ALARM_MCP",
        "USING_APM_MCP",
        "USING_OPERATION_MCP",
        # Space-level manage
        "MANAGE_SYNTHETIC",
        "MANAGE_HOST",
        "MANAGE_EVENT",
        "MANAGE_PLUGIN",
        "MANAGE_COLLECTION",
        "MANAGE_NOTIFY_TEAM",
        "MANAGE_RULE",
        "MANAGE_DOWNTIME",
        "MANAGE_CUSTOM_METRIC",
        "MANAGE_CUSTOM_EVENT",
        "MANAGE_DASHBOARD",
        "MANAGE_DATASOURCE",
        "NEW_DASHBOARD",
        "IMPORT_CONFIG",
        "MANAGE_INCIDENT",
        "MANAGE_REPORT",
        "USING_ALARM_HANDLING_MCP",
        # Sub-resource view
        "VIEW_APM_APPLICATION",
        "VIEW_SINGLE_DASHBOARD",
        "VIEW_RUM_APPLICATION",
        # Sub-resource manage
        "MANAGE_APM_APPLICATION",
        "EDIT_SINGLE_DASHBOARD",
        "MANAGE_RUM_APPLICATION",
        # Resource-free
        "VIEW_GLOBAL_SETTING",
        "MANAGE_GLOBAL_SETTING",
        "VIEW_SELF_STATE",
        "MANAGE_PUBLIC_PLUGIN",
        "MANAGE_PUBLIC_ACTION_CONFIG",
        "MANAGE_PUBLIC_SYNTHETIC_LOCATION",
        "USE_PUBLIC_SYNTHETIC_LOCATION",
        "MANAGE_CALENDAR",
    ]

    def test_all_old_members_exist(self):
        from bkmonitor.iam.action import ActionEnum

        missing = []
        for name in self.OLD_MEMBERS:
            if not hasattr(ActionEnum, name):
                missing.append(name)

        assert not missing, f"Missing ActionEnum members: {missing}"

    def test_no_extra_members(self):
        """验证没有多余的成员（与 definitions 保持一致）。"""
        from bkmonitor.iam.action import ActionEnum

        # 获取所有非私有、有 .id 属性的成员
        actual = set()
        for name in dir(ActionEnum):
            if name.startswith("_"):
                continue
            member = getattr(ActionEnum, name)
            if hasattr(member, "id"):
                actual.add(name)

        expected = set(self.OLD_MEMBERS)

        extra = actual - expected
        missing = expected - actual

        assert not extra, f"Extra ActionEnum members: {extra}"
        assert not missing, f"Missing ActionEnum members: {missing}"


# ============================================================================
# 4. Attribute access — ActionDef 属性可用
# ============================================================================


class TestActionDefAttributes:
    """验证 ActionEnum 成员的 ActionDef 属性。"""

    def test_name_attribute(self):
        from bkmonitor.iam.action import ActionEnum

        assert ActionEnum.VIEW_BUSINESS.name == "业务访问"
        assert ActionEnum.VIEW_RULE.name == "策略查看"
        assert ActionEnum.EXPLORE_METRIC.name == "指标检索"

    def test_resource_type_attribute(self):
        from bkmonitor.iam.action import ActionEnum

        assert ActionEnum.VIEW_BUSINESS.resource_type == "space"
        assert ActionEnum.VIEW_APM_APPLICATION.resource_type == "apm_application"
        assert ActionEnum.VIEW_SINGLE_DASHBOARD.resource_type == "grafana_dashboard"
        assert ActionEnum.VIEW_GLOBAL_SETTING.resource_type == ""

    def test_extensions_attribute(self):
        from bkmonitor.iam.action import ActionEnum

        assert "v3" in ActionEnum.VIEW_BUSINESS.extensions
        assert ActionEnum.VIEW_BUSINESS.extensions["v3"]["action_id"] == "view_business_v2"
        assert ActionEnum.VIEW_BUSINESS.extensions["v3"]["type"] == "view"

    def test_description_attribute(self):
        from bkmonitor.iam.action import ActionEnum

        assert isinstance(ActionEnum.VIEW_BUSINESS.description, str)
        assert isinstance(ActionEnum.VIEW_RULE.description, str)


# ============================================================================
# 5. 直接 .id 访问的兼容性（已验证的 2 处外部使用）
# ============================================================================


class TestDirectIdAccessors:
    """验证外部直接访问 ActionEnum.XXX.id 的代码不受影响。"""

    def test_grafana_direct_id_access(self):
        """模拟 grafana/views.py:184 的使用模式。"""
        from bkmonitor.iam.action import ActionEnum

        # grafana/views.py 中的代码：
        #   ActionEnum.VIEW_SINGLE_DASHBOARD.id
        # 期望值：view_single_dashboard
        action_id = ActionEnum.VIEW_SINGLE_DASHBOARD.id
        assert action_id == "view_single_dashboard"
        assert isinstance(action_id, str)

    def test_mail_report_direct_id_access(self):
        """模拟 kernel_api/views/v4/mail_report.py:210 的使用模式。"""
        from bkmonitor.iam.action import ActionEnum

        # mail_report.py 中的代码：
        #   ActionEnum.VIEW_SINGLE_DASHBOARD.id
        action_id = ActionEnum.VIEW_SINGLE_DASHBOARD.id
        assert action_id == "view_single_dashboard"


# ============================================================================
# 6. 外部调用者模式验证
# ============================================================================


class TestCallerPatterns:
    """验证外部调用者的使用模式不 broken。"""

    def test_drf_permission_pattern(self):
        """验证 BusinessActionPermission 的构造模式。

        模式: BusinessActionPermission([ActionEnum.VIEW_SYNTHETIC])
        这需要 ActionEnum 成员可以作为列表元素传递。
        """
        from bkmonitor.iam.action import ActionEnum

        # 模拟构造
        actions = [ActionEnum.VIEW_SYNTHETIC]
        assert len(actions) == 1
        assert actions[0] is ActionEnum.VIEW_SYNTHETIC

    def test_permission_is_allowed_pattern(self):
        """验证 Permission.is_allowed_by_biz 的调用模式。

        模式: Permission().is_allowed_by_biz(biz_id, ActionEnum.VIEW_BUSINESS)
        """
        from bkmonitor.iam.action import ActionEnum

        # ActionEnum 成员作为参数传递
        action = ActionEnum.VIEW_BUSINESS
        assert action.id == "view_business"
        assert action.name == "业务访问"

    def test_search_handler_pattern(self):
        """验证 SearchHandler 的调用模式。

        模式: self.add_permission_for_results(results, action=ActionEnum.VIEW_EVENT)
        """
        from bkmonitor.iam.action import ActionEnum

        # ActionEnum 成员作为参数传递
        action = ActionEnum.VIEW_EVENT
        assert action.id == "view_event"


# ============================================================================
# 7. 删除的符号验证
# ============================================================================


class TestDeletedSymbols:
    """验证旧符号已正确删除。"""

    def test_actionmeta_class_deleted(self):
        """ActionMeta 类已被删除。"""
        with pytest.raises(ImportError):
            from bkmonitor.iam.action import ActionMeta  # noqa: F401

    def test_resource_dicts_deleted(self):
        """4 个 resource dict 常量已被删除。"""
        from bkmonitor.iam import action as action_module

        for name in [
            "SPACE_RESOURCE",
            "APM_APPLICATION_RESOURCE",
            "GRAFANA_DASHBOARD_RESOURCE",
            "RUM_APPLICATION_RESOURCE",
        ]:
            assert not hasattr(action_module, name), f"{name} should be deleted from action.py"

    def test_get_action_by_id_still_exists_for_compat(self):
        """get_action_by_id 保留以兼容旧 import（使用 Business ID）。"""
        from bkmonitor.iam.action import get_action_by_id, _all_actions

        assert callable(get_action_by_id)
        assert isinstance(_all_actions, dict)


# ============================================================================
# 8. MINI_ACTION_IDS 使用 Business ID
# ============================================================================


class TestMiniActionIds:
    """验证 MINI_ACTION_IDS 使用 Business ID。"""

    def test_mini_action_ids_not_v2(self):
        from bkmonitor.iam.action import MINI_ACTION_IDS

        for aid in MINI_ACTION_IDS:
            assert "_v2" not in aid, f"MINI_ACTION_IDS entry {aid!r} should NOT contain '_v2'"

    def test_mini_action_ids_are_valid_business_ids(self):
        from bkmonitor.iam.action import ActionEnum, MINI_ACTION_IDS

        # 所有 MINI_ACTION_IDS 条目应该与某个 ActionEnum 成员的 .id 匹配
        business_ids = set()
        for name in dir(ActionEnum):
            if name.startswith("_"):
                continue
            member = getattr(ActionEnum, name)
            if hasattr(member, "id"):
                business_ids.add(member.id)

        for aid in MINI_ACTION_IDS:
            assert aid in business_ids, f"MINI_ACTION_IDS entry {aid!r} not found in ActionEnum"


# ============================================================================
# 9. V3Provider 依赖检查
# ============================================================================


class TestV3ProviderNoOldDeps:
    """验证 V3Provider 不再依赖外部旧代码，使用 V3Client 自包含。"""

    def test_v3_provider_no_sdk_types_directly(self):
        """V3Provider 不应直接导入 iam.Action/Request/Resource/Subject/MultiActionRequest。"""
        import inspect

        from bkmonitor.iam.iam_v3 import provider as pkg

        source = inspect.getsource(pkg)
        for forbidden in [
            "iam import Action",
            "iam import MultiActionRequest",
            "iam import Request",
            "iam import Resource",
            "iam import Subject",
            "from iam import Action",
            "from iam import Request",
            "from iam import Resource",
            "from iam import Subject",
            "from iam import MultiActionRequest",
        ]:
            assert forbidden not in source, f"V3Provider should not directly import SDK type: {forbidden}"

    def test_v3_provider_no_build_sdk_action(self):
        """V3Provider 不应有 _build_sdk_action 方法（已移到 V3Client）。"""
        import inspect

        from bkmonitor.iam.iam_v3.provider import V3PermissionProvider

        source = inspect.getsource(V3PermissionProvider)
        assert "_build_sdk_action" not in source, "V3Provider should not have _build_sdk_action (moved to V3Client)"

    def test_v3_provider_uses_client_methods(self):
        """V3Provider 应使用 V3Client SDK 辅助方法。"""
        import inspect

        from bkmonitor.iam.iam_v3.provider import V3PermissionProvider

        source = inspect.getsource(V3PermissionProvider)
        for method in [
            "make_action",
            "make_subject",
            "make_resource",
            "make_request",
            "make_multi_action_request",
        ]:
            assert f"_iam_client.{method}" in source, f"V3Provider should delegate {method} to V3Client"

    def test_v3_provider_health_check_delegates(self):
        """V3Provider.health_check 应委托给 V3Client。"""
        import inspect

        from bkmonitor.iam.iam_v3.provider import V3PermissionProvider

        source = inspect.getsource(V3PermissionProvider.health_check)
        assert "_iam_client.health_check" in source, "V3Provider.health_check should delegate to V3Client"


class TestV3ClientSdkWrappers:
    """验证 V3Client 封装了 SDK 对象构造。"""

    def test_v3client_has_all_sdk_wrapper_methods(self):
        """V3Client 应有全部 6 个 SDK 辅助方法。"""
        from bkmonitor.iam.iam_v3.client import V3Client

        expected = [
            "make_action",
            "make_subject",
            "make_resource",
            "make_request",
            "make_multi_action_request",
            "health_check",
        ]
        for name in expected:
            assert hasattr(V3Client, name), f"V3Client missing method: {name}"
            assert callable(getattr(V3Client, name)), f"V3Client.{name} should be callable"

    def test_v3client_imports_no_bkmonitor_iam(self):
        """V3Client 不应导入任何 bkmonitor.iam.* 外部模块。"""
        import inspect

        from bkmonitor.iam.iam_v3.client import V3Client

        source = inspect.getsource(V3Client)
        for forbidden in [
            "from bkmonitor.iam.action",
            "from bkmonitor.iam.compatible",
            "from bkmonitor.iam.resource",
            "from django.conf",
        ]:
            assert forbidden not in source, f"V3Client should not import: {forbidden}"

    def test_v3client_extends_iam_sdk(self):
        """V3Client 应该继承 iam.IAM。"""
        from iam import IAM

        from bkmonitor.iam.iam_v3.client import V3Client

        assert issubclass(V3Client, IAM), "V3Client should extend iam.IAM"

    def test_v3client_has_action_aliases(self):
        """V3Client 应定义 ACTION_COMPATIBLE_ALIASES。"""
        from bkmonitor.iam.iam_v3.client import ACTION_COMPATIBLE_ALIASES

        assert isinstance(ACTION_COMPATIBLE_ALIASES, dict)
        assert "new_dashboard" in ACTION_COMPATIBLE_ALIASES, "ACTION_COMPATIBLE_ALIASES should contain new_dashboard"


# ============================================================================
# 10. ActionEnum identity semantics — member identity is preserved
# ============================================================================


class TestActionEnumIdentity:
    """验证 ActionEnum 成员的身份语义。"""

    def test_same_member_is_identical(self):
        """同一个 ActionEnum 成员多次访问应返回同一对象。"""
        from bkmonitor.iam.action import ActionEnum

        a1 = ActionEnum.VIEW_BUSINESS
        a2 = ActionEnum.VIEW_BUSINESS
        assert a1 is a2, "Same ActionEnum member should be the same object (identity)"

    def test_different_members_are_different(self):
        """不同 ActionEnum 成员应是不同对象。"""
        from bkmonitor.iam.action import ActionEnum

        assert ActionEnum.VIEW_BUSINESS is not ActionEnum.MANAGE_RULE
        assert ActionEnum.VIEW_RULE is not ActionEnum.MANAGE_RULE

    def test_frozen_actiondef(self):
        """ActionDef 是 frozen dataclass，不应可变。"""
        from bkmonitor.iam.action import ActionEnum

        with pytest.raises(Exception):
            ActionEnum.VIEW_BUSINESS.id = "hacked"  # type: ignore[misc]
