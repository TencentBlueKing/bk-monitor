"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from core.drf_resource import Resource, api
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from .bk_doris import APIParams, APIType, Query
from .parser import ProfileParser


# TODO: abandon Resource-like API, use vanilla DRF APIView instead
class ProfilesQueryResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        application_id = serializers.IntegerField(label="应用ID")
        app_name = serializers.CharField(label="应用 Key")
        profile_id = serializers.CharField(label="profile ID")
        profile_type = serializers.CharField(label="profile类型", default="cpu")
        start = serializers.IntegerField(label="开始时间", help_text="请使用 millisecond")
        end = serializers.IntegerField(label="结束时间", help_text="请使用 millisecond")

    def perform_request(self, validated_request_data):
        """通过 profile_id 查询 profiling 数据"""
        bk_biz_id, application_id, app_name, profile_id, profile_type, start, end = validated_request_data.values()
        # 获取 ApmApplication.profiling_datasource 信息
        try:
            application_info = api.apm_api.detail_application({"application_id": application_id})
        except Exception:
            raise ValueError(_("应用({}) 不存在").format(application_id))
        if "profiling_config" not in application_info:
            raise ValueError(_("应用({}) 未开启性能分析").format(application_id))

        # 查询 BK Doris 数据
        q = Query(
            api_type=APIType.QUERY_SAMPLE,
            api_params=APIParams(
                biz_id=bk_biz_id,
                app=app_name,
                type=profile_type,
                start=start,
                end=end,
                label_filter={"profile_id": profile_id},
            ),
            result_table_id=application_info["profiling_config"]["result_table_id"],
        )

        r = q.execute()
        if r is None:
            raise ValueError(_("未查询到有效数据"))

        # 直接将 profiling 数据转换成火焰图格式
        return ProfileParser.raw_to_flamegraph(r)
