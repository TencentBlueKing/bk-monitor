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
import functools
from enum import Enum
from typing import Any, Dict, List

from django.utils.translation import gettext_lazy as _

from apm_web.handlers.strategy_group.define import AlgorithmType
from apm_web.metric.constants import SeriesAliasType
from constants.alert import EventSeverity


class RPCApplyType(Enum):
    CALLEE: str = SeriesAliasType.CALLEE.value
    CALLER: str = SeriesAliasType.CALLER.value
    PANIC: str = "panic"
    RESOURCE: str = "resource"

    @classmethod
    def options(cls) -> List[str]:
        return [cls.CALLER.value, cls.CALLEE.value, cls.PANIC.value, cls.RESOURCE.value]


def _name_tmpl(child_name: str):
    return _("[RPC] {child_name} {tmpl}").format(child_name=child_name, tmpl="[{app_name}/{scope}]")


def _detect_config(
    recovery_check_window: int,
    trigger_check_window: int,
    trigger_count: int,
    level: str,
) -> Dict[str, Any]:
    return {
        "level": level,
        "recovery_check_window": recovery_check_window,
        "trigger_check_window": trigger_check_window,
        "trigger_count": trigger_count,
    }


_warning_detect_config = functools.partial(_detect_config, level=EventSeverity.WARNING)
_fatal_detect_config = functools.partial(_detect_config, level=EventSeverity.FATAL)


def _threshold_algorithm_config(method: str, threshold: float, level: str) -> Dict[str, Any]:
    return {"level": level, "method": method, "threshold": threshold, "type": AlgorithmType.THRESHOLD.value}


_warning_threshold_algorithm_config = functools.partial(_threshold_algorithm_config, level=EventSeverity.WARNING)
_fatal_threshold_algorithm_config = functools.partial(_threshold_algorithm_config, level=EventSeverity.FATAL)


def _year_round_algorithm_config(ceil: float, floor: float, level: str) -> Dict[str, Any]:
    return {"level": level, "ceil": ceil, "floor": floor, "type": AlgorithmType.ADVANCE_YEAR_ROUND.value}


_warning_year_round_algorithm_config = functools.partial(_year_round_algorithm_config, level=EventSeverity.WARNING)
_fatal_year_round_algorithm_config = functools.partial(_year_round_algorithm_config, level=EventSeverity.FATAL)


CALLER_AVG_DURATION_STRATEGY_CONFIG: Dict[str, Any] = {
    "name": _name_tmpl(_("主调平均耗时告警")),
    "query_name": _("主调平均耗时（ms）"),
    "detects": [_warning_detect_config(5, 5, 2), _fatal_detect_config(5, 5, 2)],
    "algorithms": [_warning_threshold_algorithm_config("gte", 1000), _fatal_threshold_algorithm_config("gte", 5000)],
}

CALLER_P99_DURATION_STRATEGY_CONFIG: Dict[str, Any] = {
    "name": _name_tmpl(_("主调 P99 耗时告警")),
    "query_name": _("主调 P99 耗时（ms）"),
    "detects": [_warning_detect_config(5, 5, 2), _fatal_detect_config(5, 5, 2)],
    "algorithms": [_warning_threshold_algorithm_config("gte", 3000), _fatal_threshold_algorithm_config("gte", 5000)],
}

CALLER_SUCCESS_RATE_STRATEGY_CONFIG: Dict[str, Any] = {
    "name": _name_tmpl("主调成功率告警"),
    "query_name": _("主调成功率（%）"),
    "detects": [_warning_detect_config(5, 5, 2), _fatal_detect_config(5, 5, 2)],
    "algorithms": [_warning_threshold_algorithm_config("lt", 99.9), _fatal_threshold_algorithm_config("lt", 90)],
}


CALLEE_REQUEST_TOTAL_STRATEGY_CONFIG: Dict[str, Any] = {
    "name": _name_tmpl(_("被调流量异常告警")),
    "query_name": _("被调流量"),
    "detects": [_warning_detect_config(5, 10, 6), _fatal_detect_config(5, 10, 6)],
    "algorithms": [_warning_year_round_algorithm_config(50, 50), _fatal_year_round_algorithm_config(100, 100)],
}

CALLEE_AVG_DURATION_STRATEGY_CONFIG: Dict[str, Any] = {
    "name": _name_tmpl("被调平均耗时告警"),
    "query_name": _("被调平均耗时（ms）"),
    "detects": [_warning_detect_config(5, 5, 2), _fatal_detect_config(5, 5, 2)],
    "algorithms": [_warning_threshold_algorithm_config("gte", 1000), _fatal_threshold_algorithm_config("gte", 5000)],
}

CALLEE_P99_DURATION_STRATEGY_CONFIG: Dict[str, Any] = {
    "name": _name_tmpl("被调 P99 耗时告警"),
    "query_name": _("被调 P99 耗时（ms）"),
    "detects": [_warning_detect_config(5, 5, 2), _fatal_detect_config(5, 5, 2)],
    "algorithms": [_warning_threshold_algorithm_config("gte", 3000), _fatal_threshold_algorithm_config("gte", 5000)],
}

CALLEE_SUCCESS_RATE_STRATEGY_CONFIG: Dict[str, Any] = {
    "name": _name_tmpl("被调成功率告警"),
    "query_name": _("被调成功率（%）"),
    "detects": [_warning_detect_config(5, 5, 2), _fatal_detect_config(5, 5, 2)],
    "algorithms": [_warning_threshold_algorithm_config("lt", 99.9), _fatal_threshold_algorithm_config("lt", 90)],
}

PANIC_STRATEGY_CONFIG: Dict[str, Any] = {
    "name": _name_tmpl("Panic（进程异常退出）告警"),
    "query_name": _("Panic（进程异常退出）次数"),
    "detects": [_fatal_detect_config(5, 1, 1)],
    "algorithms": [_fatal_threshold_algorithm_config("gt", 0)],
}

MEMORY_USAGE_STRATEGY_CONFIG: Dict[str, Any] = {
    "name": _name_tmpl("内存使用率过高"),
    "query_name": _("内存使用率（%）"),
    "detects": [_fatal_detect_config(10, 15, 15)],
    "algorithms": [_warning_threshold_algorithm_config("gt", 80), _fatal_threshold_algorithm_config("gt", 90)],
}

CPU_USAGE_STRATEGY_CONFIG: Dict[str, Any] = {
    "name": _name_tmpl("CPU 使用率过高"),
    "query_name": _("CPU 使用率（%）"),
    "detects": [_fatal_detect_config(10, 15, 15)],
    "algorithms": [_warning_threshold_algorithm_config("gt", 80), _fatal_threshold_algorithm_config("gt", 90)],
}

OOM_KILLED_STRATEGY_CONFIG: Dict[str, Any] = {
    "name": _name_tmpl("OOMKilled 退出"),
    "query_name": _("OOMKilled 退出次数"),
    "detects": [_fatal_detect_config(5, 1, 1)],
    "algorithms": [_fatal_threshold_algorithm_config("gt", 0)],
}

ABNORMAL_RESTART_STRATEGY_CONFIG: Dict[str, Any] = {
    "name": _name_tmpl("异常重启"),
    "query_name": _("异常重启次数"),
    "detects": [_fatal_detect_config(5, 1, 1)],
    "algorithms": [_fatal_threshold_algorithm_config("gt", 0)],
}
