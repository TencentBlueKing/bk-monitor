"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.models import AlgorithmModel


def is_auto_level_intelligent_detect(strategy_item: dict) -> bool:
    algorithms = strategy_item.get("algorithms") or []
    if len(algorithms) != 1:
        return False

    algorithm = algorithms[0]
    config = algorithm.get("config")
    return (
        algorithm.get("type") == AlgorithmModel.AlgorithmChoices.IntelligentDetect
        and isinstance(config, dict)
        and config.get("alert_level_mode") == "auto"
    )
