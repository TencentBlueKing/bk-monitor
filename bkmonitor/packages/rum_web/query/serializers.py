"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from rum_web.constants import RumQueryMode
from constants.apm import OperatorGroupRelation


class FilterSerializer(serializers.Serializer):
    class OptionsSerializer(serializers.Serializer):
        is_wildcard = serializers.BooleanField(label=_("是否使用通配符"), default=False)
        group_relation = serializers.ChoiceField(
            label=_("分组关系"), choices=OperatorGroupRelation.choices(), default=OperatorGroupRelation.OR
        )

    key = serializers.CharField(label=_("查询键"))
    operator = serializers.CharField(label=_("操作符"))
    options = OptionsSerializer(label=_("操作符选项"), default={})
    value = serializers.ListSerializer(
        label=_("查询值"), child=serializers.CharField(allow_blank=True), allow_empty=True
    )


class BaseRumRequestSerializer(serializers.Serializer):
    """RUM 查询接口公共请求字段"""

    bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
    app_name = serializers.CharField(label=_("应用名称"))
    mode = serializers.ChoiceField(
        label=_("查询层级模式"), choices=RumQueryMode.choices(), default=RumQueryMode.SPAN.value
    )
    extra_config = serializers.DictField(label=_("扩展配置"), default={})


class BaseTimeRangeSerializer(BaseRumRequestSerializer):
    """带时间范围的公共请求字段"""

    start_time = serializers.IntegerField(label=_("开始时间"))
    end_time = serializers.IntegerField(label=_("结束时间"))


class BaseSearchSerializer(BaseTimeRangeSerializer):
    filters = serializers.ListField(label=_("过滤条件"), child=serializers.DictField(), default=[])
    query_string = serializers.CharField(label=_("查询字符串"), default="", allow_blank=True)


class RumRecordsRequestSerializer(BaseSearchSerializer):
    """分页查询记录列表"""

    offset = serializers.IntegerField(label=_("偏移量"), default=0, min_value=0)
    limit = serializers.IntegerField(label=_("每页数量"), default=10, min_value=1)
    sort = serializers.ListField(label=_("排序条件"), child=serializers.CharField(), default=[])


class RumViewConfigRequestSerializer(BaseTimeRangeSerializer):
    """获取页面视图配置"""

    mode = None


class RumFieldsOptionValuesRequestSerializer(BaseSearchSerializer):
    """批量查询字段可选枚举值"""

    fields = serializers.ListField(label=_("查询字段列表"), child=serializers.CharField())
    limit = serializers.IntegerField(label=_("查询条数"), default=10, min_value=1)


class RumGenerateQueryStringRequestSerializer(serializers.Serializer):
    """将过滤条件转换为查询字符串"""

    class QueryStringFilterSerializer(FilterSerializer):
        value = serializers.ListSerializer(label=_("查询值"), child=serializers.JSONField(), allow_empty=True)

    filters = serializers.ListField(label=_("查询条件"), child=QueryStringFilterSerializer(), default=[])
