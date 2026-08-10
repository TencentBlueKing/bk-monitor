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

from abc import ABC, abstractmethod
from typing import Any

from metadata.models.data_link.tags.context import DatabusLabelContext


class DatabusLabelGenerator(ABC):
    """Databus 标签生成器协议。

    通过注册表挂载不同实现，可按 datasource / resulttable 等维度推导标签。
    生成规则后续可独立扩展，无需改动创建链路主流程。
    """

    # 生成器唯一名称，用于注册与覆盖
    name: str = ""
    # 数字越小越先执行；同键冲突时后执行者覆盖先执行者
    priority: int = 100

    @abstractmethod
    def generate(self, context: DatabusLabelContext) -> dict[str, Any]:
        """根据上下文生成标签。

        Args:
            context: 标签生成上下文。

        Returns:
            标签字典。值建议可被 JSON 序列化为字符串友好的标量；合并层会统一转成 str。
        """
        raise NotImplementedError
