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
import logging

from alarm_backends.service.alert.qos.influence import clear_failure, publish_failure
from bkmonitor.views import serializers
from core.drf_resource import Resource

logger = logging.getLogger(__name__)


class FailurePublishResource(Resource):
    # 自监控：故障发布
    # 此接口接受自监控告警事件，基于内置模块规则，将目标影响范围进行故障发布
    class RequestSerializer(serializers.Serializer):
        target = serializers.CharField(required=True, label="目标")
        module = serializers.CharField(required=True, label="模块")

    def perform_request(self, validated_request_data):
        duration = publish_failure(validated_request_data["module"], validated_request_data["target"])
        return duration


class FailureRecoveryResource(Resource):
    # 自监控，故障恢复
    class RequestSerializer(serializers.Serializer):
        target = serializers.CharField(required=True, label="目标")
        module = serializers.CharField(required=True, label="模块")

    def perform_request(self, validated_request_data):
        clear_failure(validated_request_data["module"], validated_request_data["target"])
        return 0
