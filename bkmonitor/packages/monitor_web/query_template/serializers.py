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

from bkmonitor.models.query_template import QueryTemplate
from bkmonitor.query_template.serializers import QueryTemplateSerializer


class BaseQueryTemplateRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    is_mock = serializers.BooleanField(label="是否为 Mock 数据", default=True)


class QueryTemplateDetailRequestSerializer(BaseQueryTemplateRequestSerializer):
    pass


class QueryTemplateListRequestSerializer(BaseQueryTemplateRequestSerializer):
    class ConditionSerializer(serializers.Serializer):
        key = serializers.CharField(label="查询条件")
        value = serializers.ListField(label="查询条件值", child=serializers.CharField())

    page = serializers.IntegerField(label="页码", min_value=1, default=1)
    page_size = serializers.IntegerField(label="每页条数", min_value=1, default=50)
    order_by = serializers.ListField(
        label="排序字段", child=serializers.CharField(), default=["-update_time"], allow_empty=True
    )
    conditions = serializers.ListField(label="查询条件", child=ConditionSerializer(), default=[], allow_empty=True)


class FunctionSerializer(serializers.Serializer):
    id = serializers.CharField()
    params = serializers.ListField(child=serializers.DictField(), allow_empty=True)


class QueryTemplateCreateRequestSerializer(BaseQueryTemplateRequestSerializer, QueryTemplateSerializer):
    def validate(self, attrs):
        return super().validate(attrs)


class QueryTemplateUpdateRequestSerializer(QueryTemplateCreateRequestSerializer):
    pass


class QueryTemplatePreviewRequestSerializer(BaseQueryTemplateRequestSerializer):
    query_template = QueryTemplateSerializer(label="查询模板")
    context = serializers.DictField(label="变量值", default={}, required=False)


class QueryTemplateRelationsRequestSerializer(BaseQueryTemplateRequestSerializer):
    query_template_ids = serializers.ListField(
        label="查询模板 ID 列表", child=serializers.IntegerField(min_value=1), default=[], allow_empty=True
    )


class QueryTemplateRelationRequestSerializer(BaseQueryTemplateRequestSerializer):
    pass


class QueryTemplateModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = QueryTemplate
        fields = "__all__"
