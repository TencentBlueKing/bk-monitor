# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import datetime
from urllib.parse import urljoin, urlparse

from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm_web.models import Application
from constants.apm import OtlpKey
from core.drf_resource import api


class SpanHandler:
    @classmethod
    def get_day_edge(cls):
        now = datetime.datetime.now()
        before_day = now - datetime.timedelta(days=1)

        return int(str(int(before_day.timestamp())) + "000000"), int(str(int(now.timestamp())) + "000000")

    @classmethod
    def get_lastly_span(cls, bk_biz_id, app_name):
        """获取一天内最近一条span"""
        app = Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
        start, end = cls.get_day_edge()
        response = api.apm_api.query_es(
            table_id=app.trace_result_table_id,
            query_body={
                "from": 0,
                "size": 1,
                "sort": {"start_time": {"order": "desc"}},
                "query": {"range": {"start_time": {"gt": start, "lte": end}}},
            },
        )

        data = response.get("hits", {}).get("hits")
        if not data:
            return None

        return data[0]["_source"]

    @classmethod
    def _get_key_pair(cls, key):
        pair = key.split(".", 1)
        if len(pair) == 1:
            return "", pair[0]
        return pair[0], pair[1]

    @classmethod
    def get_span_field_value(cls, span, key):
        if not span:
            return None

        first, second = cls._get_key_pair(key)
        first_item = span.get(first, span)
        if not isinstance(first_item, dict):
            return None

        return first_item.get(second, "")

    @classmethod
    def get_span_urls(cls, app, start_time, end_time, service_name=None):
        """获取100条 span url字段数据"""
        query = {
            "size": 0,
            "query": {
                "bool": {
                    "filter": [
                        {
                            "range": {
                                "end_time": {
                                    "gt": start_time.timestamp() * 1000 * 1000,
                                    "lte": end_time.timestamp() * 1000 * 1000,
                                }
                            }
                        }
                    ]
                }
            },
            "aggs": {
                "unique_urls": {"terms": {"field": OtlpKey.get_attributes_key(SpanAttributes.HTTP_URL), "size": 100}}
            },
        }
        if service_name:
            query["query"]["bool"]["filter"].append(
                {"term": {OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME): service_name}}
            )

        response = api.apm_api.query_es(table_id=app.trace_result_table_id, query_body=query)
        return list(
            {i["key"] for i in response.get("aggregations", {}).get("unique_urls", {}).get("buckets", []) if i["key"]}
        )

    @classmethod
    def get_span_uris(cls, app, start_time, end_time, service_name=None):
        urls = cls.get_span_urls(app, start_time, end_time, service_name)
        res = []
        for url in urls:
            url_parse = urlparse(url)
            res.append(cls.generate_uri(url_parse))

        return list(set(res))

    @classmethod
    def generate_uri(cls, url_parser):
        return urljoin(f"{url_parser.scheme}://{url_parser.netloc}", url_parser.path).rstrip("/")
