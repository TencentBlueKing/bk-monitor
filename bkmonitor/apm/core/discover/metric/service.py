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
from typing import Any

from apm.core.discover.base import combine_list
from apm.core.discover.metric.base import Discover
from apm.models import TopoNode
from constants.apm import TelemetryDataType, CUSTOM_METRICS_PROMQL_FILTER
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
            ).values("id", "topo_key", "source", "system")
        }

    def query_dimensions(self, promql: str, start_time: int, end_time: int) -> list[dict[str, str | None]]:
        query_params: dict[str, Any] = {
            "bk_biz_ids": [self.bk_biz_id],
            "start": start_time,
            "end": end_time,
            "promql": promql,
            "step": f"{end_time - start_time}s",
        }
        logger.info(
            f"[MetricServiceDiscover] ({self.bk_biz_id}:{self.app_name}) query series with params: {query_params}"
        )

        try:
            response: dict[str, Any] = api.unify_query.query_data_by_promql(query_params)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                f"[MetricServiceDiscover] ({self.bk_biz_id}:{self.app_name}) query dimensions failed: "
                f"error -> {e}, promql -> {promql}"
            )
            return []

        return [
            {group_key: item.get("group_values")[index] for index, group_key in enumerate(item["group_keys"])}
            for item in response.get("series", [])
            if item.get("group_keys")
        ]

    @classmethod
    def merge_dimensions(cls, dimensions_list: list[list[dict[str, str | None]]]) -> list[dict[str, str | None]]:
        merged_dimensions: dict[str, dict[str, str | None]] = {}
        for dimensions in dimensions_list:
            for item in dimensions:
                service_name: str | None = item.get("service_name")
                if not service_name:
                    continue
                merged_dimensions.setdefault(service_name, {}).update(item)
        return list(merged_dimensions.values())

    def discover(self, start_time, end_time):
        # 1 - 查询自定义指标中的 service_name 维度。
        custom_metric_promql: str = (
            f'count by (service_name) ({{__name__=~"custom:{self.result_table_id}:.*",{CUSTOM_METRICS_PROMQL_FILTER}}})'
        )
        # 2 - 查询 RPC 指标中的 service_name 和 rpc_system 维度。
        #     相较于上一个实现版本，去掉 target 维度（已由接收端清洗为 service_name），增加 rpc_system 维度（兼容更多 RPC 框架）。
        rpc_metric_promql: str = (
            f"count by (service_name, rpc_system) "
            f'({{__name__=~"custom:{self.result_table_id}:rpc_(client|server)_handled_total"}})'
        )
        dimensions: list[dict[str, str | None]] = self.merge_dimensions(
            [
                self.query_dimensions(custom_metric_promql, start_time, end_time),
                self.query_dimensions(rpc_metric_promql, start_time, end_time),
            ]
        )
        logger.info(f"[MetricServiceDiscover] ({self.bk_biz_id}:{self.app_name}) find {len(dimensions)} dimensions")
        if not dimensions:
            logger.warning(f"[MetricServiceDiscover] ({self.bk_biz_id}:{self.app_name}) no dimensions found, skipped")
            return

        found_topo_keys: set[str] = set()
        to_be_created_topo_nodes: list[TopoNode] = []
        to_be_updated_topo_nodes: list[TopoNode] = []
        exists_mapping: dict[str, dict[str, Any]] = self.list_exists_mapping()
        for item in dimensions:
            topo_key: str | None = item.get("service_name")
            if not topo_key or topo_key in found_topo_keys:
                continue

            system: list[dict[str, Any]] = [
                {"name": "trpc", "extra_data": {"rpc_system": item.get("rpc_system") or ""}}
            ]
            if topo_key in exists_mapping:
                source: list[str] = exists_mapping[topo_key]["source"] or [TelemetryDataType.METRIC.value]
                if TelemetryDataType.METRIC.value not in source:
                    source.append(TelemetryDataType.METRIC.value)

                to_be_updated_topo_nodes.append(
                    TopoNode(
                        bk_biz_id=self.bk_biz_id,
                        app_name=self.app_name,
                        **{
                            **exists_mapping[topo_key],
                            "source": source,
                            "system": combine_list(exists_mapping[topo_key]["system"], system),
                        },
                        updated_at=datetime.now(),
                    )
                )
            else:
                to_be_created_topo_nodes.append(
                    TopoNode(
                        bk_biz_id=self.bk_biz_id,
                        app_name=self.app_name,
                        topo_key=topo_key,
                        extra_data=TopoNode.get_empty_extra_data(),
                        source=[TelemetryDataType.METRIC.value],
                        system=system,
                    )
                )

            found_topo_keys.add(topo_key)

        if to_be_updated_topo_nodes:
            TopoNode.objects.bulk_update(
                to_be_updated_topo_nodes, fields=["source", "system", "updated_at"], batch_size=200
            )
            logger.info(
                f"[MetricServiceDiscover] ({self.bk_biz_id}:{self.app_name}) "
                f"updated {len(to_be_updated_topo_nodes)} topo nodes"
            )

        if to_be_created_topo_nodes:
            TopoNode.objects.bulk_create(to_be_created_topo_nodes, batch_size=200)
            logger.info(
                f"[MetricServiceDiscover] ({self.bk_biz_id}:{self.app_name}) "
                f"creating {len(to_be_created_topo_nodes)} topo nodes"
            )
