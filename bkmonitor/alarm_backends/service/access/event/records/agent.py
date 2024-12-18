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


import logging
from typing import Dict

from django.utils.translation import gettext as _

from .gse_event import GSEBaseAlarmEventRecord

logger = logging.getLogger("access.event")


class AgentEvent(GSEBaseAlarmEventRecord):
    """
    Agent心跳丢失事件

    raw data format:
    Agent 1.0
    {
        "server": "", // 发此条告警数据的 ip
        "time": "%04d-%02d-%02d %02d:%02d:%02d", // 发告警的时间
        "timezone": 0,
        "utctime": "%04d-%02d-%02d %02d:%02d:%02d", // 发告警的时间
        "utctime2": "%04d-%02d-%02d %02d:%02d:%02d", // 发告警的时间utc时间
        "value": [
            {
                "event_desc": "",
                "event_raw_id": 0, // 自增id
                "event_time": "%04d-%02d-%02d %02d:%02d:%02d", // 发告警的时间
                "event_source_system": "", // 保持空字符串
                "event_title": "", // 保持空字符串
                "event_type": "gse_basic_alarm_type", // 固定值 gse_basic_alarm_type
                "extra": {
                    "type": 2, // 固定值 2
                    "count": 0, // host 数组元素个数
                    "host": [
                        {
                            "bizid": 0, // 业务id，现在应该都是0 了，参考 tgse::splitBizId 实现
                            "cloudid": 0, // 云区域ID
                            "ip": "127.0.0.1", // 心跳超时的主机 ip
                            "agent_id": "0:127.0.0.1" // 兼容的agent_id, {cloud_id}:{ip}
                        }
                    ]
                }
            }
        ]
    }
    Agent 2.0
    {
        "server": "", // 发此条告警数据的 ip
        "time": "%04d-%02d-%02d %02d:%02d:%02d", // 发告警的时间
        "timezone": 0,
        "utctime": "%04d-%02d-%02d %02d:%02d:%02d", // 发告警的时间
        "utctime2": "%04d-%02d-%02d %02d:%02d:%02d", // 发告警的时间utc时间
        "value": [
            {
                "event_desc": "",
                "event_raw_id": 0, // 自增id
                "event_time": "%04d-%02d-%02d %02d:%02d:%02d", // 发告警的时间
                "event_source_system": "", // 保持空字符串
                "event_title": "", // 保持空字符串
                "event_type": "gse_basic_alarm_type", // 固定值 gse_basic_alarm_type
                "extra": {
                    "type": 2, // 固定值 2
                    "count": 0, // host 数组元素个数
                    "host": [
                        {
                            "bizid": 0, // 业务id，现在应该都是0 了，参考 tgse::splitBizId 实现
                            "cloudid": 0, // 云区域ID, 无IP字段
                            "agent_id": "0100005254008ed86116666614661851" // 真实的agent_id, 最大64长度字符串
                        }
                    ]
                }
            }
        ]
    }
    """

    TYPE = 2
    NAME = "agent-gse"
    METRIC_ID = "bk_monitor.agent-gse"
    TITLE = _("AGENT心跳丢失-GSE")

    def __init__(self, raw_data, strategies):
        super(AgentEvent, self).__init__(raw_data, strategies)

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

                hosts = alarm["extra"].get("host", [])
                for host in hosts:
                    new_alarm = {
                        "_time_": alarm_time,
                        "_type_": alarm["extra"]["type"],
                        "_bizid_": host["bizid"],
                        "_cloudid_": host.get("cloudid", 0),
                        "_server_": server,
                        "_host_": host.get("ip", ""),
                        "_title_": alarm["event_title"],
                        "_agent_id_": host.get("agent_id", ""),
                    }
                    alarms.append(self.__class__(new_alarm, self.strategies))
            logger.info("GSE agent-gse received: (%s)", self.raw_data)
            return alarms
        except Exception as e:
            logger.exception("GSE agent-gse process error: (%s) (%s)", self.raw_data, e)
            return []

    def clean_anomaly_message(self):
        raw = self.raw_data["_title_"]
        if raw:
            return raw

        return _("GSE AGENT 失联")

    @property
    def filter_dimensions(self) -> Dict:
        return {"agent_version": self.dimensions.get("agent_version", "")}
