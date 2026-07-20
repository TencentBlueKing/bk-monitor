"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

运营数据 MCP 鉴权收敛（方案 A）相关单测。

核心诉求：运营数据为平台总量，bk_biz_id 仅用于鉴权范围。
当部署方配置了固定运营业务（OPERATION_MCP_AUTH_BIZ_ID）后，运营 MCP 的 IAM 校验必须收敛到该业务，
而不是调用方传入的 bk_biz_id —— 否则用户用自有业务权限即可解锁全平台运营数据。

由于真实 IAM 校验依赖外部服务，这里 mock 掉 ``IAMPermission.has_permission`` 与
``ResourceEnum.BUSINESS.create_instance``，只验证"最终拿去鉴权的业务 ID"是否符合预期。
"""

import pytest

from bkmonitor.iam import drf as iam_drf
from bkmonitor.iam.action import ActionEnum
from bkmonitor.iam.drf import MCPPermission
from core.errors.iam import PermissionDeniedError


class _FakeRequest:
    """最小化的 request 桩：MCPPermission 仅读取 biz_id 与 skip_check。"""

    def __init__(self, biz_id=None, skip_check=False):
        self.biz_id = biz_id
        self.skip_check = skip_check


@pytest.fixture
def capture(monkeypatch):
    """捕获最终用于 IAM 校验的业务 ID，并放行鉴权。"""
    captured: dict = {}

    def fake_has_permission(self, request, view):
        captured["resources"] = self.resources
        return True

    def fake_create_instance(biz_id, *args, **kwargs):
        captured["biz_id"] = biz_id
        return ("BIZ", biz_id)

    monkeypatch.setattr(iam_drf.IAMPermission, "has_permission", fake_has_permission)
    monkeypatch.setattr(iam_drf.ResourceEnum.BUSINESS, "create_instance", fake_create_instance)
    return captured


class TestMCPPermissionBizOverride:
    def test_override_biz_used_when_provided(self, capture):
        """配置了固定鉴权业务时，应使用该业务而非调用方传入业务。"""
        perm = MCPPermission(action=ActionEnum.USING_OPERATION_MCP, biz_id=999)
        assert perm.has_permission(_FakeRequest(biz_id=2), view=None) is True
        # 鉴权落在固定运营业务 999，而不是调用方传入的 2
        assert capture["biz_id"] == 999

    def test_fallback_to_request_biz_when_no_override(self, capture):
        """未配置固定鉴权业务时，沿用调用方传入的 bk_biz_id（向后兼容）。"""
        perm = MCPPermission(action=ActionEnum.USING_OPERATION_MCP)
        assert perm.has_permission(_FakeRequest(biz_id=2), view=None) is True
        assert capture["biz_id"] == 2

    def test_override_zero_falls_back(self, capture):
        """biz_id=0 视为未配置（falsy），回退到调用方传入业务。"""
        perm = MCPPermission(action=ActionEnum.USING_OPERATION_MCP, biz_id=0)
        assert perm.has_permission(_FakeRequest(biz_id=2), view=None) is True
        assert capture["biz_id"] == 2

    def test_missing_biz_raises(self, capture):
        """既无固定鉴权业务、调用方也未传 biz 时，必须拒绝。"""
        perm = MCPPermission(action=ActionEnum.USING_OPERATION_MCP)
        with pytest.raises(PermissionDeniedError):
            perm.has_permission(_FakeRequest(biz_id=None), view=None)

    def test_override_used_even_when_request_biz_missing(self, capture):
        """即使调用方未传 biz，只要配置了固定鉴权业务，也应使用固定业务校验。"""
        perm = MCPPermission(action=ActionEnum.USING_OPERATION_MCP, biz_id=777)
        assert perm.has_permission(_FakeRequest(biz_id=None), view=None) is True
        assert capture["biz_id"] == 777
