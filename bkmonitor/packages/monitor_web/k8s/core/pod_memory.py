"""Pod memory gauges: prefer the cgroup total at each evaluation instant."""

POD_MEMORY_METRICS = frozenset(
    f"container_memory_{suffix}"
    for suffix in ("working_set_bytes", "usage_bytes", "rss", "cache", "mapped_file", "swap")
)

POD_MEMORY_IDENTITY = ("bcs_cluster_id", "namespace", "pod_name")
POD_MEMORY_DIMENSIONS = (*POD_MEMORY_IDENTITY, "workload_kind", "workload_name")


def pod_memory_usage(metric, filters, *, dimensions=POD_MEMORY_DIMENSIONS, time_shift=""):
    """Select independently per Pod and metric; an existing zero is authoritative.

    Explicit container selection is handled by callers, which query children only.
    Keep cluster in the matching identity even when the caller projects it away.
    """
    parent_filters = ",".join(filter(None, (filters, 'metrics_path="/metrics/cadvisor"')))
    child_filters = ",".join(filter(None, (filters, 'container_name!="",container_name!="POD"')))
    group_by = ", ".join(dict.fromkeys(dimensions))
    identity = ", ".join(POD_MEMORY_IDENTITY)
    parent = metric.replace("container_memory_", "pod_memory_", 1)
    return (
        f"(sum by ({group_by}) ({parent}{{{parent_filters}}} {time_shift}) "
        f"or on ({identity}) "
        f"sum by ({group_by}) ({metric}{{{child_filters}}} {time_shift}))"
    )
