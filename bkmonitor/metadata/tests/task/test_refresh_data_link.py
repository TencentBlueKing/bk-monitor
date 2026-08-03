"""DataLink 组件状态批量刷新测试。"""

from unittest.mock import call

import pytest

from metadata import models
from metadata.models.data_link.constants import DataLinkResourceStatus
from metadata.task.refresh_data_link import refresh_data_link_status
from metadata.task.tasks import (
    _refresh_bkbase_result_table_statuses,
    _refresh_data_link_component_statuses,
)


def _remote_component(name: str, status: str) -> dict:
    return {"metadata": {"name": name}, "status": {"phase": status}}


def _create_bkbase_result_table(data_link_name: str, *, tenant: str = "system", status: str = "Creating"):
    return models.BkBaseResultTable.objects.create(
        bk_tenant_id=tenant,
        data_link_name=data_link_name,
        monitor_table_id=f"{data_link_name}.__default__",
        status=status,
    )


def _create_result_table_component(
    name: str,
    data_link_name: str,
    *,
    tenant: str = "system",
    namespace: str = "bkmonitor",
    status: str = "Creating",
):
    return models.ResultTableConfig.objects.create(
        bk_tenant_id=tenant,
        namespace=namespace,
        name=name,
        data_link_name=data_link_name,
        bk_biz_id=2,
        status=status,
    )


def _create_databus_component(name: str, data_link_name: str, *, status: str = "Creating"):
    return models.DataBusConfig.objects.create(
        bk_tenant_id="system",
        namespace="bkmonitor",
        name=name,
        data_link_name=data_link_name,
        data_id_name=f"{name}_data_id",
        bk_biz_id=2,
        status=status,
    )


def _refresh_and_aggregate():
    statuses_by_link, untrusted_links, biz_id_by_link, changed_count = _refresh_data_link_component_statuses()
    changed_bkbase_count = _refresh_bkbase_result_table_statuses(
        statuses_by_link=statuses_by_link,
        untrusted_links=untrusted_links,
        biz_id_by_link=biz_id_by_link,
    )
    return changed_count, changed_bkbase_count


@pytest.fixture(autouse=True)
def mock_status_metrics(mocker):
    mocker.patch("metadata.task.tasks.report_metadata_data_link_status_info")


def test_refresh_data_link_status_dispatches_task_without_records(mocker):
    delay = mocker.patch("metadata.task.refresh_data_link.bulk_refresh_data_link_status.delay")

    refresh_data_link_status()

    delay.assert_called_once_with()


@pytest.mark.django_db(databases="__all__")
def test_refresh_components_batches_by_tenant_namespace_and_kind(mocker):
    _create_result_table_component("rt_a", "link_a")
    _create_result_table_component("rt_b", "link_b")
    _create_result_table_component("rt_c", "link_c", tenant="tenant-a", namespace="bklog")

    list_data_link = mocker.patch("metadata.task.tasks.api.bkdata.list_data_link")

    def list_side_effect(**kwargs):
        if kwargs["bk_tenant_id"] == "system":
            return [
                _remote_component("rt_a", DataLinkResourceStatus.OK.value),
                _remote_component("rt_b", DataLinkResourceStatus.PENDING.value),
            ]
        return [_remote_component("rt_c", DataLinkResourceStatus.FAILED.value)]

    list_data_link.side_effect = list_side_effect

    _, _, _, changed_count = _refresh_data_link_component_statuses()

    assert changed_count == 3
    assert models.ResultTableConfig.objects.get(name="rt_a").status == DataLinkResourceStatus.OK.value
    assert models.ResultTableConfig.objects.get(name="rt_b").status == DataLinkResourceStatus.PENDING.value
    assert models.ResultTableConfig.objects.get(name="rt_c").status == DataLinkResourceStatus.FAILED.value
    assert list_data_link.call_args_list == [
        call(bk_tenant_id="system", namespace="bkmonitor", kind="resulttables"),
        call(bk_tenant_id="tenant-a", namespace="bklog", kind="resulttables"),
    ]


@pytest.mark.django_db(databases="__all__")
def test_refresh_marks_missing_component_and_link_terminated(mocker):
    component = _create_result_table_component("missing_rt", "terminated_link")
    bkbase_record = _create_bkbase_result_table("terminated_link")
    mocker.patch(
        "metadata.task.tasks.api.bkdata.list_data_link",
        return_value=[_remote_component("another_rt", DataLinkResourceStatus.OK.value)],
    )

    changed_count, changed_bkbase_count = _refresh_and_aggregate()

    component.refresh_from_db()
    bkbase_record.refresh_from_db()
    assert changed_count == 1
    assert changed_bkbase_count == 1
    assert component.status == DataLinkResourceStatus.TERMINATED.value
    assert bkbase_record.status == DataLinkResourceStatus.TERMINATED.value


@pytest.mark.django_db(databases="__all__")
def test_refresh_aggregates_mixed_component_status_as_pending(mocker):
    _create_result_table_component("mixed_rt", "mixed_link")
    _create_databus_component("mixed_databus", "mixed_link")
    bkbase_record = _create_bkbase_result_table("mixed_link", status=DataLinkResourceStatus.OK.value)

    def list_side_effect(**kwargs):
        if kwargs["kind"] == "resulttables":
            return [_remote_component("mixed_rt", DataLinkResourceStatus.OK.value)]
        return [_remote_component("mixed_databus", DataLinkResourceStatus.FAILED.value)]

    mocker.patch("metadata.task.tasks.api.bkdata.list_data_link", side_effect=list_side_effect)

    _refresh_and_aggregate()

    bkbase_record.refresh_from_db()
    assert bkbase_record.status == DataLinkResourceStatus.PENDING.value


@pytest.mark.django_db(databases="__all__")
def test_refresh_aggregates_all_ok_components_as_ok(mocker):
    _create_result_table_component("ok_rt", "ok_link")
    _create_databus_component("ok_databus", "ok_link")
    bkbase_record = _create_bkbase_result_table("ok_link")

    def list_side_effect(**kwargs):
        name = "ok_rt" if kwargs["kind"] == "resulttables" else "ok_databus"
        return [_remote_component(name, DataLinkResourceStatus.OK.value)]

    mocker.patch("metadata.task.tasks.api.bkdata.list_data_link", side_effect=list_side_effect)

    _refresh_and_aggregate()

    bkbase_record.refresh_from_db()
    assert bkbase_record.status == DataLinkResourceStatus.OK.value


@pytest.mark.parametrize(
    "remote_result",
    [
        [],
        [{}],
        [{"metadata": {"name": "safe_rt"}, "status": {}}],
        "invalid",
    ],
)
@pytest.mark.django_db(databases="__all__")
def test_refresh_skips_empty_or_invalid_batch(mocker, remote_result):
    component = _create_result_table_component("safe_rt", "safe_link")
    bkbase_record = _create_bkbase_result_table("safe_link")
    component_modify_time = component.last_modify_time
    bkbase_modify_time = bkbase_record.last_modify_time
    mocker.patch("metadata.task.tasks.api.bkdata.list_data_link", return_value=remote_result)

    changed_count, changed_bkbase_count = _refresh_and_aggregate()

    component.refresh_from_db()
    bkbase_record.refresh_from_db()
    assert changed_count == 0
    assert changed_bkbase_count == 0
    assert component.status == DataLinkResourceStatus.CREATING.value
    assert component.last_modify_time == component_modify_time
    assert bkbase_record.status == DataLinkResourceStatus.CREATING.value
    assert bkbase_record.last_modify_time == bkbase_modify_time


@pytest.mark.django_db(databases="__all__")
def test_refresh_skips_failed_batch_and_link_aggregation(mocker):
    component = _create_result_table_component("failed_batch_rt", "failed_batch_link")
    bkbase_record = _create_bkbase_result_table("failed_batch_link")
    mocker.patch("metadata.task.tasks.api.bkdata.list_data_link", side_effect=RuntimeError("bkbase unavailable"))

    changed_count, changed_bkbase_count = _refresh_and_aggregate()

    component.refresh_from_db()
    bkbase_record.refresh_from_db()
    assert changed_count == 0
    assert changed_bkbase_count == 0
    assert component.status == DataLinkResourceStatus.CREATING.value
    assert bkbase_record.status == DataLinkResourceStatus.CREATING.value


@pytest.mark.django_db(databases="__all__")
def test_refresh_skips_link_aggregation_when_one_component_batch_is_untrusted(mocker):
    result_table = _create_result_table_component("partial_rt", "partial_link")
    databus = _create_databus_component("partial_databus", "partial_link")
    bkbase_record = _create_bkbase_result_table("partial_link")

    def list_side_effect(**kwargs):
        if kwargs["kind"] == "resulttables":
            return [_remote_component("partial_rt", DataLinkResourceStatus.OK.value)]
        return []

    mocker.patch("metadata.task.tasks.api.bkdata.list_data_link", side_effect=list_side_effect)

    changed_count, changed_bkbase_count = _refresh_and_aggregate()

    result_table.refresh_from_db()
    databus.refresh_from_db()
    bkbase_record.refresh_from_db()
    assert changed_count == 1
    assert changed_bkbase_count == 0
    assert result_table.status == DataLinkResourceStatus.OK.value
    assert databus.status == DataLinkResourceStatus.CREATING.value
    assert bkbase_record.status == DataLinkResourceStatus.CREATING.value


@pytest.mark.django_db(databases="__all__")
def test_refresh_does_not_write_unchanged_status(mocker):
    component = _create_result_table_component(
        "unchanged_rt",
        "unchanged_link",
        status=DataLinkResourceStatus.OK.value,
    )
    bkbase_record = _create_bkbase_result_table("unchanged_link", status=DataLinkResourceStatus.OK.value)
    component_modify_time = component.last_modify_time
    bkbase_modify_time = bkbase_record.last_modify_time
    mocker.patch(
        "metadata.task.tasks.api.bkdata.list_data_link",
        return_value=[_remote_component("unchanged_rt", DataLinkResourceStatus.OK.value)],
    )

    changed_count, changed_bkbase_count = _refresh_and_aggregate()

    component.refresh_from_db()
    bkbase_record.refresh_from_db()
    assert changed_count == 0
    assert changed_bkbase_count == 0
    assert component.last_modify_time == component_modify_time
    assert bkbase_record.last_modify_time == bkbase_modify_time


@pytest.mark.django_db(databases="__all__")
def test_refresh_component_without_data_link_does_not_update_bkbase_status(mocker):
    component = _create_result_table_component("orphan_rt", "")
    bkbase_record = _create_bkbase_result_table("orphan_link")
    mocker.patch(
        "metadata.task.tasks.api.bkdata.list_data_link",
        return_value=[_remote_component("orphan_rt", DataLinkResourceStatus.OK.value)],
    )

    _refresh_and_aggregate()

    component.refresh_from_db()
    bkbase_record.refresh_from_db()
    assert component.status == DataLinkResourceStatus.OK.value
    assert bkbase_record.status == DataLinkResourceStatus.CREATING.value
