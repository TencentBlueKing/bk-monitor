"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from unittest.mock import patch

import pytest
from rest_framework.exceptions import ValidationError

from core.errors.metadata import EntityNotFoundError, UnsupportedKindError
from metadata.models.entity_relation import CustomRelationStatus, RelationDefinition, ResourceDefinition
from metadata.resources.entity_relation import (
    ENTITY_REDIS_KEY_PREFIX,
    NAMESPACE_ALL,
    REDIS_SYNC_KINDS,
    EntityHandler,
    EntityHandlerFactory,
)

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


class TestEntityHandlerRedisSync:
    """测试 Redis 同步功能 - 针对 ResourceDefinition 和 RelationDefinition"""

    @pytest.fixture
    def cleanup_definition_data(self):
        """清理 Definition 测试数据"""
        yield
        ResourceDefinition.objects.filter(namespace__startswith="test_").delete()
        ResourceDefinition.objects.filter(namespace=NAMESPACE_ALL, name__startswith="test_").delete()
        RelationDefinition.objects.filter(namespace__startswith="test_").delete()
        RelationDefinition.objects.filter(namespace=NAMESPACE_ALL, name__startswith="test_").delete()

    @pytest.mark.parametrize(
        "case_id,model_class,metadata,spec,expected_redis_data",
        [
            # ResourceDefinition 同步
            (
                "resource_definition",
                ResourceDefinition,
                {"namespace": NAMESPACE_ALL, "name": "test_pod", "labels": {"source": "cmdb"}},
                {"fields": [{"namespace": "k8s", "name": "pod_name", "required": True}]},
                {
                    "test_pod": {
                        "namespace": NAMESPACE_ALL,
                        "name": "test_pod",
                        "labels": {"source": "cmdb"},
                        "fields": [{"namespace": "k8s", "name": "pod_name", "required": True}],
                    }
                },
            ),
            # RelationDefinition 同步
            (
                "relation_definition",
                RelationDefinition,
                {"namespace": NAMESPACE_ALL, "name": "test_pod_node", "labels": {}},
                {
                    "from_resource": "pod",
                    "to_resource": "node",
                    "category": "static",
                    "is_directional": False,
                    "is_belongs_to": True,
                },
                {
                    "test_pod_node": {
                        "namespace": NAMESPACE_ALL,
                        "name": "test_pod_node",
                        "labels": {},
                        "from_resource": "pod",
                        "to_resource": "node",
                        "category": "static",
                        "is_directional": False,
                        "is_belongs_to": True,
                    }
                },
            ),
        ],
    )
    @patch("metadata.resources.entity_relation.RedisTools")
    def test_sync_to_redis(
        self, mock_redis, cleanup_definition_data, case_id, model_class, metadata, spec, expected_redis_data
    ):
        """验证 ResourceDefinition/RelationDefinition 同步到 Redis 的数据结构"""
        mock_redis.hget.return_value = None

        handler = EntityHandler(model_class=model_class)
        handler.apply(metadata=metadata, spec=spec)

        # 验证 Redis 写入
        kind = model_class.get_kind()
        redis_key = f"{ENTITY_REDIS_KEY_PREFIX}:{kind}"
        call_args = mock_redis.hset_to_redis.call_args

        assert call_args[0][0] == redis_key
        assert call_args[0][1] == (metadata.get("namespace") or NAMESPACE_ALL)
        assert json.loads(call_args[0][2]) == expected_redis_data

        # 验证 Publish 通知
        channel = f"{redis_key}:channel"
        pub_args = mock_redis.publish.call_args
        assert pub_args[0][0] == channel
        assert json.loads(pub_args[0][1][0]) == {
            "namespace": metadata.get("namespace"),
            "name": metadata["name"],
            "kind": kind,
        }

    @patch("metadata.resources.entity_relation.RedisTools")
    def test_custom_relation_status_not_synced(self, mock_redis, cleanup_test_data):
        """CustomRelationStatus 不在 REDIS_SYNC_KINDS 中，不同步到 Redis"""
        assert "CustomRelationStatus" not in REDIS_SYNC_KINDS

        handler = EntityHandler(model_class=CustomRelationStatus)
        handler.apply(
            metadata={"namespace": "test_ns", "name": "test_no_sync"},
            spec={"from_resource": "src", "to_resource": "dst"},
        )

        mock_redis.hget.assert_not_called()
        mock_redis.hset_to_redis.assert_not_called()
        mock_redis.publish.assert_not_called()

    @patch("metadata.resources.entity_relation.RedisTools")
    def test_delete_updates_redis(self, mock_redis, cleanup_definition_data):
        """删除时从 Redis 移除实体，保留同 namespace 下其他实体"""
        mock_redis.hget.return_value = None

        handler = EntityHandler(model_class=ResourceDefinition)
        handler.apply(
            metadata={"namespace": NAMESPACE_ALL, "name": "test_del"},
            spec={"fields": []},
        )

        # 模拟 Redis 中有两个实体
        mock_redis.hget.return_value = json.dumps({
            "test_del": {"name": "test_del"},
            "other": {"name": "other"},
        }).encode()
        mock_redis.reset_mock()

        handler.delete(namespace=NAMESPACE_ALL, name="test_del")

        # 验证删除后只剩 other
        call_args = mock_redis.hset_to_redis.call_args
        assert json.loads(call_args[0][2]) == {"other": {"name": "other"}}

    @patch("metadata.resources.entity_relation.RedisTools")
    def test_delete_last_entity_calls_hdel(self, mock_redis, cleanup_definition_data):
        """删除 namespace 下最后一个实体时，调用 hdel 而非 hset"""
        mock_redis.hget.return_value = None

        handler = EntityHandler(model_class=ResourceDefinition)
        handler.apply(
            metadata={"namespace": NAMESPACE_ALL, "name": "test_last"},
            spec={"fields": []},
        )

        mock_redis.hget.return_value = json.dumps({"test_last": {"name": "test_last"}}).encode()
        mock_redis.reset_mock()

        handler.delete(namespace=NAMESPACE_ALL, name="test_last")

        mock_redis.hdel.assert_called_once()
        mock_redis.hset_to_redis.assert_not_called()

    @patch("metadata.resources.entity_relation.RedisTools")
    def test_redis_error_not_affect_db(self, mock_redis, cleanup_definition_data):
        """Redis 异常不影响数据库操作"""
        mock_redis.hget.return_value = None
        mock_redis.hset_to_redis.side_effect = Exception("Redis connection failed")

        handler = EntityHandler(model_class=ResourceDefinition)
        result = handler.apply(
            metadata={"namespace": NAMESPACE_ALL, "name": "test_err"},
            spec={"fields": []},
        )

        assert result["metadata"]["name"] == "test_err"
        assert ResourceDefinition.objects.filter(name="test_err").exists()
