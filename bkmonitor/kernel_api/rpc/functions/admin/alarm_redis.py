"""后台 Redis Router、Node、INFO 和 Key 查询入口。"""

import time

from rest_framework import serializers
from redis.client import NEVER_DECODE

from bkmonitor.models import CacheNode
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response
from kernel_api.rpc.functions.admin import alarm_redis_service as service


class Params(serializers.Serializer):
    bk_tenant_id = serializers.CharField(required=False, allow_blank=True)
    node_id = serializers.IntegerField(min_value=1, required=False)
    router_id = serializers.IntegerField(min_value=1, required=False)
    strategy_id = serializers.IntegerField(min_value=1, required=False)
    backend = serializers.ChoiceField(choices=service.BACKENDS, default="service")
    key = serializers.CharField(max_length=4096, required=False)
    keys = serializers.ListField(
        child=serializers.CharField(max_length=4096), min_length=1, max_length=20, required=False
    )
    pattern = serializers.CharField(max_length=4096, default="*")
    template_id = serializers.CharField(required=False)
    key_params = serializers.DictField(child=serializers.CharField(), default=dict)
    cursor = serializers.RegexField(r"^\d+$", default="0")
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)
    count = serializers.IntegerField(min_value=1, max_value=1000, default=100)
    keyword = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=20)


def page(items, params):
    start = (params["page"] - 1) * params["page_size"]
    return {
        "items": items[start : start + params["page_size"]],
        "total": len(items),
        "page": params["page"],
        "page_size": params["page_size"],
    }


def execute(operation, params):
    unexpected = set(params) - set(OPERATION_FIELDS[operation])
    if unexpected:
        service.fail("不支持的请求参数：" + ", ".join(sorted(unexpected)), "INVALID_PARAMS")
    serializer = Params(data=params)
    serializer.is_valid(raise_exception=True)
    p = serializer.validated_data
    warnings = []
    if operation == "template_list":
        data = page(list(service.template_catalog().values()), p)
    elif operation in ("router_list", "router_detail"):
        _, items = service.routes()
        if p.get("strategy_id"):
            node = service.resolve_node(p)
            items = [
                row for row in items if row["node"]["id"] == node.id and row["floor"] <= p["strategy_id"] <= row["ceil"]
            ]
        if operation == "router_detail":
            data = {"router": next((row for row in items if row["id"] == p.get("router_id")), None)}
            if data["router"] is None:
                service.fail("未找到 Redis Router", "ROUTER_NOT_FOUND")
        else:
            data = page(items, p)
    elif operation in ("node_list", "node_detail"):
        query = CacheNode.objects.order_by("id")
        if p.get("keyword"):
            from django.db.models import Q

            query = query.filter(Q(node_alias__icontains=p["keyword"]) | Q(host__icontains=p["keyword"]))
        if operation == "node_detail":
            node = query.filter(id=p.get("node_id")).first()
            if node is None:
                service.fail("未找到 Redis Node", "NODE_NOT_FOUND")
            _, items = service.routes()
            data = {
                "node": service.node_data(node),
                "routers": page([r for r in items if r["node"]["id"] == node.id], p),
            }
        else:
            start = (p["page"] - 1) * p["page_size"]
            data = {
                "items": [service.node_data(n) for n in query[start : start + p["page_size"]]],
                "total": query.count(),
                "page": p["page"],
                "page_size": p["page_size"],
            }
    elif operation in ("node_info", "node_clients", "node_slowlog"):
        if not p.get("node_id"):
            service.fail("node_id 为必填项", "INVALID_PARAMS")
        client, source, _ = service.target({**p, "backend": "service"})
        if operation == "node_info":
            info = client.info()
            info.update(client.info("commandstats"))
            optional = {}
            for section in ("errorstats", "latencystats"):
                try:
                    optional[section] = client.info(section)
                except Exception:
                    optional[section] = None
                    warnings.append({"code": "INFO_SECTION_UNAVAILABLE", "message": section + " 未提供"})
            commands = [
                {"command": name.removeprefix("cmdstat_"), **value}
                for name, value in info.items()
                if name.startswith("cmdstat_") and isinstance(value, dict)
            ]
            data = {
                "source": source,
                "sampled_at": time.time(),
                "address": service.actual_address(client),
                "info": {k: v for k, v in info.items() if not k.startswith("cmdstat_")},
                "commands": commands,
                **optional,
            }
        elif operation == "node_clients":
            fields = ("id", "addr", "name", "age", "idle", "flags", "db", "cmd", "qbuf", "omem")
            clients = client.client_list()
            data = page(
                [
                    {
                        k: int(row[k])
                        if k in {"age", "idle", "db", "qbuf", "omem"} and row.get(k) is not None
                        else row.get(k)
                        for k in fields
                    }
                    for row in clients[:1000]
                ],
                p,
            )
            if len(clients) > 1000:
                warnings.append({"code": "CLIENTS_TRUNCATED", "message": "仅展示前 1000 个客户端"})
        else:
            # 分开传递命令名，保留原始参数数组；redis-py 的 slowlog_get 会把参数拼成文本。
            # 慢查询参数可能是压缩/二进制内容，在协议层禁止自动 UTF-8 解码；仅解码命令名。
            rows = client.execute_command("SLOWLOG", "GET", p["limit"], **{NEVER_DECODE: True})
            items = []
            for row in rows:
                arguments = row[3]
                command = arguments[0] if arguments else ""
                if isinstance(command, bytes):
                    command = command.decode("utf-8", errors="replace")
                items.append(
                    {
                        "id": row[0],
                        "timestamp": row[1],
                        "duration_usec": row[2],
                        "command": command,
                        "argument_count": max(0, len(arguments) - 1),
                    }
                )
            data = page(items, p)
    elif operation in ("key_status", "key_read") and "keys" in p:
        if p.get("key") or p.get("template_id"):
            service.fail("keys 不可与 key 或 template_id 同时使用", "INVALID_PARAMS")
        items = []
        # 同一请求复用目标连接；每个 Key 单独返回错误，保留顺序及其独立游标。
        client, source, _ = service.target(p)
        for redis_key in p["keys"]:
            try:
                item = (
                    service.key_status(client, redis_key, source)
                    if operation == "key_status"
                    else service.key_read(client, redis_key, source, p)
                )
            except Exception as error:
                item = {
                    "key": redis_key,
                    "exists": None,
                    "type": None,
                    "ttl": None,
                    "length": None,
                    "source": source,
                    "error": str(error),
                }
                if operation == "key_read":
                    item.update(value=None, next_cursor="0", content_omitted=False, content_omitted_reason=None)
            items.append(item)
        data = {"items": items}
    else:
        if operation != "key_scan" and not p.get("key") and not p.get("template_id"):
            service.fail("请提供 key 或 template_id", "INVALID_PARAMS")
        client, source, redis_key = service.target(p)
        if operation == "key_scan":
            cursor, found = client.scan(cursor=int(p["cursor"]), match=redis_key, count=p["count"])
            data = {"items": [str(k) for k in found], "next_cursor": str(cursor), "source": source}
        elif operation == "key_status":
            data = service.key_status(client, redis_key, source)
        else:
            data = service.key_read(client, redis_key, source, p)
    name = "alarm_redis." + operation
    return build_response(
        operation=name,
        func_name="admin." + name,
        bk_tenant_id=p.get("bk_tenant_id"),
        data=data,
        warnings=warnings,
        safety_level="read" if operation in READ_OPERATIONS else "inspect",
    )


READ_OPERATIONS = ("template_list", "router_list", "router_detail", "node_list", "node_detail")
OPERATIONS = (*READ_OPERATIONS, "node_info", "node_clients", "node_slowlog", "key_scan", "key_status", "key_read")
INPUT_PROPERTIES = {
    "bk_tenant_id": {"type": "string"},
    "node_id": {"type": "integer", "minimum": 1},
    "router_id": {"type": "integer", "minimum": 1},
    "strategy_id": {"type": "integer", "minimum": 1},
    "backend": {"type": "string", "enum": list(service.BACKENDS)},
    "key": {"type": "string", "minLength": 1, "maxLength": 4096},
    "keys": {
        "type": "array",
        "minItems": 1,
        "maxItems": 20,
        "items": {"type": "string", "minLength": 1, "maxLength": 4096},
    },
    "pattern": {"type": "string", "maxLength": 4096, "default": "*"},
    "template_id": {"type": "string"},
    "key_params": {"type": "object", "additionalProperties": {"type": ["string", "number"]}},
    "cursor": {"type": "string", "pattern": "^[0-9]+$", "default": "0"},
    "page": {"type": "integer", "minimum": 1, "default": 1},
    "page_size": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
    "count": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100},
    "keyword": {"type": "string"},
    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
}
PAGING_FIELDS = ("bk_tenant_id", "page", "page_size")
TARGET_FIELDS = ("bk_tenant_id", "node_id", "strategy_id", "backend", "key", "template_id", "key_params")
OPERATION_FIELDS = {
    "template_list": PAGING_FIELDS,
    "router_list": (*PAGING_FIELDS, "strategy_id"),
    "router_detail": ("bk_tenant_id", "router_id"),
    "node_list": (*PAGING_FIELDS, "keyword"),
    "node_detail": (*PAGING_FIELDS, "node_id"),
    "node_info": ("bk_tenant_id", "node_id"),
    "node_clients": (*PAGING_FIELDS, "node_id"),
    "node_slowlog": (*PAGING_FIELDS, "node_id", "limit"),
    "key_scan": (*TARGET_FIELDS, "pattern", "cursor", "count"),
    "key_status": (*TARGET_FIELDS, "keys"),
    "key_read": (*TARGET_FIELDS, "keys", "cursor", "page_size"),
}
for name in OPERATIONS:
    required = (
        ["node_id"]
        if name in {"node_detail", "node_info", "node_clients", "node_slowlog"}
        else ["router_id"]
        if name == "router_detail"
        else []
    )
    KernelRPCRegistry.register_function(
        func_name="admin.alarm_redis." + name,
        handler=lambda params, operation=name: execute(operation, params),
        summary="告警 Redis " + name,
        description="只读查询全部已配置告警节点；不接受任意地址，不初始化默认节点。"
        + (
            "可用 keys 批量查询同一目标的 1–20 个完整 Key，返回 items 逐项结果；单 Key 响应不变。"
            if name in {"key_status", "key_read"}
            else ""
        ),
        params_schema={
            "type": "object",
            "properties": {field: INPUT_PROPERTIES[field] for field in OPERATION_FIELDS[name]},
            "required": required,
            "additionalProperties": False,
        },
        example_params={"node_id": 1, "keys": ["key-a", "key-b"]}
        if name in {"key_status", "key_read"}
        else {"node_id": 1}
        if "node_id" in required
        else {"router_id": 1}
        if "router_id" in required
        else {},
    )
