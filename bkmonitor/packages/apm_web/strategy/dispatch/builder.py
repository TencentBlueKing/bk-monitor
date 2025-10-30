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
from typing import Any
from collections.abc import Callable

from django.conf import settings

from apm_web.models import StrategyTemplate, Application
from apm_web.strategy.constants import (
    StrategyTemplateSystem,
    AlgorithmType,
    ALGORITHM_METHOD_CONFIG_MAPPING,
    DetectConnector,
)
from bkmonitor.query_template.core import QueryTemplateWrapper
from constants.alert import DEFAULT_NOTICE_MESSAGE_TEMPLATE
from constants.apm import DEFAULT_DATA_LABEL, CommonMetricTag

from monitor_web.strategies.default_settings.common import (
    DEFAULT_NOTICE,
    NO_DATA_CONFIG,
    algorithms_config,
    detects_config,
)

from .base import DispatchConfig


class StrategyBuilder:
    def __init__(
        self,
        service_name: str,
        dispatch_config: DispatchConfig,
        strategy_template: StrategyTemplate,
        query_template_wrapper: QueryTemplateWrapper,
    ) -> None:
        self.service_name: str = service_name
        self.dispatch_config: DispatchConfig = dispatch_config
        self.strategy_template: StrategyTemplate = strategy_template
        self.query_template_wrapper: QueryTemplateWrapper = query_template_wrapper

    @classmethod
    def _prepare_detects(cls, detect: dict[str, Any], levels: list[int]) -> list[dict[str, Any]]:
        prepared_detects: list[dict[str, Any]] = []
        for level in set(levels):
            detect_config: dict[str, Any] = detect["config"]
            prepared_detects.extend(
                detects_config(
                    recovery_check_window=detect_config["recovery_check_window"],
                    trigger_check_window=detect_config["trigger_check_window"],
                    trigger_count=detect_config["trigger_count"],
                    level=level,
                    connector=detect.get("connector", DetectConnector.AND.value),
                )
            )

        return prepared_detects

    @classmethod
    def _year_round_algorithm_config(cls, algorithm: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "config": {
                    "floor": algorithm["floor"],
                    "ceil": algorithm["ceil"],
                    "ceil_interval": 7,
                    "floor_interval": 7,
                    "fetch_type": "avg",
                },
                "level": algorithm["level"],
                "type": algorithm["type"],
                "unit_prefix": "",
            }
        ]

    @classmethod
    def _threshold_algorithm_config(cls, algorithm: dict[str, Any]) -> list[dict[str, Any]]:
        return algorithms_config(
            level=algorithm["level"],
            method=algorithm["config"]["method"],
            threshold=algorithm["config"]["threshold"],
        )

    @classmethod
    def _year_round_and_ring_ratio_algorithm_config(cls, algorithm: dict[str, Any]) -> list[dict[str, Any]]:
        algorithm_config = algorithm["config"]
        method_config = ALGORITHM_METHOD_CONFIG_MAPPING[algorithm_config["method"]]
        return [
            {
                "config": {
                    "floor": algorithm_config["floor"],
                    "ceil": algorithm_config["ceil"],
                    "ceil_interval": method_config["ceil_interval"],
                    "floor_interval": method_config["floor_interval"],
                    "fetch_type": method_config["fetch_type"],
                },
                "level": algorithm["level"],
                "type": method_config["type"],
                "unit_prefix": "",
            }
        ]

    @classmethod
    def _prepare_algorithms(cls, algorithms: list[dict[str, Any]]) -> list[dict[str, Any]]:
        config_getter_map: dict[str, Callable[[dict[str, Any]], list[dict[str, Any]]]] = {
            AlgorithmType.THRESHOLD.value: cls._threshold_algorithm_config,
            AlgorithmType.ADVANCED_YEAR_ROUND.value: cls._year_round_algorithm_config,
            AlgorithmType.YEAR_ROUND_AND_RING_RATIO.value: cls._year_round_and_ring_ratio_algorithm_config,
        }
        prepared_algorithms: list[dict[str, Any]] = []
        for algorithm in algorithms:
            prepared_algorithms.extend(config_getter_map[algorithm["type"]](algorithm))
        return prepared_algorithms

    def _prepare_query_template(self) -> dict[str, Any]:
        strategy_item: dict[str, Any] = self.query_template_wrapper.render_to_strategy_item(
            self.dispatch_config.context
        )

        bk_biz_id: int = self.strategy_template.bk_biz_id
        app_name: str = self.strategy_template.app_name
        enable_global_metric: bool = f"{bk_biz_id}-{app_name}" in (settings.APM_RPC_GLOBAL_METRIC_ENABLE_APP_LIST or [])
        if enable_global_metric:
            return strategy_item

        # 没有开启全局指标，替换为应用的指标表。
        # TODO 后续 bk-collector 灰度完成后，删除此逻辑，页面重新下发策略即可。
        for query_config in strategy_item.get("query_configs", []):
            if query_config.get("data_label") != DEFAULT_DATA_LABEL:
                continue

            query_config.pop("data_label", None)
            query_config["result_table_id"] = Application.get_metric_table_id(bk_biz_id, app_name)

            # 去掉 APP_NAME 过滤条件
            processed_agg_condition: list[dict[str, Any]] = []
            for cond in query_config.get("agg_condition", []):
                if cond.get("key") != CommonMetricTag.APP_NAME.value:
                    processed_agg_condition.append(cond)
            query_config["agg_condition"] = processed_agg_condition

        return strategy_item

    def build(self) -> dict[str, Any]:
        notice: dict[str, Any] = copy.deepcopy(DEFAULT_NOTICE)
        notice["user_groups"] = self.dispatch_config.user_group_ids
        notice["config"]["template"] = copy.deepcopy(DEFAULT_NOTICE_MESSAGE_TEMPLATE)
        notice["config"]["template"][0]["message_tmpl"] = self.dispatch_config.message_template

        algorithms: list[dict[str, Any]] = self._prepare_algorithms(self.dispatch_config.algorithms)
        detects: list[dict[str, Any]] = self._prepare_detects(
            self.dispatch_config.detect, [algorithm["level"] for algorithm in algorithms]
        )

        app_name: str = self.strategy_template.app_name
        system_enum: StrategyTemplateSystem = StrategyTemplateSystem.from_value(self.strategy_template.system)
        return {
            "bk_biz_id": self.strategy_template.bk_biz_id,
            "service_name": self.service_name,
            "name": f"[{system_enum.label}] {self.strategy_template.name} [{app_name}/{self.service_name}]",
            "labels": [
                f"APM-APP({app_name})",
                f"APM-SERVICE({self.service_name})",
                f"APM-SYSTEM({self.strategy_template.system})",
                f"APM-CATEGORY({self.strategy_template.category})",
                f"APM-TEMPLATE({self.strategy_template.id})",
            ],
            "items": [
                {
                    "target": [[]],
                    "algorithms": algorithms,
                    "no_data_config": NO_DATA_CONFIG,
                    **self._prepare_query_template(),
                }
            ],
            "detects": detects,
            "notice": notice,
            "actions": [],
            "scenario": system_enum.scenario,
        }
