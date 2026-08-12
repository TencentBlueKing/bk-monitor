"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# action.py — ActionEnum 定义（自动从 definitions/actions.py 派生）
#
# 改造说明 (2026-08):
#   - ActionEnum 成员现在是 ActionDef 实例，不再是 ActionMeta 实例
#   - ActionEnum.XXX.id 返回 Business ID（如 "view_business"），而非 V3 平台 ID
#   - V3 平台 ID 映射由 v3/codec.py 的处理
#   - 新增 action 只需在 definitions/actions.py 添加 ActionDef，ActionEnum 自动感知
#   - ActionMeta 类已删除；旧代码应使用 ActionDef 或直接使用 ActionEnum 成员
#
# 外部调用者兼容性：
#   - BusinessActionPermission([ActionEnum.VIEW_SYNTHETIC])  ← 不变
#   - Permission().is_allowed_by_biz(biz_id, ActionEnum.VIEW_BUSINESS) ← 不变
#   - ActionEnum.VIEW_SINGLE_DASHBOARD.id  ← 值从 "view_single_dashboard" 不变（该 action 无 _v2 后缀）
#
#   注意：依赖 ActionMeta 类、_all_actions、get_action_by_id 的旧代码
#   （permission.py、drf.py 等）将在后续步骤中改造。
# ---------------------------------------------------------------------------

from __future__ import annotations

from bkmonitor.iam.definitions.actions import Actions as _NewActions
from bkmonitor.iam.iam_engine.schema.definitions import ActionDef


# ============================================================================
# ActionEnum — 从 definitions/actions.py 自动生成
# ============================================================================


class ActionEnum:
    """IAM 操作枚举。

    成员由 definitions/actions.py 的 Actions 类自动生成，
    每个成员是一个 ActionDef 实例。新增 action 只需在 definitions/actions.py
    添加定义即可，无需修改本文件。

    ActionDef 属性：
        .id             — Business action ID（如 "view_business"）
        .name           — 中文名（如 "业务访问"）
        .resource_type  — 关联资源类型 ID；空字符串表示无资源
        .description    — 描述
        .extensions     — Provider 私有扩展字段（如 v3 的 type/version/action_id）
    """


# 遍历 Actions 类，将每个 ActionDef 成员自动挂载到 ActionEnum
for _act_name, _act_def in vars(_NewActions).items():
    if _act_name.startswith("_"):
        continue
    if not isinstance(_act_def, ActionDef):
        continue
    setattr(ActionEnum, _act_name, _act_def)


# ============================================================================
# _all_actions — 所有 action 的 {business_id: ActionDef} 映射
# ============================================================================

_all_actions: dict[str, ActionDef] = {
    action.id: action for action in ActionEnum.__dict__.values() if isinstance(action, ActionDef)
}


def get_action_by_id(action_id: str | ActionDef) -> ActionDef:
    """
    根据动作 ID 获取动作实例（使用 Business ID）。

    兼容旧接口：如果传入的已经是 ActionDef 实例，则直接返回。
    """
    if isinstance(action_id, ActionDef):
        return action_id

    if action_id not in _all_actions:
        from core.errors.iam import ActionNotExistError

        raise ActionNotExistError({"action_id": action_id})

    return _all_actions[action_id]


# ============================================================================
# 以下函数已弃用，仅保留以防止 import 报错，将在后续步骤中清理
# ============================================================================


# DEPRECATED: fetch_related_actions — 依赖旧 ActionMeta.related_actions，
# 该字段在 ActionDef 中不存在且原有调用已全部注释。
# 保留仅为兼容 import，始终返回空字典。
def fetch_related_actions(actions: list[ActionDef | str]) -> dict[str, ActionDef]:
    """
    [DEPRECATED] 递归获取 action 动作依赖列表。

    依赖旧 ActionMeta.related_actions 字段，ActionDef 中无此概念。
    所有原有调用（permission.py 中）已注释，此函数不再使用。
    """
    return {}


# DEPRECATED: generate_all_actions_json — 依赖旧 ActionMeta.to_json()，
# ActionDef 无此方法。旧 migration JSON 生成方式已由 iam_engine 替代。
def generate_all_actions_json() -> list:
    """
    [DEPRECATED] 生成 migrations 的 json 配置。

    依赖旧 ActionMeta.to_json()；新的 migration 机制由 iam_engine 提供。
    """
    return []


# ============================================================================
# Action 集合常量（使用 Business ID）
# ============================================================================

# 权限全集
ALL_ACTION_IDS = set(_all_actions.keys())

# 默认最小监控功能使用权限
MINI_ACTION_IDS = [
    ActionEnum.VIEW_BUSINESS.id,
    ActionEnum.EXPLORE_METRIC.id,
    ActionEnum.VIEW_EVENT.id,
    ActionEnum.MANAGE_EVENT.id,
    ActionEnum.VIEW_NOTIFY_TEAM.id,
    ActionEnum.MANAGE_NOTIFY_TEAM.id,
    ActionEnum.VIEW_RULE.id,
    ActionEnum.MANAGE_RULE.id,
    ActionEnum.VIEW_DOWNTIME.id,
    ActionEnum.MANAGE_DOWNTIME.id,
    ActionEnum.VIEW_CUSTOM_METRIC.id,
    ActionEnum.MANAGE_CUSTOM_METRIC.id,
    ActionEnum.VIEW_CUSTOM_EVENT.id,
    ActionEnum.MANAGE_CUSTOM_EVENT.id,
    ActionEnum.VIEW_SINGLE_DASHBOARD.id,
    ActionEnum.EDIT_SINGLE_DASHBOARD.id,
    ActionEnum.MANAGE_DATASOURCE.id,
    ActionEnum.EXPORT_CONFIG.id,
    ActionEnum.IMPORT_CONFIG.id,
    ActionEnum.VIEW_APM_APPLICATION.id,
    ActionEnum.MANAGE_APM_APPLICATION.id,
    ActionEnum.VIEW_RUM_APPLICATION.id,
    ActionEnum.MANAGE_RUM_APPLICATION.id,
    ActionEnum.VIEW_INCIDENT.id,
    ActionEnum.MANAGE_INCIDENT.id,
    ActionEnum.USE_PUBLIC_SYNTHETIC_LOCATION.id,
]

# CMDB（主机依赖）权限
CMDB_REQUIRE_ACTION_IDS = [
    ActionEnum.MANAGE_COLLECTION.id,
    ActionEnum.VIEW_COLLECTION.id,
    ActionEnum.MANAGE_HOST.id,
    ActionEnum.VIEW_HOST.id,
    ActionEnum.MANAGE_PLUGIN.id,
    ActionEnum.VIEW_PLUGIN.id,
    ActionEnum.MANAGE_SYNTHETIC.id,
    ActionEnum.VIEW_SYNTHETIC.id,
]

# 管理权限
ADMIN_ACTION_IDS = [
    ActionEnum.MANAGE_CALENDAR.id,
    ActionEnum.MANAGE_REPORT.id,
    ActionEnum.MANAGE_GLOBAL_SETTING.id,
    ActionEnum.VIEW_GLOBAL_SETTING.id,
    ActionEnum.MANAGE_PUBLIC_PLUGIN.id,
    ActionEnum.MANAGE_PUBLIC_ACTION_CONFIG.id,
    ActionEnum.MANAGE_PUBLIC_SYNTHETIC_LOCATION.id,
    ActionEnum.VIEW_SELF_STATE.id,
]
