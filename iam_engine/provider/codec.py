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
# NameCodec —— 业务规范化命名 ↔ 平台方言命名 的双向纯函数编解码器
#
# 使命：
#   iam_engine 层始终使用"业务规范化命名"（如 action="view_business"、
#   resource_type="space"、resource_id="3"），"平台方言命名"（如 v3 的
#   action="view_business_v2"、v4 的 resource_id="space|3"）仅在 Provider
#   内部的边界上出现。NameCodec 是这两种命名之间的双射。
#
# 覆盖的四类符号：
#   - action_id       ← 业务动作名 vs 平台注册的 action ID
#   - resource_type   ← 业务资源类型名 vs 平台注册的 resource_type ID
#   - resource_id     ← 业务实例 ID    vs 平台实际存储的实例 ID
#   - role_id         ← 业务角色名     vs 平台注册的 role ID
#
# 契约：
#   - 所有方法必须是"纯函数"：无 IO、无副作用、幂等。
#   - encode 与 decode 严格双射：decode(encode(x)) == x。
#   - resource_id 需按 resource_type 分派规则（不同资源类型可能规则不同）。
#
# 使用位置：
#   - Provider 内部的公共接口方法（is_allowed/batch_*/get_apply_url/回调）
#     在跨"业务 ↔ 平台"边界的进出口调用。
#   - iam_engine 层本身不使用 codec，不感知任何方言。
# ---------------------------------------------------------------------------

from typing import Protocol, runtime_checkable


@runtime_checkable
class NameCodec(Protocol):
    """业务规范化命名 ↔ 平台方言命名 的编解码 Protocol。

    - encode_*: 业务规范化名 → 平台方言名（出站边界调用）
    - decode_*: 平台方言名 → 业务规范化名（入站边界调用）
    """

    # ---------------- action ----------------

    def encode_action(self, action_id: str) -> str: ...

    def decode_action(self, dialect_action_id: str) -> str: ...

    # ---------------- resource_type ----------------

    def encode_resource_type(self, rt_id: str) -> str: ...

    def decode_resource_type(self, dialect_rt_id: str) -> str: ...

    # ---------------- resource_id（需按 resource_type 分派） ----------------

    def encode_resource_id(self, rt_id: str, business_id: str) -> str: ...

    def decode_resource_id(self, rt_id: str, dialect_id: str) -> str: ...

    # ---------------- role ----------------

    def encode_role(self, role_id: str) -> str: ...

    def decode_role(self, dialect_role_id: str) -> str: ...


class IdentityCodec:
    """恒等编解码器 —— 默认实现。

    所有 encode/decode 都返回原值不变。适用于"业务命名与平台方言完全一致"
    的 Provider（例如当前 v4 就是这种情况）。

    Provider 若只有部分符号需要方言映射（如 v3 只有 action_id 需要
    `_v2` 后缀），推荐继承本类，仅覆盖需要的方法。
    """

    def encode_action(self, action_id: str) -> str:
        return action_id

    def decode_action(self, dialect_action_id: str) -> str:
        return dialect_action_id

    def encode_resource_type(self, rt_id: str) -> str:
        return rt_id

    def decode_resource_type(self, dialect_rt_id: str) -> str:
        return dialect_rt_id

    def encode_resource_id(self, rt_id: str, business_id: str) -> str:
        return business_id

    def decode_resource_id(self, rt_id: str, dialect_id: str) -> str:
        return dialect_id

    def encode_role(self, role_id: str) -> str:
        return role_id

    def decode_role(self, dialect_role_id: str) -> str:
        return dialect_role_id


__all__ = ["IdentityCodec", "NameCodec"]
