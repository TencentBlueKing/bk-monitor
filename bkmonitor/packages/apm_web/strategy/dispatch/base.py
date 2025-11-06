"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
from dataclasses import dataclass, fields
from typing import Any

from apm_web.models import StrategyTemplate
from apm_web.strategy.constants import DetectConnector
from bkmonitor.query_template.core import QueryTemplateWrapper
from utils import count_md5


@dataclass(slots=True)
class DispatchGlobalConfig:
    detect: dict[str, Any] | None = None
    user_group_list: list[dict[str, Any]] | None = None
    user_group_ids: list[int] | None = None

    def __post_init__(self):
        if self.user_group_list is not None:
            self.user_group_ids = [user_group["id"] for user_group in self.user_group_list]


@dataclass(slots=True)
class DispatchExtraConfig:
    service_name: str
    context: dict[str, Any] | None = None
    algorithms: list[dict[str, Any]] | None = None
    detect: dict[str, Any] | None = None
    user_group_list: list[dict[str, Any]] | None = None
    user_group_ids: list[int] | None = None

    def __post_init__(self):
        if self.user_group_list is not None:
            self.user_group_ids = [user_group["id"] for user_group in self.user_group_list]

    def merge(self, other: "DispatchExtraConfig") -> "DispatchExtraConfig":
        """合并配置，优先级 other > self"""
        for field in fields(self):
            if field.name == "context":
                other_context: dict[str, Any] = copy.deepcopy(other.context or {})
                if self.context is None:
                    self.context = other_context
                else:
                    self.context.update(other_context)
                continue

            if getattr(other, field.name) is not None:
                setattr(self, field.name, getattr(other, field.name))
        return self


@dataclass(slots=True)
class DispatchConfig:
    service_name: str
    context: dict[str, Any]
    detect: dict[str, Any]
    algorithms: list[dict[str, Any]]
    user_group_ids: list[int]

    message_template: str | None = None

    @classmethod
    def from_configs(
        cls,
        global_config: DispatchGlobalConfig,
        extra_config: DispatchExtraConfig,
        strategy_template: StrategyTemplate,
        default_context: dict[str, Any],
    ) -> "DispatchConfig":
        data: dict[str, Any] = {}
        for field in ["service_name", "context", "detect", "algorithms", "user_group_ids"]:
            # 优先级：策略模板 < 额外配置 < 全局配置。
            for obj in [strategy_template, extra_config, global_config]:
                if getattr(obj, field, None) is None:
                    continue

                if field != "context":
                    # 深拷贝，防止后续修改对象属性时影响到原对象。
                    data[field] = copy.deepcopy(getattr(obj, field))
                else:
                    if field not in data:
                        data[field] = {}

                    # context 需要合并。
                    for k, v in getattr(obj, field).items():
                        data.setdefault(field, {})[k] = copy.deepcopy(v)

        for k, v in default_context.items():
            # strategy_template 的 context 一定存在，所以这里不需要判断 data 是否存在 context 字段。
            # default_context 优先级最低，仅在 context 不存在对应 key 时填充。
            if k not in data["context"]:
                # default_context 是一个共享的全局变量，必须深拷贝。
                data["context"][k] = copy.deepcopy(v)

        return cls(**data)


def calculate_strategy_md5_by_dispatch_config(
    config: DispatchConfig, query_template_wrapper: QueryTemplateWrapper
) -> str:
    origin_detect = config.detect
    # 向前兼容，connector 为 AND 时，不计算 connector
    if config.detect.get("connector") == DetectConnector.AND.value:
        config.detect = copy.deepcopy(origin_detect)
        config.detect.pop("connector", None)
    md5: str = count_md5(
        {
            "detect": config.detect,
            "algorithms": config.algorithms,
            "user_group_ids": config.user_group_ids,
            "context": config.context,
            "query_template": {"name": query_template_wrapper.name, "bk_biz_id": query_template_wrapper.bk_biz_id},
        }
    )
    config.detect = origin_detect
    return md5
