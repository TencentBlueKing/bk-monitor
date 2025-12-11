"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from collections import defaultdict

import arrow

from alarm_backends.core.control.checkpoint import Checkpoint
from alarm_backends.service.incident.base import BaseIncidentProcess
from bkmonitor.documents import AlertDocument
from bkmonitor.utils.time_tools import split_time_range


class FetchAlertProcessor(BaseIncidentProcess):
    """
    获取告警处理器
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.from_timestamp = None
        self.until_timestamp = None
        self.alerts = defaultdict(list)

    def process(self):
        """
        处理逻辑
        """
        self.pull()
        self.push()

    def pull(self):
        """
        1. 拉取最近最近（3分钟前）1分钟的告警数据
        """
        now_timestamp = arrow.utcnow().timestamp

        # 设置查询时间范围
        self.until_timestamp = (now_timestamp - 60 * 3) // 60 * 60
        last_end_checkpoint = Checkpoint("incident.alert").get(self.until_timestamp - 60)
        self.from_timestamp = last_end_checkpoint // 60 * 60

        if self.from_timestamp > self.until_timestamp:
            return

        # 告警数据查询
        max_size = 10000
        time_step = 10
        for start_time, end_time in split_time_range(self.from_timestamp, self.until_timestamp, time_step):
            alerts = (
                AlertDocument.search()
                .filter("range", update_time={"gte": start_time, "lt": end_time})
                .params(size=max_size)
                .execute()
                .hits
            )
            for alert in alerts:
                self.alerts[alert.event.bk_biz_id].append(
                    {
                        "timestamp": alert.latest_time,
                        "alert": json.dumps(
                            {
                                "id": alert.id,
                                "alert_name": alert.alert_name,
                                "assignee": alert.assignee,
                                "bk_biz_id": alert.event.bk_biz_id,
                                "data_type": alert.event.data_type,
                                "descritpion": alert.event.description,
                                "dimensions": alert.dimensions,
                                "duration": alert.duration,
                                "event": alert.event.to_dict(),
                                "first_anomaly_time": alert.first_anomaly_time,
                                "severity": alert.severity,
                                "status": alert.status,
                                "strategy": alert.strategy,
                                "strategy_id": alert.strategy_id,
                            }
                        ),
                    }
                )

    def push(self):
        """
        1. 把业务告警推送到告警降噪任务进行处理
        """
        for bk_biz_id, alerts in self.alerts.items():
            pass
