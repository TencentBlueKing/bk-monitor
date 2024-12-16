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


import copy
import logging
from typing import Dict

from django.conf import settings
from django.utils.translation import gettext as _

from alarm_backends.service.access.base import Filter

from .gse_event import GSEBaseAlarmEventRecord

logger = logging.getLogger("access.event")


class DiskReadonlyFilter(Filter):
    def filter(
        self, event_record  # type: GSEBaseAlarmEventRecord
    ):
        new_alarm = copy.deepcopy(event_record.raw_data)
        ro_list = new_alarm["_extra_"].get("ro", [])
        new_alarm["_extra_"]["ro"] = []
        for ro in ro_list:
            fstype = ro.get("type") or ""
            if fstype.lower() in settings.FILE_SYSTEM_TYPE_IGNORE:
                continue
            else:
                new_alarm["_extra_"]["ro"].append(ro)
        if len(new_alarm["_extra_"]["ro"]):
            event_record.raw_data["_extra_"]["ro"] = new_alarm["_extra_"]["ro"]
            return False

        logger.info("GSE DISK_READONLY_ALARM filter alarm: %s", event_record.raw_data)
        return True


class DiskReadonlyEvent(GSEBaseAlarmEventRecord):
    r"""
    磁盘只读事件

    raw data format:
    {
        "isdst":0,
        "utctime2":"2019-10-16 00:28:53",
        "value":[
            {
                "event_raw_id":5853,
                "event_type":"gse_basic_alarm_type",
                "event_time":"2019-10-16 08:28:53",
                "extra":{
                    "cloudid":0,
                    "host":"127.0.0.1",
                    "ro":[
                        {
                            "position":"\/sys\/fs\/cgroup",
                            "fs":"tmpfs",
                            "type":"tmpfs"
                        },
                        {
                            "position":"\/readonly_disk",
                            "fs":"dev\/vdb",
                            "type":"ext4"
                        }
                    ],
                    "type":3,
                    "bizid":0
                },
                "event_title":"",
                "event_desc":"",
                "event_source_system":""
            }
        ],
        "server":"127.0.0.1",
        "utctime":"2019-10-16 08:28:53",
        "time":"2019-10-16 08:28:53",
        "timezone":8
    }

    """
    TYPE = 3
    NAME = "disk-readonly-gse"
    METRIC_ID = "bk_monitor.disk-readonly-gse"
    TITLE = _("磁盘只读-GSE")

    def __init__(self, raw_data, strategies):
        super(DiskReadonlyEvent, self).__init__(raw_data, strategies)
        self.filters.append(DiskReadonlyFilter())

    def clean_anomaly_message(self):
        raw = self.raw_data["_title_"]
        if raw:
            return raw

        desc = []
        ro_list = self.raw_data["_extra_"].get("ro", [])
        for ro in ro_list:
            # 兼容采集器的错误字段 positoin
            desc.append("{}-{}({})".format(ro.get("fs"), ro.get("type"), ro.get("position") or ro.get("positoin")))
        return _("磁盘({})只读告警").format(", ".join(desc))

    @property
    def filter_dimensions(self) -> Dict:
        ro_list = self.raw_data["_extra_"].get("ro", [])

        return {
            "position": "".join(ro.get("position", "") for ro in ro_list if ro.get("position")),
            "type": "".join(ro.get("type", "") for ro in ro_list if ro.get("type")),
            "fs": "".join(ro.get("fs", "") for ro in ro_list if ro.get("fs")),
        }
