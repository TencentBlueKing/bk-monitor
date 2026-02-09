"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from opentelemetry.semconv.resource import ResourceAttributes

from apm.constants import ApmCacheType
from apm.core.discover.base import DiscoverBase, extract_field_value
from apm.core.discover.cached_mixin import CachedDiscoverMixin
from apm.core.discover.instance_data import RootEndpointInstanceData
from apm.models import RootEndpoint
from constants.apm import OtlpKey, SpanKind

logger = logging.getLogger("apm")


class RootEndpointDiscover(CachedDiscoverMixin, DiscoverBase):
    """
    RootEndpoint 发现类
    使用多继承: CachedDiscoverMixin 提供缓存功能, DiscoverBase 提供基础发现功能
    """

    DISCOVERY_ALL_SPANS = False
    MAX_COUNT = 100000
    CACHE_KEY_SPLIT = ":"
    model = RootEndpoint

    @classmethod
    def _get_cache_type(cls) -> str:
        """获取缓存类型"""
        return ApmCacheType.ROOT_ENDPOINT

    @classmethod
    def to_cache_key(cls, instance: RootEndpointInstanceData) -> str:
        """从实例数据对象生成 root_endpoint 缓存 key"""
        return cls.CACHE_KEY_SPLIT.join(map(str, cls._to_found_key(instance)))

    @classmethod
    def build_instance_data(cls, root_endpoint_obj) -> RootEndpointInstanceData:
        return RootEndpointInstanceData(
            id=DiscoverBase.get_attr_value(root_endpoint_obj, "id"),
            endpoint_name=DiscoverBase.get_attr_value(root_endpoint_obj, "endpoint_name"),
            service_name=DiscoverBase.get_attr_value(root_endpoint_obj, "service_name"),
            category_id=DiscoverBase.get_attr_value(root_endpoint_obj, "category_id"),
            updated_at=DiscoverBase.get_attr_value(root_endpoint_obj, "updated_at"),
        )

    @classmethod
    def _to_found_key(cls, instance_data: RootEndpointInstanceData) -> tuple:
        """从实例数据对象生成业务唯一标识（不包含数据库ID）用于在 discover 过程中匹配已存在的实例"""
        return instance_data.endpoint_name, instance_data.service_name, instance_data.category_id

    def group_by_trace_id(self, spans):
        """按 trace_id 对 spans 进行分组并排序"""
        res = {}
        for span in spans:
            res.setdefault(span[OtlpKey.TRACE_ID], []).append(span)

        for trace_spans in res.values():
            trace_spans.sort(key=lambda i: (i[OtlpKey.START_TIME], -i[OtlpKey.ELAPSED_TIME]))

        return res

    def get_remain_data(self):
        instances = self.model.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        return self.process_duplicate_records(instances, True)

    def discover(self, origin_data, remain_data: dict[tuple, RootEndpointInstanceData]):
        """
        Discover Root Endpoint
        Rule:
            Trace Spans Sort by start time + elapsed time
        """
        rules, other_rule = self.get_rules()

        need_update_instances = list()
        need_create_instances = set()

        for _, trace_spans in self.group_by_trace_id(origin_data).items():
            first_span = next(
                (i for i in trace_spans if i[OtlpKey.KIND] in [SpanKind.SPAN_KIND_SERVER, SpanKind.SPAN_KIND_PRODUCER]),
                None,
            )

            if not first_span:
                continue

            match_rule = self.get_match_rule(first_span, rules, other_rule)

            endpoint_name = extract_field_value(match_rule.endpoint_key, first_span)
            service_name = extract_field_value((OtlpKey.RESOURCE, ResourceAttributes.SERVICE_NAME), first_span)

            found_key = (endpoint_name, service_name, match_rule.category_id)

            if found_key in remain_data:
                need_update_instances.append(remain_data[found_key])
            else:
                need_create_instances.add(found_key)

        created_instances = [
            RootEndpoint(
                bk_biz_id=self.bk_biz_id,
                app_name=self.app_name,
                endpoint_name=i[0],
                service_name=i[1],
                category_id=i[2],
            )
            for i in need_create_instances
        ]
        RootEndpoint.objects.bulk_create(created_instances)

        # 使用抽象方法处理缓存刷新
        self.handle_cache_refresh_after_create(
            existing_instances=list(remain_data.values()),
            created_db_instances=created_instances,
            updated_instances=need_update_instances,
        )
