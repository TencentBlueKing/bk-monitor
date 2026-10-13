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
# iam.definitions — 平台无关的权限模型定义
#
# Action / ResourceType / Role 的定义不绑定任何 IAM 版本（v3/v4），
# 各版本 Provider 共用同一套 schema。
#
from bkmonitor.iam.action import ActionEnum as Actions
from bkmonitor.iam.definitions.resource_types import ResourceTypes
from bkmonitor.iam.definitions.roles import Roles

from types import MappingProxyType
from iam_engine.schema.definitions import ActionDef, ResourceTypeDef, RoleDef

# Static indexes of the authoritative product definitions. No registration,
# freezing lifecycle, loaders or independent synchronization snapshots.
from bkmonitor.iam.action import ActionMeta, canonicalize_action_id

# Derive protocol-neutral metadata from the untouched public V3 definitions.
# Only the explicit ID mapping is additional; no independently editable Action model.
actions = MappingProxyType({
    canonicalize_action_id(a.id): ActionDef(
        id=canonicalize_action_id(a.id), name=a.name, description=a.description,
        resource_type=a.related_resource_types[0]["id"] if a.related_resource_types else "",
        extensions={"v3": {
            "action_id": a.id, "type": a.type, "version": a.version,
            "name_en": a.name_en, "description_en": a.description_en, "related_actions": a.related_actions,
        }},
    )
    for a in vars(Actions).values() if isinstance(a, ActionMeta)
})
resource_types = MappingProxyType({r.id: r for r in vars(ResourceTypes).values() if isinstance(r, ResourceTypeDef)})
roles = MappingProxyType({r.id: r for r in vars(Roles).values() if isinstance(r, RoleDef)})
# These historical V3 space actions were replaced by instance Dashboard actions
# in the confirmed V4 model. Retain them only for the original V3 contract.
v4_actions = MappingProxyType({k: v for k, v in actions.items() if k not in {"view_dashboard", "manage_dashboard"}})

__all__ = ["Actions", "ResourceTypes", "Roles", "actions", "resource_types", "roles", "v4_actions"]
