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

from typing import Any

from metadata.models.data_link.tags.context import DatabusLabelContext
from metadata.models.data_link.tags.protocol import DatabusLabelGenerator


class ResultTableLabelGenerator(DatabusLabelGenerator):
    """基于 ResultTable 推导 Databus 标签。

    首版仅提供扩展挂点，具体规则待定；当前返回空字典，不影响现有链路。
    后续可在此根据 data_label / labels / label 等字段补充标签。
    """

    name = "resulttable"
    priority = 200

    def generate(self, context: DatabusLabelContext) -> dict[str, Any]:
        """根据 ResultTable 生成标签。

        Args:
            context: 标签生成上下文。

        Returns:
            标签字典。首版固定返回空字典。
        """
        if context.result_table is None:
            return {}
        # TODO: 在此补充基于 ResultTable 的标签生成规则
        return {}
