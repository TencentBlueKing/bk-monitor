"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import MagicMock, patch

import pytest
from iam.exceptions import AuthAPIError

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin.permission import (
    _batch_query_policies,
    _build_action_result_item,
    _fallback_query_policies,
    _field_to_resource_type,
    _get_resource_type,
    _parse_action_permissions,
    _parse_iam_path,
    _parse_permission_entries,
    _resolve_display_names,
    _resolve_parent_paths,
    action_categories,
    query_user_permissions,
)

# ---------------------------------------------------------------------------
# Real IAM condition data captured from pre-release pod (xuchaoshan user, 2026-07-24)
# via: iam_client._do_policy_query_by_actions(multi_request, with_resources=False)
# ---------------------------------------------------------------------------

MOCK_POLICY_RESULTS = [
    # all space (any)
    {"action": {"id": "view_business_v2"}, "condition": {"field": "space.id", "op": "any", "value": []}},
    # partial space (in space.id)
    {"action": {"id": "explore_metric_v2"}, "condition": {"field": "space.id", "op": "in", "value": ["2", "-3", "3"]}},
    # none space (empty dict)
    {"action": {"id": "view_plugin_v2"}, "condition": {}},
    # none instance (empty dict)
    {"action": {"id": "view_apm_application_v2"}, "condition": {}},
    # partial instance with OR(in + starts_with)
    {
        "action": {"id": "manage_apm_application_v2"},
        "condition": {
            "content": [
                {"field": "apm_application.id", "op": "in", "value": ["390", "405"]},
                {
                    "content": [
                        {"field": "apm_application._bk_iam_path_", "op": "starts_with", "value": "/space,61/"},
                        {"field": "apm_application._bk_iam_path_", "op": "starts_with", "value": "/space,60/"},
                    ],
                    "op": "OR",
                },
            ],
            "op": "OR",
        },
    },
    # all global (any with empty field — CompatibleIAM V1)
    {"action": {"id": "manage_global_setting"}, "condition": {"field": "", "op": "any", "value": []}},
    # error global (None)
    {"action": {"id": "view_self_state"}, "condition": None},
    # CompatibleIAM V1+V2 merge: OR([any, any]) with empty field
    {
        "action": {"id": "manage_public_plugin"},
        "condition": {
            "op": "OR",
            "content": [
                {"op": "any", "field": "", "value": []},
                {"op": "any", "field": "", "value": []},
            ],
        },
    },
    # partial grafana with OR(in(id), OR(starts_with(path)))
    {
        "action": {"id": "view_single_dashboard"},
        "condition": {
            "content": [
                {"field": "grafana_dashboard.id", "op": "in", "value": ["14|f0ImroNIz", "14|nKviroNIz"]},
                {
                    "content": [
                        {"field": "grafana_dashboard._bk_iam_path_", "op": "starts_with", "value": "/space,2/"},
                        {"field": "grafana_dashboard._bk_iam_path_", "op": "starts_with", "value": "/space,-6/"},
                    ],
                    "op": "OR",
                },
            ],
            "op": "OR",
        },
    },
]


# ============================================================================
# _parse_iam_path
# ============================================================================


class TestParseIamPath:
    def test_single_segment(self):
        assert _parse_iam_path("/space,2/") == [{"type": "space", "id": "2"}]

    def test_multi_segment(self):
        result = _parse_iam_path("/space,2/apm_app,3/")
        assert result == [{"type": "space", "id": "2"}, {"type": "apm_app", "id": "3"}]

    def test_empty(self):
        assert _parse_iam_path("") == []
        assert _parse_iam_path("/") == []

    def test_no_trailing_slash(self):
        assert _parse_iam_path("/space,2") == [{"type": "space", "id": "2"}]

    def test_deep_nesting(self):
        """3+ levels — parser is unlimited."""
        result = _parse_iam_path("/space,1/sub_type,2/leaf,3/")
        assert len(result) == 3
        assert result[2] == {"type": "leaf", "id": "3"}


# ============================================================================
# _field_to_resource_type
# ============================================================================


class TestFieldToResourceType:
    def test_space_id(self):
        assert _field_to_resource_type("space.id") == "space"

    def test_instance_id(self):
        assert _field_to_resource_type("apm_application.id") == "apm_application"

    def test_iam_path(self):
        assert _field_to_resource_type("grafana_dashboard._bk_iam_path_") == "grafana_dashboard"

    def test_empty(self):
        assert _field_to_resource_type("") == ""
        assert _field_to_resource_type(None) == ""


# ============================================================================
# _parse_permission_entries
# ============================================================================


class TestParsePermissionEntries:
    def test_none_condition(self):
        is_all, entries = _parse_permission_entries(None, None)
        assert is_all is False
        assert entries == []

    def test_empty_dict(self):
        is_all, entries = _parse_permission_entries({}, None)
        assert is_all is False
        assert entries == []

    def test_any(self):
        is_all, entries = _parse_permission_entries({"op": "any"}, None)
        assert is_all is True
        assert entries == []

    def test_any_with_empty_field(self):
        """CompatibleIAM V1 condition: any with field=""."""
        is_all, entries = _parse_permission_entries({"op": "any", "field": "", "value": []}, None)
        assert is_all is True

    def test_in_space_id(self):
        cond = {"op": "in", "field": "space.id", "value": ["2", "5"]}
        is_all, entries = _parse_permission_entries(cond, "space")
        assert is_all is False
        assert len(entries) == 2
        assert entries[0] == {"path": [{"type": "space", "id": "2"}]}
        assert entries[1] == {"path": [{"type": "space", "id": "5"}]}

    def test_in_instance_id(self):
        cond = {"op": "in", "field": "apm_application.id", "value": ["390", "405"]}
        is_all, entries = _parse_permission_entries(cond, "apm_application")
        assert is_all is False
        assert len(entries) == 2
        assert entries[0]["path"][0] == {"type": "apm_application", "id": "390"}

    def test_in_empty_values(self):
        cond = {"op": "in", "field": "space.id", "value": []}
        is_all, entries = _parse_permission_entries(cond, None)
        assert is_all is False
        assert entries == []

    def test_eq(self):
        cond = {"op": "eq", "field": "space.id", "value": "2"}
        is_all, entries = _parse_permission_entries(cond, None)
        assert is_all is False
        assert entries == [{"path": [{"type": "space", "id": "2"}]}]

    def test_eq_empty_value(self):
        cond = {"op": "eq", "field": "space.id", "value": ""}
        is_all, entries = _parse_permission_entries(cond, None)
        assert is_all is False
        assert entries == []

    def test_starts_with(self):
        cond = {"field": "grafana_dashboard._bk_iam_path_", "op": "starts_with", "value": "/space,2/"}
        is_all, entries = _parse_permission_entries(cond, "grafana_dashboard")
        assert is_all is False
        assert entries == [{"path": [{"type": "space", "id": "2"}]}]

    def test_starts_with_empty(self):
        cond = {"field": "grafana_dashboard._bk_iam_path_", "op": "starts_with", "value": ""}
        is_all, entries = _parse_permission_entries(cond, "grafana_dashboard")
        assert is_all is False
        assert entries == []

    def test_or_combines(self):
        cond = {
            "op": "or",
            "content": [
                {"op": "in", "field": "space.id", "value": ["2", "5"]},
                {"op": "eq", "field": "space.id", "value": "10"},
            ],
        }
        is_all, entries = _parse_permission_entries(cond, "space")
        assert is_all is False
        assert len(entries) == 3
        ids = {e["path"][0]["id"] for e in entries}
        assert ids == {"2", "5", "10"}

    def test_or_with_any_sub(self):
        cond = {
            "op": "or",
            "content": [
                {"op": "in", "field": "space.id", "value": ["2"]},
                {"op": "any"},
            ],
        }
        is_all, entries = _parse_permission_entries(cond, None)
        assert is_all is True
        assert entries == []

    def test_or_nested_with_starts_with(self):
        """Real pattern: OR([in(id), OR([starts_with, ...])])."""
        cond = {
            "op": "OR",
            "content": [
                {"field": "apm_application.id", "op": "in", "value": ["390", "405"]},
                {
                    "content": [
                        {"field": "apm_application._bk_iam_path_", "op": "starts_with", "value": "/space,61/"},
                        {"field": "apm_application._bk_iam_path_", "op": "starts_with", "value": "/space,60/"},
                    ],
                    "op": "OR",
                },
            ],
        }
        is_all, entries = _parse_permission_entries(cond, "apm_application")
        assert is_all is False
        # 2 instance IDs + 2 space paths = 4 entries
        assert len(entries) == 4
        types = {(e["path"][0]["type"], e["path"][0]["id"]) for e in entries}
        assert ("apm_application", "390") in types
        assert ("apm_application", "405") in types
        assert ("space", "61") in types
        assert ("space", "60") in types

    def test_and_cartesian(self):
        """AND with prefix (starts_with) and leaf (in)."""
        cond = {
            "op": "and",
            "content": [
                {"field": "module._bk_iam_path_", "op": "starts_with", "value": "/space,2/"},
                {"field": "module.id", "op": "in", "value": ["10", "20"]},
            ],
        }
        is_all, entries = _parse_permission_entries(cond, "module")
        assert is_all is False
        assert len(entries) == 2
        assert entries[0] == {"path": [{"type": "space", "id": "2"}, {"type": "module", "id": "10"}]}
        assert entries[1] == {"path": [{"type": "space", "id": "2"}, {"type": "module", "id": "20"}]}

    def test_and_any_noop(self):
        """AND with any sub → any is no-op constraint."""
        cond = {
            "op": "and",
            "content": [
                {"op": "any"},
                {"field": "space.id", "op": "in", "value": ["2"]},
            ],
        }
        is_all, entries = _parse_permission_entries(cond, "space")
        assert is_all is False
        assert entries == [{"path": [{"type": "space", "id": "2"}]}]

    def test_and_only_any(self):
        cond = {
            "op": "and",
            "content": [
                {"op": "any"},
                {"op": "any"},
            ],
        }
        is_all, entries = _parse_permission_entries(cond, None)
        assert is_all is False
        assert entries == []

    def test_unknown_op(self):
        assert _parse_permission_entries({"op": "unknown"}, None) == (False, [])


# ============================================================================
# _parse_action_permissions
# ============================================================================


class TestParseActionPermissions:
    def _make_action(self, resource_type="space"):
        from bkmonitor.iam.action import ActionMeta

        return ActionMeta(
            id="test_action",
            name="测试",
            name_en="Test",
            type="view",
            version=1,
            related_resource_types=[{"id": resource_type}] if resource_type else [],
        )

    def test_all(self):
        action = self._make_action()
        gt, permissions, note = _parse_action_permissions(action, {"op": "any"})
        assert gt == "all"
        assert permissions == [{"path": []}]
        assert note is None

    def test_none_condition(self):
        action = self._make_action()
        gt, permissions, note = _parse_action_permissions(action, None)
        assert gt == "error"
        assert permissions == []
        assert note == "IAM 查询失败"

    def test_empty_condition(self):
        action = self._make_action()
        gt, permissions, note = _parse_action_permissions(action, {})
        assert gt == "none"
        assert permissions == []
        assert note is None

    def test_partial_space(self):
        action = self._make_action("space")
        gt, permissions, note = _parse_action_permissions(
            action, {"op": "in", "field": "space.id", "value": ["2", "5"]}
        )
        assert gt == "partial"
        assert len(permissions) == 2

    def test_partial_instance(self):
        action = self._make_action("apm_application")
        gt, permissions, note = _parse_action_permissions(
            action, {"op": "in", "field": "apm_application.id", "value": ["390"]}
        )
        assert gt == "partial"
        assert permissions[0]["path"][0]["type"] == "apm_application"


# ============================================================================
# _resolve_parent_paths
# ============================================================================

_MOCK_PARENT_SPACE_ID = "61"


class TestResolveParentPaths:
    @patch("kernel_api.rpc.functions.admin.permission._all_resources", new_callable=dict)
    def test_prepend_parent_space(self, mock_resources):
        from unittest.mock import MagicMock

        mock_cls = MagicMock()
        # 显式声明父资源类型（模拟 apm_application → space 的拓扑）
        mock_cls.parent_resource.id = "space"
        mock_cls.batch_get_parent.return_value = {"390": _MOCK_PARENT_SPACE_ID}
        mock_resources["apm_application"] = mock_cls

        permissions = [{"path": [{"type": "apm_application", "id": "390"}]}]
        _resolve_parent_paths(permissions)

        assert permissions[0]["path"] == [
            {"type": "space", "id": _MOCK_PARENT_SPACE_ID},
            {"type": "apm_application", "id": "390"},
        ]

    @patch("kernel_api.rpc.functions.admin.permission._all_resources", new_callable=dict)
    def test_skip_space_first(self, mock_resources):
        """Paths already starting with space are not modified."""
        mock_resources.clear()
        permissions = [{"path": [{"type": "space", "id": "2"}]}]
        _resolve_parent_paths(permissions)
        assert permissions[0]["path"] == [{"type": "space", "id": "2"}]

    @patch("kernel_api.rpc.functions.admin.permission._all_resources", new_callable=dict)
    def test_skip_empty_path(self, mock_resources):
        permissions = [{"path": []}]
        _resolve_parent_paths(permissions)
        assert permissions[0]["path"] == []

    @patch("kernel_api.rpc.functions.admin.permission._all_resources", new_callable=dict)
    def test_unknown_resource_type(self, mock_resources):
        mock_resources.clear()
        permissions = [{"path": [{"type": "unknown_rt", "id": "x"}]}]
        _resolve_parent_paths(permissions)
        # unchanged
        assert permissions[0]["path"] == [{"type": "unknown_rt", "id": "x"}]

    @patch("kernel_api.rpc.functions.admin.permission._all_resources", new_callable=dict)
    def test_parent_not_found(self, mock_resources):
        from unittest.mock import MagicMock

        mock_cls = MagicMock()
        mock_cls.batch_get_parent.return_value = {}
        mock_resources["grafana_dashboard"] = mock_cls

        permissions = [{"path": [{"type": "grafana_dashboard", "id": "14|missing"}]}]
        _resolve_parent_paths(permissions)
        # unchanged when parent not found
        assert len(permissions[0]["path"]) == 1


# ============================================================================
# _resolve_display_names
# ============================================================================


class TestResolveDisplayNames:
    @patch("kernel_api.rpc.functions.admin.permission._all_resources", new_callable=dict)
    def test_fills_display_names(self, mock_resources):
        from unittest.mock import MagicMock

        mock_space_cls = MagicMock()
        mock_space_cls.batch_get_display_names.return_value = {"2": "测试业务"}
        mock_resources["space"] = mock_space_cls

        permissions = [{"path": [{"type": "space", "id": "2"}]}]
        _resolve_display_names(permissions)

        assert permissions[0]["path"][0]["display_name"] == "测试业务"

    @patch("kernel_api.rpc.functions.admin.permission._all_resources", new_callable=dict)
    def test_empty_display_name(self, mock_resources):
        """Missing display_name → empty string."""
        from unittest.mock import MagicMock

        mock_cls = MagicMock()
        mock_cls.batch_get_display_names.return_value = {}
        mock_resources["space"] = mock_cls

        permissions = [{"path": [{"type": "space", "id": "2"}]}]
        _resolve_display_names(permissions)
        assert permissions[0]["path"][0]["display_name"] == ""

    @patch("kernel_api.rpc.functions.admin.permission._all_resources", new_callable=dict)
    def test_multiple_types(self, mock_resources):
        from unittest.mock import MagicMock

        mock_space = MagicMock()
        mock_space.batch_get_display_names.return_value = {"2": "业务"}
        mock_apm = MagicMock()
        mock_apm.batch_get_display_names.return_value = {"390": "my_app"}
        mock_resources["space"] = mock_space
        mock_resources["apm_application"] = mock_apm

        permissions = [
            {
                "path": [
                    {"type": "space", "id": "2"},
                    {"type": "apm_application", "id": "390"},
                ]
            }
        ]
        _resolve_display_names(permissions)

        path = permissions[0]["path"]
        assert path[0]["display_name"] == "业务"
        assert path[1]["display_name"] == "my_app"


# ============================================================================
# _get_resource_type
# ============================================================================


class TestGetResourceType:
    def test_space(self):
        from bkmonitor.iam.action import get_action_by_id

        assert _get_resource_type(get_action_by_id("view_business_v2")) == "space"

    def test_global(self):
        from bkmonitor.iam.action import get_action_by_id

        assert _get_resource_type(get_action_by_id("manage_global_setting")) is None

    def test_instance(self):
        from bkmonitor.iam.action import get_action_by_id

        assert _get_resource_type(get_action_by_id("view_single_dashboard")) == "grafana_dashboard"


# ============================================================================
# _build_action_result_item (v2)
# ============================================================================


class TestBuildActionResultItem:
    def _make_action(self, resource_type="space"):
        from bkmonitor.iam.action import ActionMeta

        return ActionMeta(
            id="test_action",
            name="测试",
            name_en="Test",
            type="view",
            version=1,
            related_resource_types=[{"id": resource_type}] if resource_type else [],
        )

    def test_all_permissions(self):
        action = self._make_action()
        item = _build_action_result_item(action, "all", [{"path": []}])
        assert item["grant_type"] == "all"
        assert item["permissions"] == [{"path": []}]
        assert "granted_space_ids" not in item
        assert "granted_instances" not in item

    def test_partial_permissions(self):
        action = self._make_action()
        perms = [{"path": [{"type": "space", "id": "2", "display_name": "test"}]}]
        item = _build_action_result_item(action, "partial", perms)
        assert item["grant_type"] == "partial"
        assert item["permissions"] == perms

    def test_with_note(self):
        action = self._make_action()
        item = _build_action_result_item(action, "error", [], note="IAM 查询失败")
        assert item["note"] == "IAM 查询失败"


# ============================================================================
# action_categories
# ============================================================================


class TestActionCategories:
    def test_returns_groups_and_index(self):
        result = action_categories({"bk_tenant_id": "system"})
        data = result["data"]
        assert "groups" in data
        assert "action_index" in data
        assert "resource_types" in data
        assert "business_groups" in data
        assert len(data["groups"]) > 0
        assert len(data["resource_types"]) > 0
        assert len(data["business_groups"]) > 0

        space_group = next((g for g in data["groups"] if g["resource_type"] == "space"), None)
        assert space_group is not None
        assert any(a["id"] == "view_business_v2" for a in space_group["actions"])
        # 分组增强字段
        assert space_group["name"] == "空间"
        assert space_group["is_top_level"] is True
        assert space_group["parent_resource_type"] is None
        assert space_group["action_count"] > 0

        global_group = next((g for g in data["groups"] if g["resource_type"] is None), None)
        assert global_group is not None
        assert any(a["id"] == "manage_global_setting" for a in global_group["actions"])
        # 全局分组增强字段
        assert global_group["name"] == "全局操作"
        assert global_group["is_top_level"] is True
        assert global_group["parent_resource_type"] is None

        # 非顶级资源分组
        apm_group = next((g for g in data["groups"] if g["resource_type"] == "apm_application"), None)
        if apm_group is not None:
            assert apm_group["is_top_level"] is False
            assert apm_group["parent_resource_type"] == "space"

        assert "view_business_v2" in data["action_index"]

        # 资源类型元数据
        space_rt = next((rt for rt in data["resource_types"] if rt["id"] == "space"), None)
        assert space_rt is not None
        assert space_rt["name"] == "空间"
        assert space_rt["is_top_level"] is True
        assert space_rt["parent_resource_type"] is None

        apm_rt = next((rt for rt in data["resource_types"] if rt["id"] == "apm_application"), None)
        if apm_rt is not None:
            assert apm_rt["is_top_level"] is False
            assert apm_rt["parent_resource_type"] == "space"

    def test_business_groups_structure(self):
        """验证 business_groups 结构完整性和分组覆盖性。"""
        from bkmonitor.iam.action import _all_actions

        result = action_categories({"bk_tenant_id": "system"})
        data = result["data"]
        business_groups = data["business_groups"]

        # 每个分组必须包含必要字段
        for group in business_groups:
            assert "name" in group
            assert "action_count" in group
            assert "actions" in group
            assert group["action_count"] == len(group["actions"])
            # 每个 action 必须包含必要字段
            for action in group["actions"]:
                assert "id" in action
                assert "name" in action
                assert "type" in action
                assert "resource_type" in action

        # 核心断言：business_groups 中的 action ID 集合必须与 _all_actions 完全一致
        grouped_action_ids = set()
        for group in business_groups:
            for action in group["actions"]:
                grouped_action_ids.add(action["id"])

        all_action_ids = set(_all_actions.keys())
        assert grouped_action_ids == all_action_ids, (
            f"分组覆盖不一致: 多出的={grouped_action_ids - all_action_ids}, "
            f"缺失的={all_action_ids - grouped_action_ids}"
        )

    def test_business_groups_known_categories(self):
        """验证已知业务分组的正确性。"""
        result = action_categories({"bk_tenant_id": "system"})
        business_groups = result["data"]["business_groups"]

        # 业务组应该存在
        group_names = [g["name"] for g in business_groups]
        assert "业务" in group_names
        assert "全局配置" in group_names
        assert "监控平台MCP" in group_names
        assert "分析定位" in group_names

        # 业务组应该包含 view_business_v2
        biz_group = next((g for g in business_groups if g["name"] == "业务"), None)
        assert biz_group is not None
        assert any(a["id"] == "view_business_v2" for a in biz_group["actions"])

        # 监控管理组应该包含策略操作
        mgmt_group = next((g for g in business_groups if g["name"] == "监控管理"), None)
        assert mgmt_group is not None
        assert any(a["id"] == "view_rule_v2" for a in mgmt_group["actions"])

        # 分析定位组应该包含仪表盘和故障相关操作
        analysis_group = next((g for g in business_groups if g["name"] == "分析定位"), None)
        assert analysis_group is not None
        assert any(a["id"] == "view_dashboard_v2" for a in analysis_group["actions"])
        assert any(a["id"] == "view_incident" for a in analysis_group["actions"])

    def test_business_groups_uncategorized_fallback(self):
        """验证 _all_actions 中未匹配硬编码分组的操作归入'其他'组。"""
        from bkmonitor.iam.action import _all_actions

        result = action_categories({"bk_tenant_id": "system"})
        business_groups = result["data"]["business_groups"]

        # 当前所有操作都已在 _ACTION_CATEGORY_MAP 中分组，"其他"组可能不存在
        other_group = next((g for g in business_groups if g["name"] == "其他"), None)
        if other_group is not None:
            for action in other_group["actions"]:
                assert action["id"] in _all_actions


# ============================================================================
# _batch_query_policies / _fallback_query_policies
# ============================================================================


class TestBatchQueryPolicies:
    def test_success(self):
        mock_iam = MagicMock()
        mock_iam._do_policy_query_by_actions.return_value = [
            {"action": {"id": "view_business_v2"}, "condition": {"op": "any"}},
            {"action": {"id": "manage_global_setting"}, "condition": None},
        ]

        from bkmonitor.iam.action import get_action_by_id

        actions = [get_action_by_id("view_business_v2"), get_action_by_id("manage_global_setting")]
        result = _batch_query_policies(mock_iam, actions, "testuser")
        assert result["view_business_v2"] == {"op": "any"}
        assert result["manage_global_setting"] is None


class TestFallbackQueryPolicies:
    def test_fallback(self):
        mock_iam = MagicMock()
        mock_iam._do_policy_query.return_value = {"op": "any"}

        from bkmonitor.iam.action import get_action_by_id

        action = get_action_by_id("view_business_v2")
        warnings = []
        result = _fallback_query_policies(mock_iam, [action], "testuser", warnings)
        assert result["view_business_v2"] == {"op": "any"}
        assert warnings == []

    def test_fallback_auth_error(self):
        mock_iam = MagicMock()
        mock_iam._do_policy_query.side_effect = AuthAPIError("test error")

        from bkmonitor.iam.action import get_action_by_id

        action = get_action_by_id("view_business_v2")
        warnings = []
        result = _fallback_query_policies(mock_iam, [action], "testuser", warnings)
        assert result["view_business_v2"] is None
        assert len(warnings) == 1
        assert warnings[0]["code"] == "IAM_QUERY_FAILED"


# ============================================================================
# query_user_permissions (v2 integration)
# ============================================================================


class TestQueryUserPermissions:
    def test_missing_username(self):
        with pytest.raises(CustomException, match="username"):
            query_user_permissions({"bk_tenant_id": "system"})

    @patch("kernel_api.rpc.functions.admin.permission._resolve_display_names")
    @patch("kernel_api.rpc.functions.admin.permission._resolve_parent_paths")
    @patch("kernel_api.rpc.functions.admin.permission.Permission")
    def test_batch_query_success(self, mock_perm_cls, mock_resolve_parents, mock_resolve_names):
        mock_iam = MagicMock()
        mock_iam._do_policy_query_by_actions.return_value = MOCK_POLICY_RESULTS
        mock_perm = MagicMock()
        mock_perm.skip_check = False
        mock_perm.iam_client = mock_iam
        mock_perm_cls.return_value = mock_perm

        result = query_user_permissions({"username": "testuser", "bk_tenant_id": "system"})
        data = result["data"]
        assert data["username"] == "testuser"

        # all → permissions = [{"path": []}]
        biz_action = next(a for a in data["actions"] if a["action_id"] == "view_business_v2")
        assert biz_action["grant_type"] == "all"
        assert biz_action["permissions"] == [{"path": []}]

        # partial space → 3 space entries
        explore = next(a for a in data["actions"] if a["action_id"] == "explore_metric_v2")
        assert explore["grant_type"] == "partial"
        assert len(explore["permissions"]) == 3

        # none → empty
        plugin = next(a for a in data["actions"] if a["action_id"] == "view_plugin_v2")
        assert plugin["grant_type"] == "none"
        assert plugin["permissions"] == []

        # error → note
        state = next(a for a in data["actions"] if a["action_id"] == "view_self_state")
        assert state["grant_type"] == "error"
        assert state["note"] == "IAM 查询失败"

        # global all
        setting = next(a for a in data["actions"] if a["action_id"] == "manage_global_setting")
        assert setting["grant_type"] == "all"

        # CompatibleIAM V1+V2 merge
        plugin_mgr = next(a for a in data["actions"] if a["action_id"] == "manage_public_plugin")
        assert plugin_mgr["grant_type"] == "all"

        # instance action parsed with entries
        apm = next(a for a in data["actions"] if a["action_id"] == "manage_apm_application_v2")
        assert apm["grant_type"] == "partial"
        assert len(apm["permissions"]) == 4  # 2 instance + 2 space

        assert data["summary"]["total_actions"] > 0

    @patch("kernel_api.rpc.functions.admin.permission._resolve_display_names")
    @patch("kernel_api.rpc.functions.admin.permission._resolve_parent_paths")
    @patch("kernel_api.rpc.functions.admin.permission.Permission")
    def test_batch_fallback_to_individual(self, mock_perm_cls, mock_resolve_parents, mock_resolve_names):
        mock_iam = MagicMock()
        mock_iam._do_policy_query_by_actions.side_effect = AuthAPIError("action.id invalid")
        mock_iam._do_policy_query.return_value = {"op": "any"}

        mock_perm = MagicMock()
        mock_perm.skip_check = False
        mock_perm.iam_client = mock_iam
        mock_perm_cls.return_value = mock_perm

        result = query_user_permissions({"username": "testuser", "bk_tenant_id": "system"})
        assert len(result.get("warnings", [])) >= 1
        assert result["warnings"][0]["code"] == "IAM_BATCH_FAILED"
