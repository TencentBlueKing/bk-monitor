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
import json
from typing import Any, Generator, Iterator

from django.http import StreamingHttpResponse
from rest_framework import serializers, viewsets
from rest_framework.request import Request

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from monitor_web.overview.search import Searcher


class PermissionMixin:
    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.VIEW_BUSINESS])]


class AlarmRankViewSet(PermissionMixin, ResourceViewSet):
    """
    告警类型排行
    """

    resource_routes = [
        ResourceRoute("GET", resource.overview.alarm_rank),
    ]


class AlarmCountInfoViewSet(PermissionMixin, ResourceViewSet):
    """
    告警数量信息
    """

    resource_routes = [
        ResourceRoute("GET", resource.overview.alarm_count_info),
    ]


class MonitorInfoViewSet(PermissionMixin, ResourceViewSet):
    """
    业务监控状态总览
    """

    resource_routes = [
        ResourceRoute("GET", resource.overview.monitor_info),
    ]


class SearchSerializer(serializers.Serializer):
    """
    搜索参数
    """

    query = serializers.CharField(label="搜索关键字")


class SearchViewSet(viewsets.GenericViewSet):
    """
    搜索, 使用多线程搜索，使用 event-stream 返回搜索结果
    """

    def unescape(self, query: str) -> str:
        """
        反转义
        """
        query = query.replace("&lt;", "<")
        query = query.replace("&gt;", ">")
        query = query.replace("&amp;", "&")
        query = query.replace("&quot;", '"')
        query = query.replace("&#39;", "'")
        query = query.replace("&nbsp;", " ")
        return query

    def list(self, request: Request, *args: Any, **kwargs: Any) -> StreamingHttpResponse:
        serializer = SearchSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        query: str = serializer.validated_data['query']

        # 反转义
        query = self.unescape(query).strip()

        # 搜索
        searcher: Searcher = Searcher(username=request.user.username)
        result: Iterator[dict] = searcher.search(query)

        # 使用 event-stream 返回搜索结果
        def event_stream() -> Generator[str, None, None]:
            yield "event: start\n\n"
            for line in result:
                yield f"data: {json.dumps(line)}\n\n"
            yield "event: end\n\n"

        sr = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        sr.headers["Cache-Control"] = "no-cache"
        sr.headers["X-Accel-Buffering"] = "no"
        return sr


class FunctionShortcutViewSet(PermissionMixin, ResourceViewSet):
    """
    功能快捷入口
    """

    resource_routes = [
        ResourceRoute("POST", resource.overview.get_function_shortcut),
        ResourceRoute("POST", resource.overview.add_access_record, endpoint="add_access_record"),
    ]


class AlarmGraphConfigViewSet(PermissionMixin, ResourceViewSet):
    """
    首页告警图配置
    """

    resource_routes = [
        ResourceRoute("GET", resource.overview.get_alarm_graph_config),
        ResourceRoute("POST", resource.overview.save_alarm_graph_config),
        ResourceRoute("POST", resource.overview.delete_alarm_graph_config, endpoint="delete"),
        ResourceRoute("POST", resource.overview.save_alarm_graph_biz_index, endpoint="save_biz_index"),
    ]
