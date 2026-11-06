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
#       - space:           "3"  <-> "3"
#                          "-42" <-> "-42"
#         与 BKLog 共用空间编解码，原始数字字符串不添加前缀。
#       - apm_application / grafana_dashboard / rum_application: 恒等
#
# 产品装配显式注入本 Codec；Provider 不再动态加载 dotted path。
# ---------------------------------------------------------------------------

from __future__ import annotations

from iam_engine.provider.codec import IdentityCodec
from iam_engine.v4.codec import SpaceResourceCodec


class MonitorV4Codec(SpaceResourceCodec, IdentityCodec):
    """监控平台 v4 命名编解码器。

    资源 ID 共用字符串归一化；其他符号均恒等。
    """

    def encode_resource_for_auth(self, resource):
        from iam_engine.core.requests import to_definition_id

        rt = to_definition_id(resource.type)
        payload = {"type": self.encode_resource_type(rt), "id": self.encode_resource_id(rt, str(resource.id))}
        attributes = dict(resource.attributes)
        if resource.ancestor_chain:
            path = (
                "/"
                + "/".join(
                    f"{self.encode_resource_type(to_definition_id(parent.type))},"
                    f"{self.encode_resource_id(to_definition_id(parent.type), str(parent.id))}"
                    for parent in resource.ancestor_chain
                )
                + "/"
            )
            attributes["_bk_iam_path_"] = path
        if attributes:
            payload["attributes"] = attributes
        return payload

    def encode_resource_for_apply(self, resource):
        from iam_engine.core.requests import to_definition_id

        rt = to_definition_id(resource.type)
        return {
            "type": self.encode_resource_type(rt),
            "id": self.encode_resource_id(rt, str(resource.id)),
            "ancestors": [
                {
                    "type": self.encode_resource_type(to_definition_id(parent.type)),
                    "id": self.encode_resource_id(to_definition_id(parent.type), str(parent.id)),
                }
                for parent in resource.ancestor_chain
            ],
        }


__all__ = ["MonitorV4Codec"]
