# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import copy
from typing import Any, Dict, List

from constants.data_source import ApplicationsResultTableLabel
from monitor_web.strategies.default_settings.common import (
    DEFAULT_NOTICE,
    NO_DATA_CONFIG,
    algorithms_config,
    detects_config,
)

from . import define
from .typing import StrategyT


class StrategyBuilder:
    @classmethod
    def _prepare_detects(cls, detects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        prepared_detects: List[Dict[str, Any]] = []
        # 确保每个 level 只存在一个 detect config
        level_detect_config_map: Dict[str, Dict[str, Any]] = {detect["level"]: detect for detect in detects}
        for level, detect_config in level_detect_config_map.items():
            prepared_detects.extend(
                detects_config(
                    recovery_check_window=detect_config["recovery_check_window"],
                    trigger_check_window=detect_config["trigger_check_window"],
                    trigger_count=detect_config["trigger_count"],
                    level=detect_config["level"],
                )
            )
        return prepared_detects

    @classmethod
    def _year_round_algorithm_config(cls, level: str, ceil: float, floor: float) -> List[Dict[str, Any]]:
        return [
            {
                "config": {"floor": floor, "ceil": ceil, "ceil_interval": 7, "floor_interval": 7, "fetch_type": "avg"},
                "level": level,
                "type": "AdvancedYearRound",
                "unit_prefix": "",
            }
        ]

    @classmethod
    def _prepare_algorithms(cls, algorithms: List[Dict[str, Any]]):
        prepared_algorithms: List[Dict[str, Any]] = []
        for algorithm in algorithms:
            if algorithm["type"] == define.AlgorithmType.THRESHOLD.value:
                prepared_algorithms.extend(
                    algorithms_config(
                        method=algorithm["method"], threshold=algorithm["threshold"], level=algorithm["level"]
                    )
                )
            elif algorithm["type"] == define.AlgorithmType.ADVANCE_YEAR_ROUND.value:
                prepared_algorithms.extend(
                    cls._year_round_algorithm_config(
                        level=algorithm["level"], ceil=algorithm["ceil"], floor=algorithm["floor"]
                    )
                )
        return prepared_algorithms

    def __init__(
        self,
        bk_biz_id: int,
        name: str,
        query_name: str,
        query_config: Dict[str, Any],
        detects: List[Dict[str, Any]],
        algorithms: List[Dict[str, Any]],
        labels: List[str],
        notice_group_ids: List[int],
        message_templates: List[Dict[str, str]],
    ):
        self.bk_biz_id: int = bk_biz_id
        self.name: str = name
        self.query_name: str = query_name
        self.query_config: Dict[str, Any] = query_config
        self.detects: List[Dict[str, Any]] = self._prepare_detects(detects)
        self.algorithms: List[Dict[str, Any]] = self._prepare_algorithms(algorithms)
        self.labels: List[str] = labels[:]
        self.notice_group_ids: List[int] = notice_group_ids[:]
        self.message_templates: List[Dict[str, str]] = copy.deepcopy(message_templates)

    def build(self) -> StrategyT:
        notice: Dict[str, Any] = copy.deepcopy(DEFAULT_NOTICE)
        notice["user_groups"] = self.notice_group_ids
        notice["config"]["template"] = self.message_templates

        return {
            "bk_biz_id": self.bk_biz_id,
            "name": str(self.name),
            "labels": self.labels,
            "items": [
                {
                    "name": str(self.query_name),
                    "expression": self.query_config["expression"],
                    "query_configs": self.query_config["query_configs"],
                    "functions": self.query_config.get("functions") or [],
                    "algorithms": self.algorithms,
                    "no_data_config": NO_DATA_CONFIG,
                    "target": [[]],
                }
            ],
            "detects": self.detects,
            "notice": notice,
            "actions": [],
            "scenario": ApplicationsResultTableLabel.application_check,
        }
