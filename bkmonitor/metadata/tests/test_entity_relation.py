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
from datetime import datetime

import pytest
from django.db import IntegrityError
from rest_framework import serializers

from metadata.models.entity_relation import CustomRelationStatus, EntityMeta

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def create_and_delete_custom_relation_status():
    """创建和删除 CustomRelationStatus 测试数据的 fixture"""
    test_namespace = "test_namespace"
    test_name = "test_relation"

    # 清理可能存在的测试数据
    CustomRelationStatus.objects.filter(namespace=test_namespace, name=test_name).delete()

    # 创建测试数据
    instance = CustomRelationStatus.objects.create(
        namespace=test_namespace,
        name=test_name,
        from_resource="source_resource",
        to_resource="target_resource",
        generation=1,
        labels={"env": "test", "app": "monitor"},
        creator="test_user",
        updater="test_user",
    )

    yield instance

    # 清理测试数据
    CustomRelationStatus.objects.filter(id=instance.id).delete()


class TestCustomRelationStatusInheritance:
    """测试 CustomRelationStatus 继承自 EntityMeta 的方法实现"""

    def test_get_kind(self):
        """测试 get_kind() 类方法，应返回类名"""
        assert CustomRelationStatus.get_kind() == "CustomRelationStatus"
        # 验证是类方法
        assert isinstance(CustomRelationStatus.get_kind(), str)

    def test_get_kind_instance_method(self, create_and_delete_custom_relation_status):
        """测试实例调用 get_kind() 方法"""
        instance = create_and_delete_custom_relation_status
        assert instance.get_kind() == "CustomRelationStatus"

    def test_get_serializer_class_class_method(self):
        """测试类方法调用 get_serializer_class()"""
        # 验证是类方法，可以通过类直接调用
        serializer_class = CustomRelationStatus.get_serializer_class()
        assert issubclass(serializer_class, serializers.ModelSerializer)
        assert serializer_class.__name__ == "CustomRelationStatusSpecSerializer"

    def test_spec_fields_property(self, create_and_delete_custom_relation_status):
        """测试 get_spec_fields 类方法，应只包含子类定义的字段（from_resource, to_resource）"""
        instance = create_and_delete_custom_relation_status
        spec_fields = instance.get_spec_fields()

        # 应该包含子类定义的字段
        assert "from_resource" in spec_fields
        assert "to_resource" in spec_fields

        # 不应该包含 META_FIELDS 中的字段
        assert "namespace" not in spec_fields
        assert "name" not in spec_fields
        assert "uid" not in spec_fields
        assert "generation" not in spec_fields
        assert "labels" not in spec_fields
        assert "creator" not in spec_fields
        assert "create_time" not in spec_fields
        assert "updater" not in spec_fields
        assert "update_time" not in spec_fields

        # 验证字段列表长度
        assert len(spec_fields) == 2

    def test_get_spec(self, create_and_delete_custom_relation_status):
        """测试 get_spec() 方法，应返回包含 spec_fields 的字典"""
        instance = create_and_delete_custom_relation_status
        spec = instance.get_spec()

        # 验证返回的是字典
        assert isinstance(spec, dict)

        # 验证包含子类定义的字段
        assert "from_resource" in spec
        assert "to_resource" in spec
        assert spec["from_resource"] == "source_resource"
        assert spec["to_resource"] == "target_resource"

        # 验证不包含 META_FIELDS 中的字段
        assert "namespace" not in spec
        assert "name" not in spec
        assert "uid" not in spec

    def test_to_json(self, create_and_delete_custom_relation_status):
        """测试 to_json() 方法，应返回完整的 Kubernetes 风格的 JSON 结构"""
        instance = create_and_delete_custom_relation_status
        json_data = instance.to_json()

        # 验证返回的是字典
        assert isinstance(json_data, dict)

        # 验证包含 kind 字段
        assert "kind" in json_data
        assert json_data["kind"] == "CustomRelationStatus"

        # 验证包含 metadata 字段
        assert "metadata" in json_data
        metadata = json_data["metadata"]
        assert isinstance(metadata, dict)
        assert "uid" in metadata
        assert "namespace" in metadata
        assert metadata["namespace"] == "test_namespace"
        assert "name" in metadata
        assert metadata["name"] == "test_relation"
        assert "generation" in metadata
        assert metadata["generation"] == 1
        assert "labels" in metadata
        assert metadata["labels"] == {"env": "test", "app": "monitor"}
        assert "creationTimestamp" in metadata
        # 验证 creationTimestamp 是有效的 ISO 格式字符串
        datetime.fromisoformat(metadata["creationTimestamp"].replace("Z", "+00:00"))

        # 验证包含 spec 字段
        assert "spec" in json_data
        spec = json_data["spec"]
        assert isinstance(spec, dict)
        assert "from_resource" in spec
        assert "to_resource" in spec
        assert spec["from_resource"] == "source_resource"
        assert spec["to_resource"] == "target_resource"

    def test_get_serializer_class(self, create_and_delete_custom_relation_status):
        """测试 get_serializer_class() 方法，应返回正确的序列化器类"""
        # get_serializer_class 现在是类方法，可以直接通过类调用
        serializer_class = CustomRelationStatus.get_serializer_class()

        # 验证返回的是序列化器类
        assert issubclass(serializer_class, serializers.ModelSerializer)

        # 验证类名
        assert serializer_class.__name__ == "CustomRelationStatusSpecSerializer"

        # 验证序列化器包含正确的字段
        serializer = serializer_class(data={"from_resource": "source_resource", "to_resource": "target_resource"})
        assert serializer.is_valid()
        serializer_data = serializer.validated_data

        # 应该只包含 spec_fields 中的字段
        assert "from_resource" in serializer_data
        assert "to_resource" in serializer_data
        assert serializer_data["from_resource"] == "source_resource"
        assert serializer_data["to_resource"] == "target_resource"

        # 不应该包含 META_FIELDS 中的字段
        assert "namespace" not in serializer_data
        assert "name" not in serializer_data
        assert "uid" not in serializer_data

    def test_get_serializer_class_caching(self, create_and_delete_custom_relation_status):
        """测试 get_serializer_class() 方法的缓存机制"""
        # get_serializer_class 现在是类方法，可以直接通过类调用

        # 第一次调用
        serializer_class_1 = CustomRelationStatus.get_serializer_class()

        # 第二次调用，应该返回同一个类（缓存）
        serializer_class_2 = CustomRelationStatus.get_serializer_class()

        assert serializer_class_1 is serializer_class_2

        # 验证缓存属性存在（现在在类上）
        assert hasattr(CustomRelationStatus, "_serializer_class_cache")
        assert CustomRelationStatus._serializer_class_cache is serializer_class_1

    def test_str_method(self, create_and_delete_custom_relation_status):
        """测试 __str__() 方法，子类重写了父类方法"""
        instance = create_and_delete_custom_relation_status
        str_repr = str(instance)

        # 验证格式：namespace/name -> from_resource -> to_resource
        assert "test_namespace" in str_repr
        assert "test_relation" in str_repr
        assert "source_resource" in str_repr
        assert "target_resource" in str_repr
        assert "->" in str_repr

        # 验证格式正确
        expected_format = f"{instance.namespace}/{instance.name} -> {instance.from_resource} -> {instance.to_resource}"
        assert str_repr == expected_format

    def test_inheritance_from_entity_meta(self):
        """测试继承关系，验证 CustomRelationStatus 确实是 EntityMeta 的子类"""
        assert issubclass(CustomRelationStatus, EntityMeta)
        assert CustomRelationStatus.__bases__ == (EntityMeta,)

    def test_meta_fields_inheritance(self, create_and_delete_custom_relation_status):
        """测试 META_FIELDS 的继承，验证子类可以访问父类的 META_FIELDS"""
        # 验证 META_FIELDS 包含所有预期的字段
        meta_fields = EntityMeta.META_FIELDS
        assert "namespace" in meta_fields
        assert "name" in meta_fields
        assert "uid" in meta_fields
        assert "generation" in meta_fields
        assert "labels" in meta_fields
        assert "creator" in meta_fields
        assert "create_time" in meta_fields
        assert "updater" in meta_fields
        assert "update_time" in meta_fields

    def test_uid_generation(self, create_and_delete_custom_relation_status):
        """测试 uid 字段的自动生成"""
        instance = create_and_delete_custom_relation_status

        # 验证 uid 是 UUID 类型
        assert isinstance(instance.uid, uuid.UUID)

        # 验证 uid 是唯一的
        instance2 = CustomRelationStatus.objects.create(
            namespace="test_namespace2",
            name="test_relation2",
            from_resource="source2",
            to_resource="target2",
            creator="test_user",
            updater="test_user",
        )
        assert instance.uid != instance2.uid
        instance2.delete()

    def test_generation_default_value(self, create_and_delete_custom_relation_status):
        """测试 generation 字段的默认值"""
        instance = create_and_delete_custom_relation_status
        # 创建时指定了 generation=1，验证正确
        assert instance.generation == 1

        # 创建新实例，不指定 generation，应该使用默认值 1
        instance2 = CustomRelationStatus.objects.create(
            namespace="test_namespace3",
            name="test_relation3",
            from_resource="source3",
            to_resource="target3",
            creator="test_user",
            updater="test_user",
        )
        assert instance2.generation == 1
        instance2.delete()

    def test_labels_default_value(self, create_and_delete_custom_relation_status):
        """测试 labels 字段的默认值和设置"""
        instance = create_and_delete_custom_relation_status
        # 创建时指定了 labels
        assert instance.labels == {"env": "test", "app": "monitor"}

        # 创建新实例，不指定 labels，应该使用默认值 {}
        instance2 = CustomRelationStatus.objects.create(
            namespace="test_namespace4",
            name="test_relation4",
            from_resource="source4",
            to_resource="target4",
            creator="test_user",
            updater="test_user",
        )
        assert instance2.labels == {}
        instance2.delete()

    def test_unique_together_constraint(self):
        """测试 namespace 和 name 的唯一性约束"""
        # 清理可能存在的测试数据
        CustomRelationStatus.objects.filter(namespace="unique_test_namespace", name="unique_test_name").delete()

        # 创建第一个实例（用于测试唯一约束）
        CustomRelationStatus.objects.create(
            namespace="unique_test_namespace",
            name="unique_test_name",
            from_resource="source1",
            to_resource="target1",
            creator="test_user",
            updater="test_user",
        )

        # 尝试创建相同 namespace 和 name 的实例，应该失败
        # 注意：由于 pytest-django 的事务管理，IntegrityError 会导致事务回滚
        # 所以我们需要在另一个数据库连接中验证约束
        with pytest.raises(IntegrityError):
            CustomRelationStatus.objects.create(
                namespace="unique_test_namespace",
                name="unique_test_name",
                from_resource="source2",
                to_resource="target2",
                creator="test_user",
                updater="test_user",
            )

    def test_to_json_with_empty_labels(self):
        """测试 to_json() 方法处理空 labels 的情况"""
        instance = CustomRelationStatus.objects.create(
            namespace="empty_labels_namespace",
            name="empty_labels_name",
            from_resource="source",
            to_resource="target",
            labels={},
            creator="test_user",
            updater="test_user",
        )

        json_data = instance.to_json()
        assert json_data["metadata"]["labels"] == {}

        instance.delete()

    def test_get_spec_with_updated_fields(self, create_and_delete_custom_relation_status):
        """测试 get_spec() 方法在字段更新后的行为"""
        instance = create_and_delete_custom_relation_status

        # 更新字段
        instance.from_resource = "updated_source"
        instance.to_resource = "updated_target"
        instance.save()

        # 验证 get_spec() 返回更新后的值
        spec = instance.get_spec()
        assert spec["from_resource"] == "updated_source"
        assert spec["to_resource"] == "updated_target"


class TestAutoQueryGraphDefinitions:
    def test_rejects_empty_space_uid_before_fallback(self, monkeypatch):
        from bkm_space import utils as space_utils

        from metadata.models.entity_relation import EntityMeta

        monkeypatch.setattr(space_utils, "bk_biz_id_to_space_uid", lambda bk_biz_id: "")

        with pytest.raises(ValueError, match=r"cannot resolve to a valid space uid"):
            EntityMeta.auto_query_graph_definitions(-42)


class TestConvertToVerticesAndRelations:

    def _make_resource_defs(self, data):
        from metadata.models.entity_relation import ResourceDefinition

        return ResourceDefinition(
            namespace=data.get("namespace", "__all__"),
            name=data["name"], fields=data.get("fields", []),
            labels=data.get("labels", {}), generation=1, creator="test", updater="test",
        )

    def _make_relation_defs(self, data):
        from metadata.models.entity_relation import RelationDefinition

        return RelationDefinition(
            namespace=data.get("namespace", "__all__"), name=data["name"],
            from_resource=data["from_resource"], to_resource=data["to_resource"],
            category=data.get("category", "static"),
            is_directional=data.get("is_directional", False),
            is_belongs_to=data.get("is_belongs_to", False),
            labels=data.get("labels", {}), generation=1, creator="test", updater="test",
        )

    def _make_required_resource_defs(self, *names):
        return [
            self._make_resource_defs({"name": name, "fields": [{"name": f"{name}_id", "required": True}]})
            for name in names
        ]

    def test_full_conversion_uses_bmw_relation_name(self):
        from metadata.models.entity_relation import convert_to_vertices_and_relations

        resource_defs = [
            self._make_resource_defs({
                "name": "pod",
                "fields": [{"namespace": "k8s", "name": "pod_name", "required": True}],
            }),
            self._make_resource_defs({
                "name": "node",
                "fields": [{"namespace": "k8s", "name": "node_ip", "required": True}],
            }),
        ]
        relation_defs = [self._make_relation_defs({
            "name": "pod_node", "from_resource": "pod", "to_resource": "node",
            "labels": {"metric_name": "pod_node_custom_metric"},
        })]

        vertices, relations = convert_to_vertices_and_relations(resource_defs, relation_defs)

        assert vertices == [
            {"name": "pod", "id_fields": ["pod_name"], "delimiter": "_"},
            {"name": "node", "id_fields": ["node_ip"], "delimiter": "_"},
        ]
        assert relations == [{
            "name": "pod_node", "from": "pod", "to": "node",
            "metric": "node_with_pod_relation", "delimiter": "_",
        }]

    def test_metric_falls_back_to_bidirectional_bmw_relation_name(self):
        from metadata.models.entity_relation import convert_to_vertices_and_relations

        _, relations = convert_to_vertices_and_relations(
            self._make_required_resource_defs("service", "pod"),
            [
                self._make_relation_defs({
                    "name": "svc_pod", "from_resource": "service", "to_resource": "pod", "labels": {},
                }),
            ],
        )
        assert relations[0]["metric"] == "pod_with_service_relation"

    def test_metric_falls_back_to_directional_bmw_relation_name(self):
        from metadata.models.entity_relation import convert_to_vertices_and_relations

        _, relations = convert_to_vertices_and_relations(
            self._make_required_resource_defs("pod", "node"),
            [
                self._make_relation_defs(
                    {
                        "name": "pod_node",
                        "from_resource": "pod",
                        "to_resource": "node",
                        "is_directional": True,
                        "labels": {},
                    }
                ),
            ],
        )
        assert relations[0]["metric"] == "pod_to_node_flow"

    def test_metric_falls_back_when_relation_labels_are_not_dict(self):
        from metadata.models.entity_relation import convert_to_vertices_and_relations

        _, relations = convert_to_vertices_and_relations(
            self._make_required_resource_defs("service", "pod"),
            [
                self._make_relation_defs({
                    "name": "svc_pod",
                    "from_resource": "service",
                    "to_resource": "pod",
                    "labels": ["metric_name"],
                }),
            ],
        )

        assert relations[0]["metric"] == "pod_with_service_relation"

    def test_dedup_keeps_first_occurrence(self):
        from metadata.models.entity_relation import convert_to_vertices_and_relations

        resource_defs = [
            self._make_resource_defs({"name": "pod", "fields": [{"name": "a", "required": True}]}),
            self._make_resource_defs({"name": "pod", "fields": [{"name": "b"}]}),
        ]
        vertices, _ = convert_to_vertices_and_relations(resource_defs, [])
        assert len(vertices) == 1 and vertices[0]["id_fields"] == ["a"]

    def test_id_fields_use_required_fields_only(self):
        from metadata.models.entity_relation import convert_to_vertices_and_relations

        resource_defs = [
            self._make_resource_defs({
                "name": "host",
                "fields": [
                    {"name": "bk_host_id", "required": True},
                    {"name": "version", "required": False},
                    {"name": "env_name"},
                ],
            }),
        ]

        vertices, _ = convert_to_vertices_and_relations(resource_defs, [])

        assert vertices[0]["id_fields"] == ["bk_host_id"]

    def test_rejects_resource_without_required_fields(self):
        from metadata.models.entity_relation import convert_to_vertices_and_relations

        resource_defs = [
            self._make_resource_defs({
                "name": "host",
                "fields": [{"name": "bk_host_id"}, {"name": "version", "required": False}],
            }),
        ]

        with pytest.raises(ValueError, match=r"ResourceDefinition\[host\].*required field"):
            convert_to_vertices_and_relations(resource_defs, [])

    def test_rejects_resource_field_with_invalid_schema(self):
        from metadata.models.entity_relation import convert_to_vertices_and_relations

        invalid_cases = [
            ([{"name": "host", "fields": {"name": "bk_host_id", "required": True}}], r"fields must be a list"),
            ([{"name": "host", "fields": ["bk_host_id"]}], r"fields\[0\] must be an object"),
            ([{"name": "host", "fields": [{"name": " ", "required": True}]}], r"name must be a non-empty string"),
            ([{"name": "host", "fields": [{"name": "bk_host_id", "required": "yes"}]}], r"required must be a boolean"),
        ]

        for resource_data, message in invalid_cases:
            with pytest.raises(ValueError, match=message):
                convert_to_vertices_and_relations([self._make_resource_defs(data) for data in resource_data], [])

    def test_rejects_relation_with_unknown_resource_endpoint(self):
        from metadata.models.entity_relation import convert_to_vertices_and_relations

        with pytest.raises(
            ValueError,
            match=r"RelationDefinition\[pod_node\].to_resource.*ResourceDefinition\[node\]",
        ):
            convert_to_vertices_and_relations(
                self._make_required_resource_defs("pod"),
                [
                    self._make_relation_defs({
                        "name": "pod_node",
                        "from_resource": "pod",
                        "to_resource": "node",
                    }),
                ],
            )

    def test_rejects_duplicate_relation_semantics(self):
        from metadata.models.entity_relation import convert_to_vertices_and_relations

        with pytest.raises(ValueError, match=r"RelationDefinition\[pod_node_copy\].*RelationDefinition\[pod_node\]"):
            convert_to_vertices_and_relations(
                self._make_required_resource_defs("pod", "node"),
                [
                    self._make_relation_defs({
                        "name": "pod_node",
                        "from_resource": "pod",
                        "to_resource": "node",
                    }),
                    self._make_relation_defs({
                        "name": "pod_node_copy",
                        "from_resource": "pod",
                        "to_resource": "node",
                    }),
                ],
            )

    def test_rejects_reversed_bidirectional_relation_semantics(self):
        from metadata.models.entity_relation import convert_to_vertices_and_relations

        with pytest.raises(
            ValueError,
            match=r"RelationDefinition\[node_pod\].*RelationDefinition\[pod_node\]",
        ):
            convert_to_vertices_and_relations(
                self._make_required_resource_defs("pod", "node"),
                [
                    self._make_relation_defs({
                        "name": "pod_node",
                        "from_resource": "pod",
                        "to_resource": "node",
                    }),
                    self._make_relation_defs({
                        "name": "node_pod",
                        "from_resource": "node",
                        "to_resource": "pod",
                    }),
                ],
            )

    def test_allows_reversed_directional_relation_semantics(self):
        from metadata.models.entity_relation import convert_to_vertices_and_relations

        _, relations = convert_to_vertices_and_relations(
            self._make_required_resource_defs("pod", "node"),
            [
                self._make_relation_defs({
                    "name": "pod_node",
                    "from_resource": "pod",
                    "to_resource": "node",
                    "is_directional": True,
                }),
                self._make_relation_defs({
                    "name": "node_pod",
                    "from_resource": "node",
                    "to_resource": "pod",
                    "is_directional": True,
                }),
            ],
        )

        assert [relation["metric"] for relation in relations] == ["pod_to_node_flow", "node_to_pod_flow"]
