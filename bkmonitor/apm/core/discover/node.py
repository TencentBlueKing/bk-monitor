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
from collections import defaultdict
from datetime import datetime

from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm.core.discover.base import (
    DiscoverBase,
    exists_field,
    extract_field_value,
    get_topo_instance_key,
)
from apm.models import ApmTopoDiscoverRule, TopoNode
from constants.apm import OtlpKey


class NodeDiscover(DiscoverBase):
    MAX_COUNT = 100000
    model = TopoNode

    @property
    def extra_data_factory(self):
        return defaultdict(
            lambda: {
                "extra_data": {"category": "", "kind": "", "predicate_value": "", "service_language": "", "type": ""},
                "framework": "",
                "platform": "",
                "sdk": "",
            }
        )

    def discover(self, origin_data):
        rules_map = {}

        rules, other_rule = self.get_rules()
        for rule in rules:
            if rule.type not in rules_map:
                rules_map[rule.type] = []
            rules_map[rule.type].append(rule)

        exists_instances = self.list_exists()

        create_topo_instances = {}
        update_topo_instances = {}
        further_instances = {}
        node_dict = {}

        for span in origin_data:
            find_instances = self.extra_data_factory

            self.execute(rules_map, node_dict, other_rule, span, find_instances, further_instances)

            update_keys = find_instances.keys() & exists_instances.keys()
            create_keys = find_instances.keys() - update_keys

            update_topo_instances.update({k: find_instances[k] for k in update_keys})
            create_topo_instances.update({k: find_instances[k] for k in create_keys})
        if further_instances:
            for k, v in further_instances.items():
                if (
                    k not in update_topo_instances
                    and k not in create_topo_instances
                    and k not in exists_instances.keys()
                ):
                    # avoid the problem that the service of the fixed-format component span is not found
                    create_topo_instances.update({k: v})

        # update
        for topo_key, topo_value in update_topo_instances.items():
            TopoNode.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name, topo_key=topo_key).update(
                **topo_value, updated_at=datetime.now()
            )

        # create
        create_instances = [
            TopoNode(bk_biz_id=self.bk_biz_id, app_name=self.app_name, topo_key=topo_key, **topo_value)
            for topo_key, topo_value in create_topo_instances.items()
        ]
        TopoNode.objects.bulk_create(create_instances)

        self.clear_if_overflow()
        self.clear_expired()
        self.get_node(node_dict)

    def execute(self, rules_map, node_dict, other_rule, span, find_instances, further_instances):
        for topo_type, rules in rules_map.items():
            # "category"
            if topo_type == ApmTopoDiscoverRule.APM_TOPO_TYPE_CATEGORY:
                match_rule = self.get_match_rule(span, rules, other_rule)
                node_keys = self.find_category(match_rule, other_rule, span, find_instances, further_instances)
                node_dict[topo_type] = node_keys
                if match_rule.topo_kind == ApmTopoDiscoverRule.TOPO_COMPONENT:
                    rules[:] = [rule for rule in rules if rule.topo_kind != ApmTopoDiscoverRule.TOPO_COMPONENT]
                    self.execute(rules_map, node_dict, other_rule, span, find_instances, further_instances)

            # "framework"
            if topo_type == ApmTopoDiscoverRule.APM_TOPO_TYPE_FRAMEWORK:
                match_rule = self.get_match_rule(span, rules, other_rule)
                node_keys = self.find_framework(match_rule, other_rule, span, find_instances, further_instances)
                node_dict[topo_type] = node_keys

            # "platform"
            if topo_type == ApmTopoDiscoverRule.APM_TOPO_TYPE_PLATFORM:
                match_rule = self.get_match_rule(span, rules, other_rule)
                node_keys = self.find_platform(match_rule, other_rule, span, find_instances, further_instances)
                node_dict[topo_type] = node_keys

            # "sdk"
            if topo_type == ApmTopoDiscoverRule.APM_TOPO_TYPE_SDK:
                match_rule = self.get_match_rule(span, rules, other_rule)
                node_keys = self.find_sdk(match_rule, other_rule, span, find_instances, further_instances)
                node_dict[topo_type] = node_keys

    def get_node(self, node_dict):
        return node_dict

    def get_further_instances(self, match_rule, other_rule, span, further_instances):
        if match_rule.topo_kind == ApmTopoDiscoverRule.TOPO_COMPONENT:
            other_rule_topo_key = get_topo_instance_key(
                other_rule.instance_keys,
                other_rule.topo_kind,
                other_rule.category_id,
                span,
            )
            if other_rule_topo_key not in further_instances:
                further_instances[other_rule_topo_key] = {}
            further_instances[other_rule_topo_key]["extra_data"] = {
                "category": other_rule.category_id,
                "kind": other_rule.topo_kind,
                "predicate_value": extract_field_value(other_rule.predicate_key, span),
                "service_language": extract_field_value(
                    (OtlpKey.RESOURCE, ResourceAttributes.TELEMETRY_SDK_LANGUAGE), span
                ),
            }

    def get_topo_key(self, match_rule, span):
        topo_key = get_topo_instance_key(
            match_rule.instance_keys,
            match_rule.topo_kind,
            match_rule.category_id,
            span,
            component_predicate_keys=match_rule.predicate_key,
        )
        if match_rule.topo_kind == ApmTopoDiscoverRule.TOPO_COMPONENT:
            # 组件类型的节点名称需要添加上服务名称的前缀 (不考虑拼接后与用户定义的服务重名情况需要引导用户进行更改)
            topo_key = f"{self.get_service_name(span)}-{topo_key}"
        return topo_key

    def find_category(self, match_rule, other_rule, span, find_instances, further_instances):
        self.find_remote_service(span, match_rule, find_instances)
        topo_key = self.get_topo_key(match_rule, span)

        find_instances[topo_key]["extra_data"]["category"] = match_rule.category_id
        find_instances[topo_key]["extra_data"]["kind"] = match_rule.topo_kind
        find_instances[topo_key]["extra_data"]["type"] = match_rule.type
        find_instances[topo_key]["extra_data"]["predicate_value"] = extract_field_value(match_rule.predicate_key, span)
        find_instances[topo_key]["extra_data"]["service_language"] = extract_field_value(
            (OtlpKey.RESOURCE, ResourceAttributes.TELEMETRY_SDK_LANGUAGE), span
        )
        self.get_further_instances(match_rule, other_rule, span, further_instances)

        return find_instances[topo_key]["extra_data"]

    def find_framework(self, match_rule, other_rule, span, find_instances, further_instances):
        self.find_remote_service(span, match_rule, find_instances)
        topo_key = self.get_topo_key(match_rule, span)

        framework_list = []
        framework_dict = {
            "name": match_rule.category_id,
            "extra_data": extract_field_value(match_rule.predicate_key, span),
        }
        framework_list.append(framework_dict)
        find_instances[topo_key]["framework"] = framework_list

        self.get_further_instances(match_rule, other_rule, span, further_instances)

        return find_instances[topo_key]["framework"]

    def find_platform(self, match_rule, other_rule, span, find_instances, further_instances):
        self.find_remote_service(span, match_rule, find_instances)
        topo_key = self.get_topo_key(match_rule, span)

        if (
            match_rule.category_id == ApmTopoDiscoverRule.APM_TOPO_CATEGORY_K8S
            or match_rule.category_id == ApmTopoDiscoverRule.APM_TOPO_CATEGORY_NODE
        ):
            if (
                extract_field_value((OtlpKey.RESOURCE, OtlpKey.TELEMETRY_SDK_NAME), span)
                == ApmTopoDiscoverRule.APM_TOPO_GELILEO
            ):
                res = {
                    "type": match_rule.category_id,
                    "extra_data": {
                        "resource.target": extract_field_value((OtlpKey.RESOURCE, OtlpKey.TARGET), span).split('.', 1)[
                            0
                        ]
                    },
                }
                find_instances[topo_key]["platform"] = res

        self.get_further_instances(match_rule, other_rule, span, further_instances)

        return find_instances[topo_key]["platform"]

    def find_sdk(self, match_rule, other_rule, span, find_instances, further_instances):
        self.find_remote_service(span, match_rule, find_instances)
        topo_key = self.get_topo_key(match_rule, span)

        sdk_list = []
        sdk_dict = {
            "name": match_rule.category_id,
            "extra_data": extract_field_value(match_rule.predicate_key, span),
        }
        sdk_list.append(sdk_dict)
        find_instances[topo_key]["sdk"] = sdk_list

        self.get_further_instances(match_rule, other_rule, span, further_instances)

        return find_instances[topo_key]["sdk"]

    def list_exists(self):
        res = {}
        topo_nodes = TopoNode.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        for node in topo_nodes:
            if node.topo_key not in res:
                res[node.topo_key] = {}
            res[node.topo_key]["extra_data"] = node.extra_data
            res[node.topo_key]["framework"] = node.framework
            res[node.topo_key]["platform"] = node.platform
            res[node.topo_key]["sdk"] = node.sdk

        return res

    def find_remote_service(self, span, rule, instance_map):
        predicate_key = (OtlpKey.ATTRIBUTES, SpanAttributes.PEER_SERVICE)

        if exists_field(predicate_key, span):
            instance_key = get_topo_instance_key(
                [predicate_key],
                ApmTopoDiscoverRule.TOPO_REMOTE_SERVICE,
                rule.category_id,
                span,
            )
            instance_map[instance_key]["extra_data"]["category"] = rule.category_id
            # remote service found by span additionally
            instance_map[instance_key]["extra_data"]["kind"] = ApmTopoDiscoverRule.TOPO_REMOTE_SERVICE
            instance_map[instance_key]["extra_data"]["predicate_value"] = extract_field_value(predicate_key, span)
