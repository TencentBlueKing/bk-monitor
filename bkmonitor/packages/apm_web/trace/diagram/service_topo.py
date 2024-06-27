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
import abc
from abc import ABC
from collections import defaultdict
from typing import List, NamedTuple, Tuple
from urllib.parse import urlparse

from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm_web.constants import CategoryEnum
from apm_web.handlers.trace_handler.base import TraceHandler
from apm_web.trace.service_color import ServiceColorClassifier
from constants.apm import OtlpKey, SpanKind


def exists_field(predicate_key: Tuple[str, str], item) -> bool:
    if item is None:
        return False
    predicate_first_key, predicate_second_key = predicate_key
    if item.get(predicate_first_key, item).get(predicate_second_key):
        return True
    return False


def extract_field_value(key: Tuple[str, str], item):
    first_key, second_key = key
    return item.get(first_key, item).get(second_key, "")


def get_node_key(keys: List[Tuple[str, str]], category: str, item: dict):
    if item is None:
        return OtlpKey.UNKNOWN_SERVICE

    instance_keys = [str(item.get(first_key, item).get(second_key, "")) for first_key, second_key in keys]

    method = extract_field_value((OtlpKey.ATTRIBUTES, SpanAttributes.HTTP_METHOD), item)
    kind = item["kind"]
    if category == CategoryEnum.HTTP and kind == SpanKind.SPAN_KIND_CLIENT:
        http_url = instance_keys[0]
        url_parse = urlparse(http_url)
        path_or_netloc = url_parse.path if url_parse.path else url_parse.netloc
        if not path_or_netloc:
            return item["span_name"]
        return f"{method}:{path_or_netloc}"
    elif category == CategoryEnum.HTTP and kind == SpanKind.SPAN_KIND_SERVER:
        http_route = extract_field_value((OtlpKey.ATTRIBUTES, SpanAttributes.HTTP_ROUTE), item)
        http_host = extract_field_value((OtlpKey.ATTRIBUTES, SpanAttributes.HTTP_HOST), item)
        route_or_host = http_route if http_route else http_host
        if not route_or_host:
            return item["span_name"]
        return f"{method}:{route_or_host}"
    if not all(instance_keys):
        instance_keys = [item["span_name"]]
    return ":".join(instance_keys)


class NodeType:
    """节点类型"""

    COMPONENT = "component"
    SERVICE = "service"
    INTERFACE = "interface"


class ServiceTopoDiscoverRuleCls(NamedTuple):
    category_id: str
    node_type: str
    predicate_key: Tuple[str, str]
    instance_keys: List[Tuple[str, str]]


# 规则实例
RULE_INSTANCES = [
    {
        "predicate_key": ("attributes", "db.system"),
        "node_type": NodeType.COMPONENT,
        "category_id": CategoryEnum.DB,
        "instance_keys": [("attributes", "db.system")],
    },
    {
        "predicate_key": ("attributes", "messaging.system"),
        "node_type": NodeType.COMPONENT,
        "category_id": CategoryEnum.MESSAGING,
        "instance_keys": [("attributes", "messaging.system")],
    },
    {
        "predicate_key": ("attributes", "http.method"),
        "node_type": NodeType.INTERFACE,
        "category_id": CategoryEnum.HTTP,
        "instance_keys": [("attributes", "http.url")],
    },
    {
        "predicate_key": ("attributes", "rpc.system"),
        "node_type": NodeType.INTERFACE,
        "category_id": CategoryEnum.RPC,
        "instance_keys": [("attributes", "rpc.system"), ("attributes", "rpc.method")],
    },
    {
        "predicate_key": ("attributes", "messaging.destination"),
        "node_type": NodeType.COMPONENT,
        "category_id": CategoryEnum.ASYNC_BACKEND,
        "instance_keys": [("attributes", "messaging.destination")],
    },
]

# 默认规则实例
DEFAULT_RULE_INSTANCE = {
    "predicate_key": ("", ""),
    "node_type": NodeType.INTERFACE,
    "category_id": CategoryEnum.OTHER,
    "instance_keys": [("", "span_name")],
}

# 服务规则实例
SERVICE_RULE_INSTANCE = {
    "predicate_key": ("resource", "service.name"),
    "node_type": "service",
    "category_id": CategoryEnum.OTHER,
    "instance_keys": [("resource", "service.name")],
}

SERVICE_TOPO_RULES = [ServiceTopoDiscoverRuleCls(**rule) for rule in RULE_INSTANCES]


class DiscoverBase(ABC):
    def __init__(self):
        self.data_map = defaultdict(list)
        self.color_classifier = ServiceColorClassifier()

    @classmethod
    def get_service_name(cls, span: dict):
        return extract_field_value((OtlpKey.RESOURCE, ResourceAttributes.SERVICE_NAME), span)

    @classmethod
    def get_match_rule(cls, span, rules: List[ServiceTopoDiscoverRuleCls]) -> ServiceTopoDiscoverRuleCls:
        res = next(
            (rule for rule in rules if exists_field(rule.predicate_key, span)),
            ServiceTopoDiscoverRuleCls(**DEFAULT_RULE_INSTANCE),
        )
        return res

    @abc.abstractmethod
    def discover(self, spans: list) -> list:
        pass

    def get_base_item_to_span(self, span: dict):
        service_name = self.get_service_name(span)
        return {
            "span_name": span[OtlpKey.SPAN_NAME],
            "span_id": span[OtlpKey.SPAN_ID],
            "kind": span[OtlpKey.KIND],
            "duration": span[OtlpKey.ELAPSED_TIME],
            "start_time": span[OtlpKey.START_TIME],
            "display_name": span[OtlpKey.SPAN_NAME],
            "operation_name": span[OtlpKey.SPAN_NAME],
            "service_name": service_name,
            "icon": TraceHandler._get_span_classify(span)[0],  # noqa
            "color": self.color_classifier.next(service_name),
        }

    @classmethod
    def get_relation_map(cls, spans: list) -> dict:
        relation_mapping = defaultdict(lambda: {"from": None, "to": []})
        for span in spans:
            span_kind = span[OtlpKey.KIND]
            if span_kind in [SpanKind.SPAN_KIND_CLIENT, SpanKind.SPAN_KIND_PRODUCER]:
                relation_mapping[span[OtlpKey.SPAN_ID]]["from"] = span
            elif span_kind in [SpanKind.SPAN_KIND_CONSUMER, SpanKind.SPAN_KIND_SERVER]:
                relation_mapping[span[OtlpKey.PARENT_SPAN_ID]]["to"].append(span)
        return {_: i for _, i in relation_mapping.items() if i["from"]}

    @classmethod
    def is_all_component_rules(cls, rules: List[ServiceTopoDiscoverRuleCls]):
        return all(value == NodeType.COMPONENT for value in [rule.node_type for rule in rules])


class NodeDiscover(DiscoverBase):
    def add_node_relation_span(self, node_key: str, span: dict, node_type: str):
        """add node and node relation span"""
        base_item = self.get_base_item_to_span(span)
        node_key_type = (node_key, node_type)
        # 入度边
        if node_type == NodeType.SERVICE and span[OtlpKey.KIND] in [
            SpanKind.SPAN_KIND_SERVER,
            SpanKind.SPAN_KIND_CONSUMER,
        ]:
            self.data_map[node_key_type].append(base_item)
        elif node_type == NodeType.COMPONENT:
            self.data_map[node_key_type].append(base_item)
        elif node_type == NodeType.INTERFACE and span[OtlpKey.KIND] in [
            SpanKind.SPAN_KIND_CLIENT,
            SpanKind.SPAN_KIND_SERVER,
        ]:
            self.data_map[node_key_type].append(base_item)
        else:
            if not self.data_map[node_key_type]:
                self.data_map[node_key_type].append(base_item)

    @classmethod
    def find_root_spans(cls, spans: list):
        root_span = []
        if not spans:
            return root_span
        spans = sorted(spans, key=lambda x: x[OtlpKey.START_TIME])
        root_span = [span for span in spans if span[OtlpKey.PARENT_SPAN_ID] == ""]
        if not root_span:
            root_span = [spans[0]]
        return root_span

    @classmethod
    def get_root_node_key(cls, root_spans):
        root_node_keys = []
        for span in root_spans:
            if span[OtlpKey.KIND] in [SpanKind.SPAN_KIND_SERVER, SpanKind.SPAN_KIND_CONSUMER]:
                rules = SERVICE_TOPO_RULES + [ServiceTopoDiscoverRuleCls(**SERVICE_RULE_INSTANCE)]
                match_rule = cls.get_match_rule(span, rules)
                root_node_key = get_node_key(match_rule.instance_keys, match_rule.category_id, span)
                root_node_keys.append(root_node_key)
            elif span[OtlpKey.KIND] in [SpanKind.SPAN_KIND_CLIENT, SpanKind.SPAN_KIND_PRODUCER]:
                root_node_key = cls.get_service_name(span)
                root_node_keys.append(root_node_key)
        return root_node_keys

    def find_node_by_single_span(self, rules: List[ServiceTopoDiscoverRuleCls], span: dict):
        match_rule = self.get_match_rule(span, rules)
        service_node_key = self.get_service_name(span)
        self.add_node_relation_span(service_node_key, span, NodeType.SERVICE)
        node_key = get_node_key(match_rule.instance_keys, match_rule.category_id, span)
        self.add_node_relation_span(node_key, span, match_rule.node_type)

    def find_node(self, rules: List[ServiceTopoDiscoverRuleCls], span: dict, to_spans: list):
        match_rule = self.get_match_rule(span, rules)
        service_node_key = self.get_service_name(span)
        self.add_node_relation_span(service_node_key, span, NodeType.SERVICE)
        node_key = get_node_key(match_rule.instance_keys, match_rule.category_id, span)
        self.add_node_relation_span(node_key, span, match_rule.node_type)
        for t in to_spans:
            service_node_key = self.get_service_name(t)
            self.add_node_relation_span(service_node_key, t, NodeType.SERVICE)

    def discover(self, spans) -> list:
        relation_mapping = self.get_relation_map(spans)
        # 无对端span, kind in [2, 5]
        span_id_set = {span[OtlpKey.SPAN_ID] for span in spans}
        for span in spans:
            if (
                span[OtlpKey.KIND] in [SpanKind.SPAN_KIND_SERVER, SpanKind.SPAN_KIND_CONSUMER]
                and span[OtlpKey.PARENT_SPAN_ID] not in span_id_set
            ):
                self.find_node_by_single_span(SERVICE_TOPO_RULES, span)
        for relation in relation_mapping.values():
            if not relation["to"] and not relation["from"]:
                continue
            from_span = relation["from"]
            if not relation["to"]:
                self.find_node_by_single_span(SERVICE_TOPO_RULES, from_span)
                continue
            self.find_node(SERVICE_TOPO_RULES, from_span, relation["to"])

        nodes = []
        root_spans = self.find_root_spans(spans)
        root_node_keys = self.get_root_node_key(root_spans)
        for k, v in self.data_map.items():
            node_key, node_type = k
            display_name = node_key
            if node_type == NodeType.INTERFACE:
                display_name = " ".join(str(node_key).split(":", 1))
            node_info = {
                "key": node_key,
                "node_type": node_type,
                "display_name": display_name,
                "spans": v,
                "icon": v[0]["icon"],
                "color": self.color_classifier.next(node_key),
            }
            if node_key in root_node_keys:
                node_info["is_root"] = True
            else:
                node_info["is_root"] = False
            nodes.append(node_info)
        return nodes


class EdgeDiscover(DiscoverBase):
    def add_edge_relation_span(self, source: str, target: str, span: dict):
        """add edge and edge relation span"""
        base_item = self.get_base_item_to_span(span)
        source_target = (source, target)
        self.data_map[source_target].append(base_item)

    def build_edge_by_single_span(self, rules: List[ServiceTopoDiscoverRuleCls], span: dict):
        match_rule = self.get_match_rule(span, rules)
        source = self.get_service_name(span)
        target = get_node_key(match_rule.instance_keys, match_rule.category_id, span)
        if span[OtlpKey.KIND] in [SpanKind.SPAN_KIND_SERVER, SpanKind.SPAN_KIND_CONSUMER]:
            self.add_edge_relation_span(target, source, span)
        else:
            self.add_edge_relation_span(source, target, span)

    def build_edge(self, rules: List[ServiceTopoDiscoverRuleCls], from_span: dict, to_spans: list):
        match_rule = self.get_match_rule(from_span, rules)
        # 服务 --> 接口 或者 服务 --> 中间键
        key = get_node_key(match_rule.instance_keys, match_rule.category_id, from_span)
        from_service_name = self.get_service_name(from_span)
        self.add_edge_relation_span(from_service_name, key, from_span)
        # 接口 --> 服务 或者 中间键 --> 服务
        for t in to_spans:
            to_service_name = self.get_service_name(t)
            self.add_edge_relation_span(key, to_service_name, t)

    def discover(self, spans: list) -> list:
        relation_mapping = self.get_relation_map(spans)
        # 无对端span, kind in [2, 5]
        span_id_set = {span[OtlpKey.SPAN_ID] for span in spans}
        for span in spans:
            if (
                span[OtlpKey.KIND] in [SpanKind.SPAN_KIND_SERVER, SpanKind.SPAN_KIND_CONSUMER]
                and span[OtlpKey.PARENT_SPAN_ID] not in span_id_set
            ):
                self.build_edge_by_single_span(SERVICE_TOPO_RULES, span)

        for relation in relation_mapping.values():
            if not relation["to"] and not relation["from"]:
                continue
            from_span = relation["from"]
            if not relation["to"]:
                self.build_edge_by_single_span(SERVICE_TOPO_RULES, from_span)
                continue
            self.build_edge(SERVICE_TOPO_RULES, from_span, relation["to"])

        edges = []
        for k, v in self.data_map.items():
            source, target = k
            display_name = key = " --> ".join(k)
            edges.append(
                {
                    "key": key,
                    "source": source,
                    "target": target,
                    "display_name": display_name,
                    "spans": v,
                    "num_of_operations": len(v),
                }
            )
        return edges


def span_collapsed(data: list):
    """span 折叠"""
    for obj in data:
        collapsed_spans = defaultdict(list)
        for span in obj["spans"]:
            collapsed_spans[span["span_name"]].append(span)
        collapsed_list = []
        for span_name, spans in collapsed_spans.items():
            first_span = spans[0]
            span_ids = list({span[OtlpKey.SPAN_ID] for span in spans})
            collapsed_list.append(
                {
                    **first_span,
                    "span_name": span_name,
                    "span_ids": span_ids,
                    "collapsed": len(span_ids) > 1,
                    "collapsed_span_num": len(span_ids),
                }
            )
        obj["spans"] = collapsed_list


def trace_data_to_service_topo(origin_data: list):
    spans = [
        span
        for span in origin_data
        if span[OtlpKey.KIND] not in [SpanKind.SPAN_KIND_INTERNAL, SpanKind.SPAN_KIND_UNSPECIFIED]
    ]

    nodes = NodeDiscover().discover(spans)
    edges = EdgeDiscover().discover(spans)

    return {"streamline_service_topo": {"nodes": nodes, "edges": edges}}
