# -*- coding: utf-8 -*-
from constants.cmdb import TargetNodeType
from core.drf_resource import api


def search_set(bk_biz_id):
    """获取一个业务下的集群信息"""
    query_data = {
        "bk_biz_id": bk_biz_id,
        "fields": ["bk_set_id", "bk_set_name"],
        "page": {"start": 0, "limit": 200, "sort": "bk_set_id"},
    }
    search_result = api.cmdb.get_set(**query_data)
    return {item.bk_set_name: item.bk_set_id for item in search_result}


def list_service_instance(bk_biz_id):
    # 获取服务模板
    all_templates = list_service_template(bk_biz_id)
    # 获取模块信息
    search_module_result = api.cmdb.get_module(bk_biz_id=bk_biz_id)
    # 服务实例于模块之间的关系存储
    for item in search_module_result:
        if item.service_template_id in all_templates:
            all_templates[item.service_template_id]["inst"].append(
                {
                    "bk_module_id": str(item.bk_module_id),
                    "bk_module_name": item.bk_module_name,
                    "bk_set_id": str(item.bk_set_id),
                }
            )

    template_instances = {item["name"]: item["inst"] for item in all_templates.values()}
    return template_instances


def list_service_template(bk_biz_id):
    query_data = {"bk_biz_id": bk_biz_id, "dynamic_type": TargetNodeType.SERVICE_TEMPLATE}
    search_result = api.cmdb.get_dynamic_query(**query_data)
    if search_result["result"]:
        templates = {item["id"]: {"name": item["name"], "inst": []} for item in search_result["data"]["info"]}
        return templates
    return {}


def list_service_template_by_module_ids(bk_biz_id, bk_module_ids, username):
    query_data = {"bk_biz_id": bk_biz_id, "bk_module_ids": bk_module_ids}
    search_result = api.cmdb.get_module(**query_data)
    templates = [item.service_template_id for item in search_result]
    return list(set(templates))


def list_module_instance(bk_biz_id):
    search_modules = api.cmdb.get_module(bk_biz_id=bk_biz_id)
    modules = []
    for module in search_modules:
        modules.append(
            {
                "bk_module_id": module.bk_module_id,
                "bk_module_name": module.bk_module_name,
                "bk_module_type": module.bk_module_type,
            }
        )
    return modules
