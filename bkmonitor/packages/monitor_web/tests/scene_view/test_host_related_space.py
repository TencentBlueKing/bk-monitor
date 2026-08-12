from types import SimpleNamespace

from monitor_web.performance.resources import SearchHostInfoResource
from monitor_web.scene_view.resources.host import GetHostProcessListResource


def test_process_list_uses_related_bkcc_biz_for_cmdb_and_metrics(mocker):
    related_biz_id = 2
    host = SimpleNamespace(bk_host_id=1, ip="host.example")
    validate_biz = mocker.patch("monitor_web.scene_view.resources.host.validate_bk_biz_id", return_value=related_biz_id)
    get_host = mocker.patch("monitor_web.scene_view.resources.host.api.cmdb.get_host_by_id", return_value=[host])
    get_process_info = mocker.patch(
        "monitor_web.scene_view.resources.host.resource.cc.get_process_info", return_value={host.bk_host_id: []}
    )
    metric_queries = [
        mocker.patch(f"monitor_web.scene_view.resources.host.resource.cc.{name}", return_value={})
        for name in (
            "get_process_port_health",
            "get_process_runtime_metrics",
            "get_process_uptime",
            "get_process_instance_count",
        )
    ]

    result = GetHostProcessListResource().request({"bk_biz_id": -100, "bk_host_id": host.bk_host_id})

    assert result == []
    validate_biz.assert_called_once_with(-100)
    get_host.assert_called_once_with(bk_host_ids=[host.bk_host_id], bk_biz_id=related_biz_id)
    assert get_process_info.call_args.args[0] == related_biz_id
    for query in metric_queries:
        assert query.call_args.kwargs["bk_biz_id"] == related_biz_id


def test_search_host_info_uses_related_bkcc_biz_for_all_cmdb_queries(mocker):
    related_biz_id = 2
    validate_biz = mocker.patch("monitor_web.performance.resources.validate_bk_biz_id", return_value=related_biz_id)
    get_hosts = mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_topo_node", return_value=[])
    topo_tree = mocker.Mock()
    topo_tree.convert_to_topo_link.return_value = {}
    get_topo_tree = mocker.patch("monitor_web.performance.resources.api.cmdb.get_topo_tree", return_value=topo_tree)

    result = SearchHostInfoResource().request({"bk_biz_id": -100})

    assert result == []
    validate_biz.assert_called_once_with(-100)
    get_hosts.assert_called_once_with(bk_biz_id=related_biz_id)
    get_topo_tree.assert_called_once_with(bk_biz_id=related_biz_id)
