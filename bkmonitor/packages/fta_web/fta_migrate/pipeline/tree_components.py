# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017-2020 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import uuid

from django.utils.translation import gettext as _


def uniqid():
    return uuid.uuid3(uuid.uuid1(), uuid.uuid4().hex).hex


def node_uniqid():
    uid = uniqid()
    return "n%s" % uid[1:]


def line_uniqid():
    uid = uniqid()
    return "l%s" % uid[1:]


def tree_skeleton():
    """返回 V3 tree 基本骨架

    :param name: 模板名
    :type name: str
    :return: V3 tree 骨架
    :rtype: dict
    """
    return {
        "activities": {},
        "end_event": {"id": node_uniqid(), "incoming": [], "name": "", "outgoing": "", "type": "EmptyEndEvent"},
        "flows": {},
        "gateways": {},
        "outputs": [],
        "start_event": {
            "id": node_uniqid(),
            "incoming": "",
            "name": "",
            "outgoing": "",
            "type": "EmptyStartEvent",
        },
        "constants": {},
    }


def parallel_gateway(id, name=""):
    """返回并行网关基本骨架

    :param id: 网关 ID
    :type id: str
    :param name: 网关名, defaults to ""
    :type name: str, optional
    :return: 并行网关骨架
    :rtype: dict
    """
    return {"id": id, "incoming": [], "name": name, "outgoing": [], "type": "ParallelGateway"}


def converge_gateway(id, name=""):
    """返回汇聚网关基本骨架

    :param id: 网关 ID
    :type id: str
    :param name: 网关名, defaults to ""
    :type name: str, optional
    :return: 汇聚网关骨架
    :rtype: dict
    """
    return {"id": id, "incoming": [], "name": name, "outgoing": "", "type": "ConvergeGateway"}


def flow(source, target):
    """返回 flow 对象

    :param source: 源节点 ID
    :type source: str
    :param target: 目标节点 ID
    :type target: str
    :return: flow 对象
    :rtype: dict
    """
    return {"id": line_uniqid(), "is_default": False, "source": source, "target": target}


def constants_skeleton(
    key,
    name,
    show_type,
    source_type,
    custom_type,
    value,
    desc="",
    validation="",
    source_tag="",
    is_meta=False,
    version="legacy",
):
    """返回全局变量基本骨架

    :param key: 全局变量 key
    :type key: str
    :param name: 全局变量名
    :type name: str
    :param show_type: 全局变量是否展示
    :type show_type: str, "show" or "hide"
    :param source_type: 变量来源
    :type source_type: str, "custom" or "component_outputs" or "component_inputs"
    :param custom_type: 自定义变量类型
    :type custom_type: str
    :param value: 变量值
    :type value: any
    :param desc: 变量描述, defaults to ""
    :type desc: str, optional
    :param validation: value 校验规则, defaults to ""
    :type validation: str, optional
    :param source_tag: 当 source_type 为 component_inputs 时的来源字段标志, defaults to ""
    :type source_tag: str, optional
    :param is_meta: 标识变量是否是元变量, defaults False
    :type is_meta: bool
    :return: 全局变量骨架
    :rtype: dict
    """
    return {
        "key": key,
        "name": name,
        "desc": desc,
        "custom_type": custom_type,
        "source_info": {},
        "source_tag": source_tag,
        "value": value,
        "show_type": show_type,
        "source_type": source_type,
        "validation": validation,
        "version": version,
        "is_meta": is_meta,
    }


def activity_result_constant(source_id, key):
    """
    节点执行状态变量输出
    """
    return {
        "custom_type": "",
        "desc": "",
        "index": 6,
        "key": key,
        "name": _("执行结果"),
        "show_type": "hide",
        "source_info": {source_id: ["_result"]},
        "source_tag": "",
        "source_type": "component_outputs",
        "validation": "",
        "value": "",
        "version": "legacy",
    }


def fta_public_constants():
    """
    故障自愈通用输出变量
    """
    return {
        "${fault_ip}": {
            "custom_type": "input",
            "desc": "",
            "form_schema": {"attrs": {"hookable": True, "name": _("输入框"), "validation": []}, "type": "input"},
            "index": 0,
            "is_meta": False,
            "key": "${fault_ip}",
            "name": _("故障机IP"),
            "show_type": "show",
            "source_info": {},
            "source_tag": "input.input",
            "source_type": "custom",
            "validation": "^.+$",
            "value": "",
            "version": "legacy",
        },
        "${fault_server_id}": {
            "custom_type": "input",
            "desc": "",
            "form_schema": {"attrs": {"hookable": True, "name": _("输入框"), "validation": []}, "type": "input"},
            "index": 0,
            "is_meta": False,
            "key": "${fault_server_id}",
            "name": _("故障机服务大区id"),
            "show_type": "show",
            "source_info": {},
            "source_tag": "input.input",
            "source_type": "custom",
            "validation": "^.+$",
            "value": "",
            "version": "legacy",
        },
        "${host_name}": {
            "custom_type": "input",
            "desc": "",
            "form_schema": {"attrs": {"hookable": True, "name": _("输入框"), "validation": []}, "type": "input"},
            "index": 2,
            "key": "${host_name}",
            "name": _("主机名"),
            "show_type": "show",
            "source_info": {},
            "source_tag": "input.input",
            "source_type": "custom",
            "validation": "^.+$",
            "value": "",
            "version": "legacy",
        },
        "${responsible}": {
            "custom_type": "input",
            "desc": "",
            "form_schema": {"attrs": {"hookable": True, "name": _("输入框"), "validation": []}, "type": "input"},
            "index": 0,
            "is_meta": False,
            "key": "${responsible}",
            "name": _("主机负责人"),
            "show_type": "show",
            "source_info": {},
            "source_tag": "input.input",
            "source_type": "custom",
            "validation": "^.+$",
            "value": "",
            "version": "legacy",
        },
    }


def fta_bak_ip_constants(relate_solution):
    """
    故障自愈备用IP机器的获取
    """
    config = relate_solution.config
    set_id = json.loads(config).get("set_id", _("空闲机池"))
    module_id = json.loads(config).get("app_module_id", _("空闲机"))
    return {
        "${bak_ip}": {
            "custom_type": "input",
            "desc": "",
            "form_schema": {"attrs": {"hookable": True, "name": _("输入框"), "validation": []}, "type": "input"},
            "index": 1,
            "key": "${bak_ip}",
            "name": _("备机IP"),
            "show_type": "hide",
            "source_info": {},
            "source_tag": "input.input",
            "source_type": "custom",
            "validation": "^.+$",
            "value": "${random.choice(bak_ips.split(','))}",
            "version": "legacy",
        },
        "${bak_ips}": {
            "custom_type": "set_module_ip_selector",
            "desc": "",
            "form_schema": {},
            "index": 5,
            "key": "${bak_ips}",
            "name": _("故障自愈待选备机"),
            "show_type": "hide",
            "source_info": {},
            "source_tag": "set_module_ip_selector.ip_selector",
            "source_type": "custom",
            "validation": "",
            "value": {
                "var_ip_method": "manual",
                "var_ip_custom_value": "",
                "var_ip_select_value": {"var_set": [set_id], "var_module": [module_id], "var_module_name": ""},
                "var_ip_manual_value": {
                    "var_manual_set": "${bak_ips_set}",
                    "var_manual_module": "${bak_ips_module}",
                    "var_module_name": "",
                },
                "var_filter_set": "",
                "var_filter_module": "",
            },
            "version": "legacy",
            "is_meta": False,
        },
        "${bak_ips_set}": {
            "custom_type": "input",
            "desc": _("备机待选集群"),
            "form_schema": {"type": "input", "attrs": {"name": _("输入框"), "hookable": True, "validation": []}},
            "index": 6,
            "key": "${bak_ips_set}",
            "name": _("备机待选集群"),
            "show_type": "show",
            "source_info": {},
            "source_tag": "input.input",
            "source_type": "custom",
            "validation": "^.+$",
            "value": set_id,
            "version": "legacy",
            "is_meta": False,
        },
        "${bak_ips_module}": {
            "custom_type": "input",
            "desc": _("备机待选模块备机待选模块备机待选模块"),
            "form_schema": {"type": "input", "attrs": {"name": _("输入框"), "hookable": True, "validation": []}},
            "index": 7,
            "key": "${bak_ips_module}",
            "name": _("备机待选模块"),
            "show_type": "show",
            "source_info": {},
            "source_tag": "input.input",
            "source_type": "custom",
            "validation": "^.+$",
            "value": module_id,
            "version": "legacy",
            "is_meta": False,
        },
    }


def fta_ping_ip_constants():
    return {
        "${proxy_ip}": {
            "custom_type": "input",
            "desc": "",
            "form_schema": {"attrs": {"hookable": True, "name": _("输入框"), "validation": []}, "type": "input"},
            "index": 0,
            "is_meta": False,
            "key": "${proxy_ip}",
            "name": _("故障机的proxy IP"),
            "show_type": "show",
            "source_info": {},
            "source_tag": "input.input",
            "source_type": "custom",
            "validation": "^.+$",
            "value": "",
            "version": "legacy",
        },
        "${bk_cloud_id}": {
            "custom_type": "input",
            "desc": "",
            "form_schema": {"attrs": {"hookable": True, "name": _("输入框"), "validation": []}, "type": "input"},
            "index": 0,
            "is_meta": False,
            "key": "${bk_cloud_id}",
            "name": _("故障机的云区域ID"),
            "show_type": "show",
            "source_info": {},
            "source_tag": "input.input",
            "source_type": "custom",
            "validation": "^.+$",
            "value": "",
            "version": "legacy",
        },
    }


def sops_constant_skeleton(new_key, name=_("通知内容")):
    return {
        "custom_type": "input",
        "desc": "",
        "form_schema": {"attrs": {"hookable": True, "name": _("输入框"), "validation": []}, "type": "input"},
        "index": 1,
        "key": new_key,
        "name": name,
        "show_type": "show",
        "source_info": {},
        "source_tag": "input.input",
        "source_type": "custom",
        "validation": "^.+$",
        "value": "",
        "version": "legacy",
    }


def activity_skeleton(act_id, stage_name, name, error_ignorable, optional, labels=None, code="", version="legacy"):
    """返回 activity 基本骨架

    :param act_id: 节点 ID
    :type act_id: str
    :param stage_name: 阶段名
    :type stage_name: str
    :param name: 节点名
    :type name: str
    :param error_ignorable: 是否可以忽略错误
    :type error_ignorable: boolean
    :param optional: 是否是可选节点
    :type optional: boolean
    :param labels: 节点标签, defaults to None
    :type labels: list, optional
    :param code: component 唯一 code, defaults to ""
    :type code: str, optional
    :param version: component version, defaults to "legacy"
    :type version: str, optional
    :return: activity 基本骨架
    :rtype: dict
    """
    return {
        "id": act_id,
        "component": {"code": code, "data": {}, "version": version},
        "error_ignorable": error_ignorable,
        "incoming": [],
        "loop": None,
        "name": name,
        "optional": optional,
        "outgoing": "",
        "stage_name": stage_name,
        "type": "ServiceActivity",
        "retryable": True,
        "skippable": True,
        "labels": labels or [],
    }


def subprocess_activity_skeleton(act_id, stage_name, name, error_ignorable, labels=None, template_id=None):
    return {
        "always_use_latest": True,
        "can_retry": True,
        "hooked_constants": [],
        "error_ignorable": error_ignorable,
        "id": act_id,
        "incoming": [],
        "isSkipped": True,
        "loop": None,
        "name": name,
        "optional": True,
        "outgoing": "",
        "scheme_id_list": [],
        "stage_name": stage_name,
        "template_id": template_id,
        "type": "SubProcess",
        "labels": labels or [],
    }


def get_template_skeleton(template_id, pipeline_template_id, bk_biz_id):
    """
    获取template数据结构
    """
    return {
        "category": "OpsTools",
        "id": template_id,
        "is_deleted": False,
        "notify_receivers": '{"receiver_group":["Maintainers"],' '"more_receiver":""}',
        "notify_type": '["weixin","email"]',
        "pipeline_template_id": pipeline_template_id,
        "pipeline_template_str_id": pipeline_template_id,
        "project_id": bk_biz_id,
        "time_out": 20,
    }
