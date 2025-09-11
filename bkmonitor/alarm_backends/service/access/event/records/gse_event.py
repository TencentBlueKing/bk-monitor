"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from alarm_backends.service.access.event.records.custom_event import (
    GseCustomStrEventRecord,
)

logger = logging.getLogger("access.event")


class GSEBaseAlarmEventRecord(GseCustomStrEventRecord):
    TYPE = -1
    NAME = ""
    METRIC_ID = ""
    TITLE = ""

    def __init__(self, raw_data, strategies):
        super().__init__(raw_data=raw_data, strategies=strategies)
        self.strategies = strategies

    @property
    def agent_ip(self):
        agent_ip = ""
        agent_info = self.raw_data.get("agent") or {}
        if agent_info.get("type") == "bkmonitorbeat":
            agent_ip = self.raw_data.get("ip", "")
        return agent_ip

    def check(self):
        if len(self.raw_data["value"]) == 1:
            logger.debug(f"GSE alarm value: {self.raw_data}")
            return True
        else:
            logger.warning(f"GSE alarm value check fail: {self.raw_data}")
            return False

    def flat(self):
        try:
            server = self.raw_data["server"]
            utctime = self.raw_data.get("utctime2")

            origin_alarms = self.raw_data["value"]
            alarms = []
            for alarm in origin_alarms:
                if not utctime:
                    alarm_time = alarm.get("event_time")
                else:
                    alarm_time = utctime

                new_alarm = {
                    "_time_": alarm_time,
                    "_type_": alarm["extra"]["type"],
                    "_bizid_": alarm["extra"]["bizid"],
                    "_cloudid_": alarm["extra"]["cloudid"],
                    "_server_": server,
                    "_host_": self.agent_ip if self.agent_ip else alarm["extra"]["host"],
                    "_title_": alarm["event_title"],
                    "_extra_": alarm["extra"],
                }

                alarms.append(self.__class__(new_alarm, self.strategies))
            return alarms
        except Exception as e:
            logger.exception("GSE %s: (%s) (%s)", self.NAME, self.raw_data, e)
            return []
