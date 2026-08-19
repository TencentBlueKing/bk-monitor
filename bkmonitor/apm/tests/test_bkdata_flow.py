from types import SimpleNamespace
from unittest.mock import mock_open

from apm.core.handlers.bk_data.flow import ApmFlow
from apm.core.handlers.bk_data.tail_sampling import TailSamplingFlow


def test_resolve_bkdata_biz_id_uses_tenant_default_for_space(settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = True
    get_tenant_default_biz_id = mocker.patch(
        "apm.core.handlers.bk_data.flow.get_tenant_default_biz_id", return_value=9527
    )

    result = ApmFlow._resolve_bkdata_biz_id("tenant-a", -100)

    assert result == 9527
    get_tenant_default_biz_id.assert_called_once_with("tenant-a")


def test_resolve_bkdata_biz_id_keeps_single_tenant_behavior(settings):
    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.BK_DATA_BK_BIZ_ID = 2

    assert ApmFlow._resolve_bkdata_biz_id("system", -100) == 2


def test_resolve_bkdata_biz_id_keeps_positive_business(settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = True
    get_tenant_default_biz_id = mocker.patch("apm.core.handlers.bk_data.flow.get_tenant_default_biz_id")

    assert ApmFlow._resolve_bkdata_biz_id("tenant-a", 1001) == 1001
    get_tenant_default_biz_id.assert_not_called()


def test_tail_sampling_registers_storage_in_resolved_bkdata_business(settings, mocker):
    settings.APM_APP_BKDATA_TAIL_SAMPLING_PROJECT_ID = 123
    storage = SimpleNamespace(retention=30, storage_cluster_id=1)
    trace_datasource = SimpleNamespace(result_table_id="2_bkapm.trace", storage=storage)
    cluster_info = SimpleNamespace(
        cluster_name="es",
        cluster_id=1,
        consul_config={},
        domain_name="es.example.com",
        password="password",
        port=9300,
        username="username",
    )
    mocker.patch("apm.core.handlers.bk_data.tail_sampling.TraceDataSource.objects.get", return_value=trace_datasource)
    mocker.patch("apm.core.handlers.bk_data.tail_sampling.ClusterInfo.objects.get", return_value=cluster_info)
    mocker.patch("apm.core.handlers.bk_data.tail_sampling.api.bkdata.query_resource_list", return_value=[])
    get_or_create_resource_set = mocker.patch(
        "apm.core.handlers.bk_data.tail_sampling.api.bkdata.get_or_create_resource_set",
        return_value={"resource_set_id": "apm_storage_id_1", "resource_set_name": "apm_storage_es"},
    )
    mocker.patch(
        "apm.core.handlers.bk_data.tail_sampling.api.bkdata.get_resource_set",
        return_value={"authorized_projects": [{"id": 123}]},
    )
    mocker.patch("builtins.open", mock_open(read_data="flink code"))
    mocker.patch.object(ApmFlow, "flow_instance", return_value=object())

    flow = object.__new__(TailSamplingFlow)
    flow.bk_biz_id = -100
    flow.bk_tenant_id = "tenant-a"
    flow.bkdata_bk_biz_id = 9527
    flow.app_name = "demo"
    flow.logger = mocker.Mock()

    flow.flow_instance()

    assert get_or_create_resource_set.call_args.args[0]["bk_biz_id"] == 9527
