from django.db import migrations


# Frozen units for bkmonitorbeat timesync and selfstats metrics. Keep historical
# migrations independent of the runtime builtin metric catalog.
METRIC_UNITS = {
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


def fill_system_base_metric_units(apps, schema_editor):
    TimeSeriesGroup = apps.get_model("metadata", "TimeSeriesGroup")
    TimeSeriesMetric = apps.get_model("metadata", "TimeSeriesMetric")
    ResultTableField = apps.get_model("metadata", "ResultTableField")
    db_alias = schema_editor.connection.alias

    groups = TimeSeriesGroup.objects.using(db_alias).filter(
        bk_tenant_id="system",
        bk_biz_id=0,
        bk_data_id=1100030,
        table_id="bkmonitor_time_series_1100030.__default__",
    )
    for group in groups.iterator():
        units = METRIC_UNITS.copy()
        units.update(
            ResultTableField.objects.using(db_alias)
            .filter(bk_tenant_id=group.bk_tenant_id, table_id=group.table_id, field_name__in=units)
            .exclude(unit="")
            .values_list("field_name", "unit")
        )
        metrics = (
            TimeSeriesMetric.objects.using(db_alias)
            .filter(group_id=group.pk, field_name__in=units)
            .only("field_id", "field_name", "field_config")
        )
        updates = []
        for metric in metrics.iterator(chunk_size=500):
            field_config = dict(metric.field_config or {})
            if field_config.get("unit"):
                continue
            field_config["unit"] = units[metric.field_name]
            metric.field_config = field_config
            updates.append(metric)
            if len(updates) == 500:
                TimeSeriesMetric.objects.using(db_alias).bulk_update(updates, ["field_config"], batch_size=500)
                updates = []
        if updates:
            TimeSeriesMetric.objects.using(db_alias).bulk_update(updates, ["field_config"], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [("metadata", "0277_vm_query_cluster_config")]

    operations = [migrations.RunPython(fill_system_base_metric_units, migrations.RunPython.noop)]
