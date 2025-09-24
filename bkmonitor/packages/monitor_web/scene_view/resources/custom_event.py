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
from django.db import models
from rest_framework import serializers

from bkmonitor.utils.request import get_request_tenant_id
from core.drf_resource import Resource
from monitor_web.models import CustomEventGroup


class GetCustomEventTargetListResource(Resource):
    """
    获取自定义事件目标列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务")
        id = serializers.IntegerField(label="自定义事件分组ID")

    def perform_request(self, params):
        config = CustomEventGroup.objects.get(
            models.Q(bk_biz_id=params["bk_biz_id"]) | models.Q(is_platform=True),
            bk_tenant_id=get_request_tenant_id(),
            pk=params["id"],
        )
        targets = config.query_target()
        return [{"id": target, "name": target} for target in set(targets)]
