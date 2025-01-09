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
from collections import namedtuple
from typing import List

from django.utils.module_loading import import_string

Category = namedtuple("Category", ["id", "name", "children"])

Metric = namedtuple("Metric", ["id", "name", "unit", "unsupported_resource"])


def get_metrics(scenario) -> List:
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
