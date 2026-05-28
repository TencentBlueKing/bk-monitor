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
from typing import Any

from django.conf import settings

from apm.core.discover.precalculation.daemon import DaemonTaskHandler
from apm.core.discover.precalculation.task_spec import (
    PreCalculateTaskSpec,
    PreCalculateTaskSpecProvider,
)
from apm.models import ApmApplication, TraceDataSource
from bkmonitor.utils.time_tools import get_datetime_range
from core.drf_resource import api

logger = logging.getLogger("apm")


@dataclass
class UnopenedCheckInfo:
    task_spec: PreCalculateTaskSpec
    load_count: int


@dataclass
class RunningCheckInfo:
    task_spec: PreCalculateTaskSpec
    load_count: int
    queue: str


class PreCalculateCheck:
    """预计算任务检查与调度规划器。"""

    TIME_DELTA = 60
    # APM 预计算在 BMW 中的名称
    APM_TASK_KIND = "daemon:apm:pre_calculate"

    _INITIAL_TEMPERATURE = 1000
    _COOLING_RATE = 0.95
    _ITERATIONS = 1000

    @classmethod
    def _list_daemon_tasks(cls):
        tasks = []
        for task in api.bmw.list_task(task_type="daemon"):
            if task.get("kind") != cls.APM_TASK_KIND:
                continue

            payload = task.get("payload") or {}
            options = task.get("options") or {}
            tasks.append(
                {
                    "task_uni_id": task.get("uni_id"),
                    "payload": payload,
                    "data_id": str(payload.get("data_id")),
                    "queue": options.get("Queue") or options.get("queue"),
                }
            )
        return tasks

    @classmethod
    def get_application_info_mapping(cls):
        """
        获取未执行预计算任务列表、正在运行预计算任务列表。

        保留历史方法名，返回 mapping 的 key 从 app_id 升级为 data_id。
        """
        start_time, end_time = get_datetime_range(period="minute", distance=cls.TIME_DELTA, rounding=False)
        start_time, end_time = int(start_time.timestamp()), int(end_time.timestamp())
        logger.info(f"[PreCalculateCheck] load_count time range: {start_time} - {end_time}")

        # Step1: 获取所有有效的应用
        task_specs: list[PreCalculateTaskSpec] = PreCalculateTaskSpecProvider.list_task_specs()
        logger.info(
            f"[PreCalculateCheck] valid tasks: "
            f"{len(task_specs)}({[task_spec.display_name for task_spec in task_specs]})"
        )

        # Step2: 获取所有预计算任务
        daemon_tasks: list[dict[str, Any]] = cls._list_daemon_tasks()
        daemon_task_mapping: dict[str, dict[str, Any]] = {task["data_id"]: task for task in daemon_tasks}
        logger.info(f"[PreCalculateCheck] running bmw tasks: {len(daemon_tasks)}")

        # Step3: 对比得出
        running_mapping: dict[str, RunningCheckInfo] = {}
        unopened_mapping: dict[str, UnopenedCheckInfo] = {}
        for task_spec in task_specs:
            info = daemon_task_mapping.get(task_spec.data_id)
            load_count = DaemonTaskHandler.get_task_spec_load_count(task_spec, start_time, end_time)

            if info:
                running_mapping[task_spec.data_id] = RunningCheckInfo(
                    task_spec=task_spec, load_count=load_count, queue=info["queue"]
                )
                logger.info(
                    f"[PreCalculateCheck] running task: {task_spec.display_name} "
                    f"load_count: {load_count} queue: {info['queue']}"
                )
            else:
                unopened_mapping[task_spec.data_id] = UnopenedCheckInfo(task_spec=task_spec, load_count=load_count)
                logger.info(f"[PreCalculateCheck] unopened task: {task_spec.display_name} load_count: {load_count}")

        # Step4: 获取无效应用
        invalid_task_uni_ids = cls._list_invalid_task_uni_ids(daemon_tasks)

        return unopened_mapping, running_mapping, invalid_task_uni_ids

    @classmethod
    def _list_invalid_task_uni_ids(cls, bmw_tasks: list[dict[str, Any]]):
        """获取无效的任务 id 列表（应用被删除、dataId 为空）"""
        trace_datasource_mapping: dict[tuple[int, str], TraceDataSource] = {
            (trace_datasource.bk_biz_id, trace_datasource.app_name): trace_datasource
            for trace_datasource in TraceDataSource.objects.all()
        }

        data_ids: set[str] = set()
        for app in ApmApplication.objects.all():
            trace_datasource: TraceDataSource | None = trace_datasource_mapping.get((app.bk_biz_id, app.app_name))
            if not trace_datasource or not trace_datasource.is_ready():
                continue
            data_ids.add(str(trace_datasource.bk_data_id))

        invalid_task_uni_ids: list[str] = []
        for task in bmw_tasks:
            data_id: str | None = task["payload"].get("data_id")
            if not data_id or data_id == "None":
                logger.info(
                    f"[PreCalculateCheck] task_id: {task['task_uni_id']} payload.data_id is empty, will be removed",
                )
                invalid_task_uni_ids.append(task["task_uni_id"])
            else:
                if str(data_id) not in data_ids:
                    logger.info(
                        f"[PreCalculateCheck] task_id: {task['task_uni_id']}"
                        f" payload.data_id: {data_id} not in valid applications, will be removed"
                    )
                    invalid_task_uni_ids.append(task["task_uni_id"])

        return list(set(invalid_task_uni_ids))

    @classmethod
    def _calculate_cost(cls, queue_info):
        # 用请求量的标准差来反映此刻所有队列的均衡程度
        loads = [info["data_count"] for info in queue_info.values()]
        mean = sum(loads) / len(loads)
        return math.sqrt(sum((x - mean) ** 2 for x in loads))

    @classmethod
    def calculate_distribution(cls, running_mapping, unopened_mapping):
        """使用模拟退火策略，计算未分派任务到合适队列，避免产生总是分配到固定队列的问题。"""
        all_queues = settings.APM_BMW_TASK_QUEUES
        if not all_queues:
            logger.info("[PreCalculateCheck] empty bmw task queues, return")
            return {}

        if not unopened_mapping:
            return {}

        logger.info(f"[PreCalculateCheck] total {len(all_queues)} queues({all_queues})")

        queue_info = {i: {"data_count": 0, "app_count": 0} for i in all_queues}
        task_spec_assignment = {}

        # 先将已分配队列的任务添加到队列信息中，保持历史队列不被重新洗牌。
        for data_id, info in running_mapping.items():
            queue_info.setdefault(info.queue, {"data_count": 0, "app_count": 0})
            queue_info[info.queue]["data_count"] += info.load_count
            queue_info[info.queue]["app_count"] += 1
            task_spec_assignment[data_id] = info.queue

        # 为未分配队列的任务分配「随机初始解」
        for data_id, info in unopened_mapping.items():
            random_queue = random.choice(all_queues)
            queue_info[random_queue]["data_count"] += info.load_count
            queue_info[random_queue]["app_count"] += 1
            task_spec_assignment[data_id] = random_queue

        current_cost = cls._calculate_cost(queue_info)
        temperature = cls._INITIAL_TEMPERATURE
        unopened_ids = list(unopened_mapping.keys())
        for _ in range(cls._ITERATIONS):
            # 每次循环随机选择一个未分配任务和一个新队列进行移动。
            task_spec_to_move = random.choice(unopened_ids)
            new_queue = random.choice(all_queues)
            # 之前分配的旧队列
            old_queue = task_spec_assignment[task_spec_to_move]
            if old_queue != new_queue:
                queue_info[old_queue]["data_count"] -= unopened_mapping[task_spec_to_move].load_count
                queue_info[old_queue]["app_count"] -= 1
                queue_info[new_queue]["data_count"] += unopened_mapping[task_spec_to_move].load_count
                queue_info[new_queue]["app_count"] += 1

                task_spec_assignment[task_spec_to_move] = new_queue
                new_cost = cls._calculate_cost(queue_info)
                if new_cost < current_cost or random.uniform(0, 1) < math.exp((current_cost - new_cost) / temperature):
                    # 新队列整体有更低负载 或者 命中概率 则完成移动
                    current_cost = new_cost
                else:
                    # 不移动 保持之前的随机结果
                    queue_info[old_queue]["data_count"] += unopened_mapping[task_spec_to_move].load_count
                    queue_info[old_queue]["app_count"] += 1
                    queue_info[new_queue]["data_count"] -= unopened_mapping[task_spec_to_move].load_count
                    queue_info[new_queue]["app_count"] -= 1
                    task_spec_assignment[task_spec_to_move] = old_queue

            temperature *= cls._COOLING_RATE

        # 过滤出未分派的任务返回
        return {k: v for k, v in task_spec_assignment.items() if k not in running_mapping}

    @classmethod
    def distribute(cls, distribute_mapping: dict[str, str]):
        if not distribute_mapping:
            return

        logger.info(f"[PreCalculateCheck] result: \n{json.dumps(distribute_mapping)}")

        # 获取当前所有期望被下发的任务
        data_ids: set[str] = {str(data_id) for data_id in distribute_mapping.keys()}
        task_specs: list[PreCalculateTaskSpec] = PreCalculateTaskSpecProvider.list_task_specs(data_ids=data_ids)
        task_spec_mapping: dict[str, PreCalculateTaskSpec] = {task_spec.data_id: task_spec for task_spec in task_specs}

        # 下发任务
        for data_id, queue in distribute_mapping.items():
            task_spec: PreCalculateTaskSpec | None = task_spec_mapping.get(str(data_id))
            if not task_spec:
                logger.warning(f"[PreCalculateCheck] distribute task not found, data_id: {data_id}")
                continue

            DaemonTaskHandler.execute(task_spec, queue)

        logger.info("[PreCalculateCheck] distribute finished")

    @classmethod
    def batch_remove(cls, task_uni_ids):
        logger.info(f"[PreCalculateCheck] remove tasks: \n{json.dumps(task_uni_ids)}")
        for i in task_uni_ids:
            DaemonTaskHandler.remove(i)
        logger.info("[PreCalculateCheck] remove finished")
