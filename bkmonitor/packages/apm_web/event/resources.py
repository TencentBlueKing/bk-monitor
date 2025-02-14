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

from typing import Any, Dict, List, Optional

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import Resource
from monitor_web.data_explorer.event import resources as event_resources

from . import handler, serializers


class EventTimeSeriesResource(Resource):
    RequestSerializer = serializers.EventTimeSeriesRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        start_time: Optional[int] = validated_request_data.get("start_time")
        end_time: Optional[int] = validated_request_data.get("end_time")

        base_q: QueryConfigBuilder = (
            QueryConfigBuilder((DataTypeLabel.EVENT, DataSourceLabel.BK_APM))
            .time_field("time")
            .interval(60)
            .filter(**{"dimensions.bk_biz_id": bk_biz_id})
        )
        k8s_q: QueryConfigBuilder = (
            base_q.table("k8s_event")
            .alias("a")
            .metric(field="_index", method="SUM", alias="a")
            .filter(**{"dimensions.bcs_cluster_id": "BCS-K8S-00000"})
        )
        system_q = base_q.table("system_event").alias("b").metric(field="_index", method="SUM", alias="b")

        qs: UnifyQuerySet = (
            handler.EventQueryHelper.time_range_qs(start_time=start_time, end_time=end_time)
            .scope(bk_biz_id)
            .add_query(k8s_q)
            .add_query(system_q)
            .expression("a + b")
        )
        return event_resources.EventTimeSeriesResource().perform_request(qs.config)


class EventLogsResource(Resource):
    RequestSerializer = serializers.EventLogsRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        return event_resources.EventLogsResource().perform_request(validated_request_data)


class EventViewConfigResource(Resource):
    RequestSerializer = serializers.EventViewConfigRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        return event_resources.EventViewConfigResource().perform_request(validated_request_data)


class EventTopKResource(Resource):
    RequestSerializer = serializers.EventTopKRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return event_resources.EventTopKResource().perform_request(validated_request_data)


class EventTotalResource(Resource):
    RequestSerializer = serializers.EventTotalRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        return event_resources.EventTotalResource().perform_request(validated_request_data)
