"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest
from rest_framework.exceptions import ValidationError

from core.errors.metadata import EntityNotFoundError, UnsupportedKindError
from metadata.models.entity_relation import CustomRelationStatus
from metadata.resources.entity_relation import EntityHandler, EntityHandlerFactory

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def entity_handler():
    """创建 EntityHandler 实例"""
    return EntityHandler(model_class=CustomRelationStatus)


@pytest.fixture
def cleanup_test_data():
    """清理测试数据的 fixture"""
    # 清理测试数据
    CustomRelationStatus.objects.filter(namespace__startswith="test_").delete()
    yield
    # 测试后清理
    CustomRelationStatus.objects.filter(namespace__startswith="test_").delete()


class TestEntityHandlerApply:
    """测试 EntityHandler.apply 方法"""

    def test_apply_create_new_entity(self, entity_handler, cleanup_test_data):
        """测试创建新实体"""
        metadata = {
            "namespace": "test_namespace",
            "name": "test_entity_1",
            "labels": {"env": "test", "app": "monitor"},
        }
        spec = {
            "from_resource": "source_entity",
            "to_resource": "target_entity",
        }

        result = entity_handler.apply(metadata=metadata, spec=spec)

        # 验证返回结果
        assert result["kind"] == "CustomRelationStatus"
        assert result["metadata"]["namespace"] == "test_namespace"
        assert result["metadata"]["name"] == "test_entity_1"
        assert result["metadata"]["labels"] == {"env": "test", "app": "monitor"}
        assert result["metadata"]["generation"] == 1
        assert result["spec"]["from_resource"] == "source_entity"
        assert result["spec"]["to_resource"] == "target_entity"
        assert "uid" in result["metadata"]
        assert "creationTimestamp" in result["metadata"]

        # 验证数据库中的记录
        entity = CustomRelationStatus.objects.get(namespace="test_namespace", name="test_entity_1")
        assert entity.from_resource == "source_entity"
        assert entity.to_resource == "target_entity"
        assert entity.labels == {"env": "test", "app": "monitor"}
        assert entity.generation == 1

    def test_apply_update_existing_entity(self, entity_handler, cleanup_test_data):
        """测试更新已存在的实体"""
        # 先创建一个实体
        metadata = {
            "namespace": "test_namespace",
            "name": "test_entity_2",
            "labels": {"env": "test"},
        }
        spec = {
            "from_resource": "source_1",
            "to_resource": "target_1",
        }
        entity_handler.apply(metadata=metadata, spec=spec)

        # 更新实体
        updated_metadata = {
            "namespace": "test_namespace",
            "name": "test_entity_2",
            "labels": {"env": "prod", "app": "monitor"},
        }
        updated_spec = {
            "from_resource": "source_2",
            "to_resource": "target_2",
        }
        result = entity_handler.apply(metadata=updated_metadata, spec=updated_spec)

        # 验证 generation 已递增
        assert result["metadata"]["generation"] == 2
        assert result["spec"]["from_resource"] == "source_2"
        assert result["spec"]["to_resource"] == "target_2"
        assert result["metadata"]["labels"] == {"env": "prod", "app": "monitor"}

        # 验证数据库中的记录
        entity = CustomRelationStatus.objects.get(namespace="test_namespace", name="test_entity_2")
        assert entity.generation == 2
        assert entity.from_resource == "source_2"
        assert entity.to_resource == "target_2"
        assert entity.labels == {"env": "prod", "app": "monitor"}

    def test_apply_update_with_same_spec(self, entity_handler, cleanup_test_data):
        """测试使用相同的 spec 更新实体，generation 不应该增加"""
        # 先创建一个实体
        metadata = {
            "namespace": "test_namespace",
            "name": "test_entity_3",
            "labels": {"env": "test"},
        }
        spec = {
            "from_resource": "source_1",
            "to_resource": "target_1",
        }
        result1 = entity_handler.apply(metadata=metadata, spec=spec)
        initial_generation = result1["metadata"]["generation"]

        # 使用相同的 spec 和 labels 再次应用
        result2 = entity_handler.apply(metadata=metadata, spec=spec)

        # generation 应该保持不变
        assert result2["metadata"]["generation"] == initial_generation

    def test_apply_update_labels_only(self, entity_handler, cleanup_test_data):
        """测试仅更新 labels，spec 不变"""
        # 先创建一个实体
        metadata = {
            "namespace": "test_namespace",
            "name": "test_entity_4",
            "labels": {"env": "test"},
        }
        spec = {
            "from_resource": "source_1",
            "to_resource": "target_1",
        }
        entity_handler.apply(metadata=metadata, spec=spec)

        # 仅更新 labels
        updated_metadata = {
            "namespace": "test_namespace",
            "name": "test_entity_4",
            "labels": {"env": "prod"},
        }
        result = entity_handler.apply(metadata=updated_metadata, spec=spec)

        # generation 应该递增
        assert result["metadata"]["generation"] == 2
        assert result["metadata"]["labels"] == {"env": "prod"}

    def test_apply_with_empty_labels(self, entity_handler, cleanup_test_data):
        """测试使用空 labels"""
        metadata = {
            "namespace": "test_namespace",
            "name": "test_entity_5",
        }
        spec = {
            "from_resource": "source_entity",
            "to_resource": "target_entity",
        }

        result = entity_handler.apply(metadata=metadata, spec=spec)

        assert result["metadata"]["labels"] == {}

    def test_apply_invalid_spec(self, entity_handler, cleanup_test_data):
        """测试使用无效的 spec"""
        metadata = {
            "namespace": "test_namespace",
            "name": "test_entity_6",
        }
        spec = {
            "invalid_field": "value",
        }

        with pytest.raises(ValidationError):
            entity_handler.apply(metadata=metadata, spec=spec)

    def test_apply_missing_required_fields(self, entity_handler, cleanup_test_data):
        """测试缺少必需字段"""
        metadata = {
            "namespace": "test_namespace",
            "name": "test_entity_7",
        }
        spec = {
            "from_resource": "source_entity",
            # 缺少 to_resource
        }

        with pytest.raises(ValidationError):
            entity_handler.apply(metadata=metadata, spec=spec)


class TestEntityHandlerGet:
    """测试 EntityHandler.get 方法"""

    def test_get_existing_entity(self, entity_handler, cleanup_test_data):
        """测试获取存在的实体"""
        # 先创建一个实体
        metadata = {
            "namespace": "test_namespace",
            "name": "test_get_entity",
            "labels": {"env": "test"},
        }
        spec = {
            "from_resource": "source_entity",
            "to_resource": "target_entity",
        }
        entity_handler.apply(metadata=metadata, spec=spec)

        # 获取实体
        result = entity_handler.get(namespace="test_namespace", name="test_get_entity")

        assert result["kind"] == "CustomRelationStatus"
        assert result["metadata"]["namespace"] == "test_namespace"
        assert result["metadata"]["name"] == "test_get_entity"
        assert result["spec"]["from_resource"] == "source_entity"
        assert result["spec"]["to_resource"] == "target_entity"

    def test_get_nonexistent_entity(self, entity_handler, cleanup_test_data):
        """测试获取不存在的实体"""
        with pytest.raises(EntityNotFoundError) as exc_info:
            entity_handler.get(namespace="nonexistent", name="nonexistent")

        assert exc_info.value.code == 3345002
        assert "nonexistent" in str(exc_info.value)


class TestEntityHandlerList:
    """测试 EntityHandler.list 方法"""

    def test_list_all_entities(self, entity_handler, cleanup_test_data):
        """测试列出所有实体"""
        # 创建多个实体
        for i in range(3):
            metadata = {
                "namespace": "test_namespace",
                "name": f"test_list_entity_{i}",
                "labels": {"env": "test"},
            }
            spec = {
                "from_resource": f"source_{i}",
                "to_resource": f"target_{i}",
            }
            entity_handler.apply(metadata=metadata, spec=spec)

        # 列出所有实体
        results = entity_handler.list()

        # 至少应该有我们创建的 3 个实体
        test_entities = [
            r
            for r in results
            if r["metadata"]["namespace"] == "test_namespace" and "test_list_entity" in r["metadata"]["name"]
        ]
        assert len(test_entities) == 3

    def test_list_filter_by_namespace(self, entity_handler, cleanup_test_data):
        """测试按命名空间过滤"""
        # 创建不同命名空间的实体
        for namespace in ["test_namespace_1", "test_namespace_2"]:
            for i in range(2):
                metadata = {
                    "namespace": namespace,
                    "name": f"test_list_entity_{i}",
                }
                spec = {
                    "from_resource": f"source_{i}",
                    "to_resource": f"target_{i}",
                }
                entity_handler.apply(metadata=metadata, spec=spec)

        # 按命名空间过滤
        results = entity_handler.list(namespace="test_namespace_1")

        assert len(results) == 2
        for result in results:
            assert result["metadata"]["namespace"] == "test_namespace_1"

    def test_list_filter_by_name(self, entity_handler, cleanup_test_data):
        """测试按名称过滤"""
        # 创建多个实体
        for i in range(3):
            metadata = {
                "namespace": "test_namespace",
                "name": f"test_list_entity_{i}",
            }
            spec = {
                "from_resource": f"source_{i}",
                "to_resource": f"target_{i}",
            }
            entity_handler.apply(metadata=metadata, spec=spec)

        # 按名称过滤
        results = entity_handler.list(name="test_list_entity_1")

        assert len(results) == 1
        assert results[0]["metadata"]["name"] == "test_list_entity_1"

    def test_list_filter_by_namespace_and_name(self, entity_handler, cleanup_test_data):
        """测试同时按命名空间和名称过滤"""
        # 创建多个实体
        for namespace in ["test_namespace_1", "test_namespace_2"]:
            for name in ["test_entity_a", "test_entity_b"]:
                metadata = {
                    "namespace": namespace,
                    "name": name,
                }
                spec = {
                    "from_resource": "source",
                    "to_resource": "target",
                }
                entity_handler.apply(metadata=metadata, spec=spec)

        # 同时按命名空间和名称过滤
        results = entity_handler.list(namespace="test_namespace_1", name="test_entity_a")

        assert len(results) == 1
        assert results[0]["metadata"]["namespace"] == "test_namespace_1"
        assert results[0]["metadata"]["name"] == "test_entity_a"

    def test_list_empty_result(self, entity_handler, cleanup_test_data):
        """测试空结果"""
        results = entity_handler.list(namespace="nonexistent_namespace")

        assert isinstance(results, list)
        assert len(results) == 0


class TestEntityHandlerDelete:
    """测试 EntityHandler.delete 方法"""

    def test_delete_existing_entity(self, entity_handler, cleanup_test_data):
        """测试删除存在的实体"""
        # 先创建一个实体
        metadata = {
            "namespace": "test_namespace",
            "name": "test_delete_entity",
        }
        spec = {
            "from_resource": "source_entity",
            "to_resource": "target_entity",
        }
        entity_handler.apply(metadata=metadata, spec=spec)

        # 验证实体存在
        entity = CustomRelationStatus.objects.get(namespace="test_namespace", name="test_delete_entity")
        assert entity is not None

        # 删除实体
        entity_handler.delete(namespace="test_namespace", name="test_delete_entity")

        # 验证实体已被删除
        with pytest.raises(CustomRelationStatus.DoesNotExist):
            CustomRelationStatus.objects.get(namespace="test_namespace", name="test_delete_entity")

    def test_delete_nonexistent_entity(self, entity_handler, cleanup_test_data):
        """测试删除不存在的实体"""
        with pytest.raises(EntityNotFoundError) as exc_info:
            entity_handler.delete(namespace="nonexistent", name="nonexistent")

        assert exc_info.value.code == 3345002
        assert "nonexistent" in str(exc_info.value)


class TestEntityHandlerFactory:
    """测试 EntityHandlerFactory"""

    def test_get_handler_valid_kind(self):
        """测试获取有效的 handler"""
        handler = EntityHandlerFactory.get_handler("CustomRelationStatus")

        assert isinstance(handler, EntityHandler)
        assert handler.model_class == CustomRelationStatus

    def test_get_handler_invalid_kind(self):
        """测试获取无效的 kind"""
        with pytest.raises(UnsupportedKindError) as exc_info:
            EntityHandlerFactory.get_handler("InvalidKind")

        assert exc_info.value.code == 3345003
        assert "InvalidKind" in str(exc_info.value)


class TestEntityHandlerIntegration:
    """测试 EntityHandler 的集成场景"""

    def test_full_lifecycle(self, entity_handler, cleanup_test_data):
        """测试完整的生命周期：创建 -> 获取 -> 更新 -> 列表 -> 删除"""
        # 1. 创建
        metadata = {
            "namespace": "test_namespace",
            "name": "test_lifecycle_entity",
            "labels": {"env": "test"},
        }
        spec = {
            "from_resource": "source_entity",
            "to_resource": "target_entity",
        }
        create_result = entity_handler.apply(metadata=metadata, spec=spec)
        assert create_result["metadata"]["generation"] == 1

        # 2. 获取
        get_result = entity_handler.get(namespace="test_namespace", name="test_lifecycle_entity")
        assert get_result["metadata"]["name"] == "test_lifecycle_entity"

        # 3. 更新
        updated_spec = {
            "from_resource": "updated_source",
            "to_resource": "updated_target",
        }
        update_result = entity_handler.apply(metadata=metadata, spec=updated_spec)
        assert update_result["metadata"]["generation"] == 2
        assert update_result["spec"]["from_resource"] == "updated_source"

        # 4. 列表
        list_results = entity_handler.list(namespace="test_namespace", name="test_lifecycle_entity")
        assert len(list_results) == 1
        assert list_results[0]["spec"]["from_resource"] == "updated_source"

        # 5. 删除
        entity_handler.delete(namespace="test_namespace", name="test_lifecycle_entity")
        with pytest.raises(EntityNotFoundError):
            entity_handler.get(namespace="test_namespace", name="test_lifecycle_entity")
