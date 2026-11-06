"""ResultTableOption 标签的租户隔离、校验及下发优先级。"""

import json
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from metadata.models import ResultTableOption
from metadata.models.data_link import DataLink
from metadata.models.data_link.constants import DataLinkKind


@pytest.mark.parametrize("table_ids", [[], [""], ["a", "b"]])
def test_skip_ambiguous_table_without_query(mocker, table_ids):
    query = mocker.patch.object(ResultTableOption.objects, "filter")
    assert DataLink(table_ids=table_ids)._get_databus_option_labels() == {}
    query.assert_not_called()


@pytest.mark.parametrize("value", [None, {}, {"team": "monitor", "empty": ""}])
def test_read_option_with_tenant_and_unique_table(mocker, value):
    option = None if value is None else ResultTableOption(value=json.dumps(value), value_type="dict")
    query = mocker.patch.object(ResultTableOption.objects, "filter")
    query.return_value.first.return_value = option
    link = DataLink(bk_tenant_id="tenant-a", table_ids=["", "table", "table"])
    assert link._get_databus_option_labels() == (value or {})
    query.assert_called_once_with(bk_tenant_id="tenant-a", table_id="table", name="databus_labels")


@pytest.mark.parametrize("value", ["[]", '"text"', "null", '{"team": 1}', '{"team": true}', '{"": "value"}', "{"])
def test_invalid_option_fails_before_writes(mocker, value):
    query = mocker.patch.object(ResultTableOption.objects, "filter")
    query.return_value.first.return_value = ResultTableOption(value=value, value_type="dict")
    create = mocker.patch("metadata.models.bkdata.result_table.BkBaseResultTable.objects.get_or_create")
    compose = mocker.patch.object(DataLink, "compose_configs")
    apply = mocker.patch.object(DataLink, "apply_data_link_with_retry")
    with pytest.raises(ValueError, match="Invalid databus_labels.*tenant-a.*table"):
        DataLink(bk_tenant_id="tenant-a", table_ids=["table"]).apply_data_link()
    create.assert_not_called()
    compose.assert_not_called()
    apply.assert_not_called()


@pytest.mark.parametrize("has_data_source", [True, False])
@pytest.mark.parametrize("option_labels", [{}, {"team": "monitor", "bk-monitor/data-scene": "override"}])
def test_apply_option_labels_to_all_databuses_last(mocker, has_data_source, option_labels):
    link = DataLink(
        bk_tenant_id="tenant-a",
        table_ids=["table"],
        data_link_strategy=DataLink.BK_STANDARD_V2_TIME_SERIES,
        bk_data_id=0,
    )
    query = mocker.patch.object(ResultTableOption.objects, "filter")
    query.return_value.first.return_value = ResultTableOption(value=json.dumps(option_labels), value_type="dict")
    mocker.patch(
        "metadata.models.bkdata.result_table.BkBaseResultTable.objects.get_or_create",
        return_value=(SimpleNamespace(), False),
    )
    mocker.patch("metadata.models.data_link.data_link.is_reuse_enabled_for", return_value=False)
    mocker.patch("metadata.models.data_link.data_link.transaction.atomic", return_value=nullcontext())
    mocker.patch.object(link, "_get_compose_method", return_value=lambda data_source=None: None)
    configs = [
        {"kind": kind, "metadata": {"labels": {"team": "old", "external": "keep"}}}
        for kind in [DataLinkKind.DATABUS.value, DataLinkKind.DATABUS.value, "ResultTable", "VMStorageBinding"]
    ]
    mocker.patch.object(link, "compose_configs", return_value=configs)
    mocker.patch.object(link, "merge_existing_component_configs", side_effect=lambda configs: configs)
    mocker.patch.object(link, "_get_databus_monitor_label_table", return_value=None)
    mocker.patch(
        "metadata.models.data_link.data_link.compose_databus_monitor_labels",
        return_value={"bk-monitor/data-scene": "system"},
    )
    mocker.patch.object(link, "_get_absent_components_to_delete", return_value=[])
    mocker.patch.object(link, "_cleanup_absent_components")
    apply = mocker.patch.object(link, "apply_data_link_with_retry", return_value={})
    link.apply_data_link(data_source=SimpleNamespace() if has_data_source else None)
    payload = apply.call_args.args[0]
    expected = {"team": "old", "external": "keep"}
    if has_data_source:
        expected["bk-monitor/data-scene"] = "system"
    expected.update(option_labels)
    assert all(config["metadata"]["labels"] == expected for config in payload[:2])
    assert all(config["metadata"]["labels"] == {"team": "old", "external": "keep"} for config in payload[2:])


@pytest.mark.django_db(databases="__all__")
def test_same_table_options_are_isolated_by_tenant():
    for tenant, team in [("labels-tenant-a", "a"), ("labels-tenant-b", "b")]:
        ResultTableOption.objects.create(
            bk_tenant_id=tenant,
            table_id="labels.test",
            name=ResultTableOption.OPTION_DATABUS_LABELS,
            value_type=ResultTableOption.TYPE_DICT,
            value=json.dumps({"team": team}),
            creator="system",
        )
    for tenant, expected in [
        ("labels-tenant-a", {"team": "a"}),
        ("labels-tenant-b", {"team": "b"}),
        ("labels-tenant-c", {}),
    ]:
        assert DataLink(bk_tenant_id=tenant, table_ids=["labels.test"])._get_databus_option_labels() == expected
