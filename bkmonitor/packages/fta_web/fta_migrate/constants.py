# -*- coding: utf-8 -*-
import json

from django.utils.translation import gettext as _

SOPS_CONSTANTS_MAPPING = {
    "${fault_ip}": "{{target.host.bk_host_innerip}}",
    "${bak_ip}": "",
    "${fault_server_id}": "{{target.host.bk_world_id}}",
    "${host_name}": "{{target.host.bk_host_name}}",
    "${operator}": "{{action_instance.assignees}}",
    "${responsible}": "{{action_instance.assignees}}",
    "${bk_biz_name}": "{{target.host.bk_biz_name}}",
    "${bk_set_name}": "{{target.host.set_string}}",
    "${bk_module_name}": "{{target.host.module_string}}",
    "${bk_cloud_id}": "{{target.host.bk_cloud_id}}",
    "${proxy_ip}": _("__用于机器ping测试的服务器，需用户填写__"),
    "${bk_http_request_body}": json.dumps(
        {
            "ip": "{{target.host.bk_host_innerip}}",
            "source_type": "MONITOR",
            "alarm_type": "{{alarm.name}}",
            "content": "{{alarm.description}}",
            "source_time": "{{alarm.begin_time}}",
            "cc_biz_id": "{{target.business.bk_biz_id}}",
        }
    ),
    "${source_time}": "{{alarm.time}}",
    "${raw}": "{{alarm.description}}",
}

FTA_SOPS_MAPPING = {
    "${ip}": "${fault_ip}",
    "${cc|bk_world_id|set}": "${fault_server_id}",
    "${cc|bk_host_name}": "${host_name}",
    "${operator}": "${operator}",
    "${operators}": "${operator}",
    "${cc|str_biz_name}": "${bk_biz_name}",
    "${cc|str_set_name}": "${bk_set_name}",
    "${cc|str_module_name}": "${bk_module_name}",
    "${cc|bk_cloud_id}": "${bk_cloud_id}",
    "${source_time}": "${source_time}",
    "${raw}": "${raw}",
}

FTA_MONITOR_MAPPING = {
    "${ip}": "{{target.host.bk_host_innerip}}",
    "${cc|bk_world_id|set}": "{{target.host.bk_world_id}}",
    "${cc|bk_host_name}": "{{target.host.bk_host_name}}",
    "${operator}": "{{action_instance.assignees}}",
    "${operators}": "{{action_instance.assignees}}",
    "${cc|str_biz_name}": "{{target.host.bk_biz_name}}",
    "${cc|str_set_name}": "{{target.host.set_string}}",
    "${cc|str_module_name}": "{{target.host.module_string}}",
    "${cc|bk_cloud_id}": "{{target.host.bk_cloud_id}}",
    "${source_time}": "{{alarm.time}}",
    "${raw}": "{{alarm.description}}",
}


class NoticeGroupMapping:
    FAILURE = 1
    SUCCESS = 2
    BEGIN = 3
    APPROVAL = 4
    SKIPPED = 5
    FINISHED = 6

    EXECUTE = "execute"
    EXECUTE_SUCCESS = "execute_success"
    EXECUTE_FAILED = "execute_failed"

    NOTICE_WAY = {"mail": "mail", "wechat": "weixin", "sms": "sms", "phone": "voice"}

    USER_GROUP = {
        "to_host_operator": [{"id": "operator", "type": "group"}, {"id": "bk_bak_operator", "type": "group"}],
        "to_role": [{"id": "bk_biz_maintainer", "type": "group"}],
        "only_to_host": [{"id": "operator", "type": "group"}, {"id": "bk_bak_operator", "type": "group"}],
        "only_to_role": [{"id": "bk_biz_maintainer", "type": "group"}],
    }

    NOTICE_PHASE = {"success": SUCCESS, "failure": FAILURE, "begin": BEGIN}

    OPERATE_SIGNAL = {BEGIN: EXECUTE, FAILURE: EXECUTE_FAILED, SUCCESS: EXECUTE_SUCCESS}


SALT = "821a11587ea434eb85c2f5327a90ae54"


def get_http_data():
    return {
        "bk_http_request_method": {"hook": False, "need_render": True, "value": "POST"},
        "bk_http_request_url": {"hook": True, "need_render": True, "value": "bk_http_request_url_convert"},
        "bk_http_request_header": {
            "hook": False,
            "need_render": True,
            "value": [{"name": "content-type", "value": "application/json"}],
        },
        "bk_http_request_body": {"hook": True, "need_render": True, "value": "${bk_http_request_body}"},
        "bk_http_timeout": {"hook": False, "need_render": True, "value": 5},
        "bk_http_success_exp": {"hook": False, "need_render": True, "value": ""},
    }


FTA_COMPONENTS = [
    {
        "code": "sleep_timer",
        "fta_code": "solution_type|sleep",
        "data": {
            "force_check": {"hook": False, "value": True},
            "bk_timing": {"hook": False, "value": "bk_timing_convert"},
        },
        "version": "legacy",
        "name": _("暂停等待"),
    },
    {
        "code": "cmdb_transfer_fault_host",
        "fta_code": "id|36",
        "data": {
            "biz_cc_id": {"hook": False, "value": "cc_biz_id_convert"},
            "cc_host_ip": {"hook": False, "value": "${fault_ip}"},
        },
        "version": "legacy",
        "name": _("【自愈快捷】转移主机至故障机模块"),
    },
    {
        "code": "cc_transfer_to_idle",
        "fta_code": "id|6",
        "data": {
            "biz_cc_id": {"hook": False, "value": "cc_biz_id_convert"},
            "cc_host_ip": {"hook": False, "value": "${fault_ip}"},
        },
        "version": "legacy",
        "name": _("【快捷】转移主机至空闲机模块"),
    },
    {
        "code": "bk_notify",
        "fta_code": "solution_type|notice",
        "name": _("自愈通知"),
        "data": {
            "biz_cc_id": {"hook": False, "value": "cc_biz_id_convert"},
            "bk_notify_content": {"hook": False, "value": "bk_notify_content_convert"},
            "bk_notify_title": {"hook": False, "value": _("故障自愈通知")},
            "bk_notify_type": {"hook": False, "value": ["weixin", "email", "sms"]},
            "bk_receiver_info": {
                "hook": False,
                "value": {"bk_more_receiver": "", "bk_receiver_group": ["Maintainers"]},
            },
        },
    },
    {
        "code": "bk_notify",
        "fta_code": "solution_type|get_bak_ip",
        "name": _("故障自愈获取备机"),
        "data": {
            "biz_cc_id": {"hook": False, "value": "cc_biz_id_convert"},
            "bk_notify_content": {"hook": False, "value": _("故障自愈获取到备机为【${bak_ip}】")},
            "bk_notify_title": {"hook": False, "value": _("故障自愈获取备机通知")},
            "bk_notify_type": {"hook": False, "value": ["weixin", "email", "sms"]},
            "bk_receiver_info": {
                "hook": False,
                "value": {"bk_more_receiver": "", "bk_receiver_group": ["Maintainers"]},
            },
        },
    },
    {
        "code": "bk_notify",
        "fta_code": "solution_type|switch_ip",
        "name": _("【快捷】替换操作对象为备机"),
        "data": {
            "biz_cc_id": {"hook": False, "value": "cc_biz_id_convert"},
            "bk_notify_content": {"hook": False, "value": _("故障自愈后续参数更改为到备机【${bak_ip}】")},
            "bk_notify_title": {"hook": False, "value": _("故障自愈切换备机")},
            "bk_notify_type": {"hook": False, "value": ["weixin", "email", "sms"]},
            "bk_receiver_info": {
                "hook": False,
                "value": {"bk_more_receiver": "", "bk_receiver_group": ["Maintainers"]},
            },
        },
    },
    {
        "code": "cc_replace_fault_machine",
        "fta_code": "id|5",
        "data": {
            "cc_host_replace_detail": {
                "hook": False,
                "value": [{"cc_new_ip": "${bak_ip}", "cc_fault_ip": "${fault_ip}"}],
            },
            "biz_cc_id": {"hook": False, "value": "cc_biz_id_convert"},
        },
        "version": "legacy",
        "name": _("CC故障机替换"),
    },
    {
        "code": "bk_approve",
        "fta_code": "solution_type|notice|approve",
        "data": {
            "bk_verifier": {"hook": False, "value": "${responsible}"},
            "bk_approve_title": {"hook": False, "value": "bk_notify_content_convert"},
            "bk_approve_content": {"hook": False, "value": "bk_notify_content_convert"},
            "rejected_block": {"hook": False, "value": True},
        },
        "version": "v1.0",
        "name": _("故障自愈执行审批"),
    },
    {
        "code": "",
        "fta_code": "solution_type|gcloud",
        "template_id": "",
        "data": {},
        "version": "",
        "name": _("【子流程】占位（子流程）"),
    },
    {
        "code": "",
        "fta_code": "mem_proc_top10",
        "data": {},
        "template_id": "",
        "version": "",
        "name": _("【子流程】发送内存进程TOP10通知（占位）"),
    },
    {
        "code": "",
        "fta_code": "cpu_proc_top10",
        "data": {},
        "version": "",
        "template_id": "",
        "name": _("【子流程】发送CPU进程TOP10通知(占位)"),
    },
    {
        "code": "",
        "fta_code": "solution_type|clean",
        "data": {},
        "version": "",
        "template_id": "",
        "name": _("【子流程】磁盘清理（占位）"),
    },
    {
        "code": "job_execute_task",
        "fta_code": "solution_type|ijobs",
        "data": {
            "biz_cc_id": {"hook": False, "need_render": True, "value": "cc_biz_id_convert"},
            "job_task_id": {"hook": False, "need_render": True, "value": "task_id_convert"},
            "button_refresh": {"hook": False, "need_render": True, "value": ""},
            "job_global_var": {"hook": True, "need_render": True, "value": "global_vars_convert"},
            "ip_is_exist": {"hook": False, "need_render": True, "value": True},
            "biz_across": {"hook": False, "need_render": True, "value": False},
            "is_tagged_ip": {"hook": False, "need_render": True, "value": False},
            "job_success_id": {"hook": False, "need_render": True, "value": ""},
            "button_refresh_2": {"hook": False, "need_render": True, "value": ""},
        },
        "version": "legacy",
        "name": _("「Job作业」流程需补充"),
    },
    {
        "code": "bk_http_request",
        "fta_code": "solution_type|http",
        "data": get_http_data(),
        "version": "legacy",
        "name": _("HTTP回调"),
    },
    {
        "code": "bk_http_request",
        "fta_code": "solution_type|http_callback",
        "data": get_http_data(),
        "version": "legacy",
        "name": _("HTTP回调"),
    },
]

FTA_COMPONENTS_DICT = {item["fta_code"]: item for item in FTA_COMPONENTS}

FTA_SOPS_QUICK_ACTION_MAPPING = {
    "solution_type|clean": "clean_disk",
    "cpu_proc_top10": "cpu_proc_top10",
    "mem_proc_top10": "mem_proc_top10",
}
