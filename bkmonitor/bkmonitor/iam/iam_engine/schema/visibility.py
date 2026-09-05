"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Provider 可见性过滤 —— Schema 实体对指定 Provider 是否可见
#
# 通过 schema 实体（ResourceTypeDef / ActionDef / RoleDef）的 extensions 字典，
# 声明"这个实体只属于某些 Provider"或"这个实体不应该在某些 Provider 上出现"，
# 让每个 Provider 的 Migrator 在 diff / apply 时自动过滤：
#
#   ActionDef(
#       id="view_ai_report",
#       name="查看 AI 报告",
#       extensions={"only_providers": ("v4",)},   # 只在 v4 上注册
#   )
#
#   ResourceTypeDef(
#       id="legacy_dashboard",
#       name="老仪表盘",
#       extensions={"exclude_providers": ("v4",)},  # v4 平台不维护
#   )
#
# 保留键约定（写在 extensions 字典里，都是可选，都是 tuple[str, ...]）：
#   * only_providers    —— 白名单；只有列出的 provider 可见
#   * exclude_providers —— 黑名单；列出的 provider 不可见
#
# 判定规则（独立判断，任一命中即拒绝）：
#   1. 若 only_providers 非空且 provider_name 不在其中 → False
#   2. 若 exclude_providers 非空且 provider_name 在其中 → False
#   3. 否则 → True（默认对所有 provider 可见，保持向后兼容）
# ---------------------------------------------------------------------------

from typing import Any, Protocol


class _HasExtensions(Protocol):
    """Duck-typed 协议：任何持有 extensions 字典的 schema 实体都可判定。"""

    extensions: Any


def is_visible_to(entity: _HasExtensions, provider_name: str) -> bool:
    """判断 schema 实体是否对指定 provider 可见。

    Args:
        entity: 拥有 ``extensions`` 属性的 schema 实体
                （ResourceTypeDef / ActionDef / RoleDef）。
        provider_name: Provider 标识（如 ``"v4"``、``"v3"``）。

    Returns:
        True  —— 实体对该 provider 可见，应参与 diff / apply。
        False —— 实体对该 provider 隐藏，应从 diff 输入中过滤掉。
    """
    ext = getattr(entity, "extensions", None) or {}

    only = ext.get("only_providers")
    if only and provider_name not in only:
        return False

    exclude = ext.get("exclude_providers")
    if exclude and provider_name in exclude:
        return False

    return True


def is_change_visible_to(change: Any, provider_name: str) -> bool:
    """判断迁移 Change 对指定 provider 是否可见。

    与 :func:`is_visible_to` 的区别：本函数以 Change 的 payload（``after``
    优先，``before`` 兜底）中的 ``extensions`` 字段为判定依据，用于 Provider
    在 ``apply_migration`` 入口对"文件迁移链路"的 Change 做过滤（迁移文件
    生成阶段是 provider 中立的，可见性过滤下沉到 apply 阶段各自处理）。

    Args:
        change: schema.diff.Change 实例（这里用 Any 是为了避免循环依赖）。
        provider_name: Provider 标识（如 ``"v4"``、``"v3"``）。

    Returns:
        True  —— Change 对该 provider 可见，应参与 apply。
        False —— Change 对该 provider 隐藏，应从 apply 输入中过滤掉。

    说明：
        * SYSTEM 类 Change 的 payload 无 extensions 概念，默认返回 True。
        * CREATE / UPDATE 以 after 为准，DELETE 以 before 为准。
    """
    payload = getattr(change, "after", None) or getattr(change, "before", None) or {}
    if not isinstance(payload, dict):
        return True
    ext = payload.get("extensions") or {}
    if not isinstance(ext, dict):
        return True

    only = ext.get("only_providers")
    if only and provider_name not in only:
        return False

    exclude = ext.get("exclude_providers")
    if exclude and provider_name in exclude:
        return False

    return True


__all__ = ["is_visible_to", "is_change_visible_to"]
