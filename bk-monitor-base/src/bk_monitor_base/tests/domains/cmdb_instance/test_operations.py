"""
CMDB 实例操作函数单元测试
"""

from unittest.mock import Mock, patch

from bk_monitor_base.domains.cmdb_instance.operations import (
    _build_search_kwargs,
    enrich_host_instances_with_agent_status,
    get_host_agent_status_map,
    get_instance,
    get_instance_with_relations,
    iter_inst_relations,
    iter_instances,
    iter_instances_by_dsl,
    query_option_values,
    refresh_host_agent_status,
    search_all_inst_relations,
    search_all_instances,
    search_all_instances_by_dsl,
    search_inst_relations,
    search_instances,
    search_instances_advanced,
    search_instances_by_dsl,
    search_obj_relations,
)
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID


class TestSearchInstances:
    """测试 search_instances 函数"""

    def test_search_instances_basic(self):
        """测试基本的实例搜索"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 10
            mock_hit1 = Mock()
            mock_hit1.to_dict.return_value = {"bk_obj_id": "host", "bk_inst_id": 1}
            mock_hit2 = Mock()
            mock_hit2.to_dict.return_value = {"bk_obj_id": "host", "bk_inst_id": 2}
            # 修复：hits 应该是一个迭代器，不能直接设置为列表
            mock_response.hits.__iter__ = Mock(return_value=iter([mock_hit1, mock_hit2]))
            mock_search.execute.return_value = mock_response
            mock_model.get_search.return_value = mock_search

            total, instances = search_instances(bk_obj_id="host", page=1, size=10)

            assert total == 10
            assert len(instances) == 2
            assert instances[0]["bk_inst_id"] == 1
            assert instances[1]["bk_inst_id"] == 2

    def test_search_instances_with_query_dict(self):
        """测试使用查询字典搜索"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 5
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.execute.return_value = mock_response
            mock_model.get_search.return_value = mock_search

            query = {"custom_field": "custom_value"}
            total, instances = search_instances(bk_obj_id="host", bk_biz_id="2", query=query)

            # 验证查询参数被正确合并
            call_args = mock_model.get_search.call_args
            assert call_args[1]["query"]["bk_obj_id"] == "host"
            assert call_args[1]["query"]["bk_biz_id"] == "2"
            assert call_args[1]["query"]["custom_field"] == "custom_value"

    def test_search_instances_with_bk_inst_ids(self):
        """测试使用实例ID列表搜索"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 3
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.execute.return_value = mock_response
            mock_model.get_search.return_value = mock_search

            total, instances = search_instances(bk_inst_ids=[1, 2, 3])

            call_args = mock_model.get_search.call_args
            assert call_args[1]["query"]["bk_inst_id"] == [1, 2, 3]

    def test_search_instances_with_tenant_id(self):
        """测试使用租户ID搜索"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 5
            mock_hit1 = Mock()
            mock_hit1.to_dict.return_value = {"bk_obj_id": "host", "bk_inst_id": 1, "bk_tenant_id": "tenant_001"}
            mock_response.hits.__iter__ = Mock(return_value=iter([mock_hit1]))
            mock_search.execute.return_value = mock_response
            mock_model.get_search.return_value = mock_search

            total, instances = search_instances(bk_obj_id="host", bk_tenant_id="tenant_001")

            # 验证租户ID参数被正确传递
            call_args = mock_model.get_search.call_args
            assert call_args[1]["query"]["bk_tenant_id"] == "tenant_001"
            assert total == 5
            assert len(instances) == 1
            assert instances[0]["bk_tenant_id"] == "tenant_001"

    def test_search_instances_with_default_tenant_id(self):
        """测试使用默认租户ID搜索"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 10
            mock_hit1 = Mock()
            mock_hit1.to_dict.return_value = {"bk_obj_id": "host", "bk_inst_id": 1, "bk_tenant_id": DEFAULT_TENANT_ID}
            mock_response.hits.__iter__ = Mock(return_value=iter([mock_hit1]))
            mock_search.execute.return_value = mock_response
            mock_model.get_search.return_value = mock_search

            total, instances = search_instances(bk_obj_id="host", bk_tenant_id=DEFAULT_TENANT_ID)

            # 验证默认租户ID被正确使用
            call_args = mock_model.get_search.call_args
            assert call_args[1]["query"]["bk_tenant_id"] == DEFAULT_TENANT_ID
            assert instances[0]["bk_tenant_id"] == DEFAULT_TENANT_ID

    def test_search_instances_without_tenant_id(self):
        """测试不指定租户ID时的搜索行为"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 20
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.execute.return_value = mock_response
            mock_model.get_search.return_value = mock_search

            total, instances = search_instances(bk_obj_id="host")

            # 验证不传递租户ID时，查询字典中不包含该字段
            call_args = mock_model.get_search.call_args
            assert "bk_tenant_id" not in call_args[1]["query"]

    def test_search_instances_with_all_params(self):
        """测试使用所有参数搜索"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 1
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.execute.return_value = mock_response
            mock_model.get_search.return_value = mock_search

            total, instances = search_instances(
                bk_obj_id="host",
                bk_inst_ids=[1, 2],
                bk_biz_id="2",
                bk_biz_ids=["2", "3"],
                bk_tenant_id="tenant_001",
                dynamic_group_id="group1",
                cw_object_model_code="custom_model",
                cw_object_model_inst_id="inst_001",
                search={"bk_host_name": "test"},
                page=2,
                size=20,
                sort="-created_at",
                fields=["bk_inst_id", "bk_inst_name"],
            )

            call_args = mock_model.get_search.call_args
            assert call_args[1]["page"] == 2
            assert call_args[1]["size"] == 20
            assert call_args[1]["sort"] == "-created_at"
            assert call_args[1]["fields"] == ["bk_inst_id", "bk_inst_name"]
            assert call_args[1]["query"]["bk_tenant_id"] == "tenant_001"
            assert call_args[1]["query"]["cw_object_model_code"] == "custom_model"
            assert call_args[1]["query"]["cw_object_model_inst_id"] == "inst_001"

    def test_search_instances_with_cw_object_model_params(self):
        """测试使用对象模型参数搜索"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 2
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.execute.return_value = mock_response
            mock_model.get_search.return_value = mock_search

            total, instances = search_instances(cw_object_model_code="custom_model", cw_object_model_inst_id="inst_001")

            call_args = mock_model.get_search.call_args
            assert call_args[1]["query"]["cw_object_model_code"] == "custom_model"
            assert call_args[1]["query"]["cw_object_model_inst_id"] == "inst_001"
            assert total == 2


class TestSearchAllInstances:
    """测试 search_all_instances 函数"""

    def test_search_all_instances_single_page(self):
        """测试单页查询所有实例"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_instances") as mock_search:
            mock_search.return_value = (5, [{"bk_inst_id": i} for i in range(1, 6)])

            instances = search_all_instances(bk_obj_id="host", batch_size=10)

            assert len(instances) == 5
            mock_search.assert_called_once()

    def test_search_all_instances_multiple_pages(self):
        """测试多页查询所有实例"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_instances") as mock_search:
            # 模拟分页返回
            mock_search.side_effect = [
                (25, [{"bk_inst_id": i} for i in range(1, 11)]),  # 第1页：10条
                (25, [{"bk_inst_id": i} for i in range(11, 21)]),  # 第2页：10条
                (25, [{"bk_inst_id": i} for i in range(21, 26)]),  # 第3页：5条
            ]

            instances = search_all_instances(bk_obj_id="host", batch_size=10)

            assert len(instances) == 25
            assert mock_search.call_count == 3

    def test_search_all_instances_empty(self):
        """测试查询空结果"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_instances") as mock_search:
            mock_search.return_value = (0, [])

            instances = search_all_instances(bk_obj_id="host")

            assert len(instances) == 0
            mock_search.assert_called_once()

    def test_search_all_instances_with_tenant_id(self):
        """测试使用租户ID查询所有实例"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_instances") as mock_search:
            mock_search.return_value = (3, [{"bk_inst_id": i, "bk_tenant_id": "tenant_001"} for i in range(1, 4)])

            instances = search_all_instances(bk_obj_id="host", bk_tenant_id="tenant_001", batch_size=10)

            assert len(instances) == 3
            # 验证租户ID参数被传递到 search_instances
            call_args = mock_search.call_args
            assert call_args[1]["bk_tenant_id"] == "tenant_001"

    def test_search_all_instances_with_tenant_id_multiple_pages(self):
        """测试使用租户ID多页查询所有实例"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_instances") as mock_search:
            # 模拟分页返回，每条记录都有租户ID
            mock_search.side_effect = [
                (15, [{"bk_inst_id": i, "bk_tenant_id": "tenant_002"} for i in range(1, 11)]),
                (15, [{"bk_inst_id": i, "bk_tenant_id": "tenant_002"} for i in range(11, 16)]),
            ]

            instances = search_all_instances(bk_obj_id="host", bk_tenant_id="tenant_002", batch_size=10)

            assert len(instances) == 15
            assert mock_search.call_count == 2
            # 验证所有调用都传递了租户ID
            for call in mock_search.call_args_list:
                assert call[1]["bk_tenant_id"] == "tenant_002"


class TestGetInstance:
    """测试 get_instance 函数"""

    def test_get_instance_success(self):
        """测试成功获取实例"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_client = Mock()
            mock_client.get.return_value = {"_source": {"bk_obj_id": "host", "bk_inst_id": 123}}
            mock_model.get_es_client.return_value = mock_client
            mock_model.Index.ALIAS = "test_alias"

            instance = get_instance("host", 123)

            assert instance is not None
            assert instance["bk_inst_id"] == 123
            mock_client.get.assert_called_once_with(index="test_alias", id="host_123")

    def test_get_instance_not_found(self):
        """测试获取不存在的实例"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_client = Mock()
            mock_client.get.side_effect = Exception("Not found")
            mock_model.get_es_client.return_value = mock_client
            mock_model.Index.ALIAS = "test_alias"

            instance = get_instance("host", 999)

            assert instance is None

    def test_get_instance_with_cw_object_model_code_match(self):
        """测试使用对象模型代码过滤实例 - 匹配情况"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_client = Mock()
            mock_client.get.return_value = {
                "_source": {"bk_obj_id": "host", "bk_inst_id": 123, "cw_object_model_code": "custom_model"}
            }
            mock_model.get_es_client.return_value = mock_client
            mock_model.Index.ALIAS = "test_alias"

            instance = get_instance("host", 123, cw_object_model_code="custom_model")

            assert instance is not None
            assert instance["cw_object_model_code"] == "custom_model"

    def test_get_instance_with_cw_object_model_code_no_match(self):
        """测试使用对象模型代码过滤实例 - 不匹配情况"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_client = Mock()
            mock_client.get.return_value = {
                "_source": {"bk_obj_id": "host", "bk_inst_id": 123, "cw_object_model_code": "other_model"}
            }
            mock_model.get_es_client.return_value = mock_client
            mock_model.Index.ALIAS = "test_alias"

            instance = get_instance("host", 123, cw_object_model_code="custom_model")

            assert instance is None

    def test_get_instance_with_cw_object_model_inst_id_match(self):
        """测试使用对象模型实例ID过滤实例 - 匹配情况"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_client = Mock()
            mock_client.get.return_value = {
                "_source": {"bk_obj_id": "host", "bk_inst_id": 123, "cw_object_model_inst_id": "inst_001"}
            }
            mock_model.get_es_client.return_value = mock_client
            mock_model.Index.ALIAS = "test_alias"

            instance = get_instance("host", 123, cw_object_model_inst_id="inst_001")

            assert instance is not None
            assert instance["cw_object_model_inst_id"] == "inst_001"

    def test_get_instance_with_cw_object_model_inst_id_no_match(self):
        """测试使用对象模型实例ID过滤实例 - 不匹配情况"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_client = Mock()
            mock_client.get.return_value = {
                "_source": {"bk_obj_id": "host", "bk_inst_id": 123, "cw_object_model_inst_id": "inst_002"}
            }
            mock_model.get_es_client.return_value = mock_client
            mock_model.Index.ALIAS = "test_alias"

            instance = get_instance("host", 123, cw_object_model_inst_id="inst_001")

            assert instance is None

    def test_get_instance_with_both_cw_params(self):
        """测试同时使用两个对象模型参数过滤实例"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_client = Mock()
            mock_client.get.return_value = {
                "_source": {
                    "bk_obj_id": "host",
                    "bk_inst_id": 123,
                    "cw_object_model_code": "custom_model",
                    "cw_object_model_inst_id": "inst_001",
                }
            }
            mock_model.get_es_client.return_value = mock_client
            mock_model.Index.ALIAS = "test_alias"

            instance = get_instance(
                "host", 123, cw_object_model_code="custom_model", cw_object_model_inst_id="inst_001"
            )

            assert instance is not None
            assert instance["cw_object_model_code"] == "custom_model"
            assert instance["cw_object_model_inst_id"] == "inst_001"


class TestQueryOptionValues:
    """测试 query_option_values 函数"""

    def test_query_option_values_basic(self):
        """测试查询字段可选值"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_model.get_search.return_value = mock_search
            mock_model.query_option_values.return_value = {"bk_biz_id": ["2", "3", "5"], "bk_cloud_id": ["0", "1"]}

            result = query_option_values(fields=["bk_biz_id", "bk_cloud_id"], bk_obj_id="host")

            assert "bk_biz_id" in result
            assert "bk_cloud_id" in result
            assert len(result["bk_biz_id"]) == 3
            assert len(result["bk_cloud_id"]) == 2

    def test_query_option_values_with_query(self):
        """测试带查询条件的字段可选值查询"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_model.get_search.return_value = mock_search
            mock_model.query_option_values.return_value = {"field": ["val1"]}

            query = {"bk_biz_id": "2"}
            query_option_values(fields=["field"], bk_obj_id="host", query=query)

            call_args = mock_model.get_search.call_args
            assert call_args[1]["query"]["bk_obj_id"] == "host"
            assert call_args[1]["query"]["bk_biz_id"] == "2"


class TestSearchObjRelations:
    """测试 search_obj_relations 函数"""

    def test_search_obj_relations_basic(self):
        """测试基本的模型关联关系搜索"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBObjRelate") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 2
            mock_hit1 = Mock()
            mock_hit1.to_dict.return_value = {"bk_obj_asst_id": "rel1"}
            mock_response.hits.__iter__ = Mock(return_value=iter([mock_hit1]))
            mock_search.execute.return_value = mock_response
            mock_model.get_search.return_value = mock_search

            total, relations = search_obj_relations(bk_obj_id="host", bk_asst_obj_id="module")

            assert total == 2
            assert len(relations) == 1


class TestSearchInstRelations:
    """测试 search_inst_relations 函数"""

    def test_search_inst_relations_basic(self):
        """测试基本的实例关联关系搜索"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstRelate") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 5
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.execute.return_value = mock_response
            mock_model.get_search.return_value = mock_search

            total, relations = search_inst_relations(bk_obj_id="host", bk_inst_id="1")

            assert total == 5
            assert len(relations) == 0

    def test_search_inst_relations_with_all_params(self):
        """测试使用所有参数搜索实例关联关系"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstRelate") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 1
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.execute.return_value = mock_response
            mock_model.get_search.return_value = mock_search

            total, relations = search_inst_relations(
                bk_obj_id="host",
                bk_inst_id="1",
                bk_asst_obj_id="module",
                bk_asst_inst_id="10",
                bk_obj_asst_id="rel1",
                page=1,
                size=10,
            )

            call_args = mock_model.get_search.call_args
            query = call_args[1]["query"]
            assert query["bk_obj_id"] == "host"
            assert query["bk_inst_id"] == "1"
            assert query["bk_asst_obj_id"] == "module"
            assert query["bk_asst_inst_id"] == "10"
            assert query["bk_obj_asst_id"] == "rel1"


class TestSearchAllInstRelations:
    """测试 search_all_inst_relations 函数"""

    def test_search_all_inst_relations_single_page(self):
        """测试单页查询所有实例关联关系"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_inst_relations") as mock_search:
            mock_search.return_value = (3, [{"bk_obj_asst_id": f"rel{i}"} for i in range(1, 4)])

            relations = search_all_inst_relations(bk_obj_id="host", bk_inst_id="1")

            assert len(relations) == 3
            mock_search.assert_called_once()

    def test_search_all_inst_relations_multiple_pages(self):
        """测试多页查询所有实例关联关系"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_inst_relations") as mock_search:
            mock_search.side_effect = [
                (15, [{"id": i} for i in range(1, 11)]),  # 第1页：10条
                (15, [{"id": i} for i in range(11, 16)]),  # 第2页：5条
            ]

            relations = search_all_inst_relations(bk_obj_id="host", bk_inst_id="1", batch_size=10)

            assert len(relations) == 15
            assert mock_search.call_count == 2


class TestGetInstanceWithRelations:
    """测试 get_instance_with_relations 函数"""

    def test_get_instance_with_relations_success(self):
        """测试成功获取实例及关联关系"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.get_instance") as mock_get:
            with patch("bk_monitor_base.domains.cmdb_instance.operations.search_inst_relations") as mock_search:
                mock_get.return_value = {"bk_obj_id": "host", "bk_inst_id": 123}
                mock_search.side_effect = [
                    (2, [{"type": "source", "id": 1}, {"type": "source", "id": 2}]),  # source_relations
                    (1, [{"type": "target", "id": 3}]),  # target_relations
                ]

                instance = get_instance_with_relations("host", 123)

                assert instance is not None
                assert "source_relations" in instance
                assert "target_relations" in instance
                assert len(instance["source_relations"]) == 2
                assert len(instance["target_relations"]) == 1

    def test_get_instance_with_relations_not_found(self):
        """测试获取不存在的实例及关联关系"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.get_instance") as mock_get:
            mock_get.return_value = None

            instance = get_instance_with_relations("host", 999)

            assert instance is None

    def test_get_instance_without_relations(self):
        """测试获取实例但不包含关联关系"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.get_instance") as mock_get:
            mock_get.return_value = {"bk_obj_id": "host", "bk_inst_id": 123}

            instance = get_instance_with_relations("host", 123, include_relations=False)

            assert instance is not None
            assert "source_relations" not in instance
            assert "target_relations" not in instance

    def test_get_instance_with_relations_calls_search_correctly(self):
        """测试正确调用搜索方法查询关联关系"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.get_instance") as mock_get:
            with patch("bk_monitor_base.domains.cmdb_instance.operations.search_inst_relations") as mock_search:
                mock_get.return_value = {"bk_obj_id": "host", "bk_inst_id": 123}
                mock_search.return_value = (0, [])

                get_instance_with_relations("host", 123)

                # 验证调用了两次搜索：一次查询起点关系，一次查询终点关系
                assert mock_search.call_count == 2

                # 第一次调用：查询该实例作为起点的关系
                first_call = mock_search.call_args_list[0]
                assert first_call[1]["bk_obj_id"] == "host"
                assert first_call[1]["bk_inst_id"] == "123"
                assert first_call[1]["size"] == 10000

                # 第二次调用：查询该实例作为终点的关系
                second_call = mock_search.call_args_list[1]
                assert second_call[1]["bk_asst_obj_id"] == "host"
                assert second_call[1]["bk_asst_inst_id"] == "123"
                assert second_call[1]["size"] == 10000


class TestBuildSearchKwargs:
    """测试 _build_search_kwargs 辅助函数"""

    def test_build_search_kwargs_empty(self):
        """测试空参数"""
        result = _build_search_kwargs()
        assert result == {}

    def test_build_search_kwargs_basic_params(self):
        """测试基本参数"""
        result = _build_search_kwargs(
            bk_obj_id="host",
            bk_inst_ids=[1, 2, 3],
            bk_biz_id="2",
            bk_tenant_id="tenant1",
        )
        assert result["bk_obj_id"] == "host"
        assert result["bk_inst_id"] == [1, 2, 3]  # 注意：参数名是 bk_inst_ids，但存储为 bk_inst_id
        assert result["bk_biz_id"] == "2"
        assert result["bk_tenant_id"] == "tenant1"

    def test_build_search_kwargs_with_custom_query(self):
        """测试合并自定义查询参数"""
        custom_query = {"custom_field": "value"}
        result = _build_search_kwargs(bk_obj_id="host", query=custom_query)
        assert result["bk_obj_id"] == "host"
        assert result["custom_field"] == "value"

    def test_build_search_kwargs_all_params(self):
        """测试所有参数"""
        result = _build_search_kwargs(
            bk_obj_id="host",
            bk_inst_ids=[1, 2],
            bk_biz_id="2",
            bk_biz_ids=["2", "3"],
            bk_tenant_id="tenant1",
            dynamic_group_id="group1",
            cw_object_model_code="custom_model",
            cw_object_model_inst_id="inst_001",
            query={"extra": "data"},
        )
        assert result["bk_obj_id"] == "host"
        assert result["bk_inst_id"] == [1, 2]  # 注意：存储为 bk_inst_id
        assert result["bk_biz_id"] == ["2", "3"]  # bk_biz_ids 会覆盖 bk_biz_id
        assert result["bk_tenant_id"] == "tenant1"
        assert result["dynamic_group_id"] == "group1"
        assert result["cw_object_model_code"] == "custom_model"
        assert result["cw_object_model_inst_id"] == "inst_001"
        assert result["extra"] == "data"


class TestSearchInstancesAdvanced:
    """测试 search_instances_advanced 函数"""

    def test_search_instances_advanced_basic(self):
        """测试基本高级查询"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 5
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.execute.return_value = mock_response
            mock_model.get_query_instance.return_value = mock_search

            total, instances = search_instances_advanced(bk_obj_id="host", query={"bk_biz_id": "2"})

            assert total == 5
            mock_model.get_query_instance.assert_called_once()

    def test_search_instances_advanced_with_or_query(self):
        """测试OR查询"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 10
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.execute.return_value = mock_response
            mock_model.get_query_instance.return_value = mock_search

            or_query = {"bk_cloud_id": [0, 1]}
            total, instances = search_instances_advanced(bk_obj_id="host", or_query=or_query)

            call_args = mock_model.get_query_instance.call_args
            assert call_args[1]["or_query"] == or_query

    def test_search_instances_advanced_with_exclude_query(self):
        """测试排除查询"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 8
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.execute.return_value = mock_response
            mock_model.get_query_instance.return_value = mock_search

            exclude_query = {"bk_state": ["stopped"]}
            total, instances = search_instances_advanced(bk_obj_id="host", exclude_query=exclude_query)

            call_args = mock_model.get_query_instance.call_args
            assert call_args[1]["exclude_query"] == exclude_query

    def test_search_instances_advanced_with_time_range(self):
        """测试时间范围查询"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 15
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.execute.return_value = mock_response
            mock_model.get_query_instance.return_value = mock_search

            time_range = {"field": "create_time", "start": "2024-01-01", "end": "2024-12-31"}
            total, instances = search_instances_advanced(bk_obj_id="host", time_range=time_range)

            call_args = mock_model.get_query_instance.call_args
            assert call_args[1]["time_field"] == "create_time"
            assert call_args[1]["start_time"] == "2024-01-01"
            assert call_args[1]["end_time"] == "2024-12-31"

    def test_search_instances_advanced_with_global_search(self):
        """测试全局多字段搜索"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 20
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.execute.return_value = mock_response
            mock_model.get_query_instance.return_value = mock_search

            global_search = {"keyword": "192.168", "fields": ["bk_host_innerip", "bk_host_outerip"]}
            total, instances = search_instances_advanced(bk_obj_id="host", global_search=global_search)

            call_args = mock_model.get_query_instance.call_args
            assert call_args[1]["global_search"]["keyword"] == "192.168"
            assert call_args[1]["global_search"]["search_list"] == ["bk_host_innerip", "bk_host_outerip"]

    def test_search_instances_advanced_with_pagination(self):
        """测试分页查询"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 100
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.__getitem__ = Mock(return_value=mock_search)
            mock_search.execute.return_value = mock_response
            mock_model.get_query_instance.return_value = mock_search

            total, instances = search_instances_advanced(bk_obj_id="host", page=2, size=20)

            # 验证分页：s[20:40]
            mock_search.__getitem__.assert_called_once_with(slice(20, 40))


class TestSearchInstancesByDsl:
    """测试 search_instances_by_dsl 函数"""

    def test_search_instances_by_dsl_basic(self):
        """测试基本DSL查询"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 10
            mock_hit = Mock()
            mock_hit.to_dict.return_value = {"bk_inst_id": 1}
            mock_response.hits.__iter__ = Mock(return_value=iter([mock_hit]))
            mock_search.update_from_dict.return_value = mock_search
            mock_search.execute.return_value = mock_response
            mock_model.search.return_value = mock_search

            dsl = {"term": {"bk_obj_id": "host"}}
            total, instances = search_instances_by_dsl(dsl)

            assert total == 10
            assert len(instances) == 1
            mock_search.update_from_dict.assert_called_once_with({"query": dsl})

    def test_search_instances_by_dsl_with_pagination(self):
        """测试DSL查询分页"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 50
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.update_from_dict.return_value = mock_search
            mock_search.__getitem__ = Mock(return_value=mock_search)
            mock_search.execute.return_value = mock_response
            mock_model.search.return_value = mock_search

            dsl = {"match_all": {}}
            total, instances = search_instances_by_dsl(dsl, page=2, size=10)

            # 验证分页：s[10:20]
            mock_search.__getitem__.assert_called_once_with(slice(10, 20))

    def test_search_instances_by_dsl_with_sort(self):
        """测试DSL查询排序"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 5
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.update_from_dict.return_value = mock_search
            mock_search.sort.return_value = mock_search
            mock_search.execute.return_value = mock_response
            mock_model.search.return_value = mock_search

            dsl = {"term": {"bk_obj_id": "host"}}
            total, instances = search_instances_by_dsl(dsl, sort="-create_time")

            mock_search.sort.assert_called_once_with("-create_time")

    def test_search_instances_by_dsl_with_fields(self):
        """测试DSL查询字段过滤"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 3
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.update_from_dict.return_value = mock_search
            mock_search.source.return_value = mock_search
            mock_search.execute.return_value = mock_response
            mock_model.search.return_value = mock_search

            dsl = {"match_all": {}}
            fields = ["bk_inst_id", "bk_inst_name"]
            total, instances = search_instances_by_dsl(dsl, fields=fields)

            mock_search.source.assert_called_once_with(fields)

    def test_search_instances_by_dsl_with_bool_query(self):
        """测试完整 bool DSL 被原样注入查询。"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance") as mock_model:
            mock_search = Mock()
            mock_response = Mock()
            mock_response.hits.total.value = 1
            mock_response.hits.__iter__ = Mock(return_value=iter([]))
            mock_search.update_from_dict.return_value = mock_search
            mock_search.execute.return_value = mock_response
            mock_model.search.return_value = mock_search

            dsl = {
                "bool": {
                    "must": [
                        {"term": {"bk_tenant_id": "system"}},
                        {"term": {"bk_obj_id": "host"}},
                        {"term": {"bk_os_type.keyword": "1"}},
                    ],
                    "must_not": [],
                }
            }

            search_instances_by_dsl(dsl)

            mock_search.update_from_dict.assert_called_once_with({"query": dsl})


class TestSearchAllInstancesByDsl:
    """测试 search_all_instances_by_dsl 函数"""

    def test_search_all_instances_by_dsl_single_page(self):
        """测试单页DSL查询所有实例"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_instances_by_dsl") as mock_search:
            mock_search.return_value = (5, [{"bk_inst_id": i} for i in range(1, 6)])

            dsl = {"term": {"bk_obj_id": "host"}}
            instances = search_all_instances_by_dsl(dsl, batch_size=10)

            assert len(instances) == 5
            mock_search.assert_called_once()

    def test_search_all_instances_by_dsl_multiple_pages(self):
        """测试多页DSL查询所有实例"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_instances_by_dsl") as mock_search:
            mock_search.side_effect = [
                (25, [{"bk_inst_id": i} for i in range(1, 11)]),
                (25, [{"bk_inst_id": i} for i in range(11, 21)]),
                (25, [{"bk_inst_id": i} for i in range(21, 26)]),
            ]

            dsl = {"match_all": {}}
            instances = search_all_instances_by_dsl(dsl, batch_size=10)

            assert len(instances) == 25
            assert mock_search.call_count == 3

    def test_search_all_instances_by_dsl_empty(self):
        """测试DSL查询空结果"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_instances_by_dsl") as mock_search:
            mock_search.return_value = (0, [])

            dsl = {"term": {"bk_obj_id": "nonexistent"}}
            instances = search_all_instances_by_dsl(dsl)

            assert len(instances) == 0


class TestIterInstances:
    """测试 iter_instances 迭代器函数"""

    def test_iter_instances_single_batch(self):
        """测试单批次迭代"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_instances") as mock_search:
            mock_search.return_value = (5, [{"bk_inst_id": i} for i in range(1, 6)])

            batches = list(iter_instances(bk_obj_id="host", batch_size=10))

            assert len(batches) == 1
            assert len(batches[0]) == 5

    def test_iter_instances_multiple_batches(self):
        """测试多批次迭代"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_instances") as mock_search:
            mock_search.side_effect = [
                (25, [{"bk_inst_id": i} for i in range(1, 11)]),
                (25, [{"bk_inst_id": i} for i in range(11, 21)]),
                (25, [{"bk_inst_id": i} for i in range(21, 26)]),
                (25, []),  # 空结果，停止迭代
            ]

            batches = list(iter_instances(bk_obj_id="host", batch_size=10))

            assert len(batches) == 3
            assert len(batches[0]) == 10
            assert len(batches[1]) == 10
            assert len(batches[2]) == 5

    def test_iter_instances_empty(self):
        """测试空结果迭代"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_instances") as mock_search:
            mock_search.return_value = (0, [])

            batches = list(iter_instances(bk_obj_id="host"))

            assert len(batches) == 0

    def test_iter_instances_lazy_loading(self):
        """测试惰性加载特性"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_instances") as mock_search:
            mock_search.side_effect = [
                (20, [{"bk_inst_id": i} for i in range(1, 11)]),
                (20, [{"bk_inst_id": i} for i in range(11, 21)]),
            ]

            iterator = iter_instances(bk_obj_id="host", batch_size=10)

            # 第一次迭代，只调用一次
            first_batch = next(iterator)
            assert len(first_batch) == 10
            assert mock_search.call_count == 1

            # 第二次迭代，再调用一次
            second_batch = next(iterator)
            assert len(second_batch) == 10
            assert mock_search.call_count == 2


class TestIterInstRelations:
    """测试 iter_inst_relations 迭代器函数"""

    def test_iter_inst_relations_single_batch(self):
        """测试单批次迭代关联关系"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_inst_relations") as mock_search:
            mock_search.return_value = (3, [{"id": i} for i in range(1, 4)])

            batches = list(iter_inst_relations(bk_obj_id="host", bk_inst_id="1"))

            assert len(batches) == 1
            assert len(batches[0]) == 3

    def test_iter_inst_relations_multiple_batches(self):
        """测试多批次迭代关联关系"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_inst_relations") as mock_search:
            mock_search.side_effect = [
                (15, [{"id": i} for i in range(1, 11)]),
                (15, [{"id": i} for i in range(11, 16)]),
                (15, []),
            ]

            batches = list(iter_inst_relations(bk_obj_id="host", batch_size=10))

            assert len(batches) == 2
            assert len(batches[0]) == 10
            assert len(batches[1]) == 5

    def test_iter_inst_relations_empty(self):
        """测试空结果迭代"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_inst_relations") as mock_search:
            mock_search.return_value = (0, [])

            batches = list(iter_inst_relations(bk_obj_id="host"))

            assert len(batches) == 0


class TestIterInstancesByDsl:
    """测试 iter_instances_by_dsl 迭代器函数"""

    def test_iter_instances_by_dsl_single_batch(self):
        """测试单批次DSL迭代"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_instances_by_dsl") as mock_search:
            mock_search.return_value = (8, [{"bk_inst_id": i} for i in range(1, 9)])

            dsl = {"term": {"bk_obj_id": "host"}}
            batches = list(iter_instances_by_dsl(dsl, batch_size=10))

            assert len(batches) == 1
            assert len(batches[0]) == 8

    def test_iter_instances_by_dsl_multiple_batches(self):
        """测试多批次DSL迭代"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_instances_by_dsl") as mock_search:
            mock_search.side_effect = [
                (22, [{"bk_inst_id": i} for i in range(1, 11)]),
                (22, [{"bk_inst_id": i} for i in range(11, 21)]),
                (22, [{"bk_inst_id": i} for i in range(21, 23)]),
                (22, []),
            ]

            dsl = {"match_all": {}}
            batches = list(iter_instances_by_dsl(dsl, batch_size=10))

            assert len(batches) == 3
            assert len(batches[0]) == 10
            assert len(batches[1]) == 10
            assert len(batches[2]) == 2

    def test_iter_instances_by_dsl_empty(self):
        """测试DSL空结果迭代"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_instances_by_dsl") as mock_search:
            mock_search.return_value = (0, [])

            dsl = {"term": {"bk_obj_id": "nonexistent"}}
            batches = list(iter_instances_by_dsl(dsl))

            assert len(batches) == 0

    def test_iter_instances_by_dsl_with_params(self):
        """测试带参数的DSL迭代"""
        with patch("bk_monitor_base.domains.cmdb_instance.operations.search_instances_by_dsl") as mock_search:
            mock_search.return_value = (5, [{"bk_inst_id": i} for i in range(1, 6)])

            dsl = {"bool": {"must": [{"term": {"bk_obj_id": "host"}}]}}
            batches = list(iter_instances_by_dsl(dsl, sort="-create_time", fields=["bk_inst_id"]))

            assert len(batches) == 1
            assert len(batches[0]) == 5

            # 验证传递了正确的参数
            call_args = mock_search.call_args
            assert call_args[1]["sort"] == "-create_time"
            assert call_args[1]["fields"] == ["bk_inst_id"]


class TestHostAgentStatusHelpers:
    """测试主机 Agent 状态辅助函数"""

    @patch("bk_monitor_base.infras.third_party_api.nodeman.api.get_ipchooser_host_details")
    def test_get_host_agent_status_map_success(self, mock_get_ipchooser_host_details):
        mock_get_ipchooser_host_details.return_value = [{"bk_host_id": 1, "bk_agent_alive": 1}]

        result = get_host_agent_status_map(
            bk_tenant_id="system",
            hosts=[
                {"bk_host_id": 1, "bk_biz_id": 2, "bk_host_innerip": "10.0.0.1", "bk_cloud_id": 0},
                {"bk_host_id": 1, "bk_biz_id": 2, "ip": "10.0.0.1", "bk_cloud_id": 0},
            ],
        )

        assert result == {"1": {"bk_host_id": 1, "bk_agent_alive": 1}}
        params = mock_get_ipchooser_host_details.call_args.kwargs["params"]
        assert params["host_list"] == [
            {
                "host_id": 1,
                "meta": {
                    "scope_type": "biz",
                    "scope_id": "2",
                    "bk_biz_id": 2,
                },
            }
        ]
        assert params["scope_list"] == [{"scope_type": "biz", "scope_id": "2"}]
        assert params["agent_realtime_state"] is True

    @patch("bk_monitor_base.infras.third_party_api.nodeman.api.get_ipchooser_host_details")
    def test_get_host_agent_status_map_error(self, mock_get_ipchooser_host_details):
        mock_get_ipchooser_host_details.side_effect = Exception("nodeman error")

        result = get_host_agent_status_map(
            bk_tenant_id="system",
            hosts=[{"bk_host_id": 1, "bk_biz_id": 2, "bk_host_innerip": "10.0.0.1", "bk_cloud_id": 0}],
        )

        assert result == {}

    @patch("bk_monitor_base.infras.third_party_api.nodeman.api.get_ipchooser_host_details")
    def test_get_host_agent_status_map_batches_host_list(self, mock_get_ipchooser_host_details):
        mock_get_ipchooser_host_details.side_effect = [
            [{"bk_host_id": 1, "bk_agent_alive": 1}],
            [{"bk_host_id": 1001, "bk_agent_alive": 0}],
        ]

        hosts = [
            {"bk_host_id": index, "bk_biz_id": 2, "bk_host_innerip": f"10.0.0.{index}", "bk_cloud_id": 0}
            for index in range(1, 1002)
        ]

        result = get_host_agent_status_map(
            bk_tenant_id="system",
            hosts=hosts,
        )

        assert result["1"]["bk_agent_alive"] == 1
        assert result["1001"]["bk_agent_alive"] == 0
        assert mock_get_ipchooser_host_details.call_count == 2
        first_call_params = mock_get_ipchooser_host_details.call_args_list[0].kwargs["params"]
        second_call_params = mock_get_ipchooser_host_details.call_args_list[1].kwargs["params"]
        assert len(first_call_params["host_list"]) == 1000
        assert len(second_call_params["host_list"]) == 1
        assert first_call_params["scope_list"] == [{"scope_type": "biz", "scope_id": "2"}]
        assert second_call_params["scope_list"] == [{"scope_type": "biz", "scope_id": "2"}]

    @patch("bk_monitor_base.infras.third_party_api.nodeman.api.get_ipchooser_host_details")
    def test_get_host_agent_status_map_skip_host_without_biz(self, mock_get_ipchooser_host_details):
        result = get_host_agent_status_map(
            bk_tenant_id="system",
            hosts=[{"bk_host_id": 1, "bk_host_innerip": "10.0.0.1", "bk_cloud_id": 0}],
        )

        assert result == {}
        mock_get_ipchooser_host_details.assert_not_called()

    @patch("bk_monitor_base.domains.cmdb_instance.agent_status.get_host_agent_status_map")
    def test_enrich_host_instances_with_agent_status(self, mock_status_map):
        mock_status_map.return_value = {"1": {"bk_agent_alive": 1}}

        result = enrich_host_instances_with_agent_status(
            bk_tenant_id="system",
            host_instances=[
                {"bk_host_id": 1, "bk_host_innerip": "10.0.0.1", "bk_cloud_id": 0},
                {"bk_host_id": 2, "bk_host_innerip": "10.0.0.2", "bk_cloud_id": 0},
            ],
        )

        assert result[0]["bk_agent_alive"] is True
        assert result[0]["error"] is False
        assert result[1]["bk_agent_alive"] is False
        assert result[1]["error"] is True
        assert result[0]["agent_status_sync_time"] is not None

    @patch("bk_monitor_base.domains.cmdb_instance.agent_status.get_host_agent_status_map")
    def test_enrich_host_instances_with_missing_agent_id(self, mock_status_map):
        mock_status_map.return_value = {}

        result = enrich_host_instances_with_agent_status(
            bk_tenant_id="system",
            host_instances=[{"bk_host_id": 2, "bk_host_innerip": "10.0.0.2", "bk_cloud_id": 0, "bk_agent_id": ""}],
        )

        assert result[0]["bk_agent_alive"] is False
        assert result[0]["error"] is True

    @patch("bk_monitor_base.domains.cmdb_instance.operations.CMDBInstance.bulk_update_or_create")
    @patch("bk_monitor_base.domains.cmdb_instance.operations.enrich_host_instances_with_agent_status")
    @patch("bk_monitor_base.domains.cmdb_instance.operations.search_all_instances")
    def test_refresh_host_agent_status(
        self,
        mock_search_all_instances,
        mock_enrich_host_instances,
        mock_bulk_update,
    ):
        mock_search_all_instances.return_value = [{"bk_host_id": 1, "bk_host_innerip": "10.0.0.1", "bk_cloud_id": 0}]
        mock_enrich_host_instances.return_value = [
            {
                "bk_host_id": 1,
                "bk_host_innerip": "10.0.0.1",
                "bk_cloud_id": 0,
                "bk_agent_alive": True,
                "error": False,
            }
        ]

        result = refresh_host_agent_status("system", bk_host_ids=[1])

        assert result == 1
        assert mock_search_all_instances.call_args.kwargs["query"] == {"bk_host_id": [1]}
        mock_bulk_update.assert_called_once_with(
            "host",
            [
                {
                    "bk_host_id": 1,
                    "bk_host_innerip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_agent_alive": True,
                    "error": False,
                }
            ],
        )
