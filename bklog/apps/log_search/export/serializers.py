"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from rest_framework import serializers


class ExportAdditionSerializer(serializers.Serializer):
    """搜索条件字段：与旧导出链路保持一致的宽松契约，不对取值的具体类型做额外限制。"""

    field = serializers.CharField()
    operator = serializers.CharField()
    value = serializers.JSONField()


class ExportCreateSerializer(serializers.Serializer):
    space_uid = serializers.CharField(max_length=256)
    index_set_id = serializers.IntegerField(min_value=1)
    # 与 GetExportHistorySerializer 保持一致，统一使用毫秒时间戳
    start_time = serializers.IntegerField(label="起始时间（毫秒时间戳）", min_value=0)
    end_time = serializers.IntegerField(label="结束时间（毫秒时间戳）", min_value=1)
    keyword = serializers.CharField(default="*", allow_blank=True)
    addition = ExportAdditionSerializer(many=True, default=list)
    ip_chooser = serializers.DictField(default=dict)
    sort_list = serializers.ListField(child=serializers.ListField(child=serializers.CharField()), default=list)
    export_fields = serializers.ListField(child=serializers.CharField(), default=list)
    requested_parallelism = serializers.IntegerField(min_value=1, required=False)

    def validate_sort_list(self, value):
        if any(len(item) != 2 or item[1] not in {"asc", "desc"} for item in value):
            raise serializers.ValidationError("排序字段格式应为 [字段, asc|desc]")
        return value

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError("导出时间范围不合法")
        return attrs


class ExportScopeSerializer(serializers.Serializer):
    space_uid = serializers.CharField(max_length=256)


class ExportListSerializer(ExportScopeSerializer):
    page = serializers.IntegerField(min_value=1, default=1)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=20)


class ExportLinkSerializer(ExportScopeSerializer):
    artifact_id = serializers.CharField(max_length=32)

    def validate_artifact_id(self, value):
        if value != "manifest" and (not value.isdecimal() or int(value) < 1):
            raise serializers.ValidationError("产物标识不合法")
        return value
