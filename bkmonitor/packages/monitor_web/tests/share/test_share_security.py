from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.urls import resolve

from bkmonitor.iam import ActionEnum
from bkmonitor.models import ApiAuthToken
from bkmonitor.share.api_auth_resource import ApiAuthResource
from bkmonitor.share.handler import HostApiAuthChecker
from bkmonitor.share.utils import check_api_permission
from core.errors.share import InvalidParamsError, ParamsPermissionDeniedError, SearchLockedError, TokenValidatedError
from monitor_web.commons.cc.resources.frontend_resources import GetTopoTree
from monitor_web.grafana.resources.unify_query import GraphUnifyQueryResource
from monitor_web.performance.resources import SearchHostInfoResource, SearchHostMetricResource
from monitor_web.scene_view.resources.host import GetHostProcessListResource
from monitor_web.share.resources import CreateShareTokenResource, UpdateShareTokenResource


def make_view(module, name, action):
    view_class = type(name, (), {})
    view_class.__module__ = module
    return SimpleNamespace(cls=view_class, actions={"post": action})


def make_host_token(scope):
    return ApiAuthToken(
        type="host",
        namespaces=["biz#2"],
        params={
            "lock_search": False,
            "start_time": None,
            "end_time": None,
            "default_time_range": [],
            "data": {"scope": scope},
        },
    )


def make_host(host_id=100, ip="10.0.0.1", cloud_id=0):
    return SimpleNamespace(
        bk_host_id=host_id,
        bk_host_innerip=ip,
        bk_host_innerip_v6="",
        bk_cloud_id=cloud_id,
        ip=ip,
    )


def mock_host_scope(mocker, hosts=None):
    hosts = hosts or [make_host()]
    mocker.patch("bkmonitor.share.handler.api.cmdb.get_host_by_id", return_value=hosts)
    mocker.patch("bkmonitor.share.handler.api.cmdb.get_host_by_topo_node", return_value=hosts)
    return hosts


def mock_host_request(mocker, action):
    request = SimpleNamespace(
        token="share-token",
        method="POST",
        resolver_match=resolve(f"/rest/v2/scene_view/{action}/"),
    )
    mocker.patch("bkmonitor.share.handler.get_request", return_value=request)
    return request


def make_unify_query_request(target):
    return {
        "bk_biz_id": 2,
        "query_configs": [
            {
                "data_source_label": "bk_monitor",
                "data_type_label": "time_series",
                "table": "system.cpu",
                "metrics": [{"field": "cpu_usage"}],
                "filter_dict": {"targets": [target]},
            }
        ],
        "expression": "A",
        "start_time": 100,
        "end_time": 200,
    }


def mock_unify_query_host_token(mocker, is_ipv6):
    token = make_host_token({"version": 1, "target_type": "host", "bk_host_id": 100})
    request = SimpleNamespace(token="share-token")
    mocker.patch("bkmonitor.share.api_auth_resource.get_request", return_value=request)
    mocker.patch("bkmonitor.share.handler.get_request", return_value=request)
    mocker.patch("bkmonitor.share.utils.get_request_tenant_id", return_value="system")
    mocker.patch.object(ApiAuthToken.objects, "get", return_value=token)
    mock_host_scope(mocker)
    mocker.patch(
        "bkmonitor.share.handler.MetricListCache.objects.filter",
        return_value=Mock(values_list=Mock(return_value=[("system.cpu", "cpu_usage")])),
    )
    mocker.patch("monitor_web.grafana.resources.unify_query.is_ipv6_biz", return_value=is_ipv6)


@pytest.mark.parametrize("token_type", ["host", "scene", "scene_collect"])
@pytest.mark.parametrize(
    "action",
    ["update_scene_view", "delete_scene_view", "bulk_update_scene_view_order_and_name"],
)
def test_scene_share_tokens_cannot_mutate_scene_views(token_type, action):
    token = ApiAuthToken(type=token_type)
    view = make_view("monitor_web.scene_view.views", "SceneViewViewSet", action)

    assert token.is_allowed_view(view) is False


@pytest.mark.parametrize("token_type", ["host", "scene", "scene_custom_metric"])
@pytest.mark.parametrize(
    "action",
    ["create_share_token", "update_share_token", "delete_share_token", "get_share_token_list"],
)
def test_scene_share_tokens_cannot_manage_share_tokens(token_type, action):
    token = ApiAuthToken(type=token_type)
    view = make_view("monitor_web.share.views", "ShareViewSet", action)

    assert token.is_allowed_view(view) is False


def test_host_share_token_can_still_call_post_read_endpoint():
    token = ApiAuthToken(type="host")
    view = make_view("monitor_web.scene_view.views", "SceneViewViewSet", "get_host_process_list")

    assert token.is_allowed_view(view) is True


def test_api_token_is_not_affected_by_scene_share_readonly_policy():
    token = ApiAuthToken(type="api")
    view = make_view("monitor_web.scene_view.views", "SceneViewViewSet", "update_scene_view")

    assert token.is_allowed_view(view) is True


@pytest.mark.parametrize(
    ("module", "name", "action"),
    [
        ("monitor_web.scene_view.views", "SceneViewViewSet", "get_host_process_list"),
        ("monitor_web.ai_whatever.views", "AISettingsViewSet", "update_ai_settings"),
    ],
)
def test_unregistered_scene_host_token_cannot_access_any_view(module, name, action):
    token = ApiAuthToken(type="scene_host")

    assert token.is_allowed_view(make_view(module, name, action)) is False


def test_unregistered_scene_host_token_does_not_enter_host_checker(mocker):
    token = ApiAuthToken(type="scene_host", token="share-token")
    mocker.patch.object(ApiAuthToken.objects, "get", return_value=token)
    host_checker = mocker.patch("bkmonitor.share.utils.checker_mapping", {"host": Mock()})["host"]
    request = SimpleNamespace(token="share-token")

    with pytest.raises(TokenValidatedError):
        check_api_permission(request, {})

    host_checker.assert_not_called()


@pytest.mark.parametrize("action", ["create", "update", "partial_update", "destroy"])
def test_scene_share_token_cannot_call_standard_mutation(action):
    token = ApiAuthToken(type="host")
    view = make_view("monitor_api.views", "UserConfigViewSet", action)

    assert token.is_allowed_view(view) is False


def test_scene_share_token_can_call_standard_read_action():
    token = ApiAuthToken(type="scene")
    view = make_view("monitor_api.views", "UserConfigViewSet", "list")

    assert token.is_allowed_view(view) is True


@pytest.mark.parametrize(
    ("module", "name", "action"),
    [
        ("monitor_web.commons.cc.views", "GetTopoTree", "create"),
        ("monitor_web.performance.views", "SearchHostInfoViewSet", "create"),
        ("monitor_web.performance.views", "SearchHostMetricViewSet", "create"),
        ("monitor_web.scene_view.views", "SceneViewViewSet", "get_host_or_topo_node_detail"),
        ("monitor_web.scene_view.views", "SceneViewViewSet", "get_host_process_port_status"),
        ("monitor_web.scene_view.views", "SceneViewViewSet", "get_host_process_list"),
        ("monitor_web.scene_view.views", "SceneViewViewSet", "get_host_process_uptime"),
        ("monitor_web.scene_view.views", "SceneViewViewSet", "get_host_views_panels"),
        ("monitor_web.scene_view.views", "SceneViewViewSet", "get_host_metric_group_panel_order"),
        ("monitor_web.scene_view.views", "SceneViewViewSet", "get_process_views_panels"),
        ("monitor_web.scene_view.views", "SceneViewViewSet", "get_process_metric_group_panel_order"),
        ("monitor_web.grafana.views", "GrafanaViewSet", "time_series/unify_query"),
    ],
)
def test_scoped_host_share_token_only_allows_new_host_read_routes(module, name, action):
    token = make_host_token({"version": 1, "target_type": "host", "bk_host_id": 100})

    assert token.is_allowed_view(make_view(module, name, action)) is True


@pytest.mark.parametrize(
    ("module", "name", "action"),
    [
        ("monitor_web.scene_view.views", "SceneViewViewSet", "get_host_info"),
        ("monitor_web.scene_view.views", "SceneViewViewSet", "get_strategy_and_event_count"),
        ("monitor_web.performance.views", "HostListViewSet", "list"),
        ("monitor_web.commons.cc.views", "GetHostInstanceByIpViewSet", "create"),
        ("monitor_web.grafana.views", "GrafanaViewSet", "time_series/unify_query_raw"),
    ],
)
def test_scoped_host_share_token_denies_unlisted_read_routes(module, name, action):
    token = make_host_token({"version": 1, "target_type": "host", "bk_host_id": 100})

    assert token.is_allowed_view(make_view(module, name, action)) is False


@pytest.mark.parametrize(
    "scope",
    [
        {},
        {"version": 1, "target_type": "host"},
        {"version": 1, "target_type": "topo", "bk_obj_id": "module"},
        {"version": 2, "target_type": "host", "bk_host_id": 100},
        {"version": 1, "target_type": "unknown", "bk_host_id": 100},
    ],
)
def test_host_scope_requires_version_and_target_keys(scope):
    with pytest.raises(InvalidParamsError):
        HostApiAuthChecker(make_host_token(scope))


@pytest.mark.parametrize(
    ("scope", "request_data"),
    [
        ({"version": 1, "target_type": "host", "bk_host_id": 100}, {}),
        ({"version": 1, "target_type": "host", "bk_host_id": 100}, {"bk_host_id": 101}),
        (
            {"version": 1, "target_type": "topo", "bk_obj_id": "module", "bk_inst_id": 10},
            {"bk_obj_id": "module"},
        ),
        (
            {"version": 1, "target_type": "topo", "bk_obj_id": "module", "bk_inst_id": 10},
            {"bk_obj_id": "module", "bk_inst_id": 11},
        ),
        (
            {"version": 1, "target_type": "topo", "bk_obj_id": "module", "bk_inst_id": 10},
            {"bk_obj_id": "module", "bk_inst_id": 10, "bk_host_id": 101},
        ),
    ],
)
def test_host_scope_request_target_is_required_and_exact(mocker, scope, request_data):
    mock_host_scope(mocker)
    checker = HostApiAuthChecker(make_host_token(scope))

    with pytest.raises((InvalidParamsError, ParamsPermissionDeniedError)):
        checker.check(request_data)


@pytest.mark.parametrize(
    ("scope", "request_data"),
    [
        ({"version": 1, "target_type": "host", "bk_host_id": 100}, {"bk_host_id": 100}),
        (
            {"version": 1, "target_type": "topo", "bk_obj_id": "module", "bk_inst_id": 10},
            {"bk_obj_id": "module", "bk_inst_id": 10},
        ),
    ],
)
def test_host_scope_accepts_exact_request_target(mocker, scope, request_data):
    mock_host_scope(mocker)
    HostApiAuthChecker(make_host_token(scope)).check(request_data)


@pytest.mark.parametrize(
    "request_data",
    [
        {"bk_host_id": 100},
        {"bk_host_id": 100, "start_time": 100},
        {"bk_host_id": 100, "end_time": 200},
    ],
)
def test_host_scope_absolute_time_lock_requires_both_bounds(mocker, request_data):
    mock_host_scope(mocker)
    token = make_host_token({"version": 1, "target_type": "host", "bk_host_id": 100})
    token.params.update({"lock_search": True, "start_time": 100, "end_time": 200})

    with pytest.raises(InvalidParamsError):
        HostApiAuthChecker(token).check(request_data)


def test_host_scope_absolute_time_lock_requires_exact_bounds(mocker):
    mock_host_scope(mocker)
    token = make_host_token({"version": 1, "target_type": "host", "bk_host_id": 100})
    token.params.update({"lock_search": True, "start_time": 100, "end_time": 200})
    checker = HostApiAuthChecker(token)

    checker.check({"bk_host_id": 100, "start_time": 100, "end_time": 200})
    with pytest.raises(SearchLockedError):
        checker.check({"bk_host_id": 100, "start_time": 101, "end_time": 200})


@pytest.mark.parametrize(
    "action",
    [
        "get_host_views_panels",
        "get_host_metric_group_panel_order",
        "get_process_views_panels",
        "get_process_metric_group_panel_order",
    ],
)
def test_host_scope_absolute_time_lock_keeps_target_independent_panel_config_available(mocker, action):
    mock_host_request(mocker, action)
    mock_host_scope(mocker)
    token = make_host_token({"version": 1, "target_type": "host", "bk_host_id": 100})
    token.params.update({"lock_search": True, "start_time": 100, "end_time": 200})

    HostApiAuthChecker(token).check({"scene_id": "host", "type": "detail", "id": "host"})


def test_host_scope_panel_fields_cannot_bypass_process_list_target(mocker):
    request = mock_host_request(mocker, "get_host_process_list")
    mocker.patch("bkmonitor.share.api_auth_resource.get_request", return_value=request)
    mocker.patch("bkmonitor.share.utils.get_request_tenant_id", return_value="system")
    mocker.patch.object(
        ApiAuthToken.objects,
        "get",
        return_value=make_host_token({"version": 1, "target_type": "host", "bk_host_id": 100}),
    )
    mock_host_scope(mocker)

    with pytest.raises(ParamsPermissionDeniedError):
        GetHostProcessListResource().validate_request_data(
            {
                "bk_biz_id": 2,
                "bk_host_id": 999,
                "scene_id": "host",
                "type": "detail",
                "id": "process",
            }
        )


@pytest.mark.parametrize(
    ("is_ipv6", "target"),
    [
        (False, {"bk_host_id": 100}),
        (True, {"bk_target_ip": "10.0.0.1", "bk_target_cloud_id": 0}),
    ],
)
def test_host_scope_unify_query_rejects_target_removed_by_normalization(mocker, is_ipv6, target):
    mock_unify_query_host_token(mocker, is_ipv6)

    with pytest.raises(InvalidParamsError):
        GraphUnifyQueryResource().validate_request_data(make_unify_query_request(target))


@pytest.mark.parametrize(
    ("is_ipv6", "expected_target"),
    [
        (False, {"bk_target_ip": "10.0.0.1", "bk_target_cloud_id": "0"}),
        (True, {"bk_host_id": "100"}),
    ],
)
def test_host_scope_unify_query_keeps_normalized_target_constrained(mocker, is_ipv6, expected_target):
    mock_unify_query_host_token(mocker, is_ipv6)
    target = {"bk_host_id": 100, "bk_target_ip": "10.0.0.1", "bk_target_cloud_id": 0}

    validated = GraphUnifyQueryResource().validate_request_data(make_unify_query_request(target))

    assert validated["query_configs"][0]["filter_dict"]["targets"] == [expected_target]


def test_host_scope_unify_query_accepts_allowed_ip_cloud_target(mocker):
    mock_host_scope(mocker)
    checker = HostApiAuthChecker(make_host_token({"version": 1, "target_type": "host", "bk_host_id": 100}))
    mocker.patch.object(checker, "query_configs_check", wraps=checker.query_configs_check)
    mocker.patch(
        "bkmonitor.share.handler.MetricListCache.objects.filter",
        return_value=Mock(values_list=Mock(return_value=[("system.cpu", "cpu_usage")])),
    )

    checker.check(
        {
            "query_configs": [
                {
                    "data_source_label": "bk_monitor",
                    "data_type_label": "time_series",
                    "table": "system.cpu",
                    "metrics": [{"field": "cpu_usage"}],
                    "filter_dict": {"targets": [{"bk_target_ip": "10.0.0.1", "bk_target_cloud_id": "0"}]},
                }
            ]
        }
    )


def test_host_scope_unify_query_denies_other_host_target(mocker):
    mock_host_scope(mocker)
    checker = HostApiAuthChecker(make_host_token({"version": 1, "target_type": "host", "bk_host_id": 100}))
    mocker.patch(
        "bkmonitor.share.handler.MetricListCache.objects.filter",
        return_value=Mock(values_list=Mock(return_value=[("system.cpu", "cpu_usage")])),
    )

    with pytest.raises(ParamsPermissionDeniedError):
        checker.check(
            {
                "query_configs": [
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "table": "system.cpu",
                        "metrics": [{"field": "cpu_usage"}],
                        "filter_dict": {"targets": [{"bk_target_ip": "10.0.0.2", "bk_target_cloud_id": "0"}]},
                    }
                ]
            }
        )


def test_topo_scope_unify_query_allows_members_and_denies_non_members(mocker):
    mock_host_scope(mocker, [make_host(100, "10.0.0.1"), make_host(101, "10.0.0.2")])
    checker = HostApiAuthChecker(
        make_host_token({"version": 1, "target_type": "topo", "bk_obj_id": "module", "bk_inst_id": 10})
    )
    mocker.patch(
        "bkmonitor.share.handler.MetricListCache.objects.filter",
        return_value=Mock(values_list=Mock(return_value=[("system.cpu", "cpu_usage")])),
    )

    checker.check(
        {
            "query_configs": [
                {
                    "data_source_label": "bk_monitor",
                    "data_type_label": "time_series",
                    "table": "system.cpu",
                    "metrics": [{"field": "cpu_usage"}],
                    "filter_dict": {
                        "targets": [
                            {"bk_target_ip": "10.0.0.1", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "10.0.0.2", "bk_target_cloud_id": 0},
                        ]
                    },
                }
            ]
        }
    )
    with pytest.raises(ParamsPermissionDeniedError):
        checker.query_target_check(
            {"bk_target_ip": "10.0.0.3", "bk_target_cloud_id": 0},
            "query_configs.0.filter_dict.targets.0",
        )


def test_host_scope_unify_query_denies_prometheus_promql(mocker):
    mock_host_scope(mocker)
    checker = HostApiAuthChecker(make_host_token({"version": 1, "target_type": "host", "bk_host_id": 100}))
    mocker.patch(
        "bkmonitor.share.handler.MetricListCache.objects.filter",
        return_value=Mock(values_list=Mock(return_value=[("system.cpu", "cpu_usage")])),
    )

    with pytest.raises(ParamsPermissionDeniedError):
        checker.check(
            {
                "query_configs": [
                    {
                        "data_source_label": "prometheus",
                        "data_type_label": "time_series",
                        "table": "system.cpu",
                        "promql": "sum(arbitrary_business_metric)",
                        "metrics": [],
                        "filter_dict": {"targets": [{"bk_target_ip": "10.0.0.1", "bk_target_cloud_id": 0}]},
                    }
                ]
            }
        )


def test_host_scope_unify_query_denies_metric_from_other_system_table(mocker):
    mock_host_scope(mocker)
    checker = HostApiAuthChecker(make_host_token({"version": 1, "target_type": "host", "bk_host_id": 100}))
    mocker.patch(
        "bkmonitor.share.handler.MetricListCache.objects.filter",
        return_value=Mock(values_list=Mock(return_value=[("system.cpu", "cpu_usage")])),
    )

    with pytest.raises(ParamsPermissionDeniedError):
        checker.check(
            {
                "query_configs": [
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "table": "system.mem",
                        "metrics": [{"field": "cpu_usage"}],
                        "filter_dict": {"targets": [{"bk_target_ip": "10.0.0.1", "bk_target_cloud_id": 0}]},
                    }
                ]
            }
        )


@pytest.mark.parametrize(
    "query_configs",
    [
        [None],
        [
            {
                "data_source_label": "bk_monitor",
                "data_type_label": "time_series",
                "table": "system.cpu",
                "metrics": [{"field": "cpu_usage"}],
                "filter_dict": [],
            }
        ],
        [
            {
                "data_source_label": "bk_monitor",
                "data_type_label": "time_series",
                "table": "system.cpu",
                "metrics": [None],
                "filter_dict": {"targets": [{"bk_target_ip": "10.0.0.1", "bk_target_cloud_id": 0}]},
            }
        ],
    ],
)
def test_host_scope_unify_query_rejects_malformed_raw_config(mocker, query_configs):
    mock_host_scope(mocker)
    checker = HostApiAuthChecker(make_host_token({"version": 1, "target_type": "host", "bk_host_id": 100}))
    mocker.patch(
        "bkmonitor.share.handler.MetricListCache.objects.filter",
        return_value=Mock(values_list=Mock(return_value=[("system.cpu", "cpu_usage")])),
    )

    with pytest.raises(InvalidParamsError):
        checker.check({"query_configs": query_configs})


def test_new_host_data_resources_all_run_api_auth_check():
    assert issubclass(GetTopoTree, ApiAuthResource)
    assert issubclass(SearchHostInfoResource, ApiAuthResource)
    assert issubclass(SearchHostMetricResource, ApiAuthResource)
    assert issubclass(GetHostProcessListResource, ApiAuthResource)


def test_get_topo_tree_response_is_pruned_to_host_scope(mocker):
    topo_tree = {
        "bk_obj_id": "biz",
        "bk_inst_id": 2,
        "bk_inst_name": "biz",
        "child": [
            {
                "bk_obj_id": "module",
                "bk_inst_id": 10,
                "bk_inst_name": "module-a",
                "child": [
                    {"bk_host_id": 100, "bk_host_innerip": "10.0.0.1", "child": []},
                    {"bk_host_id": 101, "bk_host_innerip": "10.0.0.2", "child": []},
                ],
            },
            {
                "bk_obj_id": "module",
                "bk_inst_id": 11,
                "bk_inst_name": "module-b",
                "child": [{"bk_host_id": 102, "bk_host_innerip": "10.0.0.3", "child": []}],
            },
        ],
    }
    mocker.patch(
        "monitor_web.commons.cc.resources.frontend_resources.resource.commons.cc_topo_tree",
        return_value=topo_tree,
    )
    mocker.patch(
        "monitor_web.commons.cc.resources.frontend_resources.get_host_view_display_fields",
        return_value=("bk_host_innerip", "bk_host_innerip"),
    )

    result = GetTopoTree().perform_request(
        {"bk_biz_id": 2, "instance_type": "host", "remove_empty_nodes": False, "bk_host_id": 100}
    )

    assert result[0]["children"][0]["children"] == [
        {
            "bk_biz_id": 2,
            "bk_host_id": 100,
            "bk_host_innerip": "10.0.0.1",
            "children": [],
            "name": "10.0.0.1",
            "alias_name": "10.0.0.1",
            "id": "100",
        }
    ]
    assert result[0]["children"][0]["bk_inst_id"] == 10
    assert len(result[0]["children"]) == 1


def test_get_topo_tree_response_keeps_only_selected_topo_subtree(mocker):
    topo_tree = {
        "bk_obj_id": "biz",
        "bk_inst_id": 2,
        "bk_inst_name": "biz",
        "child": [
            {
                "bk_obj_id": "module",
                "bk_inst_id": 10,
                "bk_inst_name": "module-a",
                "child": [{"bk_host_id": 100, "bk_host_innerip": "10.0.0.1", "child": []}],
            },
            {
                "bk_obj_id": "module",
                "bk_inst_id": 11,
                "bk_inst_name": "module-b",
                "child": [{"bk_host_id": 101, "bk_host_innerip": "10.0.0.2", "child": []}],
            },
        ],
    }
    mocker.patch(
        "monitor_web.commons.cc.resources.frontend_resources.resource.commons.cc_topo_tree",
        return_value=topo_tree,
    )
    mocker.patch(
        "monitor_web.commons.cc.resources.frontend_resources.get_host_view_display_fields",
        return_value=("bk_host_innerip", "bk_host_innerip"),
    )

    result = GetTopoTree().perform_request(
        {
            "bk_biz_id": 2,
            "instance_type": "host",
            "remove_empty_nodes": False,
            "bk_obj_id": "module",
            "bk_inst_id": 10,
        }
    )

    assert [node["bk_inst_id"] for node in result[0]["children"]] == [10]
    assert [host["bk_host_id"] for host in result[0]["children"][0]["children"]] == [100]


def test_search_host_info_response_is_limited_to_scope_target(mocker):
    host = make_host()
    host.display_name = "host-100"
    host.bk_biz_id = 2
    host.bk_cloud_name = "default"
    host.bk_host_outerip = ""
    host.bk_os_type = "1"
    host.bk_os_name = "linux"
    host.bk_province_name = ""
    host.bk_host_name = "host-100"
    host.ignore_monitoring = False
    host.is_shielding = False
    host.bk_module_ids = []
    get_host_by_id = mocker.patch(
        "monitor_web.performance.resources.api.cmdb.get_host_by_id",
        return_value=[host],
    )
    mocker.patch(
        "monitor_web.performance.resources.api.cmdb.get_topo_tree",
        return_value=SimpleNamespace(convert_to_topo_link=lambda: {}),
    )

    result = SearchHostInfoResource().perform_request({"bk_biz_id": 2, "bk_host_id": 100})

    assert [item["bk_host_id"] for item in result] == [100]
    get_host_by_id.assert_called_once_with(bk_biz_id=2, bk_host_ids=[100])


def test_search_host_metric_response_and_request_are_limited_to_host_scope(mocker):
    host = make_host()
    get_host_by_id = mocker.patch(
        "monitor_web.performance.resources.api.cmdb.get_host_by_id",
        return_value=[host],
    )
    for method in ["get_agent_status", "get_performance_data", "get_process_status", "get_alarm_count"]:
        mocker.patch.object(SearchHostMetricResource, method)

    result = SearchHostMetricResource().perform_request({"bk_biz_id": 2, "bk_host_id": 100, "bk_host_ids": [100]})

    assert set(result) == {100}
    get_host_by_id.assert_called_once_with(bk_biz_id=2, bk_host_ids=[100])
    with pytest.raises(ParamsPermissionDeniedError):
        SearchHostMetricResource.validate_scope_host_ids({"bk_biz_id": 2, "bk_host_id": 100, "bk_host_ids": [100, 101]})


def test_create_host_share_token_requires_view_host(mocker):
    expected_permission_error = RuntimeError("VIEW_HOST required")
    permission = mocker.patch("monitor_web.share.resources.Permission")
    permission.return_value.is_allowed_by_biz.side_effect = expected_permission_error
    mocker.patch("monitor_web.share.resources.get_global_user", return_value="token-creator")
    mocker.patch("monitor_web.share.resources.get_request_tenant_id", return_value="system")
    token_values = Mock()
    token_values.distinct.return_value = []
    token_queryset = Mock()
    token_queryset.values_list.return_value = token_values
    mocker.patch.object(ApiAuthToken.origin_objects, "filter", return_value=token_queryset)
    create = mocker.patch.object(ApiAuthToken.objects, "create")

    with pytest.raises(RuntimeError, match="VIEW_HOST required"):
        CreateShareTokenResource().perform_request(
            {
                "bk_biz_id": 2,
                "type": "host",
                "expire_time": int(datetime.now().timestamp()) + 3600,
                "expire_period": "1h",
                "lock_search": False,
                "default_time_range": [],
                "start_time": None,
                "end_time": None,
                "data": {},
            }
        )

    permission.return_value.is_allowed_by_biz.assert_called_once_with(
        bk_biz_id=2,
        action=ActionEnum.VIEW_HOST,
        raise_exception=True,
    )
    permission.assert_called_once_with(username="token-creator", bk_tenant_id="system")
    create.assert_not_called()


def test_create_unregistered_scene_host_token_is_rejected(mocker):
    create = mocker.patch.object(ApiAuthToken.objects, "create")

    with pytest.raises(TokenValidatedError):
        CreateShareTokenResource().perform_request(
            {
                "bk_biz_id": 2,
                "type": "scene_host",
                "expire_time": int(datetime.now().timestamp()) + 3600,
                "expire_period": "1h",
                "lock_search": False,
                "default_time_range": [],
                "start_time": None,
                "end_time": None,
                "data": {},
            }
        )

    create.assert_not_called()


def test_create_host_share_token_requires_canonical_existing_scope(mocker):
    mocker.patch("monitor_web.share.resources.Permission")
    mocker.patch("monitor_web.share.resources.get_request_tenant_id", return_value="system")
    create = mocker.patch.object(ApiAuthToken.objects, "create")
    params = {
        "bk_biz_id": 2,
        "type": "host",
        "expire_time": int(datetime.now().timestamp()) + 3600,
        "expire_period": "1h",
        "lock_search": False,
        "default_time_range": [],
        "start_time": None,
        "end_time": None,
        "data": {},
    }

    with pytest.raises(InvalidParamsError):
        CreateShareTokenResource().perform_request(params)

    params["data"] = {"scope": {"version": 1, "target_type": "host", "bk_host_id": 100}}
    mocker.patch("monitor_web.share.resources.api.cmdb.get_host_by_id", return_value=[])
    with pytest.raises(TokenValidatedError):
        CreateShareTokenResource().perform_request(params)

    create.assert_not_called()


def test_update_host_share_token_requires_view_host(mocker):
    expected_permission_error = RuntimeError("VIEW_HOST required")
    permission = mocker.patch("monitor_web.share.resources.Permission")
    permission.return_value.is_allowed_by_biz.side_effect = expected_permission_error
    mocker.patch("monitor_web.share.resources.get_global_user", return_value="token-creator")
    mocker.patch("monitor_web.share.resources.get_request_tenant_id", return_value="system")
    token = SimpleNamespace(
        token="share-token",
        type="host",
        namespaces=["biz#2"],
        is_deleted=False,
        is_expired=lambda: False,
        expire_time=datetime.now(),
        params={},
        save=Mock(),
    )
    mocker.patch.object(ApiAuthToken.origin_objects, "get", return_value=token)

    with pytest.raises(RuntimeError, match="VIEW_HOST required"):
        UpdateShareTokenResource().perform_request({"token": "share-token"})

    permission.return_value.is_allowed_by_biz.assert_called_once_with(
        bk_biz_id=2,
        action=ActionEnum.VIEW_HOST,
        raise_exception=True,
    )
    permission.assert_called_once_with(username="token-creator", bk_tenant_id="system")
    token.save.assert_not_called()


def test_update_host_share_token_preserves_and_revalidates_scope(mocker):
    mocker.patch("monitor_web.share.resources.Permission")
    mocker.patch("monitor_web.share.resources.get_request_tenant_id", return_value="system")
    token = SimpleNamespace(
        token="share-token",
        type="host",
        namespaces=["biz#2"],
        is_deleted=False,
        is_expired=lambda: False,
        expire_time=datetime.now(),
        params={"data": {"scope": {"version": 1, "target_type": "host", "bk_host_id": 100}}},
        save=Mock(),
    )
    mocker.patch.object(ApiAuthToken.origin_objects, "get", return_value=token)
    get_host_by_id = mocker.patch("monitor_web.share.resources.api.cmdb.get_host_by_id", return_value=[make_host()])

    UpdateShareTokenResource().perform_request({"token": "share-token"})

    get_host_by_id.assert_called_once_with(bk_biz_id=2, bk_host_ids=[100])
    token.save.assert_called_once_with()


def test_update_non_host_share_token_keeps_existing_permission_contract(mocker):
    permission = mocker.patch("monitor_web.share.resources.Permission")
    mocker.patch("monitor_web.share.resources.get_request_tenant_id", return_value="system")
    token = SimpleNamespace(
        token="share-token",
        type="dashboard",
        namespaces=[],
        is_deleted=False,
        is_expired=lambda: False,
        expire_time=datetime.now(),
        params={},
        save=Mock(),
    )
    mocker.patch.object(ApiAuthToken.origin_objects, "get", return_value=token)

    result = UpdateShareTokenResource().perform_request({"token": "share-token"})

    assert result["token"] == "share-token"
    permission.assert_not_called()
    token.save.assert_called_once_with()


def test_update_unregistered_scene_host_token_is_rejected(mocker):
    mocker.patch("monitor_web.share.resources.get_request_tenant_id", return_value="system")
    token = SimpleNamespace(
        token="share-token",
        type="scene_host",
        namespaces=["biz#2"],
        is_deleted=False,
        is_expired=lambda: False,
        expire_time=datetime.now(),
        params={},
        save=Mock(),
    )
    mocker.patch.object(ApiAuthToken.origin_objects, "get", return_value=token)

    with pytest.raises(TokenValidatedError):
        UpdateShareTokenResource().perform_request({"token": "share-token"})

    token.save.assert_not_called()
