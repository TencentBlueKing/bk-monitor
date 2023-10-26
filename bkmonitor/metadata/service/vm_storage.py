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

import json
import logging
from typing import List, Optional

from metadata import models
from metadata.utils import consul_tools

logger = logging.getLogger(__name__)


def disable_influxdb_router_for_vm_table(
    table_ids: List, switched_storage_id: Optional[int] = 0, can_deleted: Optional[bool] = False
) -> bool:
    """禁用接入 vm 的结果表的写入 influxdb 的路由
    :param table_ids: 结果表 id
    :param switched_storage_id: 要切换到的关联关系 ID
    :param can_deleted: 是否删除
    :return: 返回是否成功
    """
    # NOTE: 现阶段路由的入口还是通过influxdb查询，这样会导致 influxdb 和 vm 比较混乱
    # 而且已经提供 vm 的接入路由，因此，可以切换到 vm 的记录中
    qs = models.InfluxDBStorage.objects.filter(table_id__in=table_ids)
    # 如果标识为要删除，则直接删除记录
    if can_deleted:
        qs.delete()
        logger.info("deleted router for table_id: %s", json.dumps(table_ids))
    # 如果不删除，则查询要切换到的存储关系是否有传递
    # 如果传递，则使用传递的数据
    # 否则，使用默认的数据
    else:
        logger.info("start to update influxdb router for table_id: %s", json.dumps(table_ids))
        # 检查集群 id 为 vm 类型
        if switched_storage_id:
            if not models.ClusterInfo.objects.filter(
                cluster_id=switched_storage_id, cluster_type=models.ClusterInfo.TYPE_VM
            ).exists():
                raise ValueError("storage cluster id: %s not vm type", switched_storage_id)
        else:
            vm_qs = models.AccessVMRecord.objects.filter(result_table_id__in=table_ids)
            if not vm_qs.exists():
                raise ValueError("table_id: %s not access to vm", json.dumps(table_ids))
            switched_storage_id = vm_qs.first().vm_cluster_id

        proxy_storage_qs = models.InfluxDBProxyStorage.objects.filter(proxy_cluster_id=switched_storage_id)
        if not proxy_storage_qs.exists():
            raise ValueError("storage cluster id: %s not register InfluxDBProxyStorage", switched_storage_id)
        proxy_storage_id = proxy_storage_qs.first().id
        qs.update(storage_cluster_id=switched_storage_id, influxdb_proxy_storage_id=proxy_storage_id)

    # 更新数据源的consul, 并且刷新路由配置
    logger.info("start to refresh datasource router")
    bk_data_ids = models.DataSourceResultTable.objects.filter(table_id__in=table_ids).values_list(
        "bk_data_id", flat=True
    )
    for ds in models.DataSource.objects.filter(bk_data_id__in=bk_data_ids):
        try:
            ds.refresh_outer_config()
        except Exception as e:
            logger.error("refresh datasource: %s consul error, %s", ds.bk_data_id, e)

    # 更新路由配置，需要通知到 unifyquery
    logger.info("start to refresh influxdb router")
    tsdb_qs = models.InfluxDBStorage.objects.filter(table_id__in=table_ids)
    index = tsdb_qs.count()
    for record in tsdb_qs:
        index -= 0
        record.refresh_consul_cluster_config(is_publish=(index == 0))

    consul_tools.refresh_router_version()

    # 更新 vm 路由
    models.AccessVMRecord.refresh_vm_router()

    logger.info("disable influxdb router for vm table successfully")
