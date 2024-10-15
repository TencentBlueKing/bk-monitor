# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import logging
from collections import defaultdict
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

    @classmethod
    def get_application_info_mapping(cls):
        """
        获取未执行预计算任务的应用列表、正在运行预计算任务的应用列表
        """
        start_time, end_time = get_datetime_range(period="minute", distance=cls.TIME_DELTA, rounding=False)
        start_time, end_time = int(start_time.timestamp()), int(end_time.timestamp())
        logger.info(f"[PreCalculateCheck] request_count time range: {start_time} - {end_time}")

        # Step1: 获取所有有效的应用
        apps = ApmApplication.objects.filter(is_enabled=True, is_enabled_trace=True, is_enabled_metric=True)
        logger.info(f"[PreCalculateCheck] valid apps: {len(apps)}({[f'{i.bk_biz_id}-{i.app_name}' for i in apps]})")

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

        for app in apps:
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

        return unopened_mapping, running_mapping

    @classmethod
    def calculate_distribution(cls, unopened_mapping, running_mapping):
        """将未分派应用分派到合适的队列中"""
        all_queues = settings.APM_BMW_TASK_QUEUES
        if not all_queues:
            logger.info(f"[PreCalculateCheck] empty bmw task queues, return")
            return {}

        logger.info(f"[PreCalculateCheck] total {len(all_queues)} queues({all_queues})")

        sorted_apps = sorted(
            [(app, info) for app, info in unopened_mapping.items()],
            key=lambda i: i[-1].request_count,
            reverse=True,
        )

        queue_load_mapping = defaultdict(int)
        for app, info in running_mapping.items():
            queue_load_mapping[info.queue] += info.request_count
        queue_loads = [(i, 0) for i in all_queues if i not in queue_load_mapping] + sorted(
            [(queue, request_count) for queue, request_count in queue_load_mapping.items()], key=lambda i: i[-1]
        )

        distribution = defaultdict(list)
        # 贪心 始终将最大量应用分派到负载最小队列
        for item in sorted_apps:
            min_value = float("inf")
            queue_index = 0
            for index, q in enumerate(queue_loads):
                if q[-1] < min_value:
                    min_value = q[-1]
                    queue_index = index

            distribution[queue_loads[queue_index][0]].append(item[0])
            load = queue_loads[queue_index]
            queue_loads[queue_index] = (load[0], load[-1] + item[-1].request_count)

        return distribution

    @classmethod
    def distribute(cls, distribute_mapping):
        if not distribute_mapping:
            return
        logger.info(f"[PreCalculateCheck] result: \n{json.dumps(distribute_mapping)}")
        for queue, app_ids in distribute_mapping.items():
            for app_id in app_ids:
                DaemonTaskHandler.execute(app_id, queue)

        logger.info(f"[PreCalculateCheck] distribute finished")
