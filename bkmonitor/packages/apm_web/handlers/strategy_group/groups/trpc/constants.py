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
from enum import Enum
from typing import Any, Dict, List

from django.utils.translation import ugettext_lazy as _

from apm_web.metric.constants import SeriesAliasType
from monitor_web.strategies.default_settings.common import (
    DEFAULT_NOTICE,
    NO_DATA_CONFIG,
    fatal_algorithms_config,
    fatal_detects_config,
    warning_algorithms_config,
    warning_detects_config,
)


class TRPCApplyType(Enum):
    CALLEE: str = SeriesAliasType.CALLEE.value
    CALLER: str = SeriesAliasType.CALLER.value
    PANIC: str = "panic"

    @classmethod
    def options(cls) -> List[str]:
        return [cls.CALLER.value, cls.CALLEE.value, cls.PANIC.value]


TRPC_LABEL: str = "BKAPM-tRPC"


def _name_tmpl(child_name: str):
    return _("[tRPC] {child_name} {tmpl}").format(child_name=child_name, tmpl="[{app_name}/{scope}]")


CALLER_AVG_DURATION_STRATEGY_CONFIG: Dict[str, Any] = {
    "detects": warning_detects_config(5, 5, 2) + fatal_detects_config(5, 5, 2),
    "items": [
        {
            "algorithms": warning_algorithms_config("gte", 1000) + fatal_algorithms_config("gte", 5000),
            "name": _("主调平均耗时（ms）"),
            "no_data_config": NO_DATA_CONFIG,
            "target": [[]],
        }
    ],
    "name": _name_tmpl(_("主调平均耗时告警")),
    "notice": DEFAULT_NOTICE,
}

CALLER_P99_DURATION_STRATEGY_CONFIG: Dict[str, Any] = {
    "detects": warning_detects_config(5, 5, 2) + fatal_detects_config(5, 5, 2),
    "items": [
        {
            "algorithms": warning_algorithms_config("gte", 3000) + fatal_algorithms_config("gte", 5000),
            "name": _("主调 P99 耗时（ms）"),
            "no_data_config": NO_DATA_CONFIG,
            "target": [[]],
        }
    ],
    "name": _name_tmpl(_("主调 P99 耗时告警")),
    "notice": DEFAULT_NOTICE,
}

CALLER_SUCCESS_RATE_STRATEGY_CONFIG: Dict[str, Any] = {
    "detects": warning_detects_config(5, 5, 2) + fatal_detects_config(5, 5, 2),
    "items": [
        {
            "algorithms": warning_algorithms_config("lt", 99.9) + fatal_algorithms_config("lt", 90),
            "name": _("主调成功率（%）"),
            "no_data_config": NO_DATA_CONFIG,
            "target": [[]],
        }
    ],
    "name": _name_tmpl("主调成功率告警"),
    "notice": DEFAULT_NOTICE,
}

CALLEE_AVG_DURATION_STRATEGY_CONFIG: Dict[str, Any] = {
    "detects": warning_detects_config(5, 5, 2) + fatal_detects_config(5, 5, 2),
    "items": [
        {
            "algorithms": warning_algorithms_config("gte", 1000) + fatal_algorithms_config("gte", 5000),
            "name": _("被调平均耗时（ms）"),
            "no_data_config": NO_DATA_CONFIG,
            "target": [[]],
        }
    ],
    "name": _name_tmpl("被调平均耗时告警"),
    "notice": DEFAULT_NOTICE,
}

CALLEE_P99_DURATION_STRATEGY_CONFIG: Dict[str, Any] = {
    "detects": warning_detects_config(5, 5, 2) + fatal_detects_config(5, 5, 2),
    "items": [
        {
            "algorithms": warning_algorithms_config("gte", 3000) + fatal_algorithms_config("gte", 5000),
            "name": _("被调 P99 耗时（ms）"),
            "no_data_config": NO_DATA_CONFIG,
            "target": [[]],
        }
    ],
    "name": _name_tmpl("被调 P99 耗时告警"),
    "notice": DEFAULT_NOTICE,
}

CALLEE_SUCCESS_RATE_STRATEGY_CONFIG: Dict[str, Any] = {
    "detects": warning_detects_config(5, 5, 2) + fatal_detects_config(5, 5, 2),
    "items": [
        {
            "algorithms": warning_algorithms_config("lt", 99.9) + fatal_algorithms_config("lt", 90),
            "name": _("被调成功率（%）"),
            "no_data_config": NO_DATA_CONFIG,
            "target": [[]],
        }
    ],
    "name": _name_tmpl("被调成功率告警"),
    "notice": DEFAULT_NOTICE,
}


PANIC_STRATEGY_CONFIG: Dict[str, Any] = {
    "detects": fatal_detects_config(5, 1, 1),
    "items": [
        {
            "algorithms": fatal_algorithms_config("gt", 0),
            "name": _("Panic（进程异常退出）次数"),
            "no_data_config": NO_DATA_CONFIG,
            "target": [[]],
        }
    ],
    "name": _name_tmpl("Panic（进程异常退出）告警"),
    "notice": DEFAULT_NOTICE,
}
