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
from django.db import migrations
from functools import reduce
from django.db.models import Q

from core.unit import load_unit
from core.unit.models import TimeUnit


def fix_algorithm_unit_prefix(apps, *args, **kwargs):
    AlgorithmModel = apps.get_model("bkmonitor", "AlgorithmModel")
    QueryConfigModel = apps.get_model("bkmonitor", "QueryConfigModel")
    unit_map = {}
    for query_config in QueryConfigModel.objects.filter(
            reduce(lambda x, y: x | y, (Q(config__unit=unit_id) for unit_id in ["ns", "µs", "ms", "s", "m", "h", "d"]))
    ):
        unit_map[query_config.strategy_id] = query_config.config["unit"]
    for algorithm in AlgorithmModel.objects.filter(
            strategy_id__in=unit_map.keys()).exclude(unit_prefix__in=TimeUnit.suffix_list):
        new_unit_suffix = load_unit(unit_map[algorithm.strategy_id]).suffix
        print(f"fix strategy({algorithm.strategy_id}) metric unit({unit_map[algorithm.strategy_id]}) "
              f"unit_prefix: {algorithm.unit_prefix} -> {new_unit_suffix}")
        algorithm.unit_prefix = new_unit_suffix
        algorithm.save()


class Migration(migrations.Migration):
    dependencies = [
        ("bkmonitor", "0105_auto_20220613_1214"),
    ]

    operations = [
        migrations.RunPython(fix_algorithm_unit_prefix),
    ]
