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

import logging
from typing import Any

from metadata.models.data_link.tags.context import DatabusLabelContext
from metadata.models.data_link.tags.protocol import DatabusLabelGenerator

logger = logging.getLogger("metadata")


class DatabusLabelRegistry:
    """Databus 标签生成器注册表。

    支持按名称注册/覆盖/注销生成器，并按 priority 顺序合并标签。
    """

    def __init__(self) -> None:
        self._generators: dict[str, DatabusLabelGenerator] = {}

    def register(self, generator: DatabusLabelGenerator, *, replace: bool = True) -> None:
        """注册标签生成器。

        Args:
            generator: 生成器实例。
            replace: 同名已存在时是否覆盖；为 False 时抛出 ValueError。

        Raises:
            ValueError: generator.name 为空，或同名已存在且 replace=False。
        """
        if not generator.name:
            raise ValueError("DatabusLabelGenerator.name 不能为空")
        if generator.name in self._generators and not replace:
            raise ValueError(f"DatabusLabelGenerator[{generator.name}] 已注册")
        self._generators[generator.name] = generator
        logger.debug(
            "databus_label_registry: registered generator->[%s], priority->[%s]",
            generator.name,
            generator.priority,
        )

    def unregister(self, name: str) -> None:
        """按名称注销生成器。不存在时静默忽略。"""
        self._generators.pop(name, None)

    def clear(self) -> None:
        """清空全部生成器。主要用于测试隔离。"""
        self._generators.clear()

    def list_generators(self) -> list[DatabusLabelGenerator]:
        """按 priority 升序、同 priority 按 name 升序返回生成器列表。"""
        return sorted(self._generators.values(), key=lambda item: (item.priority, item.name))

    def build(self, context: DatabusLabelContext) -> dict[str, str]:
        """执行全部生成器并合并标签。

        合并规则：
        1. 按 priority 升序执行；同键后执行者覆盖先执行者。
        2. context.extra_labels 最后合并，优先级高于所有生成器。
        3. 值为 None 的键会被丢弃；其余值统一转为 str。
        """
        labels: dict[str, str] = {}
        for generator in self.list_generators():
            try:
                generated = generator.generate(context) or {}
            except Exception:  # noqa: BLE001 - 单生成器失败不应阻断链路创建
                logger.exception(
                    "databus_label_registry: generator->[%s] failed, skip",
                    generator.name,
                )
                continue
            labels.update(self._normalize_labels(generated))

        if context.extra_labels:
            labels.update(self._normalize_labels(context.extra_labels))
        return labels

    @staticmethod
    def _normalize_labels(raw_labels: dict[str, Any]) -> dict[str, str]:
        """将标签值规范化为字符串，并丢弃空值。"""
        normalized: dict[str, str] = {}
        for key, value in raw_labels.items():
            if value is None:
                continue
            label_key = str(key).strip()
            if not label_key:
                continue
            normalized[label_key] = str(value)
        return normalized
