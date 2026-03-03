"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from apm_web.models.application import Application


# 注: 此序列化器的参数在 apm_web.k8s.resources.ListServicePodsResource 也使用到
class KubernetesListRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
    keyword = serializers.CharField(required=False, allow_null=True, label="查询关键词", allow_blank=True)
    status = serializers.CharField(required=False, allow_null=True, label="状态过滤", allow_blank=True)
    condition_list = serializers.ListField(required=False, allow_null=True)
    filter_dict = serializers.DictField(required=False, allow_null=True, label="枚举列过滤")
    sort = serializers.CharField(required=False, allow_null=True, label="排序", allow_blank=True)
    page = serializers.IntegerField(required=False, allow_null=True, label="页码")
    page_size = serializers.IntegerField(required=False, allow_null=True, label="每页条数")


class CustomMetricBaseRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
    time_series_group_id = serializers.IntegerField(label=_("自定义指标 ID"), required=False, allow_null=True)
    apm_app_name = serializers.CharField(label=_("应用名称(APM场景变量)"), required=False, allow_null=True)
    apm_service_name = serializers.CharField(label=_("服务名称(APM场景变量)"), required=False, allow_null=True)

    def to_internal_value(self, data):
        result_table_id = ""
        # 1. 如果提供了 apm_app_name，则自动补充 time_series_group_id
        apm_app_name = data.get("apm_app_name")
        bk_biz_id = data.get("bk_biz_id")

        if apm_app_name and bk_biz_id:
            try:
                application = Application.objects.get(bk_biz_id=bk_biz_id, app_name=apm_app_name)
                data["time_series_group_id"] = application.time_series_group_id
                result_table_id = application.metric_result_table_id
            except Application.DoesNotExist:
                raise ValueError(
                    _("应用不存在: bk_biz_id={bk_biz_id}, app_name={app_name}").format(
                        bk_biz_id=bk_biz_id, app_name=apm_app_name
                    )
                )

        # 2. 调用父类的 to_internal_value
        validated_data = super().to_internal_value(data)
        # 3. 补充 result_table_id
        validated_data["result_table_id"] = result_table_id

        # 4. 如果提供了 apm_service_name，则补充 scope_prefix（用于后续过滤）
        if validated_data.get("apm_service_name"):
            validated_data["scope_prefix"] = validated_data["apm_service_name"] + "||"

        # 5. 补充 is_apm_scenario
        validated_data["is_apm_scenario"] = apm_app_name and data.get("apm_service_name")

        return validated_data
