"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from opentelemetry.semconv.trace import SpanAttributes

from apm.constants import ApmCacheType
from apm.core.discover.base import (
    DiscoverBase,
    exists_field,
    extract_field_value,
    get_topo_instance_key,
)
from apm.core.discover.cached_mixin import CachedDiscoverMixin
from apm.core.discover.instance_data import RemoteServiceRelationInstanceData
from apm.models import ApmTopoDiscoverRule, RemoteServiceRelation
from constants.apm import OtlpKey


class RemoteServiceRelationDiscover(CachedDiscoverMixin, DiscoverBase):
    """
    RemoteServiceRelation 发现类
    使用多继承: CachedDiscoverMixin 提供缓存功能, DiscoverBase 提供基础发现功能
    """

    DISCOVERY_ALL_SPANS = True
    MAX_COUNT = 100000
    RELATION_KEY_SPLIT = ":"
    model = RemoteServiceRelation

    @classmethod
    def _get_cache_type(cls) -> str:
        """获取缓存类型"""
        return ApmCacheType.REMOTE_SERVICE_RELATION

    @classmethod
    def to_cache_key(cls, instance: RemoteServiceRelationInstanceData) -> str:
        """从实例数据对象生成缓存 key"""
        return cls.RELATION_KEY_SPLIT.join(map(str, cls._to_found_key(instance)))

    @classmethod
    def build_instance_data(cls, relation_obj) -> RemoteServiceRelationInstanceData:
        return RemoteServiceRelationInstanceData(
            id=DiscoverBase.get_attr_value(relation_obj, "id"),
            topo_node_key=DiscoverBase.get_attr_value(relation_obj, "topo_node_key"),
            from_endpoint_name=DiscoverBase.get_attr_value(relation_obj, "from_endpoint_name"),
            category=DiscoverBase.get_attr_value(relation_obj, "category"),
            updated_at=DiscoverBase.get_attr_value(relation_obj, "updated_at"),
        )

    @classmethod
    def _to_found_key(cls, instance_data: RemoteServiceRelationInstanceData) -> tuple:
        """从实例数据对象生成业务唯一标识（不包含数据库ID）用于在 discover 过程中匹配已存在的实例"""
        return instance_data.topo_node_key, instance_data.from_endpoint_name, instance_data.category

    def get_remain_data(self):
        instances = self.model.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        return self.process_duplicate_records(instances, True)

    def discover(self, origin_data, remain_data: dict[tuple, RemoteServiceRelationInstanceData]):
        rules, other_rule = self.get_rules()

        without_peer_mapping = {}
        with_peer_spans_mapping = {}
        for span in origin_data:
            (without_peer_mapping, with_peer_spans_mapping)[
                exists_field((OtlpKey.ATTRIBUTES, SpanAttributes.PEER_SERVICE), span)
            ][span[OtlpKey.SPAN_ID]] = span

        need_update_instances = []
        need_create_instances = set()

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
            if found_key in remain_data:
                need_update_instances.append(remain_data[found_key])
            else:
                need_create_instances.add(found_key)

        created_instances = [
            RemoteServiceRelation(
                bk_biz_id=self.bk_biz_id,
                app_name=self.app_name,
                topo_node_key=i[0],
                from_endpoint_name=i[1],
                category=i[2],
            )
            for i in need_create_instances
        ]
        RemoteServiceRelation.objects.bulk_create(created_instances)

        # 使用抽象方法处理缓存刷新
        self.handle_cache_refresh_after_create(
            existing_instances=list(remain_data.values()),
            created_db_instances=created_instances,
            updated_instances=need_update_instances,
        )

    def get_parent_endpoint(self, rules, other_rule, parent_span):
        rule = next((r for r in rules if exists_field(r.predicate_key, parent_span)), other_rule)
        return rule.category_id, extract_field_value(rule.endpoint_key, parent_span)
