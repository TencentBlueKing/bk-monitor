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


import arrow

from bkmonitor.utils import time_tools


class AnomalyIDParser(object):
    """
    异常ID解析器
    格式： "{dimensions_md5}.{timestamp}.{strategy_id}.{item_id}.{level}"
    """

    def __init__(self, anomaly_id):
        record_infos = anomaly_id.split(".")
        self.dimensions_md5 = record_infos[0]
        self.source_time = int(record_infos[1])
        self.strategy_id = int(record_infos[2])
        self.item_id = int(record_infos[3])
        self.level = int(record_infos[4])

    @property
    def mysql_time(self):
        """
        source_time to mysql saved time
        """
        return time_tools.mysql_time(arrow.get(self.source_time).datetime)


class EventIDParser(AnomalyIDParser):
    """
    事件ID解析器
    """

    def __init__(self, event_id):
        # 格式与异常ID相同，直接复用
        super(EventIDParser, self).__init__(event_id)


class RecordParser(AnomalyIDParser):
    """
    数据记录解析器
    {
        "data":{
            "record_id":"{dimensions_md5}.{timestamp}",
            "value":1.38,
            "values":{
                "timestamp":1569246480,
                "load5":1.38
            },
            "dimensions":{
                "ip":"127.0.0.1"
            },
            "time":1569246480
        },
        "anomaly": {
            "1":{
                "anomaly_message": "",
                "anomaly_id": "{dimensions_md5}.{timestamp}.{strategy_id}.{item_id}.{level}",
                "anomaly_time": "2019-10-10 10:10:00"
            }
        },
        "strategy_snapshot_key": "xxx",
        "trigger": {
            "level": "1",
            "anomaly_ids": [
                "{dimensions_md5}.{timestamp}.{strategy_id}.{item_id}.{level}"
            ]
        }
    }
    """

    def __init__(self, record):
        self.record = record
        anomaly_id = list(self.record["anomaly"].values())[0]["anomaly_id"]
        super(RecordParser, self).__init__(anomaly_id)
