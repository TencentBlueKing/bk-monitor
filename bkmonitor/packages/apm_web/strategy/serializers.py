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

from constants.data_source import DATA_SOURCE_LABEL_ALIAS, DATA_TYPE_LABEL_ALIAS

from .constants import QueryTemplateVariableType


class BizBaseSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID")
    is_mock = serializers.BooleanField(label="是否为Mock数据", default=True)


class AppBaseSerializer(BizBaseSerializer):
    app_name = serializers.CharField(label="应用名称")


class QueryTemplateDetailRequestSerializer(BizBaseSerializer):
    query_template_id = serializers.IntegerField(label="查询模板ID", min_value=1)


class QueryTemplateListRequestSerializer(BizBaseSerializer):
    class ConditionSerializer(serializers.Serializer):
        key = serializers.CharField(label="查询条件")
        value = serializers.CharField(label="查询值")

    page = serializers.IntegerField(label="页码", min_value=1, default=1)
    page_size = serializers.IntegerField(label="每页条数", min_value=1, default=50)
    order_by = serializers.ListField(
        label="排序字段", child=serializers.CharField(), default=["-update_time"], allow_empty=True
    )
    conditions = serializers.ListField(label="查询条件", child=ConditionSerializer(), default=[], allow_empty=True)


class FunctionSerializer(serializers.Serializer):
    id = serializers.CharField()
    params = serializers.ListField(child=serializers.DictField(), allow_empty=True)


class QueryTemplateCreateRequestSerializer(BizBaseSerializer):
    class QueryConfigSerializer(serializers.Serializer):
        class MetricsSerializer(serializers.Serializer):
            field = serializers.CharField(label="字段")
            method = serializers.CharField(label="方法")
            alias = serializers.CharField(label="别名")

        data_source_label = serializers.ChoiceField(label="数据源标签", choices=list(DATA_SOURCE_LABEL_ALIAS.keys()))
        data_type_label = serializers.ChoiceField(label="数据类型标签", choices=list(DATA_TYPE_LABEL_ALIAS.keys()))
        table = serializers.CharField(label="表名", default="", allow_blank=True)
        metrics = serializers.ListField(label="指标", child=MetricsSerializer(), allow_empty=True)
        group_by = serializers.ListField(label="分组", child=serializers.CharField(), allow_empty=True)
        where = serializers.ListField(label="过滤条件", child=serializers.JSONField(), allow_empty=True)
        interval = serializers.CharField(label="时间间隔", default="auto")
        time_field = serializers.CharField(label="时间字段", allow_blank=True, allow_null=True, required=False)
        functions = serializers.ListField(label="函数", child=FunctionSerializer(), allow_empty=True)

    class VariableSerializer(serializers.Serializer):
        name = serializers.CharField(label="变量名称")
        type = serializers.ChoiceField(label="变量类型", choices=QueryTemplateVariableType.choices())
        alias = serializers.CharField(label="变量别名", default="", allow_blank=True)
        default = serializers.JSONField(label="默认值")
        description = serializers.CharField(label="变量描述", default="", allow_blank=True)
        relation_value = serializers.JSONField(label="关联值")
        allowed_values = serializers.ListField(label="可选值列表", child=serializers.JSONField())

    # max_length
    name = serializers.CharField(label="查询模板名称")
    description = serializers.CharField(label="查询模板描述", allow_blank=True, default="")
    biz_scope = serializers.ListField(label="业务范围", child=serializers.IntegerField())
    biz_name_scope = serializers.CharField(label="业务名称范围")
    query_configs = serializers.ListField(label="查询配置", child=QueryConfigSerializer())
    expressions = serializers.CharField(label="表达式")
    variables = serializers.ListField(label="变量", child=VariableSerializer(), allow_empty=True)
    functions = serializers.ListField(label="函数", child=FunctionSerializer(), allow_empty=True)


class QueryTemplateUpdateRequestSerializer(QueryTemplateCreateRequestSerializer):
    id = serializers.IntegerField(label="查询模板ID", min_value=1)


class QueryTemplatePreviewRequestSerializer(BizBaseSerializer):
    class QueryTemplateSerializer(serializers.Serializer):
        query_configs = serializers.ListField(
            label="查询配置", child=QueryTemplateCreateRequestSerializer.QueryConfigSerializer()
        )
        expressions = serializers.CharField(label="表达式")
        variables = serializers.ListField(label="变量", child=QueryTemplateCreateRequestSerializer.VariableSerializer())
        functions = serializers.ListField(label="函数", child=serializers.JSONField())

    class VariableSerializer(serializers.Serializer):
        name = serializers.CharField(label="变量名称")
        type = serializers.ChoiceField(label="变量类型", choices=QueryTemplateVariableType.choices())
        value = serializers.JSONField(label="变量值")

    query_template = QueryTemplateSerializer(label="查询模板")
    variables = serializers.ListField(label="变量", child=VariableSerializer())


class QueryTemplateRelationsRequestSerializer(BizBaseSerializer):
    query_template_ids = serializers.ListField(label="查询模板ID列表", child=serializers.IntegerField(min_value=1))


class QueryTemplateRelationRequestSerializer(BizBaseSerializer):
    query_template_id = serializers.IntegerField(label="查询模板ID", min_value=1)
