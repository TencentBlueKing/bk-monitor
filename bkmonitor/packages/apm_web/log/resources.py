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
from rest_framework import serializers

from apm_web.constants import LogIndexSource
from apm_web.handlers.log_handler import ServiceLogHandler
from core.drf_resource import Resource, api
from monitor_web.scene_view.resources import HostIndexQueryMixin


class ServiceLogInfoResource(Resource, HostIndexQueryMixin):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        service_name = serializers.CharField()
        span_id = serializers.CharField(label="SpanId", required=False)

    def perform_request(self, data):

        bk_biz_id = data["bk_biz_id"]
        app_name = data["app_name"]
        service_name = data["service_name"]

        # Step: 从自定义上报中找日志
        datasource_index_set_id = ServiceLogHandler.get_and_check_datasource_index_set_id(bk_biz_id, app_name)
        if datasource_index_set_id:
            return True

        # Step: 从SpanId中查询主机关联采集项
        if data.get("span_id"):
            host_indexes = ServiceLogHandler.list_host_indexes_by_span(bk_biz_id, app_name, data["span_id"])
            if host_indexes:
                return True

        # Step: 从服务关联中找日志
        relation_index_set_id = ServiceLogHandler.get_log_relation(bk_biz_id, app_name, service_name)

        return bool(relation_index_set_id)


class ServiceRelationListResource(Resource, HostIndexQueryMixin):
    """服务索引集列表"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        service_name = serializers.CharField()
        # [!!!] 当传递 span_id 时候 场景为 span 检索日志处
        # [!!!] 当没有传递 span_id 时候 场景为观测场景 span 日志处
        span_id = serializers.CharField(label="SpanId", required=False)

    def perform_request(self, data):

        bk_biz_id = data["bk_biz_id"]
        app_name = data["app_name"]
        service_name = data["service_name"]

        index_set_ids = []

        # Step: 从SpanId中查询主机关联采集项
        if data.get("span_id"):
            host_indexes = ServiceLogHandler.list_host_indexes_by_span(bk_biz_id, app_name, data["span_id"])
            for item in host_indexes:
                index_set_ids.append(
                    {
                        "index_set_id": item["index_set_id"],
                        "source": LogIndexSource.get_source_label(LogIndexSource.HOST),
                        "related_bk_biz_id": bk_biz_id,
                    }
                )

        # Step 从服务关联中找
        relation = ServiceLogHandler.get_log_relation(bk_biz_id, app_name, service_name)
        if relation:
            index_set_ids.append(
                {
                    "index_set_id": relation.value,
                    "source": LogIndexSource.get_source_label(LogIndexSource.RELATION),
                    "related_bk_biz_id": relation.related_bk_biz_id,
                }
            )

        indexes = api.log_search.search_index_set(bk_biz_id=data["bk_biz_id"])

        # Step 从自定义上报中找
        datasource_index_set_id = ServiceLogHandler.get_and_check_datasource_index_set_id(
            bk_biz_id,
            app_name,
            full_indexes=indexes,
        )
        if datasource_index_set_id:
            index_set_ids.append(
                {
                    "index_set_id": datasource_index_set_id,
                    "source": LogIndexSource.get_source_label(LogIndexSource.CUSTOM_REPORT),
                    "related_bk_biz_id": bk_biz_id,
                }
            )

        if data.get("span_id"):
            return self.list_span_query_log_infos(index_set_ids, indexes)
        return self.list_apm_log_infos(index_set_ids, indexes)

    @classmethod
    def list_span_query_log_infos(cls, index_set_ids, full_indexes):
        res = []
        for item in index_set_ids:
            index_set_info = next(
                (i for i in full_indexes if str(i["index_set_id"]) == str(item["index_set_id"])), None
            )
            if index_set_info:
                res.append(
                    {
                        "index_set_id": index_set_info["index_set_id"],
                        "index_set_name": index_set_info['index_set_name'],
                        "related_bk_biz_id": item["related_bk_biz_id"],
                        "source": item["source"],
                        "log_type": "bk_log",
                    }
                )

        return res

    @classmethod
    def list_apm_log_infos(cls, index_set_ids, full_indexes):
        res = []
        for item in index_set_ids:
            index_set_info = next(
                (i for i in full_indexes if str(i["index_set_id"]) == str(item["index_set_id"])), None
            )

            if index_set_info:
                res.append(index_set_info)
        return res
