from types import SimpleNamespace
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.iam.backends.config import build_provider

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

import pytest

from iam.exceptions import AuthAPIError

from iam_engine.provider.requests import (
    Subject as CoreSubject,
)
from iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance
from iam_engine.core.types import AuthStatus
from iam import Action, Resource
from iam_engine.schema.definitions import ActionDef, ResourceTypeDef
from bkmonitor.iam.backends.v3.codec import MonitorV3Codec
from bkmonitor.iam.backends.v3.provider import V3PermissionProvider


def _valid_options() -> dict:
    return {
        "codec_class": "bkmonitor.iam.backends.v3.codec.MonitorV3Codec",
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
        "system": {
            "id": "bk_monitorv3",
            "name": "监控平台",
            "name_en": "BKMonitor",
            "clients": ["test_app", "bkci"],
            "provider_config": {"host": "https://monitor.example.com", "auth": "basic"},
        },
        "bk_tenant_id": "default",
        "chunk_size": 8,
        "max_workers": 1,
    }


def _build_test_schema():
    """测试直接提供最小的产品定义映射。"""
    schema = SimpleNamespace(actions={}, resource_types={}, roles={})
    schema.actions["view_business"] = ActionDef(
            id="view_business",
            name="业务访问",
            resource_type="space",
            extensions={"v3": {"action_id": "view_business_v2", "type": "view", "version": 1}},
        )
    schema.actions["manage_synthetic"] = ActionDef(
            id="manage_synthetic",
            name="拨测管理",
            resource_type="space",
            extensions={"v3": {"action_id": "manage_synthetic_v2", "type": "manage", "version": 1}},
        )
    schema.actions["using_dashboard_mcp"] = ActionDef(
            id="using_dashboard_mcp",
            name="使用仪表盘MCP",
            resource_type="space",
            extensions={"v3": {"action_id": "using_dashboard_mcp", "type": "view", "version": 1}},
        )
    schema.actions["manage_global_setting"] = ActionDef(
            id="manage_global_setting",
            name="全局配置编辑",
            resource_type="",
            extensions={"v3": {"action_id": "manage_global_setting", "type": "manage", "version": 1}},
        )
    schema.resource_types["space"] = ResourceTypeDef(
            id="space",
            name="空间",
            extensions={"v3": {"system_id": "bk_monitorv3", "selection_mode": "instance"}},
        )

    return schema


def _make_provider(**overrides) -> V3PermissionProvider:
    options = _valid_options()
    options.update(overrides)
    provider = build_provider("v3", schema=_build_test_schema(), options={**options})
    mock_client = MagicMock()
    mock_client.make_resource.side_effect = lambda rt, rid, **kwargs: Resource("bk_monitorv3", rt, rid, {})
    provider.resolver = None
    # 方言方法通过 _get_client(tenant_id) 获取 client，统一返回 mock
    provider._get_client = MagicMock(return_value=mock_client)
    return provider


class TestV3ProviderConstruction:
    """V3Provider 构造与属性验证。"""

    def test_construct_from_options(self):
        p = build_provider("v3", schema=_build_test_schema(), options={**_valid_options()})
        assert p.name == "v3"
        assert p.schema is not None
        assert isinstance(p.codec, MonitorV3Codec)
        assert p._cfg.base_url == "https://iam.example.com"
        assert p._cfg.credentials.app_code == "test_app"
        assert p._cfg.system.id == "bk_monitorv3"
        assert p._cfg.chunk_size == 8
        assert p._cfg.max_workers == 1

class TestV3ProviderCapabilities:
    """Native three-state contract with the real product codec and mocked SDK."""

    @pytest.mark.parametrize(
        "action,raw,method,status",
        [
            ("view_business", True, "is_allowed_with_cache", AuthStatus.ALLOW),
            ("view_business", False, "is_allowed_with_cache", AuthStatus.DENY),
            ("manage_synthetic", False, "is_allowed", AuthStatus.DENY),
            ("manage_synthetic", None, "is_allowed", AuthStatus.ERROR),
        ],
    )
    def test_read_cache_write_and_strict_decision(self, action, raw, method, status):
        p = _make_provider()
        getattr(p.client, method).return_value = raw
        result = p.is_allowed(AuthRequest(CoreSubject(id="alice"), action, (ResourceInstance("space", "3"),)))
        assert result.status is status
        getattr(p.client, method).assert_called_once()
        args = p.client.make_request.call_args.args
        assert args[:2] == ("alice", p.codec.encode_action(action))
        assert len(args[2]) == 1

    def test_auth_api_failure_preserves_error(self):
        p = _make_provider()
        p.client.is_allowed.side_effect = AuthAPIError("offline")
        result = p.is_allowed(AuthRequest(CoreSubject(id="alice"), "manage_synthetic"))
        assert result.status is AuthStatus.ERROR
        assert not result.allowed

    def test_batch_encodes_actions_and_missing_row(self):
        p = _make_provider()
        p.client.batch_resource_multi_actions_allowed.return_value = {
            "3": {"view_business_v2": True, "manage_synthetic_v2": False}
        }
        result = p.batch_is_allowed(
            BatchAuthRequest(
                CoreSubject(id="alice"),
                ("view_business", "manage_synthetic"),
                ((ResourceInstance("space", "3"),), (ResourceInstance("space", "4"),)),
            )
        )
        values = result.by_key()
        assert values["view_business", "3"].allowed
        assert values["manage_synthetic", "3"].status is AuthStatus.DENY
        assert values["view_business", "4"].status is AuthStatus.ERROR
        p.client.batch_resource_multi_actions_allowed.assert_called_once()

    def test_batch_without_ancestor_keeps_sdk_empty_path_guard(self):
        p = _make_provider()
        p.client.batch_resource_multi_actions_allowed.return_value = {"3": {"view_business_v2": False}}
        p.batch_is_allowed(
            BatchAuthRequest(CoreSubject(id="alice"), ("view_business",), ((ResourceInstance("space", "3"),),))
        )
        p.client.make_resource.assert_called_once_with("space", "3", ancestors=(), attribute={"_bk_iam_path_": ""})

    def test_batch_ancestor_is_encoded_at_product_boundary(self):
        p = _make_provider()
        resource = ResourceInstance("space", "3", ancestor_chain=(ResourceInstance("space", "-6"),))
        p.client.batch_resource_multi_actions_allowed.return_value = {"3": {"view_business_v2": True}}
        assert (
            p.batch_is_allowed(BatchAuthRequest(CoreSubject(id="alice"), ("view_business",), ((resource,),)))
            .items[0]
            .result.allowed
        )
        ancestor = p.client.make_resource.call_args.kwargs["ancestors"][0]
        assert (ancestor.type, ancestor.id) == ("space", "-6")

    def test_batch_error_marks_every_requested_key(self):
        p = _make_provider()
        p.client.batch_resource_multi_actions_allowed.side_effect = AuthAPIError("offline")
        request = BatchAuthRequest(
            CoreSubject(id="alice"),
            ("view_business", "manage_synthetic"),
            ((ResourceInstance("space", "3"),), (ResourceInstance("space", "4"),)),
        )
        result = p.batch_is_allowed(request)
        assert set(result.by_key()) == set(request.iter_keys())
        assert all(item.result.status is AuthStatus.ERROR for item in result.items)

    @pytest.mark.parametrize(
        "action,resources", [("view_business", [ResourceInstance("space", "3")]), ("manage_global_setting", [])]
    )
    def test_application_native_tuple(self, action, resources):
        p = _make_provider()
        p.client.make_action.side_effect = lambda aid: Action(aid)
        p.client.make_resource.side_effect = lambda rt, rid, **kw: Resource("bk_monitorv3", rt, rid, {})
        p.client.get_apply_url.return_value = (True, "", "https://iam.example.test/apply")
        data, url = p.get_apply_data([action], resources)
        assert data["actions"][0]["id"] == p.codec.encode_action(action)
        assert url == "https://iam.example.test/apply"

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
