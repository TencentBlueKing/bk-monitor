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
# drf.py 重构对照测试
#
# 对照基线：merge-base 7b360f40 上的旧 drf.py（362 行）
# 测试目标：
#   1. 权限类/装饰器函数签名与旧调用方式兼容（外部调用零改动）
#   2. 鉴权语义一致：多 action OR、全部拒绝抛 PermissionDeniedError、
#      无 biz_id 放行、URL/body 取实例 ID 等
#   3. insert_permission_field / filter_data_by_permission 三种 mode 行为一致
#   4. 已知差异显式记录（permission 键为业务 ID、request.skip_check 不再读取等）
# 安全约束：全部用例走 mock 框架，无真实服务器访问。
# ==============================================================================

from unittest.mock import MagicMock, patch

import pytest

from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import (
    BusinessActionPermission,
    IAMPermission,
    InstanceActionForDataPermission,
    InstanceActionPermission,
    MCPPermission,
    ViewBusinessPermission,
    filter_data_by_permission,
    insert_permission_field,
)
from bkmonitor.iam.iam_engine.core.types import (
    BatchAuthResult,
    ResourceAuthResult,
    ResourceInstance,
)
from core.errors.iam import PermissionDeniedError


def _make_request(biz_id=None, user="tester", tenant="system", skip_check=False, data=None, query=None):
    request = MagicMock()
    request.biz_id = biz_id
    request.user.username = user
    request.user.tenant_id = tenant
    request.skip_check = skip_check
    # 注意：MagicMock 自动属性会让 getattr(request, "token", None) 返回真值子 mock，
    # 从而误入 token 豁免分支触发真实 ApiAuthToken 查询；必须显式置 None。
    request.token = None
    request.path = "/whatever/"
    request.data = data if data is not None else {}
    request.query_params = query if query is not None else {}
    return request


def _make_view(**kwargs):
    view = MagicMock()
    view.kwargs = kwargs
    view.lookup_field = "pk"
    # 必须显式置 None：MagicMock 自动属性会返回真值 mock，
    # 导致 drf._get_look_url_kwarg 的 lookup_url_kwarg or lookup_field 取到 mock 而断言失败
    view.lookup_url_kwarg = None
    return view


class _ScriptedProvider:
    """可按调用顺序返回结果的 provider（OR 语义测试用）。"""

    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def is_allowed(self, request):
        self.calls.append(request)
        return self.results.pop(0)


class TestDrfSurface:
    """外部接口面与旧版一致。"""

    def test_classes_and_functions_importable(self):
        assert callable(IAMPermission)
        assert callable(BusinessActionPermission)
        assert callable(ViewBusinessPermission)
        assert callable(MCPPermission)
        assert callable(InstanceActionPermission)
        assert callable(InstanceActionForDataPermission)
        assert callable(insert_permission_field)
        assert callable(filter_data_by_permission)

    def test_old_constructor_calls_still_work(self):
        """旧调用方式：位置参数 + 关键字参数。"""
        p1 = IAMPermission(actions=[ActionEnum.VIEW_EVENT], resources=[ResourceEnum.BUSINESS.create_instance("2")])
        assert p1._action_ids == ["view_event"]
        assert len(p1.resources) == 1

        p2 = BusinessActionPermission([ActionEnum.VIEW_EVENT, ActionEnum.VIEW_BUSINESS])
        assert p2._action_ids == ["view_event", "view_business"]

        p3 = InstanceActionPermission([ActionEnum.VIEW_APM_APPLICATION], ResourceEnum.APM_APPLICATION)
        assert p3.resource_type_id == "apm_application"

        p4 = InstanceActionForDataPermission(
            "application_id", [ActionEnum.VIEW_APM_APPLICATION], ResourceEnum.APM_APPLICATION
        )
        assert p4.iam_instance_id_key == "application_id"

        p5 = MCPPermission(action=ActionEnum.USING_DASHBOARD_MCP)
        assert p5._action_ids == ["using_dashboard_mcp"]


class TestIAMPermission:
    def test_no_actions_grants(self, fake_framework):
        perm = IAMPermission(actions=[])
        request = _make_request()
        assert perm.has_permission(request, view=None) is True

    def test_or_semantics_first_denied_second_allowed(self, fake_framework):
        """旧版 OR 语义：第一个动作被拒、第二个通过 → 放行。"""
        fw, provider = fake_framework
        scripted = _ScriptedProvider([False, True])
        provider.is_allowed = scripted.is_allowed
        perm = IAMPermission(actions=[ActionEnum.VIEW_EVENT, ActionEnum.MANAGE_EVENT])
        request = _make_request()
        assert perm.has_permission(request, view=None) is True
        assert [c.action_id for c in scripted.calls] == ["view_event", "manage_event"]

    def test_or_semantics_first_allowed_short_circuit(self, fake_framework):
        fw, provider = fake_framework
        scripted = _ScriptedProvider([True])
        provider.is_allowed = scripted.is_allowed
        perm = IAMPermission(actions=[ActionEnum.VIEW_EVENT, ActionEnum.MANAGE_EVENT])
        assert perm.has_permission(_make_request(), view=None) is True
        assert len(scripted.calls) == 1

    def test_all_denied_raises_permission_denied(self, fake_framework):
        fw, provider = fake_framework
        provider.is_allowed_result = False
        provider.apply_url = "http://iam.invalid/apply/x"
        perm = IAMPermission(actions=[ActionEnum.VIEW_EVENT, ActionEnum.MANAGE_EVENT])
        with pytest.raises(PermissionDeniedError) as exc:
            perm.has_permission(_make_request(), view=None)
        assert exc.value.data.get("apply_url") == "http://iam.invalid/apply/x"

    def test_resources_passed_through(self, fake_framework):
        fw, provider = fake_framework
        scripted = _ScriptedProvider([True])
        provider.is_allowed = scripted.is_allowed
        resource = ResourceInstance(type="space", id="2")
        perm = IAMPermission(actions=[ActionEnum.VIEW_BUSINESS], resources=[resource])
        assert perm.has_permission(_make_request(), view=None) is True
        assert scripted.calls[0].resource.id == "2"

    def test_global_action_with_resource_still_passed(self, fake_framework):
        """已知差异：旧版 is_allowed 对无资源 action 清空 resources；
        新版 _fw_check_any 原样传给框架，由 provider 方言层在发 SDK 请求时丢弃
        （净效果一致——见 test_resource_interface 的方言层用例）。"""
        fw, provider = fake_framework
        scripted = _ScriptedProvider([True])
        provider.is_allowed = scripted.is_allowed
        perm = IAMPermission(
            actions=[ActionEnum.MANAGE_GLOBAL_SETTING], resources=[ResourceInstance(type="space", id="2")]
        )
        assert perm.has_permission(_make_request(), view=None) is True
        assert scripted.calls[0].resource.id == "2"


class TestBusinessActionPermission:
    def test_no_biz_id_grants_without_framework(self, fake_framework):
        fw, provider = fake_framework
        provider.is_allowed_result = False
        perm = BusinessActionPermission([ActionEnum.VIEW_EVENT])
        assert perm.has_permission(_make_request(biz_id=None), view=None) is True

    def test_biz_id_uses_space_resource(self, fake_framework):
        fw, provider = fake_framework
        scripted = _ScriptedProvider([True])
        provider.is_allowed = scripted.is_allowed
        perm = BusinessActionPermission([ActionEnum.VIEW_EVENT])
        assert perm.has_permission(_make_request(biz_id=2), view=None) is True
        assert scripted.calls[0].resource.type == "space"
        assert scripted.calls[0].resource.id == "2"

    def test_object_permission_uses_obj_bk_biz_id(self, fake_framework):
        """新旧版一致的行为：obj.bk_biz_id 分支设置的 resources 会被多态覆盖。

        super().has_object_permission -> IAMPermission.has_object_permission
        -> self.has_permission（多态）-> BusinessActionPermission.has_permission
        重新按 request.biz_id 覆盖 resources。旧版同样如此（obj 分支为历史遗留的
        "意图未实现"代码），因此最终鉴权始终按 request.biz_id。
        """
        fw, provider = fake_framework
        scripted = _ScriptedProvider([True])
        provider.is_allowed = scripted.is_allowed
        perm = BusinessActionPermission([ActionEnum.VIEW_EVENT])
        obj = MagicMock()
        obj.bk_biz_id = 7
        assert perm.has_object_permission(_make_request(biz_id=2), view=None, obj=obj) is True
        assert scripted.calls[0].resource.id == "2"

    def test_object_permission_falls_back_to_request(self, fake_framework):
        fw, provider = fake_framework
        scripted = _ScriptedProvider([True])
        provider.is_allowed = scripted.is_allowed
        perm = BusinessActionPermission([ActionEnum.VIEW_EVENT])
        obj = MagicMock()
        del obj.bk_biz_id  # 无 bk_biz_id 属性 → 回退 request.biz_id
        assert perm.has_object_permission(_make_request(biz_id=5), view=None, obj=obj) is True
        assert scripted.calls[0].resource.id == "5"


class TestViewBusinessPermission:
    def test_default_action(self, fake_framework):
        fw, provider = fake_framework
        scripted = _ScriptedProvider([True])
        provider.is_allowed = scripted.is_allowed
        perm = ViewBusinessPermission()
        assert perm._action_ids == ["view_business"]
        assert perm.has_permission(_make_request(biz_id=2), view=None) is True


class TestMCPPermission:
    def test_missing_biz_id_raises(self, fake_framework):
        perm = MCPPermission()
        with pytest.raises(PermissionDeniedError):
            perm.has_permission(_make_request(biz_id=None), view=None)

    def test_with_biz_id(self, fake_framework):
        fw, provider = fake_framework
        scripted = _ScriptedProvider([True])
        provider.is_allowed = scripted.is_allowed
        perm = MCPPermission()
        assert perm.has_permission(_make_request(biz_id=2), view=None) is True
        assert scripted.calls[0].resource.type == "space"


class TestInstanceActionPermission:
    def test_url_kwarg_resource(self, fake_framework):
        fw, provider = fake_framework
        scripted = _ScriptedProvider([True])
        provider.is_allowed = scripted.is_allowed
        perm = InstanceActionPermission([ActionEnum.VIEW_APM_APPLICATION], ResourceEnum.APM_APPLICATION)
        assert perm.has_permission(_make_request(), view=_make_view(pk="app-1")) is True
        assert scripted.calls[0].resource.type == "apm_application"
        assert scripted.calls[0].resource.id == "app-1"

    def test_missing_kwarg_asserts(self, fake_framework):
        perm = InstanceActionPermission([ActionEnum.VIEW_APM_APPLICATION], ResourceEnum.APM_APPLICATION)
        with pytest.raises(AssertionError):
            perm.has_permission(_make_request(), view=_make_view())


class TestInstanceActionForDataPermission:
    def test_get_query_params(self, fake_framework):
        fw, provider = fake_framework
        scripted = _ScriptedProvider([True])
        provider.is_allowed = scripted.is_allowed
        perm = InstanceActionForDataPermission(
            "application_id", [ActionEnum.VIEW_APM_APPLICATION], ResourceEnum.APM_APPLICATION
        )
        request = _make_request(query={"application_id": "app-9"})
        request.method = "GET"
        assert perm.has_permission(request, view=_make_view()) is True
        assert scripted.calls[0].resource.id == "app-9"

    def test_post_body(self, fake_framework):
        fw, provider = fake_framework
        scripted = _ScriptedProvider([True])
        provider.is_allowed = scripted.is_allowed
        perm = InstanceActionForDataPermission(
            "application_id", [ActionEnum.VIEW_APM_APPLICATION], ResourceEnum.APM_APPLICATION
        )
        request = _make_request(data={"application_id": "app-9"})
        request.method = "POST"
        assert perm.has_permission(request, view=_make_view()) is True

    def test_kwargs_fallback(self, fake_framework):
        fw, provider = fake_framework
        scripted = _ScriptedProvider([True])
        provider.is_allowed = scripted.is_allowed
        perm = InstanceActionForDataPermission(
            "application_id", [ActionEnum.VIEW_APM_APPLICATION], ResourceEnum.APM_APPLICATION
        )
        request = _make_request()
        request.method = "POST"
        assert perm.has_permission(request, view=_make_view(pk="app-9")) is True

    def test_get_instance_id_transform(self, fake_framework):
        fw, provider = fake_framework
        scripted = _ScriptedProvider([True])
        provider.is_allowed = scripted.is_allowed
        perm = InstanceActionForDataPermission(
            "application_id",
            [ActionEnum.VIEW_APM_APPLICATION],
            ResourceEnum.APM_APPLICATION,
            get_instance_id=lambda _id: f"transformed-{_id}",
        )
        request = _make_request(data={"application_id": "app-9"})
        request.method = "POST"
        assert perm.has_permission(request, view=_make_view()) is True
        assert scripted.calls[0].resource.id == "transformed-app-9"

    def test_missing_instance_id_raises(self, fake_framework):
        perm = InstanceActionForDataPermission(
            "application_id", [ActionEnum.VIEW_APM_APPLICATION], ResourceEnum.APM_APPLICATION
        )
        request = _make_request()
        request.method = "POST"
        # kwargs 需含 pk 键（值为 None）才能通过 _get_look_url_kwarg 的 assert，
        # 走到 instance_id is None -> ValueError；空 kwargs 会先触发 AssertionError
        with pytest.raises(ValueError):
            perm.has_permission(request, view=_make_view(pk=None))


def _batch_result_for(pairs, action_id="view_event"):
    return BatchAuthResult(
        items=tuple(
            ResourceAuthResult(action_id=action_id, resource_type="space", resource_id=rid, allowed=allowed)
            for rid, allowed in pairs
        )
    )


class TestInsertPermissionField:
    """insert_permission_field：权限注入行为与旧版一致（键为业务 ID）。"""

    def _decorated_view(self, fw, provider, pairs, actions, resource_meta, **kwargs):
        provider.batch_result = _batch_result_for(pairs, action_id=actions[0].id)

        def view_func(request):
            resp = MagicMock()
            resp.data = [
                {"id": "2", "name": "a"},
                {"id": "3", "name": "b"},
                {"id": None, "name": "no-id"},
            ]
            return resp

        return insert_permission_field(actions=actions, resource_meta=resource_meta, **kwargs)(view_func)

    def test_injects_business_id_keys(self, fake_framework):
        """权限键为业务 ID（旧版为 V3 平台 ID，如 view_event_v2）——已知差异记录。"""
        fw, provider = fake_framework
        actions = [ActionEnum.VIEW_EVENT]
        wrapped = self._decorated_view(
            fw, provider, [("2", True), ("3", False)], actions, ResourceEnum.BUSINESS, id_field=lambda d: d["id"]
        )
        request = _make_request()
        response = wrapped(request)
        data = response.data
        assert data[0]["permission"] == {"view_event": True}
        assert data[1]["permission"] == {"view_event": False}
        # 无 id 的行不注入
        assert "permission" not in data[2]

    def test_always_allowed(self, fake_framework):
        fw, provider = fake_framework
        actions = [ActionEnum.VIEW_EVENT]
        wrapped = self._decorated_view(
            fw,
            provider,
            [("2", False), ("3", False)],
            actions,
            ResourceEnum.BUSINESS,
            id_field=lambda d: d["id"],
            always_allowed=lambda item: item.get("name") == "b",
        )
        response = wrapped(_make_request())
        data = response.data
        assert data[0]["permission"]["view_event"] is False
        assert data[1]["permission"]["view_event"] is True  # always_allowed 豁免

    def test_many_false(self, fake_framework):
        fw, provider = fake_framework
        provider.batch_result = _batch_result_for([("2", True)])
        actions = [ActionEnum.VIEW_EVENT]

        def view_func(request):
            resp = MagicMock()
            resp.data = {"id": "2", "name": "a"}
            return resp

        wrapped = insert_permission_field(actions=actions, resource_meta=ResourceEnum.BUSINESS, many=False)(view_func)
        response = wrapped(_make_request())
        assert response.data["permission"]["view_event"] is True

    def test_data_field(self, fake_framework):
        fw, provider = fake_framework
        provider.batch_result = _batch_result_for([("2", True)])
        actions = [ActionEnum.VIEW_EVENT]

        def view_func(request):
            resp = MagicMock()
            resp.data = {"list": [{"id": "2", "name": "a"}]}
            return resp

        wrapped = insert_permission_field(
            actions=actions,
            resource_meta=ResourceEnum.BUSINESS,
            data_field=lambda d: d["list"],
        )(view_func)
        response = wrapped(_make_request())
        assert response.data["list"][0]["permission"]["view_event"] is True


class TestFilterDataByPermission:
    """filter_data_by_permission 三种 mode 与旧版一致。"""

    def _items(self):
        return [
            {"id": "2", "name": "a"},
            {"id": "3", "name": "b"},
            {"id": "5", "name": "c"},
            {"id": None, "name": "no-id"},
        ]

    def _setup(self, fake_framework, pairs):
        fw, provider = fake_framework
        provider.batch_result = _batch_result_for(pairs)
        return fw, provider

    def test_mode_any(self, fake_framework):
        fw, provider = self._setup(fake_framework, [("2", True), ("3", False), ("5", True)])
        result = filter_data_by_permission(
            bk_tenant_id="system",
            data=self._items(),
            actions=[ActionEnum.VIEW_EVENT],
            resource_meta=ResourceEnum.BUSINESS,
            id_field=lambda d: d["id"],
            mode="any",
        )
        assert [item["id"] for item in result] == ["2", "5"]

    def test_mode_all(self, fake_framework):
        """全部 action 通过才保留（框架按 action×resource 返回全部组合）。"""
        fw, provider = fake_framework
        provider.batch_result = BatchAuthResult(
            items=(
                ResourceAuthResult(action_id="view_event", resource_type="space", resource_id="2", allowed=True),
                ResourceAuthResult(action_id="view_event", resource_type="space", resource_id="3", allowed=False),
                ResourceAuthResult(action_id="view_event", resource_type="space", resource_id="5", allowed=True),
                ResourceAuthResult(action_id="manage_event", resource_type="space", resource_id="2", allowed=True),
                ResourceAuthResult(action_id="manage_event", resource_type="space", resource_id="3", allowed=False),
                ResourceAuthResult(action_id="manage_event", resource_type="space", resource_id="5", allowed=False),
            )
        )
        result = filter_data_by_permission(
            bk_tenant_id="system",
            data=self._items(),
            actions=[ActionEnum.VIEW_EVENT, ActionEnum.MANAGE_EVENT],
            resource_meta=ResourceEnum.BUSINESS,
            id_field=lambda d: d["id"],
            mode="all",
        )
        # 只有 2 在 view_event 和 manage_event 上都通过
        assert [item["id"] for item in result] == ["2"]

    def test_mode_insert(self, fake_framework):
        fw, provider = self._setup(fake_framework, [("2", True), ("3", False), ("5", True)])
        result = filter_data_by_permission(
            bk_tenant_id="system",
            data=self._items(),
            actions=[ActionEnum.VIEW_EVENT],
            resource_meta=ResourceEnum.BUSINESS,
            id_field=lambda d: d["id"],
            mode="insert",
        )
        assert len(result) == 3
        assert result[0]["permission"]["view_event"] is True
        assert result[1]["permission"]["view_event"] is False

    def test_always_allowed(self, fake_framework):
        fw, provider = self._setup(fake_framework, [("2", False), ("3", False), ("5", False)])
        result = filter_data_by_permission(
            bk_tenant_id="system",
            data=self._items(),
            actions=[ActionEnum.VIEW_EVENT],
            resource_meta=ResourceEnum.BUSINESS,
            id_field=lambda d: d["id"],
            always_allowed=lambda item: item["name"] == "c",
            mode="any",
        )
        assert [item["id"] for item in result] == ["5"]

    def test_dict_input(self, fake_framework):
        fw, provider = self._setup(fake_framework, [("2", True)])
        result = filter_data_by_permission(
            bk_tenant_id="system",
            data={"id": "2", "name": "a"},
            actions=[ActionEnum.VIEW_EVENT],
            resource_meta=ResourceEnum.BUSINESS,
            id_field=lambda d: d["id"],
        )
        assert len(result) == 1

    def test_empty_data(self, fake_framework):
        fw, provider = self._setup(fake_framework, [])
        result = filter_data_by_permission(
            bk_tenant_id="system",
            data=[],
            actions=[ActionEnum.VIEW_EVENT],
            resource_meta=ResourceEnum.BUSINESS,
            id_field=lambda d: d["id"],
        )
        assert result == []

    def test_username_passthrough(self, fake_framework):
        fw, provider = fake_framework

        captured = {}

        def _record(request):
            captured["subject"] = request.subject
            return _batch_result_for([("2", True)])

        provider.batch_by_resource = _record
        _result = filter_data_by_permission(
            bk_tenant_id="tenant-x",
            data=[{"id": "2", "name": "a"}],
            actions=[ActionEnum.VIEW_EVENT],
            resource_meta=ResourceEnum.BUSINESS,
            id_field=lambda d: d["id"],
            username="someone",
        )
        assert captured["subject"].id == "someone"
        assert captured["subject"].tenant_id == "tenant-x"


# ===========================================================================
# 前置豁免（方案 A 修复验证）：DRF 权限类 / insert_permission_field /
# filter_data_by_permission 与旧版 Permission 路径的 token / skip_check 豁免一致
# ===========================================================================


class TestDrfPreflight:
    """request.skip_check / settings 级 / token 临时分享豁免在 DRF 路径生效（与旧版一致）。"""

    def test_request_skip_check_granted(self, fake_framework):
        """回归点修复验证：BusinessActionPermission 读取 request.skip_check=True 直接放行，不调框架。"""
        fw, provider = fake_framework
        provider.is_allowed_result = False  # 若框架被调用将返回 False
        request = _make_request(biz_id=2, skip_check=True)
        perm = BusinessActionPermission([ActionEnum.VIEW_BUSINESS])
        assert perm.has_permission(request, view=None) is True

    def test_request_skip_check_false_goes_to_framework(self, fake_framework):
        """request.skip_check=False 显式强制校验时覆盖 settings 级，仍走真实鉴权。"""
        fw, provider = fake_framework
        scripted = _ScriptedProvider([True])
        provider.is_allowed = scripted.is_allowed
        request = _make_request(biz_id=2, skip_check=False)
        with patch("bkmonitor.iam.permission.settings.SKIP_IAM_PERMISSION_CHECK", True):
            perm = BusinessActionPermission([ActionEnum.VIEW_EVENT])
            assert perm.has_permission(request, view=None) is True
        assert len(scripted.calls) == 1

    def test_settings_skip_check_granted(self, fake_framework):
        """settings.SKIP_IAM_PERMISSION_CHECK=True 且 request 无 skip_check 属性时 DRF 路径放行。"""
        from types import SimpleNamespace

        fw, provider = fake_framework
        provider.is_allowed_result = False
        # SimpleNamespace：真实缺失 skip_check 属性（MagicMock 会自动创建属性，无法模拟“无属性”）
        request = SimpleNamespace(
            biz_id=2,
            user=SimpleNamespace(username="tester", tenant_id="system"),
        )
        with patch("bkmonitor.iam.permission.settings.SKIP_IAM_PERMISSION_CHECK", True):
            perm = BusinessActionPermission([ActionEnum.VIEW_EVENT])
            assert perm.has_permission(request, view=None) is True

    def test_token_no_record_denied(self, fake_framework):
        """token 存在但记录不存在：不豁免 → 走真实鉴权 → 拒绝。

        旧版此处存在生成器表达式恒真 bug（任何带 token 的请求直接放行），
        check_iam_preflight 已用 any(...) 显式求值修复（见 permission.py 注释）：
        记录不存在且非 view_business / ActionIdMap / api_paths 命中时不再豁免。
        """
        from bkmonitor.models import ApiAuthToken

        fw, provider = fake_framework
        provider.is_allowed_result = False
        request = _make_request(biz_id=2)
        request.token = "tok"
        request.path = "/whatever/"
        with patch("bkmonitor.iam.permission.ApiAuthToken.objects.get", side_effect=ApiAuthToken.DoesNotExist):
            perm = BusinessActionPermission([ActionEnum.VIEW_EVENT])
            with pytest.raises(PermissionDeniedError):
                perm.has_permission(request, view=None)
        # 前置豁免未放行，框架被真实调用（is_allowed 返回 False → 拒绝）
        assert len(provider.is_allowed_calls) == 1

    def test_token_action_id_map_hit(self, fake_framework):
        """token 记录存在且 ActionIdMap 命中 → 放行（不调框架）。"""

        fw, provider = fake_framework
        provider.is_allowed_result = False
        record = MagicMock()
        record.type = "host"  # ActionIdMap["host"] = [ActionEnum.VIEW_HOST]
        request = _make_request(biz_id=2)
        request.token = "tok"
        request.path = "/whatever/"
        with patch("bkmonitor.iam.permission.ApiAuthToken.objects.get", return_value=record):
            perm = BusinessActionPermission([ActionEnum.VIEW_HOST])
            assert perm.has_permission(request, view=None) is True

    def test_insert_permission_field_skip_check_all_true(self, fake_framework):
        """insert_permission_field：request.skip_check=True 时全部权限为 True（旧 batch 语义），不调框架。"""
        fw, provider = fake_framework
        provider.batch_result = BatchAuthResult(items=())  # 若走框架将无任何权限
        actions = [ActionEnum.VIEW_EVENT]

        def view_func(request):
            resp = MagicMock()
            resp.data = [{"id": "2", "name": "a"}, {"id": "3", "name": "b"}]
            return resp

        wrapped = insert_permission_field(actions=actions, resource_meta=ResourceEnum.BUSINESS)(view_func)
        request = _make_request(skip_check=True)
        response = wrapped(request)
        assert response.data[0]["permission"] == {"view_event": True}
        assert response.data[1]["permission"] == {"view_event": True}

    def test_insert_permission_field_token_no_record_raises(self, fake_framework):
        """insert_permission_field：带 token 且记录不存在 → TokenValidatedError（与旧 batch_is_allowed 一致）。"""
        from bkmonitor.models import ApiAuthToken
        from core.errors.share import TokenValidatedError

        fw, provider = fake_framework
        actions = [ActionEnum.VIEW_EVENT]

        def view_func(request):
            resp = MagicMock()
            resp.data = [{"id": "2", "name": "a"}]
            return resp

        wrapped = insert_permission_field(actions=actions, resource_meta=ResourceEnum.BUSINESS)(view_func)
        request = _make_request()
        request.token = "tok"
        with patch("bkmonitor.iam.permission.ApiAuthToken.objects.get", side_effect=ApiAuthToken.DoesNotExist):
            with pytest.raises(TokenValidatedError):
                wrapped(request)

    def test_filter_data_by_permission_request_skip_check_keeps_all(self, fake_framework):
        """filter_data_by_permission：未显式传 username 时读当前请求的 skip_check（旧 Permission() 语义）。"""
        fw, provider = fake_framework
        provider.batch_result = BatchAuthResult(items=())  # 若走框架将过滤掉全部
        request = _make_request(skip_check=True)
        with patch("bkmonitor.iam.drf.get_request", return_value=request):
            result = filter_data_by_permission(
                bk_tenant_id="system",
                data=[{"id": "2", "name": "a"}, {"id": "3", "name": "b"}],
                actions=[ActionEnum.VIEW_EVENT],
                resource_meta=ResourceEnum.BUSINESS,
                id_field=lambda d: d["id"],
            )
        assert [item["id"] for item in result] == ["2", "3"]

    def test_filter_data_by_permission_explicit_username_ignores_request(self, fake_framework):
        """显式传 username 时不读 request（旧 Permission(username=...) 语义），仅 settings 级豁免生效。"""
        fw, provider = fake_framework

        captured = {}

        def _record(request):
            captured["subject"] = request.subject
            return _batch_result_for([("2", True)])

        provider.batch_by_resource = _record
        request = _make_request(skip_check=True)  # 显式 username 时该 request 不应生效
        with patch("bkmonitor.iam.drf.get_request", return_value=request):
            result = filter_data_by_permission(
                bk_tenant_id="system",
                data=[{"id": "2", "name": "a"}],
                actions=[ActionEnum.VIEW_EVENT],
                resource_meta=ResourceEnum.BUSINESS,
                id_field=lambda d: d["id"],
                username="someone",
            )
        # request.skip_check=True 不应豁免（显式 username → 旧版不读 request），框架被调用
        assert captured["subject"].id == "someone"
        assert len(result) == 1
