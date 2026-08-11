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
# MonitorV3Codec —— 监控平台 IAM v3 action_id 编解码器
#
# 规则：
#   action_id：
#       业务 action_id → V3 平台 action_id：
#           经历了 V1→V2 迁移的 action 带 _v2 后缀，
#           新增 action 的 V3 平台 ID 与业务 ID 一致（恒等）。
#           映射表从 ActionDef.extensions["v3"]["action_id"] 构建。
#
#   resource_type / resource_id / role：
#       V3 全部恒等映射，继承 IdentityCodec。
#
# 配置方式：
#   在 IAM_FRAMEWORK.PROVIDERS[*].options.codec_class 中配置本类的 dotted path：
#       "codec_class": "bkmonitor.iam.definitions.codec_v3.MonitorV3Codec"
#   Provider 在初始化时自动加载。
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import TYPE_CHECKING

from ..iam_engine.provider.codec import IdentityCodec

if TYPE_CHECKING:
    from ..iam_engine.schema.registry import SchemaRegistry


class MonitorV3Codec(IdentityCodec):
    """V3 action_id 映射编解码器。

    仅覆盖 encode_action / decode_action；其他符号全部恒等。
    映射表在构造时从 SchemaRegistry 的 extensions["v3"]["action_id"] 构建，
    只存储 action_id 与业务 ID 不同的条目，恒等 action 走 dict.get 兜底。
    """

    def __init__(self, schema: SchemaRegistry | None = None):
        """初始化 V3 编解码器。

        Args:
            schema: 已冻结的 SchemaRegistry，从 extensions["v3"] 构建映射表。
                    为 None 时所有操作恒等（用于测试/兜底）。
        """
        super().__init__()
        self._fwd: dict[str, str] = {}  # 业务 action_id → V3 平台 action_id
        self._rev: dict[str, str] = {}  # V3 平台 action_id → 业务 action_id
        self._action_types: dict[str, str] = {}  # 业务 action_id → type ("view"/"manage")

        if schema is not None:
            for action_def in schema.all_actions():
                v3_ext = dict(action_def.extensions.get("v3", {}))
                v3_action_id = v3_ext.get("action_id", "")
                action_type = v3_ext.get("type", "")
                # 只对与业务 ID 不同的 action_id 建立映射（带 _v2 后缀的历史迁移 action）
                if v3_action_id and v3_action_id != action_def.id:
                    self._fwd[action_def.id] = v3_action_id
                    self._rev[v3_action_id] = action_def.id
                # 缓存 action type，用于读写策略判断
                if action_type:
                    self._action_types[action_def.id] = action_type

    # ================================================================
    # action_id 编解码
    # ================================================================

    def encode_action(self, action_id: str) -> str:
        """业务 action_id → V3 平台 action_id。"""
        return self._fwd.get(action_id, action_id)

    def decode_action(self, dialect_action_id: str) -> str:
        """V3 平台 action_id → 业务 action_id。"""
        return self._rev.get(dialect_action_id, dialect_action_id)

    # ================================================================
    # 辅助方法
    # ================================================================

    def is_read_action(self, business_action_id: str) -> bool:
        """判断是否为读操作（用于 is_allowed_with_cache 策略）。"""
        return self._action_types.get(business_action_id) == "view"
