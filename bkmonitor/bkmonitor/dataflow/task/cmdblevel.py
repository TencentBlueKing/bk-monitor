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


from django.conf import settings
from django.utils.translation import gettext as _

from bkmonitor.dataflow.node.processor import (
    CMDBPrepareAggregateFullNode,
    CMDBPrepareAggregateSplitNode,
)
from bkmonitor.dataflow.node.source import RelationSourceNode, StreamSourceNode
from bkmonitor.dataflow.node.storage import create_tspider_or_druid_node
from bkmonitor.dataflow.task.base import BaseTask


class CMDBPrepareAggregateTask(BaseTask):
    """
    补充CMDB节点信息  预聚合任务

    如果表中含有固定字段（bk_target_ip, bk_target_cloud_id）两个字段，即可配置这个任务
    """

    TMP_FULL_STORAGE_NODE_EXPIRES = 1  # 临时存储节点保留天数
    MUST_HAVE_FIELDS = {"bk_target_ip", "bk_target_cloud_id"}

    def __init__(self, rt_id, agg_interval, agg_method, metric_field, dimension_fields):
        super(CMDBPrepareAggregateTask, self).__init__()
        if self.MUST_HAVE_FIELDS - set(dimension_fields):
            raise ValueError("bk_target_ip && bk_target_cloud_id must in dimension fields.")

        self.rt_id = rt_id
        cmdb_host_topo_source_node = RelationSourceNode(CMDBPrepareAggregateFullNode.CMDB_HOST_TOPO_RT_ID)
        stream_source_node = StreamSourceNode(rt_id)

        # 将两张原始表的数据，做合并，维度信息补充，1对1
        full_process_node = CMDBPrepareAggregateFullNode(
            source_rt_id=self.rt_id,
            agg_interval=agg_interval,
            agg_method=agg_method,
            metric_fields=metric_field,
            dimension_fields=dimension_fields,
            parent=[cmdb_host_topo_source_node, stream_source_node],
        )

        # cmdb预聚合flow中，去掉中间结果表的存储。
        # full_storage_node = create_tspider_or_druid_node(
        #     source_rt_id=full_process_node.output_table_name,
        #     storage_expires=self.TMP_FULL_STORAGE_NODE_EXPIRES,
        #     parent=full_process_node,
        # )

        # 将补充的信息进行拆解， 1对多
        split_process_node = CMDBPrepareAggregateSplitNode(
            source_rt_id=full_process_node.output_table_name,
            agg_interval=agg_interval,
            agg_method=agg_method,
            metric_fields=metric_field,
            dimension_fields=dimension_fields,
            parent=full_process_node,
        )

        split_storage_node = create_tspider_or_druid_node(
            source_rt_id=split_process_node.output_table_name,
            storage_expires=settings.BK_DATA_DATA_EXPIRES_DAYS,
            parent=split_process_node,
        )

        self.node_list = [
            stream_source_node,
            cmdb_host_topo_source_node,
            full_process_node,
            split_process_node,
            split_storage_node,
        ]

    @property
    def flow_name(self):
        return "{} {}".format(_("CMDB预聚合"), self.rt_id)
