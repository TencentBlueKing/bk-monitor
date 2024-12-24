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

from apm.constants import DiscoverRuleType
from apm.core.discover.base import (
    DiscoverBase,
    exists_field,
    extract_field_value,
    get_topo_instance_key,
)
from apm.models import ApmTopoDiscoverRule, TopoNode
from apm.utils.base import divide_biscuit
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import OtlpKey, TelemetryDataType, Vendor


class NodeDiscover(DiscoverBase):
    DISCOVERY_ALL_SPANS = True
    MAX_COUNT = 100000
    model = TopoNode
    # 批量处理 span 时 每批次的数量
    HANDLE_SPANS_BATCH_SIZE = 10000

    @property
    def extra_data_factory(self):
        return defaultdict(
            lambda: {
                "extra_data": {"category": "", "kind": "", "predicate_value": "", "service_language": ""},
                "platform": {},
                # system: multiple
                "system": {},
                # sdk: multiple
                "sdk": {},
            }
        )

    def discover(self, origin_data):
        rules_map = defaultdict(list)

        all_rules, other_rule = self.get_rules(_type="all")
        for rule in all_rules:
            rules_map[rule.type].append(rule)
        category_rules = (rules_map.pop(DiscoverRuleType.CATEGORY.value), other_rule)
        rules = [(k, v) for k, v in rules_map.items()]

        pool = ThreadPool()
        results = pool.map_ignore_exception(
            self.batch_execute,
            [(spans, category_rules, rules) for spans in divide_biscuit(origin_data, self.HANDLE_SPANS_BATCH_SIZE)],
        )

        # 结合发现的数据和已有数据判断 创建/更新
        exists_instances = self.list_exists()
        create_instances = {}
        update_instances = {}

        for instances_mapping in results:
            if not instances_mapping:
                continue

            for k, v in instances_mapping.items():
                v["system"] = list(v["system"].values())
                v["sdk"] = list(v["sdk"].values())
                if v["extra_data"]["category"] == ApmTopoDiscoverRule.APM_TOPO_CATEGORY_OTHER:
                    if all(k not in i for i in [update_instances, create_instances, exists_instances]):
                        # 如果目前没有发现这个符合 other 规则的服务 才把他添加进列表中 (不然如果更新的话会导致数据被覆盖为空)
                        create_instances.update({k: {**v, "source": [TelemetryDataType.TRACE.value]}})
                else:
                    if k not in exists_instances:
                        create_instances.update({k: {**v, "source": [TelemetryDataType.TRACE.value]}})
                    else:
                        source = exists_instances[k]["source"]
                        if not source:
                            source = [TelemetryDataType.TRACE.value]
                        elif TelemetryDataType.TRACE.value not in source:
                            source.append(TelemetryDataType.TRACE.value)
                        update_instances.update({k: {**v, "source": source}})

        # update
        update_combine_instances = []
        for topo_key, topo_value in update_instances.items():

            # 合并数组字段: platform | system
            exist_instance = exists_instances.get(topo_key)
            if not exist_instance:
                continue

            update_combine_instances.append(
                TopoNode(
                    id=exist_instance["id"],
                    topo_key=topo_key,
                    extra_data=topo_value["extra_data"],
                    platform=topo_value["platform"],
                    system=self.combine_list(exist_instance["system"], topo_value["system"]),
                    sdk=self.combine_list(exist_instance["sdk"], topo_value["sdk"]),
                    source=topo_value["source"],
                    updated_at=datetime.now(),
                )
            )

        TopoNode.objects.bulk_update(
            update_combine_instances, fields=["extra_data", "platform", "system", "sdk", "source", "updated_at"]
        )

        # create
        create_instances = [
            TopoNode(bk_biz_id=self.bk_biz_id, app_name=self.app_name, topo_key=topo_key, **topo_value)
            for topo_key, topo_value in create_instances.items()
        ]
        TopoNode.objects.bulk_create(create_instances)

        self.clear_if_overflow()
        self.clear_expired()

    @classmethod
    def combine_list(cls, target, source):
        """
        合并两个列表
        相同 name 的进行 extra_data 合并
        不同 name 的追加在数组中
        """
        if not target and not source:
            return []
        if not target:
            return source
        if not source:
            return target

        merged_dict = {}

        for item in target:
            name = item["name"]
            extra_data = item["extra_data"]
            merged_dict[name] = extra_data

        for item in source:
            name = item["name"]
            extra_data = item["extra_data"]
            if name in merged_dict:
                merged_dict[name].update(extra_data)
            else:
                merged_dict[name] = extra_data

        return [{"name": name, "extra_data": data} for name, data in merged_dict.items()]

    def batch_execute(self, origin_data, category_rules, rules):
        instance_mapping = self.extra_data_factory
        for span in origin_data:
            topo_key = None

            # 先进行 category 类型的规则发现
            # 类型为: category | 作用: 推断出 span 的服务、组件、自定义服务
            match_rule = self.get_match_rule(span, category_rules[0], category_rules[1])
            if match_rule:
                topo_key = self.find_category(instance_mapping, match_rule, category_rules[1], span)

            if not topo_key:
                # 如果 category 类型没有匹配规则 直接获取 other 规则的 topo_key 用于下面补充数据
                # (因为可能存在不符合规则的但是可以发现 platform 等其他信息)
                topo_key = get_topo_instance_key(
                    category_rules[1].instance_keys,
                    category_rules[1].topo_kind,
                    category_rules[1].category_id,
                    span,
                )
                instance_mapping[topo_key]["extra_data"]["category"] = category_rules[1].category_id
                instance_mapping[topo_key]["extra_data"]["kind"] = category_rules[1].topo_kind

            if not topo_key:
                continue

            # 后续的规则基于上一步发现的 topo_key 来补充数据
            for item in rules:
                item_rule_type = item[0]
                item_rules = item[1]

                if item_rule_type == DiscoverRuleType.SYSTEM.value:
                    match_rule = self.get_match_rule(span, item_rules)
                    if match_rule:
                        self.find_system(instance_mapping, match_rule, span, topo_key)

                elif item_rule_type == DiscoverRuleType.PLATFORM.value:
                    match_rule = self.get_match_rule(span, item_rules)
                    if match_rule:
                        self.find_platform(instance_mapping, match_rule, span, topo_key)

                elif item_rule_type == DiscoverRuleType.SDK.value:
                    match_rule = self.get_match_rule(span, item_rules)
                    if match_rule:
                        self.find_sdk(instance_mapping, match_rule, span, topo_key)

        return instance_mapping

    def find_category(self, instance_mapping, match_rule, other_rule, span):
        self.find_remote_service(span, match_rule, instance_mapping)

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

        instance_mapping[topo_key]["extra_data"]["category"] = match_rule.category_id
        instance_mapping[topo_key]["extra_data"]["kind"] = match_rule.topo_kind
        instance_mapping[topo_key]["extra_data"]["predicate_value"] = extract_field_value(
            match_rule.predicate_key, span
        )
        instance_mapping[topo_key]["extra_data"]["service_language"] = extract_field_value(
            (OtlpKey.RESOURCE, ResourceAttributes.TELEMETRY_SDK_LANGUAGE), span
        )
        if match_rule.topo_kind == ApmTopoDiscoverRule.TOPO_COMPONENT:
            other_rule_topo_key = get_topo_instance_key(
                other_rule.instance_keys,
                other_rule.topo_kind,
                other_rule.category_id,
                span,
            )
            instance_mapping[other_rule_topo_key]["extra_data"] = {
                "category": other_rule.category_id,
                "kind": other_rule.topo_kind,
                "predicate_value": extract_field_value(other_rule.predicate_key, span),
                "service_language": extract_field_value(
                    (OtlpKey.RESOURCE, ResourceAttributes.TELEMETRY_SDK_LANGUAGE), span
                ),
            }
        # 返回匹配规则的节点名称(非组件类)
        if match_rule.topo_kind != ApmTopoDiscoverRule.TOPO_COMPONENT:
            return topo_key

        return None

    def find_system(self, instance_mapping, match_rule, span, topo_key):
        extra_data = {}
        for i in match_rule.instance_keys:
            extra_data[self.join_keys(i)] = extract_field_value(i, span)
        instance_mapping[topo_key]["system"][match_rule.category_id] = {
            "name": match_rule.category_id,
            "extra_data": extra_data,
        }

    def find_platform(self, instance_mapping, match_rule, span, topo_key):
        extra_data = {}
        for i in match_rule.instance_keys:
            extra_data[self.join_keys(i)] = extract_field_value(i, span)
        instance_mapping[topo_key]["platform"] = {"name": match_rule.category_id, "extra_data": extra_data}

    def find_sdk(self, instance_mapping, match_rule, span, topo_key):
        # SDK 规则中无分类 id 直接将 predicate_value 作为名称
        predicate_value = extract_field_value(match_rule.predicate_key, span)
        extra_data = {self.join_keys(match_rule.predicate_key): predicate_value}
        if Vendor.equal(Vendor.G, predicate_value):
            for i in match_rule.instance_keys:
                extra_data[self.join_keys(i)] = extract_field_value(i, span)
        instance_mapping[topo_key]["sdk"][predicate_value] = {
            "name": predicate_value,
            "extra_data": extra_data,
        }

    def list_exists(self):
        return {
            i["topo_key"]: i
            for i in TopoNode.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).values(
                "topo_key", "extra_data", "system", "platform", "sdk", "id", "source"
            )
        }

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
