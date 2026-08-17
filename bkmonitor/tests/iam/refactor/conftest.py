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
# bkmonitor/tests/iam/refactor/conftest.py
#
# 新老 IAM 版本对照测试（只读权限查询）共享设施：
#   1. 真实 schema（Actions / ResourceTypes / Roles 定义）构建的冻结注册表
#   2. 可注入 mock client 的 V3PermissionProvider（新鉴权路径）
#   3. 旧版参考实现（Legacy 兼容客户端 / 旧 Permission 行为），用于路径对照
#   4. facade 单例安装 / 恢复（get_framework）
#   5. 实测环境 gate（BK_IAM_ENGINE_USER）
#
# 安全约束：本目录所有用例只允许“权限查询”类操作（is_allowed / batch_is_allowed /
# get_apply_url / get_apply_data / filter_space_list_by_action / query_policy 等），
# 禁止任何授权 / 迁移 / 删除类写操作。
# ==============================================================================

from __future__ import annotations

import copy
import os
import warnings
from typing import Any

import pytest

from bkmonitor.iam.iam_engine.django.facade import _set_framework
from bkmonitor.iam.iam_engine.schema.loaders import load_from_class
from bkmonitor.iam.iam_engine.schema.registry import SchemaRegistry
from bkmonitor.iam.iam_engine.core.framework import IAMFramework
from bkmonitor.iam.iam_engine.provider.composition.single import SinglePolicy
from bkmonitor.iam.iam_engine.provider.base import PermissionProvider

# ---------------------------------------------------------------------------
# 旧版快照（取自本分支 merge-base 7b360f40 的 bkmonitor/iam/action.py）
#
# 每个条目: 成员名 -> (旧 id = V3 平台注册 ID, type, 中文名)
# 新版要求：ActionEnum.X.id == 业务 ID；extensions["v3"]["action_id"] == 旧 id
# ---------------------------------------------------------------------------

OLD_ACTION_SNAPSHOT: dict[str, tuple[str, str, str]] = {
    "VIEW_BUSINESS": ("view_business_v2", "view", "业务访问"),
    "USING_DASHBOARD_MCP": ("using_dashboard_mcp", "view", "使用仪表盘MCP"),
    "USING_METRICS_MCP": ("using_metrics_mcp", "view", "使用指标MCP"),
    "USING_LOG_MCP": ("using_log_mcp", "view", "使用日志MCP"),
    "USING_METADATA_MCP": ("using_metadata_mcp", "view", "使用元数据MCP"),
    "USING_ALARM_MCP": ("using_alarm_mcp", "view", "使用告警查询MCP"),
    "USING_ALARM_HANDLING_MCP": ("using_alarm_handling_mcp", "manage", "使用告警处置MCP"),
    "USING_APM_MCP": ("using_apm_mcp", "view", "使用APM MCP"),
    "USING_OPERATION_MCP": ("using_operation_mcp", "view", "使用运营数据MCP"),
    "EXPLORE_METRIC": ("explore_metric_v2", "view", "指标检索"),
    "VIEW_SYNTHETIC": ("view_synthetic_v2", "view", "拨测查看"),
    "MANAGE_SYNTHETIC": ("manage_synthetic_v2", "manage", "拨测管理"),
    "USE_PUBLIC_SYNTHETIC_LOCATION": ("use_public_synthetic_location", "view", "拨测公共节点使用"),
    "MANAGE_PUBLIC_SYNTHETIC_LOCATION": ("manage_public_synthetic_location", "manage", "拨测公共节点管理"),
    "VIEW_HOST": ("view_host_v2", "view", "主机详情查看"),
    "MANAGE_HOST": ("manage_host_v2", "manage", "主机详情管理"),
    "VIEW_EVENT": ("view_event_v2", "view", "事件中心查看"),
    "MANAGE_EVENT": ("manage_event_v2", "manage", "事件中心管理"),
    "VIEW_PLUGIN": ("view_plugin_v2", "view", "指标插件查看"),
    "MANAGE_PLUGIN": ("manage_plugin_v2", "manage", "指标插件管理"),
    "MANAGE_PUBLIC_PLUGIN": ("manage_public_plugin", "manage", "公共插件管理"),
    "VIEW_COLLECTION": ("view_collection_v2", "view", "采集查看"),
    "MANAGE_COLLECTION": ("manage_collection_v2", "manage", "采集管理"),
    "VIEW_NOTIFY_TEAM": ("view_notify_team_v2", "view", "告警组查看"),
    "MANAGE_NOTIFY_TEAM": ("manage_notify_team_v2", "manage", "告警组管理"),
    "VIEW_RULE": ("view_rule_v2", "view", "策略查看"),
    "MANAGE_RULE": ("manage_rule_v2", "manage", "策略管理"),
    "VIEW_DOWNTIME": ("view_downtime_v2", "view", "屏蔽查看"),
    "MANAGE_DOWNTIME": ("manage_downtime_v2", "manage", "屏蔽管理"),
    "VIEW_CUSTOM_METRIC": ("view_custom_metric_v2", "view", "自定义指标上报查看"),
    "MANAGE_CUSTOM_METRIC": ("manage_custom_metric_v2", "manage", "自定义指标上报管理"),
    "VIEW_CUSTOM_EVENT": ("view_custom_event_v2", "view", "自定义事件上报查看"),
    "MANAGE_CUSTOM_EVENT": ("manage_custom_event_v2", "manage", "自定义事件上报管理"),
    "VIEW_DASHBOARD": ("view_dashboard_v2", "view", "仪表盘查看"),
    "MANAGE_DASHBOARD": ("manage_dashboard_v2", "manage", "仪表盘管理"),
    "VIEW_SINGLE_DASHBOARD": ("view_single_dashboard", "view", "仪表盘实例查看"),
    "EDIT_SINGLE_DASHBOARD": ("edit_single_dashboard", "manage", "仪表盘实例编辑"),
    "NEW_DASHBOARD": ("new_dashboard", "manage", "新建仪表盘"),
    "MANAGE_DATASOURCE": ("manage_datasource_v2", "manage", "仪表盘配置管理"),
    "EXPORT_CONFIG": ("export_config_v2", "view", "导出"),
    "IMPORT_CONFIG": ("import_config_v2", "manage", "导入"),
    "VIEW_GLOBAL_SETTING": ("view_global_setting", "view", "全局配置查看"),
    "MANAGE_GLOBAL_SETTING": ("manage_global_setting", "manage", "全局配置编辑"),
    "VIEW_SELF_STATE": ("view_self_state", "view", "自监控查看"),
    "MANAGE_PUBLIC_ACTION_CONFIG": ("manage_public_action_config", "manage", "公共套餐管理"),
    "VIEW_APM_APPLICATION": ("view_apm_application_v2", "view", "APM应用查看"),
    "MANAGE_APM_APPLICATION": ("manage_apm_application_v2", "manage", "APM应用管理"),
    "MANAGE_CALENDAR": ("manage_calendar", "manage", "日历服务管理"),
    "MANAGE_REPORT": ("manage_report", "manage", "订阅管理"),
    "VIEW_INCIDENT": ("view_incident", "view", "故障查看"),
    "MANAGE_INCIDENT": ("manage_incident", "manage", "故障管理"),
    "VIEW_RUM_APPLICATION": ("view_rum_application_v2", "view", "RUM应用查看"),
    "MANAGE_RUM_APPLICATION": ("manage_rum_application_v2", "manage", "RUM应用管理"),
}

# 旧版资源类型快照：业务资源类型 ID -> V3 system_id（bk_monitorv3）
OLD_RESOURCE_RRT: dict[str, str] = {
    "space": "bk_monitorv3",
    "apm_application": "bk_monitorv3",
    "grafana_dashboard": "bk_monitorv3",
    "rum_application": "bk_monitorv3",
}

# 旧版常量（V3 平台 ID 集合）——用于对照新版常量（业务 ID 集合）
OLD_MINI_ACTION_IDS = {
    "edit_single_dashboard",
    "explore_metric_v2",
    "export_config_v2",
    "import_config_v2",
    "manage_apm_application_v2",
    "manage_custom_event_v2",
    "manage_custom_metric_v2",
    "manage_datasource_v2",
    "manage_downtime_v2",
    "manage_event_v2",
    "manage_incident",
    "manage_notify_team_v2",
    "manage_rule_v2",
    "manage_rum_application_v2",
    "use_public_synthetic_location",
    "view_apm_application_v2",
    "view_business_v2",
    "view_custom_event_v2",
    "view_custom_metric_v2",
    "view_downtime_v2",
    "view_event_v2",
    "view_incident",
    "view_notify_team_v2",
    "view_rule_v2",
    "view_rum_application_v2",
    "view_single_dashboard",
}
OLD_CMDB_REQUIRE_ACTION_IDS = {
    "manage_collection_v2",
    "manage_host_v2",
    "manage_plugin_v2",
    "manage_synthetic_v2",
    "view_collection_v2",
    "view_host_v2",
    "view_plugin_v2",
    "view_synthetic_v2",
}
OLD_ADMIN_ACTION_IDS = {
    "manage_calendar",
    "manage_global_setting",
    "manage_public_action_config",
    "manage_public_plugin",
    "manage_public_synthetic_location",
    "manage_report",
    "view_global_setting",
    "view_self_state",
}


# ---------------------------------------------------------------------------
# 旧版参考实现（Legacy 兼容客户端）
#
# 忠实复刻 merge-base 上 bkmonitor/iam/compatible.py 的 CompatibleIAM：
#   - V1→V2 双查 + biz→space 表达式修正
#   - new_dashboard → manage_dashboard_v2 / manage_datasource_v2 语义别名（V3 ID）
# 差异说明：in_compatibility_mode() 恒定 True（旧版默认行为 = GlobalConfig
# IAM_V1_COMPATIBLE 缺失时默认 True）。
# ---------------------------------------------------------------------------

LEGACY_ACTION_COMPATIBLE_ALIASES: dict[str, list[str]] = {
    "new_dashboard": ["manage_dashboard_v2", "manage_datasource_v2"],
}


class LegacyCompatibleIAM:
    """旧版 CompatibleIAM 参考实现（仅查询路径，无真实网络）。"""

    def __init__(self, system_id: str, codec=None):
        self._system_id = system_id
        # codec: 兼容新版的反向解码（request.action.id 为 V3 ID → 业务 ID），
        # 旧版通过 get_action_by_id 实现；测试里用 MonitorV3Codec 等价替代。
        self._codec = codec
        self._client = None  # 注入 mock（与新版 V3Client 共用同一 mock 可做 payload 对照）

    # ---- V3 平台 API 查询（mock 注入点） ----
    def policy_query(self, data: dict) -> tuple[bool, str, Any]:
        if self._client is not None:
            return self._client.policy_query(data)
        return True, "", {"op": "any"}

    def policy_query_by_actions(self, data: dict) -> tuple[bool, str, Any]:
        if self._client is not None:
            return self._client.policy_query_by_actions(data)
        return True, "", []

    # ---- V1 兼容逻辑（与旧 compatible.py 一致） ----

    def _has_v1_actions(self) -> bool:
        ok, _message, data = self.policy_query({"action": {"id": "view_business"}})
        if not ok:
            return False
        return "view_business" in [a["id"] for a in (data or {}).get("actions", [])]

    def in_compatibility_mode(self) -> bool:
        return True

    def _patch_policy_expression(self, expression: dict | None) -> None:
        if not expression:
            return
        if expression["op"] == "OR":
            for sub_expr in expression["content"]:
                self._patch_policy_expression(sub_expr)
        else:
            if expression["field"] == "biz.id":
                expression["field"] = "space.id"
            if "biz" in expression["value"]:
                expression["value"] = expression["value"].replace("biz", "space")

    def _biz_to_v3_action_id(self, biz_action_id: str) -> str:
        if self._codec is not None:
            return self._codec.encode_action(biz_action_id)
        return biz_action_id

    def _merge_alias_policies(self, request, policies, with_resources=True):
        # 旧版：ACTION_COMPATIBLE_ALIASES 键为 V3 平台 ID（new_dashboard 恒等）
        for alias_action_id in LEGACY_ACTION_COMPATIBLE_ALIASES.get(request["action"]["id"], []):
            alias_request = copy.deepcopy(request)
            alias_request["action"] = {"id": alias_action_id}
            try:
                alias_policies = self._do_policy_query(alias_request, with_resources)
            except Exception:
                continue
            if not alias_policies:
                continue
            policies = alias_policies if not policies else {"op": "OR", "content": [policies, alias_policies]}
        return policies

    def _do_policy_query(self, request, with_resources=True):
        """旧版 _do_policy_query（V1 双查 + 别名），request 为 dict 形态。"""
        data = copy.deepcopy(request)
        if not with_resources:
            data["resources"] = []

        ok, message, policies = self.policy_query(data)
        if not ok:
            raise RuntimeError(message)

        if data["action"]["id"].endswith("_v2"):
            v1_data = copy.deepcopy(data)
            v1_data["action"]["id"] = v1_data["action"]["id"].replace("_v2", "")
            for resource in v1_data["resources"]:
                if resource["type"] == "space":
                    resource["system"] = "bk_cmdb"
                    resource["type"] = "biz"
                iam_path = resource.get("attribute", {}).get("_bk_iam_path_", "")
                if "space" in iam_path:
                    resource["attribute"]["_bk_iam_path_"] = iam_path.replace("space", "biz")
            _v1_ok, _v1_message, v1_policies = self.policy_query(v1_data)
            self._patch_policy_expression(v1_policies)
            if v1_policies:
                policies = v1_policies if not policies else {"op": "OR", "content": [policies, v1_policies]}

        policies = self._merge_alias_policies(request, policies, with_resources)
        return policies

    def _do_policy_query_by_actions(self, request, with_resources=True):
        data = copy.deepcopy(request)
        if not with_resources:
            data["resources"] = []
        ok, message, action_policies = self.policy_query_by_actions(data)
        if not ok:
            raise RuntimeError(message)

        v2_actions = [a["id"] for a in data["actions"] if a["id"].endswith("_v2")]
        if v2_actions:
            v1_data = copy.deepcopy(data)
            v1_data["actions"] = [{"id": a.replace("_v2", "")} for a in v2_actions]
            _v1_ok, _v1_message, v1_action_policies = self.policy_query_by_actions(v1_data)
            for v1_policy in v1_action_policies or []:
                v1_policy["action"]["id"] += "_v2"
                self._patch_policy_expression(v1_policy["condition"])
                for policy in action_policies:
                    if v1_policy["action"]["id"] != policy["action"]["id"]:
                        continue
                    if not v1_policy["condition"]:
                        continue
                    if not policy["condition"]:
                        policy["condition"] = v1_policy["condition"]
                    else:
                        policy["condition"] = {"op": "OR", "content": [policy["condition"], v1_policy["condition"]]}
        return action_policies


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def real_schema() -> SchemaRegistry:
    """从真实 definitions 构建的冻结 SchemaRegistry（与 load_framework 一致）。"""
    from bkmonitor.iam.definitions.actions import Actions
    from bkmonitor.iam.definitions.resource_types import ResourceTypes
    from bkmonitor.iam.definitions.roles import Roles

    registry = SchemaRegistry()
    load_from_class(registry, ResourceTypes)
    load_from_class(registry, Actions)
    load_from_class(registry, Roles)
    registry.freeze()
    return registry


def build_v3_options(**overrides) -> dict:
    """构造 V3Provider options（默认指向本地假地址，测试中 client 会被替换）。"""
    options = {
        "codec_class": "bkmonitor.iam.adapters.v3.codec.MonitorV3Codec",
        "resolver_class": "bkmonitor.iam.adapters.v3.resolver.V3ResourceResolver",
        "base_url": "https://iam.invalid/",
        "bk_tenant_id": "system",
        "credentials": {"app_code": "test_app", "app_secret": "test_secret"},
        "system": {"id": "bk_monitorv3", "name": "监控平台", "description": "", "managers": [], "clients": []},
        "chunk_size": 20,
        "max_workers": 1,
    }
    options.update(overrides)
    return options


@pytest.fixture
def v3_provider_factory(real_schema):
    """返回可注入 mock client 的 V3PermissionProvider 工厂。"""

    def _build(**options_overrides) -> tuple[PermissionProvider, Any]:
        from bkmonitor.iam.iam_v3.provider import V3PermissionProvider
        from unittest.mock import MagicMock

        provider = V3PermissionProvider(real_schema, **build_v3_options(**options_overrides))
        mock_client = MagicMock()
        provider._get_client = MagicMock(return_value=mock_client)  # type: ignore[method-assign]
        return provider, mock_client

    return _build


@pytest.fixture
def installed_framework(real_schema):
    """把指定 framework 安装到 facade 单例，测试结束后恢复。

    用法::

        def test_x(installed_framework):
            fw = installed_framework.build(provider)
            ...
    """
    from bkmonitor.iam.iam_engine.django.facade import get_framework

    saved = None
    try:
        saved = get_framework()
    except RuntimeError:
        saved = None

    class _Installer:
        def build(self, providers, bypass_rules=None, schema=None):
            fw = IAMFramework(
                schema=schema or real_schema,
                providers=providers,
                composition=SinglePolicy(providers),
                bypass_rules=bypass_rules or [],
            )
            _set_framework(fw)
            return fw

    installer = _Installer()
    yield installer

    _set_framework(saved)  # type: ignore[arg-type]


@pytest.fixture
def fake_framework(installed_framework, real_schema):
    """安装一个“可脚本化”的框架（is_allowed/batch_by_resource 等由测试控制）。

    返回 (framework, controller)，controller 是各方法的 side_effect 设置器。
    """

    class FakeProvider(PermissionProvider):
        name = "fake"

        def __init__(self):
            self.schema = real_schema
            self.is_allowed_result = True
            self.is_allowed_calls: list = []
            self.batch_result: dict = {}
            self.apply_url = "http://iam.invalid/apply"
            self.apply_data = {"system": "bk_monitorv3", "actions": []}
            self.visible = None  # VisibleResult

        def is_allowed(self, request):
            self.is_allowed_calls.append(request)
            if isinstance(self.is_allowed_result, Exception):
                raise self.is_allowed_result
            return self.is_allowed_result

        def batch_by_resource(self, request):
            return self.batch_result

        def get_apply_url(self, request):
            return self.apply_url

        def get_apply_data(self, action_ids, resources, subject):
            return self.apply_data

        def filter_visible_resources(self, subject, action_id, candidates):
            return self.visible

        # ---- PermissionProvider 抽象方言方法：本桩不直接使用（框架层只调
        #      is_allowed / batch_by_resource 等非抽象接口），补实现以满足实例化 ----
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
            return {"status": "ok", "provider": self.name}

    provider = FakeProvider()
    fw = installed_framework.build([provider])
    return fw, provider


@pytest.fixture
def iam_user() -> str:
    """实测账号（BK_IAM_ENGINE_USER），未配置时跳过 live 用例。"""
    user = os.getenv("BK_IAM_ENGINE_USER", "").strip()
    if not user:
        pytest.skip("BK_IAM_ENGINE_USER 未配置，跳过需要真实鉴权服务器的用例")
    return user


@pytest.fixture(scope="session")
def live_framework():
    """从 settings.IAM_FRAMEWORK 构建真实框架（连接测试鉴权服务器）。

    仅查询类接口会被用例调用；本 fixture 本身不触发任何写操作。
    """
    from bkmonitor.iam.iam_engine.django.conf import load_framework

    return load_framework()


@pytest.fixture(autouse=True)
def _ignore_insecure_ssl_warnings():
    """本地开发环境没有内部 CA 证书，忽略 IAM API 网关 HTTPS 证书警告。

    生产服务器上预装了内部 CA 证书，不会触发此 warning，该 fixture 等于空操作。
    """
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")
        yield
