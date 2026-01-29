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
    def _to_instance_key(cls, instance: dict) -> str:
        """从实例字典生成实例key"""
        endpoint_name = instance.get("endpoint_name")
        service_name = instance.get("service_name")
        category_id = instance.get("category_id")
        category_kind_key = instance.get("category_kind_key")
        category_kind_value = instance.get("category_kind_value")
        span_kind = instance.get("span_kind")
        return f"{span_kind}:{category_kind_value}:{category_kind_key}:{category_id}:{service_name}:{endpoint_name}"

    @classmethod
    def _tuple_to_instance_dict(cls, tuple_data: tuple) -> dict:
        """
        将元组数据转换为实例字典
        元组格式: (endpoint_name, service_name, category_id, category_kind_key, category_kind_value, span_kind)
        """
        return {
            "id": None,
            "endpoint_name": tuple_data[0],
            "service_name": tuple_data[1],
            "category_id": tuple_data[2],
            "category_kind_key": tuple_data[3],
            "category_kind_value": tuple_data[4],
            "span_kind": tuple_data[5],
            "updated_at": None,
        }

    # ========== EndpointDiscover 特有方法 ==========

    @staticmethod
    def _build_endpoint_dict(endpoint_obj, include_updated_at=False):
        """构建端点字典的辅助方法"""

        def get_attr(obj, attr_name):
            """统一的属性获取方法"""
            if hasattr(obj, attr_name):
                return getattr(obj, attr_name)
            return obj.get(attr_name) if isinstance(obj, dict) else None

        base_dict = {
            "id": get_attr(endpoint_obj, "id"),
            "service_name": get_attr(endpoint_obj, "service_name"),
            "endpoint_name": get_attr(endpoint_obj, "endpoint_name"),
            "category_id": get_attr(endpoint_obj, "category_id"),
            "category_kind_key": get_attr(endpoint_obj, "category_kind_key"),
            "category_kind_value": get_attr(endpoint_obj, "category_kind_value"),
            "span_kind": get_attr(endpoint_obj, "span_kind"),
        }

        if include_updated_at:
            base_dict["updated_at"] = get_attr(endpoint_obj, "updated_at")

        return base_dict

    def list_exists(self):
        endpoints = Endpoint.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        exists_mapping = {}
        for e in endpoints:
            exists_mapping.setdefault(
                (
                    e.endpoint_name,
                    e.service_name,
                    e.category_id,
                    e.category_kind_key,
                    e.category_kind_value,
                    e.span_kind,
                ),
                [],
            ).append(self._build_endpoint_dict(e, include_updated_at=True))

        # 处理重复数据并构建最终结果
        res = {}
        need_delete_ids = []
        instance_data = []

        for key, records in exists_mapping.items():
            records.sort(key=lambda x: x["id"])
            keep_record = records[0]
            # 收集需要删除的ID
            if len(records) > 1:
                need_delete_ids.extend([r["id"] for r in records[1:]])

            # 保留的记录 - 使用辅助方法构建字典
            res[key] = self._build_endpoint_dict(keep_record)
            instance_data.append(self._build_endpoint_dict(keep_record, include_updated_at=True))

        # 执行数据库删除操作
        if need_delete_ids:
            self.model.objects.filter(id__in=need_delete_ids).delete()

        return res, instance_data

    def get_remain_data(self):
        return self.list_exists()

    def discover_with_remain_data(self, origin_data, remain_data):
        """
        Endpoint name according to endpoint_key in discover rule
        """
        exists_endpoints, instance_data = remain_data
        self._do_discover(exists_endpoints, instance_data, origin_data)

    def discover(self, origin_data):
        """
        Endpoint name according to endpoint_key in discover rule
        """
        exists_endpoints, instance_data = self.list_exists()
        self._do_discover(exists_endpoints, instance_data, origin_data)

    def _do_discover(
        self,
        exists_endpoints,
        instance_data,
        origin_data,
    ):
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
                if k in exists_endpoints:
                    need_update_instances.append(exists_endpoints[k])
                else:
                    need_create_instances.add(k)

        Endpoint.objects.bulk_create(
            [
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
        )

        # 使用抽象方法处理缓存刷新
        self.handle_cache_refresh_after_create(
            instance_data=instance_data,
            need_create_instances=need_create_instances,
            need_update_instances=need_update_instances,
        )
