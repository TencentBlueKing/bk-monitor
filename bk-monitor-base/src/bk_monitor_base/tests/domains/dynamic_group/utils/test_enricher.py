"""
测试 HostRelationEnricher 主机关联增强器
"""

from unittest.mock import patch

from bk_monitor_base.domains.dynamic_group.utils.enricher import HostRelationEnricher


class TestHostRelationEnricherInit:
    """测试 HostRelationEnricher 初始化"""

    def test_init_with_all_params(self):
        enricher = HostRelationEnricher(
            bk_tenant_id="system",
            bk_obj_id="bk_switch",
            host_related_field="host_connect",
        )

        assert enricher.bk_tenant_id == "system"
        assert enricher.bk_obj_id == "bk_switch"
        assert enricher.host_related_field == "host_connect"

    def test_init_with_empty_host_related_field(self):
        enricher = HostRelationEnricher(
            bk_tenant_id="system",
            bk_obj_id="bk_switch",
            host_related_field="",
        )

        assert enricher.host_related_field == ""


class TestEnrich:
    """测试 enrich 方法"""

    def test_enrich_empty_list(self):
        enricher = HostRelationEnricher("system", "bk_switch", "host_connect")

        assert enricher.enrich([]) == []

    def test_enrich_without_host_related_field(self):
        enricher = HostRelationEnricher("system", "bk_switch", "")
        inst_list = [
            {"bk_inst_id": 1, "bk_inst_name": "实例1"},
            {"bk_inst_id": 2, "bk_inst_name": "实例2"},
        ]

        result = enricher.enrich(inst_list)

        assert len(result) == 2
        assert result[0]["ip_list"] == []
        assert result[1]["ip_list"] == []

    @patch.object(HostRelationEnricher, "_batch_get_host_info")
    @patch.object(HostRelationEnricher, "_fetch_inst_host_mapping")
    def test_enrich_with_host_relation(self, mock_fetch_mapping, mock_get_host_info):
        mock_fetch_mapping.return_value = {1: [101, 102], 2: [103]}
        mock_get_host_info.return_value = {
            101: {"bk_host_id": 101, "ip": "10.0.0.1", "bk_cloud_id": 0, "error": False},
            102: {"bk_host_id": 102, "ip": "10.0.0.2", "bk_cloud_id": 0, "error": True},
            103: {"bk_host_id": 103, "ip": "10.0.0.3", "bk_cloud_id": 0, "error": False},
        }

        enricher = HostRelationEnricher("system", "bk_switch", "host_connect")
        result = enricher.enrich(
            [{"bk_inst_id": 1, "bk_inst_name": "实例1"}, {"bk_inst_id": 2, "bk_inst_name": "实例2"}],
            bk_biz_id=2,
        )

        assert len(result) == 2
        inst1 = next(r for r in result if r["bk_inst_id"] == 1)
        assert len(inst1["ip_list"]) == 2
        assert inst1["ip_list"][1]["error"] is True

    @patch.object(HostRelationEnricher, "_batch_get_host_info")
    @patch.object(HostRelationEnricher, "_fetch_inst_host_mapping")
    def test_enrich_without_biz_id_includes_unmatched(self, mock_fetch_mapping, mock_get_host_info):
        mock_fetch_mapping.return_value = {1: [101]}
        mock_get_host_info.return_value = {101: {"bk_host_id": 101, "ip": "10.0.0.1", "bk_cloud_id": 0, "error": False}}

        enricher = HostRelationEnricher("system", "bk_switch", "host_connect")
        result = enricher.enrich(
            [{"bk_inst_id": 1, "bk_inst_name": "实例1"}, {"bk_inst_id": 2, "bk_inst_name": "实例2"}],
            bk_biz_id=0,
        )

        assert len(result) == 2
        assert next(r for r in result if r["bk_inst_id"] == 2)["ip_list"] == []

    @patch.object(HostRelationEnricher, "_batch_get_host_info")
    @patch.object(HostRelationEnricher, "_fetch_inst_host_mapping")
    def test_enrich_with_biz_id_excludes_unmatched(self, mock_fetch_mapping, mock_get_host_info):
        mock_fetch_mapping.return_value = {1: [101]}
        mock_get_host_info.return_value = {101: {"bk_host_id": 101, "ip": "10.0.0.1", "bk_cloud_id": 0, "error": False}}

        enricher = HostRelationEnricher("system", "bk_switch", "host_connect")
        result = enricher.enrich(
            [{"bk_inst_id": 1, "bk_inst_name": "实例1"}, {"bk_inst_id": 2, "bk_inst_name": "实例2"}],
            bk_biz_id=2,
        )

        assert len(result) == 1
        assert result[0]["bk_inst_id"] == 1

    @patch.object(HostRelationEnricher, "_fetch_inst_host_mapping")
    def test_enrich_no_mapping_found(self, mock_fetch_mapping):
        mock_fetch_mapping.return_value = {}
        enricher = HostRelationEnricher("system", "bk_switch", "host_connect")

        result = enricher.enrich([{"bk_inst_id": 1, "bk_inst_name": "实例1"}], bk_biz_id=0)

        assert len(result) == 1
        assert result[0]["ip_list"] == []


class TestFetchInstHostMapping:
    """测试 _fetch_inst_host_mapping 方法"""

    @patch("bk_monitor_base.domains.dynamic_group.utils.enricher.search_all_inst_relations")
    def test_fetch_forward_association(self, mock_search_relations):
        mock_search_relations.return_value = [
            {"bk_inst_id": "1", "bk_asst_inst_id": "101"},
            {"bk_inst_id": "1", "bk_asst_inst_id": "102"},
        ]

        enricher = HostRelationEnricher("system", "bk_switch", "connect")
        result = enricher._fetch_inst_host_mapping([1])

        assert result == {1: [101, 102]}
        query = mock_search_relations.call_args.kwargs["query"]
        assert query["bk_obj_id"] == "bk_switch"
        assert query["bk_asst_obj_id"] == "host"
        assert query["bk_inst_id"] == ["1"]

    @patch("bk_monitor_base.domains.dynamic_group.utils.enricher.search_all_inst_relations")
    def test_fetch_reverse_association(self, mock_search_relations):
        mock_search_relations.return_value = [{"bk_inst_id": "101", "bk_asst_inst_id": "1"}]

        enricher = HostRelationEnricher("system", "bk_switch", "host_connect")
        result = enricher._fetch_inst_host_mapping([1])

        assert result == {1: [101]}
        query = mock_search_relations.call_args.kwargs["query"]
        assert query["bk_obj_id"] == "host"
        assert query["bk_asst_obj_id"] == "bk_switch"
        assert query["bk_asst_inst_id"] == ["1"]

    @patch("bk_monitor_base.domains.dynamic_group.utils.enricher.search_all_inst_relations")
    def test_fetch_no_associations(self, mock_search_relations):
        mock_search_relations.return_value = []

        enricher = HostRelationEnricher("system", "bk_switch", "connect")

        assert enricher._fetch_inst_host_mapping([1, 2]) == {}

    @patch("bk_monitor_base.domains.dynamic_group.utils.enricher.search_all_inst_relations")
    def test_fetch_api_error(self, mock_search_relations):
        mock_search_relations.side_effect = Exception("ES error")

        enricher = HostRelationEnricher("system", "bk_switch", "connect")

        assert enricher._fetch_inst_host_mapping([1]) == {}

    @patch("bk_monitor_base.domains.dynamic_group.utils.enricher.search_all_inst_relations")
    def test_fetch_filters_by_inst_ids(self, mock_search_relations):
        mock_search_relations.return_value = [
            {"bk_inst_id": "1", "bk_asst_inst_id": "101"},
            {"bk_inst_id": "999", "bk_asst_inst_id": "102"},
        ]

        enricher = HostRelationEnricher("system", "bk_switch", "connect")
        result = enricher._fetch_inst_host_mapping([1])

        assert result == {1: [101]}


class TestBatchGetHostInfo:
    """测试 _batch_get_host_info 方法"""

    @patch("bk_monitor_base.domains.dynamic_group.utils.enricher.search_all_instances")
    def test_batch_get_host_info_success(self, mock_search_instances):
        mock_search_instances.return_value = [
            {
                "bk_host_id": 101,
                "bk_host_innerip": "10.0.0.1",
                "bk_cloud_id": 0,
                "bk_agent_id": "agent-001",
                "bk_biz_id": 2,
                "error": False,
            }
        ]

        enricher = HostRelationEnricher("system", "bk_switch", "connect")
        result = enricher._batch_get_host_info([101])

        assert result[101]["bk_host_id"] == 101
        assert result[101]["ip"] == "10.0.0.1"
        assert result[101]["bk_agent_id"] == "agent-001"
        assert result[101]["bk_biz_id"] == 2
        assert result[101]["error"] is False

    @patch("bk_monitor_base.domains.dynamic_group.utils.enricher.search_all_instances")
    def test_batch_get_host_info_empty_list(self, mock_search_instances):
        enricher = HostRelationEnricher("system", "bk_switch", "connect")

        assert enricher._batch_get_host_info([]) == {}
        mock_search_instances.assert_not_called()

    @patch("bk_monitor_base.domains.dynamic_group.utils.enricher.search_all_instances")
    def test_batch_get_host_info_api_error(self, mock_search_instances):
        mock_search_instances.side_effect = Exception("ES error")
        enricher = HostRelationEnricher("system", "bk_switch", "connect")

        assert enricher._batch_get_host_info([101]) == {}

    @patch("bk_monitor_base.domains.dynamic_group.utils.enricher.search_all_instances")
    def test_batch_get_host_info_missing_fields(self, mock_search_instances):
        mock_search_instances.return_value = [{"bk_host_id": 101}]
        enricher = HostRelationEnricher("system", "bk_switch", "connect")

        result = enricher._batch_get_host_info([101])

        assert result[101]["ip"] == ""
        assert result[101]["bk_cloud_id"] == 0
        assert result[101]["bk_agent_id"] == ""
        assert result[101]["bk_biz_id"] == 0
        assert result[101]["error"] is True


class TestHostRelationEnricherConstants:
    """测试 HostRelationEnricher 常量"""

    def test_host_fields_constant(self):
        assert "bk_host_id" in HostRelationEnricher.HOST_FIELDS
        assert "bk_cloud_id" in HostRelationEnricher.HOST_FIELDS
        assert "bk_host_innerip" in HostRelationEnricher.HOST_FIELDS
        assert "bk_agent_id" in HostRelationEnricher.HOST_FIELDS
        assert "bk_biz_id" in HostRelationEnricher.HOST_FIELDS
