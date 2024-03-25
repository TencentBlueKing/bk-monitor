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
import logging
import time

import requests
from django.conf import settings
from rest_framework import serializers
from six.moves.urllib.parse import urljoin

from bkm_space.utils import bk_biz_id_to_space_uid, parse_space_uid
from bkmonitor.utils.request import get_request
from core.drf_resource import Resource
from core.errors.api import BKAPIError

logger = logging.getLogger("bkmonitor")


def get_unify_query_url(space_uid: str):
    """
    根据空间ID获取统一查询的URL
    """
    if not space_uid:
        return settings.UNIFY_QUERY_URL

    space_type, space_id = parse_space_uid(space_uid)
    for routing_rule in settings.UNIFY_QUERY_ROUTING_RULES:
        url = routing_rule.get("url")
        if not url:
            continue

        match_keys = {"space_type": space_type, "space_id": space_id, "space_uid": space_uid}

        # 至少存在一个匹配条件
        if not (set(match_keys.keys()) & set(routing_rule.keys())):
            continue

        # 匹配条件
        for key, value in match_keys.items():
            match_values = routing_rule.get(key)
            if match_values:
                if isinstance(match_values, (int, str)):
                    # 匹配条件是数字或者字符串，转换成列表
                    match_values = [str(match_values)]
                elif not isinstance(match_values, list):
                    # 匹配条件不是列表或者字符串，跳过
                    break

                if value not in match_values:
                    break
        else:
            return url

    return settings.UNIFY_QUERY_URL


class UnifyQueryAPIResource(Resource):
    """
    统一查询模块
    """

    method = ""
    path = ""

    def perform_request(self, params):
        request = get_request(peaceful=True)
        if request and hasattr(request, "user"):
            username = request.user.username
        else:
            username = ""

        space_uid = ""
        if "space_uid" in params:
            space_uid = params["space_uid"]
        elif params.get("bk_biz_ids"):
            bk_biz_id = params.pop("bk_biz_ids")[0]
            space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        elif request and request.biz_id:
            space_uid = bk_biz_id_to_space_uid(request.biz_id)

        url = urljoin(get_unify_query_url(space_uid), self.path.format(**params))
        requests_params = {
            "method": self.method,
            "url": url,
            "headers": {"Bk-Query-Source": f"username:{username}" if username else "backend"},
        }
        if space_uid is None:
            # 跨业务查询
            requests_params["headers"]["X-Bk-Scope-Skip-Space"] = settings.APP_CODE
        elif space_uid:
            requests_params["headers"]["X-Bk-Scope-Space-Uid"] = space_uid

        if self.method in ["PUT", "POST", "PATCH"]:
            requests_params["json"] = params
        elif self.method in ["GET", "HEAD", "DELETE"]:
            requests_params["params"] = params

        r = requests.request(timeout=60, **requests_params)

        result = r.status_code in [200, 204]
        if not result:
            raise BKAPIError(system_name="unify-query", url=url, result=r.text)

        return r.json()


class QueryDataResource(UnifyQueryAPIResource):
    """
    查询数据
    """

    method = "POST"
    path = "/query/ts"

    class RequestSerializer(serializers.Serializer):
        query_list = serializers.ListField()
        metric_merge = serializers.CharField()
        start_time = serializers.CharField()
        end_time = serializers.CharField()
        step = serializers.CharField()
        space_uid = serializers.CharField(allow_null=True)
        down_sample_range = serializers.CharField(allow_blank=True)
        timezone = serializers.CharField(required=False)


class QueryClusterMetricsDataResource(UnifyQueryAPIResource):
    """
    查询数据
    """

    method = "POST"
    path = "/query/ts/cluster_metrics"

    class RequestSerializer(serializers.Serializer):
        query_list = serializers.ListField()
        metric_merge = serializers.CharField()
        start_time = serializers.CharField(required=False)
        end_time = serializers.CharField()
        step = serializers.CharField(required=False)
        timezone = serializers.CharField(required=False)
        instant = serializers.BooleanField(required=False)

        def validate(self, attrs):
            logger.info(f"ClusterMetrics Query: {json.dumps(attrs)}")
            return attrs


class QueryDataByPromqlResource(UnifyQueryAPIResource):
    """
    使用PromQL查询数据
    """

    method = "POST"
    path = "/query/ts/promql"

    class RequestSerializer(serializers.Serializer):
        promql = serializers.CharField()
        match = serializers.CharField(default="", allow_blank=True, required=False)
        start = serializers.CharField()
        end = serializers.CharField()
        bk_biz_ids = serializers.ListField(child=serializers.CharField(), allow_empty=True, required=False)
        step = serializers.RegexField(required=False, regex=r"^\d+(ms|s|m|h|d|w|y)$")
        timezone = serializers.CharField(required=False)

        def validate(self, attrs):
            logger.info(f"PROMQL_QUERY: {json.dumps(attrs)}")
            return attrs


class PromqlToStructResource(UnifyQueryAPIResource):
    """
    PromQL转结构化查询参数
    """

    method = "POST"
    path = "/query/ts/promql_to_struct"

    class RequestSerializer(serializers.Serializer):
        promql = serializers.CharField()


class StructToPromqlResource(UnifyQueryAPIResource):
    """
    结构化查询参数转PromQL
    """

    method = "POST"
    path = "/query/ts/struct_to_promql"

    class RequestSerializer(serializers.Serializer):
        query_list = serializers.ListField()
        metric_merge = serializers.CharField(allow_blank=True, required=False)
        order_by = serializers.ListField(allow_null=True, required=False, allow_empty=True)
        step = serializers.CharField(allow_blank=True, required=False, allow_null=True)
        space_uid = serializers.CharField()


class GetDimensionDataResource(UnifyQueryAPIResource):
    """
    获取维度数据
    """

    method = "POST"
    path = "/query/ts/info/{info_type}"

    class RequestSerializer(serializers.Serializer):
        info_type = serializers.CharField(required=True, label="请求资源类型")
        table_id = serializers.CharField(required=False, allow_blank=True)
        conditions = serializers.DictField(required=False, label="查询参数")
        keys = serializers.ListField(required=False)
        limit = serializers.IntegerField(required=False, default=1000)
        metric_name = serializers.CharField(required=False, allow_null=True)
        start_time = serializers.CharField(required=False)
        end_time = serializers.CharField(required=False)


class GetPromqlLabelValuesResource(UnifyQueryAPIResource):
    """
    获取promql label values
    """

    method = "GET"
    path = "/query/ts/label/{label}/values"

    class RequestSerializer(serializers.Serializer):
        match = serializers.ListField(child=serializers.CharField())
        label = serializers.CharField()
        bk_biz_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)

        def validate(self, attrs):
            attrs["match[]"] = attrs.pop("match")
            return attrs


class QueryDataByExemplarResource(QueryDataResource):
    method = "POST"
    path = "/query/ts/exemplar"

    class RequestSerializer(serializers.Serializer):
        query_list = serializers.ListField()
        start_time = serializers.CharField()
        end_time = serializers.CharField()
        down_sample_range = serializers.CharField(allow_blank=True)
        space_uid = serializers.CharField()


class QueryDataByTableResource(UnifyQueryAPIResource):
    method = "POST"
    path = "query/ts/info/time_series"

    class RequestSerializer(serializers.Serializer):
        limit = serializers.IntegerField()
        slimit = serializers.IntegerField()
        metric_name = serializers.CharField(default="")
        table_id = serializers.CharField()
        keys = serializers.ListField(child=serializers.CharField())
        start_time = serializers.CharField()
        end_time = serializers.CharField()
        conditions = serializers.DictField(default={"field_list": [], "condition_list": []})


class GetKubernetesRelationResource(UnifyQueryAPIResource):
    method = "POST"
    path = "/api/v1/relation/multi_resource"

    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(child=serializers.IntegerField(), required=True)
        source_info_list = serializers.ListField(child=serializers.DictField(), required=True)

    def validate_request_data(self, request_data):
        request_data = super(GetKubernetesRelationResource, self).validate_request_data(request_data)
        query_list = []
        for source_info in request_data.pop("source_info_list", []):
            data_timestamp = source_info.pop("data_timestamp", int(time.time()))
            query_list.append({"target_type": "system", "timestamp": data_timestamp, "source_info": source_info})
        request_data["query_list"] = query_list
        return request_data
