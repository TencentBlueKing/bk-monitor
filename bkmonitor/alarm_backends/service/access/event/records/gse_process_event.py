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
from datetime import datetime

import arrow
from django.utils.translation import gettext as _

from constants.strategy import GSE_PROCESS_EVENT_NAME

from .gse_event import GSEBaseAlarmEventRecord

logger = logging.getLogger("access.event")


class GseProcessEventRecord(GSEBaseAlarmEventRecord):
    """
    raw data format:
    {
        "data": [{
            "dimension": {
                "bk_target_cloud_id": "0",
                "bk_target_ip": "127.0.0.1",
                "process_group_id": "nodeman",
                "process_index": "nodeman:bkmonitorbeat",
                "process_name": "bkmonitorbeat"
            },
            "event": {
                "content": "check bkmonitorbeat not running, and restart it success"
            },
            "event_name": "process_restart_success",
            "target": "127.0.0.1|0",
            "timestamp": 1618382611690
        }],
        "data_id": 1100008
    }

    output_standard_data:
    {
        "data": {
            "time": 1618382611,
            "value": {
                "content": "check bkmonitorbeat not running, and restart it success"
            },
            "values": {
                "time": 1618382611,
                "value": {
                    "content": "check bkmonitorbeat not running, and restart it success"
                }
            },
            "dimensions": {
                "bk_target_cloud_id": "0",
                "bk_target_ip": "127.0.0.1",
                "process_group_id": "nodeman",
                "process_index": "nodeman:bkmonitorbeat",
                "process_name": "bkmonitorbeat"
            },
            "record_id": "5300947a470bb4c094d624d998be2b5c.1618382611"
        },
        "anomaly": {
            "2": {
                "anomaly_id": "5300947a470bb4c094d624d998be2b5c.1618382611.209x.218.2",
                "anomaly_time": 1618386807,
                "anomaly_message": {
                    "content": "check bkmonitorbeat not running, and restart it success"
                }
            }
        },
        "strategy_snapshot_key": "bk_bkmonitorv3.ee.cache.strategy.snapshot.209.1617956776"
    }
    """

    TYPE = 101
    NAME = "gse_process_event"
    METRIC_ID = "bk_monitor.gse_process_event"
    TITLE = _("Gse进程托管事件上报")

    def __init__(self, raw_data, strategies):
        super(GseProcessEventRecord, self).__init__(raw_data=raw_data, strategies=strategies)

        self.strategies = strategies

    def check(self):
        for data in self.raw_data.get("data", []):
            # 是否存在符合规则的数据
            if data.get("event_name"):
                logger.debug("custom event value: %s" % self.raw_data)
                return True
        logger.warning("custom event value check fail: %s" % self.raw_data)
        return False

    def flat(self):
        try:
            event_records = []
            for data in self.raw_data.get("data", []):
                alarm_time = datetime.utcfromtimestamp(int(data.get("timestamp", 0)) // 1000).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if not alarm_time:
                    alarm_time = datetime.utcfromtimestamp(arrow.utcnow().timestamp).strftime("%Y-%m-%d %H:%M:%S")
                dimension = data.get("dimension", {})
                dimension["event_name"] = data.get("event_name")
                new_alarm = {
                    "_time_": alarm_time,
                    "_type_": "-1",
                    "_bizid_": dimension.get("_bizid_") or 0,
                    "_cloudid_": int(dimension.get("bk_target_cloud_id") or 0),
                    "_server_": dimension.get("bk_target_ip"),
                    "_host_": dimension.get("bk_target_ip"),
                    "_agent_id_": dimension.get("bk_agent_id", ""),
                    "_title_": _("事件类型: {}, 事件内容: {}").format(
                        GSE_PROCESS_EVENT_NAME.get(dimension.get('event_name')), data.get('event', {}).get('content')
                    ),
                    "_extra_": {"value": data},
                    "dimensions": dimension,
                }
                event_records.append(self.__class__(new_alarm, self.strategies))
            return event_records
        except Exception as e:
            logger.exception("GSE gse_process_event: (%s) (%s)", self.raw_data, e)
            return []

    @property
    def filter_dimensions(self):
        dimension = self.raw_data["_extra_"]["value"].get("dimension", {})
        return {
            "event_name": self.raw_data["_extra_"]["value"]["event_name"],
            "process_index": dimension.get("process_index", ""),
            "process_group_id": dimension.get("process_group_id", ""),
            "process_name": dimension.get("process_name", ""),
            "agent_version": dimension.get("agent_version", ""),
        }
