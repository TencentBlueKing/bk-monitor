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

from alarm_backends.core.cache import key
from alarm_backends.service.detect.process import DetectProcess
from alarm_backends.service.scheduler.app import app
from core.errors.alarm_backends import LockError
from core.prometheus import metrics

logger = logging.getLogger("detect")


@app.task(ignore_result=True, queue="celery_service")
def run_detect(strategy_id):
    client = key.DATA_SIGNAL_KEY.client
    data_signal_key = key.DATA_SIGNAL_KEY.get_key()
    exc = None
    try:
        processor = DetectProcess(strategy_id)
        processor.process()
    except LockError:
        logger.info("Failed to acquire lock. on strategy({})".format(strategy_id))
        client.delay("lpush", data_signal_key, strategy_id, delay=20)
    except Exception as e:
        exc = e
        logger.exception("Process strategy({strategy_id}) exception, " "{msg}".format(strategy_id=strategy_id, msg=e))
    else:
        # 当前策略待检测数据过多
        if processor.is_busy:
            run_detect.apply_async(args=(strategy_id,))
            logger.info(f"detect processor is busy with strategy({strategy_id})")

    metrics.DETECT_PROCESS_COUNT.labels(
        strategy_id=metrics.TOTAL_TAG, status=metrics.StatusEnum.from_exc(exc), exception=exc
    ).inc()

    metrics.report_all()


@app.task(ignore_result=True, queue="celery_service_aiops")
def run_detect_with_sdk(strategy_id):
    return run_detect(strategy_id)
