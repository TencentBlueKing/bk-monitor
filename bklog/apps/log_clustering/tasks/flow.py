# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
from apps.log_clustering.handlers.clustering_config import ClusteringConfigHandler
from apps.log_clustering.handlers.data_access.data_access import DataAccessHandler
from apps.log_clustering.handlers.dataflow.dataflow_handler import DataFlowHandler
from apps.utils.log import logger
from apps.utils.task import high_priority_task


@high_priority_task(ignore_result=True)
def update_clustering_clean(collector_config_id, fields, etl_config, etl_params):
    logger.info(f"update flow beginning: collector_config_id -> {collector_config_id}")
    clustering_handler = ClusteringConfigHandler(collector_config_id=collector_config_id)
    ClusteringConfigHandler.pre_check_fields(
        fields=fields, etl_config=etl_config, clustering_fields=clustering_handler.data.clustering_fields
    )
    if clustering_handler.data.bkdata_etl_processing_id:
        DataAccessHandler().create_or_update_bkdata_etl(collector_config_id, fields, etl_params)
    DataFlowHandler().update_flow(index_set_id=clustering_handler.data.index_set_id)
    logger.info(f"update flow success: collector_config_id -> {collector_config_id}")
