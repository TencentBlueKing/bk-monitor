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


class ProfileQuerySerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID")
    app_name = serializers.CharField(label="应用名称")
    start = serializers.IntegerField(label="开始时间", help_text="请使用 Microsecond")
    end = serializers.IntegerField(label="结束时间", help_text="请使用 Microsecond")
    profile_type = serializers.CharField(label="profile类型", required=False, default="cpu")
    profile_id = serializers.CharField(label="profile ID", required=False, default="")
    offset = serializers.IntegerField(label="偏移量(秒)", required=False, default=300)
    diagram_type = serializers.ChoiceField(
        choices=["flamegraph", "callgraph", "table"], required=False, default="flamegraph"
    )


class ProfileUploadSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID")
    file_type = serializers.ChoiceField(choices=["perf_script", "pprof"])


class ProfileUploadRecordSLZ(serializers.ModelSerializer):
    class Meta:
        model = ProfileUploadRecord
        fields = "__all__"
