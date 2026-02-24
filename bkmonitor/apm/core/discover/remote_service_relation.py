"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import datetime

from opentelemetry.semconv.trace import SpanAttributes

from apm.core.discover.base import (
    DiscoverBase,
    exists_field,
    extract_field_value,
    get_topo_instance_key,
)
from apm.models import ApmTopoDiscoverRule, RemoteServiceRelation
from constants.apm import OtlpKey


class RemoteServiceRelationDiscover(DiscoverBase):
    MAX_COUNT = 100000
    model = RemoteServiceRelation

    def list_exists(self):
        res = {}
        relations = RemoteServiceRelation.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        for r in relations:
            res.setdefault((r.topo_node_key, r.from_endpoint_name, r.category), set()).add(r.id)

        return res

    def discover(self, origin_data, remain_data=None):
        rules, other_rule = self.get_rules()

        without_peer_mapping = {}
        with_peer_spans_mapping = {}
        for span in origin_data:
            (without_peer_mapping, with_peer_spans_mapping)[
                exists_field((OtlpKey.ATTRIBUTES, SpanAttributes.PEER_SERVICE), span)
            ][span[OtlpKey.SPAN_ID]] = span

        exists_relations = self.list_exists()
        need_update_relation_ids = set()
        need_create_relations = set()

        for span_id, span in with_peer_spans_mapping.items():
            match_rule = self.get_match_rule(span, rules, other_rule)
            parent_span_id = span[OtlpKey.PARENT_SPAN_ID]
            if not parent_span_id or parent_span_id not in without_peer_mapping:
                continue

            topo_node_key = get_topo_instance_key(
                [(OtlpKey.ATTRIBUTES, SpanAttributes.PEER_SERVICE)],
                ApmTopoDiscoverRule.TOPO_REMOTE_SERVICE,
                match_rule.category_id,
                span,
            )
            category, endpoint_name = self.get_parent_endpoint(rules, other_rule, without_peer_mapping[parent_span_id])

            found_key = (topo_node_key, endpoint_name, category)
            if found_key in exists_relations:
                need_update_relation_ids |= exists_relations[found_key]
            else:
                need_create_relations.add(found_key)

        # only update update_time
        RemoteServiceRelation.objects.filter(id__in=need_update_relation_ids).update(updated_at=datetime.now())

        # create
        RemoteServiceRelation.objects.bulk_create(
            [
                RemoteServiceRelation(
                    bk_biz_id=self.bk_biz_id,
                    app_name=self.app_name,
                    topo_node_key=i[0],
                    from_endpoint_name=i[1],
                    category=i[2],
                )
                for i in need_create_relations
            ]
        )

        self.clear_if_overflow()
        self.clear_expired()

    def get_parent_endpoint(self, rules, other_rule, parent_span):
        rule = next((r for r in rules if exists_field(r.predicate_key, parent_span)), other_rule)
        return rule.category_id, extract_field_value(rule.endpoint_key, parent_span)
