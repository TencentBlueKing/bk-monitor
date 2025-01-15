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

from alarm_backends.service.nodata.processor import CheckProcessor
from alarm_backends.service.scheduler.app import app
from core.errors.alarm_backends import LockError
from core.prometheus import metrics

logger = logging.getLogger("nodata")


@app.task(ignore_result=True, queue="celery_service")
def no_data_check(strategy_id, now_timestamp):
    """
    :summary: 检测当前策略是否需要无数据告警
    :param strategy_id:
    :param now_timestamp: 程序启动时间，pull_data 依赖该参数获取 data，避免 celery 拥塞，提前计算
    :return:
    """
    start_time = time.time()
    exc = None
    try:
        CheckProcessor(strategy_id).process(now_timestamp)
    except LockError:
        logger.info("Failed to acquire lock. on strategy({})".format(strategy_id))
    except Exception as e:
        logger.exception("Process strategy({strategy_id}) exception, " "{msg}".format(strategy_id=strategy_id, msg=e))
        exc = e
    duration = time.time() - start_time
    metrics.NODATA_PROCESS_TIME.labels(strategy_id=metrics.TOTAL_TAG).observe(duration)
    metrics.NODATA_PROCESS_COUNT.labels(
        strategy_id=metrics.TOTAL_TAG, status=metrics.StatusEnum.from_exc(exc), exception=exc
    ).inc()
    metrics.report_all()
