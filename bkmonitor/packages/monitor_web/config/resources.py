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


from monitor_web.config.converter import convert_field
from rest_framework import serializers

from bkmonitor.define.global_config import STANDARD_CONFIGS
from bkmonitor.models import GlobalConfig
from core.drf_resource import Resource


class ListGlobalConfig(Resource):
    """
    拉取全局配置列表
    """

    def perform_request(self, validated_request_data):
        configs = GlobalConfig.objects.filter(is_advanced=False)
        result = {}
        for config in configs:
            result[config.key] = convert_field(config)
        standard_keys = list(STANDARD_CONFIGS.keys())
        sorted_configs = []
        for key in standard_keys:
            if key in result:
                sorted_configs.append(result.pop(key))
        return sorted_configs


class SetGlobalConfig(Resource):
    """
    设置全局配置
    """

    class RequestSerializer(serializers.Serializer):
        class ConfigSerializer(serializers.Serializer):
            key = serializers.CharField()
            value = serializers.JSONField(allow_null=True)

        configs = ConfigSerializer(required=True, many=True)

    def get_serializer_cls(self, data_type, options):
        cls_name = "{}Field".format(data_type)
        serializer_cls = getattr(serializers, cls_name)
        options = options or {}
        return serializer_cls(**options)

    def perform_request(self, validated_request_data):
        configs = {config.key: config for config in GlobalConfig.objects.filter(is_advanced=False)}

        set_results = []
        for data in validated_request_data["configs"]:
            key, value = data["key"], data["value"]
            if key not in configs:
                continue
            config = configs[key]
            try:
                serializer = config.get_serializer()
                value = serializer.run_validation(value)
                config.value = value
                config.save()
                result = True
                message = "modify success"
            except Exception as e:
                result = False
                message = "modify failed: {}".format(e)
            set_results.append(
                {
                    "key": key,
                    "value": value,
                    "result": result,
                    "message": message,
                }
            )
        return set_results
