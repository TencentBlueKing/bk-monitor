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
# V4NameCodec —— IAM v4 平台方言编解码
#
# 规则（本 Provider 独有，业务侧和 iam_engine 不感知）：
#
#   action_id / resource_type / role_id：
#       与业务规范化命名完全一致（恒等）。
#
#   resource_id：
#       - space:               "3"           <-> "space|3"
#                              "-42"         <-> "space|-42"
#         （加 "space|" 前缀，避免与其他数字型 ID 混淆；同时把首字符从
#          可能的 "-" 变为字母 "s"，符合 v4 平台对 ID 首字符的约束。）
#       - apm_application:     恒等
#       - grafana_dashboard:   恒等（业务侧已经是 "{org_id}|{uid}"
#                              或 "folder:{org_id}|{folder_id}" 复合形态）
#       - rum_application:     恒等
#
#   decode 兜底：
#       解码 space 时，若发现输入没有 "space|" 前缀但能作为整数解析
#       （历史数据、极端兼容路径），视作已是业务 ID 原样返回，仅打 debug 日志。
# ---------------------------------------------------------------------------

import logging

from ..iam_engine.provider.codec import IdentityCodec

logger = logging.getLogger(__name__)

# resource_type = "space" 时使用的方言前缀
_SPACE_PREFIX = "space|"


class V4NameCodec(IdentityCodec):
    """IAM v4 平台的命名编解码器。

    仅覆盖 resource_id 的 space 分支；action / resource_type / role
    以及其他资源类型均保持恒等（继承自 IdentityCodec）。
    """

    def encode_resource_id(self, rt_id: str, business_id: str) -> str:
        if rt_id == "space":
            # 已经带前缀（防御性）：幂等
            if business_id.startswith(_SPACE_PREFIX):
                return business_id
            return f"{_SPACE_PREFIX}{business_id}"
        # 其他资源类型：apm_application / grafana_dashboard / rum_application 恒等
        return business_id

    def decode_resource_id(self, rt_id: str, dialect_id: str) -> str:
        if rt_id == "space":
            if dialect_id.startswith(_SPACE_PREFIX):
                return dialect_id[len(_SPACE_PREFIX) :]
            # 兜底：无前缀的历史 / 兼容路径，视作业务 ID 原样返回
            try:
                int(dialect_id)  # 至少形似合法业务 ID
                logger.debug(
                    "[V4NameCodec] decode space without prefix, fallback to raw id: %s",
                    dialect_id,
                )
            except (TypeError, ValueError):
                logger.debug(
                    "[V4NameCodec] decode space unexpected shape: %s",
                    dialect_id,
                )
            return dialect_id
        # 其他资源类型：恒等
        return dialect_id


__all__ = ["V4NameCodec"]
