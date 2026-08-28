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
# permission.py 重构对照测试（含新旧鉴权路径一致性验证）
#
# 对照基线：merge-base 7b360f40 上的旧 permission.py（520 行）
# 测试目标：
#   1. 对外方法面完整（is_allowed / is_allowed_by_biz / batch_is_allowed /
#      get_apply_url / get_apply_data / filter_space_list_by_action /
#      make_resource / batch_make_resource / get_iam_client / grant_creator_action 签名）
#   2. 鉴权路径一致性：同一用户/动作/资源，旧版（LegacyIAM + 旧 ActionMeta）与
#      新版（V3PermissionProvider + codec）发给 V3 平台的请求载荷与判定结果一致
#   3. V1 双查 / new_dashboard 语义别名 / 读写缓存策略与旧版一致
#   4. 已发现回归点显式记录（list_actions 抛 NotImplementedError 等，xfail 标记）
#   5. live 用例（BK_IAM_ENGINE_USER 门控）：对真实测试鉴权服务器的只读查询
# 安全约束：本文件所有用例均为权限查询（is_allowed / policy_query /
# get_apply_url 等只读 API），无任何授权/迁移/删除操作。
# ==============================================================================

import copy
import os

import pytest
from unittest.mock import MagicMock, patch

from iam import Action as SdkAction
from iam import IAM as SdkIAM
from iam import MultiActionRequest
from iam import Request as SdkRequest
from iam import Resource as SdkResource
from iam import Subject as SdkSubject

from bkmonitor.iam import ActionEnum, Permission, ResourceEnum
from bkmonitor.iam.iam_engine.core.types import (
    AuthRequest,
    ResourceInstance as FwResource,
    Subject as FwSubject,
    SubjectType,
    VisibleResult,
)
from bkmonitor.iam.iam_v3.client import V3Client
from core.errors.iam import PermissionDeniedError

from .conftest import LegacyCompatibleIAM


# ---------------------------------------------------------------------------
# 旧路径参考实现（与旧 permission.py 的 make_request/is_allowed 行为一致）
# ---------------------------------------------------------------------------


class LegacyIAM(SdkIAM):
    """旧版 CompatibleIAM 参考实现：真实 SDK + 旧版 _do_policy_query 覆盖。

    仅用于查询路径对照；不访问网络（_client 由测试注入 mock）。
    """

    def __init__(self, app_code, app_secret, bk_apigateway_url, system_id, bk_tenant_id=""):
        super().__init__(app_code, app_secret, bk_apigateway_url, bk_tenant_id=bk_tenant_id)
        self._system_id = system_id
        self._compat = LegacyCompatibleIAM(system_id=system_id)

    def _do_policy_query(self, request, with_resources=True):
        # 每次调用实时转发当前 _client：测试注入 mock（legacy_client._client = http）后同样生效，
        # 否则 _compat 仍持有构造时的真实 SDK Client（此前导致对照用例发起真实网络请求而失败）
        self._compat._client = self._client
        # 兼容模式下：走 V1 双查 + 别名（参考实现恒定兼容模式 = 旧版默认）
        return self._compat._do_policy_query(request.to_dict(), with_resources)

    def _do_policy_query_by_actions(self, request, with_resources=True):
        self._compat._client = self._client
        return self._compat._do_policy_query_by_actions(request.to_dict(), with_resources)


def legacy_make_request(username, v3_action_id, resources):
    """旧 permission.make_request 的等价物。"""
    return SdkRequest(
        system="bk_monitorv3",
        subject=SdkSubject("user", username),
        action=SdkAction(id=v3_action_id),
        resources=resources or [],
        environment=None,
    )


def legacy_make_resource(rt, rid, attribute=None):
    return SdkResource("bk_monitorv3", rt, rid, attribute or {})


def legacy_eval_decision(legacy_client, username, v3_action_id, resources, is_read):
    """旧 Permission.is_allowed 的核心判定：读走缓存、写不走。"""
    request = legacy_make_request(username, v3_action_id, resources)
    if is_read:
        return legacy_client.is_allowed_with_cache(request)
    return legacy_client.is_allowed(request)


# ---------------------------------------------------------------------------
# 接口面
# ---------------------------------------------------------------------------


class TestPermissionSurface:
    """Permission 对外方法面与旧版一致。"""

    def test_public_methods_preserved(self):
        old_methods = {
            "get_iam_client",
            "grant_creator_action",
            "get_apply_url",
            "get_apply_data",
            "is_allowed",
            "is_allowed_by_biz",
            "batch_is_allowed",
            "prepare_apply_for_saas",
            "filter_space_list_by_action",
            "filter_space_list_by_action_with_scope",
            "make_resource",
            "batch_make_resource",
            "list_actions",
        }
        for name in old_methods:
            assert callable(getattr(Permission, name)), name

    def test_init_with_username_and_tenant(self, fake_framework):
        p = Permission(username="tester", bk_tenant_id="system")
        assert p.username == "tester"
        assert p.bk_tenant_id == "system"
        assert p.skip_check is False

    def test_init_requires_username(self):
        with pytest.raises(ValueError):
            Permission(username="", bk_tenant_id="")

    def test_get_iam_client_shape(self):
        """get_iam_client 返回 V3Client（替代旧 CompatibleIAM），系统/租户一致。"""
        client = Permission.get_iam_client("system")
        assert isinstance(client, V3Client)
        assert client._system_id == "bk_monitorv3"
        # 租户透传（SDK 层 client 保存）
        client2 = Permission.get_iam_client("other_tenant")
        assert client2._client._bk_tenant_id == "other_tenant"

    def test_default_tenant_is_system(self):
        """租户概念核对：无 request 时的默认租户为 DEFAULT_TENANT_ID="system"，
        与 config/default.py 的 IAM_FRAMEWORK.PROVIDERS[0].options.bk_tenant_id="system" 一致。"""
        from constants.common import DEFAULT_TENANT_ID

        assert DEFAULT_TENANT_ID == "system"
        p = Permission(username="tester", bk_tenant_id="system")
        assert p.bk_tenant_id == "system"


# ---------------------------------------------------------------------------
# is_allowed
# ---------------------------------------------------------------------------


class TestIsAllowed:
    def test_action_enum_passes_business_id(self, fake_framework):
        fw, provider = fake_framework
        provider.is_allowed_result = True
        p = Permission(username="tester", bk_tenant_id="system")
        assert p.is_allowed(ActionEnum.VIEW_BUSINESS, [ResourceEnum.BUSINESS.create_simple_instance("2")]) is True
        req: AuthRequest = provider.is_allowed_calls[0]
        assert req.action_id == "view_business"
        assert req.resource.type == "space"
        assert req.resource.id == "2"
        assert req.subject.id == "tester"
        assert req.subject.tenant_id == "system"

    def test_legacy_v3_id_is_normalized_before_framework(self, fake_framework):
        """旧前端传入 V3 平台 ID 时，Framework 只能收到业务 ID。"""
        fw, provider = fake_framework
        provider.is_allowed_result = True
        p = Permission(username="tester", bk_tenant_id="system")

        assert p.is_allowed("view_business_v2", [ResourceEnum.BUSINESS.create_simple_instance("2")]) is True

        req: AuthRequest = provider.is_allowed_calls[0]
        assert req.action_id == "view_business"

    def test_legacy_v3_id_string_same_decision(self, fake_framework, real_schema, v3_provider_factory):
        """前端以 V3 平台 ID 字符串（view_business_v2）调用 is_allowed 时，
        新版路径经 codec 恒等回退后仍以正确的 V3 action 发起请求（与旧版一致）。"""
        provider, mock_client = v3_provider_factory()
        # 让 provider 走真实 dialect：action=view_business_v2（前端传入原样透传）
        from bkmonitor.iam.iam_engine.provider.dialect_types import DialectAuthRequest, DialectResource
        from bkmonitor.iam.iam_engine.core.types import Subject

        mock_client.is_allowed_with_cache.return_value = True
        req = DialectAuthRequest(
            subject=Subject(id="u", tenant_id="system"),
            action_id="view_business_v2",
            resource=DialectResource(type="space", id="2"),
        )
        assert provider._is_allowed_dialect(req) is True
        # 发给 SDK 的 action 仍是 V3 平台 ID
        assert mock_client.make_request.call_args.args[1] == "view_business_v2"
        # 读操作走缓存
        mock_client.is_allowed_with_cache.assert_called_once()

    def test_legacy_v3_id_roundtrips_through_facade_and_v3_codec(self, installed_framework, v3_provider_factory):
        """旧前端 ID 先归一化，随后由 v3 codec 重新编码为正确的平台 ID。"""
        provider, mock_client = v3_provider_factory()
        installed_framework.build([provider])
        mock_client.is_allowed_with_cache.return_value = True
        p = Permission(username="tester", bk_tenant_id="system")

        assert p.is_allowed("view_business_v2", [ResourceEnum.BUSINESS.create_simple_instance("2")]) is True

        assert mock_client.make_request.call_args.args[1] == "view_business_v2"
        mock_client.is_allowed_with_cache.assert_called_once()

    def test_write_action_no_cache(self, real_schema, v3_provider_factory):
        from bkmonitor.iam.iam_engine.provider.dialect_types import DialectAuthRequest, DialectResource
        from bkmonitor.iam.iam_engine.core.types import Subject

        provider, mock_client = v3_provider_factory()
        mock_client.is_allowed.return_value = False
        req = DialectAuthRequest(
            subject=Subject(id="u", tenant_id="system"),
            action_id="manage_event_v2",
            resource=DialectResource(type="space", id="2"),
        )
        assert provider._is_allowed_dialect(req) is False
        mock_client.is_allowed.assert_called_once()
        mock_client.is_allowed_with_cache.assert_not_called()

    def test_denied_with_raise_exception(self, fake_framework):
        fw, provider = fake_framework
        provider.is_allowed_result = False
        provider.apply_url = "http://iam.invalid/apply/1"
        provider.apply_data = {"system": "bk_monitorv3", "actions": []}
        p = Permission(username="tester", bk_tenant_id="system")
        with pytest.raises(PermissionDeniedError) as exc:
            p.is_allowed(
                ActionEnum.VIEW_BUSINESS, [ResourceEnum.BUSINESS.create_simple_instance("2")], raise_exception=True
            )
        assert exc.value.data.get("apply_url") == "http://iam.invalid/apply/1"
        assert exc.value.extra.get("permission") == {"system": "bk_monitorv3", "actions": []}

    def test_denied_no_raise_returns_false(self, fake_framework):
        fw, provider = fake_framework
        provider.is_allowed_result = False
        p = Permission(username="tester", bk_tenant_id="system")
        assert p.is_allowed(ActionEnum.VIEW_BUSINESS, raise_exception=False) is False

    def test_skip_check_short_circuits(self, fake_framework):
        fw, provider = fake_framework
        provider.is_allowed_result = False
        p = Permission(username="tester", bk_tenant_id="system")
        p.skip_check = True
        assert p.is_allowed(ActionEnum.VIEW_BUSINESS) is True
        assert provider.is_allowed_calls == []

    def test_multi_resource_routes_to_batch_by_resource(self, fake_framework):
        """守护修复：多资源同类型必须走 framework.batch_by_resource，不再退化到 is_allowed 的第一项。

        修复前旧实现只取 resources[0] 调 is_allowed 单点鉴权，导致后续资源
        被静默漏检；修复后走批量鉴权，全部允许才判 True。
        """
        from bkmonitor.iam.iam_engine.core.types import BatchAuthResult, ResourceAuthResult

        fw, provider = fake_framework
        # 全部资源都允许
        provider.batch_result = BatchAuthResult(
            items=(
                ResourceAuthResult(action_id="view_business", resource_type="space", resource_id="2", allowed=True),
                ResourceAuthResult(action_id="view_business", resource_type="space", resource_id="3", allowed=True),
            )
        )
        p = Permission(username="tester", bk_tenant_id="system")
        resources = [
            ResourceEnum.BUSINESS.create_simple_instance("2"),
            ResourceEnum.BUSINESS.create_simple_instance("3"),
        ]
        assert p.is_allowed(ActionEnum.VIEW_BUSINESS, resources) is True
        # 关键守护：多资源分支不能退化到调 is_allowed（否则又会只看第一项）
        assert provider.is_allowed_calls == [], (
            "多资源鉴权必须走 batch_by_resource，不允许退化为对 resources[0] 的单点 is_allowed"
        )

    def test_token_bypass_parity(self, fake_framework):
        """token 临时分享豁免逻辑与旧版一致（业务查看动作直接豁免）。"""
        from bkmonitor.models import ApiAuthToken

        fw, provider = fake_framework
        request = MagicMock()
        request.token = "tok"
        request.path = "/whatever/"
        request.user.username = "tester"
        request.user.tenant_id = "system"
        request.skip_check = False
        with patch("bkmonitor.iam.permission.ApiAuthToken.objects.get", side_effect=ApiAuthToken.DoesNotExist):
            p = Permission(request=request)
            # 业务查看权限：直接豁免（无需查 token 记录）
            assert p.is_allowed(ActionEnum.VIEW_BUSINESS) is True


# ---------------------------------------------------------------------------
# is_allowed_by_biz / batch_is_allowed
# ---------------------------------------------------------------------------


class TestIsAllowedByBiz:
    def test_space_resource_built(self, fake_framework):
        fw, provider = fake_framework
        provider.is_allowed_result = True
        p = Permission(username="tester", bk_tenant_id="system")
        assert p.is_allowed_by_biz(2, ActionEnum.VIEW_EVENT) is True
        req: AuthRequest = provider.is_allowed_calls[0]
        assert req.resource.type == "space"
        assert req.resource.id == "2"

    def test_skip_check(self, fake_framework):
        fw, provider = fake_framework
        p = Permission(username="tester", bk_tenant_id="system")
        p.skip_check = True
        assert p.is_allowed_by_biz(2, ActionEnum.MANAGE_DOWNTIME) is True
        assert provider.is_allowed_calls == []


class TestBatchIsAllowed:
    def test_result_shape_and_business_id_keys(self, fake_framework):
        """结果键：新版为业务 ID（旧版为 V3 平台 ID）。
        现有外部调用方 kernel_api mail_report 使用恒等动作 view_single_dashboard，
        不受影响；其余调用方需按业务 ID 读取。"""
        fw, provider = fake_framework
        from bkmonitor.iam.iam_engine.core.types import BatchAuthResult, ResourceAuthResult

        provider.batch_result = BatchAuthResult(
            items=(
                ResourceAuthResult(action_id="view_event", resource_type="space", resource_id="2", allowed=True),
                ResourceAuthResult(action_id="view_event", resource_type="space", resource_id="3", allowed=False),
            )
        )
        p = Permission(username="tester", bk_tenant_id="system")
        result = p.batch_is_allowed(
            [ActionEnum.VIEW_EVENT],
            [[ResourceEnum.BUSINESS.create_simple_instance("2")], [ResourceEnum.BUSINESS.create_simple_instance("3")]],
        )
        assert result["2"]["view_event"] is True
        assert result["3"]["view_event"] is False

    def test_framework_batch_grouping(self, installed_framework, real_schema):
        """Permission.batch_is_allowed 按资源类型分组后一次批量调用。"""
        from bkmonitor.iam.iam_engine.provider.base import PermissionProvider
        from bkmonitor.iam.iam_engine.core.types import BatchAuthResult, ResourceAuthResult

        class Recorder(PermissionProvider):
            name = "recorder"

            def __init__(self):
                self.batch_calls: list = []

            def batch_by_resource(self, request):
                self.batch_calls.append(request)
                return BatchAuthResult(
                    items=tuple(
                        ResourceAuthResult(
                            action_id=request.action_id, resource_type=r.type, resource_id=r.id, allowed=True
                        )
                        for r in request.resources
                    )
                )

            # ---- PermissionProvider 抽象方言方法：补实现以满足实例化 ----
            def _is_allowed_dialect(self, request):
                raise NotImplementedError

            def _batch_by_resource_dialect_page(self, request):
                raise NotImplementedError

            def _batch_by_action_dialect_page(self, request):
                raise NotImplementedError

            def _get_apply_url_dialect(self, request):
                raise NotImplementedError

            def plan_migration(self, schema, *, scope="full"):
                raise NotImplementedError

            def apply_migration(self, plan, *, dry_run=False, allow_destructive=False):
                raise NotImplementedError

            def health_check(self):
                return {"status": "ok"}

        provider = Recorder()
        _fw = installed_framework.build([provider])
        p = Permission(username="tester", bk_tenant_id="system")
        result = p.batch_is_allowed(
            [ActionEnum.VIEW_EVENT, ActionEnum.MANAGE_EVENT],
            [
                [ResourceEnum.BUSINESS.create_simple_instance("2")],
                [ResourceEnum.BUSINESS.create_simple_instance("3")],
                [ResourceEnum.BUSINESS.create_simple_instance("4")],
            ],
        )
        # 2 actions × 1 类型组 = 2 次批量调用
        assert len(provider.batch_calls) == 2
        assert provider.batch_calls[0].action_id == "view_event"
        assert provider.batch_calls[1].action_id == "manage_event"
        assert {r.id for r in provider.batch_calls[0].resources} == {"2", "3", "4"}
        assert result["2"] == {"view_event": True, "manage_event": True}
        assert result["3"] == {"view_event": True, "manage_event": True}
        assert result["4"] == {"view_event": True, "manage_event": True}

    def test_skip_check_branch(self, fake_framework):
        fw, provider = fake_framework
        p = Permission(username="tester", bk_tenant_id="system")
        p.skip_check = True
        result = p.batch_is_allowed(
            [ActionEnum.VIEW_EVENT],
            [[ResourceEnum.BUSINESS.create_simple_instance("2")]],
        )
        assert result["2"]["view_event"] is True

    def test_legacy_v3_id_is_normalized_and_result_uses_business_key(self, fake_framework):
        from bkmonitor.iam.iam_engine.core.types import BatchAuthResult, ResourceAuthResult

        fw, provider = fake_framework
        provider.batch_by_resource = MagicMock(
            return_value=BatchAuthResult(
                items=(
                    ResourceAuthResult(action_id="view_event", resource_type="space", resource_id="2", allowed=True),
                )
            )
        )
        p = Permission(username="tester", bk_tenant_id="system")

        result = p.batch_is_allowed(
            ["view_event_v2"],
            [[ResourceEnum.BUSINESS.create_simple_instance("2")]],
        )

        request = provider.batch_by_resource.call_args.args[0]
        assert request.action_id == "view_event"
        assert result == {"2": {"view_event": True}}

    def test_skip_check_legacy_v3_id_result_uses_business_key(self, fake_framework):
        fw, provider = fake_framework
        p = Permission(username="tester", bk_tenant_id="system")
        p.skip_check = True

        result = p.batch_is_allowed(
            ["view_event_v2"],
            [[ResourceEnum.BUSINESS.create_simple_instance("2")]],
        )

        assert result == {"2": {"view_event": True}}


# ---------------------------------------------------------------------------
# apply url / apply data / 空间列表过滤 / make_resource
# ---------------------------------------------------------------------------


class TestApplyMethods:
    def test_get_apply_url(self, fake_framework):
        fw, provider = fake_framework
        provider.apply_url = "http://iam.invalid/apply/xyz"
        p = Permission(username="tester", bk_tenant_id="system")
        url = p.get_apply_url(["view_business"], [ResourceEnum.BUSINESS.create_simple_instance("2")])
        assert url == "http://iam.invalid/apply/xyz"

    def test_get_apply_data(self, fake_framework):
        fw, provider = fake_framework
        provider.apply_data = {"system": "bk_monitorv3", "actions": [{"id": "view_business"}]}
        provider.apply_url = "http://iam.invalid/apply/xyz"
        p = Permission(username="tester", bk_tenant_id="system")
        data, url = p.get_apply_data([ActionEnum.VIEW_BUSINESS], [ResourceEnum.BUSINESS.create_simple_instance("2")])
        assert data == {"system": "bk_monitorv3", "actions": [{"id": "view_business"}]}
        assert url == "http://iam.invalid/apply/xyz"

    def test_get_apply_data_accepts_v3_platform_id_string(self, fake_framework):
        """前端 V3 ID 字符串在申请路径进入 Framework 前归一化为业务 ID。"""
        fw, provider = fake_framework
        provider.get_apply_data = MagicMock(return_value={"system": "bk_monitorv3", "actions": []})
        provider.get_apply_url = MagicMock(return_value="http://iam.invalid/apply/xyz")
        p = Permission(username="tester", bk_tenant_id="system")
        data, url = p.get_apply_data(["view_business_v2"], [ResourceEnum.BUSINESS.create_simple_instance("2")])
        assert data == {"system": "bk_monitorv3", "actions": []}
        assert url == "http://iam.invalid/apply/xyz"
        assert provider.get_apply_data.call_args.args[0] == ["view_business"]
        assert provider.get_apply_url.call_args.args[0].action_ids == ("view_business",)


class TestFilterSpaceListByAction:
    def _space_list(self):
        return [
            {"bk_biz_id": 2, "space_name": "A"},
            {"bk_biz_id": 3, "space_name": "B"},
            {"bk_biz_id": 5, "space_name": "C"},
        ]

    def test_all_granted(self, fake_framework):
        fw, provider = fake_framework
        provider.visible = VisibleResult(all_granted=True, visible_ids=("2", "3", "5"))
        p = Permission(username="tester", bk_tenant_id="system")
        with patch("bkmonitor.iam.permission.SpaceApi.list_spaces_dict", return_value=self._space_list()):
            result = p.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS)
        assert len(result) == 3

    def test_with_scope_reports_all_granted(self, fake_framework):
        fw, provider = fake_framework
        provider.visible = VisibleResult(all_granted=True, visible_ids=("2", "3", "5"))
        p = Permission(username="tester", bk_tenant_id="system")
        with patch("bkmonitor.iam.permission.SpaceApi.list_spaces_dict", return_value=self._space_list()):
            spaces, tenant_wide_authorized = p.filter_space_list_by_action_with_scope(ActionEnum.VIEW_BUSINESS)

        assert [space["bk_biz_id"] for space in spaces] == [2, 3, 5]
        assert tenant_wide_authorized is True

    def test_visible_ids_filter(self, fake_framework):
        fw, provider = fake_framework
        provider.visible = VisibleResult(all_granted=False, visible_ids=("2", "5"))
        p = Permission(username="tester", bk_tenant_id="system")
        with patch("bkmonitor.iam.permission.SpaceApi.list_spaces_dict", return_value=self._space_list()):
            result = p.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS)
        assert [s["bk_biz_id"] for s in result] == [2, 5]

    def test_with_scope_reports_partial_authorization(self, fake_framework):
        fw, provider = fake_framework
        provider.visible = VisibleResult(all_granted=False, visible_ids=("2", "5"))
        p = Permission(username="tester", bk_tenant_id="system")
        with patch("bkmonitor.iam.permission.SpaceApi.list_spaces_dict", return_value=self._space_list()):
            spaces, tenant_wide_authorized = p.filter_space_list_by_action_with_scope(ActionEnum.VIEW_BUSINESS)

        assert [space["bk_biz_id"] for space in spaces] == [2, 5]
        assert tenant_wide_authorized is False

    def test_legacy_v3_id_is_normalized_before_visible_resource_query(self, fake_framework):
        fw, provider = fake_framework
        provider.filter_visible_resources = MagicMock(
            return_value=VisibleResult(all_granted=False, visible_ids=("2", "5"))
        )
        p = Permission(username="tester", bk_tenant_id="system")

        with patch("bkmonitor.iam.permission.SpaceApi.list_spaces_dict", return_value=self._space_list()):
            result = p.filter_space_list_by_action("view_business_v2")

        assert [space["bk_biz_id"] for space in result] == [2, 5]
        assert provider.filter_visible_resources.call_args.args[1] == "view_business"

    def test_provider_error_returns_empty(self, fake_framework):
        fw, provider = fake_framework
        from bkmonitor.iam.iam_engine.core.exceptions import ProviderError

        def _boom(subject, action_id, candidates):
            raise ProviderError("backend down")

        provider.filter_visible_resources = _boom
        p = Permission(username="tester", bk_tenant_id="system")
        with patch("bkmonitor.iam.permission.SpaceApi.list_spaces_dict", return_value=self._space_list()):
            result = p.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS)
        assert result == []

    def test_with_scope_provider_error_is_not_tenant_wide(self, fake_framework):
        fw, provider = fake_framework
        from bkmonitor.iam.iam_engine.core.exceptions import ProviderError

        def _boom(subject, action_id, candidates):
            raise ProviderError("backend down")

        provider.filter_visible_resources = _boom
        p = Permission(username="tester", bk_tenant_id="system")
        with patch("bkmonitor.iam.permission.SpaceApi.list_spaces_dict", return_value=self._space_list()):
            spaces, tenant_wide_authorized = p.filter_space_list_by_action_with_scope(ActionEnum.VIEW_BUSINESS)

        assert spaces == []
        assert tenant_wide_authorized is False

    def test_skip_check(self, fake_framework):
        fw, provider = fake_framework
        p = Permission(username="tester", bk_tenant_id="system")
        p.skip_check = True
        with patch("bkmonitor.iam.permission.SpaceApi.list_spaces_dict", return_value=self._space_list()):
            result = p.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS)
        assert len(result) == 3

    def test_with_scope_skip_check_is_tenant_wide(self, fake_framework):
        fw, provider = fake_framework
        p = Permission(username="tester", bk_tenant_id="system")
        p.skip_check = True
        with patch("bkmonitor.iam.permission.SpaceApi.list_spaces_dict", return_value=self._space_list()):
            spaces, tenant_wide_authorized = p.filter_space_list_by_action_with_scope(ActionEnum.VIEW_BUSINESS)

        assert [space["bk_biz_id"] for space in spaces] == [2, 3, 5]
        assert tenant_wide_authorized is True


class TestLegacyFrontendResourceCompatibility:
    def test_check_allowed_by_action_ids_echoes_original_legacy_id(self):
        """内部归一化不能改变前端按原请求 ID 匹配响应的既有契约。"""
        from monitor_web.iam.resources import CheckAllowedByActionIdsResource

        permission = MagicMock()
        permission.is_allowed_by_biz.return_value = True
        with patch("monitor_web.iam.resources.Permission", return_value=permission):
            result = CheckAllowedByActionIdsResource().perform_request(
                {"bk_biz_id": 2, "action_ids": ["view_business_v2"]}
            )

        permission.is_allowed_by_biz.assert_called_once_with(2, "view_business_v2", raise_exception=False)
        assert result == [{"action_id": "view_business_v2", "is_allowed": True}]


class TestMakeResource:
    def test_make_resource(self):
        r = Permission.make_resource("space", "2")
        assert isinstance(r, FwResource)
        assert r.type == "space"
        assert r.id == "2"

    def test_batch_make_resource(self):
        resources = Permission.batch_make_resource(
            [{"type": "space", "id": "2"}, {"type": "apm_application", "id": "app-1"}]
        )
        assert [r.type for r in resources] == ["space", "apm_application"]
        assert [r.id for r in resources] == ["2", "app-1"]

    def test_unknown_type_no_longer_validated(self):
        """已知行为差异：旧版 make_resource 对未知资源类型抛 ResourceNotExistError；
        新版不再校验（直接构造 FwResource）。全仓调用方均为已知类型，无实际影响。"""
        r = Permission.make_resource("no_such_type", "1")
        assert r.type == "no_such_type"


# ---------------------------------------------------------------------------
# 已发现回归点（xfail 记录，测试结果即为证据）
#
# 注：DRF 权限类 request.skip_check 回归点已按方案 A 修复（共享前置豁免 helper），
# 对应验证用例移入 test_drf_parity.py::TestDrfPreflight。
# ---------------------------------------------------------------------------


class TestPreflightHelpers:
    """check_iam_preflight / check_iam_batch_preflight 的兼容豁免与安全修复。"""

    def test_preflight_none_request_uses_settings(self):
        from bkmonitor.iam.permission import check_iam_preflight

        with patch("bkmonitor.iam.permission.settings.SKIP_IAM_PERMISSION_CHECK", True):
            assert check_iam_preflight(None, ActionEnum.VIEW_BUSINESS) is True
        with patch("bkmonitor.iam.permission.settings.SKIP_IAM_PERMISSION_CHECK", False):
            assert check_iam_preflight(None, ActionEnum.VIEW_BUSINESS) is False

    def test_preflight_request_skip_check_true(self):
        from bkmonitor.iam.permission import check_iam_preflight

        request = MagicMock()
        request.skip_check = True
        request.token = None  # 显式置 None：MagicMock 自动属性会误入 token 分支
        request.path = "/whatever/"
        assert check_iam_preflight(request, ActionEnum.VIEW_BUSINESS) is True

    def test_preflight_request_skip_check_false_overrides_settings(self):
        """request.skip_check=False 显式强制校验时覆盖 settings 级（与 Permission.__init__ 一致）。"""
        from bkmonitor.iam.permission import check_iam_preflight

        request = MagicMock()
        request.skip_check = False
        request.token = None  # 显式置 None：MagicMock 自动属性会误入 token 分支
        request.path = "/whatever/"
        with patch("bkmonitor.iam.permission.settings.SKIP_IAM_PERMISSION_CHECK", True):
            assert check_iam_preflight(request, ActionEnum.VIEW_BUSINESS) is False

    def test_preflight_skip_check_param_passthrough(self):
        """Permission.is_allowed 传入实例值 self.skip_check（兼容调用方构造后修改实例属性）。"""
        from bkmonitor.iam.permission import check_iam_preflight

        assert check_iam_preflight(None, ActionEnum.VIEW_BUSINESS, skip_check=True) is True
        assert check_iam_preflight(None, ActionEnum.VIEW_BUSINESS, skip_check=False) is False

    def test_preflight_token_no_record_is_not_bypassed(self):
        """Token 记录不存在时不再因旧 generator 恒真问题被放行。"""
        from bkmonitor.models import ApiAuthToken
        from bkmonitor.iam.permission import check_iam_preflight

        request = MagicMock()
        request.token = "tok"
        request.path = "/any/path/"
        request.skip_check = False
        request.user.tenant_id = "system"
        with patch("bkmonitor.iam.permission.ApiAuthToken.objects.get", side_effect=ApiAuthToken.DoesNotExist):
            assert check_iam_preflight(request, ActionEnum.VIEW_EVENT) is False

    def test_preflight_token_action_id_map_accepts_string_action(self):
        """Token 动作匹配按 action ID 执行，ActionEnum 与字符串调用语义一致。"""
        from bkmonitor.iam.permission import check_iam_preflight

        request = MagicMock()
        request.token = "tok"
        request.path = "/any/path/"
        request.skip_check = False
        request.user.tenant_id = "system"
        record = MagicMock()
        record.type = "host"
        with patch("bkmonitor.iam.permission.ApiAuthToken.objects.get", return_value=record):
            assert check_iam_preflight(request, "view_host") is True

    def test_preflight_token_action_id_map_accepts_legacy_alias(self):
        from bkmonitor.iam.permission import check_iam_preflight

        request = MagicMock()
        request.token = "tok"
        request.path = "/any/path/"
        request.skip_check = False
        request.user.tenant_id = "system"
        record = MagicMock()
        record.type = "host"
        with patch("bkmonitor.iam.permission.ApiAuthToken.objects.get", return_value=record):
            assert check_iam_preflight(request, "view_host_v2") is True

    def test_preflight_no_exemption_goes_to_framework(self):
        from bkmonitor.iam.permission import check_iam_preflight

        request = MagicMock()
        request.skip_check = False
        request.token = None  # 显式置 None：MagicMock 自动属性会误入 token 分支
        request.path = "/whatever/"
        assert check_iam_preflight(request, ActionEnum.VIEW_EVENT) is False

    def test_batch_preflight_skip_all_true(self):
        from bkmonitor.iam.permission import check_iam_batch_preflight

        request = MagicMock()
        request.skip_check = True
        request.token = None  # 显式置 None：MagicMock 自动属性会误入 token 分支
        result = check_iam_batch_preflight(request, [ActionEnum.VIEW_EVENT, ActionEnum.MANAGE_EVENT])
        assert result == {"view_event": True, "manage_event": True}

    def test_batch_preflight_skip_legacy_alias_uses_business_key(self):
        from bkmonitor.iam.permission import check_iam_batch_preflight

        request = MagicMock()
        request.skip_check = True
        request.token = None
        result = check_iam_batch_preflight(request, ["view_event_v2"])
        assert result == {"view_event": True}

    def test_batch_preflight_none(self):
        from bkmonitor.iam.permission import check_iam_batch_preflight

        request = MagicMock()
        request.skip_check = False
        request.token = None  # 显式置 None：MagicMock 自动属性会误入 token 分支
        assert check_iam_batch_preflight(request, [ActionEnum.VIEW_EVENT]) is None

    def test_batch_preflight_token_no_record_raises(self):
        """batch 语义：token 记录不存在 → 抛 TokenValidatedError（与旧版 batch_is_allowed 一致）。"""
        from bkmonitor.models import ApiAuthToken
        from bkmonitor.iam.permission import check_iam_batch_preflight
        from core.errors.share import TokenValidatedError

        request = MagicMock()
        request.token = "tok"
        request.user.tenant_id = "system"
        with patch("bkmonitor.iam.permission.ApiAuthToken.objects.get", side_effect=ApiAuthToken.DoesNotExist):
            with pytest.raises(TokenValidatedError):
                check_iam_batch_preflight(request, [ActionEnum.VIEW_EVENT])

    def test_batch_preflight_token_action_id_map(self):
        from bkmonitor.iam.permission import check_iam_batch_preflight

        request = MagicMock()
        request.token = "tok"
        request.user.tenant_id = "system"
        record = MagicMock()
        record.type = "host"  # ActionIdMap["host"] = [ActionEnum.VIEW_HOST]
        with patch("bkmonitor.iam.permission.ApiAuthToken.objects.get", return_value=record):
            result = check_iam_batch_preflight(request, ["view_host", "view_event"])
        assert result == {"view_host": True, "view_event": False}

    def test_batch_preflight_token_action_id_map_accepts_legacy_alias(self):
        from bkmonitor.iam.permission import check_iam_batch_preflight

        request = MagicMock()
        request.token = "tok"
        request.user.tenant_id = "system"
        record = MagicMock()
        record.type = "host"
        with patch("bkmonitor.iam.permission.ApiAuthToken.objects.get", return_value=record):
            result = check_iam_batch_preflight(request, ["view_host_v2", "view_event_v2"])
        assert result == {"view_host": True, "view_event": False}


class TestKnownRegressions:
    """本次回归修复的守卫用例：list_actions + is_allowed 多资源静默漏检。"""

    def test_list_actions_returns_action_list(self, installed_framework):
        """list_actions 应从 SchemaRegistry 生成动作列表（含旧版兼容字段）。

        与旧版 IAM V3 model.actions 契约对齐：每项含 id / name / name_en / type /
        version / related_resource_types / related_actions / description。
        """
        result = Permission(username="tester", bk_tenant_id="system").list_actions()
        assert isinstance(result, list)
        assert len(result) > 0

        first = result[0]
        for key in ("id", "name", "name_en", "type", "version", "related_resource_types", "related_actions"):
            assert key in first, f"list_actions 缺少兼容字段 {key!r}: {first}"

        # 抽样断言：view_business 的 v3 兼容字段来自 extensions.v3
        view_business = next((a for a in result if a["id"] == "view_business"), None)
        assert view_business is not None, "SchemaRegistry 应包含 view_business"
        assert view_business["type"] == "view"
        assert view_business["version"] == 1
        assert view_business["related_resource_types"], "view_business 关联 space，应有一条 related_resource_types"

    def test_is_allowed_multi_resource_partial_deny(self, fake_framework):
        """回归：多资源同类型鉴权，第一项允许、第二项拒绝时整体必须 False。

        旧实现只取 resources[0]，会把上述场景误判为 True 并静默漏检后续资源。
        修复后走 framework.batch_by_resource，任一资源被拒即整体 False。
        """
        from bkmonitor.iam.iam_engine.core.types import BatchAuthResult, ResourceAuthResult

        fw, provider = fake_framework
        provider.batch_result = BatchAuthResult(
            items=(
                ResourceAuthResult(action_id="view_business", resource_type="space", resource_id="2", allowed=True),
                ResourceAuthResult(action_id="view_business", resource_type="space", resource_id="3", allowed=False),
            )
        )
        p = Permission(username="tester", bk_tenant_id="system")

        resources = [
            ResourceEnum.BUSINESS.create_simple_instance("2"),
            ResourceEnum.BUSINESS.create_simple_instance("3"),
        ]
        # raise_exception=False：不抛错但必须返回 False
        assert p.is_allowed(ActionEnum.VIEW_BUSINESS, resources) is False

        # raise_exception=True：抛 PermissionDeniedError，且 context 归属被拒的动作
        with pytest.raises(PermissionDeniedError):
            p.is_allowed(ActionEnum.VIEW_BUSINESS, resources, raise_exception=True)

    def test_is_allowed_multi_resource_all_hit(self, fake_framework):
        """多资源同类型全部允许 → 整体 True。"""
        from bkmonitor.iam.iam_engine.core.types import BatchAuthResult, ResourceAuthResult

        fw, provider = fake_framework
        provider.batch_result = BatchAuthResult(
            items=(
                ResourceAuthResult(action_id="view_business", resource_type="space", resource_id="2", allowed=True),
                ResourceAuthResult(action_id="view_business", resource_type="space", resource_id="3", allowed=True),
            )
        )
        p = Permission(username="tester", bk_tenant_id="system")

        resources = [
            ResourceEnum.BUSINESS.create_simple_instance("2"),
            ResourceEnum.BUSINESS.create_simple_instance("3"),
        ]
        assert p.is_allowed(ActionEnum.VIEW_BUSINESS, resources) is True

    def test_is_allowed_mixed_resource_types_raises(self, fake_framework):
        """混合资源类型必须显式拒绝：Permission.is_allowed 不接受隐式混合。"""
        p = Permission(username="tester", bk_tenant_id="system")

        resources = [
            ResourceEnum.BUSINESS.create_simple_instance("2"),
            ResourceEnum.APM_APPLICATION.create_simple_instance("app-1"),
        ]
        with pytest.raises(ValueError, match="混合资源类型"):
            p.is_allowed(ActionEnum.VIEW_BUSINESS, resources)


# ---------------------------------------------------------------------------
# 新旧鉴权路径一致性（核心对照）
# ---------------------------------------------------------------------------


def _mock_http(policy_map, batch_map=None):
    """构造 IAM SDK 层 mock http 客户端。

    policy_map: dict action_id -> policy dict（None 表示无策略）
    对 _v2 action 的 V1 双查：自动以去掉 _v2 后缀的 action 查 policy_map。
    """
    http = MagicMock()

    def _policy_query(data):
        action_id = data.get("action", {}).get("id", "")
        if action_id in policy_map:
            return True, "", copy.deepcopy(policy_map[action_id])
        # V1 双查：去掉 _v2 后缀再查
        if action_id.endswith("_v2"):
            v1_id = action_id[:-3]
            if v1_id in policy_map:
                return True, "", copy.deepcopy(policy_map[v1_id])
        return True, "", {}

    def _policy_query_by_actions(data):
        items = []
        for act in data.get("actions", []):
            aid = act["id"]
            if aid in policy_map:
                items.append({"action": {"id": aid}, "condition": copy.deepcopy(policy_map[aid])})
            elif aid.endswith("_v2") and aid[:-3] in policy_map:
                items.append({"action": {"id": aid}, "condition": copy.deepcopy(policy_map[aid[:-3]])})
            else:
                items.append({"action": {"id": aid}, "condition": {}})
        return True, "", items

    http.policy_query.side_effect = _policy_query
    http.policy_query_by_actions.side_effect = _policy_query_by_actions
    return http


def _new_provider_with_http(real_schema, http, codec_kwargs=None):
    from bkmonitor.iam.iam_v3.provider import V3PermissionProvider
    from .conftest import build_v3_options

    options = build_v3_options()
    # 对照用例禁用 resolver：避免 DB/API 补全干扰载荷对照
    # （resolver 行为由 test_resource_interface 单独覆盖）
    options.pop("resolver_class", None)
    if codec_kwargs:
        options["codec_kwargs"] = codec_kwargs
    provider = V3PermissionProvider(real_schema, **options)
    client = V3Client(
        "test_app",
        "test_secret",
        "https://iam.invalid/",
        system_id="bk_monitorv3",
        codec=provider.codec,
        bk_tenant_id="system",
    )
    client._client = http
    provider._get_client = MagicMock(return_value=client)  # type: ignore[method-assign]
    return provider, client


def _new_auth_request(username, action_ref, resource_type, resource_id, tenant="system"):
    resource = None
    if resource_type is not None:
        resource = FwResource(type=resource_type, id=resource_id)
    return AuthRequest(
        subject=FwSubject(id=username, type=SubjectType.USER, tenant_id=tenant),
        action_id=action_ref,
        resource=resource,
    )


def _normalize_payload(data: dict) -> dict:
    """归一化 SDK policy_query 载荷：去掉 attribute（名称补全属实现细节）。"""
    out = copy.deepcopy(data)
    for r in out.get("resources", []):
        r.pop("attribute", None)
    return out


class TestAuthPathParity:
    """同一 mock 服务器下，旧路径与新增路径的请求载荷与判定结果一致性。"""

    # (action_business_id, v3_action_id, resource_type, resource_id, is_read)
    CASES = [
        ("view_business", "view_business_v2", "space", "2", True),
        ("view_event", "view_event_v2", "space", "2", True),
        ("manage_event", "manage_event_v2", "space", "2", False),
        ("view_incident", "view_incident", "space", "2", True),  # 恒等 ID
        ("manage_global_setting", "manage_global_setting", None, None, False),  # 无资源
        ("view_apm_application", "view_apm_application_v2", "apm_application", "app-1", True),
    ]

    @pytest.mark.parametrize("biz_action,v3_action,rt,rid,is_read", CASES)
    def test_single_is_allowed_parity(self, real_schema, biz_action, v3_action, rt, rid, is_read):
        policy = {"op": "eq", "field": "space.id", "value": rid} if rt else {"op": "any", "field": "", "value": []}
        http = _mock_http({v3_action: policy})
        legacy_client = LegacyIAM("a", "s", "https://iam.invalid/", "bk_monitorv3", bk_tenant_id="system")
        legacy_client._client = http

        resources = [legacy_make_resource(rt, rid)] if rt else []
        legacy_allowed = legacy_eval_decision(legacy_client, "tester", v3_action, resources, is_read)

        provider, client = _new_provider_with_http(real_schema, http)
        new_allowed = provider.is_allowed(_new_auth_request("tester", biz_action, rt, rid))

        assert new_allowed == legacy_allowed, (biz_action, legacy_allowed, new_allowed)

        # 载荷一致性：主查询（第一次 policy_query）action/资源/主体一致。
        # 注意1：SDK is_allowed_with_cache 是类级 TTL 缓存，载荷抓取必须用
        #       不同用户名避免命中同一缓存条目。
        # 注意2：调用记录在 http.policy_query.call_args_list（子属性），且 V1 双查
        #       会产生 v2/v1 两次调用，必须取 [0]（v2 主查询）；http.call_args_list
        #       记录的是对 mock 本身的调用（恒空），call_args 是最后一次调用（v1）。
        legacy_payload = _normalize_payload(http.policy_query.call_args_list[0].args[0])
        http2 = _mock_http({v3_action: policy})
        _provider2, client2 = _new_provider_with_http(real_schema, http2)
        _provider2.is_allowed(_new_auth_request("tester_payload", biz_action, rt, rid))
        new_payload = _normalize_payload(http2.policy_query.call_args_list[0].args[0])

        assert new_payload["action"]["id"] == legacy_payload["action"]["id"] == v3_action
        # subject 抓取用了独立用户名（避开 is_allowed_with_cache 的类级 TTL 缓存）
        assert legacy_payload["subject"]["id"] == "tester"
        assert new_payload["subject"]["id"] == "tester_payload"
        new_res = new_payload.get("resources", [])
        legacy_res = legacy_payload.get("resources", [])
        assert len(new_res) == len(legacy_res)
        for nr, lr in zip(new_res, legacy_res):
            assert nr["system"] == lr["system"] == "bk_monitorv3"
            assert nr["type"] == lr["type"]
            assert nr["id"] == lr["id"]

    def test_v1_dual_query_payload_parity(self, real_schema):
        """V1 双查：_v2 动作会追加一次 V1 查询，且 V1 载荷（biz 资源替换）新旧一致。"""
        v2_policy = {"op": "eq", "field": "space.id", "value": "2"}
        v1_policy = {"op": "eq", "field": "biz.id", "value": "2"}
        http = _mock_http({"view_business_v2": v2_policy, "view_business": v1_policy})

        legacy_client = LegacyIAM("a", "s", "https://iam.invalid/", "bk_monitorv3", bk_tenant_id="system")
        legacy_client._client = http
        legacy_client.is_allowed_with_cache(
            legacy_make_request("legacy_v1_user", "view_business_v2", [legacy_make_resource("space", "2")])
        )
        legacy_calls = [c.args[0] for c in http.policy_query.call_args_list]

        http2 = _mock_http({"view_business_v2": v2_policy, "view_business": v1_policy})
        provider, client = _new_provider_with_http(real_schema, http2)
        provider.is_allowed(_new_auth_request("new_v1_user", "view_business", "space", "2"))
        new_calls = [c.args[0] for c in http2.policy_query.call_args_list]

        assert len(new_calls) == len(legacy_calls) == 2
        # V1 查询载荷：action 去掉 _v2、space→biz、system→bk_cmdb
        legacy_v1 = _normalize_payload(legacy_calls[1])
        new_v1 = _normalize_payload(new_calls[1])
        assert new_v1["action"]["id"] == legacy_v1["action"]["id"] == "view_business"
        assert new_v1["resources"][0]["type"] == legacy_v1["resources"][0]["type"] == "biz"
        assert new_v1["resources"][0]["system"] == legacy_v1["resources"][0]["system"] == "bk_cmdb"

    def test_alias_parity_new_dashboard(self, real_schema):
        """new_dashboard 语义别名：新旧都 OR 合并 manage_dashboard_v2 / manage_datasource_v2 策略。"""
        http = _mock_http(
            {
                "new_dashboard": {"op": "eq", "field": "space.id", "value": "999"},  # 主查询拒绝
                "manage_dashboard_v2": {"op": "any", "field": "", "value": []},  # 别名放行（平台 any 格式）
                "manage_datasource_v2": {},
            }
        )
        legacy_client = LegacyIAM("a", "s", "https://iam.invalid/", "bk_monitorv3", bk_tenant_id="system")
        legacy_client._client = http
        legacy_allowed = legacy_client.is_allowed(
            legacy_make_request("tester", "new_dashboard", [legacy_make_resource("space", "2")])
        )

        http2 = _mock_http(
            {
                "new_dashboard": {"op": "eq", "field": "space.id", "value": "999"},
                "manage_dashboard_v2": {"op": "any", "field": "", "value": []},
                "manage_datasource_v2": {},
            }
        )
        provider, client = _new_provider_with_http(real_schema, http2)
        new_allowed = provider.is_allowed(_new_auth_request("tester", "new_dashboard", "space", "2"))

        assert legacy_allowed is True  # OR 合并后放行
        assert new_allowed == legacy_allowed
        # 调用次数一致（主查询 + 别名各含 V2/V1 双查）
        assert len(http2.policy_query.call_args_list) == len(http.policy_query.call_args_list)
        assert len(http2.policy_query.call_args_list) >= 3

    def test_batch_policy_query_parity(self, real_schema):
        """批量策略查询（_do_policy_query_by_actions）：新旧合并 V1 条件的逻辑一致。"""
        http = _mock_http({"view_business_v2": {"op": "eq", "field": "space.id", "value": "2"}})
        legacy_client = LegacyIAM("a", "s", "https://iam.invalid/", "bk_monitorv3", bk_tenant_id="system")
        legacy_client._client = http
        legacy_req = MultiActionRequest(
            system="bk_monitorv3",
            subject=SdkSubject("user", "tester"),
            actions=[SdkAction(id="view_business_v2")],
            resources=[],
            environment=None,
        )
        legacy_result = legacy_client._do_policy_query_by_actions(legacy_req, with_resources=False)
        legacy_v1_merged = legacy_result[0]["condition"]

        http2 = _mock_http({"view_business_v2": {"op": "eq", "field": "space.id", "value": "2"}})
        provider, client = _new_provider_with_http(real_schema, http2)
        new_req = client.make_multi_action_request("tester", ["view_business_v2"])
        new_result = client._do_policy_query_by_actions(new_req, with_resources=False)
        new_v1_merged = new_result[0]["condition"]

        assert new_v1_merged == legacy_v1_merged

    def test_filter_visible_resources_parity(self, real_schema):
        """空间列表过滤：新旧对同一策略表达式的过滤结果一致。"""
        from bkmonitor.iam.iam_engine.core.types import VisibleResult as VR

        for policy, expected in [
            ({"op": "any"}, {"all": True}),
            ({"op": "in", "field": "space.id", "value": ["2", "5"]}, {"visible": ["2", "5"]}),
            ({"op": "eq", "field": "space.id", "value": "2"}, {"visible": ["2"]}),
            ({"op": "in", "field": "biz.id", "value": ["2"]}, {"visible": []}),  # V1 表达式未 patch 时不可见
        ]:
            http = _mock_http({"view_business_v2": policy})
            provider, client = _new_provider_with_http(real_schema, http)
            result: VR = provider.filter_visible_resources(
                FwSubject(id="tester", tenant_id="system"),
                "view_business",
                tuple(FwResource(type="space", id=i) for i in ("2", "3", "5")),
            )
            if "all" in expected:
                assert result.all_granted is True
            else:
                assert result.all_granted is False
                assert list(result.visible_ids) == expected["visible"]

    def test_legacy_compat_dual_query_matches_v3_client(self, real_schema):
        """LegacyCompatibleIAM（旧 compatible.py 参考实现）与新版 V3Client 的
        _do_policy_query 调用序列一致（含 V1 双查 + 别名）。"""
        http = _mock_http(
            {
                "view_business_v2": {"op": "eq", "field": "space.id", "value": "2"},
                "view_business": {"op": "eq", "field": "biz.id", "value": "2"},
            }
        )
        legacy_compat = LegacyCompatibleIAM("bk_monitorv3")
        legacy_compat._client = http
        legacy_req = {
            "system": "bk_monitorv3",
            "subject": {"type": "user", "id": "tester"},
            "action": {"id": "view_business_v2"},
            "resources": [{"system": "bk_monitorv3", "type": "space", "id": "2", "attribute": {}}],
            "environment": {},
        }
        legacy_policies = legacy_compat._do_policy_query(legacy_req, with_resources=True)

        http2 = _mock_http(
            {
                "view_business_v2": {"op": "eq", "field": "space.id", "value": "2"},
                "view_business": {"op": "eq", "field": "biz.id", "value": "2"},
            }
        )
        provider, client = _new_provider_with_http(real_schema, http2)
        new_req = client.make_request("tester", "view_business_v2", [client.make_resource("space", "2")])
        new_policies = client._do_policy_query(new_req, with_resources=True)

        assert new_policies == legacy_policies
        # 调用序列长度一致：V2 主查 + V1 双查
        assert len(http2.policy_query.call_args_list) == len(http.policy_query.call_args_list) == 2


# ---------------------------------------------------------------------------
# live 用例（BK_IAM_ENGINE_USER 门控；只读权限查询）
# ---------------------------------------------------------------------------


@pytest.fixture
def live_permission(live_framework, iam_user):
    """真实框架 + 真实用户（bk_tenant_id 默认 system）。

    注意 scope 必须是 function：iam_user（function scope）的 pytest.skip 门控需要
    逐用例生效；此前 module scope 依赖 function scope 触发 ScopeMismatch。
    """
    from bkmonitor.iam.iam_engine.django.facade import get_framework, _set_framework

    saved = None
    try:
        saved = get_framework()
    except RuntimeError:
        saved = None
    _set_framework(live_framework)
    perm = Permission(username=iam_user, bk_tenant_id="system")
    yield perm
    _set_framework(saved)


def _live_biz_id() -> str:
    return os.getenv("BK_IAM_ENGINE_BIZ_ID", "2").strip()


class TestLiveQueries:
    """真实测试鉴权服务器只读查询（无任何写操作）。"""

    pytestmark = [pytest.mark.live, pytest.mark.django_db(databases=["default", "monitor_api"])]

    def test_live_is_allowed_business(self, live_permission):
        biz_id = _live_biz_id()
        is_allow = live_permission.is_allowed_by_biz(int(biz_id), ActionEnum.VIEW_BUSINESS)
        print(f"biz_id: {biz_id}, is_allow: {is_allow}")
        assert isinstance(is_allow, bool)

    def test_live_is_allowed_with_resource(self, live_permission):
        biz_id = _live_biz_id()
        result = live_permission.is_allowed(
            ActionEnum.VIEW_BUSINESS,
            [ResourceEnum.BUSINESS.create_simple_instance(biz_id)],
        )
        assert isinstance(result, bool)

    def test_live_legacy_vs_new_decision_parity(self, live_permission, live_framework):
        """真实服务器上：旧 SDK 路径（LegacyIAM + V3 ID）与新框架路径判定一致。"""
        from django.conf import settings

        username = live_permission.username
        biz_id = _live_biz_id()
        v3_action_id = "view_business_v2"

        legacy_client = LegacyIAM(
            settings.APP_CODE,
            settings.SECRET_KEY,
            settings.BK_IAM_APIGATEWAY_URL,
            "bk_monitorv3",
            bk_tenant_id="system",
        )
        legacy_allowed = legacy_client.is_allowed_with_cache(
            legacy_make_request(username, v3_action_id, [legacy_make_resource("space", biz_id)])
        )

        new_allowed = live_permission.is_allowed(
            ActionEnum.VIEW_BUSINESS,
            [ResourceEnum.BUSINESS.create_simple_instance(biz_id)],
        )
        assert new_allowed == legacy_allowed

    def test_live_batch_is_allowed(self, live_permission):
        biz_id = _live_biz_id()
        result = live_permission.batch_is_allowed(
            [ActionEnum.VIEW_BUSINESS, ActionEnum.VIEW_EVENT, ActionEnum.MANAGE_EVENT],
            [[ResourceEnum.BUSINESS.create_simple_instance(biz_id)]],
        )
        assert set(result[biz_id]) == {"view_business", "view_event", "manage_event"}

    def test_live_apply_url_and_data(self, live_permission):
        biz_id = _live_biz_id()
        data, url = live_permission.get_apply_data(
            [ActionEnum.VIEW_BUSINESS], [ResourceEnum.BUSINESS.create_instance(biz_id)]
        )
        assert isinstance(url, str) and url
        assert isinstance(data, dict)

    def test_live_filter_space_list(self, live_permission):
        result = live_permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS)
        assert isinstance(result, list)

    def test_live_legacy_alias_new_dashboard(self, live_permission, live_framework):
        """真实服务器：new_dashboard 别名（OR 合并）在新旧路径下判定一致。"""
        from django.conf import settings

        username = live_permission.username
        biz_id = _live_biz_id()

        legacy_client = LegacyIAM(
            settings.APP_CODE,
            settings.SECRET_KEY,
            settings.BK_IAM_APIGATEWAY_URL,
            "bk_monitorv3",
            bk_tenant_id="system",
        )
        legacy_allowed = legacy_client.is_allowed(
            legacy_make_request(username, "new_dashboard", [legacy_make_resource("space", biz_id)])
        )
        new_allowed = live_permission.is_allowed(
            ActionEnum.NEW_DASHBOARD,
            [ResourceEnum.BUSINESS.create_simple_instance(biz_id)],
        )
        assert new_allowed == legacy_allowed
