from types import SimpleNamespace

from monitor_web.data_explorer.resources import GetGraphQueryConfig
from monitor_web.grafana.resources.time_series import GetVariableValue

from api.cmdb import default as cmdb


def test_empty_ids_skip_cmdb(mocker):
    batch = mocker.patch.object(cmdb, "batch_request")

    assert cmdb.GetServiceInstanceByID().perform_request({"bk_biz_id": 2, "service_instance_ids": []}) == []
    batch.assert_not_called()


def test_request_has_no_with_name(mocker):
    batch = mocker.patch.object(cmdb, "batch_request", return_value=[])

    cmdb.GetServiceInstanceByID().perform_request({"bk_biz_id": 2, "service_instance_ids": [1]})

    assert "with_name" not in batch.call_args.args[1]


def test_variable_translate_keeps_missing_service_instance(mocker):
    mocker.patch("monitor_web.grafana.resources.time_series.get_request_tenant_id", return_value="system")
    get_services = mocker.patch(
        "core.drf_resource.api.cmdb.get_service_instance_by_id",
        return_value=[SimpleNamespace(service_instance_id=1, name="svc-1")],
    )

    params = {"field": "bk_target_service_instance_id", "result_table_id": "system.proc"}
    result = GetVariableValue.dimension_translate(2, params, ["1", "2", ""])

    assert result == [{"label": "svc-1", "value": "1"}, {"label": "2", "value": "2"}, {"label": "", "value": ""}]
    assert get_services.call_args.kwargs["service_instance_ids"] == ["1", "2"]


def test_graph_translate_skips_non_integer_ids(mocker):
    get_hosts = mocker.patch("core.drf_resource.api.cmdb.get_host_by_id", return_value=[])
    get_services = mocker.patch("core.drf_resource.api.cmdb.get_service_instance_by_id", return_value=[])

    GetGraphQueryConfig.get_dimensions_translate_mapping(
        2, [(("bk_host_id", "1"), ("service_instance_id", "")), (("bk_host_id", "None"), ("service_instance_id", "3"))]
    )

    assert get_hosts.call_args.kwargs["bk_host_ids"] == ["1"]
    assert get_services.call_args.kwargs["service_instance_ids"] == ["3"]
