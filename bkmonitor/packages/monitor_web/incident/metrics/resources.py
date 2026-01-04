"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any
from core.drf_resource.base import Resource
from monitor_web.incident.metrics.constants import MetricType, EntityType, MetricName, MetricUnit
from monitor_web.incident.metrics.serializers import MetricsSearchSerializer
from monitor_web.incident.metrics.metric_config import get_apm_config, get_bcs_config, get_host_config
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from core.drf_resource import resource
import threading
import abc
from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode
from bkmonitor.utils.request import get_request_username
from core.drf_resource.exceptions import record_exception


class BaseIncidentMetricsResource(Resource, abc.ABC):
    """
    故障告警指标查询接口
    """

    @abc.abstractmethod
    def _perform_request(self, validated_request_data: dict[str, Any]):
        pass

    def perform_request(self, validated_request_data: dict[str, Any]):
        try:
            return self._perform_request(validated_request_data)
        except Exception as exc:
            span = trace.get_current_span()
            span.set_attribute("user.username", get_request_username())
            span.set_status(
                Status(
                    status_code=StatusCode.ERROR,
                    description=f"{type(exc).__name__}: {exc}",
                )
            )
            record_exception(span, exc, out_limit=10)
            return {}

    # 明确定义的度量单位映射，便于扩展
    UNIT_BY_METRIC = {
        # 内存量（bytes）
        MetricName.BCS_PERFORMANCE_MEMORY_USAGE.value: MetricUnit.BYTES,
        MetricName.HOST_MEM_PHYSICAL_FREE.value: MetricUnit.BYTES,
        # 使用率（percent）
        MetricName.APM_ERROR_RATE.value: MetricUnit.PERCENT_UNIT,
        MetricName.BCS_PERFORMANCE_CPU_REQUEST_USAGE_RATE.value: MetricUnit.PERCENT_UNIT,
        MetricName.BCS_PERFORMANCE_CPU_LIMIT_USAGE_RATE.value: MetricUnit.PERCENT_UNIT,
        MetricName.BCS_PERFORMANCE_MEMORY_REQUEST_USAGE_RATE.value: MetricUnit.PERCENT_UNIT,
        MetricName.BCS_PERFORMANCE_MEMORY_LIMIT_USAGE_RATE.value: MetricUnit.PERCENT_UNIT,
        MetricName.HOST_CPU_USAGE_RATE.value: MetricUnit.PERCENT_UNIT,
        MetricName.HOST_DISK_USAGE_RATE.value: MetricUnit.PERCENT_UNIT,
        # 流量带宽（Bps）
        MetricName.BCS_TRAFFIC_IN.value: MetricUnit.BPS,
        MetricName.BCS_TRAFFIC_OUT.value: MetricUnit.BPS,
        MetricName.HOST_NIC_IN_RATE.value: MetricUnit.BPS,
        MetricName.HOST_NIC_OUT_RATE.value: MetricUnit.BPS,
        # 耗时
        MetricName.APM_DURATION.value: MetricUnit.NANOSECONDS,
    }

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()

    def get_tables_by_entity_type(self, entity_type: str, **kwargs) -> str:
        """
        根据实体类型获取对应的table名集合
        """

        table_getters = {
            EntityType.BcsPod.value: self.get_bcs_pod_tables,
            EntityType.APMService.value: self.get_apm_service_table,
            EntityType.BkNodeHost.value: self.get_bk_node_host_tables,
        }

        getter = table_getters.get(entity_type)
        return getter(**kwargs) if getter else ""

    def get_apm_service_table(self, **kwargs) -> str:
        """
        获取APMService类型的表名
        """
        app_name = kwargs.get("apm_application_name", "")
        bk_biz_id = kwargs.get("bk_biz_id", 0)
        if not app_name or not bk_biz_id:
            return ""

        return f"{bk_biz_id}_bkapm_metric_{app_name}.__default__"

    def get_bcs_pod_tables(self, **kwargs) -> str:
        """
        获取BcsPod类型的表名
        """
        return ""

    def get_bk_node_host_tables(self, **kwargs) -> str:
        """
        获取BKNodeHost类型的表名
        """
        return ""


class IncidentMetricsSearchResource(BaseIncidentMetricsResource):
    """
    故障告警指标查询接口
    """

    # ==================== 配置常量 ====================

    def __init__(self):
        super().__init__()

    RequestSerializer = MetricsSearchSerializer

    def get_config_by_dimensions(self, dimensions: dict[str, Any], **kwargs):
        """根据实体类型获取配置"""
        entity_type = kwargs.get("entity_type")
        config_getters = {
            EntityType.BcsPod.value: get_bcs_config,
            EntityType.APMService.value: get_apm_config,
            EntityType.BkNodeHost.value: get_host_config,
        }

        getter = config_getters.get(entity_type)
        return getter(dimensions, **kwargs) if getter else {}

    def _perform_request(self, validated_request_data: dict) -> dict:
        metric_type = validated_request_data.get("metric_type")
        bk_biz_id = validated_request_data.get("bk_biz_id")
        base_response = {"bk_biz_id": bk_biz_id, "metrics": {}}
        if metric_type == MetricType.NODE.value:
            return self.query_node_metrics(validated_request_data, base_response)
        elif metric_type == MetricType.EBPF_CALL.value or metric_type == MetricType.DEPENDENCY.value:
            return self.query_edge_metrics(validated_request_data, base_response)

    def query_node_metrics(self, validated_request_data: dict, base_response: dict) -> dict:
        """
        查询节点指标
        """
        query_requests = self.build_metrics_query_requests(validated_request_data)
        resp = self.execute_query(validated_request_data, query_requests, base_response)
        return resp

    def query_edge_metrics(self, validated_request_data: dict, base_response: dict) -> dict:
        """
        查询边指标
        """
        return base_response

    def execute_query(self, validated_request_data: dict, query_requests: dict, base_response: dict) -> dict:
        """
        执行指标查询
        """
        if not query_requests:
            return base_response
        metric_type = validated_request_data.get("metric_type")
        metric_query_response = base_response

        def _aggregation(req_data: dict[str, Any], metric_name: str, dimension_type: str):
            unify_query_resp = resource.grafana.graph_unify_query(req_data)
            with self._lock:
                self.format_metrics_response(
                    unify_query_resp,
                    metric_query_response,
                    metric_name,
                    dimension_type=dimension_type,
                    metric_type=metric_type,
                )

        for metric_name, req_dict in query_requests.items():
            for dimension_type, req_data in req_dict.items():
                run_threads([InheritParentThread(target=_aggregation, args=(req_data, metric_name, dimension_type))])

        return metric_query_response

    def build_metrics_query_requests(self, validated_request_data: dict) -> dict:
        """
        构建指标查询请求(key为指标名称,value为查询请求)
        """
        index_info: dict[str, Any] = validated_request_data.get("index_info")
        entity_type: str = index_info.get("entity_type")
        start_time: int = validated_request_data.get("start_time")
        end_time: int = validated_request_data.get("end_time")
        bk_biz_id: int = validated_request_data.get("bk_biz_id")
        interval: int = validated_request_data.get("interval", 3600)
        dimensions: dict[str, Any] = index_info.get("dimensions", {})
        app_name: str = dimensions.get("apm_application_name", "")

        table_extra_params = {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
        }
        table: str = self.get_tables_by_entity_type(entity_type, **table_extra_params)

        config_extra_params = {
            "start_time": start_time,
            "end_time": end_time,
            "bk_biz_id": bk_biz_id,
            "table": table,
            "entity_type": entity_type,
            "interval": interval,
        }
        query_requests = self.get_config_by_dimensions(dimensions, **config_extra_params)
        return query_requests

    def format_metrics_response(
        self, unify_query_resp: dict[str, Any], metric_query_response: dict[str, Any], metric_name: str, **kwargs
    ):
        """
        格式化指标查询响应
        """
        # 初始化或获取metric_info
        metric_info = metric_query_response["metrics"].get(metric_name)
        if not metric_info:
            metric_info = {
                "metric_name": metric_name,
                "metric_alias": MetricName(metric_name).label,
                "metric_type": kwargs.get("metric_type"),
                "time_series": {},
                "display_by_dimensions": False,
            }
            metric_query_response["metrics"][metric_name] = metric_info

        for series in unify_query_resp.get("series", []):
            current_dimension_type = kwargs.get("dimension_type")
            if "dimensions" in series and series["dimensions"]:
                current_dimension_type = next(iter(series["dimensions"].values()))
                metric_info["display_by_dimensions"] = True

            # 当 unit 为空时，按规则填充：内存量=bytes；使用率=percentunit；流量带宽=Bps
            unit = series.get("unit", "")
            if unit == "":
                series["unit"] = self.UNIT_BY_METRIC.get(metric_name, "")
            # 将 datapoints 中的时间戳和值交换位置， 适配格式
            series["datapoints"] = [[datapoint[1], datapoint[0]] for datapoint in series.get("datapoints", [])]
            metric_info["time_series"][current_dimension_type] = series

        if len(metric_info["time_series"]) > 1:
            metric_info["display_by_dimensions"] = True
