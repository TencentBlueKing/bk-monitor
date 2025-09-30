# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import logging
import math
import random
from dataclasses import dataclass

from django.conf import settings

from apm.core.discover.precalculation.daemon import DaemonTaskHandler
from apm.models import ApmApplication
from bkmonitor.utils.time_tools import get_datetime_range
from core.drf_resource import api

logger = logging.getLogger("apm")


@dataclass
class UnopenedCheckInfo:
    app: ApmApplication
    request_count: int


@dataclass
class RunningCheckInfo:
    app: ApmApplication
    request_count: int
    queue: str


class PreCalculateCheck:
    """预计算应用运行状态检查器"""

    TIME_DELTA = 60
    # APM 预计算在 BMW 中的名称
    APM_TASK_KIND = "daemon:apm:pre_calculate"

    _INITIAL_TEMPERATURE = 1000
    _COOLING_RATE = 0.95
    _ITERATIONS = 1000

    @classmethod
    def get_application_info_mapping(
        cls,
    ):
        """
        获取未执行预计算任务的应用列表、正在运行预计算任务的应用列表
        """
        start_time, end_time = get_datetime_range(period="minute", distance=cls.TIME_DELTA, rounding=False)
        start_time, end_time = int(start_time.timestamp()), int(end_time.timestamp())
        logger.info(f"[PreCalculateCheck] request_count time range: {start_time} - {end_time}")

        # Step1: 获取所有有效的应用
        applications = ApmApplication.objects.all()
        valid_apps = applications.filter(is_enabled=True, is_enabled_trace=True, is_enabled_metric=True)
        logger.info(
            f"[PreCalculateCheck] valid apps: {len(valid_apps)}({[f'{i.bk_biz_id}-{i.app_name}' for i in valid_apps]})",
        )

        # Step2: 获取所有预计算任务
        daemon_tasks = [
            {
                "task_uni_id": i["uni_id"],
                "payload": i["payload"],
                "data_id": i["payload"]["data_id"],
                "queue": i["options"]["Queue"],
            }
            for i in api.bmw.list_task(task_type="daemon")
            if i.get("kind") == cls.APM_TASK_KIND
        ]
        logger.info(f"[PreCalculateCheck] running bmw tasks: {len(daemon_tasks)}")

        # Step3: 对比得出
        unopened_mapping = {}
        running_mapping = {}

        for app in valid_apps:
            trace_datasource = app.trace_datasource
            metric_datasource = app.metric_datasource
            if not trace_datasource or not metric_datasource:
                logger.warning(
                    f"[PreCalculateCheck] app: {app.bk_biz_id}-{app.app_name} missing trace or metric datasource"
                )
                continue

            # 由 BMW 模块来保证任务正常运行(SaaS 不关注)
            info = next((i for i in daemon_tasks if i["data_id"] == str(trace_datasource.bk_data_id)), None)
            # 获取总数据量
            request_count = DaemonTaskHandler.get_application_request_count(metric_datasource, start_time, end_time)

            if info:
                running_mapping[app.id] = RunningCheckInfo(app=app.id, request_count=request_count, queue=info["queue"])
                logger.info(
                    f"[PreCalculateCheck] running task: {app.bk_biz_id}-{app.app_name} "
                    f"request_count: {request_count} queue: {info['queue']}"
                )
            else:
                unopened_mapping[app.id] = UnopenedCheckInfo(app=app.id, request_count=request_count)
                logger.info(
                    f"[PreCalculateCheck] unopened app: {app.bk_biz_id}-{app.app_name} request_count: {request_count}"
                )

        # Step4: 获取无效应用
        invalid_task_uni_ids = cls._list_invalid_task_uni_ids(daemon_tasks, applications)

        return unopened_mapping, running_mapping, invalid_task_uni_ids

    @classmethod
    def _list_invalid_task_uni_ids(cls, bmw_tasks, applications):
        """获取无效的任务 id 列表（应用被删除、dataId 为空）"""
        res = []

        data_id_app_mapping = {}
        for i in applications:
            if not i.trace_datasource:
                continue
            data_id = i.trace_datasource.bk_data_id
            if data_id:
                data_id_app_mapping[str(data_id)] = i

        for task in bmw_tasks:
            data_id = task["payload"].get("data_id")
            if not data_id or data_id == "None":
                logger.info(
                    f"[PreCalculateCheck] task_id: {task['task_uni_id']} payload.data_id is empty, will be removed",
                )
                res.append(task["task_uni_id"])
            else:
                if data_id not in data_id_app_mapping:
                    logger.info(
                        f"[PreCalculateCheck] task_id: {task['task_uni_id']}"
                        f" payload.data_id: {data_id} not in valid applications, will be removed"
                    )
                    res.append(task["task_uni_id"])

        return list(set(res))

    @classmethod
    def _calculate_cost(cls, queue_info):
        # 用请求量的标准差来反映此刻所有队列的均衡程度
        loads = [info['data_count'] for info in queue_info.values()]
        mean = sum(loads) / len(loads)
        return math.sqrt(sum((x - mean) ** 2 for x in loads))

    @classmethod
    def calculate_distribution(cls, running_mapping, unopened_mapping):
        """使用模拟退火策略，计算未分派应用到合适队列，避免产生总是分配到固定队列的问题"""
        all_queues = settings.APM_BMW_TASK_QUEUES
        if not all_queues:
            logger.info(f"[PreCalculateCheck] empty bmw task queues, return")
            return {}

        if not unopened_mapping:
            return {}

        logger.info(f"[PreCalculateCheck] total {len(all_queues)} queues({all_queues})")

        queue_info = {i: {"data_count": 0, "app_count": 0} for i in all_queues}
        app_assignment = {}

        # 先将已分配队列的应用添加到队列信息中
        for app_id, info in running_mapping.items():
            queue_info[info.queue]["data_count"] += info.request_count
            queue_info[info.queue]["app_count"] += 1
            app_assignment[app_id] = info.queue

        # 为未分配队列的应用分配「随机初始解」
        for app_id, info in unopened_mapping.items():
            random_queue = random.choice(all_queues)
            queue_info[random_queue]["data_count"] += info.request_count
            queue_info[random_queue]["app_count"] += 1
            app_assignment[app_id] = random_queue

        current_cost = cls._calculate_cost(queue_info)
        temperature = cls._INITIAL_TEMPERATURE
        unopened_ids = list(unopened_mapping.keys())
        for _ in range(cls._ITERATIONS):
            # 每次循环随机选择一个应用和一个新队列进行移动
            app_to_move = random.choice(unopened_ids)
            new_queue = random.choice(all_queues)
            # 之前分配的旧队列
            old_queue = app_assignment[app_to_move]
            if old_queue != new_queue:
                queue_info[old_queue]["data_count"] -= unopened_mapping[app_to_move].request_count
                queue_info[old_queue]["app_count"] -= 1
                queue_info[new_queue]["data_count"] += unopened_mapping[app_to_move].request_count
                queue_info[new_queue]["app_count"] += 1

                app_assignment[app_to_move] = new_queue
                new_cost = cls._calculate_cost(queue_info)
                if new_cost < current_cost or random.uniform(0, 1) < math.exp((current_cost - new_cost) / temperature):
                    # 新队列整体有更低负载 或者 命中概率 则完成移动
                    current_cost = new_cost
                else:
                    # 不移动 保持之前的随机结果
                    queue_info[old_queue]['data_count'] += unopened_mapping[app_to_move].request_count
                    queue_info[old_queue]['app_count'] += 1
                    queue_info[new_queue]['data_count'] -= unopened_mapping[app_to_move].request_count
                    queue_info[new_queue]['app_count'] -= 1
                    app_assignment[app_to_move] = old_queue

            temperature *= cls._COOLING_RATE

        # 过滤出未分派的应用返回
        return {k: v for k, v in app_assignment.items() if k not in running_mapping}

    @classmethod
    def distribute(cls, distribute_mapping):
        if not distribute_mapping:
            return
        logger.info(f"[PreCalculateCheck] result: \n{json.dumps(distribute_mapping)}")
        for app_id, queue in distribute_mapping.items():
            DaemonTaskHandler.execute(app_id, queue)

        logger.info(f"[PreCalculateCheck] distribute finished")

    @classmethod
    def batch_remove(cls, task_uni_ids):
        logger.info(f"[PreCalculateCheck] remove tasks: \n{json.dumps(task_uni_ids)}")
        for i in task_uni_ids:
            DaemonTaskHandler.remove(i)
        logger.info(f"[PreCalculateCheck] remove finished")
