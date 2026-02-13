"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import uuid
from typing import Any

from django.db import models
from django.utils.translation import gettext as _
from rest_framework import serializers

from metadata.models.common import BaseModel


class EntityMeta(BaseModel):
    """
    实体类型抽象基类，用于描述资源实体的范围
    """

    META_FIELDS = (
        # EntityMeta 中的字段
        "namespace",
        "name",
        "uid",
        "generation",
        "labels",
        # BaseModel 的审计字段
        "creator",
        "create_time",
        "updater",
        "update_time",
    )

    uid = models.UUIDField(_("唯一标识符"), default=uuid.uuid4, editable=False, unique=True, db_index=True)
    generation = models.BigIntegerField(_("世代号"), default=1, help_text=_("跟踪资源规格变更次数"))
    namespace = models.CharField(_("命名空间"), max_length=128, db_index=True)
    name = models.CharField(_("资源名称"), max_length=128)
    labels = models.JSONField(_("资源标签"), default=dict)

    class Meta:
        unique_together = ("namespace", "name")
        abstract = True

    def __str__(self):
        return f"{self.namespace}/{self.name}"

    @classmethod
    def get_kind(cls) -> str:
        """
        返回实体类型 (Entity Type), 类似 Kubernetes 中的 kind 字段
        默认返回类名，子类可以重写此属性以返回自定义的实体类型标识
        """
        return cls.__name__

    @classmethod
    def get_spec_fields(cls) -> list[str]:
        """
        获取资源规格字段，排除metadata中的字段 (namespace, name 等) 和 BaseModel 的审计字段
        """
        fields = []
        for field in cls._meta.fields:
            # 排除主键和指定字段
            if field.primary_key or field.name in cls.META_FIELDS:
                continue
            fields.append(field.name)
        return fields

    def get_spec(self) -> dict[str, Any]:
        """
        获取spec部分，子类可以重写此方法
        """

        spec = {}
        for field in self.get_spec_fields():
            spec[field] = getattr(self, field)
        return spec

    def to_json(self) -> dict[str, Any]:
        """
        生成JSON结构，类似 Kubernetes 资源格式
        """
        metadata = {
            "uid": str(self.uid),
            "creationTimestamp": self.create_time.isoformat(),
            "namespace": self.namespace,
            "name": self.name,
            "generation": self.generation,
            "labels": self.labels,
        }

        return {
            "kind": self.get_kind(),
            "metadata": metadata,
            "spec": self.get_spec(),
        }

    @classmethod
    def get_serializer_class(cls) -> type[serializers.ModelSerializer]:
        """
        获取用于校验 spec_fields 的序列化器类，子类可以重写此方法
        """
        cache_attr = "_serializer_class_cache"
        if hasattr(cls, cache_attr):
            return getattr(cls, cache_attr)

        class Meta:
            model = cls
            fields = tuple(cls.get_spec_fields())

        serializer_class = type(f"{cls.__name__}SpecSerializer", (serializers.ModelSerializer,), {"Meta": Meta})
        setattr(cls, cache_attr, serializer_class)
        return serializer_class


class CustomRelationStatus(EntityMeta):
    """自定义关联状态表"""

    from_resource = models.CharField(_("源资源"), max_length=128)
    to_resource = models.CharField(_("目标资源"), max_length=128)

    class Meta:
        verbose_name = _("自定义关联关系状态")
        verbose_name_plural = _("自定义关联关系状态")
        unique_together = ("namespace", "name")

    def __str__(self):
        return f"{self.namespace}/{self.name} -> {self.from_resource} -> {self.to_resource}"


class ResourceDefinition(EntityMeta):
    """
    资源类型定义

    定义资源的元数据结构，包括字段定义列表。
    用于 bmw 的 SchemaProvider，支持资源关联查询功能。

    字段结构示例:
    [
        {"namespace": "k8s", "name": "pod", "required": true},
        {"namespace": "bkmonitor", "name": "bk_biz_id", "required": true}
    ]
    """

    fields = models.JSONField(
        _("字段定义列表"), default=list, help_text=_("资源的字段定义，每个字段包含 namespace, name, required")
    )

    class Meta:
        verbose_name = _("资源类型定义")
        verbose_name_plural = _("资源类型定义")
        unique_together = ("namespace", "name")

    def __str__(self):
        return f"ResourceDefinition({self.namespace}/{self.name})"

    def to_redis_json(self) -> dict[str, Any]:
        """
        生成 Redis 存储格式的 JSON，供 bmw SchemaProvider 消费

        - namespace: string
        - name: string
        - fields: []FieldDefinition
        - labels: map[string]string
        """
        return {
            "namespace": self.namespace,
            "name": self.name,
            "fields": self.fields,
            "labels": self.labels,
        }


class RelationDefinition(EntityMeta):
    """
    关联关系定义

    定义资源之间的关联关系，支持单向和双向关系。
    用于 bmw 的 SchemaProvider，支持资源关联查询功能。
    """

    # 关联类别选项
    CATEGORY_STATIC = "static"
    CATEGORY_DYNAMIC = "dynamic"
    CATEGORY_CHOICES = (
        (CATEGORY_STATIC, _("静态关联")),
        (CATEGORY_DYNAMIC, _("动态关联")),
    )

    from_resource = models.CharField(_("源资源类型"), max_length=128, help_text=_("关联的源资源类型名称"))
    to_resource = models.CharField(_("目标资源类型"), max_length=128, help_text=_("关联的目标资源类型名称"))
    category = models.CharField(
        _("关联类别"),
        max_length=32,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_STATIC,
        help_text=_("静态关联或动态关联"),
    )
    is_directional = models.BooleanField(
        _("是否单向关系"), default=False, help_text=_("单向关系使用 from_to_to 格式命名")
    )
    is_belongs_to = models.BooleanField(
        _("是否归属关系"), default=False, help_text=_("仅对双向关系有效，表示 from_resource 归属于 to_resource")
    )

    class Meta:
        verbose_name = _("关联关系定义")
        verbose_name_plural = _("关联关系定义")
        unique_together = ("namespace", "name")

    def __str__(self):
        direction = "->" if self.is_directional else "<->"
        return f"RelationDefinition({self.namespace}/{self.name}: {self.from_resource} {direction} {self.to_resource})"

    def to_redis_json(self) -> dict[str, Any]:
        """
        生成 Redis 存储格式的 JSON，供 bmw SchemaProvider 消费

        - namespace: string
        - name: string
        - from_resource: string
        - to_resource: string
        - category: string
        - is_directional: bool
        - is_belongs_to: bool
        - labels: map[string]string
        """
        return {
            "namespace": self.namespace,
            "name": self.name,
            "from_resource": self.from_resource,
            "to_resource": self.to_resource,
            "category": self.category,
            "is_directional": self.is_directional,
            "is_belongs_to": self.is_belongs_to,
            "labels": self.labels,
        }
