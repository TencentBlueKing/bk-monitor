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
import math
import time
from typing import Any

import arrow
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone

from apm.core.discover.base import combine_list
from apm.core.discover.metric.base import Discover
from apm.core.discover.exceptions import IncompleteDiscoveryError
from apm.models import TopoNode
from constants.apm import TelemetryDataType, CUSTOM_METRICS_PROMQL_FILTER, TraceMetric
from core.drf_resource import api

logger = logging.getLogger(__name__)


class ServiceDiscover(Discover):
    """从指标中发现服务"""

    def list_exists_mapping(self) -> dict[str, dict[str, Any]]:
        return {
            i["topo_key"]: i
            for i in TopoNode.objects.filter(
                bk_biz_id=self.bk_biz_id,
                app_name=self.app_name,
            ).values("id", "topo_key", "source", "system")
        }

    def query_series(self, promql: str, start_time: int, end_time: int) -> list[dict[str, Any]]:
        response: dict[str, Any] = api.unify_query.query_data_by_promql(
            {
                "bk_biz_ids": [self.bk_biz_id],
                "start": start_time,
                "end": end_time,
                "promql": promql,
                "step": "60s",
            }
        )
        status: dict[str, Any] = response.get("status") or {}
        if response.get("is_partial") or status.get("is_partial") or status.get("series_limit_reached"):
            raise IncompleteDiscoveryError("incomplete metric discovery result")
        return response["series"]

    def query_dimensions(self, promql: str, start_time: int, end_time: int) -> list[dict[str, str | None]]:
        try:
            series: list[dict[str, Any]] = self.query_series(promql, start_time, end_time)
        except SoftTimeLimitExceeded:
            raise
        except Exception:
            logger.exception(
                "[MetricServiceDiscover] query failed: bk_biz_id=%s app_name=%s", self.bk_biz_id, self.app_name
            )
            return []
        return [dict(zip(item["group_keys"], item["group_values"])) for item in series if item.get("group_keys")]

    def discover(self, start_time: int, end_time: int) -> None:
        split_seconds: int = settings.APM_APPLICATION_METRIC_DISCOVER_SPLIT_DELTA
        for start in range(start_time, end_time, split_seconds):
            end: int = min(start + split_seconds, end_time)
            self.discover_services(start, end)
        try:
            self.discover_heartbeat(start_time, end_time)
        except SoftTimeLimitExceeded:
            raise
        except Exception:
            logger.exception(
                "[MetricServiceDiscover] heartbeat unchanged: bk_biz_id=%s app_name=%s start=%s end=%s",
                self.bk_biz_id,
                self.app_name,
                start_time,
                end_time,
            )

    def discover_heartbeat(self, start_time: int, end_time: int) -> None:
        observed: dict[str, int | None] = {}
        groups: tuple[tuple[str, ...], ...] = (
            ("service_name",),
            ("service_name", "db_system"),
            ("service_name", "messaging_system"),
            ("peer_service",),
        )
        metric_table: str = self.result_table_id.replace(".", ":")
        for group in groups:
            promql: str = (
                f'sum by ({", ".join(group)}) ({{__name__="custom:{metric_table}:{TraceMetric.BK_APM_COUNT}"}})'
            )
            for series in self.query_series(promql, start_time, end_time):
                dimensions: dict[str, str] = dict(zip(series["group_keys"], series["group_values"]))
                name: str = dimensions.get(group[0]) or ""
                if not name:
                    continue
                if len(group) == 2:
                    component: str = dimensions.get(group[1]) or ""
                    if not component:
                        continue
                    name = f"{name}-{component}"
                elif group == ("peer_service",):
                    name = f"http:{name}"

                columns: list[str] = series["columns"]
                time_index: int = columns.index("_time")
                value_index: int = columns.index("_value" if "_value" in columns else "_result")
                for point in series["values"]:
                    # 零值仍是有效数据；只采用查询窗口内的有效序列点时间。
                    if point[value_index] is None or not math.isfinite(float(point[value_index])):
                        continue
                    raw_time: int | float | str = point[time_index]
                    if isinstance(raw_time, int | float):
                        # UQ 兼容秒级与毫秒级数值时间，字符串按其时区解析。
                        timestamp: int = int(raw_time / 1000 if raw_time >= 100_000_000_000 else raw_time)
                    else:
                        timestamp = int(arrow.get(raw_time).float_timestamp)
                    if start_time <= timestamp <= end_time:
                        observed[name] = max(observed.get(name) or 0, timestamp)

        # 四路查询全部成功后，统一入口按应用检查全部现存节点，无需先枚举服务名。
        TopoNode.touch_heartbeat(
            self.bk_biz_id,
            self.app_name,
            TelemetryDataType.METRIC.value,
            observed,
            int(time.time()),
            check_all_services=True,
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
        promoted_node_ids: list[int] = []
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
                existing: dict[str, Any] = exists_mapping[topo_key]
                if not TopoNode.has_trace_or_metric_source(existing["source"]):
                    promoted_node_ids.append(existing["id"])
                source: list[str] = existing["source"] or [TelemetryDataType.METRIC.value]
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
                        updated_at=timezone.now(),
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

        if promoted_node_ids:
            # 只提升仍属于新来源的节点，避免覆盖期间由 Trace 写入的分类。
            TopoNode.objects.filter(TopoNode.new_source_filter(), id__in=promoted_node_ids).update(
                extra_data=TopoNode.get_empty_extra_data()
            )

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
