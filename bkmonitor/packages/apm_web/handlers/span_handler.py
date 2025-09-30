"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm_web.models import Application
from constants.apm import OtlpKey
from core.drf_resource import api


class SpanHandler:
    @classmethod
    def get_lastly_span(cls, bk_biz_id, app_name):
        """获取一天内最近一条span"""
        app = Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
        if not app.trace_result_table_id:
            # 未开启 trace，这里直接返回空
            return None

        end: int = int(datetime.datetime.now().timestamp())
        # 先从一个较小的时间范围内查询，加快有数据应用的查询速度。
        for duration in [datetime.timedelta(minutes=5), datetime.timedelta(hours=6), datetime.timedelta(days=1)]:
            try:
                return api.apm_api.query_span(
                    {
                        "bk_biz_id": app.bk_biz_id,
                        "app_name": app.app_name,
                        "start_time": int(end - duration.total_seconds()),
                        "end_time": end,
                        "limit": 1,
                    }
                )[0]
            except IndexError:
                continue

        return None

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
    def get_span_urls(
        cls, app: Application, start_time: datetime.datetime, end_time: datetime.datetime, service_name: str = None
    ):
        """获取 500 条 attributes.http.url 候选项"""
        filters: list[dict[str, Any]] = []
        if service_name:
            filters.append(
                {
                    "key": OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME),
                    "operator": "equal",
                    "value": [service_name],
                }
            )

        field: str = OtlpKey.get_attributes_key(SpanAttributes.HTTP_URL)
        field_options: dict[str, list[str]] = api.apm_api.query_span_option_values(
            {
                "bk_biz_id": app.bk_biz_id,
                "app_name": app.app_name,
                "start_time": int(start_time.timestamp()),
                "end_time": int(end_time.timestamp()),
                "filters": filters,
                "fields": [field],
                "limit": 500,
            }
        )
        return field_options.get(field, [])

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
