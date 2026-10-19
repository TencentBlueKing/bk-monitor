import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connections, router

from metadata import models


pytestmark = pytest.mark.django_db(databases="__all__")
migration = importlib.import_module("metadata.migrations.0279_repair_system_base_metric_units")
OFFSET = "host_timesync_query_seconds_avg"
# Explicit expectations for the metrics emitted by timesync and selfstats.
EXPECTED_UNITS = {
    "host_timesync_query_seconds_min": "s",
    "host_timesync_query_seconds_max": "s",
    "host_timesync_query_seconds_avg": "s",
    "host_timesync_query_count": "none",
    "host_timesync_query_err": "none",
    "bkmonitorbeat_version": "none",
    "bkmonitorbeat_uptime": "s",
    "bkmonitorbeat_reload_total": "none",
    "bkmonitorbeat_running_tasks": "none",
    "go_gc_duration_seconds": "s",
    "go_gc_duration_seconds_sum": "s",
    "go_gc_duration_seconds_count": "none",
    "go_goroutines": "none",
    "go_info": "none",
    "go_memstats_alloc_bytes_total": "bytes",
    "go_memstats_heap_idle_bytes": "bytes",
    "go_memstats_heap_released_bytes": "bytes",
    "go_memstats_next_gc_bytes": "bytes",
    "go_threads": "none",
    "process_cpu_seconds_total": "s",
    "process_open_fds": "none",
    "process_resident_memory_bytes": "bytes",
}


@pytest.fixture
def group(mocker):
    mocker.patch.object(models.TimeSeriesGroup, "is_auto_discovery", return_value=True)
    return models.TimeSeriesGroup.objects.create(
        bk_tenant_id="system",
        bk_biz_id=2,
        bk_data_id=1100030,
        table_id="bkmonitor_time_series_1100030.__default__",
        time_series_group_name="System base metrics",
        is_split_measurement=True,
    )


def discover(group, *names):
    models.TimeSeriesMetric.bulk_refresh_ts_metrics(
        group,
        [{"field_name": name, "tag_list": [], "scope_id": 1} for name in names],
    )


def create_metric(group, name=OFFSET, **kwargs):
    # Legacy metric tables can differ from the group's result table naming.
    prefix = "2_bkmonitor_time_series_1100030" if name.startswith("host_timesync_") else "timesync"
    kwargs.setdefault("table_id", f"{prefix}.{name}")
    return models.TimeSeriesMetric.objects.create(group_id=group.pk, field_name=name, **kwargs)


def create_rt_field(group, unit="", tenant=None, name=OFFSET):
    return models.ResultTableField.objects.create(
        bk_tenant_id=tenant or group.bk_tenant_id,
        table_id=group.table_id,
        field_name=name,
        field_type="float",
        tag="metric",
        unit=unit,
        is_config_by_user=True,
    )


def migrate():
    connection = connections[router.db_for_write(models.TimeSeriesMetric)]
    migration.fill_system_base_metric_units(apps, SimpleNamespace(connection=connection))


def test_discovery_assigns_units_and_preserves_unknown_metrics(group):
    discover(group, *EXPECTED_UNITS, "unknown_seconds")
    configs = dict(models.TimeSeriesMetric.objects.filter(group_id=group.pk).values_list("field_name", "field_config"))
    assert configs == {**{name: {"unit": unit} for name, unit in EXPECTED_UNITS.items()}, "unknown_seconds": {}}


@pytest.mark.parametrize(
    "overrides",
    [
        {"bk_tenant_id": "another-tenant"},
        {"bk_biz_id": 0},
        {"table_id": "timesync.__default__"},
    ],
)
def test_builtin_identity_is_independent_of_group_ownership_and_table(group, overrides):
    for key, value in overrides.items():
        setattr(group, key, value)
    group.save(update_fields=list(overrides))
    old = create_metric(group)
    migrate()
    old.refresh_from_db()
    assert old.field_config == {"unit": "s"}
    discover(group, OFFSET, "bkmonitorbeat_uptime")
    assert models.TimeSeriesMetric.objects.get(group_id=group.pk, field_name="bkmonitorbeat_uptime").field_config == {
        "unit": "s"
    }


def test_other_data_source_with_identical_names_is_unchanged(group):
    group.bk_data_id = 12345
    group.save(update_fields=["bk_data_id"])
    old = create_metric(group)
    migrate()
    discover(group, OFFSET, "bkmonitorbeat_uptime")
    old.refresh_from_db()
    assert old.field_config == {}
    assert models.TimeSeriesMetric.objects.get(group_id=group.pk, field_name="bkmonitorbeat_uptime").field_config == {}


def test_discovery_keeps_legacy_unit_and_readers_use_it(group):
    create_rt_field(group, unit="ms")
    create_rt_field(group, unit="bytes", tenant="another-tenant")
    discover(group, OFFSET)
    metric = models.TimeSeriesMetric.objects.get(group_id=group.pk, field_name=OFFSET)
    assert metric.field_config == {"unit": "ms"}
    assert metric.to_metric_info(group=group)["unit"] == "ms"
    assert metric.to_metric_info_with_label(group=group)["unit"] == "ms"


@pytest.mark.parametrize("unit", [None, "", "ms"])
def test_disabled_builtin_restores_unit_without_losing_settings(group, unit):
    config = {"alias": "Clock offset", "interval": 60, "aggregate_method": "AVG", "disabled": True}
    if unit is not None:
        config["unit"] = unit
    metric = create_metric(group, scope_id=0, field_config=config)
    discover(group, OFFSET)
    metric.refresh_from_db()
    assert metric.scope_id == 1
    assert metric.field_config == {
        "alias": "Clock offset",
        "interval": 60,
        "aggregate_method": "AVG",
        "unit": unit or "s",
    }


def test_disabled_builtin_uses_legacy_unit(group):
    create_rt_field(group, unit="ms")
    metric = create_metric(group, scope_id=0, field_config={"unit": "", "disabled": True})
    discover(group, OFFSET)
    metric.refresh_from_db()
    assert metric.field_config == {"unit": "ms"}


def test_existing_active_config_is_not_overwritten(group):
    metric = create_metric(group, scope_id=1, field_config={"unit": "ms", "alias": "Clock offset"})
    discover(group, OFFSET)
    metric.refresh_from_db()
    assert metric.field_config == {"unit": "ms", "alias": "Clock offset"}


def test_migration_fills_only_empty_known_units_and_is_idempotent(group):
    empty = create_metric(group, field_config={"unit": "", "alias": "Clock offset", "disabled": True}, scope_id=0)
    missing = create_metric(group, "process_resident_memory_bytes", field_config={"interval": 60})
    configured = create_metric(group, "bkmonitorbeat_uptime", field_config={"unit": "ms"})
    unknown = create_metric(group, "unknown_seconds", field_config={"unit": ""})
    original_time = empty.last_modify_time
    for _ in range(2):
        migrate()
        for metric in (empty, missing, configured, unknown):
            metric.refresh_from_db()
        assert empty.field_config == {"unit": "s", "alias": "Clock offset", "disabled": True}
        assert empty.scope_id == 0
        assert empty.last_modify_time == original_time
        assert missing.field_config == {"unit": "bytes", "interval": 60}
        assert configured.field_config == {"unit": "ms"}
        assert unknown.field_config == {"unit": ""}

    discover(group, OFFSET)
    empty.refresh_from_db()
    assert empty.field_config == {"unit": "s", "alias": "Clock offset"}


def test_migration_keeps_legacy_unit_and_tenant_isolation(group):
    create_rt_field(group, unit="ms")
    create_rt_field(group, unit="bytes", tenant="another-tenant")
    metric = create_metric(group)
    migrate()
    metric.refresh_from_db()
    assert metric.field_config == {"unit": "ms"}


def test_migration_covers_multiple_scopes_and_batches(group):
    models.TimeSeriesMetric.objects.bulk_create(
        [
            models.TimeSeriesMetric(group_id=group.pk, field_name=OFFSET, field_scope=f"scope-{i}", field_config={})
            for i in range(501)
        ]
    )
    migrate()
    configs = list(models.TimeSeriesMetric.objects.filter(group_id=group.pk).values_list("field_config", flat=True))
    assert len(configs) == 501
    assert all(config == {"unit": "s"} for config in configs)


def test_compensation_repairs_metrics_skipped_by_0278_and_restores_them(group):
    metrics = []
    for name in EXPECTED_UNITS:
        create_rt_field(group, name=name)
        metrics.append(create_metric(group, name, scope_id=0, field_config={"disabled": True, "alias": name}))
    original_tables = {metric.pk: metric.table_id for metric in metrics}
    previous = importlib.import_module("metadata.migrations.0278_system_base_metric_units")
    connection = connections[router.db_for_write(models.TimeSeriesMetric)]
    previous.fill_system_base_metric_units(apps, SimpleNamespace(connection=connection))
    assert all(
        "unit" not in config
        for config in models.TimeSeriesMetric.objects.filter(group_id=group.pk).values_list("field_config", flat=True)
    )

    migrate()
    for metric in metrics:
        metric.refresh_from_db()
        assert metric.field_config == {
            "disabled": True,
            "alias": metric.field_name,
            "unit": EXPECTED_UNITS[metric.field_name],
        }
        assert metric.scope_id == 0
        assert metric.table_id == original_tables[metric.pk]
        assert metric.to_metric_info(group=group)["unit"] == EXPECTED_UNITS[metric.field_name]
        assert metric.to_metric_info_with_label(group=group)["unit"] == EXPECTED_UNITS[metric.field_name]

    discover(group, *EXPECTED_UNITS)
    for metric in metrics:
        metric.refresh_from_db()
        assert metric.scope_id == 1
        assert metric.field_config == {"alias": metric.field_name, "unit": EXPECTED_UNITS[metric.field_name]}
    group.refresh_from_db()
    assert group.bk_biz_id == 2
