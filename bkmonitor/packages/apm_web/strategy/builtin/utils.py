"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import functools
from typing import Any

from constants.alert import EventSeverity

from bkmonitor.models.strategy import AlgorithmModel

from .. import constants


def detect_config(recovery_check_window: int, trigger_check_window: int, trigger_count: int) -> dict[str, Any]:
    return {
        "type": constants.DEFAULT_DETECT_TYPE,
        "config": {
            "recovery_check_window": recovery_check_window,
            "trigger_check_window": trigger_check_window,
            "trigger_count": trigger_count,
        },
    }


def _threshold_algorithm_config(method: str, threshold: float, level: str, suffix: str | None = "") -> dict[str, Any]:
    return {
        "level": level,
        "type": AlgorithmModel.AlgorithmChoices.Threshold,
        "config": {"method": method, "threshold": threshold},
        "unit_prefix": suffix or "",
    }


warning_threshold_algorithm_config = functools.partial(_threshold_algorithm_config, level=EventSeverity.WARNING)
fatal_threshold_algorithm_config = functools.partial(_threshold_algorithm_config, level=EventSeverity.FATAL)
