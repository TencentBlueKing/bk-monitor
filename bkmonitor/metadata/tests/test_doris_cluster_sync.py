import copy
import json

import pytest

from metadata.models import ClusterInfo
from metadata.models.data_link.constants import DataLinkKind
from metadata.models.data_link.data_link_configs import ClusterConfig
from metadata.resources.cluster import CreateClusterInfoResource, ModifyClusterInfoResource, UpdateRegisteredCluster
from metadata.task.bkbase import sync_bkbase_cluster_info
from metadata.task.constants import BKBASE_V4_KIND_STORAGE_CONFIGS


def make_cluster(**kwargs):
    values = dict(
        bk_tenant_id="system",
        cluster_name="doris-safe",
        cluster_type="doris",
        domain_name="doris.example.com",
        port=9030,
        username="user",
        password="secret",
        default_settings={"write_port": 8030},
        description="",
        is_default_cluster=False,
    )
    values.update(kwargs)
    return ClusterInfo(**values)


def make_config(cluster, **kwargs):
    return ClusterConfig(
        bk_tenant_id=cluster.bk_tenant_id,
        namespace="bklog",
        name=cluster.cluster_name,
        kind=DataLinkKind.DORIS.value,
        **kwargs,
    )


@pytest.mark.parametrize("multi_tenant", [True, False])
def test_compose_preserves_extensions_and_values(settings, multi_tenant):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    cluster = make_cluster(
        default_settings={"write_port": 8030, "shard_minutes": 0, "support_node_tag": False, "host": "ignored"}
    )
    origin = {
        "spec": {"extension": {"keep": True}, "description": "remote", "write_port": 9999},
        "metadata": {"tenant": "old"},
        "status": {"phase": "Ok"},
    }
    config = make_config(cluster, origin_config=origin)
    result = config.compose_doris_config(cluster)
    assert result["spec"]["host"] == cluster.domain_name
    assert result["spec"]["write_port"] == 8030
    assert result["spec"]["shard_minutes"] == 0
    assert result["spec"]["support_node_tag"] is False
    assert result["spec"]["extension"] == {"keep": True}
    assert result["spec"]["description"] == "remote"
    assert result["metadata"].get("tenant") == ("system" if multi_tenant else None)
    assert "status" not in result
    assert origin["spec"]["write_port"] == 9999


@pytest.mark.parametrize(
    "overrides",
    [
        {"default_settings": {}},
        {"default_settings": []},
        {"username": ""},
        {"password": ""},
        {"domain_name": ""},
        {"port": True},
        {"port": 0},
        {"port": 65536},
        {"default_settings": {"write_port": "8030"}},
        {"default_settings": {"write_port": 8030, "table_bucket_num": -1}},
        {"default_settings": {"write_port": 8030, "support_node_tag": 1}},
        {"default_settings": {"write_port": 8030, "expires": {}}},
    ],
)
def test_invalid_direct_sync_has_no_writes(mocker, overrides):
    get = mocker.patch.object(ClusterConfig.objects, "get_or_create")
    apply = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.apply_data_link")
    with pytest.raises(ValueError):
        ClusterConfig.sync_cluster_config(make_cluster(**overrides))
    get.assert_not_called()
    apply.assert_not_called()


@pytest.mark.django_db(databases="__all__")
def test_create_and_modify_doris(mocker):
    apply = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.apply_data_link")
    cluster = ClusterInfo.create_cluster(
        bk_tenant_id="system",
        cluster_name="new-doris",
        cluster_type="doris",
        domain_name="new.example.com",
        port=9030,
        username="user",
        password="secret",
        default_settings={"write_port": 8030, "shard_minutes": 1},
        registered_system="test",
        operator="admin",
    )
    config = ClusterConfig.objects.get(name=cluster.cluster_name)
    assert config.origin_config == apply.call_args.kwargs["config"][0]
    assert cluster.registered_to_bkbase
    apply.reset_mock()
    cluster.modify(operator="admin", description="new", display_name="Doris", custom_option="{}")
    apply.assert_not_called()
    cluster.modify(operator="admin", default_settings={"table_bucket_num": 0})
    assert apply.call_count == 1
    cluster.refresh_from_db()
    assert cluster.default_settings == {"write_port": 8030, "shard_minutes": 1, "table_bucket_num": 0}
    apply.reset_mock()
    cluster.modify(operator="admin", password="secret", default_settings={"table_bucket_num": 0})
    apply.assert_not_called()
    cluster.modify(operator="admin", version="3.0")
    assert apply.call_args.kwargs["config"][0]["spec"]["version"] == "3.0"


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize("failure", ["missing", "remote"])
def test_modify_failure_rolls_back_all_fields(mocker, failure):
    cluster = make_cluster()
    cluster.save()
    config = make_config(cluster, origin_config={"spec": {"write_port": 8030}})
    config.save()
    apply = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.apply_data_link")
    if failure == "remote":
        apply.side_effect = RuntimeError("unavailable")
    with pytest.raises((ValueError, RuntimeError)):
        cluster.modify(
            operator="admin",
            description="changed",
            password="new",
            default_settings={"write_port": None} if failure == "missing" else {},
        )
    cluster.refresh_from_db()
    config.refresh_from_db()
    assert cluster.description == ""
    assert cluster.password == "secret"
    assert cluster.default_settings == {"write_port": 8030}
    assert config.origin_config == {"spec": {"write_port": 8030}}
    assert not cluster.registered_to_bkbase
    if failure == "missing":
        apply.assert_not_called()


@pytest.mark.django_db(databases="__all__")
def test_legacy_requires_explicit_completion(mocker):
    apply = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.apply_data_link")
    cluster = make_cluster(default_settings={})
    cluster.save()
    make_config(cluster, origin_config={"spec": {"write_port": 8030}}).save()
    cluster.modify(operator="admin", description="allowed")
    with pytest.raises(ValueError, match="write_port"):
        cluster.modify(operator="admin", password="new")
    apply.assert_not_called()
    cluster.refresh_from_db()
    cluster.modify(operator="admin", password="new", default_settings={"write_port": 8030})
    apply.assert_called_once()


@pytest.mark.django_db(databases="__all__")
def test_es_sync_uses_normalized_changes(mocker):
    sync = mocker.patch.object(ClusterConfig, "sync_cluster_config")
    cluster = make_cluster(cluster_type=ClusterInfo.TYPE_ES, schema="https")
    cluster.save()
    cluster.modify(operator="admin", schema=" HTTPS ", description="local", version="7.1")
    sync.assert_not_called()
    cluster.modify(operator="admin", schema="http")
    sync.assert_called_once()


@pytest.mark.parametrize("resource", [ModifyClusterInfoResource, UpdateRegisteredCluster])
def test_modify_serializer_preserves_absent_fields(resource):
    serializer = resource.RequestSerializer(
        data={"bk_tenant_id": "system", "cluster_id": 1, "operator": "admin", "description": "local"}
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data.get("default_settings") is None
    assert serializer.validated_data.get("username") is None
    assert serializer.validated_data.get("password") is None


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize("update", [True, False])
def test_reverse_sync_merges_only_present_fields(update):
    cluster = make_cluster(default_settings={"write_port": 8030, "shard_minutes": 1, "extension": "keep"})
    cluster.save()
    original = copy.deepcopy(cluster.default_settings)
    mapping = next(c["field_mappings"] for c in BKBASE_V4_KIND_STORAGE_CONFIGS if c["cluster_type"] == "doris")
    sync_bkbase_cluster_info(
        "system",
        {
            "metadata": {"name": cluster.cluster_name, "namespace": "bklog"},
            "spec": {
                "host": cluster.domain_name,
                "port": 9030,
                "user": "user",
                "password": "secret",
                "shard_minutes": 0,
            },
        },
        mapping,
        "doris",
        update=update,
    )
    cluster.refresh_from_db()
    assert cluster.default_settings == ({**original, "shard_minutes": 0} if update else original)


@pytest.mark.django_db(databases="__all__")
def test_modify_api_preserves_legacy_name_and_absent_credentials(mocker):
    mocker.patch("metadata.resources.cluster.get_request", return_value=None)
    mocker.patch("metadata.resources.cluster.get_app_code_by_request", return_value="test")
    apply = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.apply_data_link")
    cluster = make_cluster(cluster_name="legacy.doris", default_settings={})
    cluster.save()
    result = ModifyClusterInfoResource().request(
        bk_tenant_id="system", cluster_id=cluster.cluster_id, operator="admin", custom_option="{}"
    )
    cluster.refresh_from_db()
    assert cluster.cluster_name == "legacy.doris"
    assert cluster.password == "secret"
    assert result["cluster_config"]["default_settings"] == {}
    apply.assert_not_called()
    ModifyClusterInfoResource().request(
        bk_tenant_id="system",
        cluster_id=cluster.cluster_id,
        operator="admin",
        auth_info={"username": "new-user"},
        default_settings={"write_port": 8030},
        version="3.0",
    )
    assert apply.call_args.kwargs["config"][0]["spec"]["password"] == "secret"
    assert apply.call_args.kwargs["config"][0]["spec"]["version"] == "3.0"


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize("failure", ["missing", "remote"])
def test_create_api_failure_does_not_leave_records(mocker, failure):
    mocker.patch("metadata.resources.cluster.get_request", return_value=None)
    mocker.patch("metadata.resources.cluster.get_app_code_by_request", return_value="test")
    apply = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.apply_data_link")
    if failure == "remote":
        apply.side_effect = RuntimeError("unavailable")
    serializer = CreateClusterInfoResource.RequestSerializer(
        data={
            "bk_tenant_id": "system",
            "cluster_name": "failed-doris",
            "cluster_type": "doris",
            "domain_name": "failed.example.com",
            "port": 9030,
            "operator": "admin",
            "auth_info": {"username": "user", "password": "secret"},
            "default_settings": {} if failure == "missing" else {"write_port": 8030},
        }
    )
    assert serializer.is_valid(), serializer.errors
    with pytest.raises((ValueError, RuntimeError)):
        CreateClusterInfoResource().perform_request(dict(serializer.validated_data))
    assert not ClusterInfo.objects.filter(cluster_name="failed-doris").exists()
    assert not ClusterConfig.objects.filter(name="failed-doris").exists()
    if failure == "missing":
        apply.assert_not_called()


def test_internal_update_serializer_does_not_inject_empty_values():
    from api.metadata.default import UpdateRegisteredClusterResource

    serializer = UpdateRegisteredClusterResource.RequestSerializer(
        data={"cluster_id": 1, "operator": "admin", "description": "local"}
    )
    assert serializer.is_valid(), serializer.errors
    assert "username" not in serializer.validated_data
    assert "password" not in serializer.validated_data
    assert "default_settings" not in serializer.validated_data


@pytest.mark.parametrize("version,expected", [("3.0", "3.0"), ("", "2.0")])
def test_surrealdb_version_precedence(version, expected):
    cluster = make_cluster(cluster_type="surrealdb", version=version, default_settings={"version": "2.0"})
    assert make_config(cluster).compose_surrealdb_config(cluster)["spec"]["version"] == expected


@pytest.mark.django_db(databases="__all__")
def test_es_legacy_name_changes_only_with_sync(mocker):
    mocker.patch("metadata.resources.cluster.get_request", return_value=None)
    mocker.patch("metadata.resources.cluster.get_app_code_by_request", return_value="test")
    apply = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.apply_data_link")
    cluster = make_cluster(cluster_type="elasticsearch", cluster_name="legacy.es", schema="http")
    cluster.save()
    request = dict(bk_tenant_id="system", cluster_id=cluster.cluster_id, operator="admin")
    ModifyClusterInfoResource().request(**request, custom_option="{}")
    cluster.refresh_from_db()
    assert cluster.cluster_name == "legacy.es"
    apply.assert_not_called()
    assert not ClusterConfig.objects.filter(name=f"auto_cluster_name_{cluster.cluster_id}").exists()

    ModifyClusterInfoResource().request(**request, auth_info={"password": "new-secret"})
    cluster.refresh_from_db()
    assert cluster.cluster_name == f"auto_cluster_name_{cluster.cluster_id}"
    apply.assert_called_once()
    assert apply.call_args.kwargs["config"][0]["metadata"]["name"] == cluster.cluster_name
    assert ClusterConfig.objects.get(name=cluster.cluster_name).origin_config["spec"]["password"] == "new-secret"


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize(
    "original,changed",
    [
        ({"write_port": 8030}, {"write_port": 8030.0}),
        ({"write_port": 8030, "support_node_tag": False}, {"support_node_tag": 0}),
        ({"write_port": 8030, "shard_minutes": 1}, {"shard_minutes": True}),
        ({"write_port": 8030, "expires": {"maxExpire": 90}}, {"expires": {"maxExpire": 90.0}}),
    ],
)
def test_doris_equal_values_with_invalid_types_are_rejected(mocker, original, changed):
    apply = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.apply_data_link")
    cluster = make_cluster(default_settings=original)
    cluster.save()
    with pytest.raises(ValueError):
        cluster.modify(operator="admin", description="must roll back", default_settings=changed)
    cluster.refresh_from_db()
    assert cluster.description == ""
    assert json.dumps(cluster.default_settings, sort_keys=True) == json.dumps(original, sort_keys=True)
    apply.assert_not_called()
    assert not ClusterConfig.objects.filter(name=cluster.cluster_name).exists()
