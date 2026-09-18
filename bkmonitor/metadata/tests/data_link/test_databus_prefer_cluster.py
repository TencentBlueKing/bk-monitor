import json
from copy import deepcopy

import pytest

from metadata import models
from metadata.models.data_link import DataLink
from metadata.models.data_link.constants import DataLinkKind

pytestmark = pytest.mark.django_db(databases="__all__")

TABLE_ID = "bklog.prefer_cluster"
CLUSTER_NAME = "eslog-tencent-gamelifeapm-1"


@pytest.fixture
def data_link(settings):
    settings.ENABLE_MULTI_TENANT_MODE = True
    settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = []
    return DataLink(
        data_link_name="prefer_cluster_test",
        bk_tenant_id="tencent",
        namespace="bklog",
        table_ids=[TABLE_ID],
        data_link_strategy=DataLink.BK_STANDARD_V2_TIME_SERIES,
    )


def create_option(value, bk_tenant_id="tencent"):
    return models.ResultTableOption.create_option(
        table_id=TABLE_ID,
        bk_tenant_id=bk_tenant_id,
        name=models.ResultTableOption.OPTION_DATABUS_PREFER_CLUSTER,
        value=value,
        creator="system",
    )


@pytest.mark.parametrize("multi_tenant", [True, False])
def test_prefer_cluster_defaults(data_link, settings, multi_tenant):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    create_option({"name": CLUSTER_NAME})

    expected = {"kind": "DatabusCluster", "namespace": "bklog", "name": CLUSTER_NAME}
    if multi_tenant:
        expected["tenant"] = "tencent"
    assert data_link._get_databus_prefer_cluster() == expected


@pytest.mark.parametrize("multi_tenant", [True, False])
def test_prefer_cluster_explicit_reference(data_link, settings, multi_tenant):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    value = {"kind": "DatabusCluster", "tenant": "shared", "namespace": "other", "name": CLUSTER_NAME}
    create_option(value)

    assert data_link._get_databus_prefer_cluster() == value


def test_prefer_cluster_is_tenant_scoped(data_link):
    create_option({"name": "other-cluster"}, bk_tenant_id="other")
    assert data_link._get_databus_prefer_cluster() is None

    create_option({"name": CLUSTER_NAME})
    assert data_link._get_databus_prefer_cluster()["name"] == CLUSTER_NAME


@pytest.mark.parametrize("table_ids", [[], ["", None], [TABLE_ID, "bklog.other"]])
def test_prefer_cluster_skips_ambiguous_tables(data_link, mocker, table_ids):
    data_link.table_ids = table_ids
    query = mocker.patch.object(models.ResultTableOption.objects, "filter")

    assert data_link._get_databus_prefer_cluster() is None
    query.assert_not_called()


def test_prefer_cluster_deduplicates_table_ids(data_link):
    data_link.table_ids = [TABLE_ID, "", TABLE_ID, None]
    create_option({"name": CLUSTER_NAME})

    assert data_link._get_databus_prefer_cluster()["name"] == CLUSTER_NAME


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"tenant": "tencent"},
        {"name": ""},
        {"name": "  "},
        {"name": 123},
        {"name": None},
        {"name": CLUSTER_NAME, "kind": "KafkaChannel"},
        {"name": CLUSTER_NAME, "namespace": ""},
        {"name": CLUSTER_NAME, "tenant": None},
        {"name": CLUSTER_NAME, "unknown": "value"},
        [CLUSTER_NAME],
        CLUSTER_NAME,
        False,
        123,
    ],
)
def test_invalid_prefer_cluster_fails_before_writes(data_link, mocker, value):
    create_option(value)
    compose = mocker.patch.object(data_link, "compose_configs")
    apply = mocker.patch.object(data_link, "apply_data_link_with_retry")
    declare = mocker.patch.object(models.BkBaseResultTable.objects, "get_or_create")

    with pytest.raises(ValueError, match="invalid databus_prefer_cluster") as error:
        data_link.apply_data_link(bk_biz_id=2, data_source=None, table_id=TABLE_ID, storage_cluster_name="vm")

    assert "bk_tenant_id(tencent)" in str(error.value)
    assert TABLE_ID in str(error.value)
    compose.assert_not_called()
    apply.assert_not_called()
    declare.assert_not_called()


def test_prefer_cluster_decode_error_has_context(data_link):
    option = create_option({"name": CLUSTER_NAME})
    option.value = "{invalid json"
    option.save(update_fields=["value"])

    with pytest.raises(ValueError, match="cannot decode option value") as error:
        data_link._get_databus_prefer_cluster()

    assert isinstance(error.value.__cause__, json.JSONDecodeError)


@pytest.mark.parametrize("configured", [True, False])
def test_apply_prefer_cluster_after_merge_without_data_source(data_link, mocker, configured):
    if configured:
        create_option({"name": CLUSTER_NAME})
    kinds = [DataLinkKind.RESULTTABLE.value, DataLinkKind.DATABUS.value, DataLinkKind.DATABUS.value]
    configs = [
        {
            "kind": kind,
            "metadata": {"name": f"component-{index}", "namespace": "bklog", "tenant": "tencent"},
            "spec": {"maintainers": ["system"]},
        }
        for index, kind in enumerate(kinds)
    ]
    legacy_cluster = {"kind": "DatabusCluster", "tenant": "old", "namespace": "legacy", "name": "old"}

    def existing_config(kind, name, namespace):
        return {
            "kind": kind,
            "metadata": {"name": name, "namespace": namespace},
            "spec": {"preferCluster": deepcopy(legacy_cluster), "external": "keep"},
        }

    mocker.patch.object(data_link, "compose_configs", return_value=configs)
    mocker.patch.object(data_link, "get_existing_component_config", side_effect=existing_config)
    apply = mocker.patch.object(data_link, "apply_data_link_with_retry", return_value={"status": "success"})

    data_link.apply_data_link(bk_biz_id=2, data_source=None, table_id=TABLE_ID, storage_cluster_name="vm")

    applied_configs = apply.call_args.args[0]
    expected = {"kind": "DatabusCluster", "tenant": "tencent", "namespace": "bklog", "name": CLUSTER_NAME}
    for config in applied_configs:
        assert config["spec"]["maintainers"] == ["system"]
        assert config["spec"]["external"] == "keep"
        if configured and config["kind"] == DataLinkKind.DATABUS.value:
            assert config["spec"]["preferCluster"] == expected
        else:
            assert config["spec"]["preferCluster"] == legacy_cluster
    assert applied_configs[1]["spec"]["preferCluster"] is not applied_configs[2]["spec"]["preferCluster"]


def test_apply_without_prefer_cluster_does_not_add_field(data_link, mocker):
    config = {
        "kind": DataLinkKind.DATABUS.value,
        "metadata": {"name": "databus", "namespace": "bklog"},
        "spec": {},
    }
    mocker.patch.object(data_link, "compose_configs", return_value=[config])
    mocker.patch.object(data_link, "get_existing_component_config", return_value=None)
    apply = mocker.patch.object(data_link, "apply_data_link_with_retry", return_value={"status": "success"})

    data_link.apply_data_link(bk_biz_id=2, data_source=None, table_id=TABLE_ID, storage_cluster_name="vm")

    assert "preferCluster" not in apply.call_args.args[0][0]["spec"]
