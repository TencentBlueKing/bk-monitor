from apps.log_databus.handlers.storage import StorageHandler


def list_storage_clusters(params):
    params = params or {}
    page = _to_positive_int(params.get("page"), default=1)
    page_size = _to_positive_int(params.get("page_size"), default=100)
    bk_biz_id = _to_int(params.get("bk_biz_id"), default=0)
    cluster_id = _to_int(params.get("storage_cluster_id") or params.get("cluster_id"), default=None)
    keyword = str(params.get("keyword") or "").strip().lower()

    clusters = StorageHandler().list(bk_biz_id=bk_biz_id, cluster_id=cluster_id)
    items = [_serialize_cluster(cluster) for cluster in clusters]
    if keyword:
        items = [
            item
            for item in items
            if keyword in str(item.get("storage_cluster_id") or "").lower()
            or keyword in str(item.get("storage_cluster_name") or "").lower()
            or keyword in str(item.get("cluster_name") or "").lower()
            or keyword in str(item.get("domain_name") or "").lower()
        ]

    total = len(items)
    start = (page - 1) * page_size
    return {"items": items[start : start + page_size], "page": page, "page_size": page_size, "total": total}


def _serialize_cluster(cluster):
    cluster_config = cluster.get("cluster_config") or {}
    custom_option = cluster_config.get("custom_option") or {}
    hot_warm_config = custom_option.get("hot_warm_config") or {}
    cluster_id = _first_not_none(
        cluster.get("storage_cluster_id"),
        cluster.get("cluster_id"),
        cluster_config.get("cluster_id"),
    )
    cluster_name = _first_not_none(
        cluster.get("storage_cluster_name"),
        cluster.get("display_name"),
        cluster.get("cluster_name"),
        cluster_config.get("cluster_name"),
        cluster_config.get("name"),
    )
    return {
        "storage_cluster_id": cluster_id,
        "storage_cluster_name": cluster_name,
        "cluster_name": cluster_name,
        "domain_name": _first_not_none(cluster.get("domain_name"), cluster_config.get("domain_name")),
        "is_active": _first_not_none(cluster.get("is_active"), cluster_config.get("is_active"), True),
        "hot_warm_enabled": bool(
            _first_not_none(
                cluster.get("hot_warm_enabled"),
                cluster.get("enable_hot_warm"),
                hot_warm_config.get("is_enabled"),
                False,
            )
        ),
    }


def _to_positive_int(value, default):
    value = _to_int(value, default)
    if value < 1:
        return default
    return value


def _to_int(value, default):
    if value in (None, ""):
        return default
    return int(value)


def _first_not_none(*values):
    for value in values:
        if value is not None:
            return value
    return None
