"""解释实际已加载的发现规则，兼容多区间发布前后版本。"""

from django.conf import settings
from django.utils import timezone


def management_scope(cluster_id, bk_biz_id, source="BCSClusterInfo"):
    from metadata.task import bcs

    multi_range = hasattr(bcs, "get_discover_cluster_id_ranges")
    threshold = getattr(settings, "NEW_ENV_START_CLUSTER_ID", "")
    configured = getattr(settings, "NEW_ENV_CLUSTER_ID_RANGES", [])
    start = bcs.get_discover_start_cluster_id_suffix()
    argument = bcs.get_discover_cluster_id_ranges() if multi_range else start
    ranges = argument if multi_range else ([] if start is None else [{"start": start, "end": None}])
    managed = None if bk_biz_id is None else bcs.is_discover_managed_cluster(cluster_id, argument, bk_biz_id)
    if bk_biz_id is None:
        reason = "未取得业务归属，尚不能判定"
    elif bcs.is_discover_biz_blacklisted(bk_biz_id):
        reason = "业务命中黑名单"
    elif bcs.is_discover_biz_whitelisted(bk_biz_id):
        reason = "业务命中白名单，豁免编号限制"
    elif not ranges:
        reason = "未启用有效编号限制"
    elif bcs.get_bcs_cluster_id_suffix(cluster_id) is None:
        reason = "集群编号无法解析"
    else:
        reason = "编号命中纳管开区间" if managed else "编号不在纳管开区间内"
    return {
        "managed": managed,
        "reason": reason,
        "cluster_id": cluster_id,
        "bk_biz_id": bk_biz_id,
        "business_source": source,
        "rule_version": "ranges" if multi_range else "legacy_threshold",
        "effective_ranges": ranges,
        "config": {
            "NEW_ENV_CLUSTER_ID_RANGES": configured,
            "NEW_ENV_START_CLUSTER_ID": threshold,
            "NEW_ENV_CLUSTER_BLACK_LIST": settings.NEW_ENV_CLUSTER_BLACK_LIST,
            "NEW_ENV_CLUSTER_WHITE_LIST": settings.NEW_ENV_CLUSTER_WHITE_LIST,
        },
        "observed_at": timezone.now().isoformat(),
        "source": "rpc_process",
        "applies_to": ["discover_bcs_clusters", "refresh_bcs_monitor_info"],
    }
