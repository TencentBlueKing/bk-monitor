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
from opentelemetry import trace
from rest_framework import serializers

from bkm_space.utils import bk_biz_id_to_space_uid
from core.drf_resource import Resource
from core.errors.metadata import EntityNotFoundError, UnsupportedKindError
from metadata.models import EntityMeta, RelationDefinition, ResourceDefinition

logger = logging.getLogger("metadata")
tracer = trace.get_tracer(__name__)


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
        with tracer.start_as_current_span("entity_handler.apply") as span:
            namespace = metadata.get("namespace", "")
            name = metadata.get("name", "")
            span.set_attribute("entity.kind", self.model_class.get_kind())
            span.set_attribute("entity.namespace", namespace)
            span.set_attribute("entity.name", name)

            # 校验 spec
            spec_slz_class = self.model_class.get_serializer_class()
            spec_slz = spec_slz_class(data=spec)
            spec_slz.is_valid(raise_exception=True)
            cleaned_spec = spec_slz.validated_data

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
                    span.set_attribute("entity.action", "updated")
                else:
                    span.set_attribute("entity.action", "created" if created else "unchanged")

            # Redis 缓存同步
            self._sync_to_redis(entity)

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
        with tracer.start_as_current_span("entity_handler.get") as span:
            span.set_attribute("entity.kind", self.model_class.get_kind())
            span.set_attribute("entity.namespace", namespace)
            span.set_attribute("entity.name", name)

            try:
                entity = self.model_class.objects.get(namespace=namespace, name=name)
                return entity.to_json()
            except self.model_class.DoesNotExist:
                span.set_attribute("error", True)
                span.set_attribute("error.message", "entity not found")
                raise EntityNotFoundError(context={"namespace": namespace, "name": name})

    def list(self, namespace: str = "", name: str = "") -> list[dict[str, Any]]:
        """
        列表查询资源

        Args:
            namespace: 命名空间
            name: 资源名称
        Returns:
            资源列表的 JSON 表示
        """
        with tracer.start_as_current_span("entity_handler.list") as span:
            span.set_attribute("entity.kind", self.model_class.get_kind())
            if namespace:
                span.set_attribute("entity.namespace", namespace)
            if name:
                span.set_attribute("entity.name", name)

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

            span.set_attribute("entity.count", len(results))
            return results

    def delete(self, namespace: str, name: str) -> None:
        """
        删除资源

        Args:
            namespace: 命名空间
            name: 资源名称

        """
        with tracer.start_as_current_span("entity_handler.delete") as span:
            span.set_attribute("entity.kind", self.model_class.get_kind())
            span.set_attribute("entity.namespace", namespace)
            span.set_attribute("entity.name", name)

            try:
                entity = self.model_class.objects.get(namespace=namespace, name=name)
                entity.delete()
            except self.model_class.DoesNotExist:
                span.set_attribute("error", True)
                span.set_attribute("error.message", "entity not found")
                raise EntityNotFoundError(context={"namespace": namespace, "name": name})

    def _sync_to_redis(self, entity: EntityMeta):
        """同步实体到 Redis（调用独立函数）"""
        from metadata.service.relation_redis import (
            push_and_publish_relation_definition,
            push_and_publish_resource_definition,
        )

        if isinstance(entity, ResourceDefinition):
            push_and_publish_resource_definition(entity.name)
        elif isinstance(entity, RelationDefinition):
            push_and_publish_relation_definition(entity.namespace, entity.name)
        # CustomRelationStatus 不需要同步到 Redis


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
            kind: 实体类型

        Returns:
            EntityHandler 实例
        """
        # 确保已发现所有模型
        cls._discover_entity_models()

        model_class = cls._model_kind_map.get(kind)

        if not model_class:
            raise UnsupportedKindError(context={"kind": kind})

        return EntityHandler(model_class=model_class)


class ApplyEntityResource(Resource):
    """
    应用实体资源（声明式API，通用接口）

    @apiDescription 应用实体资源，支持创建或更新实体。如果实体已存在则更新，不存在则创建。
    @api {POST} /api/v3/meta/entity/apply/ 应用实体资源
    @apiName ApplyEntityResource
    @apiGroup Entity
    @apiParam {String} kind 实体类型
    @apiParam {Object} metadata 资源元数据
    @apiParam {String} [metadata.namespace] 命名空间，可选。如果提供了 bk_biz_id，则会被自动转换覆盖
    @apiParam {String} metadata.name 资源名称
    @apiParam {Object} [metadata.labels={}] 标签，键值对格式
    @apiParam {Object} spec 资源配置，根据不同的实体类型有不同的字段
    @apiParam {Number} [bk_biz_id] 业务ID，可选。如果提供，会自动转换为 space_uid 并覆盖 metadata.namespace
    @apiParamExample {json} Request-Example:
        {
            "kind": "CustomRelationStatus",
            "metadata": {
                "namespace": "default",
                "name": "relation-001",
                "labels": {
                    "env": "production",
                    "app": "monitor"
                }
            },
            "spec": {
                "from_resource": "source_entity",
                "to_resource": "target_entity"
            }
        }
    @apiParamExample {json} Request-Example-With-BkBizId:
        {
            "kind": "CustomRelationStatus",
            "metadata": {
                "name": "relation-001",
                "labels": {
                    "env": "production",
                    "app": "monitor"
                }
            },
            "spec": {
                "from_resource": "source_entity",
                "to_resource": "target_entity"
            },
            "bk_biz_id": 2
        }
    @apiSuccessExample {json} Success-Response:
        {
            "kind": "CustomRelationStatus",
            "metadata": {
                "namespace": "default",
                "name": "relation-001",
                "labels": {
                    "env": "production",
                    "app": "monitor"
                },
                "generation": 1,
                "creationTimestamp": "2021-01-01T00:00:00Z",
                "uid": "b194835f-7726-474d-b21f-cf5c859c11e6"
            },
            "spec": {
                "from_resource": "source_entity",
                "to_resource": "target_entity"
            }
        }
    """

    class RequestSerializer(serializers.Serializer):
        class Metadata(serializers.Serializer):
            namespace = serializers.CharField(required=False, label=_("命名空间"))
            name = serializers.CharField(required=True, label=_("资源名称"))
            labels = serializers.DictField(
                required=False, label=_("标签"), allow_empty=True, child=serializers.CharField()
            )

        kind = serializers.CharField(required=True, label=_("实体类型"))
        metadata = Metadata(required=True, label=_("元数据"))
        spec = serializers.DictField(required=True, label=_("资源配置"), allow_empty=True)
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")

        def validate(self, attrs):
            # 如果 bk_biz_id 存在，则覆盖 metadata.namespace
            if "bk_biz_id" in attrs and attrs["bk_biz_id"]:
                space_uid = bk_biz_id_to_space_uid(attrs["bk_biz_id"])
                if not space_uid:
                    raise serializers.ValidationError(_("无效的业务ID: %s") % attrs["bk_biz_id"])
                attrs["metadata"]["namespace"] = space_uid
            elif "namespace" not in attrs["metadata"]:
                raise serializers.ValidationError(_("metadata.namespace 字段不能为空"))
            return attrs

    def perform_request(self, validated_request_data):
        kind = validated_request_data["kind"]
        metadata = validated_request_data["metadata"]
        spec = validated_request_data["spec"]

        handler = EntityHandlerFactory.get_handler(kind)
        return handler.apply(metadata=metadata, spec=spec)


class GetEntityResource(Resource):
    """
    获取实体资源（通用接口）

    @apiDescription 根据命名空间和名称获取单个实体资源的详细信息
    @api {GET} /api/v3/meta/entity/get/ 获取实体资源
    @apiName GetEntityResource
    @apiGroup Entity
    @apiParam {String} kind 实体类型
    @apiParam {String} [namespace] 命名空间，可选。如果提供了 bk_biz_id，则会被自动转换覆盖
    @apiParam {String} name 资源名称
    @apiParam {Number} [bk_biz_id] 业务ID，可选。如果提供，会自动转换为 space_uid 并覆盖 namespace
    @apiParamExample {json} Request-Example:
        {
            "kind": "CustomRelationStatus",
            "namespace": "default",
            "name": "relation-001"
        }
    @apiParamExample {json} Request-Example-With-BkBizId:
        {
            "kind": "CustomRelationStatus",
            "name": "relation-001",
            "bk_biz_id": 2
        }
    @apiSuccessExample {json} Success-Response:
        {
            "kind": "CustomRelationStatus",
            "metadata": {
                "namespace": "default",
                "name": "relation-001",
                "labels": {
                    "env": "production",
                    "app": "monitor"
                },
                "generation": 1,
                "creationTimestamp": "2021-01-01T00:00:00Z",
                "uid": "b194835f-7726-474d-b21f-cf5c859c11e6"
            },
            "spec": {
                "from_resource": "source_entity",
                "to_resource": "target_entity"
            }
        }
    """

    class RequestSerializer(serializers.Serializer):
        kind = serializers.CharField(required=True, label=_("实体类型"))
        namespace = serializers.CharField(required=False, label=_("命名空间"))
        name = serializers.CharField(required=True, label=_("资源名称"))
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")

        def validate(self, attrs):
            # 如果 bk_biz_id 存在，则覆盖 namespace，否则 namespace 为必填
            if "bk_biz_id" in attrs and attrs["bk_biz_id"]:
                space_uid = bk_biz_id_to_space_uid(attrs["bk_biz_id"])
                if not space_uid:
                    raise serializers.ValidationError(_("无效的业务ID: %s") % attrs["bk_biz_id"])
                attrs["namespace"] = space_uid
            elif "namespace" not in attrs:
                raise serializers.ValidationError(_("namespace 字段不能为空"))
            return attrs

    def perform_request(self, validated_request_data):
        kind = validated_request_data["kind"]
        namespace = validated_request_data["namespace"]
        name = validated_request_data["name"]

        handler = EntityHandlerFactory.get_handler(kind)
        return handler.get(namespace=namespace, name=name)


class ListEntityResource(Resource):
    """
    列表查询实体资源（通用接口）

    @apiDescription 查询实体资源列表，支持按命名空间和名称过滤
    @api {GET} /api/v3/meta/entity/list/ 列表查询实体资源
    @apiName ListEntityResource
    @apiGroup Entity
    @apiParam {String} kind 实体类型
    @apiParam {String} [namespace=""] 命名空间，可选，用于过滤。如果提供了 bk_biz_id，则会被自动转换覆盖
    @apiParam {String} [name=""] 资源名称，可选，用于过滤
    @apiParam {Number} [bk_biz_id] 业务ID，可选。如果提供，会自动转换为 space_uid 并覆盖 namespace
    @apiParamExample {json} Request-Example:
        {
            "kind": "CustomRelationStatus",
            "namespace": "default",
            "name": "relation-001"
        }
    @apiParamExample {json} Request-Example-All:
        {
            "kind": "CustomRelationStatus"
        }
    @apiParamExample {json} Request-Example-With-BkBizId:
        {
            "kind": "CustomRelationStatus",
            "bk_biz_id": 2
        }
    @apiSuccessExample {json} Success-Response:
        [
            {
                "kind": "CustomRelationStatus",
                "metadata": {
                    "namespace": "default",
                    "name": "relation-001",
                    "labels": {
                        "env": "production",
                        "app": "monitor"
                    },
                    "generation": 1,
                    "creationTimestamp": "2021-01-01T00:00:00Z",
                    "uid": "b194835f-7726-474d-b21f-cf5c859c11e6"
                },
                "spec": {
                    "from_resource": "source_entity",
                    "to_resource": "target_entity"
                }
            }
        ]
    """

    class RequestSerializer(serializers.Serializer):
        kind = serializers.CharField(required=True, label=_("实体类型"))
        namespace = serializers.CharField(required=False, label=_("命名空间"))
        name = serializers.CharField(required=False, label=_("资源名称"))
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")

        def validate(self, attrs):
            # 如果 bk_biz_id 存在，则覆盖 namespace
            if "bk_biz_id" in attrs and attrs["bk_biz_id"]:
                space_uid = bk_biz_id_to_space_uid(attrs["bk_biz_id"])
                if not space_uid:
                    raise serializers.ValidationError(_("无效的业务ID: %s") % attrs["bk_biz_id"])
                attrs["namespace"] = space_uid
            return attrs

    def perform_request(self, validated_request_data):
        kind = validated_request_data["kind"]
        namespace = validated_request_data.get("namespace")
        name = validated_request_data.get("name")

        handler = EntityHandlerFactory.get_handler(kind)
        return handler.list(namespace=namespace, name=name)


class DeleteEntityResource(Resource):
    """
    删除实体资源（通用接口）

    @apiDescription 根据命名空间和名称删除指定的实体资源
    @api {POST} /api/v3/meta/entity/delete/ 删除实体资源
    @apiName DeleteEntityResource
    @apiGroup Entity
    @apiParam {String} kind 实体类型
    @apiParam {String} [namespace] 命名空间，可选。如果提供了 bk_biz_id，则会被自动转换覆盖
    @apiParam {String} name 资源名称
    @apiParam {Number} [bk_biz_id] 业务ID，可选。如果提供，会自动转换为 space_uid 并覆盖 namespace
    @apiParamExample {json} Request-Example:
        {
            "kind": "CustomRelationStatus",
            "namespace": "default",
            "name": "relation-001"
        }
    @apiParamExample {json} Request-Example-With-BkBizId:
        {
            "kind": "CustomRelationStatus",
            "name": "relation-001",
            "bk_biz_id": 2
        }
    """

    class RequestSerializer(serializers.Serializer):
        kind = serializers.CharField(required=True, label=_("实体类型"))
        namespace = serializers.CharField(required=False, label=_("命名空间"))
        name = serializers.CharField(required=True, label=_("资源名称"))
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")

        def validate(self, attrs):
            # 如果 bk_biz_id 存在，则覆盖 namespace，否则 namespace 为必填
            if "bk_biz_id" in attrs and attrs["bk_biz_id"]:
                space_uid = bk_biz_id_to_space_uid(attrs["bk_biz_id"])
                if not space_uid:
                    raise serializers.ValidationError(_("无效的业务ID: %s") % attrs["bk_biz_id"])
                attrs["namespace"] = space_uid
            elif "namespace" not in attrs:
                raise serializers.ValidationError(_("namespace 字段不能为空"))
            return attrs

    def perform_request(self, validated_request_data):
        kind = validated_request_data["kind"]
        namespace = validated_request_data["namespace"]
        name = validated_request_data["name"]

        handler = EntityHandlerFactory.get_handler(kind)
        return handler.delete(namespace=namespace, name=name)
