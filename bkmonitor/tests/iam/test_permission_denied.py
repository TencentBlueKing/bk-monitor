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
# IAM Engine 鉴权拒绝流程集成测试
#
# 覆盖：
#   1. PermissionDenied 异常结构
#   2. get_apply_data 返回格式（IAM Application 兼容）
#   3. get_apply_url 格式
#   4. custom_exception_handler 格式化后响应结构
#   5. 批量鉴权 BatchAuthResult 结构
#
# 前置条件：.env 中配置好以下环境变量
#   BK_IAM_V4_API_BASE_URL = https://xxxxxxx
#   BK_IAM_V4_SYSTEM_ID = bk_monitor_v4
#   BK_IAM_APP_CODE = <your_app_code>
#   BK_IAM_APP_SECRET = <your_app_secret>
#   IAM_V4_TEST_USER = <your_username>  （可选）
#   IAM_V4_TEST_SPACE_ID = <space_id>   （可选）
# ==============================================================================

import os

import pytest
from django.conf import settings

from bkmonitor.iam.definitions.actions import Actions
from bkmonitor.iam.definitions.resource_types import ResourceTypes
from bkmonitor.iam.iam_engine.core.exceptions import PermissionDenied
from bkmonitor.iam.iam_engine.core.types import (
    ApplyURLRequest,
    AuthRequest,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceInstance,
    Subject,
)
from bkmonitor.iam.iam_engine.django.facade import get_framework

# ---- 配置 ----

_MISSING_CONFIG = (
    not getattr(settings, "BK_IAM_V4_API_BASE_URL", "")
    or not getattr(settings, "BK_IAM_APP_CODE", "")
    or not getattr(settings, "BK_IAM_APP_SECRET", "")
)
SKIP_REASON = "IAM v4 API 未配置（BK_IAM_V4_API_BASE_URL / BK_IAM_APP_CODE / BK_IAM_APP_SECRET）"

TEST_USER = os.getenv("IAM_V4_TEST_USER", "admin")
TEST_SPACE_ID = os.getenv("IAM_V4_TEST_SPACE_ID", "2")


# ==============================================================================
# PermissionDenied 异常结构
# ==============================================================================


class TestPermissionDeniedException:
    """验证 PermissionDenied 异常的字段和 DRF 兼容性。"""

    def test_basic_fields(self):
        """构造 PermissionDenied，验证各字段。"""
        exc = PermissionDenied(
            action_id="view_business",
            apply_url="https://iam.example.com/apply/test",
            detail={"permission": {"system": "bk_monitor_v4", "actions": []}},
        )
        assert exc.action_id == "view_business"
        assert exc.apply_url == "https://iam.example.com/apply/test"
        assert exc.detail_data == {"permission": {"system": "bk_monitor_v4", "actions": []}}
        assert exc.code == 9900403
        assert exc.status_code == 403
        assert str(exc) == "permission denied: action=view_business"

    def test_minimal_fields(self):
        """不传 detail 时 detail_data 应为空 dict。"""
        exc = PermissionDenied(action_id="view_business")
        assert exc.detail_data == {}
        assert exc.apply_url == ""

    def test_custom_exception_handler_compatibility(self):
        """模拟 custom_exception_handler 的 PermissionDenied 分支格式化。

        验证响应结构与 V3 PermissionDeniedError 兼容：
          - result: false
          - code: 9900403
          - data 含 apply_url
          - detail_data 的键合并到响应顶层（前端 perimssion 字段）
        """
        exc = PermissionDenied(
            action_id="view_business",
            apply_url="https://iam.example.com/apply/abc123",
            detail={
                "permission": {"system": "bk_monitor_v4", "actions": [{"id": "view_business", "name": "业务访问"}]}
            },
        )

        # 模拟 handler 中 PermissionDenied 分支的格式化逻辑
        result = {
            "result": False,
            "code": PermissionDenied.code,
            "name": PermissionDenied.default_detail,
            "message": str(exc),
            "data": {"apply_url": exc.apply_url},
        }
        result.update(exc.detail_data)

        assert result["result"] is False
        assert result["code"] == 9900403
        assert result["name"] == "权限校验不通过"
        assert result["message"] == "permission denied: action=view_business"
        assert result["data"] == {"apply_url": "https://iam.example.com/apply/abc123"}
        assert "permission" in result
        assert result["permission"]["system"] == "bk_monitor_v4"


# ==============================================================================
# get_apply_data — Provider 生成权限申请数据
# ==============================================================================


@pytest.mark.skipif(_MISSING_CONFIG, reason=SKIP_REASON)
class TestGetApplyData:
    """验证 V4Provider.get_apply_data 的返回格式。"""

    def test_structure_resource_free(self):
        """resource-free action：related_resource_types 为空列表。"""
        fw = get_framework()
        subject = Subject(id=TEST_USER)
        data = fw.get_apply_data(
            action_ids=[Actions.MANAGE_GLOBAL_SETTING.id],
            resources=[],
            subject=subject,
        )
        assert data is not None, "V4Provider 应实现 get_apply_data"
        assert isinstance(data, dict)
        assert data["system"] == settings.BK_IAM_V4_SYSTEM_ID
        assert len(data["actions"]) == 1

        action = data["actions"][0]
        assert action["id"] == Actions.MANAGE_GLOBAL_SETTING.id  # 恒等编码
        assert action["name"] == Actions.MANAGE_GLOBAL_SETTING.name
        assert action["related_resource_types"] == []
        print(f"\n  ✓ resource-free: {action}")

    def test_structure_with_resource(self):
        """有资源 action + 单个资源实例。"""
        fw = get_framework()
        subject = Subject(id=TEST_USER)
        data = fw.get_apply_data(
            action_ids=[Actions.VIEW_BUSINESS.id],
            resources=[ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID)],
            subject=subject,
        )
        assert data is not None
        assert data["system"] == settings.BK_IAM_V4_SYSTEM_ID
        assert len(data["actions"]) == 1

        action = data["actions"][0]
        assert action["id"] == Actions.VIEW_BUSINESS.id  # codec 对 action_id 恒等编码
        assert action["name"] == Actions.VIEW_BUSINESS.name

        rts = action["related_resource_types"]
        assert len(rts) == 1
        rt = rts[0]
        assert rt["system_id"] == settings.BK_IAM_V4_SYSTEM_ID
        assert rt["id"] == ResourceTypes.SPACE.id
        assert len(rt["instances"]) == 1
        instance = rt["instances"][0][0]
        assert instance["type"] == ResourceTypes.SPACE.id
        assert instance["id"] == f"space|{TEST_SPACE_ID}"  # codec 编码后
        assert "name" in instance
        print(f"\n  ✓ with resource: rt={rt}")

    def test_structure_multiple_actions(self):
        """多个 action + 同一 resource。"""
        fw = get_framework()
        subject = Subject(id=TEST_USER)
        data = fw.get_apply_data(
            action_ids=[Actions.VIEW_BUSINESS.id, Actions.VIEW_RULE.id],
            resources=[ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID)],
            subject=subject,
        )
        assert data is not None
        assert len(data["actions"]) == 2

        for action in data["actions"]:
            assert "id" in action
            assert "name" in action
            assert "related_resource_types" in action
            assert len(action["related_resource_types"]) == 1
            rt = action["related_resource_types"][0]
            assert rt["system_id"] == settings.BK_IAM_V4_SYSTEM_ID
            assert rt["id"] == ResourceTypes.SPACE.id
        print(f"\n  ✓ {len(data['actions'])} actions")

    def test_structure_no_callback_graceful(self):
        """不存在的 resource_type 不抛异常，related_resource_types 为空。"""
        fw = get_framework()
        subject = Subject(id=TEST_USER)
        data = fw.get_apply_data(
            action_ids=["nonexistent_action"],
            resources=[ResourceInstance(type="space", id="999")],
            subject=subject,
        )
        assert data is not None
        assert len(data["actions"]) == 1
        action = data["actions"][0]
        assert action["id"] == "nonexistent_action"
        # 查不到 action_def 时 resource_type 为空
        assert action["related_resource_types"] == []
        print("\n  ✓ graceful fallback for nonexistent action")


# ==============================================================================
# get_apply_url
# ==============================================================================


@pytest.mark.skipif(_MISSING_CONFIG, reason=SKIP_REASON)
class TestGetApplyUrl:
    """验证权限申请 URL 的格式。"""

    def test_url_format(self):
        """get_apply_url 返回合法的 http(s) URL。"""
        fw = get_framework()
        url = fw.get_apply_url(
            ApplyURLRequest(
                subject=Subject(id=TEST_USER),
                action_ids=[Actions.VIEW_BUSINESS.id],
                resources=(ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID),),
            )
        )
        assert isinstance(url, str)
        assert url.startswith("http"), f"URL should start with http, got: {url}"
        print(f"\n  apply_url: {url}")

    def test_url_resource_free(self):
        """resource-free action 的申请 URL。"""
        fw = get_framework()
        url = fw.get_apply_url(
            ApplyURLRequest(
                subject=Subject(id=TEST_USER),
                action_ids=[Actions.MANAGE_GLOBAL_SETTING.id],
            )
        )
        assert isinstance(url, str)
        assert url.startswith("http"), f"URL should start with http, got: {url}"
        print(f"\n  resource-free apply_url: {url}")

    def test_url_multiple_actions(self):
        """多个 action 的申请 URL。"""
        fw = get_framework()
        url = fw.get_apply_url(
            ApplyURLRequest(
                subject=Subject(id=TEST_USER),
                action_ids=[Actions.VIEW_BUSINESS.id, Actions.EXPLORE_METRIC.id, Actions.VIEW_RULE.id],
                resources=(ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID),),
            )
        )
        assert isinstance(url, str)
        assert url.startswith("http")
        print(f"\n  multi-action apply_url: {url}")


# ==============================================================================
# 端到端 denied 响应格式
# ==============================================================================


class TestDeniedResponseFormat:
    """验证 IAMPermission → PermissionDenied → custom_exception_handler → 前端 JSON 全链路。"""

    def _simulate_handler_response(self, exc: PermissionDenied) -> dict:
        """模拟 custom_exception_handler 中 PermissionDenied 分支的格式化。

        与 core/drf_resource/exceptions.py 中的格式保持一致。
        """
        from core.errors import ErrorDetails

        result = {
            "result": False,
            "code": PermissionDenied.code,
            "name": PermissionDenied.default_detail,
            "message": str(exc),
            "data": {"apply_url": exc.apply_url},
            "error_details": ErrorDetails(
                exc_type=type(exc).__name__,
                exc_code=PermissionDenied.code,
                overview=str(exc),
                detail=exc.apply_url,
                popup_message="primary",
            ).to_dict(),
        }
        result.update(exc.detail_data)
        return result

    def test_response_format_with_permission(self):
        """被拒 + 有 apply_data 时，响应含 permission 字段。"""
        exc = PermissionDenied(
            action_id="view_business",
            apply_url="https://iam.example.com/apply/test",
            detail={
                "permission": {
                    "system": "bk_monitor_v4",
                    "actions": [
                        {
                            "id": "view_business",
                            "name": "业务访问",
                            "related_resource_types": [
                                {
                                    "system_id": "bk_monitor_v4",
                                    "id": "space",
                                    "instances": [[{"type": "space", "id": "2", "name": "蓝鲸监控"}]],
                                }
                            ],
                        }
                    ],
                }
            },
        )

        result = self._simulate_handler_response(exc)

        assert result["result"] is False
        assert result["code"] == 9900403
        assert result["name"] == "权限校验不通过"
        assert "permission" in result
        assert result["permission"]["system"] == "bk_monitor_v4"
        assert len(result["permission"]["actions"]) == 1
        assert result["data"] == {"apply_url": "https://iam.example.com/apply/test"}
        assert result["error_details"]["type"] == "PermissionDenied"
        assert result["error_details"]["popup_message"] == "primary"  # 蓝框

        print("\n  ✓ 完整 denied 响应:")
        for k, v in result.items():
            print(f"    {k}: {v}")

    def test_response_format_minimal(self):
        """被拒但无 apply_data，detail_data 为空。"""
        exc = PermissionDenied(action_id="view_global_setting", apply_url="https://iam.example.com/apply")

        result = self._simulate_handler_response(exc)

        assert result["result"] is False
        assert result["code"] == 9900403
        assert result["data"] == {"apply_url": "https://iam.example.com/apply"}
        assert "permission" not in result
        print("\n  ✓ 最小 denied 响应: ok")

    def test_response_serializable(self):
        """响应结构可以被 JSON 序列化。"""
        import json

        exc = PermissionDenied(
            action_id="view_business",
            apply_url="https://iam.example.com/apply/test",
            detail={"permission": {"system": "test", "actions": []}},
        )
        result = self._simulate_handler_response(exc)

        serialized = json.dumps(result, ensure_ascii=False)
        assert isinstance(serialized, str)
        parsed = json.loads(serialized)
        assert parsed["result"] is False
        assert parsed["code"] == 9900403
        print(f"\n  ✓ JSON 可序列化: {len(serialized)} bytes")


# ==============================================================================
# 框架层 get_apply_data 回退 — Provider 不支持时返回 None
# ==============================================================================


class TestGetApplyDataFallback:
    """不支持的 Provider 不会让 get_apply_data 抛异常。"""

    def test_none_on_unsupported(self):
        """基类默认 get_apply_data 返回 None。"""
        from bkmonitor.iam.iam_engine.provider.base import PermissionProvider as BaseProvider

        class NoopProvider(BaseProvider):
            name = "noop"

            def _is_allowed_dialect(self, request):
                return False

            def _batch_by_resource_dialect_page(self, request):
                return []

            def _batch_by_action_dialect_page(self, request):
                return []

            def _get_apply_url_dialect(self, request):
                return ""

            def plan_migration(self, schema):
                raise NotImplementedError

            def apply_migration(self, plan, **kwargs):
                raise NotImplementedError

            def health_check(self):
                return {}

        result = NoopProvider(None).get_apply_data(["view_business"], [], Subject(id="test"))
        assert result is None
        print("\n  ✓ 默认返回 None")


# ==============================================================================
# 批量鉴权 BatchAuthResult 结构
# ==============================================================================


@pytest.mark.skipif(_MISSING_CONFIG, reason=SKIP_REASON)
class TestBatchAuthResultFormat:
    """验证批量鉴权返回结构的正确性，确保与 insert_permission_field 的兼容。"""

    def test_batch_by_resource_structure(self):
        """BatchAuthResult.items 格式：每个 item 含 action_id / resource_type / resource_id / allowed。"""
        fw = get_framework()
        space_ids = [str(i) for i in range(1, 4)]
        result = fw.batch_by_resource(
            BatchByResourceRequest(
                subject=Subject(id=TEST_USER),
                action_id=Actions.VIEW_BUSINESS.id,
                resources=tuple(ResourceInstance(type=ResourceTypes.SPACE, id=sid) for sid in space_ids),
            )
        )
        assert len(result.items) == len(space_ids)

        for item in result.items:
            assert item.action_id == Actions.VIEW_BUSINESS.id
            assert item.resource_type == ResourceTypes.SPACE.id
            assert item.resource_id in space_ids
            assert isinstance(item.allowed, bool)

        print(f"\n  batch_by_resource results ({len(result.items)} items):")
        for item in result.items:
            print(f"    space={item.resource_id} allowed={item.allowed}")

    def test_batch_by_action_structure(self):
        """BatchAuthResult.items 格式：每个 item 含 action_id / allowed。"""
        fw = get_framework()
        action_ids = [
            Actions.VIEW_BUSINESS.id,
            Actions.VIEW_RULE.id,
            Actions.EXPLORE_METRIC.id,
        ]
        result = fw.batch_by_action(
            BatchByActionRequest(
                subject=Subject(id=TEST_USER),
                action_ids=action_ids,
                resource=ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID),
            )
        )
        assert len(result.items) == len(action_ids)

        for item in result.items:
            assert item.action_id in action_ids
            assert isinstance(item.allowed, bool)

        print(f"\n  batch_by_action results ({len(result.items)} items):")
        for item in result.items:
            print(f"    {item.action_id}: allowed={item.allowed}")

    def test_format_compatible_with_insert_permission_field(self):
        """模拟 insert_permission_field 的 {resource_id: {action_id: bool}} 转换。"""
        from collections import defaultdict

        fw = get_framework()
        space_ids = ["1", "2", "3"]
        actions = [Actions.VIEW_BUSINESS.id, Actions.VIEW_RULE.id]

        # 模拟 insert_permission_field 的转换逻辑：batch_by_action 做跨 action、同 resource 的批量
        output: dict[str, dict[str, bool]] = defaultdict(dict)
        for space_id in space_ids:
            result = fw.batch_by_action(
                BatchByActionRequest(
                    subject=Subject(id=TEST_USER),
                    action_ids=actions,
                    resource=ResourceInstance(type=ResourceTypes.SPACE, id=space_id),
                )
            )
            for item in result.items:
                output[space_id][item.action_id] = item.allowed

        assert len(output) == len(space_ids)
        for sid in space_ids:
            assert set(output[sid].keys()) == set(actions)
            for aid in actions:
                assert isinstance(output[sid][aid], bool)

        print("\n  insert_permission_field 兼容格式:")
        for sid, perms in output.items():
            print(f"    space={sid} → {perms}")


# ==============================================================================
# IAMPermission denied 集成 — 验证 PermissionDenied 能被 raise
# ==============================================================================


@pytest.mark.skipif(_MISSING_CONFIG, reason=SKIP_REASON)
class TestIAMPermissionDeniedIntegration:
    """框架 IAMPermission 在 denied 后 raise PermissionDenied。"""

    def test_denied_raises_permission_denied(self):
        """对一个大概率没权限的 action 调 is_allowed，验证无异常（bool 返回）。

        被拒时抛异常由 DRF IAMPermission 层负责，不在此测试。
        本测试只验证 Provider 层的 is_allowed 正常返回 bool。
        """
        fw = get_framework()
        allowed = fw.is_allowed(
            AuthRequest(
                subject=Subject(id=TEST_USER),
                action_id=Actions.VIEW_BUSINESS.id,
                resource=ResourceInstance(type=ResourceTypes.SPACE, id="99999999"),
            )
        )
        assert isinstance(allowed, bool)
        print(f"\n  is_allowed(nonexistent_space) = {allowed}  (预期 False)")

    def test_get_apply_url_on_denied_scenario(self):
        """模拟 IAMPermission._is_any_action_allowed 的 denied 分支：
        调 get_apply_url + get_apply_data，验证两者返回合法的值。
        """
        fw = get_framework()
        subject = Subject(id=TEST_USER)
        action_ids = [Actions.VIEW_BUSINESS.id]
        resource = ResourceInstance(type=ResourceTypes.SPACE, id="99999999")

        # 模拟 denied 后的处理
        apply_url = fw.get_apply_url(
            ApplyURLRequest(
                subject=subject,
                action_ids=tuple(action_ids),
                resources=(resource,),
            )
        )
        assert isinstance(apply_url, str)
        assert apply_url.startswith("http")

        apply_data = fw.get_apply_data(action_ids, [resource], subject)
        assert apply_data is not None
        assert apply_data["system"] == settings.BK_IAM_V4_SYSTEM_ID

        # 构造 PermissionDenied（模拟 DRF IAMPermission 行为）
        exc = PermissionDenied(
            action_id=action_ids[-1],
            apply_url=apply_url,
            detail={"permission": apply_data},
        )
        assert exc.apply_url == apply_url

        print("\n  ✓ denied scenario complete:")
        print(f"    apply_url: {apply_url[:80]}...")
        print(f"    apply_data actions: {[a['id'] for a in apply_data['actions']]}")
        print(f"    exception: {exc}")
