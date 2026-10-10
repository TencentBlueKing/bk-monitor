from copy import deepcopy

import pytest

from api.cmdb import default as cmdb


def record(host_id, ipv4="host-a", ipv6=""):
    return {
        "host": {"bk_host_id": host_id, "bk_host_innerip": ipv4, "bk_host_innerip_v6": ipv6, "bk_cloud_id": 0},
        "topo": [],
    }


def test_candidates_only_query_requested_ids_without_global_cache_or_host_construction(mocker):
    records = [record(1), record(3, ",,", ",host-v6,second"), record(4, ",,", ",,")]
    before = deepcopy(records)
    query = mocker.patch.object(cmdb.client, "list_biz_hosts_topo", return_value={"info": records, "count": 3})
    raw = mocker.patch.object(cmdb, "get_host_dict_by_biz")
    construct = mocker.patch.object(cmdb, "Host")
    batch = mocker.patch.object(cmdb, "batch_request")
    result = cmdb.GetHostIdentities().request({"bk_biz_id": 2, "bk_host_ids": [1, 2, 3, 4, 1]})
    assert [(host["bk_host_id"], host["bk_host_innerip"], host["bk_host_innerip_v6"]) for host in result] == [
        (1, "host-a", ""),
        (3, "", "host-v6"),
    ]
    assert records == before
    params = query.call_args.args[0]
    assert params["bk_biz_id"] == 2
    assert params["page"] == {"start": 0, "limit": 500}
    assert params["host_property_filter"]["rules"] == [{"field": "bk_host_id", "operator": "in", "value": [1, 2, 3, 4]}]
    assert params["fields"] == ["bk_host_id", "bk_host_innerip", "bk_host_innerip_v6", "bk_cloud_id"]
    raw.assert_not_called()
    construct.assert_not_called()
    batch.assert_not_called()


@pytest.mark.parametrize("count,expected_requests", [(0, 0), (500, 1), (501, 2), (1234, 3)])
def test_candidates_cmdb_calls_are_bounded_by_abnormal_set_size(mocker, count, expected_requests):
    query = mocker.patch.object(cmdb.client, "list_biz_hosts_topo", return_value={"info": [], "count": 0})
    assert cmdb.GetHostIdentities().perform_request({"bk_biz_id": 2, "bk_host_ids": list(range(count))}) == []
    assert query.call_count == expected_requests
    assert sum(len(call.args[0]["host_property_filter"]["rules"][0]["value"]) for call in query.call_args_list) == count
    assert all(len(call.args[0]["host_property_filter"]["rules"][0]["value"]) <= 500 for call in query.call_args_list)


def test_candidate_query_handles_provider_page_cap(mocker):
    mocker.patch.object(cmdb.client, "list_biz_hosts_topo", return_value={"info": [record(1)], "count": 2})
    batch = mocker.patch.object(cmdb, "batch_request", return_value=[record(1), record(2)])
    result = cmdb.GetHostIdentities().perform_request({"bk_biz_id": 2, "bk_host_ids": [1, 2]})
    assert [host["bk_host_id"] for host in result] == [1, 2]
    assert batch.call_args.args[1]["host_property_filter"]["rules"][0]["value"] == [1, 2]


@pytest.mark.parametrize("scope", [{"bk_host_id": 1}, {"topo_nodes": {"module": [8]}}])
def test_candidates_cannot_override_a_local_scope(scope):
    serializer = cmdb.GetHostIdentities.RequestSerializer(data={"bk_biz_id": 2, "bk_host_ids": [1], **scope})
    assert not serializer.is_valid()
