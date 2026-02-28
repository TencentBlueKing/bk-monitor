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

from django.utils.translation import gettext as _

from .gse_event import GSEBaseAlarmEventRecord

logger = logging.getLogger("access.event")


class OOMEvent(GSEBaseAlarmEventRecord):
    """
    OOM 告警

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
                    "host":"127.0.0.1",
                    "type":9,
                    "total":3,
                    "process":"oom/java/consul",
                    "message":"total-vm:44687536kB, anon-rss:32520504kB, file-rss:0kB, shmem-rss:0kB",
                    "oom_memcg" : "oom_cgroup_path",
                    "task_memcg" :  "oom_cgroup_task",
                    "task" :  "process_name",
                    "constraint" :  "CONSTRAINT_MEMCG"
                }
            }
        ]
    }
    """

    TYPE = 9
    NAME = "oom-gse"
    METRIC_ID = "bk_monitor.oom-gse"
    TITLE = _("OOM产生-GSE")

    def __init__(self, raw_data, strategies):
        super().__init__(raw_data, strategies)

    def clean_anomaly_message(self):
        raw = self.raw_data["_title_"]
        if raw:
            return raw

        process = self.raw_data["_extra_"].get("process")
        total = self.raw_data["_extra_"].get("total")
        message = self.raw_data["_extra_"].get("message")
        return _("发现OOM异常事件发生（进程:{}），共OOM次数{}次, 信息:{}").format(process, total, message)

    @property
    def filter_dimensions(self) -> dict[str, str]:
        dimensions = {
            "process": self.raw_data["_extra_"].get("process", ""),
            "message": self.raw_data["_extra_"].get("message", ""),
        }

        external_fields = ["oom_memcg", "task_memcg", "task", "constraint"]
        for field in external_fields:
            if field not in self.raw_data["_extra_"]:
                continue
            dimensions[field] = self.raw_data["_extra_"][field]

        return dimensions

    def clean_dimensions(self):
        """
        清理和补充维度信息
        """
        # 手动添加 filter_dimensions 中除了 process 之外的维度到 dimensions
        filter_dims = self.filter_dimensions
        for k, v in filter_dims.items():
            if k != "process" and v:  # 排除 process，其他维度都添加到 dimensions
                self.raw_data["dimensions"][k] = v

        # 将 process 作为补充维度添加，用于告警展示和检索，但不参与 dedupe_keys 去重计算
        # 这样可以保证：同一主机产生不同进程 OOM 时，仍然关联到同一个告警
        process = self.raw_data["_extra_"].get("process")
        if process:
            self.raw_data["dimensions"]["__additional_dimensions"] = {"process": process}

        return self.raw_data["dimensions"]
