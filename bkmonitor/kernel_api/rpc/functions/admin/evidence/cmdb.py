"""直接使用 CMDB 的固定查询接口；普通列表在 CMDB 分页。"""

from rest_framework import serializers

from api.cmdb import client
from .common import BusinessPage, list_page, query


class CmdbPage(BusinessPage):
    bk_biz_id = serializers.IntegerField(min_value=1)


class Topology(CmdbPage):
    bk_obj_id = serializers.CharField(required=False)
    bk_inst_id = serializers.IntegerField(min_value=1, required=False)


class SetPage(CmdbPage):
    bk_set_id = serializers.IntegerField(min_value=1, required=False)


class ModulePage(SetPage):
    bk_module_id = serializers.IntegerField(min_value=1, required=False)


class HostPage(ModulePage):
    bk_host_id = serializers.IntegerField(min_value=1, required=False)
    ip = serializers.IPAddressField(required=False)


class ServicePage(CmdbPage):
    bk_host_id = serializers.IntegerField(min_value=1, required=False)
    bk_module_id = serializers.IntegerField(min_value=1, required=False)
    service_instance_id = serializers.IntegerField(min_value=1, required=False)


class GroupPage(CmdbPage):
    bk_obj_id = serializers.ChoiceField(choices=("host", "set"), default="host")


class Members(GroupPage):
    group_id = serializers.CharField()


def scope(p):
    return {"bk_tenant_id": p["bk_tenant_id"], "bk_biz_id": p["bk_biz_id"]}


def cmdb_page(method, p, sort=None, **params):
    page = {"start": (p["page"] - 1) * p["page_size"], "limit": p["page_size"]}
    if sort:
        page["sort"] = sort
    result = method(**scope(p), **params, page=page)
    return result["info"], result["count"]


HOST_FIELDS = [
    "bk_host_id",
    "bk_host_name",
    "bk_host_innerip",
    "bk_host_innerip_v6",
    "bk_cloud_id",
    "bk_os_name",
    "bk_agent_id",
]
SET_FIELDS = [
    "bk_set_id",
    "bk_set_name",
    "bk_parent_id",
    "bk_set_env",
    "bk_service_status",
    "set_template_id",
    "default",
]
MODULE_FIELDS = [
    "bk_module_id",
    "bk_module_name",
    "bk_set_id",
    "bk_parent_id",
    "service_template_id",
    "service_category_id",
    "default",
]


@query("cmdb.topology_list", "业务拓扑节点及所属路径", Topology)
def topology(p):
    roots = client.search_biz_inst_topo(**scope(p))
    if not roots:
        return [], 0
    root = roots[0]
    # 主线拓扑与内置空闲机池来自不同的 CMDB 接口。
    internal = client.get_biz_internal_module(**scope(p))
    children = list(root.get("child") or [])
    if internal and not any(n["bk_obj_id"] == "set" and n["bk_inst_id"] == internal["bk_set_id"] for n in children):
        children.append(
            {
                "bk_obj_id": "set",
                "bk_inst_id": internal["bk_set_id"],
                "bk_inst_name": internal["bk_set_name"],
                "child": [
                    {"bk_obj_id": "module", "bk_inst_id": m["bk_module_id"], "bk_inst_name": m["bk_module_name"]}
                    for m in internal.get("module") or []
                ],
            }
        )
    stack = [({**root, "child": children}, "", None, None)]
    rows = []
    while stack:
        node, prefix, parent_obj, parent_id = stack.pop()
        path = f"{prefix} / {node['bk_inst_name']}" if prefix else node["bk_inst_name"]
        obj, inst = node["bk_obj_id"], node["bk_inst_id"]
        if ("bk_obj_id" not in p or p["bk_obj_id"] == obj) and ("bk_inst_id" not in p or p["bk_inst_id"] == inst):
            rows.append(
                {
                    **{k: v for k, v in node.items() if k != "child"},
                    "path": path,
                    "parent_obj_id": parent_obj,
                    "parent_inst_id": parent_id,
                }
            )
        stack.extend((n, path, obj, inst) for n in reversed(node.get("child") or []))
    return list_page(rows, p)


@query("cmdb.set_list", "业务集群", SetPage)
def sets(p):
    return cmdb_page(
        client.search_set, p, "bk_set_id", fields=SET_FIELDS, condition={k: p[k] for k in ("bk_set_id",) if k in p}
    )


@query("cmdb.module_list", "业务服务模块", ModulePage)
def modules(p):
    return cmdb_page(
        client.search_module,
        p,
        "bk_module_id",
        bk_set_id=p.get("bk_set_id", 0),
        fields=MODULE_FIELDS,
        condition={k: p[k] for k in ("bk_module_id",) if k in p},
    )


@query("cmdb.host_list", "业务主机及所在集群和模块", HostPage)
def hosts(p):
    params = {"fields": HOST_FIELDS}
    for key, target in (("bk_set_id", "set"), ("bk_module_id", "module"), ("bk_host_id", "host")):
        if key in p:
            params[target + "_property_filter"] = {
                "condition": "AND",
                "rules": [{"field": key, "operator": "equal", "value": p[key]}],
            }
    if "ip" in p:
        prop = params.setdefault("host_property_filter", {"condition": "AND", "rules": []})
        prop["rules"].append(
            {
                "field": "bk_host_innerip_v6" if ":" in p["ip"] else "bk_host_innerip",
                "operator": "equal",
                "value": p["ip"],
            }
        )
    rows, total = cmdb_page(client.list_biz_hosts_topo, p, **params)
    return [{**item["host"], "topo": item["topo"]} for item in rows], total


@query("cmdb.service_instance_list", "业务服务实例及进程标识", ServicePage)
def services(p):
    params = {"bk_module_id": p["bk_module_id"]} if "bk_module_id" in p else {}
    if "bk_host_id" in p:
        params["bk_host_list"] = [p["bk_host_id"]]
    if "service_instance_id" in p:
        params["service_instance_ids"] = [p["service_instance_id"]]
    rows, total = cmdb_page(client.list_service_instance_detail, p, "-id", **params)
    result = []
    for row in rows:
        item = {
            k: row.get(k)
            for k in (
                "id",
                "name",
                "bk_biz_id",
                "bk_module_id",
                "bk_host_id",
                "service_template_id",
                "service_category_id",
                "create_time",
                "last_time",
            )
        }
        item["processes"] = [
            {k: proc["process"].get(k) for k in ("bk_process_id", "bk_process_name", "bk_func_name", "bind_info")}
            for proc in row.get("process_instances") or []
            if proc.get("process")
        ]
        result.append(item)
    return result, total


@query("cmdb.dynamic_group_list", "动态分组定义", GroupPage)
def groups(p):
    return cmdb_page(client.search_dynamic_group, p, "id", condition={"bk_obj_id": p["bk_obj_id"]})


@query("cmdb.dynamic_group_members", "动态分组当前命中实例", Members, {"group_id": "group-1", "bk_obj_id": "host"})
def members(p):
    fields = HOST_FIELDS if p["bk_obj_id"] == "host" else SET_FIELDS
    return cmdb_page(client.execute_dynamic_group, p, fields[0], id=p["group_id"], fields=fields)
