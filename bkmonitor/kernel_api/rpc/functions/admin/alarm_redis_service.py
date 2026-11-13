"""告警 Redis 只读查询；不初始化节点，不改变进程路由状态。"""

import json
from string import Formatter


from alarm_backends.cluster import TargetType
from alarm_backends.core.cache import key as keys
from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.storage.redis import CACHE_BACKEND_CONF_MAP, Cache
from alarm_backends.core.storage.redis_cluster import setup_client
from bkmonitor.models import CacheNode, CacheRouter
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin.common import to_json_safe

MAX_CONTENT_BYTES = 1024 * 1024
BACKENDS = tuple(CACHE_BACKEND_CONF_MAP) + ("cache-strategy",)


def fail(message, code="ALARM_REDIS_ERROR", **details):
    raise CustomException(message=message, data={"code": code, **details})


def node_data(node):
    return {
        "id": node.id,
        "node_alias": node.node_alias or "",
        "cache_type": node.cache_type,
        "host": node.host,
        "port": node.port,
        "is_enable": node.is_enable,
        "is_default": node.is_default,
        "master_name": (node.connection_kwargs or {}).get("master_name"),
    }


def routes():
    rows = list(CacheRouter.objects.select_related("node").order_by("cluster_name", "strategy_score", "id"))
    floors = {}
    result = []
    for row in rows:
        floor = floors.get(row.cluster_name, 1)
        if row.strategy_score > 0:
            floors[row.cluster_name] = row.strategy_score
        result.append(
            {
                "id": row.id,
                "strategy_score": row.strategy_score,
                "floor": floor,
                "ceil": row.strategy_score - 1,
                "node": node_data(row.node),
            }
        )
    return rows, result


def resolve_node(params):
    if params.get("node_id"):
        node = CacheNode.objects.filter(id=params["node_id"]).first()
        if node is None:
            fail("未找到 Redis Node", "NODE_NOT_FOUND")
        return node
    sid = params.get("strategy_id") or 0
    rows, _ = routes()
    groups = {}
    for row in rows:
        groups.setdefault(row.cluster_name, []).append(row)
    if sid:
        from kernel_api.rpc.functions.admin.alarm_strategy import scoped_strategy

        strategy = scoped_strategy(params, sid)
        candidates_by_group = get_cluster().get_targets_by_cluster(TargetType.biz, [strategy.bk_biz_id])
        matched = [name for name in groups if name in candidates_by_group]
        # 只有一组配置时直接使用；多组时仅使用明确匹配业务的组。
        selected_groups = matched if matched else list(groups)
        candidates = []
        for name in selected_groups:
            for row in groups[name]:
                if row.strategy_score > sid:
                    candidates.append(row.node)
                    break
    else:
        candidates = list(CacheNode.objects.filter(is_default=True).order_by("id"))
    unique = {node.id: node for node in candidates}
    if len(unique) != 1:
        fail(
            "无法唯一确定 Redis 节点，请显式选择 node_id",
            "ROUTE_SELECTION_REQUIRED",
            candidates=[node_data(node) for node in unique.values()],
        )
    return next(iter(unique.values()))


def template_catalog():
    catalog = {}
    for name, value in vars(keys).items():
        if isinstance(value, keys.RedisDataKey):
            fields = list(dict.fromkeys(field for _, field, _, _ in Formatter().parse(value.key_tpl) if field))
            catalog[name] = {
                "id": name,
                "label": getattr(value, "label", name),
                "backend": value.backend,
                "key_template": value.key_tpl.removeprefix(keys.KEY_PREFIX + "."),
                "parameters": fields,
                "field_template": getattr(value, "field_tpl", None),
            }
    from alarm_backends.core.cache.strategy import StrategyCacheManager

    catalog["STRATEGY_CONFIG_CACHE"] = {
        "id": "STRATEGY_CONFIG_CACHE",
        "label": "策略配置缓存",
        "backend": "cache-strategy",
        "key_template": StrategyCacheManager.CACHE_KEY_TEMPLATE,
        "parameters": ["strategy_id"],
        "field_template": None,
    }
    return catalog


def target(params):
    template_id = params.get("template_id")
    backend = params.get("backend", "service")
    if template_id:
        catalog = template_catalog()
        if template_id not in catalog:
            fail("未知告警 Key 模板", "INVALID_TEMPLATE")
        template = catalog[template_id]
        backend = template["backend"]
        values = dict(params.get("key_params") or {})
        if params.get("strategy_id"):
            values["strategy_id"] = params["strategy_id"]
        missing = [field for field in template["parameters"] if field not in values]
        if missing:
            fail("请补充模板参数：" + ", ".join(missing), "MISSING_KEY_PARAMETERS")
        try:
            redis_key = template["key_template"].format(**values)
        except (ValueError, TypeError, KeyError) as error:
            fail(str(error), "INVALID_KEY_PARAMETERS")
    else:
        redis_key = params.get("key") or params.get("pattern", "*")
    if backend not in BACKENDS:
        fail("不支持的 Redis backend", "INVALID_BACKEND")
    if backend == "cache-strategy":
        if params.get("strategy_id"):
            from kernel_api.rpc.functions.admin.alarm_strategy import scoped_strategy

            scoped_strategy(params, params["strategy_id"])
        client = Cache("cache-strategy")
        return client, {"node": None, "backend": backend, "db": CACHE_BACKEND_CONF_MAP["cache"]["db"]}, redis_key
    node = resolve_node(params)
    if not node.is_enable:
        fail("该 Redis 节点已禁用", "NODE_DISABLED")
    if template_id:
        definition = getattr(keys, template_id)
        prefix = (
            keys.PUBLIC_KEY_PREFIX
            if definition.is_global or node.cluster_name == "default"
            else f"{keys.PUBLIC_KEY_PREFIX}.{node.cluster_name}"
        )
        # 部分旧模板在定义时已拼入 KEY_PREFIX，先移除已知前缀再按目标节点生成。
        redis_key = redis_key.removeprefix(keys.KEY_PREFIX + ".")
        redis_key = prefix + "." + redis_key
    client = setup_client(node, backend)
    return client, {"node": node_data(node), "backend": backend, "db": CACHE_BACKEND_CONF_MAP[backend]["db"]}, redis_key


def key_status(client, redis_key, source):
    kind = client.type(redis_key)
    if isinstance(kind, bytes):
        kind = kind.decode()
    ttl = client.ttl(redis_key)
    if ttl == -2:
        kind = "none"
    sizes = {"string": "strlen", "hash": "hlen", "list": "llen", "set": "scard", "zset": "zcard"}
    length = getattr(client, sizes[kind])(redis_key) if kind in sizes else None
    return {
        "key": redis_key,
        "exists": kind != "none",
        "type": kind,
        "ttl": ttl,
        "length": length,
        "source": source,
        "error": None,
    }


def key_read(client, redis_key, source, params):
    status = key_status(client, redis_key, source)
    kind = status["type"]
    count = params.get("page_size", 20)
    cursor = str(params.get("cursor", "0"))
    next_cursor = "0"
    if kind == "none":
        value = None
    elif kind == "string":
        value = None if status["length"] > MAX_CONTENT_BYTES else client.getrange(redis_key, 0, MAX_CONTENT_BYTES - 1)
    elif kind == "list":
        offset = int(cursor)
        value = client.lrange(redis_key, offset, offset + count - 1)
        next_cursor = str(offset + len(value)) if offset + len(value) < (status["length"] or 0) else "0"
    elif kind == "zset":
        offset = int(cursor)
        value = client.zrange(redis_key, offset, offset + count - 1, withscores=True)
        next_cursor = str(offset + len(value)) if offset + len(value) < (status["length"] or 0) else "0"
    elif kind in ("hash", "set"):
        next_cursor, value = getattr(client, "hscan" if kind == "hash" else "sscan")(
            redis_key, cursor=int(cursor), count=count
        )
        next_cursor = str(next_cursor)
    else:
        fail("暂不支持读取该 Redis 类型：" + kind, "UNSUPPORTED_KEY_TYPE")
    value = to_json_safe(value)
    omitted = len(json.dumps(value, ensure_ascii=False).encode()) > MAX_CONTENT_BYTES
    if kind == "string" and status["length"] > MAX_CONTENT_BYTES:
        omitted = True
    if omitted:
        value = None
    return {
        **status,
        "value": value,
        "next_cursor": next_cursor,
        "content_omitted": omitted,
        "content_omitted_reason": "超过 1 MiB 内容上限" if omitted else None,
    }


def actual_address(client):
    instance = client._instance
    pool = instance.connection_pool
    if hasattr(pool, "get_master_address"):
        host, port = pool.get_master_address()
    else:
        host, port = pool.connection_kwargs.get("host"), pool.connection_kwargs.get("port")
    return {"host": host, "port": port}
