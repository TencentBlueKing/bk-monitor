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
# MonitorV4Codec —— 监控平台的 IAM v4 命名编解码器
#
# 规则：
#   action / resource_type / role：与业务规范化命名完全一致（恒等）。
#
#   resource_id：
#       - space:           "3"  <-> "space|3"
#                          "-42" <-> "space|-42"
#         （加 "space|" 前缀，避免与其他数字型 ID 混淆；同时把首字符从
#          可能的 "-" 变为字母 "s"，符合 v4 平台对 ID 首字符的约束。）
#       - apm_application / grafana_dashboard / rum_application: 恒等
#
#   decode 兜底：
#       解码 space 时，若输入没有 "space|" 前缀但能作为整数解析
#       （历史数据、极端兼容路径），视作已是业务 ID 原样返回。
#
# 配置方式：
#   在 IAM_FRAMEWORK.PROVIDER_CATALOG["v4"].options.codec_class 中配置本类的 dotted path：
#       "codec_class": "bkmonitor.iam.adapters.v4.codec.MonitorV4Codec"
#   Provider 在初始化时自动加载。业务可自由替换为自己的 codec 实现。
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging

from ...iam_engine.provider.codec import IdentityCodec

logger = logging.getLogger(__name__)

_SPACE_PREFIX = "space|"


class MonitorV4Codec(IdentityCodec):
    """监控平台 v4 命名编解码器。

    仅覆盖 resource_id 的 space 分支；其他符号均恒等。
    """

    def encode_resource_id(self, rt_id: str, business_id: str) -> str:
        """编码 resource_id：业务 ID → v4 方言 ID。

        Args:
            rt_id: 业务资源类型 ID（如 "space"）
            business_id: 业务资源实例 ID（如 "3"）

        Returns:
            v4 方言 ID：space 类型加 "space|" 前缀，其他类型恒等。

        Raises:
            无（纯函数，幂等，不抛异常）
        """
        if rt_id == "space":
            if business_id.startswith(_SPACE_PREFIX):
                return business_id
            return f"{_SPACE_PREFIX}{business_id}"
        return business_id

    def decode_resource_id(self, rt_id: str, dialect_id: str) -> str:
        """解码 resource_id：v4 方言 ID → 业务 ID。

        Args:
            rt_id: 业务资源类型 ID
            dialect_id: v4 方言 ID（如 "space|3"）

        Returns:
            业务 ID（去 "space|" 前缀）；无前缀时视作已是业务 ID，原样返回。

        Raises:
            无（纯函数，做兜底兼容，不抛异常）
        """
        if rt_id == "space":
            if dialect_id.startswith(_SPACE_PREFIX):
                return dialect_id[len(_SPACE_PREFIX) :]
            try:
                int(dialect_id)
            except (TypeError, ValueError):
                pass
            return dialect_id
        return dialect_id


__all__ = ["MonitorV4Codec"]
