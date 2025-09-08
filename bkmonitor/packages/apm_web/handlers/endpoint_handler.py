# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from apm_web.metric_handler import ServiceFlowCount
from apm_web.models import Application
from bkmonitor.utils.cache import CacheType, using_cache
from core.drf_resource import api


class EndpointHandler:
    @classmethod
    @using_cache(CacheType.APM(60 * 60))
    def get_endpoint(cls, bk_biz_id, app_name, service_name, endpoint_name):
        endpoint_info = api.apm_api.query_endpoint(
            **{
                "bk_biz_id": bk_biz_id,
                "app_name": app_name,
                "service_name": service_name,
                "filters": {"endpoint_name": endpoint_name},
            }
        )
        if endpoint_info:
            return endpoint_info[0]

        application = Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
        start_time, end_time = application.list_retention_time_range()

        flow_response = ServiceFlowCount(
            **{
                "application": application,
                "start_time": start_time,
                "end_time": end_time,
                "where": [
                    {"condition": "and", "key": "from_apm_service_name", "method": "eq", "value": [service_name]},
                    {"condition": "and", "key": "from_span_name", "method": "eq", "value": [endpoint_name]},
                    {"condition": "or", "key": "to_apm_service_name", "method": "eq", "value": [service_name]},
                    {"condition": "and", "key": "to_span_name", "method": "eq", "value": [endpoint_name]},
                ],
                "group_by": [
                    "from_apm_service_name",  # index: 0
                    "from_span_name",  # index: 1
                    "from_apm_service_category",  # index: 2
                    "to_apm_service_name",  # index: 3
                    "to_span_name",  # index: 4
                    "to_apm_service_category",  # index: 5
                ],
            }
        ).get_instance_values_mapping()
        if not flow_response:
            return None

        for k in flow_response.keys():
            if k[1] == endpoint_name:
                return {
                    "service_name": k[0],
                    "category": k[2],
                }
            if k[4] == endpoint_name:
                return {
                    "service_name": k[3],
                    "category": k[5],
                }

        return None
