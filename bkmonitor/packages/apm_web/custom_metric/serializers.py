"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from apm_web.models.application import Application


class BaseRequestSerializer(serializers.Serializer):
    app_name = serializers.CharField(label=_("应用名称"))
    service_name = serializers.CharField(label=_("服务名称"))
    bk_biz_id = serializers.IntegerField(label=_("业务 ID"))

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        # 1. 必须先补充 time_series_group_id
        app_name = data.get("app_name")
        bk_biz_id = data.get("bk_biz_id")

        try:
            application = Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
            data["time_series_group_id"] = application.time_series_group_id
        except Application.DoesNotExist:
            raise serializers.ValidationError(
                _("应用不存在: bk_biz_id={bk_biz_id}, app_name={app_name}").format(
                    bk_biz_id=bk_biz_id, app_name=app_name
                )
            )

        # 2. 调用父类的 to_internal_value
        validated_data = super().to_internal_value(data)

        # 3. 补充 scope_prefix
        validated_data["scope_prefix"] = validated_data["service_name"] + "||"

        return validated_data
