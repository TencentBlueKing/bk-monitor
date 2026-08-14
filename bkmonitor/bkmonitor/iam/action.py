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
# 改造说明:
#   - ActionEnum 成员是 ActionMeta 实例（ActionDef 子类，兼容旧 ActionMeta 接口）
#   - ActionEnum.XXX.id 返回 Business ID（如 "view_business"），而非 V3 平台 ID
#   - 平台 ID 映射由 codec.py 的处理
#   - 新增 action 只需在 definitions/actions.py 添加 ActionDef，ActionEnum 自动感知
#
# 外部调用者兼容性：
#   - BusinessActionPermission([ActionEnum.VIEW_SYNTHETIC])  ← 不变
#   - Permission().is_allowed_by_biz(biz_id, ActionEnum.VIEW_BUSINESS) ← 不变
#   - ActionEnum.VIEW_SINGLE_DASHBOARD.id  ← 值 "view_single_dashboard" 不变
#   - action.type / action.related_resource_types 等旧 ActionMeta 属性 ← 由兼容 property 提供
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import Any

from bkmonitor.iam.definitions.actions import Actions as _NewActions
from bkmonitor.iam.definitions.resource_types import ResourceTypes as _NewResourceTypes
from bkmonitor.iam.iam_engine.schema.definitions import ActionDef, ResourceTypeDef


# 资源类型 ID → V3 system_id 映射（由 definitions/resource_types.py 派生）
_RESOURCE_TYPE_SYSTEM_IDS: dict[str, str] = {
    rt.id: rt.extensions.get("v3", {}).get("system_id", "")
    for rt in vars(_NewResourceTypes).values()
    if isinstance(rt, ResourceTypeDef)
}


# ============================================================================
# ActionMeta — 旧接口兼容类（ActionDef 子类）
# ============================================================================


class ActionMeta(ActionDef):
    """旧 ActionMeta 兼容类（对外接口保活）。

    框架内部统一使用 ActionDef：id 为框架操作 ID（Business ID，如 "view_business"），
    V3 平台 ID 由 codec 编解码（extensions["v3"]["action_id"]）。本类以 property 提供
    旧 ActionMeta 接口：

      * type                   — ABAC 动作分类 "view"/"manage"（extensions["v3"]["type"]，
                                 不是任何 id/别名）
      * version                — extensions["v3"]["version"]
      * related_resource_types — 旧格式 [{"id": ..., "system_id": ...}]，由 resource_type 派生
      * name_en / description_en / related_actions — 新定义无对应字段，返回空值
    """

    @property
    def type(self) -> str:
        """ABAC 动作分类（"view" / "manage"）。等价 extensions["v3"]["type"]。"""
        return self.extensions.get("v3", {}).get("type", "")

    @property
    def version(self) -> int:
        return self.extensions.get("v3", {}).get("version", 0)

    @property
    def related_resource_types(self) -> list[dict[str, Any]]:
        if not self.resource_type:
            return []
        return [{"id": self.resource_type, "system_id": _RESOURCE_TYPE_SYSTEM_IDS.get(self.resource_type, "")}]

    @property
    def name_en(self) -> str:
        return ""

    @property
    def description_en(self) -> str:
        return ""

    @property
    def related_actions(self) -> list:
        return []

    def is_read_action(self) -> bool:
        return self.type == "view"

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "name_en": self.name_en,
            "type": self.type,
            "version": self.version,
            "related_resource_types": self.related_resource_types,
            "related_actions": self.related_actions,
            "description": self.description,
            "description_en": self.description_en,
        }

    @classmethod
    def from_def(cls, action_def: ActionDef) -> ActionMeta:
        """将 ActionDef 包装为 ActionMeta 兼容实例。"""
        return cls(
            id=action_def.id,
            name=action_def.name,
            resource_type=action_def.resource_type,
            description=action_def.description,
            extensions=action_def.extensions,
        )


# ============================================================================
# ActionEnum — 从 definitions/actions.py 自动生成
# ============================================================================


class ActionEnum:
    """IAM 操作枚举。

    成员由 definitions/actions.py 的 Actions 类自动生成，
    每个成员是一个 ActionMeta 实例（ActionDef 子类，兼容旧接口）。
    新增 action 只需在 definitions/actions.py 添加定义即可，无需修改本文件。

    属性：
        .id             — Business action ID（如 "view_business"）
        .name           — 中文名（如 "业务访问"）
        .resource_type  — 关联资源类型 ID；空字符串表示无资源
        .description    — 描述
        .extensions     — Provider 私有扩展字段（如 v3 的 type/version/action_id）
        .type           — 兼容旧接口：ABAC 分类 "view"/"manage"
        .related_resource_types — 兼容旧接口：旧格式资源类型列表
    """


# 遍历 Actions 类，将每个 ActionDef 包装为 ActionMeta 挂载到 ActionEnum
for _act_name, _act_def in vars(_NewActions).items():
    if _act_name.startswith("_"):
        continue
    if not isinstance(_act_def, ActionDef):
        continue
    setattr(ActionEnum, _act_name, ActionMeta.from_def(_act_def))


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
