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
import copy
import logging
from collections import defaultdict
from typing import Dict

from django.conf import settings

from bkmonitor.dataflow.constant import CheckErrorType
from bkmonitor.dataflow.flow import DataFlow
from bkmonitor.dataflow.task.intelligent_detect import (
    HostAnomalyIntelligentDetectTask,
    StrategyIntelligentModelDetectTask,
)
from bkmonitor.models import AlgorithmModel, QueryConfigModel, StrategyModel
from bkmonitor.strategy.new_strategy import QueryConfig
from bkmonitor.utils.common_utils import to_bk_data_rt_id
from constants.data_source import DataSourceLabel
from core.drf_resource import api
from core.prometheus import metrics

logger = logging.getLogger("aiops.maintainer")


def report_aiops_check_metrics(base_labels: Dict, status: str, exception: str = "", exc_type: str = ""):
    labels = copy.deepcopy(base_labels)
    labels.update({"status": status, "exception": exception, "exc_type": exc_type})
    metrics.AIOPS_STRATEGY_CHECK.labels(**labels).inc()
    metrics.report_all()


class AIOpsStrategyMaintainer:
    """用于巡检职能监控策略和bkbase任务状态是否一致，保证打开的策略有正常运行的任务并输出数据、没有打开的策略任务也是关闭的."""

    MAINTAIN_ACCESS_INTERVAL = 60

    def __init__(self, access_func_factory: callable):
        self.flow_strategies = defaultdict(dict)
        self.monitor_strategies = {}

        self.access_func_factory = access_func_factory

        self.prepare_strategies_in_bkbase()
        self.prepare_strategies_in_monitor()

        # 检测过的有问题的策略ID，防止同一个策略ID上报多个异常埋点
        self.checked_abnormal_strategies = set()

    def prepare_strategies_in_bkbase(self):
        """准备在bkbase中所有的监控策略(基于flow名称)."""
        flow_list = api.bkdata.get_data_flow_list(project_id=settings.BK_DATA_PROJECT_ID)
        if not flow_list:
            logger.info("no dataflow exists in project({})".format(settings.BK_DATA_PROJECT_ID))

        # 需要检测的flow关键字
        flow_name_keys = [
            StrategyIntelligentModelDetectTask.FLOW_NAME_KEY,
            HostAnomalyIntelligentDetectTask.FLOW_NAME_KEY,
        ]

        # 找到当前计算平台已有的模型应用dataflow
        for flow_info in flow_list:
            for flow_name_key in flow_name_keys:
                # 从名称判断是否为智能异常检测的dataflow
                flow_name = flow_info.get("flow_name", "")
                if flow_name_key not in flow_name:
                    continue

                groups = flow_name.split(flow_name_key)
                groups = [i.strip() for i in groups if i.strip()]
                if len(groups) != 2:
                    continue

                strategy_id, biz_or_rt = groups
                if not strategy_id.isdigit():
                    continue

                self.flow_strategies[int(strategy_id)][flow_info["flow_id"]] = {
                    "flow_info": flow_info,
                    "biz_or_rt": biz_or_rt,
                }

    def prepare_strategies_in_monitor(self):
        """准备监控平台所有生效中的智能监控策略."""
        # 找到监控平台配置了智能异常检测的所有策略
        queryset = AlgorithmModel.objects.filter(type__in=AlgorithmModel.AIOPS_ALGORITHMS).values_list(
            "strategy_id", flat=True
        )
        strategy_ids = list(queryset)

        strategies = {item.id: item for item in StrategyModel.objects.filter(id__in=strategy_ids, is_enabled=True)}
        query_configs = {
            query_config.strategy_id: query_config
            for query_config in QueryConfig.from_models(
                QueryConfigModel.objects.filter(strategy_id__in=list(strategies.keys()))
            )
        }
        algorithms = {
            algorithm.strategy_id: algorithm
            for algorithm in AlgorithmModel.objects.filter(
                strategy_id__in=list(strategies.keys()), type__in=AlgorithmModel.AIOPS_ALGORITHMS
            )
        }
        self.monitor_strategies = {
            strategy_id: {
                "strategy": strategy,
                "query_config": query_configs[strategy_id],
                "algorithm": algorithms[strategy_id],
                "base_labels": self.generate_strategy_base_labels(
                    strategy, query_configs[strategy_id], algorithms[strategy_id]
                ),
            }
            for strategy_id, strategy in strategies.items()
        }

    def generate_strategy_base_labels(
        self, strategy: StrategyModel, query_config: QueryConfig, algorithm: AlgorithmModel
    ) -> Dict:
        """生成巡检任务埋点的基础label."""
        return {
            "bk_biz_id": strategy.bk_biz_id,
            "strategy_id": strategy.id,
            "algorithm": algorithm.type,
            "data_source_label": query_config.data_source_label,
            "data_type_label": query_config.data_type_label,
            "metric_id": query_config.metric_id,
        }

    def check_strategies_valid(self):
        """检测监控平台生效中的智能监控策略是否有效.

        1. 检测策略是否完成接入，没有则重新触发接入流程
        2. 检测任务启动状态
        3. 检测任务的数据监控埋点
        4. 检测任务是否有输出
        5. 停止没有生效或已经删除的任务
        """
        if not self.monitor_strategies or not self.flow_strategies:
            logger.warning("No aiops strategies or strategies preparation error.")
            return

        self.access_enable_strategies()

        for strategy_info in self.monitor_strategies.values():
            self.check_strategy_flow_status(strategy_info)

            self.check_strategy_data_monitor_metrics(strategy_info)

            self.check_strategy_output(strategy_info)

            if strategy_info["strategy"].id not in self.checked_abnormal_strategies:
                report_aiops_check_metrics(strategy_info["base_labels"], DataFlow.Status.Running)

        self.stop_invalid_strategies()

    def access_enable_strategies(self):
        """触发没有创建任务且已经打开的智能监控策略的接入."""
        interval = 0

        for strategy_id, strategy_info in self.monitor_strategies.items():
            error_type = CheckErrorType.ACCESS_ERROR

            # 如果告警策略配置记录的flow_id与dataflow记录的flow_id相符，则跳过，否则触发接入流程
            if strategy_id in self.flow_strategies and self.flow_strategies[strategy_id]:
                monitor_flow_id = strategy_info["query_config"].intelligent_detect.get("data_flow_id")

                # 如果已经接入成功（监控配置记录的flow_id和bkbase实际的flow_id一致），且正在运行中，则认为已经接入且成功
                if monitor_flow_id in self.flow_strategies[strategy_id]:
                    if (
                        self.flow_strategies[strategy_id][monitor_flow_id]["flow_info"]["status"]
                        == DataFlow.Status.Running
                    ):
                        continue
                    else:
                        error_type = CheckErrorType.NOT_RUNNING

            # 不满足上述接入成功的条件，则重新触发接入流程，并启动
            try:
                err_msg = (
                    f"Dataflow for strategy({strategy_id}) is abnormal({error_type}: "
                    f"{getattr(strategy_info['query_config'], 'intelligent_detect', {}).get('message')})"
                )
                logger.error(err_msg)
                # access_func = self.access_func_factory(strategy_info["algorithm"].type)
                # access_func.apply_async(args=(strategy_id,), countdown=interval)
                interval += self.MAINTAIN_ACCESS_INTERVAL
                report_aiops_check_metrics(
                    strategy_info["base_labels"],
                    DataFlow.Status.NoStart,
                    err_msg,
                    error_type,
                )
                self.checked_abnormal_strategies.add(strategy_id)
            except BaseException as e:  # noqa
                logger.exception(f"check strategy({strategy_id}) dataflow status error({str(e)})")

    def check_strategy_flow_status(self, strategy_info: Dict):
        """检测任务运行是否有异常.

        :param strategy_info: 策略信息
        """
        if strategy_info["strategy"].id in self.checked_abnormal_strategies:
            return

        flow_id = int(strategy_info["query_config"].intelligent_detect["data_flow_id"])

        # 检测任务启动状态
        deploy_data = api.bkdata.get_latest_deploy_data_flow(flow_id=flow_id)
        if deploy_data["status"] == DataFlow.Status.Failure:
            error_msg = f"Dataflow for strategy({strategy_info['strategy'].id}) had started failure"
            logger.error(error_msg)
            report_aiops_check_metrics(
                strategy_info["base_labels"],
                DataFlow.Status.Failure,
                error_msg,
                CheckErrorType.NOT_RUNNING,
            )
            self.checked_abnormal_strategies.add(strategy_info["strategy"].id)
            return

        # 检测任务的运行状态
        flow_running_info = api.bkdata.get_data_flow_running_info(flow_id=flow_id)
        err_msgs = []
        for node_info in flow_running_info["locations"]:
            if node_info["status"] == DataFlow.Status.Failure:
                err_msgs.append(f"Node[{node_info['node_name']}]({node_info['node_type']}) is running failure")
        if err_msgs:
            error_msg = (
                f"Dataflow for strategy({strategy_info['strategy'].id}) is running failure({'|'.join(err_msgs)})"
            )
            logger.error(error_msg)
            report_aiops_check_metrics(
                strategy_info["base_labels"],
                DataFlow.Status.Failure,
                error_msg,
                CheckErrorType.RUNNING_FAILURE,
            )
            self.checked_abnormal_strategies.add(strategy_info["strategy"].id)
            return

    def check_strategy_data_monitor_metrics(self, strategy_info: Dict):
        """检测任务的数据监控埋点.

        :param strategy_info: 策略信息
        """
        if strategy_info["strategy"].id in self.checked_abnormal_strategies:
            return

        if strategy_info["query_config"].data_source_label == DataSourceLabel.BK_DATA:
            bk_data_result_table_id = strategy_info["query_config"].result_table_id
        else:
            bk_data_result_table_id = to_bk_data_rt_id(
                strategy_info["query_config"].result_table_id, settings.BK_DATA_RAW_TABLE_SUFFIX
            )

        # 默认检查最近1小时的输出埋点
        metrics_data = api.bkdata.get_data_monitor_metrics(
            data_set_ids=bk_data_result_table_id,
            start_time="now()-1h",
            format="value",
        )
        if not (len(metrics_data) > 0 and metrics_data[0]["value"]["output_count"] > 0):
            error_msg = f"Dataflow for strategy({strategy_info['strategy'].id}) has no metrics about running"
            logger.error(error_msg)
            report_aiops_check_metrics(
                strategy_info["base_labels"],
                DataFlow.Status.Failure,
                error_msg,
                CheckErrorType.NO_RUNTIME_METRICS,
            )
            self.checked_abnormal_strategies.add(strategy_info["strategy"].id)

    def check_strategy_output(self, strategy_info: Dict):
        """检测任务是否有输出.

        :param strategy_info: 策略信息
        """
        if strategy_info["strategy"].id in self.checked_abnormal_strategies:
            return

        # 默认监控平台也是查RT存储的数据，暂不对结果表数据进行检测
        pass

    def stop_invalid_strategies(self):
        """停止没有生效或已经删除的任务."""
        for strategy_id, flows in self.flow_strategies.items():
            monitor_flow_id = None

            # 如果监控有对应策略，但是flow id不对应，也需要停止对应任务
            if strategy_id in self.monitor_strategies:
                strategy_info = self.monitor_strategies[strategy_id]
                monitor_flow_id = strategy_info["query_config"].intelligent_detect.get("data_flow_id")

            for bkbase_flow_id in flows.keys():
                if monitor_flow_id and int(monitor_flow_id) == bkbase_flow_id:
                    continue

                if flows[bkbase_flow_id]["flow_info"]["status"] == DataFlow.Status.Running:
                    try:
                        logger.info(
                            f"stop dataflow({bkbase_flow_id}) because strategy({strategy_id}) is disabled or deleted"
                        )
                        api.bkdata.stop_data_flow(flow_id=bkbase_flow_id)
                    except BaseException:  # noqa
                        logger.exception(f"stop dataflow({bkbase_flow_id}) error")
