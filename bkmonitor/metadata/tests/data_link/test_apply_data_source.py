"""DataSource 跨 namespace 下发，不复制 DataId 或修改本地数据源。"""

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
@pytest.mark.parametrize("target_namespace", ["shared", "bkmonitor"])
def test_apply_to_namespace(mocker, settings, source, multi_tenant, target_namespace):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
    config = models.DataIdConfig(
        bk_tenant_id="system", namespace="bkmonitor", name="registered_source", bk_data_id=960001, bk_biz_id=2
    )
    query = mocker.patch.object(models.DataIdConfig.objects, "filter")
    query.return_value.exclude.return_value.order_by.return_value.first.return_value = config
    apply = mocker.patch("metadata.models.data_source.api.bkdata.apply_data_link")
    save = mocker.patch.object(source, "save")
    for _ in range(2):
        result = source.apply_to_namespace(target_namespace)
        payload = apply.call_args.kwargs["config"]
        assert len(payload) == 1
        assert payload[0]["kind"] == "DataSource"
        assert payload[0]["metadata"]["namespace"] == target_namespace
        assert payload[0]["metadata"]["name"] == "registered_source"
        assert payload[0]["spec"]["data_id"]["namespace"] == "bkmonitor"
        assert payload[0]["spec"]["data_id"]["name"] == "registered_source"
        assert ("tenant" in payload[0]["metadata"]) is multi_tenant
        assert ("tenant" in payload[0]["spec"]["data_id"]) is multi_tenant
        assert result == dict(bk_data_id=960001, name="registered_source", target_namespace=target_namespace)
    query.assert_called_with(bk_tenant_id="system", bk_data_id=960001)
    query.return_value.exclude.return_value.order_by.assert_called_with("-last_modify_time", "-id")
    save.assert_not_called()
    apply.side_effect = RuntimeError("BKBase unavailable")
    with pytest.raises(RuntimeError, match="BKBase unavailable"):
        source.apply_to_namespace(target_namespace)


def test_missing_registration(mocker, source):
    query = mocker.patch.object(models.DataIdConfig.objects, "filter")
    query.return_value.exclude.return_value.order_by.return_value.first.return_value = None
    apply = mocker.patch("metadata.models.data_source.api.bkdata.apply_data_link")
    with pytest.raises(models.DataIdConfig.DoesNotExist, match="DataIdConfig not found"):
        source.apply_to_namespace("shared")
    apply.assert_not_called()


def test_resource_tenant_scope(mocker, source):
    get = mocker.patch.object(models.DataSource.objects, "get", return_value=source)
    apply = mocker.patch.object(source, "apply_to_namespace", return_value={"name": "registered_source"})
    params = dict(bk_tenant_id="system", bk_data_id=960001, target_namespace="shared")
    assert ApplyDataSourceResource().perform_request(params) == {"name": "registered_source"}
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
