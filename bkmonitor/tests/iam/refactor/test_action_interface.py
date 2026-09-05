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
# action.py 重构对照测试
#
# 对照基线：本分支 merge-base 7b360f40 上的旧 action.py（729 行）
# 测试目标：
#   1. 对外接口（ActionEnum 成员 / get_action_by_id / 常量 / ActionMeta 属性）稳定
#   2. 业务 ID（新版 .id）↔ V3 平台 ID（extensions["v3"]["action_id"]）映射与旧版一致
#   3. type / version / name / related_resource_types 与旧版语义一致
#   4. 已知差异（name_en/related_actions 置空等）显式记录，供上层评估
# 安全约束：本文件只做内存级接口检查，不访问任何鉴权服务器。
# ==============================================================================

import pytest

from bkmonitor.iam.action import (
    ADMIN_ACTION_IDS,
    ALL_ACTION_IDS,
    CMDB_REQUIRE_ACTION_IDS,
    MINI_ACTION_IDS,
    ActionEnum,
    ActionMeta,
    get_action_by_id,
)
from bkmonitor.iam.definitions.actions import Actions
from bkmonitor.iam.iam_engine.schema.definitions import ActionDef
from core.errors.iam import ActionNotExistError

from .conftest import (
    OLD_ACTION_SNAPSHOT,
    OLD_ADMIN_ACTION_IDS,
    OLD_CMDB_REQUIRE_ACTION_IDS,
    OLD_MINI_ACTION_IDS,
    OLD_RESOURCE_RRT,
)

# 旧版资源类型快照：成员名 -> 旧 related_resource_types[0]["id"]（无资源为 None）
OLD_MEMBER_RRT: dict[str, str | None] = {
    "VIEW_BUSINESS": "space",
    "USING_DASHBOARD_MCP": "space",
    "USING_METRICS_MCP": "space",
    "USING_LOG_MCP": "space",
    "USING_METADATA_MCP": "space",
    "USING_ALARM_MCP": "space",
    "USING_ALARM_HANDLING_MCP": "space",
    "USING_APM_MCP": "space",
    "USING_OPERATION_MCP": "space",
    "EXPLORE_METRIC": "space",
    "VIEW_SYNTHETIC": "space",
    "MANAGE_SYNTHETIC": "space",
    "USE_PUBLIC_SYNTHETIC_LOCATION": None,
    "MANAGE_PUBLIC_SYNTHETIC_LOCATION": None,
    "VIEW_HOST": "space",
    "MANAGE_HOST": "space",
    "VIEW_EVENT": "space",
    "MANAGE_EVENT": "space",
    "VIEW_PLUGIN": "space",
    "MANAGE_PLUGIN": "space",
    "MANAGE_PUBLIC_PLUGIN": None,
    "VIEW_COLLECTION": "space",
    "MANAGE_COLLECTION": "space",
    "VIEW_NOTIFY_TEAM": "space",
    "MANAGE_NOTIFY_TEAM": "space",
    "VIEW_RULE": "space",
    "MANAGE_RULE": "space",
    "VIEW_DOWNTIME": "space",
    "MANAGE_DOWNTIME": "space",
    "VIEW_CUSTOM_METRIC": "space",
    "MANAGE_CUSTOM_METRIC": "space",
    "VIEW_CUSTOM_EVENT": "space",
    "MANAGE_CUSTOM_EVENT": "space",
    "VIEW_DASHBOARD": "space",
    "MANAGE_DASHBOARD": "space",
    "VIEW_SINGLE_DASHBOARD": "grafana_dashboard",
    "EDIT_SINGLE_DASHBOARD": "grafana_dashboard",
    "NEW_DASHBOARD": "space",
    "MANAGE_DATASOURCE": "space",
    "EXPORT_CONFIG": "space",
    "IMPORT_CONFIG": "space",
    "VIEW_GLOBAL_SETTING": None,
    "MANAGE_GLOBAL_SETTING": None,
    "VIEW_SELF_STATE": None,
    "MANAGE_PUBLIC_ACTION_CONFIG": None,
    "VIEW_APM_APPLICATION": "apm_application",
    "MANAGE_APM_APPLICATION": "apm_application",
    "MANAGE_CALENDAR": None,
    "MANAGE_REPORT": "space",
    "VIEW_INCIDENT": "space",
    "MANAGE_INCIDENT": "space",
    "VIEW_RUM_APPLICATION": "rum_application",
    "MANAGE_RUM_APPLICATION": "rum_application",
}


def _enum_members() -> list[str]:
    return [n for n in dir(ActionEnum) if not n.startswith("_") and isinstance(getattr(ActionEnum, n), ActionDef)]


class TestActionEnumSurface:
    """ActionEnum 成员集合与旧版一致（接口完整性）。"""

    def test_member_set_identical_to_old(self):
        members = set(_enum_members())
        old_members = set(OLD_ACTION_SNAPSHOT)
        assert members == old_members, f"缺失: {old_members - members}, 新增: {members - old_members}"

    def test_all_members_are_action_meta(self):
        for name in _enum_members():
            member = getattr(ActionEnum, name)
            assert isinstance(member, ActionMeta), name
            assert isinstance(member, ActionDef), name

    def test_member_ids_are_business_ids(self):
        """新版 .id 为业务 ID；且业务 ID 与 V3 平台 ID 的映射与旧版定义一致。"""
        from bkmonitor.iam.adapters.v3.codec import MonitorV3Codec

        codec = MonitorV3Codec()
        for name, (old_v3_id, _type, _name) in OLD_ACTION_SNAPSHOT.items():
            member = getattr(ActionEnum, name)
            v3_action_id = member.extensions.get("v3", {}).get("action_id")
            assert member.id == getattr(Actions, name).id, name
            assert v3_action_id == old_v3_id, f"{name}: 期望 V3 ID {old_v3_id}, 实际 {v3_action_id}"
            # 业务 ID 经 codec 编码后必须还原成旧版 V3 平台 ID（鉴权路径一致性的前提）
            assert codec.encode_action(member.id) == old_v3_id, name


class TestActionMetaCompatibility:
    """ActionMeta 旧属性接口兼容。"""

    def test_type_and_version_match_old(self):
        for name, (old_v3_id, old_type, old_name) in OLD_ACTION_SNAPSHOT.items():
            member = getattr(ActionEnum, name)
            assert member.type == old_type, f"{name}: type 期望 {old_type}, 实际 {member.type}"
            assert member.version == 1, name
            assert str(member.name) == old_name, f"{name}: name 期望 {old_name}, 实际 {member.name}"

    def test_related_resource_types_shape(self):
        """新版 related_resource_types 为 [{"id", "system_id"}]，与旧版首个资源类型一致。"""
        for name, old_rrt_id in OLD_MEMBER_RRT.items():
            member = getattr(ActionEnum, name)
            if old_rrt_id is None:
                assert member.related_resource_types == [], name
            else:
                assert len(member.related_resource_types) == 1, name
                rrt = member.related_resource_types[0]
                assert rrt["id"] == old_rrt_id, name
                assert rrt["system_id"] == OLD_RESOURCE_RRT[old_rrt_id], name

    def test_is_read_action(self):
        for name, (old_v3_id, old_type, old_name) in OLD_ACTION_SNAPSHOT.items():
            member = getattr(ActionEnum, name)
            assert member.is_read_action() == (old_type == "view"), name

    def test_to_json_keeps_old_keys(self):
        json_data = ActionEnum.VIEW_BUSINESS.to_json()
        assert set(json_data) == {
            "id",
            "name",
            "name_en",
            "type",
            "version",
            "related_resource_types",
            "related_actions",
            "description",
            "description_en",
        }
        # 旧版 name_en 有值；新版恒为空 —— 显式记录该差异（review 发现项）
        assert json_data["id"] == "view_business"
        assert json_data["name_en"] == ""

    def test_known_differences_documented(self):
        """显式记录新版与旧版的有意差异（供上层评估是否可接受）。"""
        # 1. name_en / description_en / related_actions 在新版恒为空
        assert ActionEnum.EXPLORE_METRIC.name_en == ""
        assert ActionEnum.EXPLORE_METRIC.description_en == ""
        assert ActionEnum.EXPLORE_METRIC.related_actions == []
        # 旧版 EXPLORE_METRIC.related_actions == [VIEW_BUSINESS.id]
        # 2. related_resource_types 不再携带 selection_mode / related_instance_selections
        rrt = ActionEnum.VIEW_BUSINESS.related_resource_types[0]
        assert set(rrt) == {"id", "system_id"}
        # 3. 旧版 SPACE_RESOURCE / APM_APPLICATION_RESOURCE / GRAFANA_DASHBOARD_RESOURCE /
        #    RUM_APPLICATION_RESOURCE 常量已删除（无外部调用方，见 review 报告）
        import bkmonitor.iam.action as action_module

        for removed in (
            "SPACE_RESOURCE",
            "APM_APPLICATION_RESOURCE",
            "GRAFANA_DASHBOARD_RESOURCE",
            "RUM_APPLICATION_RESOURCE",
            "fetch_related_actions",
            "generate_all_actions_json",
        ):
            assert not hasattr(action_module, removed), removed


class TestGetActionById:
    """get_action_by_id 接口稳定性。"""

    def test_business_id_lookup(self):
        action = get_action_by_id("view_business")
        assert action is ActionEnum.VIEW_BUSINESS

    def test_action_def_instance_passthrough(self):
        assert get_action_by_id(ActionEnum.VIEW_BUSINESS) is ActionEnum.VIEW_BUSINESS

    def test_unknown_id_raises(self):
        with pytest.raises(ActionNotExistError):
            get_action_by_id("no_such_action")

    def test_old_v3_platform_id_is_not_resolvable(self):
        """已知行为变化：旧版 get_action_by_id("view_business_v2") 可解析，
        新版仅接受业务 ID（"view_business_v2" 会抛 ActionNotExistError）。
        影响面：仅当上层直接以 V3 平台 ID 字符串调 get_action_by_id 时才会触发
        （全仓检索无此类调用，前端 V3 ID 字符串走 is_allowed 路径不受影响）。
        """
        with pytest.raises(ActionNotExistError):
            get_action_by_id("view_business_v2")


class TestActionConstants:
    """常量集合与旧版一致（以业务 ID 表达）。"""

    def test_mini_action_ids(self):
        # 新版业务 ID 集合经 codec 编码后应等于旧版 V3 平台 ID 集合
        from bkmonitor.iam.adapters.v3.codec import MonitorV3Codec

        codec = MonitorV3Codec()
        assert {codec.encode_action(aid) for aid in MINI_ACTION_IDS} == OLD_MINI_ACTION_IDS

    def test_cmdb_require_action_ids(self):
        from bkmonitor.iam.adapters.v3.codec import MonitorV3Codec

        codec = MonitorV3Codec()
        assert {codec.encode_action(aid) for aid in CMDB_REQUIRE_ACTION_IDS} == OLD_CMDB_REQUIRE_ACTION_IDS

    def test_admin_action_ids(self):
        assert set(ADMIN_ACTION_IDS) == OLD_ADMIN_ACTION_IDS

    def test_all_action_ids(self):
        from bkmonitor.iam.adapters.v3.codec import MonitorV3Codec

        codec = MonitorV3Codec()
        assert {codec.encode_action(aid) for aid in ALL_ACTION_IDS} == {
            v3 for v3, _t, _n in OLD_ACTION_SNAPSHOT.values()
        }

    def test_constants_use_business_ids(self):
        """显式记录：常量值从 V3 平台 ID 变为业务 ID（无外部调用方直接消费常量值）。"""
        assert "view_business" in MINI_ACTION_IDS
        assert "view_business_v2" not in MINI_ACTION_IDS


class TestActionIdMappingConsistency:
    """codec 映射与 definitions 的完整性（鉴权路径一致性的前提）。"""

    def test_codec_roundtrip_all_actions(self, real_schema):
        from bkmonitor.iam.adapters.v3.codec import MonitorV3Codec

        codec = MonitorV3Codec()
        for action in real_schema.all_actions():
            biz_id = action.id
            v3_id = action.extensions.get("v3", {}).get("action_id", biz_id)
            assert codec.encode_action(biz_id) == v3_id, biz_id
            assert codec.decode_action(v3_id) == biz_id, v3_id

    def test_codec_identity_for_unmapped_ids(self):
        from bkmonitor.iam.adapters.v3.codec import MonitorV3Codec

        codec = MonitorV3Codec()
        assert codec.encode_action("view_incident") == "view_incident"
        assert codec.decode_action("view_incident") == "view_incident"

    def test_read_action_types_complete(self):
        """所有 action 的 v3 type 均在 codec 的 action_types 中（读写缓存策略依赖）。"""
        from bkmonitor.iam.adapters.v3.codec import MonitorV3Codec

        codec = MonitorV3Codec()
        for name, (old_v3_id, old_type, _old_name) in OLD_ACTION_SNAPSHOT.items():
            member = getattr(ActionEnum, name)
            assert codec.is_read_action(member.id) == (old_type == "view"), name


class TestActionIdAliasCompatibility:
    """历史 Provider Action ID 只在系统边界归一化，框架主键仍保持业务 ID。"""

    def test_known_v3_alias_is_canonicalized(self):
        from bkmonitor.iam.action import canonicalize_action_id

        assert canonicalize_action_id("view_business_v2") == "view_business"
        assert canonicalize_action_id("manage_apm_application_v2") == "manage_apm_application"

    def test_business_and_unknown_ids_are_not_guessed(self):
        from bkmonitor.iam.action import canonicalize_action_id

        assert canonicalize_action_id("view_business") == "view_business"
        assert canonicalize_action_id("unknown_action_v2") == "unknown_action_v2"

    def test_registered_legacy_ids_are_available_for_compatible_responses(self):
        from bkmonitor.iam.action import get_legacy_action_ids

        assert get_legacy_action_ids("view_apm_application") == ("view_apm_application_v2",)
        assert get_legacy_action_ids("view_incident") == ()

    def test_all_declared_v3_ids_have_consistent_compatibility_mappings(self):
        from bkmonitor.iam.action import canonicalize_action_id, get_legacy_action_ids

        for name, (v3_action_id, _action_type, _action_name) in OLD_ACTION_SNAPSHOT.items():
            business_action_id = getattr(ActionEnum, name).id
            assert canonicalize_action_id(v3_action_id) == business_action_id
            expected_aliases = () if v3_action_id == business_action_id else (v3_action_id,)
            assert get_legacy_action_ids(business_action_id) == expected_aliases

    def test_duplicate_legacy_alias_is_rejected(self):
        from bkmonitor.iam.action import _build_legacy_action_id_mappings

        actions = {
            "first": ActionDef(
                id="first", name="first", resource_type="", extensions={"v3": {"action_id": "shared_v2"}}
            ),
            "second": ActionDef(
                id="second", name="second", resource_type="", extensions={"v3": {"action_id": "shared_v2"}}
            ),
        }

        with pytest.raises(RuntimeError, match="duplicate IAM action alias"):
            _build_legacy_action_id_mappings(actions)


class TestProviderVisibility:
    """v4 平台纯净性：v3 兼容遗留的已废弃 space 级仪表盘操作不在 v4 注册。

    definitions 通过 extensions["exclude_providers"] 声明可见性，
    V4Migrator 的 plan/diff 据此过滤；roles 不再绑定这两个 action。
    """

    def _plan_v4_full(self, real_schema):
        from unittest.mock import MagicMock

        from bkmonitor.iam.adapters.v4.codec import MonitorV4Codec
        from bkmonitor.iam.iam_engine.schema.diff import EntityKind
        from bkmonitor.iam.iam_v4.config import V4SystemInfo
        from bkmonitor.iam.iam_v4.migrator import V4Migrator

        system = V4SystemInfo(id="bk_monitor_v4", name="监控平台V4")
        migrator = V4Migrator(client=MagicMock(), schema=real_schema, system_def=system, codec=MonitorV4Codec())
        plan = migrator.plan_migration(scope="full")
        return plan, EntityKind

    def test_deprecated_dashboard_actions_excluded_from_v4(self, real_schema):
        plan, EntityKind = self._plan_v4_full(real_schema)
        action_ids = {c.entity_id for c in plan.changes if c.kind == EntityKind.ACTION}
        assert "view_dashboard" not in action_ids
        assert "manage_dashboard" not in action_ids
        # 51 = 53 - 2 个已废弃；v4 实例级语义仍由 single_dashboard 承担
        assert len(action_ids) == 51
        assert "view_single_dashboard" in action_ids
        assert "edit_single_dashboard" in action_ids

    def test_deprecated_dashboard_actions_still_visible_to_v3(self, real_schema):
        from bkmonitor.iam.iam_engine.schema.visibility import is_visible_to

        assert is_visible_to(Actions.VIEW_DASHBOARD, "v3") is True
        assert is_visible_to(Actions.MANAGE_DASHBOARD, "v3") is True
        assert is_visible_to(Actions.VIEW_DASHBOARD, "v4") is False
        assert is_visible_to(Actions.MANAGE_DASHBOARD, "v4") is False

    def test_roles_no_longer_bind_deprecated_dashboard_actions(self, real_schema):
        assert real_schema.roles_containing_action("view_dashboard") == []
        assert real_schema.roles_containing_action("manage_dashboard") == []
        # v4 的仪表盘语义由 grafana_dashboard 实例级的 single_dashboard 操作承担
        assert real_schema.roles_containing_action("view_single_dashboard")
        assert real_schema.roles_containing_action("edit_single_dashboard")
