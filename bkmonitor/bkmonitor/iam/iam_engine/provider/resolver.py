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
# ResourceResolver — 资源实例补全协议（类似 NameCodec）
#
# 框架在鉴权前自动调用 resolve()，补全 ResourceInstance 的业务属性
# （name / ancestor_chain / attributes）。上层只需传 type + id，框架负责补全。
#
# 用法：
#   class MyResolver:
#       def resolve(self, resource: ResourceInstance) -> ResourceInstance:
#           ...  # 查 DB、补祖先链、填名称
#
# 注入方式（同 codec）：
#   IAM_FRAMEWORK.PROVIDER_CATALOG[<name>].options.resolver_class = "dotted.path.MyResolver"
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..core.types import ResourceInstance


@runtime_checkable
class ResourceResolver(Protocol):
    """资源实例补全协议。

    Provider 在编码资源前自动调用 resolve()，将仅含 type + id 的
    ResourceInstance 补全为含 name / ancestor_chain / attributes 的完整实例。
    用户可以在此查询 DB、调用 API 等，补充业务相关的资源属性。

    类似于 NameCodec 的编解码，Resolver 的补全是 Provider 和业务之间的切面。
    """

    def resolve(self, resource: ResourceInstance) -> ResourceInstance:
        """补全资源实例的业务属性。

        Args:
            resource: 调用方传入的原始 ResourceInstance（至少含 type + id）。

        Returns:
            同类型的 ResourceInstance，name / ancestor_chain / attributes 可能已填充。
            如果无法解析或不需要解析，原样返回 resource 即可。
        """
        ...
