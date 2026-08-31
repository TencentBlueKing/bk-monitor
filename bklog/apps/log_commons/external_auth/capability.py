"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from dataclasses import dataclass

from apps.constants import ExternalPermissionActionEnum
from apps.log_commons.external_auth.base import AuthSource
from apps.log_commons.external_auth.sources import LEGACY_TICKET_SOURCE


@dataclass(frozen=True)
class Capability:
    """一类外部能力，以及它认可的放行来源。

    来源按声明顺序参与 OR，顺序只影响拒绝文案和审计取值的优先级，不影响是否放行。
    """

    action_id: str
    sources: tuple[AuthSource, ...]


# 能力到放行来源的注册表。当前每个能力只认旧票，OR 退化成单来源，放行行为与接入管道前一致。
# 后续接入新侧时只需要在对应能力后面追加来源，不必改动 pipeline：
# 日志检索追加 IAM 来源，日志提取追加策略匹配来源，客户端日志随其自身排期接入。
# 注意「新侧」不等于 IAM，各能力的新侧机制不同，这正是按能力注册而不是全局开关的原因。
CAPABILITY_REGISTRY: dict[str, Capability] = {
    ExternalPermissionActionEnum.LOG_SEARCH.value: Capability(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
        sources=(LEGACY_TICKET_SOURCE,),
    ),
    ExternalPermissionActionEnum.LOG_EXTRACT.value: Capability(
        action_id=ExternalPermissionActionEnum.LOG_EXTRACT.value,
        sources=(LEGACY_TICKET_SOURCE,),
    ),
    ExternalPermissionActionEnum.CLIENT_LOG.value: Capability(
        action_id=ExternalPermissionActionEnum.CLIENT_LOG.value,
        sources=(LEGACY_TICKET_SOURCE,),
    ),
    ExternalPermissionActionEnum.LOG_CLUSTERING.value: Capability(
        action_id=ExternalPermissionActionEnum.LOG_CLUSTERING.value,
        sources=(LEGACY_TICKET_SOURCE,),
    ),
    ExternalPermissionActionEnum.LOG_COMMON.value: Capability(
        action_id=ExternalPermissionActionEnum.LOG_COMMON.value,
        sources=(LEGACY_TICKET_SOURCE,),
    ),
}

# 注册表未覆盖的 action_id 一律只认旧票，避免新增授权项时静默放宽鉴权
FALLBACK_CAPABILITY = Capability(action_id="", sources=(LEGACY_TICKET_SOURCE,))


def get_capability(declared_action_id: str, registry: dict[str, Capability] | None = None) -> Capability:
    registry = CAPABILITY_REGISTRY if registry is None else registry
    return registry.get(declared_action_id, FALLBACK_CAPABILITY)
