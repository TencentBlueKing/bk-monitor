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
from alarm_backends.core.cache import key
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.service.access import ACCESS_TYPE_TO_CLASS
from alarm_backends.service.access.data import AccessBatchDataProcess, AccessDataProcess
from alarm_backends.service.access.data.token import TokenBucket
from alarm_backends.service.access.event.processor import AccessCustomEventGlobalProcess
from alarm_backends.service.access.incident import AccessIncidentProcess
from alarm_backends.service.scheduler.app import app
from core.prometheus import metrics


@app.task(ignore_result=True, queue="celery_service")
def run_access_data(strategy_group_key, interval=60):
    with service_lock(key.SERVICE_LOCK_ACCESS, strategy_group_key=strategy_group_key):
        task_tb = TokenBucket(strategy_group_key, interval)
        if task_tb.acquire():
            processor = AccessDataProcess(strategy_group_key)
            processor.process()
            metrics.report_all()
            # 500ms内的请求不计令牌消耗
            if processor.pull_duration <= 0.5:
                task_tb.release(0)
                return
            task_tb.release(max([int(processor.pull_duration), 1]))


@app.task(queue="celery_service_batch", ignore_result=True)
def run_access_batch_data(strategy_group_key: str, sub_task_id: str):
    processor = AccessBatchDataProcess(strategy_group_key=strategy_group_key, sub_task_id=sub_task_id)
    return processor.process()


@app.task(ignore_result=True, queue="celery_service")
def run_access_event(access_type):
    access_type_cls = ACCESS_TYPE_TO_CLASS.get(access_type)
    access_type_cls().process()
    metrics.report_all()


@app.task(ignore_result=True, queue="celery_service_access_event")
def run_access_event_handler(data_id):
    """
    事件处理器
    1. 处理任务，对DataID加锁
    2. 如果加锁成功，拉取数据；加锁失败，return；
    3. 拉取数据成功后，如果数据大小刚好等于上限，说明可能还有数据，继续将此 DataID 发布给下个Worker
    4. 解锁DataID，处理数据。
    """
    processor = AccessCustomEventGlobalProcess(data_id=data_id)
    processor.process()
    metrics.report_all()


def run_access_incident_handler(incident_broker_url: str, queue_name: str):
    """
    故障分析结果同步处理器.
    """
    processor = AccessIncidentProcess(broker_url=incident_broker_url, queue_name=queue_name)
    processor.process()
