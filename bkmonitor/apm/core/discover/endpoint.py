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
from datetime import datetime

from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm.core.discover.base import (
    DiscoverBase,
    exists_field,
    extract_field_value,
    get_topo_instance_key,
)
from apm.models import ApmTopoDiscoverRule, Endpoint, TraceDataSource
from constants.apm import OtlpKey


class EndpointDiscover(DiscoverBase):
    MAX_COUNT = 100000
    model = Endpoint

    def list_exists(self):
        res = {}
        endpoints = Endpoint.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        for e in endpoints:
            res.setdefault(
                (
                    e.endpoint_name,
                    e.service_name,
                    e.category_id,
                    e.category_kind_key,
                    e.category_kind_value,
                    e.span_kind,
                ),
                set(),
            ).add(e.id)

        return self.get_and_clear_if_repeat(res)

    def discover(self, origin_data):
        """
        Endpoint name according to endpoint_key in discover rule
        """
        rules, other_rule = self.get_rules()

        exists_endpoints = self.list_exists()

        need_update_instance_ids = set()
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
                    need_update_instance_ids |= exists_endpoints[k]
                else:
                    need_create_instances.add(k)

        # only update update_time
        Endpoint.objects.filter(id__in=need_update_instance_ids).update(updated_at=datetime.now())

        # create
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

        self.clear_if_overflow()
        self.clear_expired()
