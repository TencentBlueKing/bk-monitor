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

from django.utils.translation import gettext as _

from alarm_backends.core.cache.cmdb import HostManager
from alarm_backends.service.access.base import Filter

from .gse_event import GSEBaseAlarmEventRecord

logger = logging.getLogger("access.event")


class PingFilter(Filter):
    def filter(
        self, event_record  # type: GSEBaseAlarmEventRecord
    ):
        ping_server = event_record.raw_data.get("_server_")
        agent_ip = event_record.raw_data.get("_host_")
        bk_cloud_id = event_record.raw_data.get("_cloudid_")
        host_app = HostManager.get(ping_server, bk_cloud_id, using_mem=True)
        agent_app = HostManager.get(agent_ip, bk_cloud_id, using_mem=True)
        if host_app and agent_app:
            # 直连区域直接告警
            # 非直连区域需要判断pa和agent所属业务是否相同
            if int(bk_cloud_id) <= 1 or host_app.bk_biz_id == agent_app.bk_biz_id:
                return False
        else:
            # TODO: should be save these error info
            pass

        logger.info("GSE PING_ALARM filter alarm: %s", event_record.raw_data)
        return True


class PingEvent(GSEBaseAlarmEventRecord):
    """
    Ping事件
    {
        "server":"127.0.0.1",
        "time":"2019-10-15 17:34:44",
        "value":[
            {
                "event_desc":"",
                "event_raw_id":27422,
                "event_source_system":"",
                "event_time":"2019-10-15 09:34:44",
                "event_timezone":0,
                "event_title":"",
                "event_type":"gse_basic_alarm_type",
                "extra":{
                    "bizid":0,
                    "cloudid":0,
                    "count":30,
                    "host":"127.0.0.1",
                    "iplist":[
                        "127.0.0.2",
                        "127.0.0.3",
                    ],
                    "type":8
                }
            }
        ]
    }
    """

    TYPE = 8
    NAME = "ping-gse"
    METRIC_ID = "bk_monitor.ping-gse"
    TITLE = _("PING不可达告警-GSE")

    def __init__(self, raw_data, strategies):
        super(PingEvent, self).__init__(raw_data, strategies)
        self.filters.append(PingFilter())

    def flat(self):
        try:
            utctime = self.raw_data.get("utctime2")

            origin_alarms = self.raw_data["value"]
            alarms = []
            for alarm in origin_alarms:
                iplist = alarm["extra"].pop("iplist", [])
                ping_server = alarm["extra"]["host"]
                cloudid = alarm["extra"]["cloudid"]
                bizid = alarm["extra"]["bizid"]

                if not utctime:
                    alarm_time = alarm.get("event_time")
                else:
                    alarm_time = utctime

                for host in iplist:
                    new_alarm = {
                        "_time_": alarm_time,
                        "_type_": alarm["extra"]["type"],
                        "_bizid_": bizid,
                        "_cloudid_": cloudid,
                        "_server_": ping_server,
                        "_host_": host,
                        "_title_": alarm["event_title"],
                    }
                    alarms.append(self.__class__(new_alarm, self.strategies))
            return alarms
        except KeyError as err:
            logger.exception("GSE ping-gse: (%s) (%s)", self.raw_data, err)
            return []

    def clean_anomaly_message(self):
        raw = self.raw_data["_title_"]
        if raw:
            return raw

        return _("Ping不可达")
