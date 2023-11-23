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
from django.db.models import TextChoices
from django.utils.translation import ugettext_lazy as _


class WorkloadType(TextChoices):
    DEPLOYMENT = "deployment", _("deployment")

    SERVICE = "service", _("service")


class DeepflowComp:
    """一些Deepflow的固定值"""

    NAMESPACE = "deepflow"

    # deployment镜像名称
    DEPLOYMENT_SERVER = "deepflow-server"
    DEPLOYMENT_GRAFANA = "grafana"
    DEPLOYMENT_APP = "deepflow-app"

    # service服务名称正则
    SERVICE_SERVER_REGEX = r"^(.*)?deepflow(.*)?-(.*)?server(.*)?$"
    SERVICE_GRAFANA_REGEX = r"^(.*)?deepflow(.*)?-(.*)?grafana(.*)?$"
    SERVICE_APP_REGEX = r"^(.*)?deepflow(.*)?-(.*)?app(.*)?$"

    # service: deepflow-server的查询端口名称
    SERVICE_SERVER_PORT_QUERY = "querier"
    # service: deepflow-app的查询端口名称
    SERVICE_APP_PORT_QUERY = "app"

    # deepflow grafana数据源名称
    GRAFANA_DATASOURCE_TYPE_NAME = "deepflowio-deepflow-datasource"

    @classmethod
    def required_deployments(cls):
        """Deepflow必须的deployment中镜像名称"""
        return [
            cls.DEPLOYMENT_SERVER,
            cls.DEPLOYMENT_GRAFANA,
            cls.DEPLOYMENT_APP,
        ]

    @classmethod
    def required_services(cls):
        """Deepflow必须的service的名称"""
        return [
            cls.SERVICE_SERVER_REGEX,
            cls.SERVICE_GRAFANA_REGEX,
            cls.SERVICE_APP_REGEX,
        ]


# tap_side
TAP_SIDE_UNKNOWN = ""
TAP_SIDE_CLIENT_PROCESS = "c-p"
TAP_SIDE_CLIENT_NIC = "c"
TAP_SIDE_CLIENT_POD_NODE = "c-nd"
TAP_SIDE_CLIENT_HYPERVISOR = "c-hv"
TAP_SIDE_CLIENT_GATEWAY_HAPERVISOR = "c-gw-hv"
TAP_SIDE_CLIENT_GATEWAY = "c-gw"
TAP_SIDE_SERVER_GATEWAY = "s-gw"
TAP_SIDE_SERVER_GATEWAY_HAPERVISOR = "s-gw-hv"
TAP_SIDE_SERVER_HYPERVISOR = "s-hv"
TAP_SIDE_SERVER_POD_NODE = "s-nd"
TAP_SIDE_SERVER_NIC = "s"
TAP_SIDE_SERVER_PROCESS = "s-p"
TAP_SIDE_REST = "rest"
TAP_SIDE_LOCAL = "local"
TAP_SIDE_RANKS = {
    TAP_SIDE_CLIENT_PROCESS: 1,
    TAP_SIDE_CLIENT_NIC: 2,
    TAP_SIDE_CLIENT_POD_NODE: 3,
    TAP_SIDE_CLIENT_HYPERVISOR: 4,
    TAP_SIDE_CLIENT_GATEWAY_HAPERVISOR: 5,
    TAP_SIDE_CLIENT_GATEWAY: 6,
    TAP_SIDE_SERVER_GATEWAY: 6,  # 由于可能多次穿越网关区域，c-gw和s-gw还需要重排
    TAP_SIDE_SERVER_GATEWAY_HAPERVISOR: 8,
    TAP_SIDE_SERVER_HYPERVISOR: 9,
    TAP_SIDE_SERVER_POD_NODE: 10,
    TAP_SIDE_SERVER_NIC: 11,
    TAP_SIDE_SERVER_PROCESS: 12,
    TAP_SIDE_REST: 13,
    TAP_SIDE_LOCAL: 13,  # rest和local需要就近排列到其他位置上
}

L7_FLOW_TYPE_REQUEST = 0
L7_FLOW_TYPE_RESPONSE = 1
L7_FLOW_TYPE_SESSION = 2

RETURN_FIELDS = (
    # 追踪Meta信息
    "l7_protocol",
    "l7_protocol_str",
    "type",
    "req_tcp_seq",
    "resp_tcp_seq",
    "start_time_us",
    "end_time_us",
    "vtap_id",
    "tap_port",
    "tap_port_name",
    "tap_port_type",
    "syscall_trace_id_request",
    "syscall_trace_id_response",
    "syscall_cap_seq_0",
    "syscall_cap_seq_1",
    "trace_id",
    "span_id",
    "parent_span_id",
    "x_request_id_0",
    "x_request_id_1",
    "_id",
    "flow_id",
    "protocol",
    "version",
    # 资源信息
    "signal_source",
    "process_id_0",
    "process_id_1",
    "tap_side",
    "Enum(tap_side)",
    "subnet_id_0",
    "subnet_0",
    "ip_0",
    "auto_instance_type_0",
    "auto_instance_id_0",
    "auto_instance_0",
    "process_kname_0",
    "subnet_id_1",
    "subnet_1",
    "ip_1",
    "app_service",
    "app_instance",
    "auto_instance_type_1",
    "auto_instance_id_1",
    "auto_instance_1",
    "process_kname_1",
    "auto_service_type_0",
    "auto_service_id_0",
    "auto_service_0",
    "auto_service_type_1",
    "auto_service_id_1",
    "auto_service_1",
    "tap_id",
    "tap",
    # 指标信息
    "response_status",
    "response_duration",
    "response_code",
    "response_exception",
    "response_result",
    "request_type",
    "request_domain",
    "request_resource",
    "request_id",
    "http_proxy_client",
    "endpoint",
)
FIELDS_MAP = {
    "start_time_us": "toUnixTimestamp64Micro(start_time) as start_time_us",
    "end_time_us": "toUnixTimestamp64Micro(end_time) as end_time_us",
    "_id": "toString(_id) as `_id_str`",
}
MERGE_KEYS = [
    "l7_protocol",
    "protocol",
    "version",
    "request_id",
    "http_proxy_client",
    "trace_id",
    "span_id",
    "x_request_id_0",
    "x_request_id_1",
    "l7_protocol_str",
    "endpoint",
]
MERGE_KEY_REQUEST = [
    "l7_protocol",
    "protocol",
    "version",
    "request_id",
    "trace_id",
    "span_id",
    "l7_protocol_str",
    "endpoint",
]
MERGE_KEY_RESPONSE = ["http_proxy_client"]

L7_TRACING_LIMIT = 100
