# -*- coding: utf-8 -*-
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
import logging

from django.core.management.base import BaseCommand

from alarm_backends.service.fta_action.tasks.alert_assign import (
    BackendAssignMatchManager,
)
from bkmonitor.documents import AlertDocument
from constants.action import ActionNoticeType, AssignMode

logger = logging.getLogger("fta_action.run")


"""
示例：
python manage.py alert_check ${alert_id}
验证告警处理流程中是否命中分派规则
"""


class Command(BaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument("alert_id", type=int, help="alert id")
        parser.add_argument("--profile", type=bool, default=False)

    def handle(self, alert_id, *args, **options):
        try:
            from pyinstrument import Profiler

            profile = options.pop("profile", False)
        except ImportError:
            profile = False

        if not profile:
            return self._handle(alert_id, *args, **options)

        profiler = Profiler()
        profiler.start()

        self._handle(alert_id, *args, **options)

        profiler.stop()
        profiler.print()

    def _handle(self, alert_id, *args, **options):
        alert = AlertDocument.get(id=alert_id)
        matched_rules = run_match(alert)
        if not matched_rules:
            print("No matched rules found.")
        for rule in matched_rules:
            print("matched: ", rule.assign_rule["assign_group_id"], rule.assign_rule["group_name"])


def run_match(alert):
    strategy = alert.strategy
    notice = copy.deepcopy(strategy.get("notice", {}))
    assign_mode = notice["options"].get("assign_mode")
    if AssignMode.BY_RULE not in assign_mode:
        print(
            "[ignore assign match] alert(%s) assign_mode(%s)",
            alert.id,
            assign_mode,
        )
        return []
    notice_type = ActionNoticeType.NORMAL
    manager = BackendAssignMatchManager(
        alert,
        {},
        assign_mode=assign_mode,
        notice_type=notice_type,
    )
    manager.run_match()
    return manager.matched_rules
