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
import re
from typing import Dict

from django.conf import settings
from django.utils.translation import gettext as _

from alarm_backends.service.access.base import Filter

from .gse_event import GSEBaseAlarmEventRecord

logger = logging.getLogger("access.event")


class DiskFullFilter(Filter):
    def filter(
        self, event_record  # type: GSEBaseAlarmEventRecord
    ):
        is_filter = False
        raw_data = event_record.raw_data["_extra_"]
        if 0 <= raw_data["free"] <= 100:
            # 该告警目前未上报磁盘类型，只能通过file_system进行过滤，后续gse上报事件需要新增类型字段fstype
            if "fstype" in raw_data and raw_data["fstype"] in settings.FILE_SYSTEM_TYPE_IGNORE:
                is_filter = True
            else:
                # 兼容方案：通过file_system名称进行正则匹配过滤，后续上报事件包含fstype字段后，可删除该段代码
                file_system = raw_data["file_system"]
                for condition in settings.DISK_FILTER_CONDITION_LIST_V1:
                    file_system_regex = condition["file_system_regex"]
                    if re.match(file_system_regex, file_system):
                        is_filter = True
                        break
        if is_filter:
            logger.info("GSE DISK_FULL_ALARM filter alarm: %s", event_record.raw_data)

        return is_filter


class DiskFullEvent(GSEBaseAlarmEventRecord):
    """
    磁盘写满事件

    raw data foramt:
    {
        "isdst":0,
        "utctime2":"2019-10-17 05:53:53",
        "value":[
            {
                "event_raw_id":7795,
                "event_type":"gse_basic_alarm_type",
                "event_time":"2019-10-17 13:53:53",
                "extra":{
                    "used_percent":93,
                    "used":45330684,
                    "cloudid":0,
                    "free":7,
                    "fstype":"ext4",
                    "host":"127.0.0.1",
                    "disk":"/",
                    "file_system":"/dev/vda1",
                    "size":51473888,
                    "bizid":0,
                    "avail":3505456,
                    "type":6
                },
                "event_title":"",
                "event_desc":"",
                "event_source_system":""
            }
        ],
        "server":"127.0.0.129",
        "utctime":"2019-10-17 13:53:53",
        "time":"2019-10-17 13:53:53",
        "timezone":8
    }
    """

    TYPE = 6
    NAME = "disk-full-gse"
    METRIC_ID = "bk_monitor.disk-full-gse"
    TITLE = _("磁盘写满-GSE")

    def __init__(self, raw_data, strategies):
        super(DiskFullEvent, self).__init__(raw_data, strategies)
        self.filters.append(DiskFullFilter())

    def clean_anomaly_message(self):
        raw = self.raw_data["_title_"]
        if raw:
            return raw

        disk = self.raw_data["_extra_"].get("disk")
        free = self.raw_data["_extra_"].get("free")
        return _("磁盘({})剩余空间只有{}%").format(disk, free)

    @property
    def filter_dimensions(self) -> Dict:
        data = self.raw_data["_extra_"]

        return {
            "disk": data.get("disk", ""),
            "file_system": data.get("file_system", ""),
            "fstype": data.get("fstype", ""),
        }

    def clean_dimension_fields(self):
        dimension_fields = super().clean_dimension_fields()
        dimension_fields.extend(["file_system", "fstype", "disk"])
        return dimension_fields
