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

from opentelemetry.semconv.resource import ResourceAttributes

from apm.core.discover.base import DiscoverBase, extract_field_value
from apm.models import RootEndpoint
from constants.apm import OtlpKey, SpanKind


class RootEndpointDiscover(DiscoverBase):
    MAX_COUNT = 100000
    model = RootEndpoint

    def group_by_trace_id(self, spans):
        res = {}
        for span in spans:
            res.setdefault(span[OtlpKey.TRACE_ID], []).append(span)

        for trace_spans in res.values():
            [].sort()
            trace_spans.sort(key=lambda i: (i[OtlpKey.START_TIME], -i[OtlpKey.ELAPSED_TIME]))

        return res

    def list_exists(self):
        endpoints = RootEndpoint.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        res = {}
        for e in endpoints:
            res.setdefault((e.endpoint_name, e.service_name, e.category_id), set()).add(e.id)

        return res

    def discover(self, origin_data, remain_data=None):
        """
        Calc the Root Endpoint
        Rule:
            Trace Spans Sort by start time + elapsed time
        """

        rules, other_rule = self.get_rules()

        need_update_endpoint_ids = set()
        need_create_endpoints = set()

        exists_endpoints = self.list_exists()

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

            if found_key in exists_endpoints:
                need_update_endpoint_ids |= exists_endpoints[found_key]
            else:
                need_create_endpoints.add(found_key)

        # only update update_time
        RootEndpoint.objects.filter(id__in=need_update_endpoint_ids).update(updated_at=datetime.now())

        # create
        RootEndpoint.objects.bulk_create(
            [
                RootEndpoint(
                    bk_biz_id=self.bk_biz_id,
                    app_name=self.app_name,
                    endpoint_name=i[0],
                    service_name=i[1],
                    category_id=i[2],
                )
                for i in need_create_endpoints
            ]
        )

        self.clear_if_overflow()
        self.clear_expired()
