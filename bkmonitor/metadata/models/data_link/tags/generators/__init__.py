"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from metadata.models.data_link.tags.generators.datasource import DataSourceLabelGenerator
from metadata.models.data_link.tags.generators.resulttable import ResultTableLabelGenerator
from metadata.models.data_link.tags.registry import DatabusLabelRegistry


def register_default_generators(registry: DatabusLabelRegistry) -> None:
    """注册默认标签生成器。

    当前规则尚未最终确定，默认生成器先作为可扩展占位实现返回空标签。
    后续只需在对应 Generator.generate 中补充规则，或注册新的 Generator。
    """
    registry.register(DataSourceLabelGenerator())
    registry.register(ResultTableLabelGenerator())


__all__ = [
    "DataSourceLabelGenerator",
    "ResultTableLabelGenerator",
    "register_default_generators",
]
