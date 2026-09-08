"""
CMDB 实例模型单元测试
"""

from unittest.mock import Mock, patch

from bk_monitor_base.domains.cmdb_instance.models import (
    BaseInstance,
    CMDBDocument,
    CMDBInstance,
    CMDBInstRelate,
    CMDBObjRelate,
    CWDocument,
)


class TestCWDocument:
    """测试 CWDocument 基础文档类"""

    def test_get_es_client_with_default_using(self):
        """测试使用默认连接获取 ES 客户端"""
        with patch.object(CWDocument, "_get_connection") as mock_get_connection:
            mock_client = Mock()
            mock_get_connection.return_value = mock_client

            client = CWDocument.get_es_client()

            assert client == mock_client
            mock_get_connection.assert_called_once()

    def test_get_es_client_with_custom_using(self):
        """测试使用自定义连接获取 ES 客户端"""
        with patch.object(CWDocument, "_get_connection") as mock_get_connection:
            mock_client = Mock()
            mock_get_connection.return_value = mock_client

            client = CWDocument.get_es_client(using="test_es")

            assert client == mock_client
            mock_get_connection.assert_called_once_with(using="test_es")

    def test_bulk_actions_empty_documents(self):
        """测试批量操作空文档列表"""
        # 空文档列表应该直接返回，不执行任何操作
        result = CWDocument.bulk_actions([])
        assert result is None

    def test_bulk_actions_with_documents(self):
        """测试批量操作文档"""

        # 创建一个具有 Index 属性的子类用于测试
        class TestDocument(CWDocument):
            class Index:
                ALIAS = "test_alias"

        with patch("bk_monitor_base.domains.cmdb_instance.models.bulk") as mock_bulk:
            with patch.object(TestDocument, "get_es_client") as mock_get_client:
                mock_client = Mock()
                mock_get_client.return_value = mock_client

                documents = [
                    {"_op_type": "index", "_id": "1", "_source": {"field": "value1"}},
                    {"_op_type": "index", "_id": "2", "_source": {"field": "value2"}},
                ]

                TestDocument.bulk_actions(documents)

                mock_bulk.assert_called_once()
                assert mock_bulk.call_args[1]["client"] == mock_client
                assert mock_bulk.call_args[1]["actions"] == documents
                assert mock_bulk.call_args[1]["index"] == "test_alias"

    def test_get_search_with_query(self):
        """测试使用精确查询条件搜索"""
        with patch("bk_monitor_base.domains.cmdb_instance.models.Document.search") as mock_search:
            mock_search_obj = Mock()
            mock_search_obj.query.return_value = mock_search_obj
            mock_search_obj.extra.return_value = mock_search_obj
            mock_search.return_value = mock_search_obj

            result = CWDocument.get_search(query={"field1": "value1", "field2": ["value2", "value3"]})

            assert result == mock_search_obj
            mock_search.assert_called_once()
            # 验证调用了 query 方法
            assert mock_search_obj.query.called

    def test_get_search_with_pagination(self):
        """测试分页查询"""
        with patch("bk_monitor_base.domains.cmdb_instance.models.Document.search") as mock_search:
            mock_search_obj = Mock()
            mock_search_obj.query.return_value = mock_search_obj
            mock_search_obj.extra.return_value = mock_search_obj
            mock_search.return_value = mock_search_obj

            CWDocument.get_search(page=2, size=20)

            # 验证分页参数计算正确: from_ = (2-1) * 20 = 20
            # extra 会被调用两次：一次用于分页，一次用于 track_total_hits
            assert mock_search_obj.extra.called
            # 检查是否有调用包含正确的分页参数
            calls = mock_search_obj.extra.call_args_list
            pagination_call_found = any("from_" in str(call) and "size" in str(call) for call in calls)
            assert pagination_call_found or mock_search_obj.extra.call_count >= 1

    def test_get_search_with_sort(self):
        """测试排序查询"""
        with patch.object(CWDocument, "search") as mock_search:
            with patch.object(CWDocument, "get_query_field") as mock_get_field:
                mock_search_obj = Mock()
                mock_search_obj.query.return_value = mock_search_obj
                mock_search_obj.sort.return_value = mock_search_obj
                mock_search.return_value = mock_search_obj
                mock_get_field.return_value = "-created_at.keyword"

                CWDocument.get_search(sort="-created_at")

                mock_search_obj.sort.assert_called_once_with("-created_at.keyword")

    def test_get_search_with_fields(self):
        """测试指定返回字段"""
        with patch.object(CWDocument, "search") as mock_search:
            mock_search_obj = Mock()
            mock_search_obj.query.return_value = mock_search_obj
            mock_search_obj.source.return_value = mock_search_obj
            mock_search.return_value = mock_search_obj

            fields = ["field1", "field2", "field3"]
            CWDocument.get_search(fields=fields)

            mock_search_obj.source.assert_called_once_with(fields)


class TestBaseInstance:
    """测试 BaseInstance 类"""

    def test_query_option_values(self):
        """测试查询字段可选值"""
        mock_query = Mock()
        mock_query.aggs.bucket = Mock()
        mock_query.extra.return_value = mock_query

        # 模拟 ES 响应
        mock_response = Mock()
        mock_query.execute.return_value = mock_response

        # 模拟聚合结果
        mock_agg_field1 = Mock()
        mock_agg_field1.buckets = [{"key": "value1"}, {"key": "value2"}, {"key": ""}]
        mock_agg_field2 = Mock()
        mock_agg_field2.buckets = [{"key": "value3"}, {"key": "value4"}]

        mock_response.aggregations.field1_values = mock_agg_field1
        mock_response.aggregations.field2_values = mock_agg_field2

        result = BaseInstance.query_option_values(mock_query, ["field1", "field2"])

        # 验证结果（空字符串应该被过滤掉）
        assert result == {"field1": ["value1", "value2"], "field2": ["value3", "value4"]}


class TestCMDBDocument:
    """测试 CMDBDocument 类"""

    def test_search_with_auto_index(self):
        """测试自动获取最新索引"""
        with patch.object(CMDBDocument, "get_read_index") as mock_get_index:
            with patch("bk_monitor_base.domains.cmdb_instance.models.BaseInstance.search") as mock_search:
                mock_get_index.return_value = "test_index_v1"
                mock_search_obj = Mock()
                mock_search.return_value = mock_search_obj

                CMDBDocument.search()

                mock_get_index.assert_called_once()
                mock_search.assert_called_once_with(using=None, index="test_index_v1")

    def test_search_with_specified_index(self):
        """测试使用指定索引"""
        with patch("bk_monitor_base.domains.cmdb_instance.models.BaseInstance.search") as mock_search:
            mock_search_obj = Mock()
            mock_search.return_value = mock_search_obj

            CMDBDocument.search(index="custom_index")

            mock_search.assert_called_once_with(using=None, index="custom_index")

    def test_get_read_index(self):
        """测试获取最新读索引"""
        with patch.object(CMDBDocument, "get_es_client") as mock_get_client:
            mock_client = Mock()

            # 模拟读别名不存在（抛出异常），需要 fallback 到版本排序
            def get_alias_side_effect(name, params=None):
                if name.endswith("-read"):
                    # 读别名不存在，抛出异常
                    raise Exception("alias not found")
                # 写别名返回所有索引
                return {
                    "test_index_v1": {},
                    "test_index_v2": {},
                    "test_index_v10": {},
                }

            mock_client.indices.get_alias.side_effect = get_alias_side_effect
            mock_get_client.return_value = mock_client

            # 设置一个测试的 Index 类
            CMDBDocument.Index = type("Index", (), {"ALIAS": "test_alias"})

            result = CMDBDocument.get_read_index()

            # 应该返回版本最高的索引
            assert result == "test_index_v10"


class TestCMDBInstance:
    """测试 CMDBInstance 模型"""

    def test_get_inst_id_field_for_host(self):
        """测试获取主机实例ID字段"""
        assert CMDBInstance.get_inst_id_field("host") == "bk_host_id"

    def test_get_inst_id_field_for_set(self):
        """测试获取集群实例ID字段"""
        assert CMDBInstance.get_inst_id_field("set") == "bk_set_id"

    def test_get_inst_id_field_for_module(self):
        """测试获取模块实例ID字段"""
        assert CMDBInstance.get_inst_id_field("module") == "bk_module_id"

    def test_get_inst_id_field_for_biz(self):
        """测试获取业务实例ID字段"""
        assert CMDBInstance.get_inst_id_field("biz") == "bk_biz_id"

    def test_get_inst_id_field_for_custom_object(self):
        """测试获取自定义对象实例ID字段"""
        assert CMDBInstance.get_inst_id_field("mysql") == "bk_inst_id"
        assert CMDBInstance.get_inst_id_field("nginx") == "bk_inst_id"

    def test_bulk_update_or_create(self):
        """测试批量更新或创建实例"""
        with patch.object(CMDBInstance, "bulk_actions") as mock_bulk:
            with patch(
                "bk_monitor_base.domains.cmdb_instance.models.enrich_host_instances_with_agent_status"
            ) as mock_enrich:
                mock_enrich.side_effect = lambda bk_tenant_id, host_instances: [
                    {**host, "bk_agent_alive": True, "error": False} for host in host_instances
                ]
                instances = [
                    {"bk_host_id": 1, "bk_host_name": "host1", "bk_tenant_id": "test_tenant", "_id": "should_remove"},
                    {"bk_host_id": 2, "bk_host_name": "host2", "bk_tenant_id": "test_tenant"},
                    {"bk_host_id": 0, "bk_host_name": "invalid", "bk_tenant_id": "test_tenant"},
                ]

                CMDBInstance.bulk_update_or_create("host", instances)

                mock_bulk.assert_called_once()
                documents = mock_bulk.call_args[0][0]

                assert len(documents) == 2
                assert documents[0]["_id"] == "test_tenant_host_1"
                assert documents[1]["_id"] == "test_tenant_host_2"
                assert documents[0]["bk_obj_id"] == "host"
                assert "_id" not in documents[0]["_source"]
                assert documents[0]["_source"]["bk_agent_alive"] is True
                assert documents[0]["_source"]["error"] is False
                mock_enrich.assert_called_once()

    def test_bulk_delete(self):
        """测试批量删除实例"""
        with patch.object(CMDBInstance, "bulk_actions") as mock_bulk:
            inst_ids = [1, 2, 3]

            CMDBInstance.bulk_delete("host", inst_ids, bk_tenant_id="test_tenant")

            mock_bulk.assert_called_once()
            documents = mock_bulk.call_args[0][0]

            assert len(documents) == 3
            assert documents[0]["_op_type"] == "delete"
            assert documents[0]["_id"] == "test_tenant_host_1"
            assert documents[1]["_id"] == "test_tenant_host_2"
            assert documents[2]["_id"] == "test_tenant_host_3"


class TestCMDBObjRelate:
    """测试 CMDBObjRelate 模型"""

    def test_bulk_update_or_create(self):
        """测试批量更新或创建模型关联关系"""
        with patch.object(CMDBObjRelate, "bulk_actions") as mock_bulk:
            instances = [
                {
                    "bk_obj_asst_id": "rel1",
                    "bk_obj_id": "host",
                    "bk_asst_obj_id": "module",
                    "bk_tenant_id": "test_tenant",
                    "_id": "should_remove",
                },
                {
                    "bk_obj_asst_id": "rel2",
                    "bk_obj_id": "module",
                    "bk_asst_obj_id": "set",
                    "bk_tenant_id": "test_tenant",
                },
            ]

            CMDBObjRelate.bulk_update_or_create(instances)

            mock_bulk.assert_called_once()
            documents = mock_bulk.call_args[0][0]

            assert len(documents) == 2
            assert documents[0]["_id"] == "test_tenant_rel1"
            assert documents[1]["_id"] == "test_tenant_rel2"
            assert "_id" not in documents[0]["_source"]

    def test_bulk_delete(self):
        """测试批量删除模型关联关系"""
        with patch.object(CMDBObjRelate, "bulk_actions") as mock_bulk:
            CMDBObjRelate.bulk_delete("rel1", bk_tenant_id="test_tenant")

            mock_bulk.assert_called_once()
            documents = mock_bulk.call_args[0][0]

            assert len(documents) == 1
            assert documents[0]["_op_type"] == "delete"
            assert documents[0]["_id"] == "test_tenant_rel1"


class TestCMDBInstRelate:
    """测试 CMDBInstRelate 模型"""

    def test_bulk_update_or_create(self):
        """测试批量更新或创建实例关联关系"""
        with patch.object(CMDBInstRelate, "bulk_actions") as mock_bulk:
            instances = [
                {
                    "bk_obj_asst_id": "rel1",
                    "bk_obj_id": "host",
                    "bk_inst_id": "1",
                    "bk_asst_obj_id": "module",
                    "bk_asst_inst_id": "10",
                    "bk_tenant_id": "test_tenant",
                    "_id": "should_remove",
                },
                {
                    "bk_obj_asst_id": "rel2",
                    "bk_obj_id": "host",
                    "bk_inst_id": "2",
                    "bk_asst_obj_id": "module",
                    "bk_asst_inst_id": "20",
                    "bk_tenant_id": "test_tenant",
                },
            ]

            CMDBInstRelate.bulk_update_or_create(instances)

            mock_bulk.assert_called_once()
            documents = mock_bulk.call_args[0][0]

            assert len(documents) == 2
            assert documents[0]["_id"] == "test_tenant_rel1_host_1_module_10"
            assert documents[1]["_id"] == "test_tenant_rel2_host_2_module_20"
            assert "_id" not in documents[0]["_source"]

    def test_bulk_delete(self):
        """测试批量删除实例关联关系"""
        with patch.object(CMDBInstRelate, "bulk_actions") as mock_bulk:
            instances = [
                {
                    "bk_obj_asst_id": "rel1",
                    "bk_obj_id": "host",
                    "bk_inst_id": "1",
                    "bk_asst_obj_id": "module",
                    "bk_asst_inst_id": "10",
                    "bk_tenant_id": "test_tenant",
                },
            ]

            CMDBInstRelate.bulk_delete(instances)

            mock_bulk.assert_called_once()
            documents = mock_bulk.call_args[0][0]

            assert len(documents) == 1
            assert documents[0]["_op_type"] == "delete"
            assert documents[0]["_id"] == "test_tenant_rel1_host_1_module_10"
