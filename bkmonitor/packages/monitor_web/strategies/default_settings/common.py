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

from functools import partial
from typing import List

from constants.alert import EventSeverity

DEFAULT_NOTICE = {
    "config": {"interval_notify_mode": "standard", "need_poll": True, "notify_interval": 7200},
    "options": {
        "converge_config": {"need_biz_converge": True},
        "end_time": "23:59:59",
        "start_time": "00:00:00",
    },
    "signal": ["no_data", "abnormal"],
}

NO_DATA_CONFIG = {"agg_dimension": [], "continuous": 10, "is_enabled": False, "level": EventSeverity.WARNING}


def detects_config(
    recovery_check_window: int, trigger_check_window: int, trigger_count: int, level: int, status_setter="recovery"
) -> List:
    return [
        {
            "connector": "and",
            "expression": "",
            "level": level,
            "recovery_config": {"check_window": recovery_check_window, "status_setter": status_setter},
            "trigger_config": {
                "check_window": trigger_check_window,
                "count": trigger_count,
                "uptime": {"calendars": [], "time_ranges": [{"end": "23:59", "start": "00:00"}]},
            },
        }
    ]


fatal_detects_config = partial(detects_config, level=EventSeverity.FATAL)
warning_detects_config = partial(detects_config, level=EventSeverity.WARNING)
remind_detects_config = partial(detects_config, level=EventSeverity.REMIND)
nodata_recover_detects_config = partial(detects_config, status_setter="recovery-nodata")


def algorithms_config(method: str, threshold: int, level: int) -> List:
    return [
        {
            "config": [[{"method": method, "threshold": threshold}]],
            "level": level,
            "type": "Threshold",
            "unit_prefix": "",
        }
    ]


fatal_algorithms_config = partial(algorithms_config, level=EventSeverity.FATAL)
warning_algorithms_config = partial(algorithms_config, level=EventSeverity.WARNING)
remind_algorithms_config = partial(algorithms_config, level=EventSeverity.REMIND)
