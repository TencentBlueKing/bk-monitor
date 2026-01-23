"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from alarm_backends.core.cache import key
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.service.access import ACCESS_TYPE_TO_CLASS
from alarm_backends.service.access.data import AccessBatchDataProcess, AccessDataProcess
from alarm_backends.service.access.data.token import TokenBucket
from alarm_backends.service.access.event.processor import AccessCustomEventGlobalProcess
from alarm_backends.service.access.event.processorv2 import AccessCustomEventGlobalProcessV2
from alarm_backends.service.access.incident import AccessIncidentProcess
from alarm_backends.service.scheduler.app import app
from core.prometheus import metrics


logger = logging.getLogger(__name__)


@app.task(ingnore_result=True, queue="celery_service_qos")
def run_access_data_with_qos_queue(strategy_group_key, interval=60):
    return run_access_data(strategy_group_key, interval)


@app.task(ignore_result=True, queue="celery_service")
def run_access_data(strategy_group_key, interval=60):
    """
    数据拉取任务：执行单个策略组的数据拉取和处理任务。

    功能说明：
    - 获取服务锁：确保同一策略组在同一时间只有一个任务在执行
    - 令牌桶限流：控制任务执行频率，避免过度消耗资源
    - 执行数据处理：调用 AccessDataProcess.process() 执行完整的数据处理流程
    - 快速任务优化：500ms 内的请求不计令牌消耗

    参数：
        strategy_group_key: 策略组键
        interval: 聚合周期，默认 60 秒

    流程：
        1. 获取服务锁
        2. 令牌桶限流
        3. 执行数据处理
        4. 释放令牌

    关键特性：
        - 服务锁：确保同一策略组在同一时间只有一个任务在执行
        - 令牌桶限流：控制任务执行频率，避免过度消耗资源
        - 快速任务优化：500ms 内的请求不计令牌消耗
    """
    # 获取服务锁：确保同一策略组在同一时间只有一个任务在执行
    with service_lock(key.SERVICE_LOCK_ACCESS, strategy_group_key=strategy_group_key):
        # 令牌桶限流：控制任务执行频率，避免过度消耗资源
        task_tb = TokenBucket(strategy_group_key, interval)
        if task_tb.acquire():
            # 执行数据处理：调用 AccessDataProcess.process() 执行完整的数据处理流程
            processor = AccessDataProcess(strategy_group_key)
            processor.process()
            metrics.report_all()

            # 快速任务优化：500ms 内的请求不计令牌消耗
            if processor.pull_duration <= 0.5:
                task_tb.release(0)
                return

            # 释放令牌：根据拉取耗时释放令牌
            # 令牌数量 = max([int(processor.pull_duration), 1])
            task_tb.release(max([int(processor.pull_duration), 1]))


@app.task(queue="celery_service_batch", ignore_result=True)
def run_access_batch_data(strategy_group_key: str, sub_task_id: str):
    """
    批量数据处理任务：处理批量数据的子任务。

    功能说明：
    - 从 Redis 读取压缩的批量数据
    - 解压数据（base64 解码 → gzip 解压 → JSON 解析）
    - 执行完整的数据处理流程（pull → handle → push）
    - 记录处理结果到 Redis，供主任务汇总

    参数：
        strategy_group_key: 策略组键
        sub_task_id: 子任务ID，格式为 {batch_timestamp}.{batch_count}

    处理流程：
        1. 创建批量处理器 AccessBatchDataProcess
        2. 执行处理 processor.process()
           - pull(): 从 Redis 读取批量数据
           - handle(): 维度补充、过滤、格式化
           - push(): 推送到检测队列
        3. 记录处理结果到 Redis（供主任务汇总）

    任务队列：
        celery_service_batch - 批量数据处理任务队列
    """
    processor = AccessBatchDataProcess(strategy_group_key=strategy_group_key, sub_task_id=sub_task_id)
    return processor.process()


@app.task(ignore_result=True, queue="celery_service")
def run_access_event(access_type):
    access_type_cls = ACCESS_TYPE_TO_CLASS.get(access_type)
    access_type_cls().process()
    metrics.report_all()


@app.task(ignore_result=True, queue="celery_service_access_event")
def run_access_event_handler(data_id, **kwargs):
    """
    事件处理器
    1. 处理任务，对DataID加锁
    2. 如果加锁成功，拉取数据；加锁失败，return；
    3. 拉取数据成功后，如果数据大小刚好等于上限，说明可能还有数据，继续将此 DataID 发布给下个Worker
    4. 解锁DataID，处理数据。
    """
    if kwargs:
        logger.warning(f"run_access_event_handler() got an unexpected keyword argument {kwargs}")
    processor = AccessCustomEventGlobalProcess(data_id=data_id)
    processor.process()
    metrics.report_all()


@app.task(ignore_result=True, queue="celery_service_access_event")
def run_access_event_handler_v2(data_id, **kwargs):
    """
    事件处理器
    1. 处理任务，对DataID加锁
    2. 如果加锁成功，拉取数据；加锁失败，return；
    3. 拉取数据成功后，如果数据大小刚好等于上限，说明可能还有数据，继续将此 DataID 发布给下个Worker
    4. 解锁DataID，处理数据。
    """
    if kwargs:
        logger.warning(f"run_access_event_handler_v2() got an unexpected keyword argument {kwargs}")
    processor = AccessCustomEventGlobalProcessV2(data_id=data_id)
    processor.process()
    metrics.report_all()


def run_access_incident_handler(incident_broker_url: str, queue_name: str):
    """
    故障分析结果同步处理器.
    """
    processor = AccessIncidentProcess(broker_url=incident_broker_url, queue_name=queue_name)
    processor.process()
