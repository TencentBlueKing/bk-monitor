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
import json

from alarm_backends.core.alert.alert import Alert
from alarm_backends.core.alert.event import Event
from alarm_backends.service.alert.manager.checker.close import CloseStatusChecker
from alarm_backends.service.alert.manager.checker.recover import RecoverStatusChecker
from constants.action import AssignMode


def make_alert_data(*, severity, severity_source="", dynamic_level=3):
    return {
        "severity": severity,
        "extra_info": {
            "severity_source": severity_source,
            "origin_alarm": {
                "data": {
                    "values": {
                        "extra_info": json.dumps({"alert_level_msg": {"alert_level": dynamic_level}}),
                    }
                }
            },
        },
    }


def make_auto_item(mode="auto"):
    return {
        "algorithms": [
            {
                "type": "IntelligentDetect",
                "level": 2,
                "config": {"alert_level_mode": mode},
            }
        ]
    }


def test_dynamic_level_is_loaded_for_unassigned_alert():
    alert = Alert(make_alert_data(severity=2, dynamic_level=3))

    assert alert.severity == 3


def test_dynamic_level_is_loaded_for_event():
    event = Event.__new__(Event)
    event.data = make_alert_data(severity=2, dynamic_level=1)

    event.init_severity()

    assert event.severity == 1


def test_by_rule_severity_survives_cache_reload():
    cached_data = make_alert_data(severity=1, severity_source=AssignMode.BY_RULE, dynamic_level=3)

    reloaded_alert = Alert(copy.deepcopy(cached_data))

    assert reloaded_alert.severity == 1
    assert reloaded_alert.severity_source == AssignMode.BY_RULE


def test_auto_intelligent_detect_uses_technical_level_lifecycle_without_becoming_multi_indicator():
    item = make_auto_item()

    assert RecoverStatusChecker.check_is_multi_indicator_strategy(item) is False
    assert RecoverStatusChecker.check_use_technical_level_config(item) is True
    assert CloseStatusChecker.__new__(CloseStatusChecker).check_skip_close_by_algorithm(item) is True


def test_manual_intelligent_detect_does_not_use_dynamic_lifecycle_special_case():
    item = make_auto_item(mode="manual")

    assert RecoverStatusChecker.check_use_technical_level_config(item) is False
    assert CloseStatusChecker.__new__(CloseStatusChecker).check_skip_close_by_algorithm(item) is False


def test_auto_intelligent_detect_selects_level_two_config():
    item = make_auto_item()
    configs = {"1": {"name": "fatal"}, "2": {"name": "technical"}, "3": {"name": "remind"}}

    selected = RecoverStatusChecker.select_level_config(configs, item, [1, 3])

    assert selected == {"name": "technical"}
