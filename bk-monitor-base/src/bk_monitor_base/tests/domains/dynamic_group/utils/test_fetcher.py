"""
测试成员获取器模块
"""

from unittest.mock import MagicMock, patch

import pytest

from bk_monitor_base.domains.dynamic_group.utils.fetcher import (
    BizMemberFetcher,
    GenericInstMemberFetcher,
    HostMemberFetcher,
    MemberFetcherRegistry,
    get_member_fetcher,
    register_member_fetcher,
)


class TestHostMemberFetcher:
    """测试 HostMemberFetcher"""

    @patch("bk_monitor_base.domains.dynamic_group.utils.condition.ConditionConverter.build_cmdb_instance_dsl")
    @patch("bk_monitor_base.domains.dynamic_group.utils.fetcher.search_instances_by_dsl")
    def test_fetch_hosts(self, mock_search_instances, mock_build_dsl):
        mock_build_dsl.return_value = {"match_all": {}}
        mock_search_instances.return_value = (
            1,
            [
                {
                    "bk_host_id": 1,
                    "bk_host_innerip": "10.0.0.1",
                    "bk_biz_id": 2,
                    "bk_cloud_id": 0,
                    "bk_agent_id": "agent-001",
                    "error": False,
                }
            ],
        )

        count, members = HostMemberFetcher().fetch(
            bk_tenant_id="system",
            bk_biz_id=2,
            condition={"condition": "AND", "rules": []},
            page={"start": 0, "limit": 20},
        )

        assert count == 1
        assert members[0]["bk_inst_id"] == 1
        assert members[0]["ip_list"][0]["error"] is False

    @patch("bk_monitor_base.domains.dynamic_group.utils.condition.ConditionConverter.build_cmdb_instance_dsl")
    @patch("bk_monitor_base.domains.dynamic_group.utils.fetcher.search_all_instances_by_dsl")
    def test_fetch_all_hosts(self, mock_search_all_instances, mock_build_dsl):
        mock_build_dsl.return_value = {"match_all": {}}
        mock_search_all_instances.return_value = [
            {
                "bk_host_id": 1,
                "bk_host_innerip": "10.0.0.1",
                "bk_biz_id": 0,
                "bk_cloud_id": 0,
                "error": True,
            }
        ]

        members = HostMemberFetcher().fetch_all(
            bk_tenant_id="system",
            bk_biz_id=0,
            condition={"condition": "AND", "rules": []},
        )

        assert len(members) == 1
        assert members[0]["ip_list"][0]["error"] is True

    def test_build_query_fields_with_none(self):
        assert HostMemberFetcher()._build_query_fields(None, {"condition": "AND", "rules": []}) is None

    def test_build_query_fields_with_fields(self):
        result = HostMemberFetcher()._build_query_fields(
            ["custom_field"],
            {"condition": "AND", "rules": [{"field": "status"}]},
        )

        assert "custom_field" in result
        assert "bk_host_id" in result
        assert "status" in result


class TestBizMemberFetcher:
    """测试 BizMemberFetcher"""

    @patch("bk_monitor_base.domains.dynamic_group.utils.condition.ConditionConverter.build_cmdb_instance_dsl")
    @patch("bk_monitor_base.domains.dynamic_group.utils.fetcher.search_instances_by_dsl")
    def test_fetch_business(self, mock_search_instances, mock_build_dsl):
        mock_build_dsl.return_value = {"match_all": {}}
        mock_search_instances.return_value = (1, [{"bk_biz_id": 2, "bk_biz_name": "测试业务"}])

        count, members = BizMemberFetcher().fetch(
            bk_tenant_id="system",
            bk_biz_id=0,
            condition={"condition": "AND", "rules": []},
            page={"start": 0, "limit": 20},
        )

        assert count == 1
        assert members[0]["bk_biz_id"] == 2

    @patch("bk_monitor_base.domains.dynamic_group.utils.condition.ConditionConverter.build_cmdb_instance_dsl")
    @patch("bk_monitor_base.domains.dynamic_group.utils.fetcher.search_all_instances_by_dsl")
    def test_fetch_all_business(self, mock_search_all_instances, mock_build_dsl):
        mock_build_dsl.return_value = {"match_all": {}}
        mock_search_all_instances.return_value = [{"bk_biz_id": 2, "bk_biz_name": "测试业务"}]

        members = BizMemberFetcher().fetch_all(
            bk_tenant_id="system",
            bk_biz_id=0,
            condition={"condition": "AND", "rules": []},
        )

        assert len(members) == 1

    def test_build_query_fields_with_none(self):
        assert BizMemberFetcher()._build_query_fields(None) is None

    def test_build_query_fields_with_fields(self):
        result = BizMemberFetcher()._build_query_fields(["custom_field"])

        assert "custom_field" in result
        assert "bk_biz_id" in result
        assert "bk_biz_name" in result


class TestGenericInstMemberFetcher:
    """测试 GenericInstMemberFetcher"""

    @patch("bk_monitor_base.domains.dynamic_group.utils.condition.ConditionConverter.build_cmdb_instance_dsl")
    @patch("bk_monitor_base.domains.dynamic_group.utils.fetcher.search_instances_by_dsl")
    def test_fetch_instances(self, mock_search_instances, mock_build_dsl):
        mock_build_dsl.return_value = {"match_all": {}}
        mock_search_instances.return_value = (1, [{"bk_inst_id": 1, "bk_inst_name": "实例1"}])

        count, members = GenericInstMemberFetcher(bk_obj_id="bk_switch").fetch(
            bk_tenant_id="system",
            bk_biz_id=2,
            condition={"condition": "AND", "rules": []},
            page={"start": 0, "limit": 20},
        )

        assert count == 1
        assert members[0]["bk_inst_id"] == 1
        assert members[0]["ip_list"] == []

    @patch("bk_monitor_base.domains.dynamic_group.utils.enricher.HostRelationEnricher")
    @patch("bk_monitor_base.domains.dynamic_group.utils.condition.ConditionConverter.build_cmdb_instance_dsl")
    @patch("bk_monitor_base.domains.dynamic_group.utils.fetcher.search_instances_by_dsl")
    def test_fetch_instances_with_host_relation(self, mock_search_instances, mock_build_dsl, mock_enricher_class):
        mock_build_dsl.return_value = {"match_all": {}}
        mock_search_instances.return_value = (1, [{"bk_inst_id": 1, "bk_inst_name": "实例1"}])
        mock_enricher = MagicMock()
        mock_enricher.enrich.return_value = [
            {"bk_inst_id": 1, "bk_inst_name": "实例1", "ip_list": [{"ip": "10.0.0.1", "error": False}]}
        ]
        mock_enricher_class.return_value = mock_enricher

        count, members = GenericInstMemberFetcher(bk_obj_id="bk_switch", host_related_field="host_field").fetch(
            bk_tenant_id="system",
            bk_biz_id=2,
            condition={"condition": "AND", "rules": []},
            page={"start": 0, "limit": 20},
        )

        assert count == 1
        assert members[0]["ip_list"][0]["error"] is False
        mock_enricher.enrich.assert_called_once()

    @patch("bk_monitor_base.domains.dynamic_group.utils.condition.ConditionConverter.build_cmdb_instance_dsl")
    @patch("bk_monitor_base.domains.dynamic_group.utils.fetcher.search_all_instances_by_dsl")
    def test_fetch_all_instances(self, mock_search_all_instances, mock_build_dsl):
        mock_build_dsl.return_value = {"match_all": {}}
        mock_search_all_instances.return_value = [{"bk_inst_id": 1, "bk_inst_name": "实例1"}]

        members = GenericInstMemberFetcher(bk_obj_id="bk_switch").fetch_all(
            bk_tenant_id="system",
            bk_biz_id=2,
            condition={"condition": "AND", "rules": []},
        )

        assert len(members) == 1
        assert members[0]["ip_list"] == []

    def test_build_query_fields_with_none(self):
        assert GenericInstMemberFetcher(bk_obj_id="bk_switch")._build_query_fields(None) == {
            "bk_switch": ["bk_inst_id", "bk_inst_name"]
        }

    def test_build_query_fields_with_fields(self):
        result = GenericInstMemberFetcher(bk_obj_id="bk_switch")._build_query_fields(["custom_field"])

        assert "bk_switch" in result
        assert "custom_field" in result["bk_switch"]
        assert "bk_inst_id" in result["bk_switch"]
        assert "bk_inst_name" in result["bk_switch"]


class TestMemberFetcherRegistry:
    """测试 MemberFetcherRegistry"""

    def test_register_and_get(self):
        registry = MemberFetcherRegistry()
        mock_fetcher = MagicMock()

        registry.register("custom-model", mock_fetcher)

        assert registry.get("custom-model") == mock_fetcher

    def test_get_nonexistent(self):
        assert MemberFetcherRegistry().get("nonexistent") is None

    @patch("bk_monitor_base.domains.dynamic_group.utils.fetcher.list_object_models")
    def test_get_or_create_generic(self, mock_list_models):
        mock_model = MagicMock()
        mock_model.bk_cmdb_obj_id = "custom_obj"
        mock_model.host_related_field = ""
        mock_list_models.return_value = [mock_model]

        fetcher = MemberFetcherRegistry().get_or_create_generic("custom-model")

        assert isinstance(fetcher, GenericInstMemberFetcher)
        assert fetcher.bk_obj_id == "custom_obj"

    @patch("bk_monitor_base.domains.dynamic_group.utils.fetcher.list_object_models")
    def test_get_or_create_generic_caches_result(self, mock_list_models):
        mock_model = MagicMock()
        mock_model.bk_cmdb_obj_id = "custom_obj"
        mock_model.host_related_field = ""
        mock_list_models.return_value = [mock_model]

        registry = MemberFetcherRegistry()
        fetcher1 = registry.get_or_create_generic("custom-model")
        fetcher2 = registry.get_or_create_generic("custom-model")

        assert fetcher1 is fetcher2
        assert mock_list_models.call_count == 1

    @patch("bk_monitor_base.domains.dynamic_group.utils.fetcher.list_object_models")
    def test_get_or_create_generic_raises_on_error(self, mock_list_models):
        mock_list_models.side_effect = Exception("API error")

        with pytest.raises(ValueError, match="无法获取对象模型"):
            MemberFetcherRegistry().get_or_create_generic("nonexistent-model")


class TestGetMemberFetcher:
    """测试 get_member_fetcher 函数"""

    def test_get_host_fetcher(self):
        assert isinstance(get_member_fetcher("cw-Host"), HostMemberFetcher)

    def test_get_biz_fetcher(self):
        assert isinstance(get_member_fetcher("cw-biz"), BizMemberFetcher)


class TestRegisterMemberFetcher:
    """测试 register_member_fetcher 函数"""

    def test_register_custom_fetcher(self):
        mock_fetcher = MagicMock()
        register_member_fetcher("test-custom-model", mock_fetcher)

        from bk_monitor_base.domains.dynamic_group.utils.fetcher import _registry

        assert _registry.get("test-custom-model") == mock_fetcher
