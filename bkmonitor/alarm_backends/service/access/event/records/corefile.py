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
from typing import Dict, List

from django.utils.translation import gettext as _

from .gse_event import GSEBaseAlarmEventRecord

logger = logging.getLogger("access.event")


class CorefileEvent(GSEBaseAlarmEventRecord):
    """
    corefile 告警

    raw data format:
    {
        "isdst":0,
        "server":"127.0.0.129",
        "time":"2018-03-01 11:45:42",
        "timezone":8,
        "utctime":"2018-03-01 11:45:42",
        "utctime2":"2018-03-01 03:45:42",
        "value":[
            {
                "event_desc":"",
                "event_raw_id":11,
                "event_source_system":"",
                "event_time":"2018-03-01 11:45:42",
                "event_title":"",
                "event_type":"gse_basic_alarm_type",
                "extra":{
                    "bizid":0,
                    "cloudid":0,
                    "executable": "test",
                    "executable_path": "/tmp/test",
                    "signal":"SIGFPE",
                    "corefile":"/data/corefile/core_101041_2018-03-10",
                    "filesize":"0",
                    "host":"127.0.0.1",
                    "type":7
                }
            }
        ]
    }
    """

    TYPE = 7
    NAME = "corefile-gse"
    METRIC_ID = "bk_monitor.corefile-gse"
    TITLE = _("Corefile产生-GSE")

    def __init__(self, raw_data, strategies):
        super(CorefileEvent, self).__init__(raw_data, strategies)

    def clean_anomaly_message(self):
        raw = self.raw_data["_title_"]
        if raw:
            return raw

        corefile = self.raw_data["_extra_"].get("corefile")
        executable = self.raw_data["_extra_"].get("executable")
        signal = self.raw_data["_extra_"].get("signal")
        if executable and signal:
            return _("{}进程因为{}异常信号产生corefile：{}".format(executable, signal, corefile))

        if executable:
            return _("{}进程产生corefile：{}".format(executable, corefile))

        if signal:
            return _("进程因为{}异常信号产生corefile：{}".format(signal, corefile))

        return _("产生corefile：{}".format(corefile))

    @property
    def filter_dimensions(self) -> Dict:
        return {
            "corefile": self.raw_data["_extra_"].get("corefile", ""),
            "executable_path": self.raw_data["_extra_"].get("executable_path", ""),
            "executable": self.raw_data["_extra_"].get("executable", ""),
            "signal": self.raw_data["_extra_"].get("signal", ""),
        }

    def clean_dimensions(self):
        for k in ["executable_path", "executable", "signal"]:
            if self.raw_data["_extra_"].get(k):
                self.raw_data["dimensions"][k] = self.raw_data["_extra_"][k]

        return self.raw_data["dimensions"]

    def clean_dimension_fields(self) -> List[str]:
        dimension_fields = super().clean_dimension_fields()
        dimension_fields.extend(["executable_path", "executable", "signal"])
        return dimension_fields
