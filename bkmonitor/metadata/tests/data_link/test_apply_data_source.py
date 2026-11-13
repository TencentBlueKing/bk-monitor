"""独立 DataSource 配置下发，不依赖 DataId 登记。"""

import ast
from pathlib import Path

import pytest
import yaml

from core.drf_resource.tools import get_underscore_viewset_name
from metadata import models
from metadata.resources import ApplyDataSourceResource


@pytest.fixture
def source():
    return models.DataSource(
        bk_tenant_id="system", bk_data_id=960001, data_name="shared-source", data_description="description"
    )


@pytest.mark.parametrize("multi_tenant", [False, True])
@pytest.mark.parametrize("target_namespace", ["shared", "shared_other"])
def test_apply_to_namespace(mocker, settings, source, multi_tenant, target_namespace):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
    mocker.patch("metadata.models.data_source.get_space_uid_and_bk_biz_id_by_bk_data_id", return_value=(2, "bkcc__2"))
    query = mocker.patch.object(models.DataIdConfig.objects, "filter", side_effect=AssertionError("无需查询 DataId"))
    apply = mocker.patch("metadata.models.data_source.api.bkdata.apply_data_link")
    register = mocker.patch.object(models.DataIdConfig.objects, "update_or_create")
    save = mocker.patch.object(source, "save")
    for _ in range(2):
        result = source.apply_to_namespace(target_namespace)
        payload = apply.call_args.kwargs["config"]
        assert len(payload) == 1
        assert payload[0]["kind"] == "DataSource"
        assert payload[0]["metadata"]["namespace"] == target_namespace
        assert payload[0]["metadata"]["name"] == "bkm_datasource_960001"
        assert "data_id" not in payload[0]["spec"]
        assert payload[0]["metadata"]["labels"] == {"raw_data_id": "960001"}
        assert payload[0]["spec"]["basic_info"]["data_source_alias"] == source.data_name
        assert payload[0]["spec"]["basic_info"]["description"] == source.data_description
        assert payload[0]["spec"]["basic_info"]["bk_biz_id"] == 2
        assert ("tenant" in payload[0]["metadata"]) is multi_tenant
        assert result == dict(bk_data_id=960001, name="bkm_datasource_960001", target_namespace=target_namespace)
    register.assert_called_with(
        bk_tenant_id="system",
        namespace=target_namespace,
        name="bkm_datasource_960001",
        defaults={"bk_data_id": 960001, "bk_biz_id": 2},
    )
    assert register.call_count == 2
    register.reset_mock()
    query.assert_not_called()
    save.assert_not_called()
    apply.side_effect = RuntimeError("BKBase unavailable")
    with pytest.raises(RuntimeError, match="BKBase unavailable"):
        source.apply_to_namespace(target_namespace)
    register.assert_not_called()


def test_resource_tenant_scope(mocker, source):
    get = mocker.patch.object(models.DataSource.objects, "get", return_value=source)
    apply = mocker.patch.object(source, "apply_to_namespace", return_value={"name": "bkm_datasource_960001"})
    params = dict(bk_tenant_id="system", bk_data_id=960001, target_namespace="shared")
    assert ApplyDataSourceResource().perform_request(params) == {"name": "bkm_datasource_960001"}
    get.assert_called_once_with(bk_tenant_id="system", bk_data_id=960001)
    apply.assert_called_once_with(target_namespace="shared")
    get.side_effect = models.DataSource.DoesNotExist
    with pytest.raises(ValueError, match="数据源不存在"):
        ApplyDataSourceResource().perform_request(params)


def test_resource_parameters_without_source(mocker):
    mocker.patch("bkmonitor.utils.serializers.get_request_tenant_id", return_value="system")
    serializer = ApplyDataSourceResource.RequestSerializer(data={"bk_data_id": 960001, "target_namespace": "shared"})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == dict(bk_tenant_id="system", bk_data_id=960001, target_namespace="shared")


@pytest.mark.parametrize("namespace", ["bkmonitor", "bklog", " bkmonitor ", " bklog "])
def test_reject_managed_namespace(mocker, namespace):
    mocker.patch("bkmonitor.utils.serializers.get_request_tenant_id", return_value="system")
    serializer = ApplyDataSourceResource.RequestSerializer(data={"bk_data_id": 960001, "target_namespace": namespace})
    assert not serializer.is_valid()
    assert "受管命名空间" in str(serializer.errors["target_namespace"])


@pytest.mark.parametrize("namespace", ["", "   "])
def test_reject_blank_namespace(mocker, namespace):
    mocker.patch("bkmonitor.utils.serializers.get_request_tenant_id", return_value="system")
    serializer = ApplyDataSourceResource.RequestSerializer(data={"bk_data_id": 960001, "target_namespace": namespace})
    assert not serializer.is_valid()
    assert serializer.errors["target_namespace"][0].code == "blank"


@pytest.mark.parametrize("missing", ["bk_data_id", "target_namespace"])
def test_required_parameters(mocker, missing):
    mocker.patch("bkmonitor.utils.serializers.get_request_tenant_id", return_value="system")
    params = dict(bk_data_id=960001, target_namespace="shared")
    del params[missing]
    serializer = ApplyDataSourceResource.RequestSerializer(data=params)
    assert not serializer.is_valid()
    assert missing in serializer.errors


def test_gateway_route():
    root = Path(__file__).resolve().parents[3]
    tree = ast.parse((root / "kernel_api/views/v3/meta.py").read_text())
    view = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ApplyDataSourceViewSet")
    assert get_underscore_viewset_name(type(view.name, (), {})) == "apply_data_source"
    route = view.body[0].value.elts[0]
    assert route.func.id == "ResourceRoute"
    assert route.args[0].value == "POST"
    assert route.args[1].attr == "ApplyDataSourceResource"
    definition = yaml.safe_load((root / "support-files/apigw/resources/internal/app/metadata.yaml").read_text())
    operation = definition["paths"]["/app/metadata/apply_data_source/"]["post"]
    assert operation["operationId"] == "metadata_apply_data_source"
    resource = operation["x-bk-apigateway-resource"]
    assert resource["backend"]["path"] == "/api/v3/meta/apply_data_source/"
    assert resource["isPublic"] is False
    assert resource["authConfig"] == dict(
        appVerifiedRequired=True, userVerifiedRequired=False, resourcePermissionRequired=True
    )
