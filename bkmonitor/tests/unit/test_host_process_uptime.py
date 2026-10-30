"""Exercise the production uptime resource without application/database bootstrap."""

import ast
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[2]


def load_function(path, name, namespace, class_name=None):
    source = ast.parse((ROOT / path).read_text())
    if class_name:
        source = next(node for node in source.body if getattr(node, "name", None) == class_name)
    function = next(node for node in source.body if getattr(node, "name", None) == name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


@pytest.fixture
def uptime_resource():
    namespace = {
        "Host": SimpleNamespace,
        "defaultdict": defaultdict,
        "settings": SimpleNamespace(IPV6_SUPPORT_BIZ_LIST=[]),
        "time": SimpleNamespace(time=lambda: 1_700_003_600),
    }
    load_function("bkmonitor/commons/tools.py", "is_ipv6_biz", namespace)
    load_function("packages/monitor_web/cc/resources/cmdb.py", "_build_host_target_filter", namespace)
    get_host = Mock()
    load_data_source = Mock(return_value=lambda **kwargs: SimpleNamespace(**kwargs))
    query_data = Mock()
    query = Mock(return_value=SimpleNamespace(query_data=query_data))
    namespace.update(
        api=SimpleNamespace(cmdb=SimpleNamespace(get_host_by_id=get_host)),
        load_data_source=load_data_source,
        UnifyQuery=query,
        DataSourceLabel=SimpleNamespace(BK_MONITOR_COLLECTOR="bk_monitor"),
        DataTypeLabel=SimpleNamespace(TIME_SERIES="time_series"),
    )
    perform_request = load_function(
        "packages/monitor_web/scene_view/resources/host.py",
        "perform_request",
        namespace,
        class_name="GetHostProcessUptimeResource",
    )
    return SimpleNamespace(
        request=lambda params: perform_request(None, params),
        get_host=get_host,
        load_data_source=load_data_source,
        query=query,
        query_data=query_data,
        settings=namespace["settings"],
    )


def make_host(ip="192.0.2.10", cloud_id=7):
    return SimpleNamespace(bk_host_id=101, bk_host_innerip=ip, bk_host_innerip_v6="2001:db8::10", bk_cloud_id=cloud_id)


def request_params(scope=2, **kwargs):
    return {
        "bk_biz_id": scope,
        "bk_host_id": 101,
        "display_name": "nginx",
        "start_time": 1_700_003_540,
        "end_time": 1_700_003_600,
        **kwargs,
    }


def configure_rows(resource, host):
    """Apply the emitted target conditions to rows with colliding process names."""
    resource.get_host.return_value = [host]
    rows = [
        {
            "bk_host_id": 101,
            "bk_target_ip": host.bk_host_innerip,
            "bk_target_cloud_id": 7,
            "display_name": "nginx",
            "_result_": 7200,
        },
        {
            "bk_host_id": 102,
            "bk_target_ip": host.bk_host_innerip,
            "bk_target_cloud_id": 8,
            "display_name": "nginx",
            "_result_": 300,
        },
        {
            "bk_host_id": 101,
            "bk_target_ip": host.bk_host_innerip,
            "bk_target_cloud_id": 7,
            "display_name": "other",
            "_result_": 60,
        },
    ]
    if not host.bk_host_innerip:
        # IPv6 rows carry the host ID rather than an IPv4 target label.
        for row in rows:
            row.pop("bk_target_ip")

    def matches(row, conditions):
        return all(
            key in row and str(row[key]) in [str(value) for value in values if value is not None]
            for key, value in conditions.items()
            for values in [value if isinstance(value, list) else [value]]
        )

    def query_rows(**_kwargs):
        data_source = resource.query.call_args.kwargs["data_sources"][0]
        conditions = data_source.filter_dict
        targets = conditions.get("targets", [{}])
        common = {key: value for key, value in conditions.items() if key != "targets"}
        return [row for row in rows if matches(row, common) and any(matches(row, target) for target in targets)]

    resource.query_data.side_effect = query_rows


@pytest.mark.parametrize("scope", [2, -2])
def test_ipv4_uptime_keeps_ip_cloud_and_process_filter(uptime_resource, scope):
    host = make_host()
    configure_rows(uptime_resource, host)

    assert uptime_resource.request(request_params(scope)) == {"value": 7200, "unit": "s"}
    uptime_resource.get_host.assert_called_once_with(bk_biz_id=scope, bk_host_ids=[101])
    assert uptime_resource.query.call_args.kwargs["bk_biz_id"] == scope
    source = uptime_resource.query.call_args.kwargs["data_sources"][0]
    assert source.group_by == ["bk_target_ip", "bk_target_cloud_id", "display_name"]
    assert source.table == "system.proc"
    assert source.metrics == [{"field": "uptime", "method": "MAX", "alias": "A"}]


@pytest.mark.parametrize("scope, ipv6_scopes", [(2, [2]), (-2, [-2]), (-2, [2])])
def test_ipv6_uptime_targets_selected_host_even_when_scope_has_no_ipv6_flag(uptime_resource, scope, ipv6_scopes):
    uptime_resource.settings.IPV6_SUPPORT_BIZ_LIST = ipv6_scopes
    configure_rows(uptime_resource, make_host(ip=""))

    assert uptime_resource.request(request_params(scope)) == {"value": 7200, "unit": "s"}
    query = uptime_resource.query.call_args.kwargs
    assert query["bk_biz_id"] == scope
    assert query["data_sources"][0].filter_dict == {"targets": [{"bk_host_id": ["101"]}], "display_name": "nginx"}


def test_ipv6_enabled_scope_uses_host_identity_for_dual_stack_host(uptime_resource):
    uptime_resource.settings.IPV6_SUPPORT_BIZ_LIST = [2]
    configure_rows(uptime_resource, make_host())

    assert uptime_resource.request(request_params()) == {"value": 7200, "unit": "s"}
    assert uptime_resource.query.call_args.kwargs["data_sources"][0].filter_dict == {
        "targets": [{"bk_host_id": ["101"]}],
        "display_name": "nginx",
    }


@pytest.mark.parametrize(
    "times, expected_start",
    [
        ({"start_time": 1_700_000_000, "end_time": 1_700_003_600}, 1_700_003_420_000),
        ({"start_time": 1_700_003_540, "end_time": 1_700_003_600}, 1_700_003_540_000),
        ({}, 1_700_003_420_000),
    ],
)
def test_uptime_keeps_selected_snapshot_window_in_milliseconds(uptime_resource, times, expected_start):
    uptime_resource.get_host.return_value = [make_host()]
    uptime_resource.query_data.return_value = [{"_result_": 0}]
    params = {key: value for key, value in request_params().items() if key not in {"start_time", "end_time"}}

    assert uptime_resource.request({**params, **times}) == {"value": 0, "unit": "s"}
    uptime_resource.query_data.assert_called_once_with(
        start_time=expected_start, end_time=1_700_003_600_000, instant=True
    )


def test_missing_host_skips_uptime_query(uptime_resource):
    uptime_resource.get_host.return_value = []

    assert uptime_resource.request(request_params()) == []
    uptime_resource.load_data_source.assert_not_called()
    uptime_resource.query.assert_not_called()


def test_missing_uptime_keeps_empty_value_and_unit(uptime_resource):
    uptime_resource.get_host.return_value = [make_host()]
    uptime_resource.query_data.return_value = []

    assert uptime_resource.request(request_params()) == {"value": "", "unit": "s"}
