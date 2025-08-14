# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json

from django.conf import settings
from django.utils.translation import gettext as _
from jinja2 import DebugUndefined
from jinja2.sandbox import SandboxedEnvironment as Environment

from bkmonitor.models import ActionPlugin
from bkmonitor.utils.template import AlarmNoticeTemplate
from constants.action import DEFAULT_TEMPLATE, ConvergeType, NoticeWay
from fta_web.action.constant import BK_PLUGIN_INITIAL_TEMPLATE


def parse_bk_plugin_deployed_info(data):
    """
    解析蓝鲸插件部署信息
    """
    plugin_code = data["plugin"].get("code")

    # 1.获取saas当前运行环境
    env = {"testing": "stag", "production": "prod"}.get(settings.ENVIRONMENT, "stag")

    # 2.获取当前环境下的插件部署地址
    deployed_statuses = data["deployed_statuses"].get(env)

    # 3.如果插件未部署，则返回False
    if not deployed_statuses["deployed"]:
        return False, plugin_code, {}

    # 4.获取插件部署地址
    plugin_address = ""
    DEFAULT_HOST_TYPE = 2  # 插件部署类型
    for address in deployed_statuses["addresses"]:
        if address["type"] == DEFAULT_HOST_TYPE:
            plugin_address = address["address"]

    # 5.获取插件名称，描述，网关名称，组装网关地址
    plugin_name = data["plugin"].get("name", plugin_code)
    plugin_description = data["profile"].get("introduction", "")
    api_gw_name = data["profile"].get("api_gw_name")
    plugin_apigw_host = "{}/{}".format(settings.APIGW_BASE_URL.format(api_gw_name).rstrip("/"), env)

    # 6.计算插件id
    try:
        # plugin_key 为插件唯一标识，根据 plugin_key 查找对应的 ActionPlugin 的 id 为 plugin_id
        plugin_id = ActionPlugin.objects.get(plugin_key=plugin_code).id
    except ActionPlugin.DoesNotExist:
        # 如果找不到，则从1001开始自增
        plugin = ActionPlugin.objects.filter(plugin_source="bk_plugin").order_by("id").last()
        plugin_id = 1001 if not plugin else plugin.id + 1

    # 7.jinja 渲染插件初始化模版
    init_params = {
        "plugin_id": plugin_id,
        "plugin_name": plugin_name,
        "plugin_code": plugin_code,
        "plugin_address": plugin_address.rstrip("/"),
        "plugin_apigw_host": plugin_apigw_host,
    }

    plugin_template = Environment(undefined=DebugUndefined).from_string(source=BK_PLUGIN_INITIAL_TEMPLATE, ).render(**init_params)
    plugin_info = json.loads(plugin_template)

    # 8.description 中的信息 在json.loads时容易出错，因此先 loads 后再为 description 赋值
    plugin_info["description"] = plugin_description.replace("\\n", "\n")

    # 9.返回解析后的插件code和初始化信息
    return True, plugin_code, plugin_info


def compile_assign_action_config(validated_request_data):
    operator = validated_request_data["operator"]
    appointees = validated_request_data["appointees"]
    assign_reason = validated_request_data["reason"]
    alert_ids = validated_request_data["alert_ids"]
    alerts_count = len(alert_ids)
    notice_type = ConvergeType.ACTION
    if alerts_count > 1:
        notice_type = ConvergeType.CONVERGE
    notice_ways = validated_request_data["notice_ways"]
    user_title_template = _("{}给您分派了告警【{{alarm.name}}({{alarm.id}})】").format(operator)
    if len(validated_request_data["alert_ids"]) > 1:
        user_title_template = _("{}给您分派了【{}】等{}个告警").format(operator, "{{alarm.name}}", alerts_count)
    action_configs = []
    for notice_way in notice_ways:
        template_path = f"notice/assign/{notice_type}/{notice_way}_content.jinja"
        title_template_path = f"notice/assign/{notice_type}/{notice_way}_title.jinja"
        message_template = AlarmNoticeTemplate.get_template(template_path)
        title_template = AlarmNoticeTemplate.get_template(title_template_path)
        title_template = title_template if title_template else "{{user_title}}"
        message_template = message_template if message_template else "{{user_content}}"
        message_tmpl = None
        if notice_way == NoticeWay.MAIL:
            message_tmpl = "{{content.assign_reason}}\n{{content.appointees}}\n" + DEFAULT_TEMPLATE
        action_configs.append(
            {
                "execute_config": {
                    "template_detail": {"title": title_template, "message": message_template},
                    "context_inputs": {
                        "title_tmpl": user_title_template,
                        "message_tmpl": message_tmpl,
                        "appointees": appointees,
                        "assign_reason": assign_reason,
                        "notice_way": notice_way,
                    },
                },
                "plugin_id": 1,
                "name": _("告警分派"),
                "is_enabled": True,
                "bk_biz_id": validated_request_data["bk_biz_id"],
                "config_id": None,
            }
        )

    return action_configs
