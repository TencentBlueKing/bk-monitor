"""使用 NodeMan 原生响应验证业务语义，不伪造 V2 兼容返回。"""

from copy import deepcopy
from unittest.mock import Mock

import pytest

from bk_monitor_base.infras.nodeman_control import v3
from bk_monitor_base.infras.nodeman_control.contracts import PluginOperation


def host(host_id=1, biz=2, area=0, status="running"):
    return {
        "bk_host_id": str(host_id),
        "info": {
            "bk_biz_id": str(biz),
            "bk_networkarea_id": str(area),
            "bk_networkunit_id": "999",
            "bk_host_innerip_list": ["127.0.0.1"],
            "bk_host_innerip_v6_list": ["::1"],
            "advertise_ip": "127.0.0.1",
            "os_type": "linux",
            "bk_host_name": "host",
        },
        "state": {"node_status": status, "node_role": "proxy", "bk_agent_id": "agent-1"},
    }


def page(*items):
    return {"total": len(items), "items": list(items)}


def query(*pairs):
    return {
        "host_list": [
            {
                "host_id": host_id,
                "meta": {
                    "scope_type": "biz",
                    "scope_id": str(biz_id),
                    "bk_biz_id": biz_id,
                },
            }
            for biz_id, host_id in pairs
        ],
        "scope_list": [{"scope_type": "biz", "scope_id": str(biz_id)} for biz_id, _ in pairs],
        "agent_realtime_state": True,
    }


def test_proxy_cloud_zero_and_native_mapping():
    request = Mock(return_value=page(host()))
    result = v3.V3HostQueries(request).proxies("tenant", 0)
    request.assert_called_once_with(
        "list_hosts",
        "tenant",
        {
            "page": {"offset": 0, "limit": 500},
            "exact_include_conditions": {"bk_networkarea_id": [0], "node_role": ["proxy"]},
        },
    )
    assert result[0]["bk_cloud_id"] == 0
    assert result[0]["bk_host_id"] == 1
    assert result[0]["conn_ip"] == "127.0.0.1"
    assert result[0]["status"] == "RUNNING"


@pytest.mark.parametrize(
    "native_field,field,addresses",
    [
        ("bk_host_innerip_list", "inner_ip", ["127.0.0.1", "127.0.0.2"]),
        ("bk_host_innerip_v6_list", "inner_ipv6", ["::1", "::2"]),
        ("bk_host_outerip_list", "outer_ip", ["127.0.0.3", "127.0.0.2"]),
    ],
)
@pytest.mark.parametrize("count", [None, 0, 1, 2])
def test_proxy_address_fields_keep_first_ip(native_field, field, addresses, count):
    """业务单地址字段沿用 V2 的首个 IP 约定，空列表或 null 返回空串。"""
    item = host()
    item["info"][native_field] = addresses[:count] if count is not None else None
    before = deepcopy(item)
    result = v3.V3HostQueries(Mock(return_value=page(item))).proxies("tenant", 0)
    assert result[0][field] == (addresses[0] if count else "")
    assert item == before


def test_business_proxies_include_shared_proxy_from_other_business():
    request = Mock(side_effect=[{"bk_networkarea_id": ["0", "3"]}, page(host(biz=88, area=3))])
    assert v3.V3HostQueries(request).business_proxies("tenant", 2)[0]["bk_biz_id"] == 88
    assert request.call_args_list[0].args[2] == {"exact_include_conditions": {"bk_biz_id": [2]}}
    assert request.call_args_list[1].args[2]["exact_include_conditions"] == {
        "bk_networkarea_id": [0, 3],
        "node_role": ["proxy"],
    }


def test_empty_business_never_queries_all_hosts():
    request = Mock(return_value={"bk_networkarea_id": []})
    assert v3.V3HostQueries(request).business_proxies("tenant", 2) == []
    assert request.call_count == 1


def test_pagination_reads_all_results():
    request = Mock(
        side_effect=[
            {"total": "2", "items": [host()]},
            {"total": "2", "items": [host(2)]},
        ]
    )
    assert len(v3.V3HostQueries(request).proxies("tenant", 0)) == 2
    assert request.call_args_list[1].args[2]["page"]["offset"] == 1


def test_incomplete_page_and_network_failure_do_not_return_partial_success():
    for failure in ({"total": 2, "items": []}, RuntimeError("network")):
        request = Mock(side_effect=[{"total": 2, "items": [host()]}, failure])
        with pytest.raises((ValueError, RuntimeError)):
            v3.V3HostQueries(request).proxies("tenant", 0)


@pytest.mark.parametrize("status,alive", [("running", 1), ("terminated", 0), ("unknown", 0), (None, 0)])
def test_details_trusts_returned_state_without_sync(status, alive):
    request = Mock(
        side_effect=[
            page(host(status=status)),
            page({"bk_biz_id": "2", "bk_biz_name": "Business"}),
            page({"bk_networkarea_id": "0", "bk_networkarea_name": "Default"}),
        ]
    )
    params = query((2, 1))
    before = deepcopy(params)
    result = v3.V3HostQueries(request).details("tenant", params)
    assert params == before
    assert result[0]["alive"] == result[0]["bk_agent_alive"] == alive
    assert result[0]["agent_id"] == result[0]["bk_agent_id"] == "agent-1"
    assert result[0]["cloud_area"] == {"id": 0, "name": "Default"}
    assert result[0]["biz"] == {"id": 2, "name": "Business"}
    assert result[0]["meta"] == params["host_list"][0]["meta"]
    assert [call.args[0] for call in request.call_args_list] == [
        "list_hosts",
        "list_businesses",
        "list_network_areas",
    ]
    assert "agent_realtime_state" not in request.call_args_list[0].args[2]


def test_host_and_business_pairs_are_not_cartesian():
    request = Mock(
        side_effect=[
            page(host(1, 2), host(1, 3), host(9, 2)),
            page(host(2, 3)),
            page({"bk_biz_id": 2}, {"bk_biz_id": 3}),
            page({"bk_networkarea_id": 0}),
        ]
    )
    result = v3.V3HostQueries(request).details("tenant", query((2, 1), (3, 2)))
    assert [(item["bk_biz_id"], item["host_id"]) for item in result] == [(2, 1), (3, 2)]
    assert request.call_args_list[0].args[2]["exact_include_conditions"] == {"bk_biz_id": [2], "bk_host_id": [1]}
    assert request.call_args_list[1].args[2]["exact_include_conditions"] == {"bk_biz_id": [3], "bk_host_id": [2]}


def test_empty_or_out_of_scope_selection_never_queries_all_hosts():
    request = Mock()
    assert v3.V3HostQueries(request).details("tenant", query()) == []
    params = query((2, 1))
    params["scope_list"] = [{"scope_type": "biz", "scope_id": "3"}]
    assert v3.V3HostQueries(request).details("tenant", params) == []
    request.assert_not_called()


def test_install_translates_intent_and_deduplicates_hosts():
    request = Mock(return_value={"workflow_id": "wf-1"})
    assert v3.V3OfficialPlugins(request).install("tenant", "bkmonitorbeat", "1.2", [1, 1, 2]) == PluginOperation("wf-1")
    request.assert_called_once_with(
        "install_plugin",
        "tenant",
        {
            "plugin": [
                {"bk_host_id": 1, "plugin_name": "bkmonitorbeat", "version": "1.2"},
                {"bk_host_id": 2, "plugin_name": "bkmonitorbeat", "version": "1.2"},
            ]
        },
    )


@pytest.mark.parametrize("response", [{}, {"workflow_id": ""}, RuntimeError("timeout")])
def test_uncertain_write_result_never_retries(response):
    request = Mock()
    if isinstance(response, Exception):
        request.side_effect = response
    else:
        request.return_value = response
    with pytest.raises((ValueError, RuntimeError)):
        v3.V3OfficialPlugins(request).install("tenant", "bkmonitorbeat", "1.2", [1])
    request.assert_called_once()


def install_host(host_id=1, generation=2, arch="x86_64"):
    """目标平台直接使用 V3 返回值，不借用本机平台。"""
    result = host(host_id)
    result["info"]["cpu_arch"] = arch
    result["state"]["node_generation"] = str(generation)
    return result


def release(version="1.2", generation=2, arch="x86_64", **fields):
    """原生包列表的 release 嵌套结构。"""
    return {
        "release": {
            "name": "collector-package",
            "generation": str(generation),
            "os_type": "linux",
            "cpu_arch": arch,
            "version": version,
            "enabled": True,
            "as_default": True,
            **fields,
        }
    }


@pytest.mark.parametrize("version", ["latest", ""])
def test_latest_resolves_default_for_each_platform_and_generation(version):
    """逻辑插件名与包名不同；同平台只查一次，不把最高版本当默认版。"""
    request = Mock(
        side_effect=[
            page({"name": "collector", "pkg_name": "collector-package"}),
            page(install_host(1), install_host(2), install_host(3, arch="aarch64"), install_host(4, generation=3)),
            page(release(), release("99.0", as_default=False)),
            page(release("2.0", arch="aarch64")),
            page(release("3.0", generation=3)),
            {"workflow_id": "wf-1"},
        ]
    )
    assert v3.V3OfficialPlugins(request).install("tenant", "collector", version, [1, 2, 3, 4]) == PluginOperation(
        "wf-1"
    )
    calls = request.call_args_list
    assert [call.args[0] for call in calls] == [
        "list_plugins",
        "list_hosts",
        "list_plugin_releases",
        "list_plugin_releases",
        "list_plugin_releases",
        "install_plugin",
    ]
    assert calls[2].args[2] == {
        "page": {"offset": 0, "limit": 500},
        "generation": 2,
        "exact_include_conditions": {
            "name": ["collector-package"],
            "platform": [{"os_type": "linux", "cpu_arch": "x86_64"}],
            "as_default": [True],
            "enabled": [True],
        },
    }
    assert calls[-1].args[2] == {
        "plugin": [
            {"bk_host_id": 1, "plugin_name": "collector", "version": "1.2"},
            {"bk_host_id": 2, "plugin_name": "collector", "version": "1.2"},
            {"bk_host_id": 3, "plugin_name": "collector", "version": "2.0"},
            {"bk_host_id": 4, "plugin_name": "collector", "version": "3.0"},
        ]
    }
    assert all(call.args[1] == "tenant" for call in calls)


@pytest.mark.parametrize(
    "packages",
    [
        page(),
        page(release(enabled=False)),
        page(release(as_default=False)),
        page(release(), release("2.0")),
        page(release(arch="aarch64")),
        page(release(generation=3)),
    ],
)
def test_missing_disabled_or_ambiguous_default_never_submits_install(packages):
    """默认包不满足唯一可用条件时，不能降级为任选版本或先部署部分主机。"""
    request = Mock(
        side_effect=[
            page({"name": "collector", "pkg_name": "collector-package"}),
            page(install_host()),
            packages,
        ]
    )
    with pytest.raises(ValueError, match="unique enabled default"):
        v3.V3OfficialPlugins(request).install("tenant", "collector", "latest", [1])
    assert all(call.args[0] != "install_plugin" for call in request.call_args_list)


@pytest.mark.parametrize("hosts", [page(), page(host()), page(install_host(2))])
def test_unresolved_target_platform_never_submits_install(hosts):
    """主机缺失或平台未同步时不把请求放宽为全部主机。"""
    request = Mock(side_effect=[page({"name": "collector", "pkg_name": "collector-package"}), hosts])
    with pytest.raises(ValueError):
        v3.V3OfficialPlugins(request).install("tenant", "collector", "latest", [1])
    assert all(call.args[0] not in ("install_plugin", "list_plugin_releases") for call in request.call_args_list)


def test_later_platform_lookup_failure_does_not_partially_install():
    """先完整解析所有主机，再一次提交；第二组读取失败时不产生写请求。"""
    request = Mock(
        side_effect=[
            page({"name": "collector", "pkg_name": "collector-package"}),
            page(install_host(), install_host(2, arch="aarch64")),
            page(release()),
            RuntimeError("lookup failed"),
        ]
    )
    with pytest.raises(RuntimeError, match="lookup failed"):
        v3.V3OfficialPlugins(request).install("tenant", "collector", "latest", [1, 2])
    assert all(call.args[0] != "install_plugin" for call in request.call_args_list)


def test_empty_install_target_does_not_query_or_write():
    """空目标不会退化为无过滤查询。"""
    request = Mock()
    with pytest.raises(ValueError, match="No target"):
        v3.V3OfficialPlugins(request).install("tenant", "collector", "latest", [])
    request.assert_not_called()


def test_default_lookup_reads_all_pages():
    """元数据分页不能静默漏掉后续的默认版本。"""
    request = Mock(
        side_effect=[
            page({"name": "collector", "pkg_name": "collector-package"}),
            page(install_host()),
            {"total": 2, "items": [release("99.0", as_default=False)]},
            {"total": 2, "items": [release()]},
            {"workflow_id": "wf-1"},
        ]
    )
    v3.V3OfficialPlugins(request).install("tenant", "collector", "latest", [1])
    assert request.call_args_list[3].args[2]["page"]["offset"] == 1
    assert request.call_args_list[-1].args[2]["plugin"][0]["version"] == "1.2"
