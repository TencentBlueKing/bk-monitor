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
import random
import time

import arrow
from django.conf import settings

from apm.core.deepflow.constants import (
    L7_PROTOCOL_DNS,
    L7_PROTOCOL_DUBBO,
    L7_PROTOCOL_GRPC,
    L7_PROTOCOL_HTTP_1,
    L7_PROTOCOL_HTTP_1_TLS,
    L7_PROTOCOL_HTTP_2,
    L7_PROTOCOL_HTTP_2_TLS,
    L7_PROTOCOL_KAFKA,
    L7_PROTOCOL_MQTT,
    L7_PROTOCOL_MYSQL,
    L7_PROTOCOL_POSTGRE,
    L7_PROTOCOL_REDIS,
)
from apm_web.constants import EbpfSignalSourceType, EbpfTapSideType
from constants.apm import SpanKind

logger = logging.getLogger("apm")


class Span:
    def __init__(self):
        self.attributes = {}
        self.kind = 0
        self.parent_span_id = ""
        self.resource = {}
        self.status = {}
        self.span_id = ""
        self.trace_id = ""
        self.span_name = ""
        self.elapsed_time = 0
        self.start_time = 0
        self.end_time = 0
        self.trace_state = ""
        self.time = 0
        self.links = []
        self.events = []

    def set_name(self, name):
        self.span_name = name

    def span_to_dict(self):
        return {
            "attributes": self.attributes,
            "kind": self.kind,
            "parent_span_id": self.parent_span_id,
            "resource": self.resource,
            "status": self.status,
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "span_name": self.span_name,
            "elapsed_time": self.elapsed_time,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "trace_state": self.trace_state,
            "time": int(time.time() * 1000),
            "links": self.links,
            "events": self.events,
        }


class EBPFHandler:
    @classmethod
    def str_time_to_unit_time(cls, str_time: str):
        """
        字符串时间 --> 时间戳, 单位 us
        """
        t = arrow.get(str_time).replace(tzinfo=settings.TIME_ZONE)
        return int(t.float_timestamp * 1000 * 1000)

    @classmethod
    def response_status_to_span_status_message(cls, status: int):
        switcher = {
            0: "Success",
            2: "Unknown",
            1: "Error",
            3: "Server Error",
            4: "client Error",
        }

        return switcher.get(status, "")

    @classmethod
    def response_status_to_span_status_code(cls, status: int):
        switcher = {
            0: 1,
            2: 0,
            1: 2,
            3: 2,
            4: 2,
        }

        return switcher.get(status, 0)

    @classmethod
    def merge_value_to_attrs_map(cls, attrs: dict, value):
        if isinstance(value, str):
            try:
                tem_value = json.loads(value)
                if isinstance(tem_value, dict):
                    attrs.update(tem_value)
            except Exception as e:
                logger.info("merge_value_to_attrs_map, value: {}, exception: {}".format(value, e))

    @classmethod
    def put_bool_value_to_map(cls, attrs: dict, key: str, value):
        if value:
            attrs[key] = True
        attrs[key] = False

    @classmethod
    def put_value_map(cls, attrs: dict, key: str, value):
        if value is not None:
            attrs[key] = value

    @classmethod
    def get_sql_span_name_and_operation(cls, sql: str):
        sql = sql.strip()
        parts = sql.split()
        if len(parts) >= 1:
            return parts[0].upper(), parts[0].upper()
        return "unknown", ""

    @classmethod
    def set_dns(cls, span: Span, span_attrs: dict, item: dict):
        cls.put_value_map(span_attrs, "df.dns.request_type", item.get("request_type"))
        cls.put_value_map(span_attrs, "df.dns.request_resource", item.get("request_resource"))
        if item.get("request_id") is not None:
            span_attrs["df.global.request_id"] = int(item.get("request_id"))

        span_attrs["df.dns.response_status"] = str(item.get("response_status"))
        if item.get("response_code") is not None:
            span_attrs["df.dns.response_code"] = int(item.get("response_code"))

        if item.get("response_exception"):
            span.status["message"] = item.get("response_exception")

        if item.get("response_result") is not None:
            span_attrs["df.dns.response_result"] = item.get("response_result")

    @classmethod
    def set_http(cls, span: Span, span_attrs: dict, item: dict):
        cls.put_value_map(span_attrs, "http.flavor", item.get("version"))
        cls.put_value_map(span_attrs, "http.method", item.get("request_type"))
        cls.put_value_map(span_attrs, "net.peer.name", item.get("request_domain"))
        cls.put_value_map(span_attrs, "df.http.path", item.get("request_resource"))
        cls.put_value_map(span_attrs, "df.http.proxy_client", item.get("http_proxy_client"))

        if item.get("request_id") is not None:
            span_attrs["df.global.request_id"] = int(item.get("request_id"))

        if item.get("response_code") is not None:
            span_attrs["http.status_code"] = int(item.get("response_code"))

        if item.get("response_exception"):
            span.status["message"] = item.get("response_exception")
        if item.get("request_type") and item.get("l7_protocol_str"):
            span.span_name = " ".join([item.get("l7_protocol_str"), item.get("request_type")])

    @classmethod
    def set_dubbo(cls, span: Span, span_attrs: dict, item: dict):
        span_attrs["rpc.system"] = "apache_dubbo"
        cls.put_value_map(span_attrs, "rpc.service", item.get("request_resource"))
        cls.put_value_map(span_attrs, "rpc.method", item.get("request_type"))
        if item.get("request_type") and item.get("request_resource"):
            span.span_name = "/".join([item.get("request_resource"), item.get("request_type")])

        if item.get("response_exception"):
            span.status["message"] = item.get("response_exception")

        cls.put_value_map(span_attrs, "df.request_domain", item.get("request_domain"))
        cls.put_value_map(span_attrs, "df.dubbo.version", item.get("version"))

        if item.get("request_id") is not None:
            span_attrs["df.global.request_id"] = int(item.get("request_id"))

        if item.get("response_code") is not None:
            span_attrs["df.response_code"] = int(*item.get("response_code"))

    @classmethod
    def set_grpc(cls, span: Span, span_attrs: dict, item: dict):
        span_attrs["rpc.system"] = "grpc"
        cls.put_value_map(span_attrs, "rpc.service", item.get("request_resource"))
        cls.put_value_map(span_attrs, "rpc.method", item.get("request_type"))

        cls.put_value_map(span_attrs, "http.flavor", item.get("version"))
        cls.put_value_map(span_attrs, "df.request_domain", item.get("request_domain"))
        if item.get("request_id") is not None:
            span_attrs["df.global.request_id"] = int(*item.get("request_id"))

        if item.get("request_type") is not None and item.get("request_resource") is not None:
            span.span_name = "/".join([item.get("request_resource"), item.get("request_type")])

        if item.get("response_exception"):
            span.status["message"] = item.get("response_exception")

    @classmethod
    def set_kafka(cls, span: Span, span_attrs: dict, item: dict):
        span_attrs["messaging.system"] = "kafka"
        span.set_name(item.get("request_resource"))

        cls.put_value_map(span_attrs, "df.kafka.request_type", item.get("request_type"))
        if item.get("request_id") is not None:
            span_attrs["df.global.request_id"] = int(item.get("request_id"))

        cls.put_value_map(span_attrs, "df.global.request_resource", item.get("request_resource"))
        cls.put_value_map(span_attrs, "df.kafka.request_domain", item.get("request_domain"))
        if item.get("response_code") is not None:
            span_attrs["df.kafka.response_code"] = item.get("response_code")

        if item.get("response_exception"):
            span.status["message"] = item.get("response_exception")

    @classmethod
    def set_mqtt(cls, span: Span, span_attrs: dict, item: dict):
        span_attrs["messaging.system"] = "mqtt"
        span.set_name(item.get("request_resource"))

        cls.put_value_map(span_attrs, "df.mqtt.request_type", item.get("request_type"))
        cls.put_value_map(span_attrs, "df.mqtt.request_resource", item.get("request_resource"))
        cls.put_value_map(span_attrs, "df.mqtt.request_domain", item.get("request_domain"))
        if item.get("response_code") is not None:
            span_attrs["df.mqtt.response_code"] = item.get("response_code")

        if item.get("response_exception"):
            span.status["message"] = item.get("response_exception")

    @classmethod
    def set_mysql(cls, span: Span, span_attrs: dict, item: dict):
        span_name, operation = cls.get_sql_span_name_and_operation(item.get("request_resource"))
        cls.put_value_map(span_attrs, "db.system", "mysql")
        cls.put_value_map(span_attrs, "db.operation", operation)
        cls.put_value_map(span_attrs, "db.statement", item.get("request_resource"))
        cls.put_value_map(span_attrs, "df.mysql.request_type", item.get("request_type"))
        if item.get("response_exception"):
            span.status["message"] = item.get("response_exception")

        span.set_name(span_name)

    @classmethod
    def set_postgresql(cls, span: Span, span_attrs: dict, item: dict):
        span_name, operation = cls.get_sql_span_name_and_operation(item.get("request_resource"))
        cls.put_value_map(span_attrs, "db.system", "postgresql")
        cls.put_value_map(span_attrs, "db.operation", operation)
        cls.put_value_map(span_attrs, "db.statement", item.get("request_resource"))
        cls.put_value_map(span_attrs, "df.postgresql.request_type", item.get("request_type"))
        if item.get("response_exception"):
            span.status["message"] = item.get("response_exception")

        span.set_name(span_name)

    @classmethod
    def set_redis(cls, span: Span, span_attrs: dict, item: dict):
        cls.put_value_map(span_attrs, "db.system", "redis")
        cls.put_value_map(span_attrs, "db.operation", item.get("request_type"))
        cls.put_value_map(span_attrs, "db.statement", item.get("request_resource"))
        if item.get("response_exception"):
            span.status["message"] = item.get("response_exception")

        span.set_name(item.get("request_type"))

    @classmethod
    def is_client_side(cls, tap_side: str):
        return tap_side.startswith("c")

    @classmethod
    def is_server_side(cls, tap_side: str):
        return tap_side.startswith("s")

    @classmethod
    def tap_side_to_span_kind(cls, tap_side):
        if cls.is_client_side(tap_side):
            return SpanKind.SPAN_KIND_CLIENT
        elif cls.is_server_side(tap_side):
            return SpanKind.SPAN_KIND_SERVER
        return SpanKind.SPAN_KIND_UNSPECIFIED

    @classmethod
    def signal_source_to_string(cls, signal_source: int):
        switcher = {
            0: EbpfSignalSourceType.SIGNAL_SOURCE_PACKET,
            1: EbpfSignalSourceType.SIGNAL_SOURCE_XFLOW,
            3: EbpfSignalSourceType.SIGNAL_SOURCE_EBPF,
            4: EbpfSignalSourceType.SIGNAL_SOURCE_OTEL,
        }

        return switcher.get(signal_source)

    @classmethod
    def tap_side_to_name(cls, tap_side: str):
        switcher = {
            "c": EbpfTapSideType.CLIENT_NIC,
            "c-nd": EbpfTapSideType.CLIENT_K8S_NODE,
            "c-hv": EbpfTapSideType.CLIENT_VM_HYPERVISOR,
            "c-gw-hv": EbpfTapSideType.CLIENT_SIDE_GATEWAY_HYPERVISOR,
            "c-gw": EbpfTapSideType.CLIENT_SIDE_GATEWAY,
            "local": EbpfTapSideType.LOCAL_NIC,
            "rest": EbpfTapSideType.OTHER_NIC,
            "s-gw": EbpfTapSideType.SERVER_SIDE_GATEWAY,
            "s-gw-hv": EbpfTapSideType.SERVER_SIDE_GATEWAY_HYPERVISOR,
            "s-hv": EbpfTapSideType.SERVER_VM_HYPERVISOR,
            "s-nd": EbpfTapSideType.SERVER_K8S_NODE,
            "s": EbpfTapSideType.SERVER_NIC,
            "c-p": EbpfTapSideType.CLIENT_PROCESS,
            "s-p": EbpfTapSideType.SERVER_PROCESS,
            "c-app": EbpfTapSideType.CLIENT_APPLICATION,
            "s-app": EbpfTapSideType.SERVER_APPLICATION,
            "app": EbpfTapSideType.APPLICATION,
        }

        return switcher.get(tap_side)

    @classmethod
    def tap_port_type_to_string(cls, tap_port_type: int):
        switcher = {
            0: "Local NIC",
            1: "NFV Gateway NIC",
            2: "ERSPAN",
            3: "ERSPAN (IPv6)",
            4: "Traffic Mirror",
            5: "NetFlow",
            6: "sFlow",
            7: "eBPF",
            8: "OTel",
        }

        return switcher.get(tap_port_type)

    @classmethod
    def new_span_id(cls):
        return ''.join(random.choice('0123456789abcdef') for _ in range(16))

    @classmethod
    def l7_flow_log_to_resource_span(cls, item: dict):

        span = Span()
        span_attrs = span.attributes
        span_resource = span.resource
        status = span.status
        span.trace_id = item.get("trace_id")
        signal_source = cls.signal_source_to_string(item.get("signal_source"))

        # 将ebpf的span_id作为parent_span_id，都挂到上一层应用span下
        # 自身的span_id则重新生成
        span_id = item.get("span_id")
        parent_span_id = item.get("parent_span_id")
        if signal_source == EbpfSignalSourceType.SIGNAL_SOURCE_OTEL:
            # 如果是OTEL应用层的span，保留父子关系
            span.parent_span_id = parent_span_id
            span.span_id = span_id
        else:
            span.parent_span_id = span_id
            span.span_id = cls.new_span_id()

        if item.get("start_time_us"):
            span.start_time = item.get("start_time_us")

        if item.get("end_time_us"):
            span.end_time = item.get("start_time_us")

        span.kind = cls.tap_side_to_span_kind(item.get("tap_side"))

        # attribute
        if item.get("attribute"):
            cls.merge_value_to_attrs_map(span_attrs, item.get("attribute"))

        # Tracing Info
        cls.put_value_map(span_attrs, "df.span.x_request_id_0", item.get("x_request_id_0"))
        cls.put_value_map(span_attrs, "df.span.x_request_id_1", item.get("x_request_id_1"))

        cls.put_value_map(span_attrs, "df.span.syscall_trace_id_request", item.get("syscall_trace_id_request"))
        cls.put_value_map(span_attrs, "df.span.syscall_trace_id_response", item.get("syscall_trace_id_response", 0))
        cls.put_value_map(span_attrs, "df.span.syscall_thread_0", item.get("syscall_thread_0", 0))
        cls.put_value_map(span_attrs, "df.span.syscall_thread_1", item.get("syscall_thread_1", 0))
        cls.put_value_map(span_attrs, "df.span.syscall_cap_seq_0", item.get("syscall_cap_seq_1", 0))
        cls.put_value_map(span_attrs, "df.span.syscall_cap_seq_1", item.get("syscall_cap_seq_1", 0))

        cls.put_value_map(span_attrs, "df.span.native.trace_id", item.get("trace_id"))
        cls.put_value_map(span_attrs, "df.span.native.span_id", item.get("span_id"))

        # service info
        if cls.is_client_side(item.get("tap_side")):
            cls.put_value_map(span_resource, "service.name", item.get("auto_service_0"))
            cls.put_value_map(span_resource, "service.instance.id", item.get("auto_instance_0"))
        else:
            cls.put_value_map(span_resource, "service.name", item.get("auto_service_1"))
            cls.put_value_map(span_resource, "service.instance.id", item.get("auto_instance_1"))

        if item.get("app_service"):
            cls.put_value_map(span_resource, "service.name", item.get("app_service"))
        if item.get("app_instance"):
            cls.put_value_map(span_resource, "service.instance.id", item.get("app_instance"))

        cls.put_value_map(span_resource, "process.pid_0", item.get("process_id_0"))
        cls.put_value_map(span_resource, "process.pid_1", item.get("process_id_1"))
        cls.put_value_map(span_resource, "thread.name_0", item.get("process_kname_0"))
        cls.put_value_map(span_resource, "thread.name_1", item.get("process_kname_1"))

        # Flow Info
        cls.put_value_map(span_resource, "df.flow_info.id", item.get("_id"))
        cls.put_value_map(span_resource, "df.flow_info.flow_id", item.get("flow_id"))

        # Capture Info
        cls.put_value_map(span_resource, "df.capture_info.signal_source", signal_source)
        cls.put_value_map(span_resource, "df.capture_info.tap", item.get("tap"))
        cls.put_value_map(span_resource, "df.capture_info.vtap", item.get("vtap"))
        cls.put_value_map(span_resource, "df.capture_info.nat_source", item.get("nat_source"))
        cls.put_value_map(span_resource, "df.capture_info.tap_port", item.get("tap_port"))
        cls.put_value_map(span_resource, "df.capture_info.tap_port_name", item.get("tap_port_name"))
        cls.put_value_map(
            span_resource, "df.capture_info.tap_port_type", cls.tap_port_type_to_string(item.get("tap_port_type"))
        )
        cls.put_value_map(span_resource, "df.capture_info.tap_side", cls.tap_side_to_name(item.get("tap_side")))

        # Network Layer
        cls.put_bool_value_to_map(span_resource, "df.network.is_ipv4", item.get("is_ipv4"))
        cls.put_bool_value_to_map(span_resource, "df.network.is_internet_0", item.get("is_internet_0"))
        cls.put_bool_value_to_map(span_resource, "df.network.is_internet_1", item.get("is_internet_1"))
        cls.put_value_map(span_resource, "df.network.protocol", item.get("Enum(protocol)"))
        cls.put_value_map(span_resource, "df.network.ip_0", item.get("ip_0"))
        cls.put_value_map(span_resource, "df.network.ip_1", item.get("ip_1"))

        # Transport Layer
        cls.put_value_map(span_resource, "df.transport.client_port", item.get("client_port"))
        cls.put_value_map(span_resource, "df.transport.server_port", item.get("server_port"))
        cls.put_value_map(span_resource, "df.transport.req_tcp_seq", item.get("req_tcp_seq"))
        cls.put_value_map(span_resource, "df.transport.resp_tcp_seq", item.get("resp_tcp_seq"))

        # Application Layer
        cls.put_value_map(span_resource, "df.application.l7_protocol", item.get("Enum(l7_protocol)"))
        cls.put_value_map(span_resource, "telemetry.sdk.name", "deepflow")
        # version
        cls.put_value_map(span_resource, "telemetry.sdk.version", "v6.3.3.0")

        # 应用协议附加字段
        if cls.is_server_side(item.get("tap_side")):
            cls.put_value_map(span_attrs, "net.host.name", item.get("chost_1", item.get("pod_node_1")))
            cls.put_value_map(span_attrs, "net.peer.name", item.get("chost_0", item.get("pod_node_0")))
            cls.put_value_map(span_attrs, "net.host.port", item.get("server_port"))
            cls.put_value_map(span_attrs, "net.peer.port", item.get("client_port"))
            if item.get("is_ipv4"):
                cls.put_value_map(span_attrs, "net.sock.host.addr", item.get("ip4_1"))
            else:
                cls.put_value_map(span_attrs, "net.sock.host.addr", item.get("ip6_1"))
            if item.get("is_ipv4"):
                cls.put_value_map(span_attrs, "net.sock.peer.addr", item.get("ip4_0"))
            else:
                cls.put_value_map(span_attrs, "net.sock.peer.addr", item.get("ip6_0"))
        else:
            cls.put_value_map(span_attrs, "net.host.name", item.get("chost_0", item.get("pod_node_0")))
            cls.put_value_map(span_attrs, "net.peer.name", item.get("chost_1", item.get("pod_node_1")))
            cls.put_value_map(span_attrs, "net.host.port", item.get("client_port"))
            cls.put_value_map(span_attrs, "net.peer.port", item.get("server_port"))
            if item.get("is_ipv4"):
                cls.put_value_map(span_attrs, "net.sock.host.addr", item.get("ip4_0"))
            else:
                cls.put_value_map(span_attrs, "net.sock.host.addr", item.get("ip6_0"))
            if item.get("is_ipv4"):
                cls.put_value_map(span_attrs, "net.sock.peer.addr", item.get("ip4_1"))
            else:
                cls.put_value_map(span_attrs, "net.sock.peer.addr", item.get("ip6_1"))

        l7_protocol = item.get("l7_protocol")
        if l7_protocol:
            if L7_PROTOCOL_DNS == l7_protocol:
                cls.set_dns(span, span_attrs, item)
            elif l7_protocol in [
                L7_PROTOCOL_HTTP_1,
                L7_PROTOCOL_HTTP_2,
                L7_PROTOCOL_HTTP_1_TLS,
                L7_PROTOCOL_HTTP_2_TLS,
            ]:
                cls.set_http(span, span_attrs, item)
            elif L7_PROTOCOL_DUBBO == l7_protocol:
                cls.set_dubbo(span, span_attrs, item)
            elif L7_PROTOCOL_GRPC == l7_protocol:
                cls.set_grpc(span, span_attrs, item)
            elif L7_PROTOCOL_KAFKA == l7_protocol:
                cls.set_kafka(span, span_attrs, item)
            elif L7_PROTOCOL_MQTT == l7_protocol:
                cls.set_mqtt(span, span_attrs, item)
            elif L7_PROTOCOL_MYSQL == l7_protocol:
                cls.set_mysql(span, span_attrs, item)
            elif L7_PROTOCOL_REDIS == l7_protocol:
                cls.set_mysql(span, span_attrs, item)
            elif L7_PROTOCOL_POSTGRE == l7_protocol:
                cls.set_postgresql(span, span_attrs, item)

        status["code"] = cls.response_status_to_span_status_code(item.get("response_status"))
        status["message"] = cls.response_status_to_span_status_message(item.get("response_status"))

        cls.put_value_map(span_attrs, "df.span.endpoint", item.get("endpoint"))
        cls.put_value_map(span_attrs, "df.span.type", item.get("Enum(type)"))

        # 数据补充
        if not span_resource.get("service.name"):
            cls.put_value_map(span_resource, "service.name", "deepflow")

        span.elapsed_time = span.end_time - span.start_time

        return span.span_to_dict()
