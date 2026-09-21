from copy import deepcopy
import re

import pytest

from api.cmdb import default as cmdb


def host_record(host_id):
    return {
        "host": {"bk_host_id": host_id, "bk_host_innerip": f"host-{host_id}", "bk_cloud_id": 0},
        "topo": [{"bk_set_id": 1, "module": [{"bk_module_id": 8}]}],
    }


def test_host_page_only_constructs_requested_page_and_preserves_cmdb_order(mocker):
    records = [host_record(host_id) for host_id in [101, 102]]
    query = mocker.patch.object(cmdb.client, "list_biz_hosts_topo", return_value={"info": records, "count": 38357})
    all_hosts = mocker.patch.object(cmdb, "get_host_dict_by_biz")
    build_host = mocker.patch.object(cmdb, "Host", side_effect=lambda value: value)
    mocker.patch.object(cmdb.api.cmdb, "search_cloud_area", return_value=[])
    result = cmdb.GetHostPage().perform_request({"bk_biz_id": 2, "fields": [], "page": 3, "page_size": 50})

    assert query.call_args.args[0]["page"] == {"start": 100, "limit": 50}
    assert result["total"] == 38357
    assert [host["bk_host_id"] for host in result["items"]] == [101, 102]
    assert build_host.call_count == 2
    all_hosts.assert_not_called()


@pytest.mark.parametrize("module_ids", [{8, 9}, set()])
def test_host_page_topology_filter_is_applied_before_pagination(mocker, module_ids):
    query = mocker.patch.object(cmdb.client, "list_biz_hosts_topo", return_value={"info": [], "count": 0})
    resolve = mocker.patch.object(cmdb, "_trans_topo_node_to_module_ids", return_value=module_ids)
    scope = {"set": [1]}
    result = cmdb.GetHostPage().perform_request(
        {"bk_biz_id": 2, "fields": [], "page": 1, "page_size": 50, "topo_nodes": deepcopy(scope)}
    )
    resolve.assert_called_once_with(2, scope)
    assert result == {"items": [], "total": 0}
    if module_ids:
        assert query.call_args.args[0]["module_property_filter"]["rules"] == [
            {"field": "bk_module_id", "operator": "in", "value": [8, 9]}
        ]
    else:
        query.assert_not_called()


def test_host_page_single_host_filter_and_empty_address_filter(mocker):
    query = mocker.patch.object(cmdb.client, "list_biz_hosts_topo", return_value={"info": [], "count": 0})
    cmdb.GetHostPage().perform_request({"bk_biz_id": 2, "fields": [], "page": 2, "page_size": 50, "bk_host_id": 7})
    filters = query.call_args.args[0]["host_property_filter"]
    assert filters["rules"][1] == {"field": "bk_host_id", "operator": "equal", "value": 7}
    assert filters["rules"][0] == {
        "condition": "OR",
        "rules": [
            {"field": "bk_host_innerip", "operator": "contains", "value": "[^,]"},
            {"field": "bk_host_innerip_v6", "operator": "contains", "value": "[^,]"},
        ],
    }


def test_host_identities_use_current_cmdb_scope_without_constructing_hosts(mocker):
    hosts = [
        {"bk_host_id": 1, "bk_host_innerip": "host-a", "bk_cloud_id": 0, "bk_module_ids": [8]},
        {"bk_host_id": 2, "bk_host_innerip": "host-b", "bk_cloud_id": 0, "bk_module_ids": [9]},
    ]
    get_raw = mocker.patch.object(cmdb, "get_host_dict_by_biz", return_value=hosts)
    warmed_fields = cmdb.Host.Fields
    build_host = mocker.patch.object(cmdb, "Host")
    build_host.Fields = warmed_fields
    mocker.patch.object(cmdb, "_trans_topo_node_to_module_ids", return_value={8})
    result = cmdb.GetHostIdentities().perform_request({"bk_biz_id": 2, "topo_nodes": {"module": [8]}})
    assert [host["bk_host_id"] for host in result] == [1]
    # cmdb_api_list 预热使用 (bk_biz_id, Host.Fields) 位置参数，字段或调用方式变化都会另建缓存键。
    get_raw.assert_called_once_with(2, warmed_fields)
    build_host.assert_not_called()


def test_host_page_builds_cloud_mapping_once_and_keeps_legacy_helper(mocker):
    class Clouds(list):
        iterations = 0

        def __iter__(self):
            self.iterations += 1
            return super().__iter__()

    clouds = Clouds([{"bk_cloud_id": 0, "bk_cloud_name": "cloud-a"}])
    records = [host_record(host_id) for host_id in range(50)]
    mocker.patch.object(cmdb.client, "list_biz_hosts_topo", return_value={"info": records, "count": 20000})
    mocker.patch.object(cmdb.api.cmdb, "search_cloud_area", return_value=clouds)
    mocker.patch.object(cmdb, "Host", side_effect=lambda value: value)
    result = cmdb.GetHostPage().perform_request({"bk_biz_id": 2, "fields": [], "page": 1, "page_size": 50})
    assert clouds.iterations == 1
    assert all(host["bk_cloud_name"] == "cloud-a" for host in result["items"])
    assert cmdb._host_full_cloud({"bk_cloud_id": 0}, clouds)["bk_cloud_name"] == "cloud-a"
    assert cmdb._host_full_cloud({"bk_cloud_id": 9}, clouds)["bk_cloud_name"] == ""


@pytest.mark.parametrize("address", [None, "", ",", ",,", "host-a", ",host-a,host-b", "host-v6"])
def test_cmdb_address_predicate_matches_existing_host_admission(address):
    assert bool(re.search("[^,]", address or "")) == bool(cmdb.split_inner_host(address))


def test_scoped_identities_keep_cross_node_ip_ambiguity(mocker):
    mocker.patch.object(
        cmdb,
        "get_host_dict_by_biz",
        return_value=[
            {"bk_host_id": 1, "bk_host_innerip": "host-a", "bk_cloud_id": 0, "bk_module_ids": [8]},
            {"bk_host_id": 2, "bk_host_innerip": "host-a", "bk_cloud_id": 0, "bk_module_ids": [9]},
            {"bk_host_id": 3, "bk_host_innerip": "host-a", "bk_cloud_id": 1, "bk_module_ids": [8]},
        ],
    )
    mocker.patch.object(cmdb, "_trans_topo_node_to_module_ids", return_value={8})
    result = cmdb.GetHostIdentities().perform_request({"bk_biz_id": 2, "topo_nodes": {"module": [8]}})
    assert [(host["bk_host_id"], host["has_duplicate_ip"]) for host in result] == [(1, True), (3, False)]


def test_page_and_identities_accept_current_business_root_without_module_filter(mocker):
    query = mocker.patch.object(cmdb.client, "list_biz_hosts_topo", return_value={"info": [], "count": 38357})
    resolve = mocker.patch.object(cmdb, "_trans_topo_node_to_module_ids")
    mocker.patch.object(cmdb, "get_host_dict_by_biz", return_value=[])
    result = cmdb.GetHostPage().perform_request(
        {"bk_biz_id": 2, "fields": [], "page": 1, "page_size": 50, "topo_nodes": {"biz": [2]}}
    )
    assert result["total"] == 38357
    assert "module_property_filter" not in query.call_args.args[0]
    assert cmdb.GetHostIdentities().perform_request({"bk_biz_id": 2, "topo_nodes": {"biz": [2]}}) == []
    resolve.assert_not_called()
