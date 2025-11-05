"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from typing import Any

from django.apps import apps
from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from core.drf_resource import Resource
from metadata.models import EntityMeta

logger = logging.getLogger("metadata")


class EntityHandler:
    """
    通用的实体处理器，支持所有继承自 EntityMeta 的模型
    提供 apply, get, list, delete 等通用操作
    """

    def __init__(self, model_class: type[EntityMeta]):
        """
        初始化处理器

        Args:
            model_class: 继承自 EntityMeta 的模型类
        """
        self.model_class = model_class

    def apply(self, metadata: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
        """
        应用资源（声明式API）

        Args:
            metadata: 资源元数据
            spec: 资源配置

        Returns:
            资源的 JSON 表示，包含 created 字段表示是否新建
        """
        # 校验 spec
        spec_slz_class = self.model_class.get_serializer_class()
        spec_slz = spec_slz_class(data=spec)
        spec_slz.is_valid(raise_exception=True)
        cleaned_spec = spec_slz.validated_data

        namespace = metadata["namespace"]
        name = metadata["name"]

        # 准备创建数据
        create_data = cleaned_spec.copy()

        labels = metadata.get("labels", {})
        create_data["labels"] = labels

        # 检查 generation 是否需要更新（当 spec 发生变化时）
        # 这里简化处理：如果 spec 有变化，generation 会自动递增（需要在模型中处理）
        # 或者可以在 defaults 中检查并更新

        with transaction.atomic():
            entity, created = self.model_class.objects.get_or_create(
                namespace=namespace,
                name=name,
                defaults=create_data,
            )

            # 如果 spec 发生变化，更新数据以及 generation
            if not created and (cleaned_spec != entity.get_spec() or entity.labels != labels):
                for field in cleaned_spec:
                    setattr(entity, field, cleaned_spec[field])
                entity.labels = labels
                entity.generation += 1
                entity.save()

        return entity.to_json()

    def get(self, namespace: str, name: str) -> dict[str, Any]:
        """
        获取资源

        Args:
            namespace: 命名空间
            name: 资源名称

        Returns:
            资源的 JSON 表示
        """
        try:
            entity = self.model_class.objects.get(namespace=namespace, name=name)
        except self.model_class.DoesNotExist:
            raise ValidationError(f"Entity not found: {namespace}/{name}")

        return entity.to_json()

    def list(self, namespace: str = "", name: str = "") -> list[dict[str, Any]]:
        """
        列表查询资源

        Args:
            namespace: 命名空间
            name: 资源名称
        Returns:
            资源列表的 JSON 表示
        """

        queryset = self.model_class.objects.all()

        if namespace:
            queryset = queryset.filter(namespace=namespace)
        if name:
            queryset = queryset.filter(name=name)

        # TODO: 根据标签选择器过滤

        # 转换为 JSON
        results = []
        for entity in queryset:
            results.append(entity.to_json())

        return results

    def delete(self, namespace: str, name: str) -> None:
        """
        删除资源

        Args:
            namespace: 命名空间
            name: 资源名称

        """
        try:
            entity = self.model_class.objects.get(namespace=namespace, name=name)
        except self.model_class.DoesNotExist:
            raise ValidationError(f"Entity not found: {namespace}/{name}")

        entity.delete()


class EntityHandlerFactory:
    """
    实体处理器工厂，自动发现所有继承自 EntityMeta 的模型
    """

    _model_kind_map: dict[str, type[EntityMeta]] = {}

    @classmethod
    def _discover_entity_models(cls):
        """自动发现所有继承自 EntityMeta 的模型"""
        if cls._model_kind_map:
            return cls._model_kind_map

        # 获取所有已注册的模型
        for app_config in apps.get_app_configs():
            for model in app_config.get_models():
                # 检查是否继承自 EntityMeta 且不是抽象类
                if issubclass(model, EntityMeta) and not model._meta.abstract and model != EntityMeta:
                    cls._model_kind_map[model.get_kind()] = model

        return cls._model_kind_map

    @classmethod
    def get_handler(cls, kind: str) -> EntityHandler:
        """
        根据 kind 获取对应的处理器

        Args:
            kind: 实体类型（kind），支持 PascalCase 或 camelCase

        Returns:
            EntityHandler 实例
        """
        # 确保已发现所有模型
        cls._discover_entity_models()

        model_class = cls._model_kind_map.get(kind)

        if not model_class:
            raise ValidationError(_("unsupported kind: {}").format(kind))

        return EntityHandler(model_class=model_class)


class ApplyEntityResource(Resource):
    """
    应用实体资源（声明式API，通用接口）
    """

    class RequestSerializer(serializers.Serializer):
        class Metadata(serializers.Serializer):
            namespace = serializers.CharField(required=True, label=_("命名空间"))
            name = serializers.CharField(required=True, label=_("资源名称"))
            labels = serializers.DictField(
                required=False, label=_("标签"), allow_empty=True, child=serializers.CharField()
            )

        kind = serializers.CharField(required=True, label=_("实体类型"))
        metadata = Metadata(required=True, label=_("元数据"))
        spec = serializers.DictField(required=True, label=_("资源配置"), allow_empty=True)

    def perform_request(self, validated_request_data):
        kind = validated_request_data["kind"]
        metadata = validated_request_data["metadata"]
        spec = validated_request_data["spec"]

        handler = EntityHandlerFactory.get_handler(kind)
        return handler.apply(metadata=metadata, spec=spec)


class GetEntityResource(Resource):
    """获取实体资源（通用接口）"""

    class RequestSerializer(serializers.Serializer):
        kind = serializers.CharField(required=True, label=_("实体类型"))
        namespace = serializers.CharField(required=True, label=_("命名空间"))
        name = serializers.CharField(required=True, label=_("资源名称"))

    def perform_request(self, validated_request_data):
        kind = validated_request_data["kind"]
        namespace = validated_request_data["namespace"]
        name = validated_request_data["name"]

        handler = EntityHandlerFactory.get_handler(kind)
        return handler.get(namespace=namespace, name=name)


class ListEntityResource(Resource):
    """列表查询实体资源（通用接口）"""

    class RequestSerializer(serializers.Serializer):
        kind = serializers.CharField(required=True, label=_("实体类型"))
        namespace = serializers.CharField(required=False, label=_("命名空间"))
        name = serializers.CharField(required=False, label=_("资源名称"))

    def perform_request(self, validated_request_data):
        kind = validated_request_data["kind"]
        namespace = validated_request_data.get("namespace")
        name = validated_request_data.get("name")

        handler = EntityHandlerFactory.get_handler(kind)
        return handler.list(namespace=namespace, name=name)


class DeleteEntityResource(Resource):
    """删除实体资源（通用接口）"""

    class RequestSerializer(serializers.Serializer):
        kind = serializers.CharField(required=True, label=_("实体类型"))
        namespace = serializers.CharField(required=True, label=_("命名空间"))
        name = serializers.CharField(required=True, label=_("资源名称"))

    def perform_request(self, validated_request_data):
        kind = validated_request_data["kind"]
        namespace = validated_request_data["namespace"]
        name = validated_request_data["name"]

        handler = EntityHandlerFactory.get_handler(kind)
        return handler.delete(namespace=namespace, name=name)
