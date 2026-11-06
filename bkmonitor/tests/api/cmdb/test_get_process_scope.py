from copy import deepcopy

import pytest

from api.cmdb import default as cmdb


def service_instance(host_id, bindings=False):
    process = {"bk_process_id": host_id, "bk_process_name": f"process-{host_id}", "bk_func_name": "process"}
    if bindings:
        process["bind_info"] = [
            {"ip": "host-a", "port": "80", "protocol": "1"},
            {"ip": "host-b", "port": "81", "enable": False, "protocol": "2"},
        ]
    return {
        "process_instances": [
            {"process": process, "relation": {"bk_host_id": str(host_id), "service_instance_id": host_id}}
        ]
    }


@pytest.mark.parametrize("multiple_bindings", [False, True])
def test_process_scope_filters_raw_relations_before_constructing_processes(mocker, multiple_bindings):
    instances = [service_instance(host_id, bindings=True) for host_id in range(1, 101)]
    original = deepcopy(instances)
    mocker.patch.object(cmdb, "get_service_instance_by_biz", return_value=instances)
    params = {"bk_biz_id": 2, "include_multiple_bind_info": multiple_bindings}
    baseline = cmdb.GetProcess().perform_request(params)
    build_process = mocker.patch.object(cmdb, "Process", wraps=cmdb.Process)
    actual = cmdb.GetProcess().perform_request({**params, "bk_host_ids": [3, 2, 3]})
    assert [process.__dict__ for process in actual] == [
        process.__dict__ for process in baseline if process.bk_host_id in {2, 3}
    ]
    assert build_process.call_count == (4 if multiple_bindings else 2)
    assert instances == original


def test_single_host_process_request_keeps_direct_cmdb_query(mocker):
    batch = mocker.patch.object(cmdb, "batch_request", return_value=[service_instance(3)])
    all_instances = mocker.patch.object(cmdb, "get_service_instance_by_biz")
    actual = cmdb.GetProcess().perform_request({"bk_biz_id": 2, "bk_host_id": 3, "include_multiple_bind_info": False})
    batch.assert_called_once_with(
        cmdb.client.list_service_instance_detail, {"bk_biz_id": 2, "bk_host_id": 3}, limit=500
    )
    assert [process.bk_host_id for process in actual] == [3]
    all_instances.assert_not_called()


def test_empty_process_scope_does_not_load_business_instances(mocker):
    all_instances = mocker.patch.object(cmdb, "get_service_instance_by_biz")
    assert (
        cmdb.GetProcess().perform_request({"bk_biz_id": 2, "bk_host_ids": [], "include_multiple_bind_info": False})
        == []
    )
    all_instances.assert_not_called()


def test_process_scope_serializer_accepts_integer_ids_without_changing_default_scope():
    serializer = cmdb.GetProcess.RequestSerializer(data={"bk_biz_id": 2, "bk_host_ids": ["2", "3"]})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["bk_host_ids"] == [2, 3]
    serializer = cmdb.GetProcess.RequestSerializer(data={"bk_biz_id": 2})
    assert serializer.is_valid(), serializer.errors
    assert "bk_host_ids" not in serializer.validated_data
