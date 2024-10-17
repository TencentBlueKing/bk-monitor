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
        return defaultdict(lambda: {"category": "", "kind": "", "predicate_value": "", "service_language": ""})

    def discover(self, origin_data):
        rules, other_rule = self.get_rules()

        exists_instances = self.list_exists()

        create_topo_instances = {}
        update_topo_instances = {}
        further_instances = {}

        for span in origin_data:
            find_instances = self.extra_data_factory

            match_rule = self.get_match_rule(span, rules, other_rule)

            self.find_remote_service(span, match_rule, find_instances)

            topo_key = get_topo_instance_key(
                match_rule.instance_keys,
                match_rule.topo_kind,
                match_rule.category_id,
                span,
                component_predicate_key=match_rule.predicate_key,
            )
            if match_rule.topo_kind == ApmTopoDiscoverRule.TOPO_COMPONENT:
                # 组件类型的节点名称需要添加上服务名称的前缀 (不考虑拼接后与用户定义的服务重名情况需要引导用户进行更改)
                topo_key = f"{self.get_service_name(span)}-{topo_key}"

            find_instances[topo_key]["category"] = match_rule.category_id
            find_instances[topo_key]["kind"] = match_rule.topo_kind
            find_instances[topo_key]["predicate_value"] = extract_field_value(match_rule.predicate_key, span)
            find_instances[topo_key]["service_language"] = extract_field_value(
                (OtlpKey.RESOURCE, ResourceAttributes.TELEMETRY_SDK_LANGUAGE), span
            )

            if match_rule.topo_kind == ApmTopoDiscoverRule.TOPO_COMPONENT:

                other_rule_topo_key = get_topo_instance_key(
                    other_rule.instance_keys,
                    other_rule.topo_kind,
                    other_rule.category_id,
                    span,
                )
                further_instances[other_rule_topo_key] = {
                    "category": other_rule.category_id,
                    "kind": other_rule.topo_kind,
                    "predicate_value": extract_field_value(other_rule.predicate_key, span),
                    "service_language": extract_field_value(
                        (OtlpKey.RESOURCE, ResourceAttributes.TELEMETRY_SDK_LANGUAGE), span
                    ),
                }

            update_keys = find_instances.keys() & exists_instances.keys()
            create_keys = find_instances.keys() - update_keys

            update_topo_instances.update({k: find_instances[k] for k in update_keys})
            create_topo_instances.update({k: find_instances[k] for k in create_keys})

        for k, v in further_instances.items():
            if k not in update_topo_instances and k not in create_topo_instances and k not in exists_instances.keys():
                # avoid the problem that the service of the fixed-format component span is not found
                create_topo_instances.update({k: v})

        # update
        for topo_key, topo_value in update_topo_instances.items():
            TopoNode.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name, topo_key=topo_key).update(
                extra_data=topo_value, updated_at=datetime.now()
            )

        # create
        create_instances = [
            TopoNode(bk_biz_id=self.bk_biz_id, app_name=self.app_name, topo_key=topo_key, extra_data=extra_data)
            for topo_key, extra_data in create_topo_instances.items()
        ]
        TopoNode.objects.bulk_create(create_instances)

        self.clear_if_overflow()
        self.clear_expired()

    def list_exists(self):
        res = {}
        topo_nodes = TopoNode.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        for node in topo_nodes:
            res[node.topo_key] = node.extra_data

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
            instance_map[instance_key]["category"] = rule.category_id
            # remote service found by span additionally
            instance_map[instance_key]["kind"] = ApmTopoDiscoverRule.TOPO_REMOTE_SERVICE
            instance_map[instance_key]["predicate_value"] = extract_field_value(predicate_key, span)
