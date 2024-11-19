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

from apm_web.handlers.log_handler import ServiceLogHandler
from core.drf_resource import Resource, api
from monitor_web.scene_view.resources import HostIndexQueryMixin


def log_relation_list(bk_biz_id, app_name, service_name, span_id=None, start_time=None, end_time=None):
    index_set_ids = []

    full_indexes = api.log_search.search_index_set(bk_biz_id=bk_biz_id)
    # Resource: 从 SpanId 关联主机中找
    if span_id:
        host_indexes = ServiceLogHandler.list_host_indexes_by_span(bk_biz_id, app_name, span_id)
        for item in host_indexes:
            if item["index_set_id"] not in index_set_ids:
                index_info = next(
                    (i for i in full_indexes if str(i["index_set_id"]) == str(item["index_set_id"])), None
                )
                if index_info:
                    index_set_ids.append(str(item["index_set_id"]))
                    yield index_info

    # Resource: 从自定义上报中找日志
    datasource_index_set_id = ServiceLogHandler.get_and_check_datasource_index_set_id(
        bk_biz_id,
        app_name,
        full_indexes=full_indexes,
    )
    if datasource_index_set_id and datasource_index_set_id not in index_set_ids:
        index_info = next((i for i in full_indexes if str(i["index_set_id"]) == str(datasource_index_set_id)), None)
        if index_info:
            index_set_ids.append(str(datasource_index_set_id))
            yield index_info

    # Resource: 从服务关联中找日志
    relation = ServiceLogHandler.get_log_relation(bk_biz_id, app_name, service_name)
    if relation and relation.value not in index_set_ids:
        if relation.related_bk_biz_id != bk_biz_id:
            relation_full_indexes = api.log_search.search_index_set(bk_biz_id=relation.related_bk_biz_id)
            index_info = next(
                (i for i in relation_full_indexes if str(i["index_set_id"]) == relation.value),
                None,
            )
            if index_info:
                index_set_ids.append(relation.value)
                yield index_info
        else:
            index_info = next((i for i in full_indexes if str(i["index_set_id"]) == relation.value), None)
            if index_info:
                index_set_ids.append(relation.value)
                yield index_info

    # Resource: 从关联指标中找
    relation_index_set_ids = ServiceLogHandler.list_indexes_by_relation(
        bk_biz_id,
        app_name,
        service_name,
        start_time,
        end_time,
    )
    if relation_index_set_ids:
        for i in relation_index_set_ids:
            if i not in index_set_ids:
                index_info = next((j for j in full_indexes if str(j["index_set_id"]) == str(i)), None)
                if index_info:
                    index_set_ids.append(i)
                    yield index_info


class ServiceLogInfoResource(Resource, HostIndexQueryMixin):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        service_name = serializers.CharField()
        span_id = serializers.CharField(label="SpanId", required=False)
        start_time = serializers.IntegerField(label="开始时间", required=False)
        end_time = serializers.IntegerField(label="结束时间", required=False)

    def perform_request(self, data):
        return any(log_relation_list(**data))


class ServiceRelationListResource(Resource, HostIndexQueryMixin):
    """服务索引集列表"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        service_name = serializers.CharField()
        # [!!!] 当传递 span_id 时候 场景为 span 检索日志处
        # [!!!] 当没有传递 span_id 时候 场景为观测场景 span 日志处
        span_id = serializers.CharField(label="SpanId", required=False)
        start_time = serializers.IntegerField(label="开始时间", required=False)
        end_time = serializers.IntegerField(label="结束时间", required=False)

    def perform_request(self, data):
        return list(log_relation_list(**data))
