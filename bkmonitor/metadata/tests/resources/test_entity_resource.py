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

from core.drf_resource.exceptions import CustomException
from core.errors.metadata.entity import EntityNotFoundError, UnsupportedKindError
from metadata.models.entity_relation import CustomRelationStatus
from metadata.resources.entity_relation import (
    ApplyEntityResource,
    DeleteEntityResource,
    GetEntityResource,
    ListEntityResource,
)

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def cleanup_test_data():
    """清理测试数据的 fixture"""
    # 清理测试数据
    CustomRelationStatus.objects.filter(namespace__startswith="test_").delete()
    yield
    # 测试后清理
    CustomRelationStatus.objects.filter(namespace__startswith="test_").delete()


@pytest.fixture
def create_test_entity(cleanup_test_data):
    """创建测试实体的 fixture"""
    entity = CustomRelationStatus.objects.create(
        namespace="test_namespace",
        name="test_entity",
        from_resource="source_entity",
        to_resource="target_entity",
        labels={"env": "test", "app": "monitor"},
        creator="test_user",
        updater="test_user",
    )
    yield entity


class TestGetEntityResource:
    """测试 GetEntityResource"""

    def test_get_existing_entity(self, create_test_entity):
        """测试获取存在的实体"""
        resource = GetEntityResource()
        result = resource.request(
            kind="CustomRelationStatus",
            namespace="test_namespace",
            name="test_entity",
        )

        assert result["kind"] == "CustomRelationStatus"
        assert result["metadata"]["namespace"] == "test_namespace"
        assert result["metadata"]["name"] == "test_entity"
        assert result["spec"]["from_resource"] == "source_entity"
        assert result["spec"]["to_resource"] == "target_entity"
        assert result["metadata"]["labels"] == {"env": "test", "app": "monitor"}

    def test_get_nonexistent_entity(self, cleanup_test_data):
        """测试获取不存在的实体"""
        resource = GetEntityResource()
        with pytest.raises(EntityNotFoundError) as exc_info:
            resource.request(
                kind="CustomRelationStatus",
                namespace="nonexistent",
                name="nonexistent",
            )

        assert "nonexistent" in str(exc_info.value)

    def test_get_invalid_kind(self, cleanup_test_data):
        """测试使用无效的 kind"""
        resource = GetEntityResource()
        with pytest.raises(UnsupportedKindError) as exc_info:
            resource.request(
                kind="InvalidKind",
                namespace="test_namespace",
                name="test_entity",
            )

        assert "InvalidKind" in str(exc_info.value)

    def test_get_missing_required_fields(self, cleanup_test_data):
        """测试缺少必需字段"""
        resource = GetEntityResource()

        # 测试缺少所有必需字段
        with pytest.raises(CustomException):
            resource.request()

        # 测试缺少 namespace
        with pytest.raises(CustomException):
            resource.request(kind="CustomRelationStatus", name="test")

        # 测试缺少 name
        with pytest.raises(CustomException):
            resource.request(kind="CustomRelationStatus", namespace="test")

    def test_get_with_space_uid(self, cleanup_test_data):
        """测试使用 space_uid 覆盖 namespace"""
        # 创建测试实体
        CustomRelationStatus.objects.create(
            namespace="test_space_uid",
            name="test_entity",
            from_resource="source_entity",
            to_resource="target_entity",
            creator="test_user",
            updater="test_user",
        )

        resource = GetEntityResource()
        # 使用 space_uid 而不是 namespace
        result = resource.request(
            kind="CustomRelationStatus",
            namespace="wrong_namespace",  # 这个会被 space_uid 覆盖
            name="test_entity",
            space_uid="test_space_uid",
        )

        assert result["metadata"]["namespace"] == "test_space_uid"
        assert result["metadata"]["name"] == "test_entity"


class TestListEntityResource:
    """测试 ListEntityResource"""

    def test_list_all_entities(self, cleanup_test_data):
        """测试列出所有实体"""
        # 创建多个测试实体
        for i in range(3):
            CustomRelationStatus.objects.create(
                namespace="test_namespace",
                name=f"test_list_entity_{i}",
                from_resource=f"source_{i}",
                to_resource=f"target_{i}",
                creator="test_user",
                updater="test_user",
            )

        resource = ListEntityResource()
        results = resource.request(kind="CustomRelationStatus")

        # 至少应该有我们创建的 3 个实体
        test_entities = [
            r
            for r in results
            if r["metadata"]["namespace"] == "test_namespace" and "test_list_entity" in r["metadata"]["name"]
        ]
        assert len(test_entities) == 3

    def test_list_filter_by_namespace(self, cleanup_test_data):
        """测试按命名空间过滤"""
        # 创建不同命名空间的实体
        for namespace in ["test_namespace_1", "test_namespace_2"]:
            for i in range(2):
                CustomRelationStatus.objects.create(
                    namespace=namespace,
                    name=f"test_list_entity_{i}",
                    from_resource=f"source_{i}",
                    to_resource=f"target_{i}",
                    creator="test_user",
                    updater="test_user",
                )

        resource = ListEntityResource()
        results = resource.request(kind="CustomRelationStatus", namespace="test_namespace_1")

        assert len(results) == 2
        for result in results:
            assert result["metadata"]["namespace"] == "test_namespace_1"

    def test_list_filter_by_name(self, cleanup_test_data):
        """测试按名称过滤"""
        # 创建多个实体
        for i in range(3):
            CustomRelationStatus.objects.create(
                namespace="test_namespace",
                name=f"test_list_entity_{i}",
                from_resource=f"source_{i}",
                to_resource=f"target_{i}",
                creator="test_user",
                updater="test_user",
            )

        resource = ListEntityResource()
        results = resource.request(kind="CustomRelationStatus", name="test_list_entity_1")

        assert len(results) == 1
        assert results[0]["metadata"]["name"] == "test_list_entity_1"

    def test_list_filter_by_namespace_and_name(self, cleanup_test_data):
        """测试同时按命名空间和名称过滤"""
        # 创建多个实体
        for namespace in ["test_namespace_1", "test_namespace_2"]:
            for name in ["test_entity_a", "test_entity_b"]:
                CustomRelationStatus.objects.create(
                    namespace=namespace,
                    name=name,
                    from_resource="source",
                    to_resource="target",
                    creator="test_user",
                    updater="test_user",
                )

        resource = ListEntityResource()
        results = resource.request(
            kind="CustomRelationStatus",
            namespace="test_namespace_1",
            name="test_entity_a",
        )

        assert len(results) == 1
        assert results[0]["metadata"]["namespace"] == "test_namespace_1"
        assert results[0]["metadata"]["name"] == "test_entity_a"

    def test_list_empty_result(self, cleanup_test_data):
        """测试空结果"""
        resource = ListEntityResource()
        results = resource.request(kind="CustomRelationStatus", namespace="nonexistent_namespace")

        assert isinstance(results, list)
        assert len(results) == 0

    def test_list_invalid_kind(self, cleanup_test_data):
        """测试使用无效的 kind"""
        resource = ListEntityResource()
        with pytest.raises(UnsupportedKindError) as exc_info:
            resource.request(kind="InvalidKind")

        assert "InvalidKind" in str(exc_info.value)

    def test_list_optional_parameters(self, cleanup_test_data):
        """测试可选参数"""
        # 创建测试实体
        CustomRelationStatus.objects.create(
            namespace="test_namespace",
            name="test_entity",
            from_resource="source",
            to_resource="target",
            creator="test_user",
            updater="test_user",
        )

        resource = ListEntityResource()

        # 只传 kind，不传 namespace 和 name
        results = resource.request(kind="CustomRelationStatus")
        assert isinstance(results, list)

        # 只传 kind 和 namespace
        results = resource.request(kind="CustomRelationStatus", namespace="test_namespace")
        assert len(results) >= 1

        # 只传 kind 和 name
        results = resource.request(kind="CustomRelationStatus", name="test_entity")
        assert len(results) >= 1

    def test_list_with_space_uid(self, cleanup_test_data):
        """测试使用 space_uid 覆盖 namespace"""
        # 创建测试实体
        CustomRelationStatus.objects.create(
            namespace="test_space_uid",
            name="test_list_entity",
            from_resource="source",
            to_resource="target",
            creator="test_user",
            updater="test_user",
        )

        resource = ListEntityResource()
        # 使用 space_uid 而不是 namespace
        results = resource.request(
            kind="CustomRelationStatus",
            namespace="wrong_namespace",  # 这个会被 space_uid 覆盖
            space_uid="test_space_uid",
        )

        assert len(results) >= 1
        # 验证结果中的 namespace 是 space_uid 的值
        test_entities = [
            r
            for r in results
            if r["metadata"]["namespace"] == "test_space_uid" and r["metadata"]["name"] == "test_list_entity"
        ]
        assert len(test_entities) == 1


class TestDeleteEntityResource:
    """测试 DeleteEntityResource"""

    def test_delete_existing_entity(self, create_test_entity):
        """测试删除存在的实体"""
        # 验证实体存在
        entity = CustomRelationStatus.objects.get(namespace="test_namespace", name="test_entity")
        assert entity is not None

        resource = DeleteEntityResource()
        result = resource.request(
            kind="CustomRelationStatus",
            namespace="test_namespace",
            name="test_entity",
        )

        # DeleteEntityResource 应该返回 None
        assert result is None

        # 验证实体已被删除
        with pytest.raises(CustomRelationStatus.DoesNotExist):
            CustomRelationStatus.objects.get(namespace="test_namespace", name="test_entity")

    def test_delete_nonexistent_entity(self, cleanup_test_data):
        """测试删除不存在的实体"""
        resource = DeleteEntityResource()
        with pytest.raises(EntityNotFoundError) as exc_info:
            resource.request(
                kind="CustomRelationStatus",
                namespace="nonexistent",
                name="nonexistent",
            )

        assert "nonexistent" in str(exc_info.value)

    def test_delete_invalid_kind(self, cleanup_test_data):
        """测试使用无效的 kind"""
        resource = DeleteEntityResource()
        with pytest.raises(UnsupportedKindError) as exc_info:
            resource.request(
                kind="InvalidKind",
                namespace="test_namespace",
                name="test_entity",
            )

        assert "InvalidKind" in str(exc_info.value)

    def test_delete_missing_required_fields(self, cleanup_test_data):
        """测试缺少必需字段"""
        resource = DeleteEntityResource()

        # 测试缺少所有必需字段
        with pytest.raises(CustomException):
            resource.request()

        # 测试缺少 namespace
        with pytest.raises(CustomException):
            resource.request(kind="CustomRelationStatus", name="test")

        # 测试缺少 name
        with pytest.raises(CustomException):
            resource.request(kind="CustomRelationStatus", namespace="test")

    def test_delete_with_space_uid(self, cleanup_test_data):
        """测试使用 space_uid 覆盖 namespace"""
        # 创建测试实体
        CustomRelationStatus.objects.create(
            namespace="test_space_uid",
            name="test_delete_entity",
            from_resource="source_entity",
            to_resource="target_entity",
            creator="test_user",
            updater="test_user",
        )

        resource = DeleteEntityResource()
        # 使用 space_uid 而不是 namespace
        result = resource.request(
            kind="CustomRelationStatus",
            namespace="wrong_namespace",  # 这个会被 space_uid 覆盖
            name="test_delete_entity",
            space_uid="test_space_uid",
        )

        assert result is None

        # 验证实体已被删除
        with pytest.raises(CustomRelationStatus.DoesNotExist):
            CustomRelationStatus.objects.get(namespace="test_space_uid", name="test_delete_entity")


class TestEntityResourceIntegration:
    """测试 Resource 类的集成场景"""

    def test_full_lifecycle_with_resources(self, cleanup_test_data):
        """测试使用 Resource 类的完整生命周期：创建 -> 获取 -> 列表 -> 删除"""
        # 1. 创建（使用 ApplyEntityResource，但这里我们直接创建来测试其他 Resource）
        CustomRelationStatus.objects.create(
            namespace="test_namespace",
            name="test_lifecycle_entity",
            from_resource="source_entity",
            to_resource="target_entity",
            labels={"env": "test"},
            creator="test_user",
            updater="test_user",
        )

        # 2. 获取
        get_resource = GetEntityResource()
        get_result = get_resource.request(
            kind="CustomRelationStatus",
            namespace="test_namespace",
            name="test_lifecycle_entity",
        )
        assert get_result["metadata"]["name"] == "test_lifecycle_entity"
        assert get_result["spec"]["from_resource"] == "source_entity"

        # 3. 列表
        list_resource = ListEntityResource()
        list_results = list_resource.request(
            kind="CustomRelationStatus",
            namespace="test_namespace",
            name="test_lifecycle_entity",
        )
        assert len(list_results) == 1
        assert list_results[0]["spec"]["from_resource"] == "source_entity"

        # 4. 删除
        delete_resource = DeleteEntityResource()
        delete_resource.request(
            kind="CustomRelationStatus",
            namespace="test_namespace",
            name="test_lifecycle_entity",
        )

        # 5. 验证删除后无法获取
        with pytest.raises(EntityNotFoundError):
            get_resource.request(
                kind="CustomRelationStatus",
                namespace="test_namespace",
                name="test_lifecycle_entity",
            )


class TestApplyEntityResource:
    """测试 ApplyEntityResource"""

    def test_apply_create_with_space_uid(self, cleanup_test_data):
        """测试使用 space_uid 创建实体"""
        resource = ApplyEntityResource()
        result = resource.request(
            kind="CustomRelationStatus",
            metadata={
                "namespace": "wrong_namespace",  # 这个会被 space_uid 覆盖
                "name": "test_apply_entity",
                "labels": {"env": "test"},
            },
            spec={
                "from_resource": "source_entity",
                "to_resource": "target_entity",
            },
            space_uid="test_space_uid",
        )

        assert result["metadata"]["namespace"] == "test_space_uid"
        assert result["metadata"]["name"] == "test_apply_entity"
        assert result["spec"]["from_resource"] == "source_entity"

        # 验证实体已创建
        entity = CustomRelationStatus.objects.get(namespace="test_space_uid", name="test_apply_entity")
        assert entity.from_resource == "source_entity"

    def test_apply_update_with_space_uid(self, cleanup_test_data):
        """测试使用 space_uid 更新实体"""
        # 先创建实体
        CustomRelationStatus.objects.create(
            namespace="test_space_uid",
            name="test_update_entity",
            from_resource="old_source",
            to_resource="old_target",
            creator="test_user",
            updater="test_user",
        )

        resource = ApplyEntityResource()
        result = resource.request(
            kind="CustomRelationStatus",
            metadata={
                "namespace": "wrong_namespace",  # 这个会被 space_uid 覆盖
                "name": "test_update_entity",
            },
            spec={
                "from_resource": "new_source",
                "to_resource": "new_target",
            },
            space_uid="test_space_uid",
        )

        assert result["metadata"]["namespace"] == "test_space_uid"
        assert result["spec"]["from_resource"] == "new_source"
        assert result["spec"]["to_resource"] == "new_target"

        # 验证实体已更新
        entity = CustomRelationStatus.objects.get(namespace="test_space_uid", name="test_update_entity")
        assert entity.from_resource == "new_source"
        assert entity.to_resource == "new_target"

    def test_apply_without_space_uid(self, cleanup_test_data):
        """测试不使用 space_uid 时，使用 metadata.namespace"""
        resource = ApplyEntityResource()
        result = resource.request(
            kind="CustomRelationStatus",
            metadata={
                "namespace": "test_namespace",
                "name": "test_entity",
            },
            spec={
                "from_resource": "source_entity",
                "to_resource": "target_entity",
            },
        )

        assert result["metadata"]["namespace"] == "test_namespace"
        assert result["metadata"]["name"] == "test_entity"
