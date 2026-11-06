"""Default display units for the platform's system base metrics.

The values are reported by bkmonitorbeat's timesync and selfstats tasks. Match
exact names: for example, a duration summary's count is not measured in seconds.
"""

# DataSource.bk_data_id is the globally unique identity of system_base_metric.
SYSTEM_BASE_DATA_ID = 1100030

SYSTEM_BASE_METRIC_UNITS = {
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
