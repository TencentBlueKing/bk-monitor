"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time
from datetime import datetime
from typing import Any

from django.conf import settings

from apm.core.discover.base import combine_list
from apm.core.discover.metric.base import Discover
from apm.models import TopoNode
from constants.apm import TelemetryDataType, CUSTOM_METRICS_PROMQL_FILTER, TraceMetric
from core.drf_resource import api

logger = logging.getLogger(__name__)


class ServiceDiscover(Discover):
    """从指标中发现服务"""

    # 由任务入口按此粒度切分查询窗口（秒）。
    SPLIT_SECONDS: int = settings.APM_APPLICATION_METRIC_DISCOVER_SPLIT_DELTA

    def list_exists_mapping(self):
        return {
            i["topo_key"]: i
            for i in TopoNode.objects.filter(
                bk_biz_id=self.bk_biz_id,
                app_name=self.app_name,
            ).values("id", "topo_key", "source", "system")
        }

    def query_dimensions(
        self, promql: str, start_time: int, end_time: int, with_last_data_at: bool = False
    ) -> list[dict[str, Any]]:
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

        dimensions: list[dict[str, Any]] = []
        for item in response.get("series", []):
            if not item.get("group_keys"):
                continue
            dimension: dict[str, Any] = dict(zip(item["group_keys"], item["group_values"]))
            if with_last_data_at:
                value_index: int = item["columns"].index("_value")
                points: list[float] = [point[value_index] for point in item["values"] if point[value_index] is not None]
                dimension["last_data_at"] = int(max(points)) if points else None
            dimensions.append(dimension)
        return dimensions

    def discover(self, start_time: int, end_time: int) -> None:
        self.discover_services(start_time, end_time)
        self.discover_heartbeat(start_time, end_time)

    def discover_heartbeat(self, start_time: int, end_time: int) -> None:
        """一次查询四个维度，按服务键合并最大的秒级样本时间。

        timestamp() 的返回值是样本时间，_time 是求值时间，不用于心跳。
        仅更新观测节点的指标心跳，并为组件、远程服务补写 Trace 心跳。
        """
        observed: dict[str, int] = {}
        trace_observed: dict[str, int] = {}
        metric_table: str = self.result_table_id.replace(".", ":")
        promql = (
            "max by (service_name, db_system, messaging_system, peer_service) "
            f'(timestamp({{__name__="custom:{metric_table}:{TraceMetric.BK_APM_COUNT}"}}))'
        )
        for dimensions in self.query_dimensions(promql, start_time, end_time, with_last_data_at=True):
            timestamp: int | None = dimensions["last_data_at"]
            if timestamp is None:
                continue
            service_name: str | None = dimensions.get("service_name")
            if service_name:
                observed[service_name] = max(observed.get(service_name, 0), timestamp)
                for field in ("db_system", "messaging_system"):
                    if component := dimensions.get(field):
                        key = f"{service_name}-{component}"
                        trace_observed[key] = max(trace_observed.get(key, 0), timestamp)
            if peer := dimensions.get("peer_service"):
                key = f"http:{peer}"
                trace_observed[key] = max(trace_observed.get(key, 0), timestamp)
        for key, timestamp in trace_observed.items():
            observed[key] = max(observed.get(key, 0), timestamp)
        checked_at: int = int(time.time())
        TopoNode.touch_heartbeat(self.bk_biz_id, self.app_name, TelemetryDataType.METRIC.value, observed, checked_at)
        # 组件及远程服务的 bk_apm_count 来自 Span，只补写这些节点的 Trace 心跳。
        TopoNode.touch_heartbeat(
            self.bk_biz_id, self.app_name, TelemetryDataType.TRACE.value, trace_observed, checked_at
        )

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

    def discover_services(self, start_time: int, end_time: int) -> None:
        # 1 - 查询自定义指标中的 service_name 和 rpc_system 维度。
        custom_metric_promql: str = (
            f"count by (service_name, rpc_system) "
            f'({{__name__=~"custom:{self.result_table_id}:.*",{CUSTOM_METRICS_PROMQL_FILTER}}})'
        )
        # 2 - 查询 RPC 指标中的 service_name 和 rpc_system 维度。
        #     相较于上一个实现版本，去掉 target 维度（已由接收端清洗为 service_name），增加 rpc_system 维度（兼容更多 RPC 框架）。
        rpc_metric_promql: str = (
            f"count by (service_name, rpc_system) "
            f'({{__name__=~"custom:{self.result_table_id}:rpc_(client|server)_handled_total"}})'
        )

        # 根据自定义指标发现服务
        custom_metric_services: list[dict[str, str | None]] = self.query_dimensions(
            custom_metric_promql, start_time, end_time
        )
        # 根据调用分析指标发现服务
        rpc_services: list[dict[str, bool | str | None]] = [
            {**service, "is_rpc": True} for service in self.query_dimensions(rpc_metric_promql, start_time, end_time)
        ]
        services: list[dict[str, str | None]] = self.merge_dimensions([custom_metric_services, rpc_services])
        logger.info(f"[MetricServiceDiscover] ({self.bk_biz_id}:{self.app_name}) find {len(services)} services")
        if not services:
            logger.warning(f"[MetricServiceDiscover] ({self.bk_biz_id}:{self.app_name}) no service found, skipped")
            return

        found_topo_keys: set[str] = set()
        to_be_created_topo_nodes: list[TopoNode] = []
        to_be_updated_topo_nodes: list[TopoNode] = []
        exists_mapping: dict[str, dict[str, Any]] = self.list_exists_mapping()
        for service in services:
            topo_key: str | None = service.get("service_name")
            if not topo_key or topo_key in found_topo_keys:
                continue

            system: list[dict[str, Any]] = []
            rpc_system: str | None = service.get("rpc_system")
            # 如何确定一个服务是否为 RPC（tRPC 或其他）类型？
            # - 通过调用分析指标发现。
            # - 自定义指标携带 rpc_system 维度。
            is_rpc: bool = bool(rpc_system) or service.get("is_rpc", False)
            if is_rpc:
                # 标记为 RPC 服务时，才设置 system。
                system.append({"name": "trpc", "extra_data": {}})
            if rpc_system:
                # 如果存在 rpc_system，才添加到 system 中，避免空值覆盖有值。
                system[0]["extra_data"]["rpc_system"] = rpc_system

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
