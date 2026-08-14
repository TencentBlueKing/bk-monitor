import threading

import pytest

from monitor_web.performance.resources import SearchHostInfoResource


def test_search_host_info_queries_hosts_and_topology_concurrently(mocker):
    barrier = threading.Barrier(2)
    overlapped_queries = []

    def wait_for_peer(query_name):
        try:
            barrier.wait(timeout=1)
        except threading.BrokenBarrierError:
            return
        overlapped_queries.append(query_name)

    get_hosts = mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_topo_node")
    get_hosts.side_effect = lambda **_kwargs: (wait_for_peer("hosts"), [])[1]

    topo_tree = mocker.Mock()
    topo_tree.convert_to_topo_link.return_value = {}
    get_topo_tree = mocker.patch("monitor_web.performance.resources.api.cmdb.get_topo_tree")
    get_topo_tree.side_effect = lambda **_kwargs: (wait_for_peer("topology"), topo_tree)[1]

    result = SearchHostInfoResource().perform_request({"bk_biz_id": 2})

    assert result == []
    assert set(overlapped_queries) == {"hosts", "topology"}


def test_search_host_info_propagates_host_query_failure(mocker):
    mocker.patch(
        "monitor_web.performance.resources.api.cmdb.get_host_by_topo_node",
        side_effect=RuntimeError("host query failed"),
    )
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_topo_tree")

    with pytest.raises(RuntimeError, match="host query failed"):
        SearchHostInfoResource().perform_request({"bk_biz_id": 2})


def test_search_host_info_propagates_topology_query_failure(mocker):
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_topo_node", return_value=[])
    mocker.patch(
        "monitor_web.performance.resources.api.cmdb.get_topo_tree",
        side_effect=RuntimeError("topology query failed"),
    )

    with pytest.raises(RuntimeError, match="topology query failed"):
        SearchHostInfoResource().perform_request({"bk_biz_id": 2})


def test_search_host_info_returns_ipv6_as_base_host_identity(mocker):
    host = mocker.Mock(
        display_name="host-1",
        bk_host_id=1,
        bk_biz_id=2,
        bk_cloud_id=0,
        bk_cloud_name="default",
        bk_host_innerip="10.0.0.1",
        bk_host_innerip_v6="2001:db8::1",
        bk_host_outerip="1.1.1.1",
        bk_host_outerip_v6="2001:db8::2",
        bk_os_type="1",
        bk_os_name="Linux",
        bk_province_name="",
        bk_host_name="host-1",
        ignore_monitoring=False,
        is_shielding=False,
        bk_module_ids=[],
    )
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_topo_node", return_value=[host])
    topo_tree = mocker.Mock()
    topo_tree.convert_to_topo_link.return_value = {}
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_topo_tree", return_value=topo_tree)

    result = SearchHostInfoResource().perform_request({"bk_biz_id": 2})

    assert result[0]["bk_host_innerip_v6"] == "2001:db8::1"
    assert result[0]["bk_host_outerip_v6"] == "2001:db8::2"
