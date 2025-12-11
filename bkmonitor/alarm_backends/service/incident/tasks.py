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

from alarm_backends.core.cache import key
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.service.incident.inputs.processor import FetchAlertProcessor
from alarm_backends.service.scheduler.app import app
from core.prometheus import metrics

logger = logging.getLogger("incident")


@app.task(queue="celery_incident_service")
def fetch_alerts_and_push_by_biz():
    """拉取告警并按业务分组.

    :param strategy_id: 策略ID
    :return:
    """
    with service_lock(key.SERVICE_LOCK_INCIDENT_ALERT):
        processor = FetchAlertProcessor()
        processor.process()
        metrics.report_all()


@app.task(queue="celery_incident_service")
def denoise_alerts_by_biz(bk_biz_id: int, alerts: list):
    """对告警进行降噪.

    :param bk_biz_id: 业务ID
    :param alerts: 告警列表
    :return:
    """
    pass
