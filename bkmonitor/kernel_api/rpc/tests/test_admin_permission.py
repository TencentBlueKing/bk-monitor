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

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin.permission import (
    _build_action_result_item,
    _field_to_resource_type,
    _get_v3_type,
    _parse_action_permissions,
    _parse_expression_entries,
    _parse_iam_path,
    _enrich_permissions,
    action_categories,
    query_user_permissions,
)

# ============================================================================
# Helpers — 构造 ActionDef / ResourceTypeDef 测试数据
# ============================================================================

from bkmonitor.iam.iam_engine.schema.definitions import ActionDef, ResourceTypeDef
from bkmonitor.iam.iam_engine.policy.expression import Op, PolicyExpression


def _make_action_def(
    id: str,
    name: str = "测试操作",
    resource_type: str = "space",
    v3_type: str = "view",
    description: str = "",
) -> ActionDef:
    return ActionDef(
        id=id,
        name=name,
        resource_type=resource_type,
        description=description,
        extensions={"v3": {"type": v3_type}},
    )


def _make_global_action_def(id: str, v3_type: str = "view") -> ActionDef:
    return _make_action_def(id=id, resource_type="", v3_type=v3_type)


def _expr_any() -> PolicyExpression:
    return PolicyExpression.any()


def _expr_none() -> PolicyExpression:
    return PolicyExpression.none()


def _expr_in(field: str, values: list[str]) -> PolicyExpression:
    return PolicyExpression.leaf(Op.IN, field, tuple(values))


def _expr_eq(field: str, value: str) -> PolicyExpression:
    return PolicyExpression.leaf(Op.EQ, field, value)


def _expr_starts_with(field: str, value: str) -> PolicyExpression:
    return PolicyExpression.leaf(Op.STARTS_WITH, field, value)


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
# _parse_expression_entries (was _parse_permission_entries — now PolicyExpression-based)
# ============================================================================


class TestParseExpressionEntries:
    def test_none_expression(self):
        is_all, entries = _parse_expression_entries(None)
        assert is_all is False
        assert entries == []

    def test_any_expression(self):
        is_all, entries = _parse_expression_entries(_expr_any())
        assert is_all is True
        assert entries == []

    def test_none_op_expression(self):
        is_all, entries = _parse_expression_entries(_expr_none())
        assert is_all is False
        assert entries == []

    def test_in_space_id(self):
        expr = _expr_in("space.id", ["2", "5"])
        is_all, entries = _parse_expression_entries(expr)
        assert is_all is False
        assert len(entries) == 2
        assert entries[0] == {"path": [{"type": "space", "id": "2"}]}
        assert entries[1] == {"path": [{"type": "space", "id": "5"}]}

    def test_in_instance_id(self):
        expr = _expr_in("apm_application.id", ["390", "405"])
        is_all, entries = _parse_expression_entries(expr)
        assert is_all is False
        assert len(entries) == 2
        assert entries[0]["path"][0] == {"type": "apm_application", "id": "390"}

    def test_in_empty_values(self):
        expr = PolicyExpression.leaf(Op.IN, "space.id", ())
        is_all, entries = _parse_expression_entries(expr)
        assert is_all is False
        assert entries == []

    def test_eq(self):
        expr = _expr_eq("space.id", "2")
        is_all, entries = _parse_expression_entries(expr)
        assert is_all is False
        assert entries == [{"path": [{"type": "space", "id": "2"}]}]

    def test_eq_empty_value(self):
        expr = PolicyExpression.leaf(Op.EQ, "space.id", "")
        is_all, entries = _parse_expression_entries(expr)
        assert is_all is False
        assert entries == []

    def test_starts_with(self):
        expr = _expr_starts_with("grafana_dashboard._bk_iam_path_", "/space,2/")
        is_all, entries = _parse_expression_entries(expr)
        assert is_all is False
        assert entries == [{"path": [{"type": "space", "id": "2"}]}]

    def test_starts_with_empty(self):
        expr = _expr_starts_with("grafana_dashboard._bk_iam_path_", "")
        is_all, entries = _parse_expression_entries(expr)
        assert is_all is False
        assert entries == []

    def test_or_combines(self):
        expr = PolicyExpression.or_(
            _expr_in("space.id", ["2", "5"]),
            _expr_eq("space.id", "10"),
        )
        is_all, entries = _parse_expression_entries(expr)
        assert is_all is False
        assert len(entries) == 3
        ids = {e["path"][0]["id"] for e in entries}
        assert ids == {"2", "5", "10"}

    def test_or_with_any_sub(self):
        expr = PolicyExpression.or_(
            _expr_in("space.id", ["2"]),
            _expr_any(),
        )
        is_all, entries = _parse_expression_entries(expr)
        assert is_all is True
        assert entries == []

    def test_or_nested_with_starts_with(self):
        """Real pattern: OR(in(id), OR(starts_with, ...))."""
        expr = PolicyExpression.or_(
            _expr_in("apm_application.id", ["390", "405"]),
            PolicyExpression.or_(
                _expr_starts_with("apm_application._bk_iam_path_", "/space,61/"),
                _expr_starts_with("apm_application._bk_iam_path_", "/space,60/"),
            ),
        )
        is_all, entries = _parse_expression_entries(expr)
        assert is_all is False
        assert len(entries) == 4
        types = {(e["path"][0]["type"], e["path"][0]["id"]) for e in entries}
        assert ("apm_application", "390") in types
        assert ("apm_application", "405") in types
        assert ("space", "61") in types
        assert ("space", "60") in types

    def test_and_cartesian(self):
        """AND with prefix (starts_with) and leaf (in)."""
        expr = PolicyExpression.and_(
            _expr_starts_with("module._bk_iam_path_", "/space,2/"),
            _expr_in("module.id", ["10", "20"]),
        )
        is_all, entries = _parse_expression_entries(expr)
        assert is_all is False
        assert len(entries) == 2
        assert entries[0] == {"path": [{"type": "space", "id": "2"}, {"type": "module", "id": "10"}]}
        assert entries[1] == {"path": [{"type": "space", "id": "2"}, {"type": "module", "id": "20"}]}

    def test_and_any_noop(self):
        """AND with any sub → any is no-op and gets skipped."""
        expr = PolicyExpression.and_(
            _expr_any(),
            _expr_in("space.id", ["2"]),
        )
        is_all, entries = _parse_expression_entries(expr)
        assert is_all is False
        assert entries == [{"path": [{"type": "space", "id": "2"}]}]

    def test_and_only_any(self):
        """AND with only any children → all skipped, result empty."""
        expr = PolicyExpression.and_(_expr_any(), _expr_any())
        is_all, entries = _parse_expression_entries(expr)
        assert is_all is False
        assert entries == []


# ============================================================================
# _parse_action_permissions
# ============================================================================


class TestParseActionPermissions:
    def test_all(self):
        action = _make_action_def("test_action")
        gt, permissions, note = _parse_action_permissions(action, _expr_any())
        assert gt == "all"
        assert permissions == [{"path": []}]
        assert note is None

    def test_none_expression(self):
        action = _make_action_def("test_action")
        gt, permissions, note = _parse_action_permissions(action, None)
        assert gt == "error"
        assert permissions == []
        assert note == "IAM 查询失败"

    def test_none_op_expression(self):
        action = _make_action_def("test_action")
        gt, permissions, note = _parse_action_permissions(action, _expr_none())
        assert gt == "none"
        assert permissions == []
        assert note is None

    def test_partial_space(self):
        action = _make_action_def("test_action", resource_type="space")
        gt, permissions, note = _parse_action_permissions(action, _expr_in("space.id", ["2", "5"]))
        assert gt == "partial"
        assert len(permissions) == 2

    def test_partial_instance(self):
        action = _make_action_def("test_action", resource_type="apm_application")
        gt, permissions, note = _parse_action_permissions(action, _expr_in("apm_application.id", ["390"]))
        assert gt == "partial"
        assert permissions[0]["path"][0]["type"] == "apm_application"


# ============================================================================
# _enrich_permissions（两阶段补全：父路径 + 展示名，经 catalog 批量查询）
# ============================================================================


class TestEnrichPermissions:
    def _make_schema_mock(self, rt_map: dict[str, ResourceTypeDef]) -> MagicMock:
        """Build a SchemaRegistry mock with given resource types."""
        schema = MagicMock()
        schema.get_resource_type.side_effect = lambda rt: rt_map[rt]
        schema.has_resource_type.side_effect = lambda rt: rt in rt_map
        return schema

    @staticmethod
    def _actions(permissions: list[dict]) -> list[dict]:
        return [{"permissions": permissions}]

    @patch("bkmonitor.iam.adapters.catalog.fetch_instance_info")
    def test_prepend_parent_chain(self, mock_fetch):
        """实例级 entry 按 catalog 返回的父链前置补齐空间节点。"""

        def fake_fetch(rt_id, ids, requires, bk_tenant_id="system"):
            if requires == ["_bk_iam_path_"]:
                return [{"id": i, "_bk_iam_path_": f"/space,61/{rt_id},{i}/"} for i in ids]
            return []

        mock_fetch.side_effect = fake_fetch

        schema = self._make_schema_mock(
            {
                "apm_application": ResourceTypeDef(id="apm_application", name="APM应用", ancestor="space"),
                "space": ResourceTypeDef(id="space", name="空间"),
            }
        )

        actions = self._actions([{"path": [{"type": "apm_application", "id": "390"}]}])
        failed = _enrich_permissions(actions, schema)

        assert failed == 0
        assert actions[0]["permissions"][0]["path"] == [
            {"type": "space", "id": "61", "display_name": ""},
            {"type": "apm_application", "id": "390", "display_name": ""},
        ]

    @patch("bkmonitor.iam.adapters.catalog.fetch_instance_info")
    def test_skip_space_first(self, mock_fetch):
        """顶级资源开头的 path 不做父链查询（仅展示名阶段）。"""
        schema = self._make_schema_mock({"space": ResourceTypeDef(id="space", name="空间")})
        actions = self._actions([{"path": [{"type": "space", "id": "2"}]}])
        _enrich_permissions(actions, schema)
        assert actions[0]["permissions"][0]["path"] == [{"type": "space", "id": "2", "display_name": ""}]
        assert all(call.kwargs.get("requires") != ["_bk_iam_path_"] for call in mock_fetch.call_args_list)

    def test_skip_empty_path(self):
        schema = MagicMock()
        actions = self._actions([{"path": []}])
        _enrich_permissions(actions, schema)
        assert actions[0]["permissions"][0]["path"] == []

    @patch("bkmonitor.iam.adapters.catalog.fetch_instance_info", return_value=[])
    def test_unknown_resource_type(self, mock_fetch):
        """Unknown resource type — silently skipped（展示名回填空串）。"""
        schema = self._make_schema_mock({})
        actions = self._actions([{"path": [{"type": "unknown_rt", "id": "x"}]}])
        _enrich_permissions(actions, schema)
        assert actions[0]["permissions"][0]["path"] == [{"type": "unknown_rt", "id": "x", "display_name": ""}]

    @patch("bkmonitor.iam.adapters.catalog.fetch_instance_info", return_value=[])
    def test_parent_not_found(self, mock_fetch):
        """父链查不到 → 保持原样，不补父节点。"""
        schema = self._make_schema_mock(
            {
                "grafana_dashboard": ResourceTypeDef(id="grafana_dashboard", name="仪表盘", ancestor="space"),
                "space": ResourceTypeDef(id="space", name="空间"),
            }
        )
        actions = self._actions([{"path": [{"type": "grafana_dashboard", "id": "14|missing"}]}])
        _enrich_permissions(actions, schema)
        assert actions[0]["permissions"][0]["path"] == [
            {"type": "grafana_dashboard", "id": "14|missing", "display_name": ""}
        ]

    @patch("bkmonitor.iam.adapters.catalog.fetch_instance_info")
    def test_fills_display_names(self, mock_fetch):
        """展示名按 rt 批量回填；apm/rum 取 name（app_name）口径。"""

        def fake_fetch(rt_id, ids, requires, bk_tenant_id="system"):
            if requires == ["_bk_iam_path_"]:
                return []
            if rt_id == "space":
                return [{"id": i, "display_name": f"业务-{i}"} for i in ids]
            return [{"id": i, "display_name": f"alias-{i}", "name": f"app-{i}"} for i in ids]

        mock_fetch.side_effect = fake_fetch

        schema = self._make_schema_mock(
            {
                "apm_application": ResourceTypeDef(id="apm_application", name="APM应用", ancestor="space"),
                "space": ResourceTypeDef(id="space", name="空间"),
            }
        )
        actions = self._actions(
            [
                {
                    "path": [
                        {"type": "space", "id": "2"},
                        {"type": "apm_application", "id": "390"},
                    ]
                }
            ]
        )
        _enrich_permissions(actions, schema)

        path = actions[0]["permissions"][0]["path"]
        assert path[0]["display_name"] == "业务-2"
        assert path[1]["display_name"] == "app-390"

    @patch("bkmonitor.iam.adapters.catalog.fetch_instance_info", return_value=[])
    def test_catalog_queried_once_per_rt(self, mock_fetch):
        """两阶段补全：每个 rt 最多 2 次 catalog 查询（父链 + 展示名），与 entry 数无关。"""
        schema = self._make_schema_mock(
            {
                "apm_application": ResourceTypeDef(id="apm_application", name="APM应用", ancestor="space"),
                "space": ResourceTypeDef(id="space", name="空间"),
            }
        )
        permissions = [{"path": [{"type": "apm_application", "id": str(390 + i)}]} for i in range(10)]
        _enrich_permissions(self._actions(permissions), schema)

        apm_calls = [c for c in mock_fetch.call_args_list if c.args[0] == "apm_application"]
        assert len(apm_calls) == 2

    @patch("bkmonitor.iam.adapters.catalog.fetch_instance_info")
    def test_catalog_failure_counts_resolve_failed(self, mock_fetch):
        """catalog 查询失败 → 记 resolve_failed，权限数据本身保留且不补 display_name。"""
        mock_fetch.side_effect = RuntimeError("db down")
        schema = self._make_schema_mock(
            {
                "apm_application": ResourceTypeDef(id="apm_application", name="APM应用", ancestor="space"),
                "space": ResourceTypeDef(id="space", name="空间"),
            }
        )
        actions = self._actions([{"path": [{"type": "apm_application", "id": "390"}]}])
        failed = _enrich_permissions(actions, schema)
        assert failed > 0
        assert actions[0]["permissions"][0]["path"] == [{"type": "apm_application", "id": "390"}]


# ============================================================================
# _get_v3_type
# ============================================================================


class TestGetV3Type:
    def test_view_type(self):
        action = _make_action_def("test", v3_type="view")
        assert _get_v3_type(action) == "view"

    def test_manage_type(self):
        action = _make_action_def("test", v3_type="manage")
        assert _get_v3_type(action) == "manage"

    def test_no_v3_extension(self):
        action = ActionDef(id="test", name="Test")
        assert _get_v3_type(action) == ""


# ============================================================================
# _build_action_result_item
# ============================================================================


class TestBuildActionResultItem:
    def test_all_permissions(self):
        action = _make_action_def("test_action")
        item = _build_action_result_item(action, "all", [{"path": []}])
        assert item["grant_type"] == "all"
        assert item["permissions"] == [{"path": []}]
        assert "note" not in item
        assert item["type"] == "view"

    def test_partial_permissions(self):
        action = _make_action_def("test_action")
        perms = [{"path": [{"type": "space", "id": "2", "display_name": "test"}]}]
        item = _build_action_result_item(action, "partial", perms)
        assert item["grant_type"] == "partial"
        assert item["permissions"] == perms

    def test_with_note(self):
        action = _make_action_def("test_action")
        item = _build_action_result_item(action, "error", [], note="IAM 查询失败")
        assert item["note"] == "IAM 查询失败"

    def test_global_action(self):
        action = _make_global_action_def("manage_global_setting", v3_type="manage")
        item = _build_action_result_item(action, "all", [{"path": []}])
        assert item["resource_type"] is None
        assert item["type"] == "manage"


# ============================================================================
# action_categories
# ============================================================================


class TestActionCategories:
    def test_returns_groups_and_index(self):
        """action_categories 直接走真实 SchemaRegistry，验证结构和 Business ID。"""
        result = action_categories({"bk_tenant_id": "system"})
        data = result["data"]
        assert "groups" in data
        assert "action_index" in data
        assert "resource_types" in data
        assert "business_groups" in data
        assert len(data["groups"]) > 0
        assert len(data["resource_types"]) > 0
        assert len(data["business_groups"]) > 0

        # 空间分组 — 使用 Business ID
        space_group = next((g for g in data["groups"] if g["resource_type"] == "space"), None)
        assert space_group is not None
        assert any(a["id"] == "view_business" for a in space_group["actions"])
        assert space_group["name"] == "空间"
        assert space_group["is_top_level"] is True
        assert space_group["parent_resource_type"] is None
        assert space_group["action_count"] > 0

        # 全局分组
        global_group = next((g for g in data["groups"] if g["resource_type"] is None), None)
        assert global_group is not None
        assert any(a["id"] == "manage_global_setting" for a in global_group["actions"])
        assert global_group["name"] == "全局操作"
        assert global_group["is_top_level"] is True
        assert global_group["parent_resource_type"] is None

        # 非顶级资源分组
        apm_group = next((g for g in data["groups"] if g["resource_type"] == "apm_application"), None)
        if apm_group is not None:
            assert apm_group["is_top_level"] is False
            assert apm_group["parent_resource_type"] == "space"

        # action_index 使用 Business ID
        assert "view_business" in data["action_index"]

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
        """验证 business_groups 覆盖所有 schema.all_actions()。"""
        from bkmonitor.iam.iam_engine.django.facade import get_framework

        fw = get_framework()
        all_ids = {a.id for a in fw.schema.all_actions()}

        result = action_categories({"bk_tenant_id": "system"})
        data = result["data"]
        business_groups = data["business_groups"]

        for group in business_groups:
            assert "name" in group
            assert "action_count" in group
            assert "actions" in group
            assert group["action_count"] == len(group["actions"])
            for action in group["actions"]:
                assert "id" in action
                assert "name" in action
                assert "type" in action
                assert "resource_type" in action

        grouped_ids = set()
        for group in business_groups:
            for action in group["actions"]:
                grouped_ids.add(action["id"])

        assert grouped_ids == all_ids, f"分组覆盖不一致: 多出的={grouped_ids - all_ids}, 缺失的={all_ids - grouped_ids}"

    def test_business_groups_known_categories(self):
        """验证已知业务分组使用 Business ID。"""
        result = action_categories({"bk_tenant_id": "system"})
        business_groups = result["data"]["business_groups"]

        group_names = [g["name"] for g in business_groups]
        assert "业务" in group_names
        assert "全局配置" in group_names
        assert "监控平台MCP" in group_names
        assert "分析定位" in group_names

        # 业务组包含 view_business（Business ID）
        biz_group = next((g for g in business_groups if g["name"] == "业务"), None)
        assert biz_group is not None
        assert any(a["id"] == "view_business" for a in biz_group["actions"])

        # 监控管理组包含策略操作（Business ID）
        mgmt_group = next((g for g in business_groups if g["name"] == "监控管理"), None)
        assert mgmt_group is not None
        assert any(a["id"] == "view_rule" for a in mgmt_group["actions"])

        # 分析定位组
        analysis_group = next((g for g in business_groups if g["name"] == "分析定位"), None)
        assert analysis_group is not None
        assert any(a["id"] == "view_dashboard" for a in analysis_group["actions"])
        assert any(a["id"] == "view_incident" for a in analysis_group["actions"])

    @staticmethod
    def _mock_backend_fw(provider_name: str, codec):
        """构造 mock 框架：schema 用真实注册表，backend 解析返回 mock provider。"""
        from bkmonitor.iam.iam_engine.django.facade import get_framework as real_get_fw

        provider = MagicMock()
        provider.name = provider_name
        provider.codec = codec
        mock_fw = MagicMock()
        mock_fw.schema = real_get_fw().schema
        mock_fw.get_provider.return_value = provider
        return mock_fw

    @patch("kernel_api.rpc.functions.admin.permission._shared.get_framework")
    def test_backend_v4_filters_hidden_actions(self, mock_get_fw):
        """backend=v4：exclude_providers=("v4",) 的过时 action 不出现在元数据中。"""
        from bkmonitor.iam.adapters.v4.codec import MonitorV4Codec

        mock_get_fw.return_value = self._mock_backend_fw("v4", MonitorV4Codec())
        result = action_categories({"bk_tenant_id": "system", "backend": "v4"})
        data = result["data"]
        ids = {a["id"] for g in data["groups"] for a in g["actions"]}
        assert "view_dashboard" not in ids
        assert "manage_dashboard" not in ids
        assert "view_single_dashboard" in ids
        assert "view_dashboard" not in data["action_index"]
        assert "view_single_dashboard" in data["action_index"]

    @patch("kernel_api.rpc.functions.admin.permission._shared.get_framework")
    def test_backend_v3_returns_dialect_ids(self, mock_get_fw):
        """backend=v3：过时 action 仍可见，id 经 v3 codec 输出方言 ID（与权限查询口径一致）。"""
        from bkmonitor.iam.adapters.v3.codec import MonitorV3Codec

        mock_get_fw.return_value = self._mock_backend_fw("v3", MonitorV3Codec())
        result = action_categories({"bk_tenant_id": "system", "backend": "v3"})
        ids = {a["id"] for g in result["data"]["groups"] for a in g["actions"]}
        assert "view_dashboard_v2" in ids
        assert "view_business_v2" in ids
        # 业务 ID 不再出现在 v3 口径的元数据中
        assert "view_business" not in ids
        assert "view_business_v2" in result["data"]["action_index"]

    @patch("kernel_api.rpc.functions.admin.permission._shared.get_framework")
    def test_backend_unknown_provider(self, mock_get_fw):
        """backend 对应 provider 未装配 → 明确报错（不再硬编码版本清单）。"""
        from bkmonitor.iam.iam_engine.core.exceptions import ProviderNotFound

        mock_fw = MagicMock()
        mock_fw.get_provider.side_effect = ProviderNotFound("provider 'v5' not found")
        mock_get_fw.return_value = mock_fw

        with pytest.raises(CustomException, match="未装配"):
            action_categories({"bk_tenant_id": "system", "backend": "v5"})

    def test_business_groups_uncategorized_fallback(self):
        """验证未匹配硬编码分组的操作归入'其他'组并不丢失。"""
        from bkmonitor.iam.iam_engine.django.facade import get_framework

        fw = get_framework()
        all_ids = {a.id for a in fw.schema.all_actions()}

        result = action_categories({"bk_tenant_id": "system"})
        business_groups = result["data"]["business_groups"]

        other_group = next((g for g in business_groups if g["name"] == "其他"), None)
        if other_group is not None:
            for action in other_group["actions"]:
                assert action["id"] in all_ids


# ============================================================================
# query_user_permissions
# ============================================================================


class TestQueryUserPermissions:
    def test_missing_username(self):
        with pytest.raises(CustomException, match="username"):
            query_user_permissions({"bk_tenant_id": "system"})

    @patch("kernel_api.rpc.functions.admin.permission._v3._enrich_permissions", return_value=0)
    @patch("kernel_api.rpc.functions.admin.permission._v3.get_framework")
    def test_batch_query_success(self, mock_get_fw, mock_enrich):
        """验证 query_user_permissions 通过 v3 provider 查询策略的完整流程。"""
        from bkmonitor.iam.iam_engine.django.facade import get_framework as real_get_fw

        real_schema = real_get_fw().schema

        # 构造 PolicyExpression → action_id 映射（Business ID，单 provider 单表达式）
        policies = {
            # all space
            "view_business": _expr_any(),
            # partial space
            "explore_metric": _expr_in("space.id", ["2", "-3", "3"]),
            # none space
            "view_plugin": _expr_none(),
            # none instance
            "view_apm_application": _expr_none(),
            # partial instance with nested OR
            "manage_apm_application": PolicyExpression.or_(
                _expr_in("apm_application.id", ["390", "405"]),
                PolicyExpression.or_(
                    _expr_starts_with("apm_application._bk_iam_path_", "/space,61/"),
                    _expr_starts_with("apm_application._bk_iam_path_", "/space,60/"),
                ),
            ),
            # all global
            "manage_global_setting": _expr_any(),
            # none global（None → 无权限，非查询失败）
            "view_self_state": None,
            # V1+V2 merge — both any
            "manage_public_plugin": PolicyExpression.or_(_expr_any(), _expr_any()),
            # partial grafana
            "view_single_dashboard": PolicyExpression.or_(
                _expr_in("grafana_dashboard.id", ["14|f0ImroNIz", "14|nKviroNIz"]),
                PolicyExpression.or_(
                    _expr_starts_with("grafana_dashboard._bk_iam_path_", "/space,2/"),
                    _expr_starts_with("grafana_dashboard._bk_iam_path_", "/space,-6/"),
                ),
            ),
        }
        # 补齐所有 action（不在 policies 中的 action 返回 None）
        all_ids = {a.id for a in real_schema.all_actions()}
        for aid in all_ids:
            policies.setdefault(aid, None)

        # 直接构造真实 v3 codec（与框架装配状态无关），
        # 使 action_id 方言编码（USE_DIALECT_ACTION_ID）走真实逻辑
        from bkmonitor.iam.adapters.v3.codec import MonitorV3Codec

        mock_v3 = MagicMock()
        mock_v3.codec = MonitorV3Codec()
        mock_v3.query_policy_by_actions.return_value = policies

        mock_fw = MagicMock()
        mock_fw.schema = real_schema
        mock_fw.get_provider.return_value = mock_v3
        mock_get_fw.return_value = mock_fw

        result = query_user_permissions({"username": "testuser", "bk_tenant_id": "system"})
        data = result["data"]
        assert data["username"] == "testuser"

        # 对外 action_id 为 V3 方言 ID（如 view_business_v2），用真实 codec 编码断言
        codec = MonitorV3Codec()

        # all → permissions = [{"path": []}]
        biz_action = next(a for a in data["actions"] if a["action_id"] == codec.encode_action("view_business"))
        assert biz_action["grant_type"] == "all"
        assert biz_action["permissions"] == [{"path": []}]

        # partial space → 3 space entries
        explore = next(a for a in data["actions"] if a["action_id"] == codec.encode_action("explore_metric"))
        assert explore["grant_type"] == "partial"
        assert len(explore["permissions"]) == 3

        # none → empty
        plugin = next(a for a in data["actions"] if a["action_id"] == codec.encode_action("view_plugin"))
        assert plugin["grant_type"] == "none"
        assert plugin["permissions"] == []

        # none（expr 为 None 时兜底为无权限；error 仅由 failed_action_ids 查询失败产生）
        state = next(a for a in data["actions"] if a["action_id"] == codec.encode_action("view_self_state"))
        assert state["grant_type"] == "none"
        assert state["permissions"] == []

        # global all
        setting = next(a for a in data["actions"] if a["action_id"] == codec.encode_action("manage_global_setting"))
        assert setting["grant_type"] == "all"

        # CompatibleIAM V1+V2 merge 等价
        plugin_mgr = next(a for a in data["actions"] if a["action_id"] == codec.encode_action("manage_public_plugin"))
        assert plugin_mgr["grant_type"] == "all"

        # instance action parsed with entries
        apm = next(a for a in data["actions"] if a["action_id"] == codec.encode_action("manage_apm_application"))
        assert apm["grant_type"] == "partial"
        assert len(apm["permissions"]) == 4

        assert data["summary"]["total_actions"] > 0

    @patch("kernel_api.rpc.functions.admin.permission._v3._enrich_permissions", return_value=0)
    @patch("kernel_api.rpc.functions.admin.permission._v3.get_framework")
    def test_framework_query_failure_fallback(self, mock_get_fw, mock_enrich):
        """批量查询失败时降级为逐条查询；逐条也失败时全部 error 且 warning 含 action_id。"""
        from bkmonitor.iam.iam_engine.django.facade import get_framework as real_get_fw

        real_schema = real_get_fw().schema
        all_ids = {a.id for a in real_schema.all_actions()}

        mock_v3 = MagicMock()
        mock_v3.query_policy_by_actions.side_effect = RuntimeError("connection failed")
        mock_v3.query_policy.side_effect = RuntimeError("per-action connection failed")

        mock_fw = MagicMock()
        mock_fw.schema = real_schema
        mock_fw.get_provider.return_value = mock_v3
        mock_get_fw.return_value = mock_fw

        result = query_user_permissions({"username": "testuser", "bk_tenant_id": "system"})
        warnings = result.get("warnings", [])
        assert warnings[0]["code"] == "IAM_BATCH_FAILED"

        # 每条失败的 action 都有独立的 warning，且包含 action_id 与错误详情
        failed_warnings = [w for w in warnings if w["code"] == "IAM_QUERY_FAILED"]
        assert len(failed_warnings) == len(all_ids)
        assert {w["details"]["action_id"] for w in failed_warnings} == all_ids
        assert all("per-action" in str(w["details"]["error"]) for w in failed_warnings)

        # 所有 action 标记为 error
        for action in result["data"]["actions"]:
            assert action["grant_type"] == "error"

    @patch("kernel_api.rpc.functions.admin.permission._v3._enrich_permissions", return_value=0)
    @patch("kernel_api.rpc.functions.admin.permission._v3.get_framework")
    def test_batch_failure_fallback_partial_success(self, mock_get_fw, mock_enrich):
        """批量失败 + 逐条部分成功：成功的 action 正常解析，失败的标 error。"""
        from bkmonitor.iam.iam_engine.django.facade import get_framework as real_get_fw

        real_schema = real_get_fw().schema

        def fake_query_policies(subject, aid):
            if aid == "view_business":
                return PolicyExpression.any()
            raise RuntimeError(f"query failed for {aid}")

        # 直接构造真实 v3 codec（与框架装配状态无关），
        # 使 action_id 方言编码（USE_DIALECT_ACTION_ID）走真实逻辑
        from bkmonitor.iam.adapters.v3.codec import MonitorV3Codec

        mock_v3 = MagicMock()
        mock_v3.codec = MonitorV3Codec()
        mock_v3.query_policy_by_actions.side_effect = RuntimeError("batch connection failed")
        mock_v3.query_policy.side_effect = fake_query_policies

        mock_fw = MagicMock()
        mock_fw.schema = real_schema
        mock_fw.get_provider.return_value = mock_v3
        mock_get_fw.return_value = mock_fw

        result = query_user_permissions({"username": "testuser", "bk_tenant_id": "system"})
        data = result["data"]
        codec = MonitorV3Codec()

        # 成功的 action 正常解析（action_id 为方言 ID）
        biz_action = next(a for a in data["actions"] if a["action_id"] == codec.encode_action("view_business"))
        assert biz_action["grant_type"] == "all"

        # 失败的 action 标 error
        failed_action = next(a for a in data["actions"] if a["action_id"] != codec.encode_action("view_business"))
        assert failed_action["grant_type"] == "error"

        warnings = result.get("warnings", [])
        assert warnings[0]["code"] == "IAM_BATCH_FAILED"
        failed_warnings = [w for w in warnings if w["code"] == "IAM_QUERY_FAILED"]
        assert len(failed_warnings) == len(data["actions"]) - 1
        # warning 里的 action_id 是业务 ID；成功的 view_business 不应出现在失败列表里
        failed_biz_ids = {w["details"]["action_id"] for w in failed_warnings}
        assert "view_business" not in failed_biz_ids
        assert all("query failed for" in str(w["details"]["error"]) for w in failed_warnings)

    @patch("kernel_api.rpc.functions.admin.permission._v3.get_framework")
    def test_v3_provider_missing_raises(self, mock_get_fw):
        """v3 provider 未配置 → 显式报错，不再静默返回全 none。"""
        from bkmonitor.iam.iam_engine.core.exceptions import ProviderNotFound

        mock_fw = MagicMock()
        mock_fw.get_provider.side_effect = ProviderNotFound("provider 'v3' not found")
        mock_get_fw.return_value = mock_fw

        with pytest.raises(CustomException, match="未配置 v3 provider"):
            query_user_permissions({"username": "testuser", "bk_tenant_id": "system"})


# ==============================================================================
# 真实 IAM 框架集成测试 — 连接真实 V3 IAM 服务器查询用户权限
# ==============================================================================


@pytest.mark.skipif(
    not __import__("django").conf.settings.BK_IAM_APP_CODE,
    reason="IAM 未配置（BK_IAM_APP_CODE 为空）",
)
class TestRealFrameworkQuery:
    """连接真实 IAM v3 服务器，调用 query_user_permissions 获取实际权限数据。"""

    @pytest.mark.django_db(databases=["default", "monitor_api", "bk_dataview"])
    def test_query_real_user_permissions(self):
        """
        调用 query_user_permissions 查询真实用户的 IAM 权限。

        环境变量：
          IAM_TEST_USER     — 测试用户名（默认 "admin"）
          IAM_TENANT_ID     — 租户 ID（默认 "system"）

        断言：
          - 返回结构正确（username / bk_tenant_id / actions / summary）
          - actions 为非空列表
          - 每个 action 含 action_id / grant_type / permissions 字段
          - summary 含 total_actions / granted_actions
        """
        username = __import__("os").environ.get("IAM_TEST_USER", "admin")
        tenant_id = __import__("os").environ.get("IAM_TENANT_ID", "system")

        result = query_user_permissions({"username": username, "bk_tenant_id": tenant_id})

        # ---- 顶层结构 ----
        assert "data" in result, f"返回缺少 data 字段: {list(result.keys())}"
        data = result["data"]

        assert data["username"] == username
        assert "bk_tenant_id" in data
        assert "actions" in data
        assert "summary" in data

        actions = data["actions"]
        assert isinstance(actions, list)
        assert len(actions) > 0, f"actions 不应为空，实际 {len(actions)} 条"

        # ---- 每条 action 的结构 ----
        for action in actions:
            assert "action_id" in action, f"action 缺少 action_id: {action}"
            assert "grant_type" in action, f"action {action['action_id']} 缺少 grant_type"
            assert "permissions" in action, f"action {action['action_id']} 缺少 permissions"
            assert action["grant_type"] in ("all", "partial", "none", "error"), (
                f"无效的 grant_type: {action['grant_type']}"
            )

        # ---- summary ----
        summary = data["summary"]
        assert "total_actions" in summary
        assert "granted_actions" in summary
        assert summary["total_actions"] == len(actions)

        # ---- 将 query_user_permissions 的完整返回值落盘，供人工核对数据结构 ----
        import json

        # diag_path = _os.path.join(_os.path.dirname(__file__), "new_version_v3.json")
        diag_path = r"/Users/xuchaoshan/code-project/bk-monitor-admin/public/v3_permission.json"
        with open(diag_path, "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
