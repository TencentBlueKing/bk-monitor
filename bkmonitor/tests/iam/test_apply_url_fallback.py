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
# apply_url fallback 兜底能力测试
#
# 背景（08-31 评审 R3 后续）：
#   V3/V4 provider 生成申请页 URL 失败/为空时，历史行为是直接返回 ""，
#   由 Permission 层做上层降级（也是 ""）。用户体验是"申请按钮直接消失"。
#
# 本轮新增 provider 级的 `fallback_apply_url` 可选配置：
#   * 未配置（默认空）→ 保持既有 "" 契约，向后完全兼容。
#   * 显式配置（例如内部 ITSM 权限工单页 / IAM SaaS 首页）→ 平台失败/空返回时
#     用此 URL 兜底，让前端至少能给用户一个可点击的链接。
#
# 覆盖：
#   1. V4 provider：client 返回空串 → fallback 生效；client 返回非空 → 原样返回
#   2. V4 provider：未配置 fallback（默认空）时 → 仍返回空串
#   3. V3 provider：client 返回 ok=False → fallback 生效
#   4. V3 provider：client 返回 ok=True 但 url="" → fallback 生效
#   5. V3 provider：未配置 fallback 时 → 仍返回空串
# ==============================================================================

from unittest.mock import MagicMock

import pytest

from bkmonitor.iam.iam_engine.core.types import Subject, SubjectType
from bkmonitor.iam.iam_engine.django.facade import get_framework
from bkmonitor.iam.iam_engine.provider.dialect_types import DialectApplyURLRequest, DialectResource


@pytest.fixture
def real_schema():
    """复用框架已构建的 SchemaRegistry（避免手工构造 schema）。"""
    return get_framework().schema


def _v4_valid_options(**overrides) -> dict:
    opts = {
        "base_url": "https://iam.example.com",
        "credentials": {"app_code": "app1", "app_secret": "secret1"},
        "system": {"id": "bk_monitor_v4", "name": "监控"},
    }
    opts.update(overrides)
    return opts


def _v3_valid_options(**overrides) -> dict:
    opts = {
        "codec_class": "bkmonitor.iam.adapters.v3.codec.MonitorV3Codec",
        "resolver_class": "bkmonitor.iam.adapters.resolver.MonitorResourceResolver",
        "base_url": "https://iam.example.com",
        "credentials": {"app_code": "app1", "app_secret": "secret1"},
        "system": {
            "id": "bk_monitorv3",
            "name": "监控",
            "clients": ["bk_monitorv3"],
        },
    }
    opts.update(overrides)
    return opts


def _build_dialect_request(action_id: str = "view_business") -> DialectApplyURLRequest:
    """构造方言层申请 URL 请求，直接对齐 provider._get_apply_url_dialect 的入参契约。

    使用 dialect 类型（DialectResource + ancestors）而不是外层的 ResourceInstance
    （ancestor_chain）—— provider 基类 get_apply_url 会先做外层 → 方言层的编码，
    这里直接测方言层，跳过编码步骤，专注 fallback 逻辑。
    """
    return DialectApplyURLRequest(
        subject=Subject(id="tester", type=SubjectType.USER, tenant_id="system"),
        action_ids=(action_id,),
        resources=(DialectResource(type="space", id="2"),),
    )


# ------------------------------------------------------------------
# V4 Provider
# ------------------------------------------------------------------


class TestV4ApplyUrlFallback:
    def _build_provider(self, schema, fallback: str = "", *, client_return: str = ""):
        from bkmonitor.iam.iam_v4.provider import V4PermissionProvider

        provider = V4PermissionProvider(schema, **_v4_valid_options(fallback_apply_url=fallback))
        # 拦截 client：避免真实 HTTP，直接返回受测值
        mock_client = MagicMock()
        mock_client.generate_perm_apply_url.return_value = client_return
        provider._get_client = MagicMock(return_value=mock_client)  # type: ignore[method-assign]
        return provider, mock_client

    def test_empty_url_falls_back_to_configured(self, real_schema):
        """client 返回 "" 且配置了 fallback → 返回 fallback。"""
        provider, mock_client = self._build_provider(
            real_schema,
            fallback="https://itsm.example.com/apply",
            client_return="",
        )
        url = provider._get_apply_url_dialect(_build_dialect_request())
        assert url == "https://itsm.example.com/apply"
        mock_client.generate_perm_apply_url.assert_called_once()

    def test_empty_url_without_fallback_returns_empty(self, real_schema):
        """未配置 fallback 时保持既有 "" 契约。"""
        provider, _ = self._build_provider(real_schema, fallback="", client_return="")
        assert provider._get_apply_url_dialect(_build_dialect_request()) == ""

    def test_non_empty_url_bypasses_fallback(self, real_schema):
        """client 返回非空 URL 时原样返回，fallback 不参与。"""
        provider, _ = self._build_provider(
            real_schema,
            fallback="https://itsm.example.com/apply",
            client_return="https://iam.example.com/apply/xyz",
        )
        assert provider._get_apply_url_dialect(_build_dialect_request()) == "https://iam.example.com/apply/xyz"


# ------------------------------------------------------------------
# V3 Provider
# ------------------------------------------------------------------


class TestV3ApplyUrlFallback:
    def _build_provider(self, schema, fallback: str = ""):
        """构造 V3 provider，并 patch 内部 _get_client / _action_has_resource。"""
        from bkmonitor.iam.iam_v3.provider import V3PermissionProvider

        provider = V3PermissionProvider(schema, **_v3_valid_options(fallback_apply_url=fallback))
        # 简化：所有 action 都视为 "无关联资源"，避免 schema.get_action 走真实数据
        provider._action_has_resource = MagicMock(return_value=False)  # type: ignore[method-assign]
        return provider

    def _mock_client_get_apply_url(self, provider, ok: bool, message: str, url: str):
        mock_client = MagicMock()
        mock_client.get_apply_url.return_value = (ok, message, url)
        provider._get_client = MagicMock(return_value=mock_client)  # type: ignore[method-assign]
        return mock_client

    def test_ok_false_falls_back_to_configured(self, real_schema):
        """SDK 返回 ok=False（业务失败）→ 走 fallback。"""
        provider = self._build_provider(real_schema, fallback="https://saas.example.com/")
        self._mock_client_get_apply_url(provider, ok=False, message="rpc error", url="")
        assert provider._get_apply_url_dialect(_build_dialect_request()) == "https://saas.example.com/"

    def test_ok_true_but_empty_url_falls_back(self, real_schema):
        """SDK 返回 ok=True 但 url="" 也应触发 fallback，避免前端拿到空链接。"""
        provider = self._build_provider(real_schema, fallback="https://saas.example.com/")
        self._mock_client_get_apply_url(provider, ok=True, message="", url="")
        assert provider._get_apply_url_dialect(_build_dialect_request()) == "https://saas.example.com/"

    def test_ok_false_without_fallback_returns_empty(self, real_schema):
        """未配置 fallback 时保持既有 "" 契约。"""
        provider = self._build_provider(real_schema, fallback="")
        self._mock_client_get_apply_url(provider, ok=False, message="rpc error", url="")
        assert provider._get_apply_url_dialect(_build_dialect_request()) == ""

    def test_non_empty_url_bypasses_fallback(self, real_schema):
        """SDK 返回非空 URL 时原样返回。"""
        provider = self._build_provider(real_schema, fallback="https://saas.example.com/")
        self._mock_client_get_apply_url(
            provider,
            ok=True,
            message="",
            url="https://iam.example.com/apply/xyz",
        )
        assert provider._get_apply_url_dialect(_build_dialect_request()) == "https://iam.example.com/apply/xyz"


# ------------------------------------------------------------------
# 配置兼容性：既有配置（不带 fallback_apply_url）不受影响
# ------------------------------------------------------------------


class TestBackwardCompat:
    def test_v4_options_without_fallback_defaults_to_empty(self):
        from bkmonitor.iam.iam_v4.config import V4Options

        cfg = V4Options.from_dict(_v4_valid_options())
        assert cfg.fallback_apply_url == ""

    def test_v3_options_without_fallback_defaults_to_empty(self):
        from bkmonitor.iam.iam_v3.config import V3Options

        cfg = V3Options.from_dict(_v3_valid_options())
        assert cfg.fallback_apply_url == ""
