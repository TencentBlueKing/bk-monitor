from unittest import mock

import pytest

from api.cmdb import default as cmdb
from core.drf_resource import resource
from core.errors.common import CustomError


SERVICE_INSTANCES = [
    {"id": 101, "bk_module_id": 10, "name": "service-101"},
    {"id": 102, "bk_module_id": 10, "name": "service-102"},
    {"id": 201, "bk_module_id": 20, "name": "service-201"},
]


def test_service_instance_module_index_groups_ids_by_module():
    assert cmdb.ServiceInstanceModuleIndex.build(SERVICE_INSTANCES) == {"10": [101, 102], "20": [201]}


def test_service_instance_module_index_caches_empty_business(mocker):
    mocker.patch.object(cmdb, "bk_biz_id_to_bk_tenant_id", return_value="tenant-a")
    mocker.patch.object(cmdb.uuid, "uuid4", return_value=mock.Mock(hex="write-1"))
    cache_set = mocker.patch.object(cmdb.cache, "set", return_value=False)
    cache_get = mocker.patch.object(
        cmdb.cache,
        "get",
        return_value={"write_id": "write-1", "module_to_service_instance_ids": {}},
    )

    cmdb.ServiceInstanceModuleIndex.set(2, [])

    cache_set.assert_called_once_with(
        "web_cache:cc_cache_always:service_instance_module_index:v2:tenant-a:2",
        {"write_id": "write-1", "module_to_service_instance_ids": {}},
        cmdb.CacheType.CC_CACHE_ALWAYS.timeout,
    )
    cache_get.assert_called_once_with("web_cache:cc_cache_always:service_instance_module_index:v2:tenant-a:2")


def test_service_instance_module_index_distinguishes_empty_from_missing(mocker):
    mocker.patch.object(cmdb, "bk_biz_id_to_bk_tenant_id", return_value="tenant-a")
    mocker.patch.object(
        cmdb.cache,
        "get",
        side_effect=[{"write_id": "write-1", "module_to_service_instance_ids": {}}, None],
    )

    assert cmdb.ServiceInstanceModuleIndex.get(2) == {}
    assert cmdb.ServiceInstanceModuleIndex.get(2) is None


def test_service_instance_module_index_cache_key_contains_tenant(mocker):
    tenant = mocker.patch.object(cmdb, "bk_biz_id_to_bk_tenant_id", side_effect=["tenant-a", "tenant-b"])

    assert cmdb.ServiceInstanceModuleIndex.cache_key(2).endswith(":tenant-a:2")
    assert cmdb.ServiceInstanceModuleIndex.cache_key(3).endswith(":tenant-b:3")
    assert tenant.call_args_list == [mock.call(2), mock.call(3)]


def test_get_service_instance_by_biz_updates_index_from_same_response(mocker):
    response = mocker.patch.object(cmdb, "batch_request", return_value=SERVICE_INSTANCES)
    set_index = mocker.patch.object(cmdb.ServiceInstanceModuleIndex, "set")

    assert cmdb.get_service_instance_by_biz.cacheless(2) is SERVICE_INSTANCES

    response.assert_called_once()
    set_index.assert_called_once_with(2, SERVICE_INSTANCES)


def test_get_service_instance_by_biz_fails_when_index_write_fails(mocker):
    mocker.patch.object(cmdb, "batch_request", return_value=SERVICE_INSTANCES)
    mocker.patch.object(cmdb, "bk_biz_id_to_bk_tenant_id", return_value="tenant-a")
    mocker.patch.object(cmdb.cache, "set", side_effect=RuntimeError("cache unavailable"))

    with pytest.raises(RuntimeError, match="cache unavailable"):
        cmdb.get_service_instance_by_biz.cacheless(2)


def test_get_service_instance_by_biz_fails_when_index_write_is_not_persisted(mocker):
    mocker.patch.object(cmdb, "batch_request", return_value=SERVICE_INSTANCES)
    mocker.patch.object(cmdb, "bk_biz_id_to_bk_tenant_id", return_value="tenant-a")
    mocker.patch.object(cmdb.cache, "set", return_value=False)
    mocker.patch.object(cmdb.cache, "get", return_value=None)

    with pytest.raises(RuntimeError, match="服务实例拓扑索引写入校验失败"):
        cmdb.get_service_instance_by_biz.cacheless(2)


def test_get_service_instance_by_biz_rejects_stale_index_with_same_ids(mocker):
    mocker.patch.object(cmdb, "batch_request", return_value=SERVICE_INSTANCES)
    mocker.patch.object(cmdb, "bk_biz_id_to_bk_tenant_id", return_value="tenant-a")
    mocker.patch.object(cmdb.uuid, "uuid4", return_value=mock.Mock(hex="current-write"))
    mocker.patch.object(cmdb.cache, "set", return_value=False)
    mocker.patch.object(
        cmdb.cache,
        "get",
        return_value={
            "write_id": "previous-write",
            "module_to_service_instance_ids": cmdb.ServiceInstanceModuleIndex.build(SERVICE_INSTANCES),
        },
    )

    with pytest.raises(RuntimeError, match="服务实例拓扑索引写入校验失败"):
        cmdb.get_service_instance_by_biz.cacheless(2)


def test_refresh_wrapper_uses_one_response_for_full_cache_and_index(mocker):
    response = mocker.patch.object(cmdb, "batch_request", return_value=SERVICE_INSTANCES)
    set_index = mocker.patch.object(cmdb.ServiceInstanceModuleIndex, "set")
    mocker.patch.object(cmdb.cache, "set")

    cmdb.get_service_instance_by_biz.refresh(2)

    response.assert_called_once()
    set_index.assert_called_once_with(2, SERVICE_INSTANCES)


def test_get_service_instance_ids_by_topo_node_only_reads_index(mocker):
    mocker.patch.object(cmdb.ServiceInstanceModuleIndex, "get", return_value={"10": [101, 102], "20": [201]})
    mocker.patch.object(cmdb, "_trans_topo_node_to_module_ids", return_value={10, 20})
    full_detail = mocker.patch.object(
        cmdb, "get_service_instance_by_biz", side_effect=AssertionError("ID-only path must not load full details")
    )

    result = cmdb.GetServiceInstanceIdsByTopoNode().perform_request(
        {"bk_biz_id": 2, "topo_nodes": {"module": [10], "set": [30]}}
    )

    assert set(result) == {101, 102, 201}
    full_detail.assert_not_called()


def test_get_service_instance_ids_by_topo_node_rejects_missing_index(mocker):
    mocker.patch.object(cmdb.ServiceInstanceModuleIndex, "get", return_value=None)
    mocker.patch.object(cmdb, "_trans_topo_node_to_module_ids", return_value={10})

    with pytest.raises(CustomError, match="服务实例拓扑索引尚未就绪"):
        cmdb.GetServiceInstanceIdsByTopoNode().perform_request({"bk_biz_id": 2, "topo_nodes": {"module": [10]}})


def test_existing_full_service_instance_resource_keeps_returning_objects(mocker):
    service_instances = [{"id": 101, "bk_module_id": 10, "name": "service-101"}]
    mocker.patch.object(cmdb, "get_service_instance_by_biz", return_value=service_instances)
    mocker.patch.object(cmdb, "_trans_topo_node_to_module_ids", return_value={10})

    result = cmdb.GetServiceInstanceByTopoNode().perform_request({"bk_biz_id": 2, "topo_nodes": {"module": [10]}})

    assert len(result) == 1
    assert result[0].service_instance_id == 101
    assert result[0].bk_module_id == 10


def test_get_service_instance_ids_by_template_uses_id_only_topo_resource(mocker):
    module = mock.Mock(bk_module_id=10)
    mocker.patch("core.drf_resource.api.cmdb.get_module", return_value=[module])
    get_ids = mocker.patch(
        "core.drf_resource.api.cmdb.get_service_instance_ids_by_topo_node", return_value=[101, 102], create=True
    )

    result = cmdb.GetServiceInstanceIdsByTemplate().perform_request(
        {"bk_biz_id": 2, "bk_obj_id": "SERVICE_TEMPLATE", "template_ids": [30]}
    )

    assert result == [101, 102]
    get_ids.assert_called_once_with(bk_biz_id=2, topo_nodes={"module": [10]})


def test_get_service_instance_ids_by_set_template_uses_id_only_topo_resource(mocker):
    bk_set = mock.Mock(bk_set_id=20)
    mocker.patch("core.drf_resource.api.cmdb.get_set", return_value=[bk_set])
    get_ids = mocker.patch(
        "core.drf_resource.api.cmdb.get_service_instance_ids_by_topo_node", return_value=[201], create=True
    )

    result = cmdb.GetServiceInstanceIdsByTemplate().perform_request(
        {"bk_biz_id": 2, "bk_obj_id": "SET_TEMPLATE", "template_ids": [30]}
    )

    assert result == [201]
    get_ids.assert_called_once_with(bk_biz_id=2, topo_nodes={"set": [20]})


@mock.patch("core.drf_resource.api.cmdb.get_service_instance_by_topo_node", create=True)
@mock.patch("core.drf_resource.api.cmdb.get_service_instance_ids_by_topo_node", return_value=[101, 102], create=True)
def test_parse_service_instance_topo_target_uses_id_only_resource(get_ids, get_full_instances):
    get_full_instances.side_effect = AssertionError("target parsing must not load full service instances")

    result = resource.cc.parse_topo_target(
        2,
        ["service_instance_id"],
        [{"bk_obj_id": "module", "bk_inst_id": 10}],
    )

    assert set(result[0]["service_instance_id"]) == {"101", "102"}
    get_ids.assert_called_once_with(bk_biz_id=2, topo_nodes={"module": [10]})
    get_full_instances.assert_not_called()


@mock.patch("core.drf_resource.api.cmdb.get_service_instance_by_template", create=True)
@mock.patch("core.drf_resource.api.cmdb.get_service_instance_ids_by_template", return_value=[201], create=True)
def test_parse_service_instance_template_target_uses_id_only_resource(get_ids, get_full_instances):
    get_full_instances.side_effect = AssertionError("target parsing must not load full service instances")

    result = resource.cc.parse_topo_target(
        2,
        ["bk_target_service_instance_id"],
        [{"bk_obj_id": "SET_TEMPLATE", "bk_inst_id": 30}],
    )

    assert result == [{"bk_target_service_instance_id": ["201"]}]
    get_ids.assert_called_once_with(bk_biz_id=2, bk_obj_id="SET_TEMPLATE", template_ids=[30])
    get_full_instances.assert_not_called()


def test_parse_service_instance_target_merges_topo_and_both_template_types(mocker):
    get_topo_ids = mocker.patch(
        "core.drf_resource.api.cmdb.get_service_instance_ids_by_topo_node", return_value=[101, 102]
    )
    get_template_ids = mocker.patch(
        "core.drf_resource.api.cmdb.get_service_instance_ids_by_template",
        side_effect=[[102, 201], [201, 301]],
    )
    mocker.patch(
        "core.drf_resource.api.cmdb.get_service_instance_by_topo_node",
        side_effect=AssertionError("target parsing must not load full service instances"),
    )
    mocker.patch(
        "core.drf_resource.api.cmdb.get_service_instance_by_template",
        side_effect=AssertionError("target parsing must not load full service instances"),
    )

    result = resource.cc.parse_topo_target(
        2,
        ["service_instance_id"],
        [
            {"bk_obj_id": "module", "bk_inst_id": 10},
            {"bk_obj_id": "SET_TEMPLATE", "bk_inst_id": 20},
            {"bk_obj_id": "SERVICE_TEMPLATE", "bk_inst_id": 30},
        ],
    )

    assert set(result[0]["service_instance_id"]) == {"101", "102", "201", "301"}
    get_topo_ids.assert_called_once_with(bk_biz_id=2, topo_nodes={"module": [10]})
    assert get_template_ids.call_args_list == [
        mock.call(bk_biz_id=2, bk_obj_id="SET_TEMPLATE", template_ids=[20]),
        mock.call(bk_biz_id=2, bk_obj_id="SERVICE_TEMPLATE", template_ids=[30]),
    ]


def test_parse_service_instance_target_preserves_empty_filter(mocker):
    mocker.patch("core.drf_resource.api.cmdb.get_service_instance_ids_by_topo_node", return_value=[])

    assert resource.cc.parse_topo_target(
        2,
        ["service_instance_id"],
        [{"bk_obj_id": "module", "bk_inst_id": 10}],
    ) == [{"service_instance_id": []}]
