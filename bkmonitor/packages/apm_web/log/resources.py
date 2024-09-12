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

from apm_web.constants import ServiceRelationLogTypeChoices
from apm_web.handlers.host_handler import HostHandler
from apm_web.models import LogServiceRelation
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

        # Step: 从SpanId中查询主机关联采集项
        if data.get("span_id"):
            span_host = HostHandler.find_host_in_span(bk_biz_id, app_name, data["span_id"])

            if span_host:
                is_host_has_log_indexes = self.query_indexes(
                    {"bk_biz_id": bk_biz_id, "bk_host_id": span_host["bk_host_id"]}
                )
                if is_host_has_log_indexes:
                    return True

        # Step: 从服务关联中找日志
        relation = LogServiceRelation.objects.filter(
            bk_biz_id=data["bk_biz_id"],
            app_name=data["app_name"],
            service_name=data["service_name"],
            log_type=ServiceRelationLogTypeChoices.BK_LOG,
        )

        return relation.exists()


class ServiceRelationListResource(Resource, HostIndexQueryMixin):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        service_name = serializers.CharField()
        span_id = serializers.CharField(label="SpanId", required=False)

    def perform_request(self, data):
        res = []

        bk_biz_id = data["bk_biz_id"]
        app_name = data["app_name"]

        # Step: 从SpanId中查询主机关联采集项
        if data.get("span_id"):
            span_host = HostHandler.find_host_in_span(bk_biz_id, app_name, data["span_id"])

            if span_host:
                infos = self.query_indexes({"bk_biz_id": bk_biz_id, "bk_host_id": span_host["bk_host_id"]})
                for item in infos:
                    res.append(
                        {
                            "index_set_id": item["index_set_id"],
                            "index_set_name": item["index_set_name"],
                            "log_type": "bk_log",
                            "related_bk_biz_id": bk_biz_id,
                        }
                    )

        relations = LogServiceRelation.objects.filter(
            bk_biz_id=data["bk_biz_id"],
            app_name=data["app_name"],
            service_name=data["service_name"],
            log_type=ServiceRelationLogTypeChoices.BK_LOG,
        )
        if not relations.exists():
            return res

        index_set = api.log_search.search_index_set(bk_biz_id=data["bk_biz_id"])
        for item in relations:
            index_set_info = next((i for i in index_set if str(i["index_set_id"]) == item.value), None)
            if index_set_info:
                res.append(
                    {
                        "index_set_id": index_set_info["index_set_id"],
                        "index_set_name": index_set_info['index_set_name'],
                        "log_type": item.log_type,
                        "related_bk_biz_id": item.related_bk_biz_id,
                    }
                )

        return res
