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

from celery.task import task

from core.prometheus import metrics

logger = logging.getLogger("fta_action.converge")


@task(ignore_result=True, queue="celery_converge")
def run_converge(converge_config, instance_id, instance_type, converge_context=None, alerts=None):
    """
    执行收敛动作
    :param converge_context:收敛上下文
    :param alerts: 告警快照
    :param instance_id: 收敛对象id
    :param instance_type: 收敛对象类型
    :param converge_config: 收敛配置
    """
    from alarm_backends.service.converge.processor import (
        ConvergeLockError,
        ConvergeProcessor,
    )

    logger.info("--begin converge action(%s_%s)--", instance_id, instance_type)

    exc = None

    bk_biz_id = 0
    start_time = time.time()
    try:
        converge_handler = ConvergeProcessor(converge_config, instance_id, instance_type, converge_context, alerts)
        bk_biz_id = getattr(converge_handler.instance, "bk_biz_id", 0)
        converge_handler.converge_alarm()
    except ConvergeLockError as error:
        logger.info(
            "end to converge %s, %s, due to can not get converge lock  %s", instance_type, instance_id, str(error)
        )
    except Exception as error:
        exc = error
        logger.exception("execute converge %s, %s error: %s", instance_type, instance_id, error)
    else:
        logger.info("--end converge action(%s_%s)--  result %s", instance_id, instance_type, converge_handler.status)

    cost = time.time() - start_time
    metrics.CONVERGE_PROCESS_TIME.labels(
        bk_biz_id=bk_biz_id, strategy_id=metrics.TOTAL_TAG, instance_type=instance_type
    ).observe(cost)
    metrics.CONVERGE_PROCESS_COUNT.labels(
        bk_biz_id=bk_biz_id,
        strategy_id=metrics.TOTAL_TAG,
        instance_type=instance_type,
        status=metrics.StatusEnum.from_exc(exc),
        exception=exc,
    ).inc()
    metrics.report_all()
