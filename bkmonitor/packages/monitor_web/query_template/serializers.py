"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from blueapps.utils.request_provider import get_local_request
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.models.query_template import QueryTemplate
from bkmonitor.query_template.serializers import QueryTemplateSerializer
from constants.query_template import GLOBAL_BIZ_ID


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

    def validate_order_by(self, values):
        allowed_fields = ["update_time", "-update_time", "create_time", "-create_time"]
        for value in values:
            if value not in allowed_fields:
                raise serializers.ValidationError(_("排序字段 {value} 不支持").format(value=value))
        return values

    def validate_conditions(self, values):
        allowed_keys = ["query", "name", "description", "create_user", "update_user"]
        for value in values:
            if value["key"] not in allowed_keys:
                raise serializers.ValidationError(_("查询条件 {key} 不支持").format(key=value["key"]))
        return values


class FunctionSerializer(serializers.Serializer):
    id = serializers.CharField()
    params = serializers.ListField(child=serializers.DictField(), allow_empty=True)


class QueryTemplateCreateRequestSerializer(BaseQueryTemplateRequestSerializer, QueryTemplateSerializer):
    pass


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
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = QueryTemplate
        fields = "__all__"

    @staticmethod
    def _is_allowed_by_bk_biz_ids(bk_biz_ids: list):
        permission = Permission()
        for bk_biz_id in bk_biz_ids:
            if permission.is_allowed_by_biz(bk_biz_id, ActionEnum.EXPLORE_METRIC):
                continue
            raise serializers.ValidationError(
                _("您没有业务 ID 为 {bk_biz_id} 的指标探索权限").format(bk_biz_id=bk_biz_id)
            )

    @staticmethod
    def _base_validate(validated_data):
        if validated_data["bk_biz_id"] == GLOBAL_BIZ_ID:
            raise serializers.ValidationError(_("全局模板不允许在页面进行操作"))

        # 校验生效范围必须包含本业务 ID
        bk_biz_id = validated_data["bk_biz_id"]
        if bk_biz_id != GLOBAL_BIZ_ID and bk_biz_id not in validated_data["space_scope"]:
            raise serializers.ValidationError(_("生效范围必须包含当前业务 ID"))

        # 校验同一业务下查询模板名称不能重复
        if QueryTemplate.objects.filter(bk_biz_id=bk_biz_id, name=validated_data["name"]).exists():
            raise serializers.ValidationError(_("同一业务下查询模板名称不能重复"))

    def create(self, validated_data):
        self._is_allowed_by_bk_biz_ids([validated_data["space_scope"]])
        self._base_validate(validated_data)
        instance = super().create(validated_data)
        return instance

    @property
    def _request_bk_biz_id(self):
        return int(get_local_request().biz_id)

    def get_can_edit(self, obj):
        # 全局模板不可编辑
        if obj.bk_biz_id == GLOBAL_BIZ_ID:
            return False
        # 可见但非归属的业务不可编辑
        if obj.bk_biz_id != self._request_bk_biz_id:
            return False
        return True

    def get_can_delete(self, obj):
        # 全局模板不可删除
        if obj.bk_biz_id == GLOBAL_BIZ_ID:
            return False
        # 可见但非归属的业务不可删除
        if obj.bk_biz_id != self._request_bk_biz_id:
            return False
        return True
