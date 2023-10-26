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

from alarm_backends.core.cache.cmdb.host import HostManager
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
        super(GSEBaseAlarmEventRecord, self).__init__(raw_data=raw_data, strategies=strategies)
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
            logger.debug("GSE alarm value: %s" % self.raw_data)
            return True
        else:
            logger.warning("GSE alarm value check fail: %s" % self.raw_data)
            return False

    def get_plat_info(self, alarm):
        """获取单机告警中的plat_id, company_id, ip等字段"""
        bk_cloud_id = alarm.get("_cloudid_") or 0
        company_id = alarm.get("_bizid_") or 0  # 这里bizid存储的是companyid，而不是真实的bizid
        ip = alarm.get("_host_")
        agent_id = alarm.get("_agent_id_")

        # 如果ip不为空，则直接返回
        if ip:
            return bk_cloud_id, company_id, ip

        # 如果agent_id为空则直接返回
        if not agent_id:
            return bk_cloud_id, company_id, ip

        # 如果agent_id中包含冒号，则说明是兼容的agent_id格式，直接解析
        if ":" in agent_id:
            bk_cloud_id, ip = agent_id.split(":")
            return bk_cloud_id, company_id, ip

        # 从缓存中获取agent_id对应的主机信息
        host = HostManager.get_by_agent_id(agent_id)
        if host:
            bk_cloud_id = host.bk_cloud_id
            ip = host.bk_host_innerip

        return bk_cloud_id, company_id, ip

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
