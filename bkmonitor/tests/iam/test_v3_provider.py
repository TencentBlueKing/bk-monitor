"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ==============================================================================
# V3PermissionProvider 单元测试（mock CompatibleIAM，无需真实 IAM 平台）
#
# 覆盖：
#   1. 从 options 构造，验证 schema/codec/config/client 正确初始化
#   2. 方言方法：读/写走不同缓存策略
#   3. 方言方法：batch 调用正确的 SDK API
#   4. 方言方法：get_apply_url / get_apply_data
#   5. health_check / plan_migration / apply_migration
# ==============================================================================

from unittest.mock import MagicMock

from iam import Request
from iam.exceptions import AuthAPIError

from bkmonitor.iam.iam_engine.core.types import (
    Subject as CoreSubject,
)
from bkmonitor.iam.iam_engine.provider.dialect_types import (
    DialectApplyURLRequest,
    DialectAuthRequest,
    DialectBatchByActionRequest,
    DialectBatchByResourceRequest,
    DialectResource,
)
from bkmonitor.iam.iam_engine.schema.definitions import ActionDef, ResourceTypeDef
from bkmonitor.iam.iam_engine.schema.registry import SchemaRegistry
from bkmonitor.iam.adapters.v3.codec import MonitorV3Codec
from bkmonitor.iam.iam_v3.provider import V3PermissionProvider


def _valid_options() -> dict:
    return {
        "codec_class": "bkmonitor.iam.adapters.v3.codec.MonitorV3Codec",
        "codec_kwargs": {
            "action_id_map": {
                "view_business": "view_business_v2",
                "manage_synthetic": "manage_synthetic_v2",
            },
            "action_types": {
                "view_business": "view",
                "manage_synthetic": "manage",
                "using_dashboard_mcp": "view",
                "manage_global_setting": "manage",
            },
        },
        "base_url": "https://iam.example.com",
        "credentials": {"app_code": "test_app", "app_secret": "test_secret"},
        "system": {"id": "bk_monitorv3", "name": "监控平台"},
        "bk_tenant_id": "default",
        "chunk_size": 8,
        "max_workers": 1,
    }


def _build_test_schema() -> SchemaRegistry:
    """构建包含测试数据的冻结 SchemaRegistry。"""
    schema = SchemaRegistry()
    schema.register_action(
        ActionDef(
            id="view_business",
            name="业务访问",
            resource_type="space",
            extensions={"v3": {"action_id": "view_business_v2", "type": "view", "version": 1}},
        )
    )
    schema.register_action(
        ActionDef(
            id="manage_synthetic",
            name="拨测管理",
            resource_type="space",
            extensions={"v3": {"action_id": "manage_synthetic_v2", "type": "manage", "version": 1}},
        )
    )
    schema.register_action(
        ActionDef(
            id="using_dashboard_mcp",
            name="使用仪表盘MCP",
            resource_type="space",
            extensions={"v3": {"action_id": "using_dashboard_mcp", "type": "view", "version": 1}},
        )
    )
    schema.register_action(
        ActionDef(
            id="manage_global_setting",
            name="全局配置编辑",
            resource_type="",
            extensions={"v3": {"action_id": "manage_global_setting", "type": "manage", "version": 1}},
        )
    )
    schema.register_resource_type(
        ResourceTypeDef(
            id="space",
            name="空间",
            extensions={"v3": {"system_id": "bk_monitorv3", "selection_mode": "instance"}},
        )
    )
    schema.freeze()
    return schema


def _make_provider(**overrides) -> V3PermissionProvider:
    options = _valid_options()
    options.update(overrides)
    provider = V3PermissionProvider(_build_test_schema(), **options)
    provider._iam_client = MagicMock()
    return provider


class TestV3ProviderConstruction:
    """V3Provider 构造与属性验证。"""

    def test_construct_from_options(self):
        p = V3PermissionProvider(_build_test_schema(), **_valid_options())
        assert p.name == "v3"
        assert p.schema is not None
        assert isinstance(p.codec, MonitorV3Codec)
        assert p._cfg.base_url == "https://iam.example.com"
        assert p._cfg.credentials.app_code == "test_app"
        assert p._cfg.system.id == "bk_monitorv3"
        assert p.CHUNK_SIZE == 8
        assert p.MAX_WORKERS == 1

    def test_get_system_info(self):
        p = _make_provider()
        info = p.get_system_info()
        assert info.id == "bk_monitorv3"
        assert info.name == "监控平台"


class TestV3ProviderDialectMethods:
    """方言层方法测试（mock CompatibleIAM）。"""

    # ---------- _is_allowed_dialect ----------

    def test_is_allowed_read_action_uses_cache(self):
        """读操作（type="view"）调用 is_allowed_with_cache。"""
        p = _make_provider()
        p._iam_client.is_allowed_with_cache.return_value = True

        result = p._is_allowed_dialect(
            DialectAuthRequest(
                subject=CoreSubject(id="alice"),
                action_id="view_business_v2",
                resource=None,
            )
        )
        assert result is True
        p._iam_client.is_allowed_with_cache.assert_called_once()
        p._iam_client.is_allowed.assert_not_called()

    def test_is_allowed_write_action_no_cache(self):
        """写操作（type="manage"）调用 is_allowed。"""
        p = _make_provider()
        p._iam_client.is_allowed.return_value = False

        result = p._is_allowed_dialect(
            DialectAuthRequest(
                subject=CoreSubject(id="alice"),
                action_id="manage_synthetic_v2",
                resource=None,
            )
        )
        assert result is False
        p._iam_client.is_allowed.assert_called_once()
        p._iam_client.is_allowed_with_cache.assert_not_called()

    def test_is_allowed_read_with_resource(self):
        """带资源的读操作鉴权，验证 Request 正确构造。"""
        p = _make_provider()
        p._iam_client.is_allowed_with_cache.return_value = True

        result = p._is_allowed_dialect(
            DialectAuthRequest(
                subject=CoreSubject(id="alice"),
                action_id="view_business_v2",
                resource=DialectResource(type="space", id="3"),
            )
        )
        assert result is True
        call_args = p._iam_client.is_allowed_with_cache.call_args[0][0]
        assert isinstance(call_args, Request)
        assert call_args.system == "bk_monitorv3"
        assert call_args.subject.id == "alice"
        assert call_args.action.id == "view_business_v2"

    def test_is_allowed_auth_api_error_returns_false(self):
        """AuthAPIError 不传播，返回 False。"""
        p = _make_provider()
        p._iam_client.is_allowed.side_effect = AuthAPIError("test error")

        result = p._is_allowed_dialect(
            DialectAuthRequest(
                subject=CoreSubject(id="alice"),
                action_id="manage_synthetic_v2",
            )
        )
        assert result is False

    # ---------- _batch_by_resource_dialect_page ----------

    def test_batch_by_resource_page(self):
        """同 action 多 resource：调用 batch_resource_multi_actions_allowed。"""
        p = _make_provider()
        p._iam_client.batch_resource_multi_actions_allowed.return_value = {
            "3": {"view_business_v2": True},
            "4": {"view_business_v2": False},
        }

        result = p._batch_by_resource_dialect_page(
            DialectBatchByResourceRequest(
                subject=CoreSubject(id="alice"),
                action_id="view_business_v2",
                resource_type="space",
                resource_ids=("3", "4"),
            )
        )
        assert result == [("3", True), ("4", False)]
        p._iam_client.batch_resource_multi_actions_allowed.assert_called_once()

    def test_batch_by_resource_auth_api_error(self):
        """SDK 异常时全部返回 False。"""
        p = _make_provider()
        p._iam_client.batch_resource_multi_actions_allowed.side_effect = AuthAPIError("err")

        result = p._batch_by_resource_dialect_page(
            DialectBatchByResourceRequest(
                subject=CoreSubject(id="alice"),
                action_id="view_business_v2",
                resource_type="space",
                resource_ids=("3", "4"),
            )
        )
        assert result == [("3", False), ("4", False)]

    # ---------- _batch_by_action_dialect_page ----------

    def test_batch_by_action_with_resource(self):
        """多 action 同 resource：调用 batch_resource_multi_actions_allowed。"""
        p = _make_provider()
        p._iam_client.batch_resource_multi_actions_allowed.return_value = {
            "3": {
                "view_business_v2": True,
                "manage_synthetic_v2": False,
            }
        }

        result = p._batch_by_action_dialect_page(
            DialectBatchByActionRequest(
                subject=CoreSubject(id="alice"),
                action_ids=("view_business_v2", "manage_synthetic_v2"),
                resource=DialectResource(type="space", id="3"),
            )
        )
        assert result == [("view_business_v2", True), ("manage_synthetic_v2", False)]
        p._iam_client.batch_resource_multi_actions_allowed.assert_called_once()

    def test_batch_by_action_without_resource(self):
        """无资源的 resource-free action 批量鉴权。"""
        p = _make_provider()
        p._iam_client.batch_resource_multi_actions_allowed.return_value = {"": {"manage_global_setting": True}}

        result = p._batch_by_action_dialect_page(
            DialectBatchByActionRequest(
                subject=CoreSubject(id="alice"),
                action_ids=("manage_global_setting",),
                resource=None,
            )
        )
        assert result == [("manage_global_setting", True)]

    # ---------- _get_apply_url_dialect ----------

    def test_get_apply_url(self):
        """生成权限申请 URL。"""
        p = _make_provider()
        p._iam_client.get_apply_url.return_value = (True, "", "https://iam.example.com/apply")

        url = p._get_apply_url_dialect(
            DialectApplyURLRequest(
                subject=CoreSubject(id="alice"),
                action_ids=("view_business_v2",),
                resources=(DialectResource(type="space", id="3"),),
            )
        )
        assert url == "https://iam.example.com/apply"
        p._iam_client.get_apply_url.assert_called_once()

    def test_get_apply_url_failure_returns_empty(self):
        """申请 URL 生成失败返回空字符串。"""
        p = _make_provider()
        p._iam_client.get_apply_url.return_value = (False, "error msg", "")

        url = p._get_apply_url_dialect(
            DialectApplyURLRequest(
                subject=CoreSubject(id="alice"),
                action_ids=("view_business_v2",),
                resources=(),
            )
        )
        assert url == ""

    def test_get_apply_url_resource_free_action(self):
        """无关联资源的 action 使用 ActionWithoutResources。"""
        p = _make_provider()
        p._iam_client.get_apply_url.return_value = (True, "", "https://iam.example.com/apply")

        url = p._get_apply_url_dialect(
            DialectApplyURLRequest(
                subject=CoreSubject(id="alice"),
                action_ids=("manage_global_setting",),
                resources=(),
            )
        )
        assert url == "https://iam.example.com/apply"

    # ---------- health_check ----------

    def test_health_check_ok(self):
        """探活成功。"""
        p = _make_provider()
        # mock _client.query 的返回值（IAM SDK 内部调用）
        mock_client = MagicMock()
        mock_client.query.return_value = (True, "ok", {"data": {"id": "bk_monitorv3"}})
        p._iam_client._client = mock_client

        result = p.health_check()
        assert result["status"] == "ok"
        assert result["provider"] == "v3"

    def test_health_check_error(self):
        """探活异常时返回 error。"""
        p = _make_provider()
        mock_client = MagicMock()
        mock_client.query.side_effect = Exception("timeout")
        p._iam_client._client = mock_client

        result = p.health_check()
        assert result["status"] == "error"
        assert "timeout" in result["error"]

    # ---------- plan_migration / apply_migration ----------

    def test_plan_migration_system_scope(self):
        """scope="system"：只生成 SYSTEM Change。"""
        p = _make_provider()
        plan = p.plan_migration(_build_test_schema(), scope="system")
        assert plan.provider_name == "v3"
        assert len(plan.changes) == 1
        assert plan.changes[0].kind.name == "SYSTEM"

    def test_plan_migration_full_scope(self):
        """scope="full"：生成 SYSTEM + ACTION + RT Change。"""
        p = _make_provider()
        plan = p.plan_migration(_build_test_schema(), scope="full")
        assert plan.provider_name == "v3"
        kinds = {c.kind.name for c in plan.changes}
        assert "SYSTEM" in kinds
        assert "ACTION" in kinds
        assert "RESOURCE_TYPE" in kinds

    def test_apply_migration_system_only(self):
        """plan 只有 SYSTEM：不查远端 actions/RTs，直接执行系统注册。"""
        p = _make_provider()
        mock_client = MagicMock()
        mock_client.query.return_value = (False, "not found", None)
        p._iam_client._client = mock_client

        from bkmonitor.iam.iam_engine.schema.diff import Change, ChangeType, EntityKind, MigrationPlan

        plan = MigrationPlan(
            provider_name="v3",
            changes=[
                Change(
                    kind=EntityKind.SYSTEM,
                    change_type=ChangeType.CREATE,
                    entity_id="bk_monitorv3",
                    after={"id": "bk_monitorv3", "name": "监控平台", "description": "", "managers": [], "clients": []},
                ),
            ],
        )
        report = p.apply_migration(plan)
        # 即使远端返回系统不存在，apply 也会尝试创建
        assert report.provider_name == "v3"

    def test_apply_migration_skip_existing(self):
        """scope="full"：远端已有 → reconcile 跳过。"""
        p = _make_provider()
        mock_client = MagicMock()
        mock_client.query.return_value = (
            True,
            "ok",
            {
                "actions": [{"id": "view_business_v2"}],
                "resource_types": [{"id": "space"}],
            },
        )
        p._iam_client._client = mock_client

        from bkmonitor.iam.iam_engine.schema.diff import Change, ChangeType, EntityKind, MigrationPlan

        plan = MigrationPlan(
            provider_name="v3",
            changes=[
                Change(
                    kind=EntityKind.ACTION,
                    change_type=ChangeType.CREATE,
                    entity_id="view_business",
                    after={"id": "view_business_v2"},
                ),
            ],
        )
        report = p.apply_migration(plan)
        assert report.success is True
        assert report.applied == []  # 远端已有，跳过
