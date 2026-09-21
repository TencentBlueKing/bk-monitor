import threading
from copy import deepcopy
from types import SimpleNamespace

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


@pytest.mark.parametrize("scope", [{}, {"bk_host_id": 7}, {"bk_obj_id": "module", "bk_inst_id": 8}])
def test_search_host_info_page_uses_cmdb_page_total_without_loading_all_hosts(mocker, scope):
    get_page = mocker.patch(
        "monitor_web.performance.resources.api.cmdb.get_host_page", return_value={"items": [], "total": 1201}
    )
    get_all = mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_topo_node")
    get_by_id = mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id")
    tree = mocker.Mock()
    tree.convert_to_topo_link.return_value = {}
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_topo_tree", return_value=tree)

    result = SearchHostInfoResource().perform_request({"bk_biz_id": 2, "page": 3, "page_size": 50, **scope})

    expected = {"bk_biz_id": 2, "page": 3, "page_size": 50}
    if "bk_host_id" in scope:
        expected["bk_host_id"] = scope["bk_host_id"]
    elif scope:
        expected["topo_nodes"] = {scope["bk_obj_id"]: [scope["bk_inst_id"]]}
    get_page.assert_called_once_with(**expected)
    get_all.assert_not_called()
    get_by_id.assert_not_called()
    assert result == {"items": [], "total": 1201, "page": 3, "page_size": 50}


@pytest.mark.parametrize("pagination", [{"page": 1}, {"page_size": 50}])
def test_search_host_info_rejects_unpaired_pagination(pagination):
    from core.errors.share import InvalidParamsError

    with pytest.raises(InvalidParamsError):
        SearchHostInfoResource.RequestSerializer().validate(pagination)


def test_search_host_info_reuses_module_display_without_changing_module_order():
    from types import SimpleNamespace

    topo_links = {
        f"module|{module_id}": [
            SimpleNamespace(bk_obj_id="module", bk_inst_id=module_id, bk_inst_name=str(module_id), bk_obj_name="Module")
        ]
        for module_id in [8, 9]
    }
    module_cache = {}
    first = SearchHostInfoResource.get_module_info([9, 8], topo_links, module_cache)
    second = SearchHostInfoResource.get_module_info([8, 9], topo_links, module_cache)
    assert [module["bk_inst_id"] for module in first] == [9, 8]
    assert second[0] is first[1]
    assert second[1] is first[0]


def test_search_host_info_page_resolves_related_space_before_cmdb(mocker):
    validate = mocker.patch("monitor_web.performance.resources.validate_bk_biz_id", return_value=2)
    get_page = mocker.patch(
        "monitor_web.performance.resources.api.cmdb.get_host_page", return_value={"items": [], "total": 0}
    )
    tree = mocker.Mock()
    tree.convert_to_topo_link.return_value = {}
    get_tree = mocker.patch("monitor_web.performance.resources.api.cmdb.get_topo_tree", return_value=tree)
    SearchHostInfoResource().request({"bk_biz_id": -100, "page": 1, "page_size": 50})
    validate.assert_called_once_with(-100)
    get_page.assert_called_once_with(bk_biz_id=2, page=1, page_size=50)
    get_tree.assert_called_once_with(bk_biz_id=2, raw=True)


def test_host_page_keeps_host_and_raw_topology_queries_concurrent(mocker):
    barrier = threading.Barrier(2)
    overlapped = []

    def get_page(**_kwargs):
        barrier.wait(timeout=1)
        overlapped.append("hosts")
        return {"items": [], "total": 0}

    def get_tree(**kwargs):
        assert kwargs == {"bk_biz_id": 2, "raw": True}
        barrier.wait(timeout=1)
        overlapped.append("topology")
        return {"bk_obj_id": "biz", "bk_inst_id": 2, "child": []}

    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_page", side_effect=get_page)
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_topo_tree", side_effect=get_tree)
    result = SearchHostInfoResource().perform_request({"bk_biz_id": 2, "page": 1, "page_size": 50})
    assert result["items"] == []
    assert set(overlapped) == {"hosts", "topology"}


def test_nonempty_page_matches_full_list_and_only_requests_its_modules(mocker):
    from api.cmdb.define import TopoTree

    raw_tree = {
        "bk_obj_id": "biz",
        "bk_inst_id": 2,
        "child": [{"bk_obj_id": "module", "bk_inst_id": i, "bk_inst_name": str(i)} for i in [8, 9, 10]],
    }
    original = deepcopy(raw_tree)
    host = SimpleNamespace(
        **{
            key: ""
            for key in [
                "display_name",
                "bk_cloud_name",
                "bk_host_innerip",
                "bk_host_outerip",
                "bk_os_type",
                "bk_os_name",
                "bk_province_name",
                "bk_host_name",
                "ignore_monitoring",
                "is_shielding",
            ]
        },
        bk_host_id=1,
        bk_biz_id=2,
        bk_cloud_id=0,
        bk_module_ids=["9", 8, "9"],
    )
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_topo_node", return_value=[host])
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_page", return_value={"items": [host], "total": 1})
    mocker.patch(
        "monitor_web.performance.resources.api.cmdb.get_topo_tree", side_effect=[TopoTree(deepcopy(raw_tree)), raw_tree]
    )
    baseline = SearchHostInfoResource().perform_request({"bk_biz_id": 2})
    paths = mocker.spy(TopoTree, "module_links_from_raw")
    actual = SearchHostInfoResource().perform_request({"bk_biz_id": 2, "page": 1, "page_size": 50})
    paths.assert_called_once_with(raw_tree, {8, "9"})
    assert actual["items"] == baseline
    assert [module["bk_inst_id"] for module in actual["items"][0]["module"]] == [9, 8, 9]
    assert raw_tree == original


@pytest.mark.parametrize("page,page_size", [(0, 50), (1, 0), (1, 501)])
def test_search_host_info_page_bounds(page, page_size, mocker):
    mocker.patch("monitor_web.performance.resources.validate_bk_biz_id", side_effect=lambda value: value)
    serializer = SearchHostInfoResource.RequestSerializer(data={"bk_biz_id": 2, "page": page, "page_size": page_size})
    assert not serializer.is_valid()


def test_page_rejects_different_business_root_without_changing_legacy_validation():
    from core.errors.share import InvalidParamsError

    params = {"bk_biz_id": 2, "bk_obj_id": "biz", "bk_inst_id": 3}
    assert SearchHostInfoResource.RequestSerializer().validate(params) == params
    with pytest.raises(InvalidParamsError):
        SearchHostInfoResource.RequestSerializer().validate({**params, "page": 1, "page_size": 50})
