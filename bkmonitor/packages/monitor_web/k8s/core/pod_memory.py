"""Pod memory gauges: prefer the cgroup total at each evaluation instant."""

POD_MEMORY_METRICS = frozenset(
    f"container_memory_{suffix}"
    for suffix in ("working_set_bytes", "usage_bytes", "rss", "cache", "mapped_file", "swap")
)

POD_MEMORY_IDENTITY = ("bcs_cluster_id", "namespace", "pod_name")
POD_MEMORY_DIMENSIONS = (*POD_MEMORY_IDENTITY, "workload_kind", "workload_name")


def pod_memory_usage(
    metric, filters, *, dimensions=POD_MEMORY_DIMENSIONS, time_shift="", marker="__bk_pod_memory_source"
):
    """Select independently per Pod and metric; an existing zero is authoritative.

    Explicit container selection is handled by callers, which query children only.
    Keep cluster in the matching identity even when the caller projects it away.
    UQ binds the parent branch through either metric name before selecting the
    parent by name. The fallback keeps the original child routing behavior.
    Aggregate before marking to avoid source-label collisions;
    the temporary marker must not be an output dimension.
    """
    parent_metric = metric.replace("container_memory_", "pod_memory_", 1)
    metric_filter = f'__name__=~"({parent_metric}|{metric})"'
    parent_filters = ",".join(filter(None, (metric_filter, filters, 'metrics_path="/metrics/cadvisor"')))
    child_filters = ",".join(filter(None, (filters, 'container_name!="",container_name!="POD"')))
    group_by = ", ".join(dict.fromkeys(dimensions))
    metric_group_by = ", ".join(dict.fromkeys(("__name__", *dimensions)))
    identity = ", ".join(POD_MEMORY_IDENTITY)
    parent = (
        f"sum by ({group_by}) ("
        f"label_replace(sum by ({metric_group_by}) ({{{parent_filters}}} {time_shift}), "
        f'"{marker}", "parent", "__name__", "{parent_metric}") '
        f'and on ({marker}) label_replace(vector(1), "{marker}", "parent", "__name__", ".*"))'
    )
    child = f"sum by ({group_by}) ({metric}{{{child_filters}}} {time_shift})"
    return f"({parent} or on ({identity}) {child})"
