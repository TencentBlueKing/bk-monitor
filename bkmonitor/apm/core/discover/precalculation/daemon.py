"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2017-2025 Tencent,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import logging
import random
from collections import defaultdict
from typing import Any

from django.conf import settings

from apm.core.discover.precalculation.consul_handler import ConsulHandler
from apm.core.discover.precalculation.task_spec import (
    PreCalculateTaskSpec,
    PreCalculateTaskSpecProvider,
)
from bkmonitor.utils.time_tools import get_datetime_range
from core.drf_resource import api, resource
from core.errors.api import BKAPIError

logger = logging.getLogger("apm")


class DaemonTaskHandler:
    """预计算常驻任务处理类"""

    DAEMON_TASK_NAME = "daemon:apm:pre_calculate"

    @classmethod
    def _create_daemon_task(cls, data_id, queue=None, body=None):
        payload = dict(body or {})
        payload.update({"data_id": str(data_id)})

        params: dict[str, Any] = {"kind": cls.DAEMON_TASK_NAME, "payload": payload, "options": {}}
        if queue:
            params["options"]["queue"] = queue

        logger.info(f"request create_task api, params: \n-----\n{params}\n-----\n")
        api.bmw.create_task(params)
        logger.info("trigger worker create successfully")

    @classmethod
    def execute(cls, task_spec: PreCalculateTaskSpec, queue=None, body=None):
        try:
            # 1. 刷新配置到consul
            data_id = ConsulHandler.check_update_by_task_spec(task_spec)
            if not data_id:
                logger.warning(f"failed to obtain consul config of task: {task_spec.display_name}")
                return
            logger.info(f"push task: {task_spec.display_name} to consul success")
            # 2. 触发任务
            cls._create_daemon_task(data_id, queue, body)
        except Exception as e:  # noqa
            logger.exception(f"execute task: {task_spec.display_name} to queue: {queue} failed, error: {e}")

    @classmethod
    def reload(cls, task_uni_id, payload=None):
        params = {"task_uni_id": task_uni_id}
        if payload:
            payload.pop("data_id", None)
            params["payload"] = payload

        logger.info(f"request reload_daemon_task api, params: \n-----\n{params}\n-----\n")
        api.bmw.reload_daemon_task(params)
        logger.info("trigger worker reload successfully")

    @classmethod
    def remove(cls, task_uni_id):
        try:
            params = {
                "task_type": "daemon",
                "task_uni_id": task_uni_id,
            }
            logger.info(f"request remove_task api, params: \n-----\n{params}\n-----\n")
            response = api.bmw.remove_task(params)
            logger.info(f"trigger worker remove successfully, response: {response}")
        except BKAPIError as e:
            logger.exception(f"remove task_uni_id: {task_uni_id} failed, error: {e}")

    @classmethod
    def get_task_info(cls):
        """
        获取预计算任务数据
        包含:
        1. SaaS 侧执行的任务
        2. BMW 侧执行的任务
        3. BMW 侧异常任务（异常任务指：独占任务指标有数据但是队列接收消息指标无数据）
        4. BMW 侧未启动任务
        """
        deployed_biz_id = settings.APM_BMW_DEPLOY_BIZ_ID
        if deployed_biz_id == 0:
            raise ValueError("bmw deploy biz is empty, please check whether bmw is deployed or configured")

        task_specs_for_beat = []
        task_specs_for_daemon = []
        task_specs_for_reload = []
        task_specs_for_create = []

        task_specs = PreCalculateTaskSpecProvider.list_task_specs(
            enabled_only=True,
            require_trace_enabled=False,
            require_metric_enabled=False,
        )
        start_time, end_time = get_datetime_range("minute", 10)
        start_time, end_time = int(start_time.timestamp()), int(end_time.timestamp())

        for index, task_spec in enumerate(task_specs):
            # 常驻任务方式进行预计算
            is_running = cls.is_daemon_task_running(deployed_biz_id, task_spec.data_id, start_time, end_time)
            if is_running:
                is_receive_data = cls.is_daemon_task_receive_data(
                    deployed_biz_id, task_spec.data_id, start_time, end_time
                )
                if not is_receive_data:
                    if cls.is_normal(task_spec, start_time, end_time):
                        task_specs_for_reload.append(task_spec)
                        logger.info(
                            f"[{index}/{len(task_specs)}] {task_spec.display_name} "
                            f"running: ok | data_status: ok | daemon_receive_data: bad -> reload",
                        )
                    else:
                        logger.info(
                            f"[{index}/{len(task_specs)}] {task_spec.display_name} task: ok(daemon, empty data) -> skip"
                        )
                else:
                    task_specs_for_daemon.append(task_spec)
                    logger.info(f"[{index}/{len(task_specs)}] {task_spec.display_name} task ok(daemon) -> skip")

            else:
                # 定时任务方式进行预计算
                task_specs_for_beat.append(task_spec)
                logger.info(f"[{index}/{len(task_specs)}] {task_spec.display_name} task: ok(beat) -> skip")

        return task_specs_for_beat, task_specs_for_daemon, task_specs_for_reload, task_specs_for_create

    @classmethod
    def is_normal(cls, task_spec: PreCalculateTaskSpec, start_time, end_time):
        """获取此任务是否有数据。"""
        return cls.get_task_spec_load_count(task_spec, start_time, end_time) > 0

    @classmethod
    def get_task_spec_load_count(cls, task_spec: PreCalculateTaskSpec, start_time: int, end_time: int) -> int:
        """按应用指标估算预计算任务的负载，共享任务不参与负载估算。"""
        if task_spec.is_shared:
            # 共享 data_id 不按 App 拆分负载；直接返回 0，避免巡检阶段扫描 trace 原表。
            return 0

        metric_datasource = task_spec.primary_app.metric_datasource
        if not metric_datasource:
            return 0

        query = {
            "id": "bk_apm_count",
            "expression": "a",
            "display": True,
            "start_time": start_time,
            "end_time": end_time,
            "dimension_field": "",
            "query_configs": [
                {
                    "data_source_label": "custom",
                    "data_type_label": "time_series",
                    "metrics": [
                        {
                            "field": "bk_apm_count",
                            "method": "SUM",
                            "alias": "a",
                        }
                    ],
                    "table": metric_datasource.result_table_id,
                    "group_by": [],
                    "display": True,
                    "where": [],
                    "interval_unit": "s",
                    "time_field": "time",
                    "filter_dict": {},
                    "functions": [],
                }
            ],
            "target": [],
            "bk_biz_id": metric_datasource.bk_biz_id,
        }

        try:
            result = resource.grafana.graph_unify_query(query)
            if not result or not result.get("series"):
                return 0

            return sum(i[0] for i in result["series"][0]["datapoints"])
        except Exception as e:  # noqa
            logger.warning(
                f"failed to get request_count of app: {metric_datasource.bk_biz_id}-{metric_datasource.app_name}",
            )
            return 0

    @classmethod
    def is_daemon_task_receive_data(cls, deployed_biz_id, bk_data_id, start_time, end_time):
        """获取常驻任务此应用是否接收到数据"""
        metric_name = "bmw_apm_pre_calc_notifier_receive_message_count"
        query = {
            "id": metric_name,
            "expression": "a",
            "display": True,
            "start_time": start_time,
            "end_time": end_time,
            "dimension_field": "",
            "query_configs": [
                {
                    "data_source_label": "custom",
                    "data_type_label": "time_series",
                    "metrics": [
                        {
                            # 常驻任务 Kafka 队列消息接收数量指标
                            "field": metric_name,
                            "method": "SUM",
                            "alias": "a",
                        }
                    ],
                    "table": "",
                    "group_by": [],
                    "display": True,
                    "where": [{"key": "data_id", "method": "eq", "value": [bk_data_id]}],
                    "interval_unit": "s",
                    "time_field": "time",
                    "filter_dict": {},
                    "functions": [],
                }
            ],
            "target": [],
            "bk_biz_id": deployed_biz_id,
        }

        result = resource.grafana.graph_unify_query(query)
        if not result or not result.get("series"):
            return False

        return sum(i[0] for i in result["series"][0]["datapoints"]) > 0

    @classmethod
    def is_daemon_task_running(cls, deployed_biz_id, bk_data_id, start_time, end_time):
        """检查常驻任务是否正在运行"""

        metric_name = "daemon_running_task_count"
        query = {
            "id": metric_name,
            "expression": "a",
            "display": True,
            "start_time": start_time,
            "end_time": end_time,
            "dimension_field": "",
            "query_configs": [
                {
                    "data_source_label": "custom",
                    "data_type_label": "time_series",
                    "metrics": [
                        {
                            # 常驻任务 Kafka 队列消息接收数量指标
                            "field": metric_name,
                            "method": "SUM",
                            "alias": "a",
                        }
                    ],
                    "table": "",
                    "group_by": [],
                    "display": True,
                    "where": [{"key": "task_dimension", "method": "eq", "value": [bk_data_id]}],
                    "interval_unit": "s",
                    "time_field": "time",
                    "filter_dict": {},
                    "functions": [],
                }
            ],
            "target": [],
            "bk_biz_id": deployed_biz_id,
        }

        result = resource.grafana.graph_unify_query(query)
        if not result or not result.get("series"):
            return False

        return len(result["series"][0]["datapoints"]) > 0

    @classmethod
    def create_tasks(cls, task_specs, queue):
        for task_spec in task_specs:
            cls.execute(task_spec, queue)

    @classmethod
    def reload_tasks(cls, task_specs):
        # 避免 py 和 go 计算 TaskUniId 不一致 这里取任务列表中的 taskUniId
        daemon_tasks = api.bmw.list_task(task_type="daemon")

        for task_spec in task_specs:
            data_id = task_spec.data_id
            task_uni_id = next(
                (i.get("uni_id") for i in daemon_tasks if str(i.get("payload", {}).get("data_id", "")) == str(data_id)),
                None,
            )
            if not task_uni_id:
                logger.warning(
                    f"[RELOAD TASKS] "
                    f"dataId: {data_id}({task_spec.display_name}) task was not found, "
                    f"please check if it is running"
                )
                continue

            cls.reload(task_uni_id)
            logger.info(f"[RELOAD] dataId: {data_id} task: {task_spec.display_name} reload success")

    @classmethod
    def list_rebalance_info(cls, queues):
        have_data_task_specs = []
        start_time, end_time = get_datetime_range("minute", 10)
        start_time, end_time = int(start_time.timestamp()), int(end_time.timestamp())

        task_specs = PreCalculateTaskSpecProvider.list_task_specs(
            enabled_only=True,
            require_trace_enabled=True,
            require_metric_enabled=True,
        )
        random.shuffle(task_specs)
        for task_spec in task_specs:
            try:
                if cls.is_normal(task_spec, start_time, end_time):
                    logger.info(f"[Rebalance] 有数据任务: {task_spec.display_name}")
                    have_data_task_specs.append(task_spec)
            except Exception as e:  # noqa
                logger.warning(f"[Rebalance] 查询 {task_spec.display_name} 数据状态时出现异常 - {e}")

        res = defaultdict(list, {queue: [] for queue in queues})

        # 先分配有数据应用到各个队列 尽量保持每个队列数量相同
        queues_count = len(queues)
        for index, task_spec in enumerate(have_data_task_specs):
            queue_index = index % queues_count
            res[queues[queue_index]].append(task_spec)

        # 再分配无数据应用
        for task_spec in task_specs:
            if task_spec in have_data_task_specs:
                continue

            # 找当前数量最小的队列
            min_queue = min(res, key=lambda k: len(res[k]))
            res[min_queue].append(task_spec)

        return res, have_data_task_specs

    @classmethod
    def rebalance(cls, queue_task_spec_mapping):
        for queue, task_specs in queue_task_spec_mapping.items():
            for task_spec in task_specs:
                cls.execute(task_spec, queue=queue, body={})
