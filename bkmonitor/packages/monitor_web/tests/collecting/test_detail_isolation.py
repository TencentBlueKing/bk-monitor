from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from constants.cmdb import TargetNodeType, TargetObjectType
from core.errors.collecting import CollectConfigNotExist
from monitor_web.collecting.resources import backend, frontend
from monitor_web.commons.cc.resources import backend_resources as cc


@pytest.fixture
def config_meta(mocker):
    config_json = [
        {"name": "password", "mode": "plugin", "type": "password", "default": "", "description": "密码"},
        {"name": "secret", "mode": "plugin", "type": "encrypt", "default": "", "description": "密钥"},
    ]
    plugin_detail = {
        "plugin_id": "sample",
        "plugin_display_name": "Sample",
        "config_json": config_json,
        "metric_json": [],
    }
    deployment = SimpleNamespace(
        target_node_type=TargetNodeType.TOPO,
        target_nodes=[{"bk_obj_id": "module", "bk_inst_id": 8}],
        plugin_version=SimpleNamespace(config_version=1, config=SimpleNamespace(config_json=config_json)),
        params={"collector": {"period": 60}, "plugin": {"password": "sample-password", "secret": "sample-secret"}},
        remote_collecting_host=None,
        subscription_id=1,
    )
    meta = SimpleNamespace(
        id=1,
        bk_biz_id=2,
        name="Sample config",
        collect_type="Script",
        label="host",
        target_object_type=TargetObjectType.HOST,
        deployment_config_id=1,
        deployment_config=deployment,
        plugin=SimpleNamespace(
            get_release_ver_by_config_ver=Mock(
                return_value=SimpleNamespace(get_plugin_version_detail=Mock(return_value=plugin_detail))
            )
        ),
        label_info={},
        create_time="",
        create_user="admin",
        update_time="",
        update_user="admin",
    )
    query = mocker.patch.object(backend.CollectConfigMeta.objects, "select_related")
    query.return_value.get.return_value = meta
    return meta, query


def config_detail(**params):
    handler = backend.CollectConfigDetailResource()
    return handler.perform_request(handler.validate_request_data({"id": 1, "bk_biz_id": 2, **params}))


@pytest.mark.parametrize("target_object_type", [TargetObjectType.HOST, TargetObjectType.SERVICE])
@pytest.mark.parametrize(
    "node_type",
    [
        TargetNodeType.TOPO,
        TargetNodeType.INSTANCE,
        TargetNodeType.SERVICE_TEMPLATE,
        TargetNodeType.SET_TEMPLATE,
        TargetNodeType.DYNAMIC_GROUP,
    ],
)
def test_basic_info_never_resolves_targets_and_masks_secrets(mocker, config_meta, target_object_type, node_type):
    meta, query = config_meta
    meta.target_object_type = target_object_type
    meta.deployment_config.target_node_type = node_type
    commons = Mock()
    cmdb = Mock()
    mocker.patch.object(backend.resource, "commons", new=commons)
    mocker.patch.object(backend.api, "cmdb", new=cmdb)
    commons.get_host_instance_by_node.side_effect = TimeoutError
    cmdb.search_dynamic_group.side_effect = TimeoutError
    mocker.patch.object(frontend.resource.collecting, "collect_config_detail", side_effect=config_detail)
    targets = mocker.patch.object(frontend.resource.collecting, "frontend_collect_config_target_info")

    result = frontend.FrontendCollectConfigDetailResource().perform_request(
        {"id": 1, "bk_biz_id": 2, "with_target_info": False}
    )

    assert result["basic_info"]["name"] == meta.name
    assert result["extend_info"]["plugin"] == {"password": True, "secret": True}
    assert [item["value"] for item in result["runtime_params"]] == [True, True]
    query.return_value.get.assert_called_once_with(id=1, bk_biz_id=2)
    assert not commons.mock_calls
    assert not cmdb.mock_calls
    targets.assert_not_called()


def test_basic_info_preserves_configuration_and_plugin_errors(mocker, config_meta):
    meta, query = config_meta
    query.return_value.get.side_effect = backend.CollectConfigMeta.DoesNotExist
    with pytest.raises(CollectConfigNotExist):
        config_detail(resolve_target=False)
    query.return_value.get.side_effect = None
    meta.plugin.get_release_ver_by_config_ver.side_effect = RuntimeError("plugin version unavailable")
    with pytest.raises(RuntimeError, match="plugin version unavailable"):
        config_detail(resolve_target=False)


@pytest.mark.parametrize("with_agent_status", [True, False])
def test_full_detail_preserves_default_target_resolution(mocker, config_meta, with_agent_status):
    targets = mocker.patch.object(backend.resource.commons, "get_host_instance_by_node", return_value=[{"count": 3}])
    result = config_detail(**({} if with_agent_status else {"with_agent_status": False}))
    assert result["target"] == [{"count": 3}]
    assert targets.call_args.args[0]["with_agent_status"] is with_agent_status


@pytest.mark.parametrize("agent_status", ["normal", "abnormal", "not_exist"])
def test_instance_target_keeps_existing_agent_status(mocker, config_meta, agent_status):
    meta, _ = config_meta
    meta.deployment_config.target_node_type = TargetNodeType.INSTANCE
    meta.deployment_config.target_nodes = [{"bk_host_id": 1}]
    row = {
        "display_name": "sample-host",
        "bk_host_id": 1,
        "ip": "host-a",
        "agent_status": agent_status,
        "bk_cloud_name": "cloud",
    }
    mocker.patch.object(backend.resource.commons, "get_host_instance_by_ip", return_value=[row])
    detail = mocker.patch.object(frontend.resource.collecting, "collect_config_detail", side_effect=config_detail)
    result = frontend.FrontendCollectConfigTargetInfoResource().perform_request({"id": 1, "bk_biz_id": 2})
    assert result["table_data"] == [row]
    assert detail.call_args.kwargs["with_agent_status"] is False


def test_frontend_default_still_composes_target_info(mocker, config_meta):
    mocker.patch.object(frontend.resource.collecting, "collect_config_detail", side_effect=config_detail)
    targets = mocker.patch.object(
        frontend.resource.collecting, "frontend_collect_config_target_info", return_value={"table_data": []}
    )
    handler = frontend.FrontendCollectConfigDetailResource()
    result = handler.perform_request(handler.validate_request_data({"id": 1, "bk_biz_id": 2}))
    assert result["target_info"] == {"table_data": []}
    targets.assert_called_once_with(id=1, bk_biz_id=2)


def node(kind, ident, children=None):
    return {"bk_obj_id": kind, "bk_inst_id": ident, "bk_inst_name": f"{kind}-{ident}", "child": children or []}


@pytest.fixture
def topology(mocker):
    tree = node("biz", 2, [node("set", 1, [node("module", 8), node("module", 9)])])
    mocker.patch.object(cc.resource.cc, "topo_tree", return_value=tree)
    mocker.patch.object(
        cc.api.cmdb,
        "get_module",
        return_value=[
            SimpleNamespace(bk_module_id=ident, service_category_id=1, service_template_id=4) for ident in [8, 9]
        ],
    )
    mocker.patch.object(cc, "ServiceCategorySearcher").return_value.search.return_value = "category"
    hosts = [
        SimpleNamespace(bk_host_id=1, bk_module_ids=[8, 9]),
        SimpleNamespace(bk_host_id=2, bk_module_ids=[8]),
        SimpleNamespace(bk_host_id=3, bk_module_ids=[9]),
    ]
    mocker.patch.object(cc.api.cmdb, "get_host_by_topo_node", return_value=hosts)
    mocker.patch.object(cc.api.cmdb, "get_host_page", return_value={"items": hosts, "total": len(hosts)})
    mocker.patch.object(
        cc.api.cmdb,
        "get_service_instance_by_topo_node",
        return_value=[
            SimpleNamespace(bk_host_id=1, bk_module_id=8, service_instance_id=10),
            SimpleNamespace(bk_host_id=1, bk_module_id=9, service_instance_id=11),
            SimpleNamespace(bk_host_id=2, bk_module_id=8, service_instance_id=12),
            SimpleNamespace(bk_host_id=999, bk_module_id=8, service_instance_id=13),
        ],
    )
    return hosts


@pytest.mark.parametrize("inst_type", [TargetObjectType.HOST, TargetObjectType.SERVICE])
def test_target_api_topology_survives_agent_query_timeout(mocker, config_meta, topology, inst_type):
    meta, _ = config_meta
    meta.target_object_type = inst_type
    mocker.patch.object(frontend.resource.collecting, "collect_config_detail", side_effect=config_detail)
    handler_type = (
        cc.GetHostInstanceByNodeResource if inst_type == TargetObjectType.HOST else cc.GetServiceInstanceByNodeResource
    )
    handler = handler_type()
    target_resource = (
        "get_host_instance_by_node" if inst_type == TargetObjectType.HOST else "get_service_instance_by_node"
    )
    mocker.patch.object(
        cc.resource.commons,
        target_resource,
        side_effect=lambda data: handler.perform_request(handler.validate_request_data(data)),
    )
    agent = mocker.patch.object(cc.resource.cc, "get_agent_status", side_effect=TimeoutError("query unavailable"))
    result = frontend.FrontendCollectConfigTargetInfoResource().perform_request({"id": 1, "bk_biz_id": 2})
    assert result == {
        "target_node_type": TargetNodeType.TOPO,
        "table_data": [{"bk_inst_name": "module-8", "count": 2, "labels": ["category"]}],
    }
    agent.assert_not_called()


@pytest.mark.parametrize("handler_type", [cc.GetHostInstanceByNodeResource, cc.GetServiceInstanceByNodeResource])
def test_counts_labels_and_host_dedup_are_preserved_without_agent_query(mocker, topology, handler_type):
    agent = mocker.patch.object(cc.resource.cc, "get_agent_status", return_value={1: 0, 2: -1, 3: 2})
    data = {"bk_biz_id": 2, "node_list": [{"bk_biz_id": 2, "bk_obj_id": "set", "bk_inst_id": 1}]}
    handler = handler_type()
    full = handler.perform_request(handler.validate_request_data(deepcopy(data)))[0]
    agent.assert_called_once()
    agent.reset_mock(side_effect=True)
    agent.side_effect = TimeoutError("query unavailable")
    count = handler.perform_request(handler.validate_request_data({**deepcopy(data), "with_agent_status": False}))[0]
    assert "agent_error_count" not in count
    assert full.pop("agent_error_count") == (2 if handler_type is cc.GetHostInstanceByNodeResource else 1)
    assert count == full
    assert count["count"] == 3
    assert set(count["all_host"]) == ({1, 2, 3} if handler_type is cc.GetHostInstanceByNodeResource else {1, 2})
    assert count["labels"] == ["category"]
    agent.assert_not_called()


def test_host_counts_page_only_selected_modules_and_reset_previous_scope(mocker, topology):
    hosts = [SimpleNamespace(bk_host_id=ident, bk_module_ids=[8, 9]) for ident in range(501)]
    all_hosts = mocker.patch.object(cc.api.cmdb, "get_host_by_topo_node", side_effect=AssertionError("full inventory"))
    agent = mocker.patch.object(cc.resource.cc, "get_agent_status", side_effect=TimeoutError)
    get_page = mocker.patch.object(
        cc.api.cmdb,
        "get_host_page",
        side_effect=[{"items": hosts[:500], "total": 501}, {"items": hosts[500:], "total": 501}],
    )
    handler = cc.GetHostInstanceByNodeResource()
    handler.need_search_module_ids = {999}
    data = {
        "bk_biz_id": 2,
        "node_list": [{"bk_biz_id": 2, "bk_obj_id": "set", "bk_inst_id": 1}],
        "with_agent_status": False,
    }
    result = handler.perform_request(handler.validate_request_data(data))[0]
    assert result["count"] == 501
    assert len(result["all_host"]) == 501
    assert [call.kwargs["page"] for call in get_page.call_args_list] == [1, 2]
    assert all(call.kwargs["topo_nodes"] == {"module": [8, 9]} for call in get_page.call_args_list)
    all_hosts.assert_not_called()
    agent.assert_not_called()


def test_host_counts_push_filter_before_reading_large_inventory(mocker, topology):
    from api.cmdb import default as cmdb

    inventory = [(ident, 999) for ident in range(100000)] + [(100001, 8), (100002, 9)]

    def query(params):
        rules = params["module_property_filter"]["rules"]
        assert rules == [{"field": "bk_module_id", "operator": "in", "value": [8, 9]}]
        selected = [(ident, module) for ident, module in inventory if module in rules[0]["value"]]
        return {
            "count": len(selected),
            "info": [
                {
                    "host": {"bk_host_id": ident, "bk_host_innerip": f"host-{ident}", "bk_cloud_id": 0},
                    "topo": [{"bk_set_id": 1, "module": [{"bk_module_id": module}]}],
                }
                for ident, module in selected
            ],
        }

    get_all = mocker.patch.object(cmdb, "get_host_dict_by_biz", side_effect=AssertionError("full inventory"))
    client = mocker.patch.object(cmdb.client, "list_biz_hosts_topo", side_effect=query)
    mocker.patch.object(cmdb.api.cmdb, "search_cloud_area", return_value=[])
    page_handler = cmdb.GetHostPage()
    mocker.patch.object(
        cc.api.cmdb,
        "get_host_page",
        side_effect=lambda **data: page_handler.perform_request(page_handler.validate_request_data(data)),
    )
    handler = cc.GetHostInstanceByNodeResource()
    result = handler.perform_request(
        handler.validate_request_data(
            {
                "bk_biz_id": 2,
                "node_list": [{"bk_biz_id": 2, "bk_obj_id": "set", "bk_inst_id": 1}],
                "with_agent_status": False,
            }
        )
    )
    assert result[0]["count"] == 2
    assert set(result[0]["all_host"]) == {100001, 100002}
    client.assert_called_once()
    get_all.assert_not_called()


@pytest.mark.parametrize("inst_type", [TargetObjectType.HOST, TargetObjectType.SERVICE])
@pytest.mark.parametrize("template_type", [TargetNodeType.SERVICE_TEMPLATE, TargetNodeType.SET_TEMPLATE])
def test_template_counts_pass_agent_switch_to_host_and_service(mocker, topology, inst_type, template_type):
    selected = SimpleNamespace(
        bk_inst_id=1 if template_type == TargetNodeType.SET_TEMPLATE else 8,
        bk_inst_name="target",
        bk_obj_id="set" if template_type == TargetNodeType.SET_TEMPLATE else "module",
        bk_module_id=8,
        service_category_id=1,
        set_template_id=4,
        service_template_id=4,
    )
    mocker.patch.object(cc.api.cmdb, "get_set", return_value=[selected])
    if template_type == TargetNodeType.SERVICE_TEMPLATE:
        mocker.patch.object(cc.api.cmdb, "get_module", return_value=[selected])
    handler_type = (
        cc.GetHostInstanceByNodeResource if inst_type == TargetObjectType.HOST else cc.GetServiceInstanceByNodeResource
    )
    handler = handler_type()
    target_resource = (
        "get_host_instance_by_node" if inst_type == TargetObjectType.HOST else "get_service_instance_by_node"
    )
    mocker.patch.object(
        cc.resource.commons,
        target_resource,
        side_effect=lambda data: handler.perform_request(handler.validate_request_data(data)),
    )
    mocker.patch.object(cc, "ServiceCategorySearcher").return_value.search.return_value = None
    agent = mocker.patch.object(cc.resource.cc, "get_agent_status", side_effect=TimeoutError)
    template_handler = cc.GetNodesByTemplate()
    result = template_handler.perform_request(
        template_handler.validate_request_data(
            {
                "bk_biz_id": 2,
                "bk_obj_id": template_type,
                "bk_inst_ids": [4],
                "bk_inst_type": inst_type,
                "with_agent_status": False,
            }
        )
    )
    assert result[0]["count"] == (3 if template_type == TargetNodeType.SET_TEMPLATE else 2)
    assert "agent_error_count" not in result[0]
    agent.assert_not_called()


@pytest.mark.parametrize(
    "handler_type", [cc.GetHostInstanceByNodeResource, cc.GetServiceInstanceByNodeResource, cc.GetNodesByTemplate]
)
def test_count_only_and_status_responses_have_distinct_cache_keys(handler_type):
    handler = handler_type()
    params = {"bk_biz_id": 2, "node_list": []}
    full_key = handler._using_cache._cache_key(handler._cache_target_func, (params,), {})
    count_key = handler._using_cache._cache_key(
        handler._cache_target_func, ({**params, "with_agent_status": False},), {}
    )
    assert full_key != count_key
