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
import logging
from datetime import datetime

from apm.core.discover.metric.base import Discover
from apm.models import TopoNode
from constants.apm import TelemetryDataType
from core.drf_resource import api

logger = logging.getLogger(__name__)


class ServiceDiscover(Discover):
    """从指标中发现服务"""

    def list_exists_mapping(self):
        return {
            i["topo_key"]: i
            for i in TopoNode.objects.filter(
                bk_biz_id=self.bk_biz_id,
                app_name=self.app_name,
            ).values("id", "topo_key", "source")
        }

    def discover(self, start_time, end_time):
        # Step1: 查询普通指标中的 service_name 维度
        params = {
            "bk_biz_ids": [self.bk_biz_id],
            "start": start_time,
            "end": end_time,
            "step": f"{end_time - start_time}s",
        }
        normal_pql = f'count by (service_name) ({{__name__=~"custom:{self.result_table_id}:.*"}})'
        params["promql"] = normal_pql
        response = api.unify_query.query_data_by_promql(params)

        # Step2: 查询框架中的 target 维度
        trpc_pql = f'count by (target) ({{__name__=~"custom:{self.result_table_id}:trpc.*"}})'
        params["promql"] = trpc_pql
        target_response = api.unify_query.query_data_by_promql(params)

        dimensions = [
            {i: item.get("group_values")[index] for index, i in enumerate(item["group_keys"])}
            for item in response.get("series", [])
            if item.get("group_keys")
        ] + [
            {i: item.get("group_values")[index] for index, i in enumerate(item["group_keys"])}
            for item in target_response.get("series", [])
            if item.get("group_keys")
        ]

        logger.info(f"[MetricServiceDiscover] ({self.bk_biz_id}:{self.app_name}) query series with params: {params}")
        if not response:
            return

        logger.info(f"[MetricServiceDiscover] ({self.bk_biz_id}:{self.app_name}) find {len(dimensions)} dimensions")
        exists_mapping = self.list_exists_mapping()
        update_instances = []
        create_instances = []
        found_topo_keys = []
        for item in dimensions:
            service_name = item.get("service_name")
            target = item.get("target")
            # TODO 获取其他指标的维度信息

            if not service_name and target:
                # 满足 [a].<b>.<c> 格式才认为是节点
                targets = target.split(".")
                if 2 <= len(targets) <= 3:
                    target = ".".join(targets[-2:])
                else:
                    continue

            topo_key = service_name or target
            if not topo_key or topo_key in found_topo_keys:
                continue

            if topo_key in exists_mapping:
                source = exists_mapping[topo_key]["source"]
                if not source:
                    source = [TelemetryDataType.METRIC.value]
                elif TelemetryDataType.METRIC.value not in source:
                    source.append(TelemetryDataType.METRIC.value)
                update_instances.append(
                    TopoNode(
                        bk_biz_id=self.bk_biz_id,
                        app_name=self.app_name,
                        **{
                            **exists_mapping[topo_key],
                            "source": source,
                        },
                        updated_at=datetime.now(),
                    )
                )
            else:
                create_instances.append(
                    TopoNode(
                        bk_biz_id=self.bk_biz_id,
                        app_name=self.app_name,
                        topo_key=topo_key,
                        extra_data=TopoNode.get_empty_extra_data(),
                        source=[TelemetryDataType.METRIC.value],
                    )
                )

            found_topo_keys.append(topo_key)

        # 注意与 trace 拓扑发现可能会同时更新 但是这里我们的 source 字段只有往里面添加的情况不会出现脏数据
        TopoNode.objects.bulk_update(update_instances, fields=["source", "updated_at"])
        TopoNode.objects.bulk_create(create_instances)
