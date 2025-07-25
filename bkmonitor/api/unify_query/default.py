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
from urllib.parse import urljoin

import requests
from django.conf import settings
from rest_framework import serializers

from bkm_space.utils import bk_biz_id_to_space_uid, parse_space_uid
from bkmonitor.utils.local import local
from bkmonitor.utils.request import get_request, get_request_tenant_id
from bkmonitor.utils.tenant import space_uid_to_bk_tenant_id
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
                if isinstance(match_values, int | str):
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

        # 记录查询来源
        source = "backend"
        if username:
            source = f"username:{username}"
        elif getattr(local, "strategy_id", None):
            source = f"strategy:{local.strategy_id}"

        requests_params = {"method": self.method, "url": url, "headers": {"Bk-Query-Source": source}}
        if space_uid is None:
            # 跨业务查询
            requests_params["headers"]["X-Bk-Scope-Skip-Space"] = settings.APP_CODE
        elif space_uid:
            requests_params["headers"]["X-Bk-Scope-Space-Uid"] = space_uid

        # 设置租户ID
        bk_tenant_id = None
        if params.get("bk_tenant_id"):
            bk_tenant_id = params["bk_tenant_id"]
        elif space_uid:
            try:
                bk_tenant_id = space_uid_to_bk_tenant_id(space_uid)
            except ValueError:
                pass

        # 如果租户ID不存在，则使用请求的租户ID
        if not bk_tenant_id:
            bk_tenant_id = get_request_tenant_id(peaceful=True)

        if bk_tenant_id:
            requests_params["headers"]["X-Bk-Tenant-Id"] = bk_tenant_id

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
        instant = serializers.BooleanField(required=False)


class QueryRawResource(UnifyQueryAPIResource):
    """
    查询原始数据
    """

    method = "POST"
    path = "/query/ts/raw"

    class RequestSerializer(serializers.Serializer):
        query_list = serializers.ListField()
        metric_merge = serializers.CharField()
        start_time = serializers.CharField()
        end_time = serializers.CharField()
        step = serializers.CharField()
        limit = serializers.IntegerField(required=False, default=1)
        # from 是 Python 关键字，此处加下划线，真正请求时转回 _from
        _from = serializers.IntegerField(required=False, default=0)
        space_uid = serializers.CharField(allow_null=True)
        timezone = serializers.CharField(required=False)
        instant = serializers.BooleanField(required=False)
        order_by = serializers.ListField(allow_null=True, required=False, allow_empty=True)

    def perform_request(self, params):
        params["from"] = params.pop("_from", 0)
        return super().perform_request(params)


class QueryReferenceResource(UnifyQueryAPIResource):
    """
    查询原始数据
    """

    method = "POST"
    path = "/query/ts/reference"

    class RequestSerializer(serializers.Serializer):
        query_list = serializers.ListField()
        metric_merge = serializers.CharField()
        start_time = serializers.CharField()
        end_time = serializers.CharField()
        step = serializers.CharField()
        space_uid = serializers.CharField(allow_null=True)
        timezone = serializers.CharField(required=False)
        instant = serializers.BooleanField(required=False)
        order_by = serializers.ListField(allow_null=True, required=False, allow_empty=True)
        look_back_delta = serializers.CharField(required=False, default="1m")


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
        is_verify_dimensions = serializers.BooleanField(default=False)
        start = serializers.CharField()
        end = serializers.CharField()
        bk_biz_ids = serializers.ListField(child=serializers.CharField(), allow_empty=True, required=False)
        step = serializers.RegexField(required=False, regex=r"^\d+(ms|s|m|h|d|w|y)$")
        timezone = serializers.CharField(required=False)
        down_sample_range = serializers.CharField(allow_blank=True, required=False)
        # 背景：默认情况下，unify-query 会对查询结果进行时序对齐，叠加上 SaaS 默认 drop 最后一个数据点逻辑，会导致数据不准确，
        # 该默认行为对基于一段时间配置汇总数据的视图非常不友好，会出现较大的误差，或者直接无数据。
        #
        # e.g. 按流水线统计一段时间（近 3h）内（2025-07-14 18:48:39 ～ 2025-07-14 21:48:39）的运行次数：
        # 1）queryTs：
        # - ES 过滤时间范围：2025-07-14 17:59:59 ～ 2025-07-15 00:48:38
        # - 按 3h 进行分桶
        #
        # 返回数据点：
        # - 1752487200000（2025-07-14 18:00:00）, 130
        # - 1752498000000（2025-07-14 21:00:00）, 0（❌不完整周期，对齐后无数据。）
        #
        # 2）queryReference
        # - ES 过滤时间范围：2025-07-14 18:48:39 ～ 2025-07-14 21:48:39
        #
        # 返回数据点：
        # - 1752487200000（2025-07-14 18:00:00）, 130
        # - 1752498000000（2025-07-14 21:00:00）, 31（✅不完整周期，也能得到当前数量。）
        #
        # 在日志场景，如果希望保证数据准确性，且保留最新数据点，设置 reference=True 取消对数据的时序对齐，配合 SaaS 侧提供的
        # time_alignment=False 参数。
        reference = serializers.BooleanField(default=False, required=False)

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
        space_uid = serializers.CharField(allow_blank=True, required=False, allow_null=True)


class GetDimensionDataResource(UnifyQueryAPIResource):
    """
    获取维度数据
    """

    method = "POST"
    path = "/query/ts/info/{info_type}"

    class RequestSerializer(serializers.Serializer):
        space_uid = serializers.CharField(allow_blank=True, required=False, allow_null=True)
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
        start = serializers.CharField(required=False)
        end = serializers.CharField(required=False)

        def validate(self, attrs):
            attrs["match[]"] = attrs.pop("match")
            return attrs


class GetTagKeysResource(UnifyQueryAPIResource):
    """
    获取tag keys
    """

    method = "POST"
    path = "/query/ts/info/tag_keys"

    class RequestSerializer(serializers.Serializer):
        data_source = serializers.CharField(default="bkmonitor")
        table_id = serializers.CharField(allow_blank=True)
        metric_name = serializers.CharField()
        bk_biz_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)


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


class QuerySeriesResource(UnifyQueryAPIResource):
    method = "POST"
    path = "query/ts/info/series"

    class RequestSerializer(serializers.Serializer):
        metric_name = serializers.CharField(default="")
        is_regexp = serializers.BooleanField(default=True)
        table_id = serializers.CharField()
        keys = serializers.ListField(child=serializers.CharField())
        start_time = serializers.CharField()
        end_time = serializers.CharField()
        conditions = serializers.DictField(default={"field_list": [], "condition_list": []})
        bk_biz_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True, default=list)


class GetKubernetesRelationResource(UnifyQueryAPIResource):
    method = "POST"
    path = "/api/v1/relation/multi_resource"

    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(child=serializers.IntegerField(), required=True)
        source_info_list = serializers.ListField(child=serializers.DictField(), required=True)

    def validate_request_data(self, request_data):
        request_data = super().validate_request_data(request_data)
        query_list = []
        for source_info in request_data.pop("source_info_list", []):
            data_timestamp = source_info.pop("data_timestamp", int(time.time()))
            query_list.append(
                {
                    "target_type": "system",
                    "path_resource": ["node"],
                    "timestamp": data_timestamp,
                    "source_info": source_info,
                }
            )
        request_data["query_list"] = query_list
        return request_data


class QueryMultiResourceRange(UnifyQueryAPIResource):
    """查询时间范围内的关联资源实体"""

    method = "POST"
    path = "/api/v1/relation/multi_resource_range"

    class RequestSerializer(serializers.Serializer):
        class QueryListSerializer(serializers.Serializer):
            start_time = serializers.IntegerField()
            end_time = serializers.IntegerField()
            step = serializers.CharField()
            target_type = serializers.CharField()
            source_type = serializers.CharField(required=False)
            source_info = serializers.DictField()
            path_resource = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)

        bk_biz_ids = serializers.ListField(child=serializers.CharField(), allow_empty=True, required=False)
        query_list = serializers.ListField(child=QueryListSerializer(), min_length=1)
