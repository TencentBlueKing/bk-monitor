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

from bkmonitor.models import GlobalConfig
from bkmonitor.views import serializers
from core.drf_resource.base import Resource


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
