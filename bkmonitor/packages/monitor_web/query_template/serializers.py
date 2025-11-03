"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections.abc import Iterable
from typing import Any

from blueapps.utils.request_provider import get_request
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.models.query_template import QueryTemplate
from bkmonitor.query_template.serializers import QueryTemplateSerializer
from constants.query_template import GLOBAL_BIZ_ID


class BaseQueryTemplateRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")


class QueryTemplateDetailRequestSerializer(BaseQueryTemplateRequestSerializer):
    pass


class QueryTemplateListRequestSerializer(BaseQueryTemplateRequestSerializer):
    class ConditionSerializer(serializers.Serializer):
        key = serializers.ChoiceField(
            label="查询条件", choices=["query", "name", "alias", "description", "create_user", "update_user"]
        )
        value = serializers.ListField(label="查询条件值", child=serializers.CharField())

    page = serializers.IntegerField(label="页码", min_value=1, default=1)
    page_size = serializers.IntegerField(label="每页条数", min_value=1, default=50)
    order_by = serializers.ListField(
        label="排序字段",
        child=serializers.ChoiceField(choices=["update_time", "-update_time", "create_time", "-create_time"]),
        default=["-update_time"],
        allow_empty=True,
    )
    conditions = serializers.ListField(label="查询条件", child=ConditionSerializer(), default=[], allow_empty=True)


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


class QueryTemplateBaseModelSerializer(serializers.ModelSerializer):
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = QueryTemplate
        fields = "__all__"

    @staticmethod
    def _get_request_bk_biz_id() -> int:
        return int(get_request().biz_id)

    @staticmethod
    def is_global_template(bk_biz_id: int) -> bool:
        return bk_biz_id == GLOBAL_BIZ_ID

    @classmethod
    def is_read_only(cls, obj: QueryTemplate) -> bool:
        if cls.is_global_template(obj.bk_biz_id):
            if get_request().user.is_superuser:
                return False
        elif obj.bk_biz_id == cls._get_request_bk_biz_id():
            return False
        return True

    def get_can_edit(self, obj: QueryTemplate) -> bool:
        return not self.is_read_only(obj)

    def get_can_delete(self, obj: QueryTemplate) -> bool:
        return not self.is_read_only(obj)


class QueryTemplateModelSerializer(QueryTemplateBaseModelSerializer):
    @staticmethod
    def _is_allowed_by_bk_biz_ids(bk_biz_ids: Iterable[int]):
        permission = Permission()
        for bk_biz_id in bk_biz_ids:
            if permission.is_allowed_by_biz(bk_biz_id, ActionEnum.EXPLORE_METRIC):
                continue
            raise serializers.ValidationError(
                _("您没有业务 ID 为 {bk_biz_id} 的指标探索权限").format(bk_biz_id=bk_biz_id)
            )

    @classmethod
    def _base_create_validate(cls, validated_data: dict[str, Any]):
        bk_biz_id = validated_data["bk_biz_id"]

        if cls.is_global_template(bk_biz_id):
            raise serializers.ValidationError(_("全局模板不允许在页面创建"))
        elif bk_biz_id not in validated_data["space_scope"]:
            raise serializers.ValidationError(_("生效范围必须包含当前业务 ID"))

        # 校验该用户是否有业务范围的权限
        cls._is_allowed_by_bk_biz_ids(validated_data["space_scope"])

        if QueryTemplate.origin_objects.filter(bk_biz_id=bk_biz_id, name=validated_data["name"]).exists():
            raise serializers.ValidationError(_("同一业务下查询模板名称不能重复"))

    def _base_update_validate(self, instance: QueryTemplate, validated_data: dict[str, Any]):
        if not self.get_can_edit(instance):
            raise serializers.ValidationError(_("当前模板不可编辑"))

        # 如果这是一个全局模板，则将 bk_biz_id 设置为 0
        bk_biz_id = validated_data["bk_biz_id"]
        if self.is_global_template(instance.bk_biz_id):
            # 全局模板 bk_biz_id & namespace 不允许被修改。
            validated_data["namespace"] = instance.namespace
            validated_data["bk_biz_id"] = bk_biz_id = GLOBAL_BIZ_ID
        elif bk_biz_id not in validated_data["space_scope"]:
            raise serializers.ValidationError(_("生效范围必须包含当前业务 ID"))

        existing_space_scopes: set[int] = set(instance.space_scope)
        modified_space_scopes: set[int] = set(validated_data["space_scope"])
        # 移除的 scopes
        removed_scopes = existing_space_scopes - modified_space_scopes
        # 新增的 scopes
        added_scopes = modified_space_scopes - existing_space_scopes
        self._is_allowed_by_bk_biz_ids(removed_scopes | added_scopes)

        if instance.name != validated_data["name"]:
            raise serializers.ValidationError(_("查询模板名称不支持修改"))

    def create(self, validated_data: dict[str, Any]) -> QueryTemplate:
        self._base_create_validate(validated_data)
        return super().create(validated_data)

    def update(self, instance: QueryTemplate, validated_data: dict[str, Any]) -> QueryTemplate:
        self._base_update_validate(instance, validated_data)
        return super().update(instance, validated_data)


class QueryTemplateListModelSerializer(QueryTemplateBaseModelSerializer):
    class Meta:
        model = QueryTemplate
        fields = [
            "id",
            "name",
            "alias",
            "description",
            "bk_biz_id",
            "can_edit",
            "can_delete",
            "is_enabled",
            "create_user",
            "create_time",
            "update_user",
            "update_time",
            "space_scope",
        ]
