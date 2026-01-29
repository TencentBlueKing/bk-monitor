"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm.constants import ApmCacheType
from apm.core.discover.base import (
    DiscoverBase,
    exists_field,
    extract_field_value,
    get_topo_instance_key,
)
from apm.core.discover.cached_mixin import CachedDiscoverMixin
from apm.core.discover.instance_data import EndpointInstanceData
from apm.models import ApmTopoDiscoverRule, Endpoint, TraceDataSource
from constants.apm import OtlpKey


class EndpointDiscover(CachedDiscoverMixin, DiscoverBase):
    MAX_COUNT = 100000
    model = Endpoint

    # ========== 实现 CachedDiscoverMixin 抽象方法 ==========

    @classmethod
    def _get_cache_type(cls) -> str:
        """获取缓存类型"""
        return ApmCacheType.ENDPOINT

    @classmethod
    def _to_instance_key(cls, instance: EndpointInstanceData) -> str:
        """从实例数据对象生成实例key"""
        endpoint_name = instance.endpoint_name
        service_name = instance.service_name
        category_id = instance.category_id
        category_kind_key = instance.category_kind_key
        category_kind_value = instance.category_kind_value
        span_kind = instance.span_kind
        return f"{span_kind}:{category_kind_value}:{category_kind_key}:{category_id}:{service_name}:{endpoint_name}"

    @staticmethod
    def _build_instance_data(endpoint_obj) -> EndpointInstanceData:
        """构建端点数据对象的辅助方法"""
        return EndpointInstanceData(
            id=CachedDiscoverMixin._get_attr_value(endpoint_obj, "id"),
            service_name=CachedDiscoverMixin._get_attr_value(endpoint_obj, "service_name"),
            endpoint_name=CachedDiscoverMixin._get_attr_value(endpoint_obj, "endpoint_name"),
            category_id=CachedDiscoverMixin._get_attr_value(endpoint_obj, "category_id"),
            category_kind_key=CachedDiscoverMixin._get_attr_value(endpoint_obj, "category_kind_key"),
            category_kind_value=CachedDiscoverMixin._get_attr_value(endpoint_obj, "category_kind_value"),
            span_kind=CachedDiscoverMixin._get_attr_value(endpoint_obj, "span_kind"),
            updated_at=CachedDiscoverMixin._get_attr_value(endpoint_obj, "updated_at"),
        )

    def list_exists(self):
        endpoints = Endpoint.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        # 使用 Mixin 提供的通用方法处理重复数据，endpoint 需要删除重复记录
        return self._process_duplicate_records(endpoints, delete_duplicates=True)

    def discover(self, origin_data, exists_endpoints: dict[str, EndpointInstanceData]):
        """
        Endpoint name according to endpoint_key in discover rule
        """
        rules, other_rule = self.get_rules()

        need_update_instances = list()
        need_create_instances = set()

        for span in origin_data:
            found_keys = []

            # Step1: 找普通接口
            match_rule = self.get_match_rule(span, rules, other_rule)
            endpoint_name = extract_field_value(match_rule.endpoint_key, span)
            service_name = extract_field_value((OtlpKey.RESOURCE, ResourceAttributes.SERVICE_NAME), span)
            category_kind_key, category_kind_value = TraceDataSource.get_category_kind(span[OtlpKey.ATTRIBUTES])
            span_kind = span.get(OtlpKey.KIND)
            found_keys.append(
                (
                    endpoint_name,
                    service_name,
                    match_rule.category_id,
                    category_kind_key,
                    category_kind_value,
                    span_kind,
                )
            )
            # Step2: 找自定义服务接口
            if exists_field((OtlpKey.ATTRIBUTES, SpanAttributes.PEER_SERVICE), span):
                peer_service_topo_key = get_topo_instance_key(
                    [(OtlpKey.ATTRIBUTES, SpanAttributes.PEER_SERVICE)],
                    ApmTopoDiscoverRule.TOPO_REMOTE_SERVICE,
                    match_rule.category_id,
                    span,
                )
                found_keys.append(
                    (
                        endpoint_name,
                        peer_service_topo_key,
                        match_rule.category_id,
                        category_kind_key,
                        category_kind_value,
                        span_kind,
                    )
                )

            for k in found_keys:
                temp_data = EndpointInstanceData(
                    endpoint_name=k[0],
                    service_name=k[1],
                    category_id=k[2],
                    category_kind_key=k[3],
                    category_kind_value=k[4],
                    span_kind=k[5],
                )
                key_str = self._to_instance_key(temp_data)
                if key_str in exists_endpoints:
                    need_update_instances.append(exists_endpoints[key_str])
                else:
                    need_create_instances.add(k)

        created_instances = [
            Endpoint(
                bk_biz_id=self.bk_biz_id,
                app_name=self.app_name,
                endpoint_name=i[0],
                service_name=i[1],
                category_id=i[2],
                category_kind_key=i[3],
                category_kind_value=i[4],
                span_kind=i[5],
            )
            for i in need_create_instances
        ]
        Endpoint.objects.bulk_create(created_instances)

        # 使用抽象方法处理缓存刷新
        self.handle_cache_refresh_after_create(
            existing_instances=list(exists_endpoints.values()),
            created_db_instances=created_instances,
            updated_instances=need_update_instances,
        )
