"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any
from core.drf_resource.base import Resource
from monitor_web.incident.metrics.constants import MetricType,EntityType,MetricName
from monitor_web.incident.metrics.serializers import MetricsSearchSerializer
from monitor_web.incident.metrics.config import get_config_by_index_info
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from core.drf_resource import resource
import threading

origin_requset = {
    "bk_biz_id": 2,
    "metric_type": "node",
    "index_info": {
        "index_type": "entity",    # 节点类型，需要带节点类型和节点name
        "entity_type": "BkNodeHost",
        "entity_name": "bkbase-datahubapi-676596b8b-ft2fk",
        "is_anomaly": True,
        "service_name": "cmdb_apiserver",
        "app_name": "bk_cmdb",
        "bcs_cluster_id": "BCS-K8S-00000",
        "namespace": "blueking|bkbase|bkbase-flink",
        "pod_name": "bk-datalink-transfer-bklog-sz-1-76bc5df79b-m7gzx",
        "container_name": "POD",
        "bk_target_ip": "9.146.100.255",
        "bk_target_cloud_id": 0,
    },
    "start_time": 1754045214,
    "end_time": 1754048814
}


class IncidentMetricsSearchResource(Resource):
    """
    故障告警指标查询接口
    """
    # ==================== 配置常量 ====================

    def __init__(self):
        super().__init__()
        self._response_lock = threading.Lock()

    RequestSerializer = MetricsSearchSerializer

    def perform_request(self, validated_request_data: dict) -> dict:
        metric_type = validated_request_data.get("metric_type")
        bk_biz_id = validated_request_data.get("bk_biz_id")
        base_response = {
            "bk_biz_id": bk_biz_id,
            "metrics": {}
        }
        if metric_type == MetricType.NODE.value:
            return self._query_node_metrics(validated_request_data,base_response)
        elif metric_type == MetricType.EBPF_CALL.value:
            return self._query_ebpf_call_metrics(validated_request_data,base_response)
        else:
            raise ValueError(f"Invalid metric type: {metric_type}")

    def _query_node_metrics(self, validated_request_data: dict,base_response: dict) -> dict:
        """
        查询节点指标
        """
        query_requests = self._build_metrics_query_requests(validated_request_data)
        resp = self._execute_query(validated_request_data, query_requests, base_response)
        return resp
    
    def _query_ebpf_call_metrics(self, validated_request_data: dict,base_response: dict) -> dict:
        """
        查询边指标        
        """
        pass
        
    def _execute_query(self, validated_request_data: dict,query_requests: dict,base_response: dict) -> dict:
        """
        执行指标查询
        """
        print(query_requests)
        metric_type = validated_request_data.get("metric_type")
        metric_query_response = base_response
        
        def _aggregation(req_data: dict[str, Any],metric_name: str):
            print(req_data)
            unify_query_resp = resource.grafana.graph_unify_query(req_data)
            with self._response_lock:
                self._format_metrics_response(unify_query_resp, metric_query_response, metric_name, metric_type=metric_type)

        run_threads(
            [InheritParentThread(target=_aggregation, args=(req, metric_name)) for metric_name, req in query_requests.items()]
        )

        return metric_query_response
    
    def _build_metrics_query_requests(self, validated_request_data: dict) -> dict:
        """
        构建指标查询请求(key为指标名称,value为查询请求)
        """
        index_info: dict[str, Any] = validated_request_data.get("index_info")
        entity_type: str = index_info.get("entity_type")
        start_time: int = validated_request_data.get("start_time")
        end_time: int = validated_request_data.get("end_time")
        bk_biz_id: int = validated_request_data.get("bk_biz_id")
        service_name: str = index_info.get("service_name")
        app_name: str = index_info.get("app_name")
        
        table_extra_params = {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
        }
        table: str = self._get_tables_by_entity_type(entity_type, **table_extra_params)
        
        config_extra_params = {
            "start_time": start_time,
            "end_time": end_time,
            "bk_biz_id": bk_biz_id,
            "service_name": service_name,
            "app_name": app_name,
            "table": table,
        }
        query_requests = get_config_by_index_info(index_info,**config_extra_params)
        return query_requests
    
    def _get_tables_by_entity_type(self, entity_type: str, **kwargs) -> str:
        """
        根据实体类型获取对应的table名集合
        """

        table_getters = {
            EntityType.BcsPod.value: self._get_bcs_pod_tables,
            EntityType.APMService.value: self._get_apm_service_table,
            EntityType.BkNodeHost.value: self._get_bk_node_host_tables,
        }

        getter = table_getters.get(entity_type)
        return getter(**kwargs) if getter else ""
    
    def _get_apm_service_table(self, **kwargs) -> str:
        """
        获取APMService类型的表名
        """
        app_name = kwargs.get("app_name","")
        bk_biz_id = kwargs.get("bk_biz_id",0)
        if not app_name or not bk_biz_id:
            return ""
        
        return f"{bk_biz_id}_bkapm_metric_{app_name}.__default__"
        
        
    def _get_bcs_pod_tables(self, **kwargs) -> str:
        """
        获取BcsPod类型的表名
        """
        pass
    
    def _get_bk_node_host_tables(self, **kwargs) -> str:
        """
        获取BKNodeHost类型的表名
        """
        pass
    
    def _format_metrics_response(self, unify_query_resp: dict[str, Any], metric_query_response: dict[str, Any], metric_name: str, **kwargs):
        """
        格式化指标查询响应
        """
        metric_info = {
            "metric_name": metric_name,
            "metric_alias": MetricName(metric_name).label,
            "metric_type": kwargs.get("metric_type"),
        }
        for series in unify_query_resp.get("series",[]):
            metric_info["time_series"] = [[datapoint[1],datapoint[0]] for datapoint in series.get("datapoints",[])]
        metric_query_response["metrics"][metric_name] = metric_info