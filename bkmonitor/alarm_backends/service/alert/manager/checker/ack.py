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
import time

from alarm_backends.core.alert import Alert
from alarm_backends.service.alert.manager.checker.base import BaseChecker

logger = logging.getLogger("alert.manager")


class AckChecker(BaseChecker):
    """
    确认时间检测
    """

    def is_enabled(self, alert: Alert):
        return True

    def check(self, alert: Alert):
        if alert.data.get("ack_duration"):
            # 如果已经设置过了，就不再设置
            return
        if alert.data.get("is_ack") or alert.data.get("is_shielded") or not alert.is_abnormal():
            now_ts = alert.end_time or int(time.time())
            ack_duration = now_ts - alert.create_time
            alert.set("ack_duration", ack_duration)
