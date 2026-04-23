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

import arrow

from alarm_backends.core.cache import key
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.service.fta_action.denoise.processor import DenoiseProcessor
from alarm_backends.service.scheduler.app import app
from core.drf_resource import api
from core.prometheus import metrics

logger = logging.getLogger("denoise")


def create_alert_denoise_action(alert_id, bk_biz_id):
    """创建告警降噪处理任务.

    因为降噪检测是默认逻辑，目前担心通过上面actions来进行降噪会导致生成巨量没有意义的action_instance
    所以暂时直接通过异步任务来进行降噪检测

    :param alert_id: 告警ID
    :param bk_biz_id: 业务ID
    """
    now_timestamp = arrow.now().timestamp()
    alert_queue = key.ALERT_DENOISE_BIZ_QUEUE.get_key(bk_biz_id=bk_biz_id)
    alert_queue.client.lpush(alert_id)


@app.task(ignore_result=True, queue="celery_cron")
def trigger_biz_alert_denoise():
    """触发业务告警降噪处理."""
    client = key.ALERT_DENOISE_BIZ_QUEUE.client

    biz_list = api.cmdb.get_business(all=True)
    for biz_info in biz_list:
        bk_biz_id = biz_info["bk_biz_id"]
        alert_queue = key.ALERT_DENOISE_BIZ_QUEUE.get_key(bk_biz_id=bk_biz_id)
        alert_count = client.llen(alert_queue)
        if alert_count > 0:
            alert_denoise_process.delay(bk_biz_id)


@app.task(ignore_result=True, queue="celery_action")
def alert_denoise_process(bk_biz_id):
    """告警降噪处理逻辑.

    :param bk_biz_id: 业务ID
    """
    with service_lock(key.ALERT_DENOISE_BIZ_LOCK_KEY, bk_biz_id=bk_biz_id):
        alert_queue = key.ALERT_DENOISE_BIZ_QUEUE.get_key(bk_biz_id=bk_biz_id)
        client = key.ALERT_DENOISE_BIZ_QUEUE.client

        total_alerts = client.llen(alert_queue)
        if total_alerts == 0:
            logger.info(f"[denoise] biz({bk_biz_id}) 无待降噪告警")
            return

        alert_ids = client.lrange(alert_queue, -total_alerts, -1)

        logger.info(f"[denoise] biz({bk_biz_id}) 检测{total_alerts}个告警")
        if alert_ids:
            client.ltrim(alert_queue, 0, -total_alerts - 1)

        processor = DenoiseProcessor(alert_ids)
        processor.process()

    metrics.report_all()
