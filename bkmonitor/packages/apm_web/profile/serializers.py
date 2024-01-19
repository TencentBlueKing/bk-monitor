"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from rest_framework import serializers

from apm_web.models import ProfileUploadRecord
from apm_web.profile.constants import DEFAULT_PROFILE_DATA_TYPE


class QueryBaseSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID")
    app_name = serializers.CharField(label="应用名称", required=False)
    service_name = serializers.CharField(label="服务名称", required=False)
    global_query = serializers.BooleanField(label="全局查询", required=False, default=False)
    data_type = serializers.CharField(label="Sample 数据类型", required=False, default=DEFAULT_PROFILE_DATA_TYPE)
    start = serializers.IntegerField(label="开始时间", help_text="请使用 Microsecond")
    end = serializers.IntegerField(label="结束时间", help_text="请使用 Microsecond")

    def validate(self, attrs):
        # 当且仅当全局查询时，不需要传递 app_name 和 service_name
        if not attrs.get("global_query"):
            if not attrs.get("app_name") or not attrs.get("service_name"):
                raise serializers.ValidationError("app_name and service_name is required")
        return attrs


class ProfileQuerySerializer(QueryBaseSerializer):
    """Query Samples"""

    profile_id = serializers.CharField(label="profile ID", required=False, default="")
    offset = serializers.IntegerField(label="偏移量(秒)", required=False, default=300)
    diagram_types = serializers.ListSerializer(
        child=serializers.CharField(), required=False, default=["flamegraph", "table"]
    )
    sort = serializers.CharField(label="排序, 只对table有效", required=False, default="-total")
    filter_labels = serializers.DictField(label="标签过滤", default={}, required=False)

    # only is_compared is true, the diff_* params is valid
    is_compared = serializers.BooleanField(label="是否开启对比模式", required=False, default=False)
    diff_profile_id = serializers.CharField(label="diff profile ID", required=False, default="")
    diff_filter_labels = serializers.DictField(label="标签过滤", default={}, required=False)


class ProfileQueryExportSerializer(ProfileQuerySerializer):
    # export
    export_format = serializers.CharField(label="数据导出格式")


class ProfileQueryLabelsSerializer(QueryBaseSerializer):
    """Query Labels"""


class ProfileQueryLabelValuesSerializer(QueryBaseSerializer):
    """Query Label Values"""

    label_key = serializers.CharField(label="标签Key")
    offset = serializers.IntegerField(label="偏移量(秒)", required=False, default=0)
    rows = serializers.IntegerField(label="返回数量", required=False, default=10)


class ProfileUploadSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID")
    service_name = serializers.CharField(label="服务名称", required=False)
    file_type = serializers.ChoiceField(choices=["perf_script", "pprof"])


class ProfileUploadRecordSLZ(serializers.ModelSerializer):
    class Meta:
        model = ProfileUploadRecord
        fields = "__all__"


class ProfileListFileSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID", required=False)
    app_name = serializers.CharField(label="应用名称", required=False)
    origin_file_name = serializers.CharField(label="上传文件名称", default="", required=False)
    service_name = serializers.CharField(label="服务名称", required=False)
