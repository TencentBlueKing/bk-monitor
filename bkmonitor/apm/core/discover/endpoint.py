"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time
from datetime import datetime, timedelta

import pytz
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm.constants import DEFAULT_ENDPOINT_EXPIRE
from apm.core.discover.base import (
    DiscoverBase,
    exists_field,
    extract_field_value,
    get_topo_instance_key,
)
from apm.core.handlers.apm_cache_handler import ApmCacheHandler
from apm.models import ApmTopoDiscoverRule, Endpoint, TraceDataSource
from constants.apm import OtlpKey


class EndpointDiscover(DiscoverBase):
    MAX_COUNT = 100000
    model = Endpoint

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

    @classmethod
    def to_instance_key(
        cls, endpoint_name, service_name, category_id, category_kind_key, category_kind_value, span_kind
    ):
        """修改为基于六元组的key生成"""
        return f"{span_kind}:{category_kind_value}:{category_kind_key}:{category_id}:{service_name}:{endpoint_name}"

    @classmethod
    def _extract_instance_key_params(cls, inst):
        """提取实例key参数的辅助方法"""
        return (
            inst.get("endpoint_name"),
            inst.get("service_name"),
            inst.get("category_id"),
            inst.get("category_kind_key"),
            inst.get("category_kind_value"),
            inst.get("span_kind"),
        )

    @classmethod
    def to_id_and_key(cls, instances: list):
        """修改为基于六元组生成keys"""
        ids, keys = set(), set()
        for inst in instances:
            inst_id = str(inst.get("id"))
            inst_key = cls.to_instance_key(*cls._extract_instance_key_params(inst))
            keys.add(inst_key)
            ids.add(inst_id)

        return ids, keys

    @classmethod
    def merge_data(cls, endpoint_data: list[dict], cache_data: dict):
        merge_data = []
        for obj in endpoint_data:
            key = cls.to_instance_key(*cls._extract_instance_key_params(obj))
            if key in cache_data:
                obj["updated_at"] = datetime.fromtimestamp(cache_data.get(key), tz=pytz.UTC)
            merge_data.append(obj)

        return merge_data

    def instance_clear_if_overflow(self, instances: list):
        overflow_delete_data = []
        count = len(instances)
        if count > self.MAX_COUNT:
            delete_count = count - self.MAX_COUNT
            instances.sort(key=lambda x: x["updated_at"])
            overflow_delete_data = instances[:delete_count]
            remain_instance_data = instances[delete_count:]
        else:
            remain_instance_data = instances
        return overflow_delete_data, remain_instance_data

    def instance_clear_expired(self, instances: list):
        """
        清除过期数据
        :param instances: 实例数据
        :return:
        """
        # mysql 中的 updated_at 时间字段, 它的时区是 UTC, 跟数据库保持一致
        boundary = datetime.now(tz=pytz.UTC) - timedelta(days=self.application.trace_datasource.retention)
        # 按照时间进行过滤
        expired_delete_data = []
        remain_instance_data = []
        for instance in instances:
            if instance.get("updated_at") <= boundary:
                expired_delete_data.append(instance)
            else:
                remain_instance_data.append(instance)
        return expired_delete_data, remain_instance_data

    def query_cache_data(self):
        cache_name = ApmCacheHandler.get_endpoint_cache_key(self.bk_biz_id, self.app_name)
        return ApmCacheHandler().get_cache_data(cache_name)

    def clear_data(self, cache_data, instance_data) -> set:
        """
        数据清除
        :param cache_data: 缓存数据
        :param instance_data: mysql 数据
        :return:
        """
        merge_data = self.merge_data(instance_data, cache_data)
        # 过期数据
        expired_delete_data, remain_instance_data = self.instance_clear_expired(merge_data)
        # 超量数据
        overflow_delete_data, remain_instance_data = self.instance_clear_if_overflow(remain_instance_data)
        delete_data = expired_delete_data + overflow_delete_data

        delete_ids, delete_keys = self.to_id_and_key(delete_data)
        if delete_ids:
            self.model.objects.filter(pk__in=delete_ids).delete()

        return delete_keys

    def refresh_cache_data(
        self, old_cache_data: dict, create_instance_keys: set, update_instance_keys: set, delete_instance_keys: set
    ):
        now = int(time.time())

        cache_data = {key: val for key, val in old_cache_data.items() if key not in delete_instance_keys}
        cache_data.update({key: now for key in create_instance_keys | update_instance_keys})
        name = ApmCacheHandler.get_endpoint_cache_key(self.bk_biz_id, self.app_name)
        ApmCacheHandler().refresh_data(name, cache_data, DEFAULT_ENDPOINT_EXPIRE)

    def discover(self, origin_data):
        """
        Endpoint name according to endpoint_key in discover rule
        """
        rules, other_rule = self.get_rules()

        exists_endpoints, instance_data = self.list_exists()

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

        cache_data = self.query_cache_data()
        delete_instance_keys = self.clear_data(cache_data, instance_data)

        # 修改为基于六元组生成缓存key
        create_instance_keys = set()
        for i in need_create_instances:
            key = self.to_instance_key(i[0], i[1], i[2], i[3], i[4], i[5])
            create_instance_keys.add(key)

        _, update_instance_keys = self.to_id_and_key(need_update_instances)
        self.refresh_cache_data(
            old_cache_data=cache_data,
            create_instance_keys=create_instance_keys,
            update_instance_keys=update_instance_keys,
            delete_instance_keys=delete_instance_keys,
        )
