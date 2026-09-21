"""
测试 dynamic_group Redis 缓存操作模块

测试 cache_dynamic_group_member, delete_dynamic_group_cache,
get_dynamic_group_cache, get_inst_group_ids, batch_delete_inst_group_cache 等函数。
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from bk_monitor_base.domains.dynamic_group.operations.cache import (
    _get_inst_group_ids_from_cache,
    _remove_group_from_inst_cache,
    batch_delete_inst_group_cache,
    cache_dynamic_group_member,
    delete_dynamic_group_cache,
    get_dynamic_group_cache,
    get_inst_group_ids,
)


@pytest.fixture
def mock_redis_client():
    """模拟 Redis 客户端"""
    mock_client = MagicMock()
    mock_pipeline = MagicMock()
    mock_client.pipeline.return_value = mock_pipeline
    return mock_client, mock_pipeline


class TestGetInstGroupIdsFromCache:
    """测试 _get_inst_group_ids_from_cache 辅助函数"""

    def test_returns_empty_set_when_no_data(self, mock_redis_client):
        """测试无数据时返回空集合"""
        mock_client, _ = mock_redis_client
        mock_client.hget.return_value = None

        result = _get_inst_group_ids_from_cache(mock_client, "test_key", 1)

        assert result == set()
        mock_client.hget.assert_called_once_with("test_key", 1)

    def test_returns_group_ids_when_data_exists(self, mock_redis_client):
        """测试有数据时返回分组 ID 集合"""
        mock_client, _ = mock_redis_client
        mock_client.hget.return_value = json.dumps({"group_ids": [1, 2, 3]})

        result = _get_inst_group_ids_from_cache(mock_client, "test_key", 100)

        assert result == {1, 2, 3}

    def test_returns_empty_set_on_invalid_json(self, mock_redis_client):
        """测试 JSON 解析失败时返回空集合"""
        mock_client, _ = mock_redis_client
        mock_client.hget.return_value = "invalid json"

        result = _get_inst_group_ids_from_cache(mock_client, "test_key", 1)

        assert result == set()

    def test_returns_empty_set_when_group_ids_missing(self, mock_redis_client):
        """测试 group_ids 字段不存在时返回空集合"""
        mock_client, _ = mock_redis_client
        mock_client.hget.return_value = json.dumps({"other_field": "value"})

        result = _get_inst_group_ids_from_cache(mock_client, "test_key", 1)

        assert result == set()


class TestRemoveGroupFromInstCache:
    """测试 _remove_group_from_inst_cache 辅助函数"""

    def test_updates_cache_when_other_groups_remain(self, mock_redis_client):
        """测试移除分组后还有其他分组时更新缓存"""
        mock_client, mock_pipeline = mock_redis_client
        mock_client.hget.return_value = json.dumps({"group_ids": [1, 2, 3]})

        _remove_group_from_inst_cache(mock_client, mock_pipeline, "test_key", 100, 2)

        # 验证 hset 被调用，新数据不包含分组 2
        mock_pipeline.hset.assert_called_once()
        call_args = mock_pipeline.hset.call_args
        assert call_args[0][0] == "test_key"
        assert call_args[0][1] == 100
        new_data = json.loads(call_args[0][2])
        assert set(new_data["group_ids"]) == {1, 3}

    def test_deletes_cache_when_no_groups_remain(self, mock_redis_client):
        """测试移除分组后没有其他分组时删除缓存"""
        mock_client, mock_pipeline = mock_redis_client
        mock_client.hget.return_value = json.dumps({"group_ids": [1]})

        _remove_group_from_inst_cache(mock_client, mock_pipeline, "test_key", 100, 1)

        # 验证 hdel 被调用
        mock_pipeline.hdel.assert_called_once_with("test_key", 100)
        mock_pipeline.hset.assert_not_called()

    def test_handles_empty_cache(self, mock_redis_client):
        """测试缓存为空时不执行任何操作"""
        mock_client, mock_pipeline = mock_redis_client
        mock_client.hget.return_value = None

        _remove_group_from_inst_cache(mock_client, mock_pipeline, "test_key", 100, 1)

        # 没有数据，删除空记录
        mock_pipeline.hdel.assert_called_once_with("test_key", 100)


class TestCacheDynamicGroupMember:
    """测试 cache_dynamic_group_member 函数"""

    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_redis_connection")
    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_dynamic_group_cache_key")
    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_dynamic_inst_group_cache_key")
    def test_cache_group_member_success(
        self,
        mock_get_inst_key,
        mock_get_group_key,
        mock_get_redis,
    ):
        """测试成功缓存分组成员"""
        mock_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_client.pipeline.return_value = mock_pipeline
        mock_client.hget.return_value = None
        mock_get_redis.return_value = mock_client
        mock_get_group_key.return_value = "group:123"
        mock_get_inst_key.return_value = "inst_group:cw-Host"

        member_list = [
            {"bk_inst_id": 1, "bk_host_name": "host1"},
            {"bk_inst_id": 2, "bk_host_name": "host2"},
        ]

        cache_dynamic_group_member(
            dynamic_group_id=123,
            member_list=member_list,
            object_model_code="cw-Host",
            bk_obj_id="host",
        )

        # 验证分组缓存被设置
        mock_client.set.assert_called_once()
        call_args = mock_client.set.call_args
        assert call_args[0][0] == "group:123"
        cache_data = json.loads(call_args[0][1])
        assert cache_data["cw_object_model_code"] == "cw-Host"
        assert cache_data["bk_obj_id"] == "host"
        assert cache_data["inst_ids"] == [1, 2]

        # 验证 pipeline 被执行
        mock_pipeline.execute.assert_called_once()

    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_redis_connection")
    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_dynamic_group_cache_key")
    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_dynamic_inst_group_cache_key")
    def test_cache_uses_object_model_code_as_bk_obj_id_when_not_provided(
        self,
        mock_get_inst_key,
        mock_get_group_key,
        mock_get_redis,
    ):
        """测试未提供 bk_obj_id 时使用 object_model_code"""
        mock_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_client.pipeline.return_value = mock_pipeline
        mock_client.hget.return_value = None
        mock_get_redis.return_value = mock_client
        mock_get_group_key.return_value = "group:123"
        mock_get_inst_key.return_value = "inst_group:cw-Host"

        cache_dynamic_group_member(
            dynamic_group_id=123,
            member_list=[{"bk_inst_id": 1}],
            object_model_code="cw-Host",
        )

        call_args = mock_client.set.call_args
        cache_data = json.loads(call_args[0][1])
        assert cache_data["bk_obj_id"] == "cw-Host"

    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_redis_connection")
    def test_cache_handles_empty_member_list(self, mock_get_redis):
        """测试空成员列表不报错"""
        mock_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_client.pipeline.return_value = mock_pipeline
        mock_get_redis.return_value = mock_client

        cache_dynamic_group_member(
            dynamic_group_id=123,
            member_list=[],
            object_model_code="cw-Host",
        )

        # 验证没有报错，pipeline 被执行
        mock_pipeline.execute.assert_called_once()

    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_redis_connection")
    def test_cache_skips_members_without_inst_id(self, mock_get_redis):
        """测试跳过没有 bk_inst_id 的成员"""
        mock_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_client.pipeline.return_value = mock_pipeline
        mock_client.hget.return_value = None
        mock_get_redis.return_value = mock_client

        member_list = [
            {"bk_inst_id": 1, "bk_host_name": "host1"},
            {"bk_host_name": "host2"},  # 没有 bk_inst_id
            {"bk_inst_id": None, "bk_host_name": "host3"},  # bk_inst_id 为 None
        ]

        cache_dynamic_group_member(
            dynamic_group_id=123,
            member_list=member_list,
            object_model_code="cw-Host",
        )

        # 只有 1 个有效成员，hset 应该只调用 1 次
        assert mock_pipeline.hset.call_count == 1


class TestDeleteDynamicGroupCache:
    """测试 delete_dynamic_group_cache 函数"""

    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_redis_connection")
    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_dynamic_group_cache_key")
    def test_delete_group_cache_only(self, mock_get_group_key, mock_get_redis):
        """测试仅删除分组缓存（不提供成员列表）"""
        mock_client = MagicMock()
        mock_get_redis.return_value = mock_client
        mock_get_group_key.return_value = "group:123"

        delete_dynamic_group_cache(dynamic_group_id=123)

        mock_client.delete.assert_called_once_with("group:123")

    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_redis_connection")
    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_dynamic_group_cache_key")
    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_dynamic_inst_group_cache_key")
    def test_delete_group_cache_and_inst_relations(
        self,
        mock_get_inst_key,
        mock_get_group_key,
        mock_get_redis,
    ):
        """测试删除分组缓存和实例分组关系"""
        mock_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_client.pipeline.return_value = mock_pipeline
        mock_client.hget.return_value = json.dumps({"group_ids": [123]})
        mock_get_redis.return_value = mock_client
        mock_get_group_key.return_value = "group:123"
        mock_get_inst_key.return_value = "inst_group:cw-Host"

        member_list = [{"bk_inst_id": 1}, {"bk_inst_id": 2}]

        delete_dynamic_group_cache(
            dynamic_group_id=123,
            member_list=member_list,
            object_model_code="cw-Host",
        )

        # 验证分组缓存被删除
        mock_client.delete.assert_called_once_with("group:123")

        # 验证 pipeline 被执行
        mock_pipeline.execute.assert_called_once()


class TestGetDynamicGroupCache:
    """测试 get_dynamic_group_cache 函数"""

    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_redis_connection")
    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_dynamic_group_cache_key")
    def test_get_cache_success(self, mock_get_group_key, mock_get_redis):
        """测试成功获取缓存"""
        mock_client = MagicMock()
        cache_data = {
            "cw_object_model_code": "cw-Host",
            "bk_obj_id": "host",
            "inst_ids": [1, 2, 3],
            "member_list": [{"bk_inst_id": 1}],
        }
        mock_client.get.return_value = json.dumps(cache_data)
        mock_get_redis.return_value = mock_client
        mock_get_group_key.return_value = "group:123"

        result = get_dynamic_group_cache(123)

        assert result == cache_data
        mock_client.get.assert_called_once_with("group:123")

    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_redis_connection")
    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_dynamic_group_cache_key")
    def test_get_cache_returns_none_when_not_exists(self, mock_get_group_key, mock_get_redis):
        """测试缓存不存在时返回 None"""
        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_get_redis.return_value = mock_client
        mock_get_group_key.return_value = "group:123"

        result = get_dynamic_group_cache(123)

        assert result is None

    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_redis_connection")
    def test_get_cache_returns_none_on_exception(self, mock_get_redis):
        """测试异常时返回 None"""
        mock_get_redis.side_effect = Exception("Redis connection error")

        result = get_dynamic_group_cache(123)

        assert result is None


class TestGetInstGroupIds:
    """测试 get_inst_group_ids 函数"""

    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_redis_connection")
    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_dynamic_inst_group_cache_key")
    def test_get_inst_group_ids_success(self, mock_get_inst_key, mock_get_redis):
        """测试成功获取实例所属分组"""
        mock_client = MagicMock()
        mock_client.hget.return_value = json.dumps({"group_ids": [1, 2, 3]})
        mock_get_redis.return_value = mock_client
        mock_get_inst_key.return_value = "inst_group:cw-Host"

        result = get_inst_group_ids(100, "cw-Host")

        assert result == [1, 2, 3]
        mock_client.hget.assert_called_once_with("inst_group:cw-Host", 100)

    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_redis_connection")
    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_dynamic_inst_group_cache_key")
    def test_get_inst_group_ids_returns_empty_when_not_exists(self, mock_get_inst_key, mock_get_redis):
        """测试实例不存在时返回空列表"""
        mock_client = MagicMock()
        mock_client.hget.return_value = None
        mock_get_redis.return_value = mock_client
        mock_get_inst_key.return_value = "inst_group:cw-Host"

        result = get_inst_group_ids(100, "cw-Host")

        assert result == []

    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_redis_connection")
    def test_get_inst_group_ids_returns_empty_on_exception(self, mock_get_redis):
        """测试异常时返回空列表"""
        mock_get_redis.side_effect = Exception("Redis connection error")

        result = get_inst_group_ids(100, "cw-Host")

        assert result == []


class TestBatchDeleteInstGroupCache:
    """测试 batch_delete_inst_group_cache 函数"""

    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_redis_connection")
    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_dynamic_inst_group_cache_key")
    def test_batch_delete_success(self, mock_get_inst_key, mock_get_redis):
        """测试成功批量删除实例分组关系"""
        mock_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_client.pipeline.return_value = mock_pipeline
        # 模拟实例只属于一个分组
        mock_client.hget.return_value = json.dumps({"group_ids": [123]})
        mock_get_redis.return_value = mock_client
        mock_get_inst_key.return_value = "inst_group:cw-Host"

        batch_delete_inst_group_cache([1, 2, 3], "cw-Host", 123)

        # 验证每个实例都调用了 hdel
        assert mock_pipeline.hdel.call_count == 3
        mock_pipeline.execute.assert_called_once()

    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_redis_connection")
    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_dynamic_inst_group_cache_key")
    def test_batch_delete_updates_when_other_groups_remain(self, mock_get_inst_key, mock_get_redis):
        """测试批量删除时保留其他分组"""
        mock_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_client.pipeline.return_value = mock_pipeline
        # 模拟实例属于多个分组
        mock_client.hget.return_value = json.dumps({"group_ids": [123, 456]})
        mock_get_redis.return_value = mock_client
        mock_get_inst_key.return_value = "inst_group:cw-Host"

        batch_delete_inst_group_cache([1], "cw-Host", 123)

        # 验证调用的是 hset 而不是 hdel
        mock_pipeline.hset.assert_called_once()
        call_args = mock_pipeline.hset.call_args
        new_data = json.loads(call_args[0][2])
        assert 456 in new_data["group_ids"]
        assert 123 not in new_data["group_ids"]

    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_redis_connection")
    def test_batch_delete_handles_empty_list(self, mock_get_redis):
        """测试空列表不报错"""
        mock_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_client.pipeline.return_value = mock_pipeline
        mock_get_redis.return_value = mock_client

        batch_delete_inst_group_cache([], "cw-Host", 123)

        mock_pipeline.execute.assert_called_once()

    @patch("bk_monitor_base.domains.dynamic_group.operations.cache.get_redis_connection")
    def test_batch_delete_handles_exception(self, mock_get_redis):
        """测试异常时不抛出错误（只记录日志）"""
        mock_get_redis.side_effect = Exception("Redis connection error")

        # 不应该抛出异常
        batch_delete_inst_group_cache([1, 2, 3], "cw-Host", 123)
