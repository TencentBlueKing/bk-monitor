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

from unittest.mock import MagicMock, patch

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
    mock_client = MagicMock()
    provider._iam_client = mock_client
    # 方言方法通过 _get_client(tenant_id) 获取 client，统一返回 mock
    provider._get_client = MagicMock(return_value=mock_client)
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
        """带资源的读操作鉴权，验证 client 工厂方法与鉴权调用参数。"""
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
        # 资源通过 client.make_resource 构造（type/id/ancestors）
        p._iam_client.make_resource.assert_called_once_with("space", "3", ancestors=())
        # Request 通过 client.make_request 构造（username/action_id/resources）
        make_req_args = p._iam_client.make_request.call_args[0]
        assert make_req_args[0] == "alice"
        assert make_req_args[1] == "view_business_v2"
        assert len(make_req_args[2]) == 1

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

    def test_batch_by_resource_without_ancestors_uses_empty_path_guard(self):
        """无祖先链的旧构造：attribute 带空串 _bk_iam_path_ 占位，避免 SDK 本地求值 KeyError。"""
        p = _make_provider()
        p._iam_client.batch_resource_multi_actions_allowed.return_value = {
            "390": {"manage_apm_application_v2": False},
        }

        result = p._batch_by_resource_dialect_page(
            DialectBatchByResourceRequest(
                subject=CoreSubject(id="alice"),
                action_id="manage_apm_application_v2",
                resource_type="apm_application",
                resource_ids=("390",),
            )
        )
        assert result == [("390", False)]
        p._iam_client.make_resource.assert_called_once_with(
            "apm_application", "390", ancestors=(), attribute={"_bk_iam_path_": ""}
        )

    def test_batch_by_resource_with_ancestors(self):
        """携带祖先链的批量鉴权：SDK resource 通过 ancestors 构造 _bk_iam_path_。"""
        p = _make_provider()
        p._iam_client.batch_resource_multi_actions_allowed.return_value = {
            "14|f0ImroNIz": {"view_single_dashboard": True},
        }

        result = p._batch_by_resource_dialect_page(
            DialectBatchByResourceRequest(
                subject=CoreSubject(id="alice"),
                action_id="view_single_dashboard",
                resource_type="grafana_dashboard",
                resource_ids=("14|f0ImroNIz",),
                resources=(
                    DialectResource(
                        type="grafana_dashboard",
                        id="14|f0ImroNIz",
                        ancestors=(DialectResource(type="space", id="-6"),),
                    ),
                ),
            )
        )
        assert result == [("14|f0ImroNIz", True)]
        p._iam_client.make_resource.assert_called_once_with(
            "grafana_dashboard",
            "14|f0ImroNIz",
            ancestors=(DialectResource(type="space", id="-6"),),
            attribute=None,
        )

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

    def test_batch_by_action_with_ancestors(self):
        """多 action 同 resource：SDK resource 携带祖先链（_bk_iam_path_ 依赖）。"""
        p = _make_provider()
        p._iam_client.batch_resource_multi_actions_allowed.return_value = {
            "390": {"manage_apm_application_v2": True},
        }

        result = p._batch_by_action_dialect_page(
            DialectBatchByActionRequest(
                subject=CoreSubject(id="alice"),
                action_ids=("manage_apm_application_v2",),
                resource=DialectResource(
                    type="apm_application",
                    id="390",
                    ancestors=(DialectResource(type="space", id="2"),),
                ),
            )
        )
        assert result == [("manage_apm_application_v2", True)]
        p._iam_client.make_resource.assert_called_once_with(
            "apm_application", "390", ancestors=(DialectResource(type="space", id="2"),), attribute=None
        )

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
        """探活成功：委托 V3Client.health_check，并附加 provider/remote_id。"""
        p = _make_provider()
        p._iam_client.health_check.return_value = {"status": "ok"}

        result = p.health_check()
        assert result["status"] == "ok"
        assert result["provider"] == "v3"
        assert result["remote_id"] == "bk_monitorv3"

    def test_health_check_error(self):
        """探活异常：V3Client 返回 error，provider 原样透传并附加标识。"""
        p = _make_provider()
        p._iam_client.health_check.return_value = {"status": "error", "error": "timeout"}

        result = p.health_check()
        assert result["status"] == "error"
        assert "timeout" in result["error"]
        assert result["provider"] == "v3"

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

    def test_plan_migration_uses_configured_system_as_v3_default(self):
        """未显式声明跨系统资源时，V3 payload 应使用当前 Provider 的系统 ID。"""
        schema = SchemaRegistry()
        schema.register_resource_type(
            ResourceTypeDef(
                id="document",
                name="文档",
                extensions={"v3": {"selection_mode": "instance"}},
            )
        )
        schema.register_action(
            ActionDef(
                id="view_document",
                name="查看文档",
                resource_type="document",
                extensions={"v3": {"type": "view"}},
            )
        )
        schema.freeze()
        options = _valid_options()
        options["system"] = {"id": "custom_v3_system", "name": "自定义系统"}
        provider = V3PermissionProvider(schema, **options)

        plan = provider.plan_migration(schema, scope="full")
        resource_change = next(change for change in plan.changes if change.entity_id == "document")
        action_change = next(change for change in plan.changes if change.entity_id == "view_document")

        assert resource_change.after["system_id"] == "custom_v3_system"
        assert action_change.after["related_resource_types"] == [
            {
                "system_id": "custom_v3_system",
                "id": "document",
                "selection_mode": "instance",
                "related_instance_selections": [],
            }
        ]

    def test_apply_migration_system_only(self):
        """plan 只有 SYSTEM：不查远端 actions/RTs，直接执行系统注册。"""
        p = _make_provider()
        # 远端系统查询：系统不存在（query_system 委托 V3Client）
        p._iam_client.query_system.return_value = (False, "not found", None)

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
        # mock 迁移执行用的 IamMigrateClient（migrator 模块内以该名字引用；
        # patch 源模块属性不会影响 migrator 已绑定的引用），避免真实网络调用
        with patch("bkmonitor.iam.iam_v3.migrator.IamMigrateClient") as mock_client_cls:
            mock_migration_client = MagicMock()
            mock_migration_client.add_system.return_value = (True, "")
            mock_client_cls.return_value = mock_migration_client

            report = p.apply_migration(plan)

        # 即使远端返回系统不存在，apply 也会尝试创建
        assert report.provider_name == "v3"
        assert report.success is True
        assert len(report.applied) == 1
        mock_migration_client.add_system.assert_called_once()

    def test_apply_migration_skip_existing(self):
        """scope="full"：远端已有 → reconcile 跳过。"""
        p = _make_provider()
        # 远端系统查询返回已注册的 actions/RTs
        p._iam_client.query_system.return_value = (
            True,
            "ok",
            {
                "base_info": {},
                "actions": [{"id": "view_business_v2"}],
                "resource_types": [{"id": "space"}],
            },
        )

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
        with patch("iam.contrib.iam_migration.utils.do_migrate.Client") as mock_client_cls:
            mock_migration_client = MagicMock()
            mock_client_cls.return_value = mock_migration_client

            report = p.apply_migration(plan)

        assert report.success is True
        assert report.applied == []  # 远端已有，跳过
        mock_migration_client.add_action.assert_not_called()
