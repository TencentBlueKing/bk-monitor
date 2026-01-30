"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import defaultdict
from datetime import datetime

from opentelemetry.semconv.trace import SpanAttributes

from apm.core.discover.base import DiscoverBase, exists_field, get_topo_instance_key
from apm.models import ApmTopoDiscoverRule, TopoNode, TopoRelation, TraceDataSource
from constants.apm import OtlpKey, SpanKind


class RelationDiscover(DiscoverBase):
    MAX_COUNT = 100000
    model = TopoRelation

    def get_relation_map(self, origin_data):
        relation_mapping = defaultdict(lambda: {"from": None, "to": [], "kind": ""})

        for span in origin_data:
            span_kind = span[OtlpKey.KIND]
            if span_kind in [SpanKind.SPAN_KIND_CLIENT, SpanKind.SPAN_KIND_PRODUCER]:
                relation_mapping[span[OtlpKey.SPAN_ID]]["from"] = span

                if span_kind == SpanKind.SPAN_KIND_CLIENT:
                    relation_mapping[span[OtlpKey.SPAN_ID]]["kind"] = TopoRelation.RELATION_KIND_SYNC
                else:
                    relation_mapping[span[OtlpKey.SPAN_ID]]["kind"] = TopoRelation.RELATION_KIND_ASYNC

            elif span_kind in [SpanKind.SPAN_KIND_CONSUMER, SpanKind.SPAN_KIND_SERVER]:
                relation_mapping[span[OtlpKey.PARENT_SPAN_ID]]["to"].append(span)

                # priority depends on from span
                if not relation_mapping[span[OtlpKey.PARENT_SPAN_ID]]["kind"]:
                    if span_kind == SpanKind.SPAN_KIND_SERVER:
                        relation_mapping[span[OtlpKey.PARENT_SPAN_ID]]["kind"] = TopoRelation.RELATION_KIND_SYNC
                    else:
                        relation_mapping[span[OtlpKey.PARENT_SPAN_ID]]["kind"] = TopoRelation.RELATION_KIND_ASYNC

        return {_: i for _, i in relation_mapping.items() if i["from"]}

    def list_exists(self):
        res = {}
        relations = TopoRelation.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        for relation in relations:
            res.setdefault(
                (
                    relation.from_topo_key,
                    relation.to_topo_key,
                    relation.kind,
                    relation.to_topo_key_kind,
                    relation.to_topo_key_category,
                ),
                set(),
            ).add(relation.id)

        return res

    def find_relation_by_single_span(self, component_rules, from_key, from_span, kind):
        relation_kind = TopoRelation.KIND_MAPPING[kind]
        found_keys = set()
        if exists_field((OtlpKey.ATTRIBUTES, SpanAttributes.PEER_SERVICE), from_span):
            kind, _ = TraceDataSource.get_category_kind(from_span[OtlpKey.ATTRIBUTES])
            if kind:
                # exist call remote service
                to_key = get_topo_instance_key(
                    [(OtlpKey.ATTRIBUTES, SpanAttributes.PEER_SERVICE)],
                    ApmTopoDiscoverRule.TOPO_REMOTE_SERVICE,
                    kind.split(".")[0],
                    from_span,
                )

                found_keys.add(
                    (
                        from_key,
                        to_key,
                        relation_kind,
                        ApmTopoDiscoverRule.TOPO_REMOTE_SERVICE,
                        ApmTopoDiscoverRule.APM_TOPO_CATEGORY_HTTP,
                    )
                )

        else:
            # 组件类
            match_rule = next((r for r in component_rules if exists_field(r.predicate_key, from_span)), None)
            if match_rule:
                to_key = get_topo_instance_key(
                    match_rule.instance_keys,
                    match_rule.topo_kind,
                    match_rule.category_id,
                    from_span,
                    component_predicate_key=match_rule.predicate_key,
                )
                to_key = f"{self.get_service_name(from_span)}-{to_key}"

                if kind in [SpanKind.SPAN_KIND_CLIENT, SpanKind.SPAN_KIND_PRODUCER]:
                    found_keys.add(
                        (
                            from_key,
                            to_key,
                            relation_kind,
                            match_rule.topo_kind,
                            match_rule.category_id,
                        )
                    )
                elif kind in [SpanKind.SPAN_KIND_SERVER, SpanKind.SPAN_KIND_CONSUMER]:
                    topo_node = TopoNode.objects.filter(
                        bk_biz_id=self.bk_biz_id, app_name=self.app_name, topo_key=self.get_service_name(from_span)
                    ).first()
                    kind = ApmTopoDiscoverRule.TOPO_SERVICE
                    category = ApmTopoDiscoverRule.APM_TOPO_CATEGORY_HTTP
                    if topo_node:
                        kind = topo_node.extra_data.get("kind", ApmTopoDiscoverRule.TOPO_SERVICE)
                        category = topo_node.extra_data.get("category", ApmTopoDiscoverRule.APM_TOPO_CATEGORY_HTTP)
                    found_keys.add(
                        (
                            to_key,
                            from_key,
                            relation_kind,
                            kind,
                            category,
                        )
                    )

        return found_keys

    def is_match_component_rule(self, component_rules, from_span):
        return bool(next((r for r in component_rules if exists_field(r.predicate_key, from_span)), None))

    def find_async_relation(self, rules, other_rules, from_key, from_span, to_spans, kind):
        found_keys = set()

        component_rules = [r for r in rules + [other_rules] if r.topo_kind == ApmTopoDiscoverRule.TOPO_COMPONENT]
        match_rule = next((r for r in component_rules if exists_field(r.predicate_key, from_span)), None)
        if not match_rule:
            return found_keys

        # find if exists middleware
        middleware_to_key = get_topo_instance_key(
            match_rule.instance_keys,
            match_rule.topo_kind,
            match_rule.category_id,
            from_span,
            component_predicate_key=match_rule.predicate_key,
        )
        if match_rule.topo_kind == ApmTopoDiscoverRule.TOPO_COMPONENT:
            middleware_to_key = f"{self.get_service_name(from_span)}-{middleware_to_key}"

        found_keys.add(
            (
                from_key,
                middleware_to_key,
                kind,
                match_rule.topo_kind,
                match_rule.category_id,
            )
        )

        for t in to_spans:
            to_span_match_rule = self.get_match_rule(t, rules, other_rules)
            middleware_key = get_topo_instance_key(
                to_span_match_rule.instance_keys,
                to_span_match_rule.topo_kind,
                to_span_match_rule.category_id,
                t,
                component_predicate_key=to_span_match_rule.predicate_key,
            )
            if to_span_match_rule.topo_kind == ApmTopoDiscoverRule.TOPO_COMPONENT:
                middleware_key = f"{self.get_service_name(t)}-{middleware_key}"

            if middleware_to_key == middleware_key:
                messaging_service_name = self.get_service_name(t)
                messaging_service_kind = ApmTopoDiscoverRule.TOPO_SERVICE
                messaging_service_category = ApmTopoDiscoverRule.APM_TOPO_CATEGORY_HTTP
                topo_node = TopoNode.objects.filter(
                    bk_biz_id=self.bk_biz_id, app_name=self.app_name, topo_key=messaging_service_name
                ).first()
                # topo_node 存在则更新
                if topo_node:
                    messaging_service_category = topo_node.extra_data.get(
                        "category", ApmTopoDiscoverRule.APM_TOPO_CATEGORY_HTTP
                    )
                    messaging_service_kind = topo_node.extra_data.get("kind", ApmTopoDiscoverRule.TOPO_SERVICE)
                # 针对异步调用中消息队列，messaging --> 服务时， 目标节点类型为service， 目标节点分类为 http
                found_keys.add(
                    (
                        middleware_key,
                        messaging_service_name,
                        kind,
                        messaging_service_kind,
                        messaging_service_category,
                    )
                )
            else:
                found_keys.add(
                    (
                        middleware_to_key,
                        middleware_key,
                        kind,
                        to_span_match_rule.topo_kind,
                        to_span_match_rule.category_id,
                    )
                )

        return found_keys

    def find_normal_relation(self, rules, other_rules, from_key, to_spans, kind):
        found_keys = set()

        for t in to_spans:
            to_span_match_rule = self.get_match_rule(t, rules, other_rules)
            topo_key = get_topo_instance_key(
                to_span_match_rule.instance_keys,
                to_span_match_rule.topo_kind,
                to_span_match_rule.category_id,
                t,
                component_predicate_key=to_span_match_rule.predicate_key,
            )
            if to_span_match_rule.topo_kind == ApmTopoDiscoverRule.TOPO_COMPONENT:
                topo_key = f"{self.get_service_name(t)}-{topo_key}"

            found_keys.add(
                (
                    from_key,
                    topo_key,
                    kind,
                    to_span_match_rule.topo_kind,
                    to_span_match_rule.category_id,
                )
            )

        return found_keys

    def discover(self, origin_data, remain_data=None):
        rules, other_rule = self.get_rules()
        component_rules = [r for r in rules + [other_rule] if r.topo_kind == ApmTopoDiscoverRule.TOPO_COMPONENT]

        relation_mapping = self.get_relation_map(origin_data)
        exist_relations = self.list_exists()

        need_update_relation_ids = set()
        need_create_relations = set()

        for span in origin_data:
            from_key = self.get_service_name(span)
            found_keys = self.find_relation_by_single_span(component_rules, from_key, span, span["kind"])
            for found_key in found_keys:
                if found_key in exist_relations:
                    need_update_relation_ids |= exist_relations[found_key]
                else:
                    need_create_relations.add(found_key)

        for relation in relation_mapping.values():
            if not relation["to"] and not relation["from"]:
                continue

            from_span = relation["from"]
            from_key = self.get_service_name(from_span)
            kind = relation["kind"]

            found_keys = set()

            if kind == TopoRelation.RELATION_KIND_ASYNC and self.is_match_component_rule(component_rules, from_span):
                found_keys |= self.find_async_relation(rules, other_rule, from_key, from_span, relation["to"], kind)
            else:
                found_keys |= self.find_normal_relation(rules, other_rule, from_key, relation["to"], kind)

            for found_key in found_keys:
                if found_key in exist_relations:
                    need_update_relation_ids |= exist_relations[found_key]
                else:
                    need_create_relations.add(found_key)

        # only update update_time
        TopoRelation.objects.filter(id__in=need_update_relation_ids).update(updated_at=datetime.now())

        # create
        TopoRelation.objects.bulk_create(
            [
                TopoRelation(
                    bk_biz_id=self.bk_biz_id,
                    app_name=self.app_name,
                    from_topo_key=i[0],
                    to_topo_key=i[1],
                    kind=i[2],
                    to_topo_key_kind=i[3],
                    to_topo_key_category=i[4],
                )
                for i in need_create_relations
            ]
        )

        self.clear_if_overflow()
        self.clear_expired()
