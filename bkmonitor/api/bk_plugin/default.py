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
import abc
import json
import logging

import six
from django.conf import settings
from rest_framework import serializers

from core.drf_resource import APIResource

logger = logging.getLogger(__name__)


class BkPluginBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url = ""
    module_name = "bk_plugin"

    def __init__(self, *args, **kwargs):
        request_url = kwargs.pop("url", "")
        if request_url:
            self.base_url = request_url
        super(BkPluginBaseResource, self).__init__(*args, **kwargs)

    def get_request_url(self, validated_request_data):
        return (
            super(BkPluginBaseResource, self).get_request_url(validated_request_data).format(**validated_request_data)
        )

    def full_request_data(self, validated_request_data):
        # 组装通用参数：SaaS凭证
        validated_request_data = super(BkPluginBaseResource, self).full_request_data(validated_request_data)
        if settings.BK_PLUGIN_APP_INFO:
            validated_request_data.update(settings.BK_PLUGIN_APP_INFO)
        return validated_request_data


class BkPluginMetaResource(BkPluginBaseResource):
    """
    获取插件版本列表
    """

    method = "GET"
    action = "/bk_plugin/meta"

    def render_response_data(self, validated_request_data, response_data):
        versions = response_data.get("versions", [])
        return [{"version": version, "name": version} for version in versions]


class BkPluginDetailResource(BkPluginBaseResource):
    """
    获取插件对应版本的表单
    """

    method = "GET"
    action = "/bk_plugin/detail/{version}"

    class RequestSerializer(serializers.Serializer):
        version = serializers.CharField(label="插件版本", required=True)

    def parse_json_schema(self, schema):
        """
        解析json_schema
        """
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        params = [
            dict(value, **{"key": key, "required": True if key in required else False})
            for key, value in properties.items()
        ]
        return params

    def render_response_data(self, validated_request_data, response_data):
        inputs = self.parse_json_schema(response_data.get("inputs", {}))
        # outputs = self.parse_json_schema(response_data.get("outputs", {}))
        # context_inputs = self.parse_json_schema(response_data.get("context_inputs", {}))
        return {"inputs": inputs}


class BkPluginInvokeResource(BkPluginBaseResource):
    """
    执行插件任务
    """

    method = "post"
    action = "/invoke/{version}"
    IS_STANDARD_FORMAT = False

    class RequestSerializer(serializers.Serializer):
        version = serializers.CharField(label="插件版本", required=True)
        inputs = serializers.ListField(label="输入参数", required=True)
        bk_biz_id = serializers.IntegerField(label="业务ID", required=False)
        assignee = serializers.ListField(label="执行人", required=False)

    def full_request_data(self, validated_request_data):
        validated_request_data = super(BkPluginInvokeResource, self).full_request_data(validated_request_data)
        inputs = validated_request_data.pop("inputs", [])
        invoke_data = {
            "inputs": {param["key"]: param["value"] for param in inputs},
            "context": {
                "bk_biz_id": validated_request_data.get("bk_biz_id"),
                "executor": ",".join(validated_request_data.get("assignee", [])),
            },
        }
        validated_request_data.update(invoke_data)
        return validated_request_data


class BkPluginScheduleResource(BkPluginBaseResource):
    """
    根据trace_id获取任务结果
    """

    method = "GET"
    action = "/bk_plugin/schedule/{trace_id}"

    class RequestSerializer(serializers.Serializer):
        trace_id = serializers.CharField(label="追溯ID", required=True)


class BkPluginSystemResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url = settings.PAASV3_APIGW_BASE_URL or "%s/api/c/compapi/v2/bk_paas/" % settings.BK_COMPONENT_API_URL
    module_name = "bk_plugin_system"
    IS_STANDARD_FORMAT = False

    def __init__(self, *args, **kwargs):
        request_url = kwargs.pop("url", "")
        if request_url:
            self.base_url = request_url
        super(BkPluginSystemResource, self).__init__(*args, **kwargs)

    def get_request_url(self, validated_request_data):
        return (
            super(BkPluginSystemResource, self).get_request_url(validated_request_data).format(**validated_request_data)
        )

    def get_headers(self):
        headers = super(BkPluginSystemResource, self).get_headers()

        # 替换掉通用参数中的bk_app_code和bk_app_secret
        if settings.BK_PLUGIN_APP_INFO:
            auth_info = json.loads(headers["x-bkapi-authorization"])
            auth_info.update(settings.BK_PLUGIN_APP_INFO)
            headers["x-bkapi-authorization"] = json.dumps(auth_info)

        return headers


class BkPluginListResource(BkPluginSystemResource):
    """
    获取蓝鲸插件列表
    """

    method = "GET"
    action = "/system/bk_plugins"


class BkPluginDeployedInfoResource(BkPluginSystemResource):
    """
    获取蓝鲸插件部署信息
    """

    method = "GET"
    action = "/system/bk_plugins/{plugin_code}"

    class RequestSerializer(serializers.Serializer):
        plugin_code = serializers.CharField(label="插件code", required=True)


class BkPluginDeployedInfoBatchResource(BkPluginSystemResource):
    """
    批量获取蓝鲸插件部署信息
    """

    method = "GET"
    action = "/system/bk_plugins/batch/detailed"

    class RequestSerializer(serializers.Serializer):
        has_deployed = serializers.BooleanField(label="插件是否部署", required=True)
        distributor_code_name = serializers.CharField(label="已授权使用方代号", required=True)
