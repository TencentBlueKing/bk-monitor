# -*- coding: utf-8 -*-
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

from django.conf import settings

from apm.core.discover.precalculation.consul_handler import ConsulHandler
from apm.models import ApmApplication, MetricDataSource, TraceDataSource
from bkmonitor.utils import group_by
from bkmonitor.utils.time_tools import get_datetime_range
from core.drf_resource import api, resource
from core.errors.api import BKAPIError

logger = logging.getLogger("apm")


class DaemonTaskHandler:
    """预计算常驻任务处理类"""

    DAEMON_TASK_NAME = "daemon:apm:pre_calculate"

    @classmethod
    def execute(cls, app_id, queue=None, body=None):
        try:
            # 1. 刷新配置到consul
            data_id = ConsulHandler.check_update_by_app_id(app_id)
            if not data_id:
                logger.warning(f"failed to obtain consul config of app_id: {app_id}")
                return
            logger.info(f"push app_id: {app_id} data_id: {data_id} to consul success")
            # 2. 触发任务

            payload = body or {}
            payload.update({"data_id": str(data_id)})

            params = {"kind": cls.DAEMON_TASK_NAME, "payload": payload, "options": {}}
            if queue:
                params["options"]["queue"] = queue

            logger.info(f"request create_task api, params: \n-----\n{params}\n-----\n")
            api.bmw.create_task(params)
            logger.info("trigger worker create successfully")
        except Exception as e:  # noqa
            logger.exception(f"execute app_id: {app_id} to queue: {queue} failed, error: {e}")

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
        1. SaaS 侧执行的应用
        2. BMW 侧执行的应用
        3. BMW 侧异常应用（异常应用指：bk_apm_count 有数据但是队列接收消息指标无数据）
        4. BMW 侧未启动应用
        """
        deployed_biz_id = settings.APM_BMW_DEPLOY_BIZ_ID
        if deployed_biz_id == 0:
            raise ValueError("bmw deploy biz is empty, please check whether bmw is deployed or configured")

        apps_for_beat = []
        apps_for_daemon = []
        apps_for_reload = []
        apps_for_create = []

        apps = ApmApplication.objects.filter(is_enabled=True)
        metric_datasource_mapping = group_by(MetricDataSource.objects.all(), lambda i: (i.bk_biz_id, i.app_name))
        trace_datasource_mapping = group_by(TraceDataSource.objects.all(), lambda i: (i.bk_biz_id, i.app_name))

        for index, app in enumerate(apps):
            metric_datasource = metric_datasource_mapping.get((app.bk_biz_id, app.app_name))
            trace_datasource = trace_datasource_mapping.get((app.bk_biz_id, app.app_name))
            if not metric_datasource or not trace_datasource:
                logger.warning(
                    f"[get_task_info] ({app.bk_biz_id}){app.app_name} traceDatasource/metricDatasource not found, skip",
                )
                continue

            start_time, end_time = get_datetime_range("minute", 10)
            start_time, end_time = int(start_time.timestamp()), int(end_time.timestamp())

            # 常驻任务方式进行预计算
            is_running = cls.is_daemon_task_running(
                deployed_biz_id, trace_datasource[0].bk_data_id, start_time, end_time
            )
            if is_running:
                is_receive_data = cls.is_daemon_task_receive_data(
                    deployed_biz_id, trace_datasource[0].bk_data_id, start_time, end_time
                )
                if not is_receive_data:
                    if cls.is_normal(metric_datasource[0], start_time, end_time):
                        apps_for_reload.append(app)
                        logger.info(
                            f"[{index}/{len(apps)}] ({app.bk_biz_id}){app.app_name} "
                            f"running: ok | data_status: ok | daemon_receive_data: bad -> reload"
                        )
                    else:
                        logger.info(
                            f"[{index}/{len(apps)}] ({app.bk_biz_id}){app.app_name} "
                            f"task: ok(daemon, empty data) -> skip"
                        )
                else:
                    apps_for_daemon.append(app)
                    logger.info(f"[{index}/{len(apps)}] ({app.bk_biz_id}){app.app_name} task ok(daemon) -> skip")

            else:
                # 定时任务方式进行预计算
                apps_for_beat.append(app)
                logger.info(f"[{index}/{len(apps)}] ({app.bk_biz_id}){app.app_name} task: ok(beat) -> skip")

        return apps_for_beat, apps_for_daemon, apps_for_reload, apps_for_create

    @classmethod
    def get_application_request_count(cls, metric_datasource, start_time, end_time):
        """获取应用的总数据量"""

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
    def is_normal(cls, metric_datasource, start_time, end_time):
        """获取此应用是否有数据"""
        return cls.get_application_request_count(metric_datasource, start_time, end_time) > 0

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
    def create_tasks(cls, applications, queue):
        for app in applications:
            cls.execute(app.id, queue)

    @classmethod
    def reload_tasks(cls, applications):
        # 避免 py 和 go 计算 TaskUniId 不一致 这里取任务列表中的 taskUniId
        daemon_tasks = api.bmw.list_task(task_type="daemon")

        for app in applications:
            data_id = app.trace_datasource.bk_data_id
            task_uni_id = next(
                (i.get("uni_id") for i in daemon_tasks if str(i.get("payload", {}).get("data_id", "")) == str(data_id)),
                None,
            )
            if not task_uni_id:
                logger.warning(
                    f"[RELOAD TASKS] "
                    f"dataId: {data_id}(app: [{app.bk_biz_id}]{app.app_name}) task was not found, "
                    f"please check if it is running"
                )
                continue

            cls.reload(task_uni_id)
            logger.info(f"[RELOAD] dataId: {data_id} app: ({app.bk_biz_id}){app.app_name} reload success")

    @classmethod
    def list_rebalance_info(cls, queues):
        have_data_apps = []
        exclude_apps = []
        start_time, end_time = get_datetime_range("minute", 10)
        start_time, end_time = int(start_time.timestamp()), int(end_time.timestamp())

        applications = list(ApmApplication.objects.filter(is_enabled=True))
        random.shuffle(applications)
        for i in applications:
            if i.metric_datasource:
                try:
                    if cls.is_normal(i.metric_datasource, start_time, end_time):
                        logger.info(f"[Rebalance] 有数据应用: {i.bk_biz_id} - {i.app_name}")
                        have_data_apps.append(i)
                except Exception as e:  # noqa
                    logger.warning(f"[Rebalance] 查询 {i.bk_biz_id} - {i.app_name} 数据状态时出现异常 - {e}")
            else:
                exclude_apps.append(i)

        res = defaultdict(list)

        # 先分配有数据应用到各个队列 尽量保持每个队列数量相同
        queues_count = len(queues)
        for index, app in enumerate(have_data_apps):
            queue_index = index % queues_count
            res[queues[queue_index]].append(app)

        # 再分配无数据应用
        for i in applications:
            if i in have_data_apps or i in exclude_apps:
                continue

            # 找当前数量最小的队列
            min_queue = min(res, key=lambda k: len(res[k]))
            res[min_queue].append(i)

        return res, have_data_apps

    @classmethod
    def rebalance(cls, queue_application_mapping):
        for queue, apps in queue_application_mapping.items():
            for app in apps:
                cls.execute(app.id, queue=queue, body={})
