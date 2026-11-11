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

        start_time = serializers.IntegerField(required=False, label="开始时间（Unix秒）")
        end_time = serializers.IntegerField(required=False, label="结束时间（Unix秒）")

        def validate(self, attrs):
            if ("start_time" in attrs) != ("end_time" in attrs):
                raise serializers.ValidationError("start_time 和 end_time 必须同时提供")
            if "start_time" in attrs and attrs["start_time"] > attrs["end_time"]:
                raise serializers.ValidationError("start_time 不能大于 end_time")
            return attrs

    def perform_request(self, params):
        config = CustomEventGroup.objects.get(
            models.Q(bk_biz_id=params["bk_biz_id"]) | models.Q(is_platform=True),
            bk_tenant_id=get_request_tenant_id(),
            pk=params["id"],
        )
        targets = config.query_target(**{key: params[key] for key in ("start_time", "end_time") if key in params})
        return [{"id": target, "name": target} for target in set(targets)]
