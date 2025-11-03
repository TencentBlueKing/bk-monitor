"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import importlib
import pkgutil
from collections import namedtuple
from pathlib import Path

from django.utils.module_loading import import_string

Category = namedtuple("Category", ["id", "name", "children"])

Metric = namedtuple("Metric", ["id", "name", "unit", "unsupported_resource", "show_chart"])


def get_metrics(scenario) -> list:
    """
    获取指标
    """
    metrics_generator = import_string(f"{get_metrics.__module__}.{scenario}.get_metrics")
    metrics = metrics_generator()
    metrics_list = []
    for category in metrics:
        category_dict = category._asdict()
        if category_dict["children"]:
            category_dict["children"] = [dict(metric._asdict()) for metric in category_dict["children"]]
        metrics_list.append(dict(category_dict))
    return metrics_list


def get_all_metrics() -> list[str]:
    """
    获取所有场景的指标
    """
    moudle_path = Path(importlib.import_module(get_all_metrics.__module__).__file__).parent
    scenario_list = [name for _, name, _ in pkgutil.iter_modules([str(moudle_path)])]

    metrics_list = []
    for scenario in scenario_list:
        for category_dict in get_metrics(scenario):
            for metric_dict in category_dict["children"]:
                metrics_list.append(metric_dict["id"])
    return metrics_list
