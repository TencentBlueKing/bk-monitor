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

from alarm_backends.service.alert.qos.influence import get_influence
from bkmonitor.views import serializers
from core.drf_resource import Resource

logger = logging.getLogger(__name__)


class IncidentPublishResource(Resource):
    # 自监控：故障发布
    # 此接口接受自监控告警事件，基于内置模块规则，将目标影响范围进行故障发布
    class RequestSerializer(serializers.Serializer):
        target = serializers.CharField(required=True, label="目标")
        module = serializers.CharField(required=True, label="模块", default="vm")

    def perform_request(self, validated_request_data):
        config = {}

        target = validated_request_data["target"]
        if not target:
            return config

        module = validated_request_data["module"]

        if module == "vm":
            target = target.split("-")[1]

        # 发布影响
        return get_influence(module, target)


class IncidentRecoveryResource(Resource):
    # 自监控，故障恢复
    pass
