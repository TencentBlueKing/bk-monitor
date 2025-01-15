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

from alarm_backends.core.alert import Alert
from alarm_backends.service.alert.manager.checker.base import BaseChecker

logger = logging.getLogger("alert.manager")


class NextStatusChecker(BaseChecker):
    def is_enabled(self, alert: Alert):
        if alert.strategy_id:
            # 有策略ID的，走监控自身状态管理
            return False
        return super(NextStatusChecker, self).is_enabled(alert)

    def check(self, alert: Alert):
        logger.info(
            "[move next status] alert(%s) strategy(%s), next_status_time: %s, next_status: %s",
            alert.id,
            alert.strategy_id,
            alert.data.get("next_status_time"),
            alert.data.get("next_status"),
        )
        alert.move_to_next_status()
