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
#           映射表从 Actions 定义类直接提取（同包的 actions.py），
#           无需 schema 注入。
#
#   resource_type / resource_id / role：
#       V3 全部恒等映射，继承 IdentityCodec。
#
# 配置方式：
#   在 IAM_FRAMEWORK.PROVIDERS[*].options.codec_class 中配置本类的 dotted path：
#       "codec_class": "bkmonitor.iam.adapters.v3.codec.MonitorV3Codec"
#   Provider 在初始化时自动加载，无需手动传参。
# ---------------------------------------------------------------------------

from __future__ import annotations

from ...iam_engine.provider.codec import IdentityCodec


def _build_v3_mappings():
    """从 Actions 定义类直接提取 v3 action_id 映射表（模块加载时执行一次）。

    使用与 schema.loaders.load_from_class 相同的 vars() 遍历模式，
    保证与 schema 注册的 action 集合完全一致。
    """
    from ...definitions.actions import Actions

    fwd: dict[str, str] = {}
    rev: dict[str, str] = {}
    action_types: dict[str, str] = {}

    for name, action in vars(Actions).items():
        if name.startswith("_"):
            continue
        if not hasattr(action, "id"):
            continue
        v3_ext = action.extensions.get("v3", {})
        v3_action_id = v3_ext.get("action_id", "")
        action_type = v3_ext.get("type", "")
        # 只对与业务 ID 不同的 action_id 建立映射（带 _v2 后缀的历史迁移 action）
        if v3_action_id and v3_action_id != action.id:
            fwd[action.id] = v3_action_id
            rev[v3_action_id] = action.id
        # 缓存 action type，用于读写策略判断
        if action_type:
            action_types[action.id] = action_type

    return fwd, rev, action_types


_FWD, _REV, _ACTION_TYPES = _build_v3_mappings()


class MonitorV3Codec(IdentityCodec):
    """V3 action_id 映射编解码器。

    仅覆盖 encode_action / decode_action；其他符号全部恒等。
    映射表在模块加载时从 Actions 定义类提取，无 schema 依赖。

    支持通过构造参数覆盖映射表（测试/自定义场景）：
        MonitorV3Codec(action_id_map={"view_business": "view_business_v2"},
                       action_types={"view_business": "view"})
    """

    def __init__(
        self,
        action_id_map: dict[str, str] | None = None,
        action_types: dict[str, str] | None = None,
    ):
        """初始化 V3 编解码器。

        Args:
            action_id_map: 业务 action_id → V3 平台 action_id 映射。
                           为 None 时使用从 Actions 类自动提取的默认映射。
            action_types: 业务 action_id → type 映射（"view"/"manage"）。
                          为 None 时使用从 Actions 类自动提取的默认映射。
        """
        super().__init__()
        if action_id_map is not None:
            self._fwd: dict[str, str] = dict(action_id_map)
            self._rev: dict[str, str] = {v: k for k, v in self._fwd.items()}
        else:
            self._fwd = _FWD
            self._rev = _REV
        self._action_types: dict[str, str] = dict(action_types) if action_types is not None else _ACTION_TYPES

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
