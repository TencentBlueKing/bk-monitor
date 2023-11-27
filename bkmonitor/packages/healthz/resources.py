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

import arrow
from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.translation import ugettext as _

from bkmonitor.models import GlobalConfig, HealthzMetricConfig, HealthzMetricRecord
from bkmonitor.views import serializers
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from healthz.utils import deep_parsing_metric_info, get_saas_healthz

from .utils import (
    BkdataHealthzChecker,
    CcHealthzChecker,
    GseHealthzChecker,
    JobHealthzChecker,
    MetadataHealthzChecker,
    NodemanHealthzChecker,
    monitor_time_elapsed,
)


def is_data_expired(data, timeout=30 * 60):
    """
    判断当前时间是否过期，默认过期时间为30分钟
    :param data: 要检查的数据
    :param timeout: 过期时间，单位为秒
    :return: True 表示过期，False 表示不过期
    """
    update_time = arrow.get(data)
    current_time = arrow.now(tz=update_time.tzinfo)
    time_delta = current_time.timestamp - update_time.timestamp
    if time_delta > timeout:
        return True
    return False


class GetGlobalStatusResource(Resource):
    """
    从配置文件中获取监控配置中主机监控的指标项
    """

    many_response_data = True

    class RequestSerializer(serializers.Serializer):
        pass

    class ResponseSerializer(serializers.Serializer):
        node_name = serializers.CharField(allow_blank=True, allow_null=True, required=False)
        description = serializers.CharField(allow_blank=True, allow_null=True, required=False)
        category = serializers.CharField(allow_blank=True, allow_null=True, required=False)
        collect_metric = serializers.CharField(allow_blank=True, allow_null=True, required=False)
        collect_args = serializers.CharField(allow_blank=True, allow_null=True, required=False)
        collect_interval = serializers.IntegerField(required=False)
        metric_alias = serializers.CharField(allow_blank=True, allow_null=True, required=False)
        solution = serializers.ListField(required=False, default=[])
        result = serializers.JSONField(required=False)
        last_update = serializers.DateTimeField(required=False)
        server_ip = serializers.IPAddressField(allow_blank=True, allow_null=True, required=False)

    @monitor_time_elapsed
    def perform_request(self, data):
        config_mappings = {c.metric_alias: model_to_dict(c) for c in HealthzMetricConfig.objects.all()}

        metric_infos = []
        for record in HealthzMetricRecord.objects.all():
            metric_info = config_mappings.get(record.metric_alias, {}).copy()
            metric_info.update(model_to_dict(record))
            metric_info["solution"] = json.loads(metric_info.get("solution") or "[]")
            metric_info["result"] = json.loads(metric_info["result"])
            # 检查是否过期，默认为5分钟
            if not is_data_expired(metric_info["last_update"], 5 * 60):
                if isinstance(metric_info["result"]["value"], dict):
                    metric_info["result"]["value"] = [metric_info["result"]["value"]]
                if isinstance(metric_info["result"]["value"], (list, tuple)):
                    try:
                        for sub_info in deep_parsing_metric_info(metric_info):
                            metric_infos.append(sub_info)
                    except TypeError:
                        metric_infos.append(metric_info)
                else:
                    metric_infos.append(metric_info)

        saas_metric_infos = get_saas_healthz()
        metric_infos += saas_metric_infos
        return metric_infos


class ServerGraphPointResource(Resource):
    class RequestSerializer(serializers.BusinessOnlySerializer):
        time_range_banner = serializers.IntegerField(required=True, label="最近几小时", min_value=0)
        host_id = serializers.CharField(required=True, label="主机ID")
        index_id = serializers.IntegerField(required=True, label="指标ID")
        dimension_field = serializers.CharField(default="", label="条件字段", allow_blank=True)
        dimension_field_value = serializers.CharField(default="", label="条件字段取值", allow_blank=True)
        group_field = serializers.CharField(default="", label="维度字段", allow_blank=True)
        filter_dict = serializers.JSONField(default={}, binary=True, label="额外过滤参数")

    def perform_request(self, validated_request_data):
        validated_request_data["bk_biz_id"] = api.cmdb.get_blueking_biz()
        validated_request_data["filter_dict"] = json.dumps(validated_request_data["filter_dict"])
        return resource.performance.graph_point(validated_request_data)


class ServerHostAlarmResource(Resource):
    class RequestSerializer(serializers.BusinessOnlySerializer):
        host_id = serializers.CharField(required=True, label="主机ID")
        alarm_date = serializers.CharField(required=True, label="日期")

    def perform_request(self, validated_request_data):
        validated_request_data["bk_biz_id"] = api.cmdb.get_blueking_biz()
        return resource.performance.host_alarm(validated_request_data)


class ApiTestRootApiResource(Resource):
    """
    API接口测试基类
    """

    _healthz_checker = None

    class RequestSerializer(serializers.Serializer):
        api_name = serializers.CharField(required=True, label="api名称")

    class ResponseSerializer(serializers.Serializer):
        status = serializers.BooleanField(required=True, label="返回状态")
        api_name = serializers.CharField(required=True, label="接口名称")
        message = serializers.CharField(required=True, label="返回信息")
        args = serializers.DictField(required=True, label="请求参数")
        result = serializers.DictField(required=True, label="返回结果")

    def perform_request(self, validated_request_data):
        api_name = validated_request_data["api_name"]
        status, api_name, message, args, results = self._healthz_checker.test_root_api(api_name)
        return {"status": status, "api_name": api_name, "message": message, "args": args, "result": results}


class MetadataTestRootApiResource(ApiTestRootApiResource):
    """
    对metadata下的根接口进行测试
    """

    _healthz_checker = MetadataHealthzChecker()


class NodemanTestRootApiResource(ApiTestRootApiResource):
    """
    对node_man下的根接口进行测试
    """

    _healthz_checker = NodemanHealthzChecker()


class GseTestRootApiResource(ApiTestRootApiResource):
    """
    对gse下的根接口进行测试
    """

    _healthz_checker = GseHealthzChecker()


class JobTestRootApiResource(ApiTestRootApiResource):
    """
    对job下的根接口进行测试
    """

    _healthz_checker = JobHealthzChecker()


############


class TestNonRootApiResource(Resource):
    healthz_checker = None

    class RequestSerializer(serializers.Serializer):
        api_name = serializers.CharField(required=True, label="api名称")
        parent_api = serializers.CharField(required=True, label="所依赖api")
        kwargs = serializers.DictField(required=True, label="请求参数")

    class ResponseSerializer(serializers.Serializer):
        status = serializers.BooleanField(required=True, label="返回状态")
        api_name = serializers.CharField(required=True, label="接口名称")
        parent_api = serializers.CharField(required=True, label="父接口名称")
        message = serializers.CharField(required=True, label="返回信息")
        args = serializers.DictField(required=True, label="请求参数")
        result = serializers.ListField(required=True, label="返回结果")

    def perform_request(self, validated_request_data):
        api_name = validated_request_data["api_name"]
        parent_api = validated_request_data["parent_api"]
        kwargs = validated_request_data["kwargs"]

        if self.healthz_checker is None:
            # 不存在健康检查，直接返回空
            return {}

        (
            status,
            return_api_name,
            return_parent_api,
            message,
            request_args,
            return_args,
        ) = self.healthz_checker.test_non_root_api(api_name, parent_api, kwargs)
        return {
            "status": status,
            "api_name": return_api_name,
            "parent_api": return_parent_api,
            "message": message,
            "args": request_args,
            "result": return_args,
        }


class JobTestNonRootApiResource(TestNonRootApiResource):
    """
    对 job 下的非根接口进行测试
    """

    healthz_checker = JobHealthzChecker()


class CcTestRootApiResource(ApiTestRootApiResource):
    """
    对cc下的根接口进行测试
    """

    _healthz_checker = CcHealthzChecker()


class CcTestNonRootApiResource(TestNonRootApiResource):
    """
    对cc下的非根接口进行测试
    """

    healthz_checker = CcHealthzChecker()


class BkDataTestRootApiResource(ApiTestRootApiResource):
    """
    对bk_data下的根接口进行测试
    """

    _healthz_checker = BkdataHealthzChecker()

    def perform_request(self, validated_request_data):
        api_name = validated_request_data["api_name"]
        status, message, args, result = (True, "OK", {}, {"data": _("计算平台未接入")})
        if settings.IS_ACCESS_BK_DATA:
            status, api_name, message, args, result = self._healthz_checker.test_root_api(api_name)
        return {"status": status, "api_name": api_name, "message": message, "args": args, "result": result}


class UpdateAlarmConfig(Resource):
    """
    更新通知配置
    """

    class RequestSerializer(serializers.Serializer):
        alarm_config = serializers.DictField(required=True, label="通知设置")

    def perform_request(self, validated_request_data):
        alarm_config = validated_request_data["alarm_config"]
        GlobalConfig.set(key="HEALTHZ_ALARM_CONFIG", value=alarm_config)
        return alarm_config


class GetAlarmConfig(Resource):
    """
    获取通知配置
    """

    def perform_request(self, validated_request_data):
        config = GlobalConfig.get("HEALTHZ_ALARM_CONFIG")

        if not config:
            config = {"alarm_type": [], "alarm_role": []}

        return config
