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
import logging

from opentelemetry.semconv.trace import SpanAttributes

from apm.constants import ApmCacheType
from apm.core.discover.base import DiscoverBase, exists_field, get_topo_instance_key
from apm.core.discover.cached_mixin import CachedDiscoverMixin
from apm.core.discover.instance_data import RelationInstanceData
from apm.models import ApmTopoDiscoverRule, TopoNode, TopoRelation, TraceDataSource
from constants.apm import OtlpKey, SpanKind

logger = logging.getLogger("apm")


class RelationDiscover(CachedDiscoverMixin, DiscoverBase):
    """
    Relation 发现类
    使用多继承: CachedDiscoverMixin 提供缓存功能, DiscoverBase 提供基础发现功能
    """

    MAX_COUNT = 100000
    model = TopoRelation
    RELATION_SPLIT = ":"

    @classmethod
    def _get_cache_type(cls) -> str:
        """获取缓存类型"""
        return ApmCacheType.RELATION

    @classmethod
    def to_cache_key(cls, instance: RelationInstanceData) -> str:
        """从实例数据对象生成 relation 缓存 key"""
        return cls.RELATION_SPLIT.join(map(str, cls._to_found_key(instance)))

    @classmethod
    def build_instance_data(cls, relation_obj) -> RelationInstanceData:
        return RelationInstanceData(
            id=DiscoverBase.get_attr_value(relation_obj, "id"),
            from_topo_key=DiscoverBase.get_attr_value(relation_obj, "from_topo_key"),
            to_topo_key=DiscoverBase.get_attr_value(relation_obj, "to_topo_key"),
            kind=DiscoverBase.get_attr_value(relation_obj, "kind"),
            to_topo_key_kind=DiscoverBase.get_attr_value(relation_obj, "to_topo_key_kind"),
            to_topo_key_category=DiscoverBase.get_attr_value(relation_obj, "to_topo_key_category"),
            updated_at=DiscoverBase.get_attr_value(relation_obj, "updated_at"),
        )

    @classmethod
    def _to_found_key(cls, instance_data: RelationInstanceData) -> tuple:
        """从实例数据对象生成业务唯一标识（不包含数据库ID）用于在 discover 过程中匹配已存在的实例"""
        return (
            instance_data.from_topo_key,
            instance_data.to_topo_key,
            instance_data.kind,
            instance_data.to_topo_key_kind,
            instance_data.to_topo_key_category,
        )

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

    def find_relation_by_single_span(self, component_rules, from_key, from_span, kind, service_edges):
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
                    service_edges[from_key].add((to_key, relation_kind))

        return found_keys

    def is_match_component_rule(self, component_rules, from_span):
        return bool(next((r for r in component_rules if exists_field(r.predicate_key, from_span)), None))

    def find_async_relation(self, rules, other_rules, from_key, from_span, to_spans, kind, service_edges):
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
                service_edges[messaging_service_name].add((middleware_key, kind))
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

    def get_remain_data(self):
        instances = self.model.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        return self.process_duplicate_records(instances, True)

    def discover(self, origin_data, remain_data: dict[tuple, RelationInstanceData]):
        rules, other_rule = self.get_rules()
        component_rules = [r for r in rules + [other_rule] if r.topo_kind == ApmTopoDiscoverRule.TOPO_COMPONENT]

        relation_mapping = self.get_relation_map(origin_data)

        found_keys = set()
        service_edges = defaultdict(set)
        for span in origin_data:
            from_key = self.get_service_name(span)
            found_keys.update(
                self.find_relation_by_single_span(component_rules, from_key, span, span["kind"], service_edges)
            )

        for relation in relation_mapping.values():
            if not relation["to"] and not relation["from"]:
                continue

            from_span = relation["from"]
            from_key = self.get_service_name(from_span)
            kind = relation["kind"]

            if kind == TopoRelation.RELATION_KIND_ASYNC and self.is_match_component_rule(component_rules, from_span):
                found_keys.update(
                    self.find_async_relation(
                        rules, other_rule, from_key, from_span, relation["to"], kind, service_edges
                    )
                )
            else:
                found_keys.update(self.find_normal_relation(rules, other_rule, from_key, relation["to"], kind))

        # 节点发现与关系发现并行，在写关系前读取本页目标服务的当前分类。
        for service_name, edges in service_edges.items():
            node = (
                TopoNode.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name, topo_key=service_name)
                .only("extra_data")
                .first()
            )
            extra_data = node.extra_data if node else {}
            service_kind = extra_data.get("kind", ApmTopoDiscoverRule.TOPO_SERVICE)
            category = extra_data.get("category", ApmTopoDiscoverRule.APM_TOPO_CATEGORY_HTTP)
            found_keys.update((source, service_name, edge_kind, service_kind, category) for source, edge_kind in edges)

        need_create_relations = found_keys.difference(remain_data)
        need_update_instances = [remain_data[key] for key in found_keys if key in remain_data]

        created_instances = [
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
        TopoRelation.objects.bulk_create(created_instances)

        self.handle_cache_refresh_after_create(
            existing_instances=list(remain_data.values()),
            remain_data=remain_data,
            created_db_instances=created_instances,
            updated_instances=need_update_instances,
        )
