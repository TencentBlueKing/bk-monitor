"""跨项目共享原始 DataId。"""

import ast
from pathlib import Path

import pytest
import yaml

from api.bkdata.default import GetNamespace
from core.drf_resource.tools import get_underscore_viewset_name
from metadata import models
from metadata.resources import ApplyDataSourceResource


@pytest.fixture
def source():
    return models.DataSource(
        bk_tenant_id="system", bk_data_id=960001, data_name="shared-source", data_description="description"
    )


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize("multi_tenant", [False, True])
def test_apply_to_namespace(mocker, settings, source, multi_tenant):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    source.etl_config = "bk_flat_batch"
    name = "bkm_did_960001_src"
    records = models.DataIdConfig.objects
    fields = {"bk_tenant_id": source.bk_tenant_id, "bk_data_id": source.bk_data_id, "bk_biz_id": 2}
    records.create(namespace="bklog", name=name, **fields)
    records.create(namespace="shared", name="bkm_datasource_960001", **fields)
    predefined = {
        "dataId": 960001,
        "channel": {"kind": "KafkaChannel", "namespace": "bklog", "name": "kafka1"},
        "topic": "logs",
    }
    spec = {"bizId": 2, "eventType": "log", "alias": "原日志源", "predefined": predefined}
    get = mocker.patch(
        "metadata.models.data_source.api.bkdata.get_data_link",
        return_value={
            "spec": spec,
            "metadata": {"annotations": {"dataId": "960001"}, "labels": {"bk_biz_id": "2"}},
            "status": {"phase": "Ok"},
        },
    )
    project = mocker.patch("metadata.models.data_source.api.bkdata.get_namespace")
    apply = mocker.patch("metadata.models.data_source.api.bkdata.apply_data_link", side_effect=RuntimeError("BKBase"))
    with pytest.raises(RuntimeError, match="BKBase"):
        source.apply_to_namespace("shared", bk_biz_id=591)
    assert list(records.filter(namespace="shared").values_list("name", flat=True)) == ["bkm_datasource_960001"]

    apply.side_effect = None
    for _ in range(2):
        assert source.apply_to_namespace("shared", bk_biz_id=591) == {
            "bk_data_id": 960001,
            "name": name,
            "target_namespace": "shared",
        }
    get.assert_called_with(bk_tenant_id=source.bk_tenant_id, namespace="bklog", kind="dataids", name=name)
    project.assert_not_called()
    metadata = {"namespace": "shared", "name": name, "labels": {"bk_biz_id": "2"}}
    if multi_tenant:
        metadata["tenant"] = source.bk_tenant_id
    apply.assert_called_with(
        config=[{"kind": "DataId", "metadata": metadata, "spec": {**spec, "bizId": 591}}],
        bk_tenant_id=source.bk_tenant_id,
    )
    assert spec["bizId"] == 2
    assert list(records.filter(namespace="shared").values_list("name", "bk_biz_id")) == [(name, 591)]
    assert records.get(namespace="bklog", name=name).bk_biz_id == 2


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize(
    ("biz_field", "annotations", "expected_topic"),
    [("bkBizId", {"topic": "original_topic"}, "original_topic"), ("bk_biz_id", {}, "existing_metric2")],
)
def test_share_allocated_data_id_without_explicit_business(mocker, source, biz_field, annotations, expected_topic):
    name = "existing_metric"
    models.DataIdConfig.objects.create(
        bk_tenant_id=source.bk_tenant_id, bk_data_id=source.bk_data_id, namespace="bkmonitor", name=name, bk_biz_id=2
    )
    project = mocker.patch(
        "metadata.models.data_source.api.bkdata.get_namespace", return_value={"spec": {biz_field: 591}}
    )
    channel = {"kind": "KafkaChannel", "namespace": "kafka_project", "name": "original_kafka"}
    get = mocker.patch(
        "metadata.models.data_source.api.bkdata.get_data_link",
        side_effect=[
            {"metadata": {"name": name}, "spec": {"bizId": 2, "eventType": "metric", "predefined": None}},
            {"metadata": {"annotations": annotations}, "spec": {"channel": channel}},
        ],
    )
    apply = mocker.patch("metadata.models.data_source.api.bkdata.apply_data_link")
    source.apply_to_namespace("shared")
    project.assert_called_once_with(bk_tenant_id=source.bk_tenant_id, name="shared")
    spec = apply.call_args.kwargs["config"][0]["spec"]
    assert spec["bizId"] == 591
    assert spec["predefined"]["dataId"] == source.bk_data_id
    assert spec["predefined"]["topic"] == expected_topic
    assert spec["predefined"]["channel"] == channel
    get.assert_called_with(
        bk_tenant_id=source.bk_tenant_id, namespace="bkmonitor", kind="channelbindings", name=f"{name}_default"
    )

    project.return_value = {"spec": {"bk_biz_id": None}}
    with pytest.raises(ValueError, match="未配置所属业务"):
        source.apply_to_namespace("unbound")
    apply.assert_called_once()


@pytest.mark.parametrize(("multi_tenant", "tenant"), [(True, "tenant-a"), (False, "default")])
def test_get_namespace_url(settings, multi_tenant, tenant):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    url = GetNamespace().get_request_url({"bk_tenant_id": "tenant-a", "name": "shared"})
    assert url.endswith(f"/v4/tenants/{tenant}/namespaces/shared")


def test_resource_tenant_scope(mocker, source):
    get = mocker.patch.object(models.DataSource.objects, "get", return_value=source)
    apply = mocker.patch.object(source, "apply_to_namespace", return_value={"name": "bkm_did_960001_src"})
    params = dict(bk_tenant_id="system", bk_data_id=960001, target_namespace="shared", bk_biz_id=591)
    assert ApplyDataSourceResource().perform_request(params) == {"name": "bkm_did_960001_src"}
    get.assert_called_once_with(bk_tenant_id="system", bk_data_id=960001)
    apply.assert_called_once_with(target_namespace="shared", bk_biz_id=591)
    get.side_effect = models.DataSource.DoesNotExist
    with pytest.raises(ValueError, match="数据源不存在"):
        ApplyDataSourceResource().perform_request(params)


@pytest.mark.parametrize("optional", [{}, {"bk_biz_id": 591}])
def test_resource_parameters_without_source(mocker, optional):
    mocker.patch("bkmonitor.utils.serializers.get_request_tenant_id", return_value="system")
    serializer = ApplyDataSourceResource.RequestSerializer(
        data={"bk_data_id": 960001, "target_namespace": "shared", **optional}
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == dict(
        bk_tenant_id="system", bk_data_id=960001, target_namespace="shared", **optional
    )


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
