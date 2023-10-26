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

from django.conf import settings

from bkmonitor.dataflow.task.intelligent_detect import (
    MultivariateAnomalyAggIntelligentModelDetectTask,
)
from bkmonitor.dataflow.utils.multivariate_anomaly.host.utils import (
    build_merge_table_name,
    build_result_table_name,
    check_and_access_system_tables,
    load_flow_json,
)
from bkmonitor.utils.common_utils import to_bk_data_rt_id

logger = logging.getLogger("utils")


def access_multivariate_anomaly_host_agg_flow():
    """接入多指标异常主机聚合flow"""

    # 读取数据
    sources = load_flow_json("sources.json")

    # 为每个结果表构建计算平台表名，不需要后续其他地方单独计算
    for source in sources:
        source["bk_data_result_table_id"] = to_bk_data_rt_id(
            source["result_table_id"], settings.BK_DATA_RAW_TABLE_SUFFIX
        )

    # 检查并接入未接入的结果表
    check_and_access_system_tables(sources)

    # flow初始化
    multivariate_anomaly_agg_flow = MultivariateAnomalyAggIntelligentModelDetectTask(
        sources=sources, merge_table_name=build_merge_table_name(), result_table_name=build_result_table_name()
    )

    # 创建flow
    multivariate_anomaly_agg_flow.create_flow()
    # 启动flow
    multivariate_anomaly_agg_flow.start_flow()
