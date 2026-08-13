"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from rum_web.constants import RumQueryMode
from rum_web.handlers.level.base import BaseRumLevelHandler
from rum_web.handlers.level.span import SpanLevelHandler


class UnsupportedRumQueryMode(ValueError):
    """不支持的 RUM 查询模式"""

    def __init__(self, mode: str):
        super().__init__(f"不支持的 RUM 查询模式: {mode}")


class RumLevelHandlerFactory:
    """RUM 层级处理器工厂

    根据 mode 校验并构造对应的 LevelHandler。
    首期只注册 span，View、Session 就绪后再注册。
    """

    HANDLERS: dict[str, type[BaseRumLevelHandler]] = {
        RumQueryMode.SPAN.value: SpanLevelHandler,
    }

    @classmethod
    def create(
        cls,
        mode: str,
        data_sources: list[TraceDatasourceTarget],
    ) -> BaseRumLevelHandler:
        """根据 mode 创建对应的 LevelHandler 实例

        :param mode: 查询层级模式，取值见 RumQueryMode
        :param data_sources: 数据源目标列表
        :raises UnsupportedRumQueryMode: mode 未注册时抛出
        :return: 对应的 LevelHandler 实例
        """
        if mode not in cls.HANDLERS:
            raise UnsupportedRumQueryMode(mode)
        return cls.HANDLERS[mode](data_sources)
