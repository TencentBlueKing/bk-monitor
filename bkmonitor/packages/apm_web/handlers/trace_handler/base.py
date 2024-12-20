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
import copy
import json
import operator
from abc import ABC
from collections import defaultdict

import networkx
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.translation import gettext as _
from networkx import dag_longest_path_length
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import RpcGrpcStatusCodeValues, SpanAttributes
from opentelemetry.trace import StatusCode
from rest_framework.status import is_success

from apm_web.constants import (
    OTLP_JAEGER_SPAN_KIND,
    CategoryEnum,
    EbpfTapSideType,
    SpanSourceCategory,
    Status,
)
from apm_web.handlers.trace_handler.display_handler import DisplayHandler
from apm_web.handlers.trace_handler.virtual_span import VirtualSpanHandler
from apm_web.icon import TraceIcon, get_icon_url
from apm_web.trace.service_color import ServiceColorClassifier
from apm_web.utils import percentile
from bkmonitor.utils import group_by
from constants.apm import OtlpKey, SpanKind, TraceWaterFallDisplayKey
from core.unit import load_unit


class AttributePredicate(ABC):
    ATTRIBUTE_TYPE = "string"

    @classmethod
    def predicate(cls, attribute_key, attribute_value):
        return True


class ErrorPredicate(AttributePredicate):
    ATTRIBUTE_TYPE = "error"

    @classmethod
    def predicate(cls, attribute_key, attribute_value):
        if attribute_value == "ERROR":
            return True
        return False


class JsonAttributePredicate(AttributePredicate):
    ATTRIBUTE_TYPE = "json"

    @classmethod
    def predicate(cls, attribute_key, attribute_value):
        try:
            json.loads(attribute_value)
            return True
        except (ValueError, TypeError):
            return False


class StatusCodeAttributePredicate(AttributePredicate):
    ATTRIBUTE_TYPE = "status_code"

    STATUS_KEYS = [SpanAttributes.HTTP_STATUS_CODE, SpanAttributes.RPC_GRPC_STATUS_CODE]

    STATUS_ERROR_TYPE = "error"

    STATUS_NORMAL = "normal"
    STATUS_ERROR = "error"

    @classmethod
    def predicate(cls, attribute_key, attribute_value):
        if attribute_key in [SpanAttributes.HTTP_STATUS_CODE, SpanAttributes.RPC_GRPC_STATUS_CODE]:
            return True
        return False

    @classmethod
    def get_status(cls, category, attributes):
        for key in cls.STATUS_KEYS:
            status_code = attributes.get(key)
            if not status_code:
                continue
            return cls.predicate_error(category, status_code)
        return None

    @classmethod
    def predicate_error(cls, category, status_code):
        if status_code is None:
            return None

        if category == CategoryEnum.RPC:
            if status_code == RpcGrpcStatusCodeValues.OK.value:
                return {"type": cls.STATUS_NORMAL, "value": status_code}

            return {"type": cls.STATUS_ERROR, "value": status_code}
        elif category == CategoryEnum.HTTP:
            if is_success(status_code):
                return {"type": cls.STATUS_NORMAL, "value": status_code}

            return {"type": cls.STATUS_ERROR, "value": status_code}

        return None


class UrlAttributePredicate(AttributePredicate):
    ATTRIBUTE_TYPE = "url"

    @classmethod
    def predicate(cls, attribute_key, attribute_value):
        try:
            URLValidator()(attribute_value)
            return True
        except ValidationError:
            return False


class SpanPredicate:
    """对Span某些字段进行转换"""

    NORMAL = "normal"
    ERROR = "error"

    @classmethod
    def predicate_status_code(cls, span):
        code = span.get("status", {}).get("code")

        if code == StatusCode.UNSET.value:
            return {"type": Status.WARNING, "value": _("未设置")}
        if code == StatusCode.OK.value:
            return {"type": Status.NORMAL, "value": _("正常")}
        return {"type": Status.FAILED, "value": _("异常")}


class QueryField:
    def __init__(self, field: str, display: str, es_field: str = None, agg_field: str = None, searchable: bool = True):
        """
        :param field: 展示的字段英文名
        :param display: 展示的字段中文名
        :param es_field: 实际用于查询ES的底层字段名
        :param agg_field: ES 用于聚合计算的字段
        :param searchable: 是否为计算字段（即不在ES中保存）
        """
        self.field = field
        self.display = display
        self.es_field = field if es_field is None else es_field
        self.agg_field = self.es_field if agg_field is None else agg_field
        self.searchable = searchable

    def get_value_by_es_field(self, data: dict):
        """
        根据ES字段从Hit中拿出对应字段数据
        :param data:
        :return:
        """
        if not self.es_field:
            return None
        value = data
        try:
            for path in self.es_field.split("."):
                value = value.get(path, None)
        except Exception:
            value = None
        return value


class TraceHandler:
    @classmethod
    def handle_span(cls, app_name, span):
        if not span:
            return {}

        origin_span = copy.deepcopy(span)

        # 保持和traceDetail的Span格式相似
        processes = {
            "p1": {
                "serviceName": span[OtlpKey.RESOURCE].get(ResourceAttributes.SERVICE_NAME),
                "tags": cls._transform_to_tags(span[OtlpKey.RESOURCE], query_key_prefix="resource"),
            }
        }
        convert_span = cls._convert_span(app_name, span)
        convert_span["processID"] = "p1"

        return {
            "trace_tree": {
                "spans": [convert_span],
                "processes": processes,
            },
            "origin_data": origin_span,
        }

    @classmethod
    def display_filter(cls, spans, displays):
        has_virtual_span = False
        if TraceWaterFallDisplayKey.VIRTUAL_SPAN in displays:
            displays.remove(TraceWaterFallDisplayKey.VIRTUAL_SPAN)
            has_virtual_span = True

        display_spans = []

        for span in spans:
            if DisplayHandler.is_match(span, displays):
                display_spans.append(span)

        if has_virtual_span:
            virtual_spans = VirtualSpanHandler.generate(display_spans)
            display_spans += virtual_spans

        return display_spans

    @classmethod
    def build_new_resource(cls, resource: dict) -> dict:
        new_resource = {}
        for k, v in resource.items():
            if isinstance(v, (list, set)):
                new_resource[k] = tuple(v)
            elif isinstance(v, dict):
                new_resource[k] = cls.build_new_resource(v)
            else:
                new_resource[k] = v
        return new_resource

    @classmethod
    def handle_trace(
        cls,
        app_name,
        trace_data: list,
        trace_id: str,
        relation_mapping: dict,
        displays: list = None,
        enabled_time_alignment=False,
    ):
        # otel data must be in displays choice
        displays = displays or []
        if TraceWaterFallDisplayKey.SOURCE_CATEGORY_OPENTELEMETRY not in displays:
            displays.append(TraceWaterFallDisplayKey.SOURCE_CATEGORY_OPENTELEMETRY)

        # 节点隐藏处理
        trace_data = cls.display_filter(trace_data, displays)
        if not trace_data:
            return {}
        trace_data_sort = sorted(trace_data, key=lambda i: i["start_time"])

        # 将ebpf的span重新排序。（相邻的ebpf的span，按耗时长短排序）
        trace_data = []
        adjacent_ebpf_spans = []
        for span in trace_data_sort:
            if DisplayHandler.get_source_category(span) != SpanSourceCategory.OPENTELEMETRY:
                adjacent_ebpf_spans.append(span)
            else:
                if adjacent_ebpf_spans:
                    trace_data.extend(sorted(adjacent_ebpf_spans, key=lambda i: i["elapsed_time"], reverse=True))
                    adjacent_ebpf_spans = []
                trace_data.append(span)
        if adjacent_ebpf_spans:
            trace_data.extend(sorted(adjacent_ebpf_spans, key=lambda i: i["elapsed_time"], reverse=True))

        res = {
            "trace_id": trace_id,
            "original_data": copy.deepcopy(trace_data),
        }

        service_color_classifier = ServiceColorClassifier()
        trace_info = {
            "app_name": app_name,
            "root_span_id": "",
            "root_service": "",
            "root_endpoint": "",
            "error": False,
            "status_code": None,
            "product_time": trace_data[0]["start_time"],
            "category": "",
            "trace_duration": 0,
            "trace_start_time": trace_data[0][OtlpKey.START_TIME],
            "trace_end_time": trace_data[0][OtlpKey.END_TIME],
            "service_count": 0,
            "hierarchy_count": 0,
            "request_count": 0,
            "max_duration": 0,
            "min_duration": 0,
            "time_error": False,
        }
        error_count = 0
        service_pair = defaultdict(lambda: {"left": None, "right": None})
        time_service_pair = defaultdict(lambda: {"left": None, "right": []})
        service_spans = defaultdict(list)
        topo_relation = set()
        durations = []
        request_count = 0
        tree_nodes = set()
        tree_edges = set()
        span_relations = []
        resources = []
        resources_set = set()
        service_span_mapping = {}
        start_times = []
        end_times = []

        # 组合初始化数据
        for span in trace_data:
            span_id = span[OtlpKey.SPAN_ID]
            parent_span_id = span[OtlpKey.PARENT_SPAN_ID]

            if span[OtlpKey.KIND] in [SpanKind.SPAN_KIND_SERVER, SpanKind.SPAN_KIND_CONSUMER]:
                service_spans[span[OtlpKey.RESOURCE].get(ResourceAttributes.SERVICE_NAME, "")].append(span)
                # 将kind为server, consumer的span添加至右侧列表，key为span的parent_span_id
                time_service_pair[parent_span_id]["right"].append(span)
                request_count += 1
            if span[OtlpKey.KIND] in [SpanKind.SPAN_KIND_CLIENT, SpanKind.SPAN_KIND_PRODUCER]:
                # 将client, producer的span作为left，key为span_id
                time_service_pair[span_id]["left"] = span

            if span[OtlpKey.KIND] in [SpanKind.SPAN_KIND_SERVER]:
                service_pair[parent_span_id]["right"] = span
            if span[OtlpKey.KIND] in [SpanKind.SPAN_KIND_CLIENT]:
                service_pair[span_id]["left"] = span

            durations.append(span[OtlpKey.ELAPSED_TIME])
            if span[OtlpKey.STATUS]["code"] == StatusCode.ERROR.value:
                error_count += 1

            if parent_span_id:
                topo_relation.add((parent_span_id, span_id))
                tree_nodes.add(span[OtlpKey.PARENT_SPAN_ID])
                tree_nodes.add(span[OtlpKey.SPAN_ID])
                tree_edges.add((span[OtlpKey.PARENT_SPAN_ID], span[OtlpKey.SPAN_ID]))
                span_relations.append({"source": span[OtlpKey.PARENT_SPAN_ID], "target": span[OtlpKey.SPAN_ID]})
            else:
                tree_nodes.add(span[OtlpKey.SPAN_ID])
                tree_edges.add((span[OtlpKey.SPAN_ID], "--"))

            service_name = span[OtlpKey.RESOURCE].get(ResourceAttributes.SERVICE_NAME)
            if service_name:
                service_span_mapping.setdefault(service_name, []).append(span)

            tem_resource = cls.build_new_resource(span[OtlpKey.RESOURCE])
            resource_key = tuple(tem_resource.items())
            if resource_key not in resources_set:
                resources_set.add(resource_key)
                resources.append(span[OtlpKey.RESOURCE])

            start_times.append(span[OtlpKey.START_TIME])
            end_times.append(span[OtlpKey.END_TIME])

        graph = networkx.DiGraph()
        graph.add_nodes_from(tree_nodes)
        graph.add_edges_from(tree_edges)
        trace_info["hierarchy_count"] = dag_longest_path_length(graph)
        trace_info["max_duration"] = max(durations)
        trace_info["min_duration"] = min(durations)
        trace_info["request_count"] = request_count
        trace_info["service_count"] = len(service_span_mapping.keys())
        trace_info["error"] = bool(error_count)
        # 总耗时(trace总耗时)
        trace_info["trace_duration"] = sorted(end_times, reverse=True)[0] - sorted(start_times)[0]

        # 时间对齐
        for span_pair in time_service_pair.values():
            if span_pair["left"] and span_pair["right"]:
                for right_span in span_pair["right"]:
                    # 校验1: 被调开始时间不能早于主调开始时间
                    time_delta = right_span[OtlpKey.START_TIME] - span_pair["left"][OtlpKey.START_TIME]
                    # 说明两个服务有时间偏差 以主调为基准对齐
                    if time_delta < 0:
                        trace_info["time_error"] = True
                        if enabled_time_alignment:
                            # 避免相同服务名不同机器产生的时间再次偏差 这里只调整当前调用关系
                            right_span[OtlpKey.START_TIME] -= time_delta
                            right_span[OtlpKey.END_TIME] -= time_delta

                    # 校验2:同步请求下被调开始时间不能大于主调结束时间
                    time_delta = right_span[OtlpKey.START_TIME] - span_pair["left"][OtlpKey.END_TIME]
                    if (
                        span_pair["left"][OtlpKey.KIND] == SpanKind.SPAN_KIND_CLIENT
                        and right_span[OtlpKey.KIND] == SpanKind.SPAN_KIND_SERVER
                        and time_delta > 0
                    ):
                        trace_info["time_error"] = True
                        if enabled_time_alignment:
                            start_delta = right_span[OtlpKey.START_TIME] - span_pair["left"][OtlpKey.START_TIME]
                            right_span[OtlpKey.START_TIME] -= start_delta
                            right_span[OtlpKey.END_TIME] -= start_delta

        # 获取各服务名称的类型: 服务的类型为此服务第一个被调span的span的类型
        service_classify = cls.classify_service(service_span_mapping)
        service_pair = {
            pair_span_id: span_pair
            for pair_span_id, span_pair in service_pair.items()
            if span_pair["left"] and span_pair["right"]
        }

        trace_tree = cls._get_trace_tree(
            app_name, trace_id, trace_data, resources, service_pair, service_color_classifier, relation_mapping
        )

        # step: 分析根span, 入口span ===
        first_span = trace_data[0]
        root_span = next(
            (i for i in trace_data if i[OtlpKey.KIND] in [SpanKind.SPAN_KIND_SERVER, SpanKind.SPAN_KIND_CONSUMER]),
            first_span,
        )
        trace_info["root_span_id"] = first_span[OtlpKey.SPAN_ID]
        if root_span:
            service_name = root_span[OtlpKey.RESOURCE].get(ResourceAttributes.SERVICE_NAME)
            trace_info["category"] = CategoryEnum.classify(root_span)
            trace_info["root_service"] = service_name
            trace_info["root_endpoint"] = root_span[OtlpKey.SPAN_NAME]
            trace_info["status_code"] = StatusCodeAttributePredicate.get_status(
                trace_info["category"], root_span[OtlpKey.ATTRIBUTES]
            )

        return {
            **res,
            "trace_info": trace_info,
            "span_classify": list(service_classify.values())
            + (
                [
                    {
                        "type": "error",
                        "filter_key": "status.code",
                        "filter_value": StatusCode.ERROR.value,
                        "name": _("错误"),
                        "count": error_count,
                        "icon": "mind-fill",
                        "color": "",
                    },
                ]
                if error_count
                else []
            )
            + [
                {
                    "type": "max_duration",
                    "filter_key": "duration",
                    "filter_value": trace_info["max_duration"],
                    "name": _(
                        "最大耗时 {}".format(
                            "".join(map(lambda x: str(x), load_unit("µs").auto_convert(trace_info["max_duration"])))
                        )
                    ),
                    "count": 0,
                    "icon": "mc-time",
                    "color": "",
                },
            ],
            "trace_tree": trace_tree,
            "topo_relation": span_relations,
        }

    @classmethod
    def classify_service(cls, service_spans):
        """
        找出服务对应的服务类型
        定义: 服务对应的第一个被调span的类型即为服务类型 若无 -> 则取第一个span
        """
        res = {}
        color_generator = ServiceColorClassifier()

        for service, spans in service_spans.items():
            order_spans = sorted(spans, key=lambda i: i[OtlpKey.START_TIME])
            root_span = next(
                (i for i in order_spans if i[OtlpKey.KIND] in [SpanKind.SPAN_KIND_SERVER, SpanKind.SPAN_KIND_CONSUMER]),
                None,
            )
            if not root_span:
                root_span = order_spans[0]

            icon, _ = cls._get_span_classify(root_span)
            res[service] = {
                "type": "service",
                "count": len(spans),
                "name": service,
                "filter_key": OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME),
                "filter_value": service,
                "color": color_generator.next(service),
                "icon": icon,
            }

        return res

    @classmethod
    def _get_trace_tree(
        cls,
        app_name,
        trace_id,
        trace_data,
        resources,
        service_pair,
        color_classifier,
        relation_map,
    ):
        from apm_web.trace.diagram.base import TraceTree, TreeBuildingConfig

        # 组件resource mappings
        res = {
            "traceID": trace_id,
            "processes": {
                f"p{index}": {
                    "serviceName": i[ResourceAttributes.SERVICE_NAME],
                    "tags": cls._transform_to_tags(i, query_key_prefix="resource"),
                }
                for index, i in enumerate(resources, 1)
                if ResourceAttributes.SERVICE_NAME in i
            },
        }
        spans = []
        # TODO: too much travels, need to optimize
        config = TreeBuildingConfig(with_group=True)
        complete_trace_tree = TraceTree.from_raw(trace_data, config)
        complete_trace_tree.build_extras()
        for span in trace_data:
            cls._add_to_trace_tree(
                app_name,
                spans,
                span,
                resources,
                service_pair,
                color_classifier,
                relation_map,
                grouped_trace_tree=complete_trace_tree,
            )

        res["spans"] = spans
        return res

    @classmethod
    def _add_to_trace_tree(
        cls,
        app_name,
        spans,
        span,
        resources,
        service_pair,
        color_classifier,
        relation_mapping,
        grouped_trace_tree,
    ):
        process_id = None

        for index, resource in enumerate(resources, 1):
            if span[OtlpKey.RESOURCE] == resource:
                process_id = f"p{index}"
                break

        convert_span = cls._convert_span(app_name, span, color_classifier=color_classifier)
        convert_span["processID"] = process_id
        convert_span["stage_duration"] = cls.handle_stage_duration(span, service_pair)
        convert_span["cross_relation"] = (
            relation_mapping[span[OtlpKey.SPAN_ID]] if span[OtlpKey.SPAN_ID] in relation_mapping else {}
        )
        convert_span["is_virtual"] = span.get("is_virtual", False)
        source_category = DisplayHandler.get_source_category(span)

        # 如果为Ebpf需要替换Icon
        if source_category != SpanSourceCategory.OPENTELEMETRY:
            convert_span["icon"] = get_icon_url(source_category)
            convert_span["source"] = SpanSourceCategory.EBPF
            convert_span["ebpf_kind"] = source_category
            if source_category == SpanSourceCategory.EBPF_NETWORK:
                # 对于网络的span:
                #  - resource.df.capture_info.tap_port_name: "eth1"  (采集位置名称, 当采集位置类型为本地网卡时，此值表示采集网卡的名称。)
                #  - resource.df.capture_info.tap_side: "Server NIC"（采集位置在流量路径中所处的逻辑位置，例如客户端网卡、客户端容器节点、服务端容器节点、服务端网卡等。）
                convert_span["ebpf_tap_port_name"] = span[OtlpKey.RESOURCE].get("df.capture_info.tap_port_name")
                convert_span["ebpf_tap_side"] = EbpfTapSideType.get_display_name(
                    span[OtlpKey.RESOURCE].get("df.capture_info.tap_side")
                )
            else:
                # 对于系统的span:
                #  - resource.thread.name_0: "nginx"     客户端进程名
                #  - resource.thread.name_1: "gunicorn"   服务端进程名
                #  需要根据客户端还是服务端从不同的字段取值
                if span[OtlpKey.RESOURCE].get("df.capture_info.tap_side") == EbpfTapSideType.CLIENT_PROCESS:
                    convert_span["ebpf_thread_name"] = span[OtlpKey.RESOURCE].get("thread.name_0")
                else:
                    convert_span["ebpf_thread_name"] = span[OtlpKey.RESOURCE].get("thread.name_1")
        else:
            convert_span["source"] = SpanSourceCategory.OPENTELEMETRY

        span_node = grouped_trace_tree.get_node_by_id(span[OtlpKey.SPAN_ID])
        if span_node:
            # TODO: trace tree next() should call it automatically
            span_node.finalize_candidates()
            if not span_node.group or span_node.children:
                convert_span["group_info"] = None
            else:
                convert_span["group_info"] = {
                    "id": span_node.group.members[0].id,
                    "members": [member.id for member in span_node.group.members],
                    "duration": span_node.group.absolute_duration,
                }

        spans.append(convert_span)

    @classmethod
    def _convert_span(cls, app_name, span, color_classifier=None):
        if not color_classifier:
            color_classifier = ServiceColorClassifier()

        service_name = span[OtlpKey.RESOURCE].get(ResourceAttributes.SERVICE_NAME, "")
        status_code_alias = {
            StatusCode.ERROR.value: "ERROR",
            StatusCode.UNSET.value: "UNSET",
            StatusCode.OK.value: "OK",
        }.get(span[OtlpKey.STATUS]["code"])

        extra_attributes = {
            "span.kind": {
                "value": f"{span[OtlpKey.KIND]}({SpanKind.get_label_by_key(span[OtlpKey.KIND])})",
                "origin_value": span[OtlpKey.KIND],
                "query_key": OtlpKey.KIND,
            },
            "span.trace_state": {
                "value": span[OtlpKey.TRACE_STATE],
                "origin_value": span[OtlpKey.TRACE_STATE],
                "query_key": OtlpKey.TRACE_STATE,
            },
            "span.status_code": {
                "value": f"{span[OtlpKey.STATUS]['code']}({status_code_alias})",
                "origin_value": span[OtlpKey.STATUS]["code"],
                "query_key": OtlpKey.STATUS_CODE,
            },
            "span.status_message": {
                "value": span[OtlpKey.STATUS]["message"],
                "origin_value": span[OtlpKey.STATUS]["message"],
                "query_key": OtlpKey.STATUS_MESSAGE,
            },
        }

        return {
            "id": span[OtlpKey.SPAN_ID],
            "app_name": app_name,
            "traceID": span[OtlpKey.TRACE_ID],
            "spanID": span[OtlpKey.SPAN_ID],
            "duration": span["elapsed_time"],
            "references": cls._transform_to_refs(span),
            "flags": 0,
            "color": color_classifier.next(service_name),
            "logs": cls._transform_to_logs(span[OtlpKey.EVENTS]),
            "operationName": span["span_name"],
            "service_name": service_name,
            "startTime": span["start_time"],
            "kind": span[OtlpKey.KIND],
            "tags": cls._transform_to_status(span.get("status", {}))
            + [{"key": "span.kind", "value": OTLP_JAEGER_SPAN_KIND.get(span[OtlpKey.KIND]), "type": "string"}],
            "error": span[OtlpKey.STATUS]["code"] == StatusCode.ERROR.value,
            "message": span[OtlpKey.STATUS]["message"],
            "attributes": cls.handle_attributes(span[OtlpKey.ATTRIBUTES], query_key=OtlpKey.ATTRIBUTES)
            + cls.handle_attributes(
                extra_attributes,
                query_key=OtlpKey.ATTRIBUTES,
                query_key_getter=lambda i: i["query_key"],
                value_getter=lambda i: i["value"],
                origin_value_getter=lambda i: i["origin_value"],
            ),
            "resource": cls.handle_attributes(span[OtlpKey.RESOURCE], query_key=OtlpKey.RESOURCE),
            "events": [
                {
                    "name": event["name"],
                    "timestamp": event["timestamp"],
                    "duration": event["timestamp"] - span["start_time"],
                    "attributes": cls.handle_attributes(event["attributes"], query_key="events.attributes"),
                }
                for event in span[OtlpKey.EVENTS]
            ],
            "icon": cls._get_span_classify(span)[0],
        }

    @classmethod
    def _get_span_classify(cls, span):
        """
        根据span分类出不同icon
        参考 API侧 TopoDiscoverRule规则
        """
        attributes = span[OtlpKey.ATTRIBUTES]
        if attributes.get(SpanAttributes.HTTP_METHOD):
            return get_icon_url(TraceIcon.HTTP), TraceIcon.HTTP
        elif attributes.get(SpanAttributes.RPC_SYSTEM):
            return get_icon_url(TraceIcon.RPC), TraceIcon.RPC
        elif attributes.get(SpanAttributes.MESSAGING_DESTINATION):
            return get_icon_url(TraceIcon.ASYNC_BACKEND), TraceIcon.ASYNC_BACKEND
        elif attributes.get(SpanAttributes.DB_SYSTEM):
            return get_icon_url(TraceIcon.DB), TraceIcon.DB
        elif attributes.get(SpanAttributes.MESSAGING_SYSTEM):
            return get_icon_url(TraceIcon.MESSAGE), TraceIcon.MESSAGE

        return get_icon_url(TraceIcon.OTHER), TraceIcon.OTHER

    @classmethod
    def _transform_to_logs(cls, events):
        return [
            {
                "timestamp": event["timestamp"],
                "fields": cls._transform_to_tags(event["attributes"], query_key_prefix="events.attributes")
                + cls._transform_to_tags({"message": event["name"]}, query_key_prefix="events.name"),
            }
            for event in events
        ]

    @classmethod
    def _transform_to_tags(cls, attributes, query_key_prefix):
        return [
            {
                "key": key,
                "value": value,
                "type": "string",
                "query_key": f"{query_key_prefix}.{key}",
                "query_value": value,
            }
            for key, value in attributes.items()
        ]

    @classmethod
    def _transform_to_refs(cls, span) -> list:
        refs = []
        if span[OtlpKey.PARENT_SPAN_ID]:
            refs.append({"refType": "CHILD_OF", "spanID": span[OtlpKey.PARENT_SPAN_ID], "traceID": span["trace_id"]})
        for link in span.get("links", []):
            refs.append({"refType": "FOLLOWS_FROM", "traceID": link["trace_id"], "spanID": link[OtlpKey.SPAN_ID]})
        return refs

    @classmethod
    def _transform_to_status(cls, status):
        if status.get("code") == StatusCode.ERROR.value:
            return [{"key": "error", "type": "string", "value": True}]
        return []

    @classmethod
    def handle_stage_duration(cls, span, service_pair):
        if not service_pair:
            return None

        is_left = False
        pair = service_pair.get(span[OtlpKey.PARENT_SPAN_ID])
        if not pair:
            pair = service_pair.get(span[OtlpKey.SPAN_ID])

            if not pair:
                return None

            is_left = True
        return {
            "target": "left" if is_left else "right",
            "left": {
                "label": pair["left"][OtlpKey.RESOURCE].get(ResourceAttributes.SERVICE_NAME, ""),
                "type": SpanKind.get_label_by_key(SpanKind.SPAN_KIND_CLIENT),
                "start_time": pair["left"][OtlpKey.START_TIME],
                "end_time": pair["left"][OtlpKey.END_TIME],
                "error": pair["left"][OtlpKey.STATUS]["code"] == StatusCode.ERROR.value,
                "error_message": pair["left"][OtlpKey.STATUS]["message"],
            },
            "right": {
                "label": pair["right"][OtlpKey.RESOURCE].get(ResourceAttributes.SERVICE_NAME, ""),
                "type": SpanKind.get_label_by_key(SpanKind.SPAN_KIND_SERVER),
                "start_time": pair["right"][OtlpKey.START_TIME],
                "end_time": pair["right"][OtlpKey.END_TIME],
                "error": pair["right"][OtlpKey.STATUS]["code"] == StatusCode.ERROR.value,
                "error_message": pair["right"][OtlpKey.STATUS]["message"],
            },
        }

    @classmethod
    def handle_attributes(
        cls,
        attributes: dict,
        query_key,
        query_key_getter=None,
        value_getter=lambda i: i,
        origin_value_getter=lambda i: i,
    ):
        result_attributes = []
        for key, value in attributes.items():
            predicate = AttributePredicate
            for predicate_item in [
                ErrorPredicate,
                JsonAttributePredicate,
                UrlAttributePredicate,
                StatusCodeAttributePredicate,
            ]:
                if predicate_item.predicate(key, value):
                    predicate = predicate_item
            attribute = {
                "type": predicate.ATTRIBUTE_TYPE,
                "key": key,
                "value": value_getter(value),
                "query_key": f"{query_key}.{key}" if not query_key_getter else query_key_getter(value),
                "query_value": origin_value_getter(value),
            }
            result_attributes.append(attribute)
        return result_attributes


RESOURCE_SDK_NAME_MAPPING = {
    "opentelemetry": "OpenTelemetry",
    "deepflow": "DeepFlow",
    "skywalking": "SkyWalking",
}


def get_sdk_display_name(raw_name: str) -> str:
    return RESOURCE_SDK_NAME_MAPPING.get(raw_name, raw_name)


class StatisticsHandler:
    TRACE_GROUP_BY_MAPPING = {
        "span_name": operator.itemgetter("span_name"),
        "resource.service.name": lambda i: i[OtlpKey.RESOURCE].get(ResourceAttributes.SERVICE_NAME),
        "resource.sdk.name": lambda i: get_sdk_display_name(
            i[OtlpKey.RESOURCE].get(ResourceAttributes.TELEMETRY_SDK_NAME)
        ),
        "kind": operator.itemgetter("kind"),
    }

    @classmethod
    def get_trace_statistics(cls, spans, group_fields, _filter):
        if not all(i in cls.TRACE_GROUP_BY_MAPPING for i in group_fields):
            raise ValueError(_(f"存在不支持的分组字段: {group_fields}"))

        group_mapping = {}
        for i in spans:
            key = tuple()
            for f in group_fields:
                key += (cls.TRACE_GROUP_BY_MAPPING[f](i),)

            group_mapping.setdefault(key, []).append(i)

        service_spans_mapping = group_by(spans, lambda i: i[OtlpKey.RESOURCE].get(ResourceAttributes.SERVICE_NAME))
        service_classify = TraceHandler.classify_service(service_spans_mapping)

        filter_type = _filter.get("type", "")
        filter_value = _filter.get("value", "")

        res = []
        for key, key_spans in group_mapping.items():
            filter_spans = key_spans
            if filter_type == "service":
                # 只筛选出属于这个服务的数据
                filter_spans = [
                    i for i in key_spans if i[OtlpKey.RESOURCE].get(ResourceAttributes.SERVICE_NAME) == filter_value
                ]
            elif filter_type == "error":
                filter_spans = [i for i in key_spans if i[OtlpKey.STATUS]["code"] == StatusCode.ERROR.value]

            line = cls._add_line(filter_spans)
            if line:
                # 添加勾选字段
                for index, f in enumerate(group_fields):
                    line[f] = getattr(cls, f"convert_{f.replace('.', '_')}", lambda i, *args, **kwargs: i)(
                        key[index], service_classify
                    )

                res.append(line)

        # 关键词与最大耗时过滤
        if filter_type == "max_duration":
            return [sorted(res, key=lambda i: i["max_duration"], reverse=True)[0]]
        elif filter_type == "keyword":
            t_res = []
            for i in res:
                # 全字段匹配
                for j in i.values():
                    if isinstance(j, str) and filter_value.lower() in j.lower():
                        t_res.append(i)
                        continue
                    if isinstance(j, dict) and filter_value.lower() in j.get("value"):
                        t_res.append(i)
                        continue

            return t_res

        return res

    @classmethod
    def convert_resource_service_name(cls, value, service_classify):
        classify = service_classify[value]
        return {"icon": classify["icon"], "value": classify["name"]}

    @classmethod
    def convert_kind(cls, value, *args, **kwargs):
        return {
            "icon": get_icon_url(value),
            "value": value,
            "text": SpanKind.get_label_by_key(value),
        }

    @classmethod
    def _add_line(cls, spans):
        if not spans:
            return None

        duration = [i["elapsed_time"] for i in spans]
        return {
            "max_duration": max(duration),
            "min_duration": min(duration),
            "avg_duration": round(sum(duration) / len(duration), 2),
            "sum_duration": sum(duration),
            "P95": percentile(duration, 95),
            "count": len(spans),
            # 是否全部为内部/未指定span -> 是: 前端不能跳转至观测场景(因为不会被发现)
            "is_interval": all(
                i[OtlpKey.KIND] in [SpanKind.SPAN_KIND_INTERNAL, SpanKind.SPAN_KIND_UNSPECIFIED] for i in spans
            ),
        }
