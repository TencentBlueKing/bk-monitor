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

# 清理停用的aiops策略对应的flow
from django.conf import settings
from django.core.management import BaseCommand

from bkmonitor.dataflow.flow import DataFlow
from bkmonitor.dataflow.task.intelligent_detect import (
    StrategyIntelligentModelDetectTask,
)
from bkmonitor.models import AlgorithmModel, QueryConfigModel, StrategyModel
from bkmonitor.strategy.new_strategy import QueryConfig
from bkmonitor.utils.common_utils import to_bk_data_rt_id
from constants.data_source import DataSourceLabel
from core.drf_resource import api


class Command(BaseCommand):
    def handle(self, **kwargs):
        run_clean()


def run_clean():
    result = api.bkdata.get_data_flow_list(project_id=settings.BK_DATA_PROJECT_ID)

    # 找到当前计算平台已有的模型应用dataflow
    strategy_to_data_flow = {}
    for flow in result:
        # 去掉没在运行的dataflow
        flow_status = flow["status"]
        if flow_status != DataFlow.Status.Running:
            continue

        # 从名称判断是否为智能异常检测的dataflow
        flow_name = flow.get("flow_name", "")
        if StrategyIntelligentModelDetectTask.FLOW_NAME_KEY not in flow_name:
            continue

        groups = flow_name.split(StrategyIntelligentModelDetectTask.FLOW_NAME_KEY)
        groups = [i.strip() for i in groups if i.strip()]
        if len(groups) != 2:
            continue

        strategy_id, rt_id = groups
        if not strategy_id.isdigit():
            continue

        strategy_to_data_flow.setdefault(int(strategy_id), []).append({"rt_id": rt_id, "flow": flow})

    # 找到监控平台配置了智能异常检测的所有策略
    strategy_ids = list(
        AlgorithmModel.objects.filter(type__in=AlgorithmModel.AIOPS_ALGORITHMS).values_list("strategy_id", flat=True)
    )
    strategy_ids = list(StrategyModel.objects.filter(id__in=strategy_ids).values_list("id", flat=True))
    query_configs = QueryConfig.from_models(QueryConfigModel.objects.filter(strategy_id__in=strategy_ids))
    strategy_to_query_config = {query_config.strategy_id: query_config for query_config in query_configs}

    # 停用掉策略已停用或删除，但是计算平台仍然在运行的dataflow
    print("# 停用掉策略已停用或删除，但是计算平台仍然在运行的dataflow")
    for strategy_id in set(strategy_to_data_flow.keys()) - set(strategy_to_query_config.keys()):
        flow_list = strategy_to_data_flow.get(strategy_id)
        for f in flow_list:
            flow_id, flow_status = f["flow"]["flow_id"], f["flow"]["status"]
            print(strategy_id, flow_id)
            api.bkdata.stop_data_flow(flow_id=flow_id)

    # 停用仍在使用AIOps策略，但结果表已被切换的flow
    print("# 停用仍在使用AIOps策略，但结果表已被切换的flow")
    for strategy_id in set(strategy_to_query_config.keys()) & set(strategy_to_data_flow.keys()):
        rt_query_config = strategy_to_query_config.get(strategy_id)
        if rt_query_config.data_source_label == DataSourceLabel.BK_DATA:
            bk_data_result_table_id = rt_query_config.result_table_id
        else:
            bk_data_result_table_id = to_bk_data_rt_id(
                rt_query_config.result_table_id, settings.BK_DATA_RAW_TABLE_SUFFIX
            )

        # 去掉多余的dataflow
        flow_list = strategy_to_data_flow.get(strategy_id)
        for f in flow_list:
            rt_id = f["rt_id"]
            flow_id = f["flow"]["flow_id"]
            if rt_id != bk_data_result_table_id:
                print(strategy_id, flow_id)
                api.bkdata.stop_data_flow(flow_id=flow_id)
