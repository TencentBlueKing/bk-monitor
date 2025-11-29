"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import time
from collections import defaultdict

from django.conf import settings
from django.template import TemplateDoesNotExist
from django.utils import translation
from django.utils.translation import gettext as _

from api.monitor.default import (
    BatchCreateActionBackendResource,
    GetActionParamsBackendResource,
)
from bkmonitor.action.serializers import (
    ActionPluginSlz,
    BatchCreateDataSerializer,
    GetCreateParamsSerializer,
)
from bkmonitor.documents import AlertDocument, AlertLog
from bkmonitor.documents.action import ActionInstanceDocument
from bkmonitor.documents.base import BulkActionType
from bkmonitor.models import GlobalConfig
from bkmonitor.models.fta import ActionConfig, ActionInstance, ActionPlugin
from bkmonitor.utils.request import get_request_username
from bkmonitor.utils.template import AlarmNoticeTemplate, NoticeRowRenderer
from bkmonitor.utils.user import get_user_display_name
from bkmonitor.views import serializers
from constants.action import (
    CONVERGE_DIMENSION,
    CONVERGE_FUNCTION,
    CONVERGE_FUNCTION_DESCRIPTION,
    VARIABLES,
    ActionPluginType,
    ActionStatus,
    ChatMessageType,
    ConvergeFunction,
)
from core.drf_resource import Resource, api
from fta_web.action.tasks import notify_to_appointee, scheduled_register_bk_plugin
from fta_web.action.utils import parse_bk_plugin_deployed_info

logger = logging.getLogger(__name__)


class GetVariablesResource(Resource):
    """
    获取所有的响应事件插件
    """

    def perform_request(self, validated_request_data):
        return VARIABLES


class RenderNoticeTemplate(Resource):
    """
    通知模板预渲染
    """

    class RequestSerializer(serializers.Serializer):
        template = serializers.CharField(required=True, label="消息模板", allow_blank=True)

    def perform_request(self, validated_request_data):
        language_suffix = ""
        language = translation.get_language()
        if language and language not in [settings.DEFAULT_LOCALE, "zh-cn", "zh-hans"]:
            language_suffix = f"_{language}"
        template_path_template = f"/notice/abnormal/{{}}/{{}}_content{language_suffix}.jinja"
        custom_template = validated_request_data["template"]

        context = {
            "content_template": custom_template,
            "level_name": _("致命"),
            "title_template": "{{business.bk_biz_name}} - {{alert.alert_name}}{{alarm.display_type}}",
            "alarm": {
                "target_type": "IP",
                "target_type_name": "IP",
                "target_string": "127.0.0.1,127.0.0.2",
                "dimension_string": _("磁盘=C,主机名=centos"),
                "collect_count": 2,
                "data_source_name": _("蓝鲸监控"),
                "data_source": "BKMONITOR",
                "current_value": 10,
                "detail_url": "http://example.com/",
                "notice_from": _("蓝鲸监控"),
                "company": _("蓝鲸"),
                "dimensions": {
                    "bk_target_ip": {"display_name": _("IP地址"), "display_value": "127.0.0.1"},
                    "bk_target_cloud_id": {"display_name": _("云区域"), "display_value": "0"},
                },
            },
            "alert": {"alert_name": _("磁盘使用率")},
            "event": {"level_name": _("致命"), "level_color": "#EA3636"},
            "strategy": {
                "id": 1,
                "strategy_id": 1,
                "name": _("磁盘使用率"),
                "scenario": "os",
                "source_type": "BKMONITOR",
                "bk_biz_id": 2,
                "item": {
                    "name": _("磁盘使用率"),
                    "result_table_id": "system.disk",
                    "metric_field": "in_use",
                    "unit": "%",
                    "agg_interval": 60,
                    "agg_method": "AVG",
                },
            },
            "content": None,
            "business": {
                "bk_biz_id": 2,
                "bk_biz_name": _("蓝鲸"),
                "bk_biz_developer_string": "user1,user2",
                "bk_biz_maintainer_string": "user1,user2",
                "bk_biz_tester_string": "user1,user2",
                "bk_biz_productor_string": "user1,user2",
                "operator_string": "user1,user2",
            },
            "target": {
                "business": {
                    "bk_biz_id": 2,
                    "bk_biz_name": _("蓝鲸"),
                    "bk_biz_developer_string": "user1,user2",
                    "bk_biz_maintainer_string": "user1,user2",
                    "bk_biz_tester_string": "user1,user2",
                    "bk_biz_productor_string": "user1,user2",
                    "operator_string": "user1,user2",
                },
                "process": defaultdict(
                    lambda: {
                        "bk_process_id": 1,
                        "bk_process_name": _("进程名"),
                        "bk_func_name": "java",
                        "bind_ip": "127.0.0.1",
                        "port": "80,8080-8090",
                        "process_template_id": 1,
                        "service_instance_id": 1,
                        "bk_host_id": 1,
                    }
                ),
                "processes": [
                    {
                        "bk_process_id": 1,
                        "bk_process_name": _("进程名"),
                        "bk_func_name": "java",
                        "bind_ip": "127.0.0.1",
                        "port": "80,8080-8090",
                        "process_template_id": 1,
                        "service_instance_id": 1,
                        "bk_host_id": 1,
                    }
                ],
                "service_instance": {
                    "service_instance_id": 1,
                    "name": "xxx_127.0.0.1",
                    "bk_host_id": 1,
                    "bk_module_id": 1,
                    "service_category_id": 1,
                },
                "service_instances": {
                    "service_instance_id": "1,2",
                    "name": "xxx_127.0.0.1,xxx_127.0.0.2",
                    "bk_host_id": "1,2",
                    "bk_module_id": "1,2",
                    "service_category_id": "1,2",
                },
                "host": {
                    "bk_host_id": 1,
                    "bk_biz_id": 2,
                    "bk_cloud_id": 0,
                    "bk_cloud_name": _("默认区域"),
                    "bk_host_innerip": "127.0.0.1",
                    "bk_host_outerip": "127.0.0.1",
                    "bk_host_name": "centos linux",
                    "bk_os_name": "linux centos",
                    "bk_os_type": 1,
                    "bk_comment": _("备注信息"),
                    "operator_string": "user1,user2",
                    "bk_bak_operator_string": "user1,user2",
                    "module_string": "module1,module2",
                    "set_string": "set1,set2",
                },
                "hosts": {
                    "bk_host_id": "1,2",
                    "bk_biz_id": "2,2",
                    "bk_cloud_id": "0,0",
                    "bk_cloud_name": f"{_('默认区域')},{_('默认区域')}",
                    "bk_host_innerip": "127.0.0.1,127.0.0.2",
                    "bk_host_outerip": "127.0.0.1,127.0.0.2",
                    "bk_host_name": "centos linux,centos linux",
                    "bk_os_name": "linux centos,linux centos",
                    "bk_os_type": "1,1",
                    "operator_string": "user1,user2",
                    "bk_bak_operator_string": "user1,user2",
                    "module_string": "module1,module2",
                    "set_string": "set1,set2",
                },
            },
            "action_instance": {
                "name": _("uwork机器重启"),
                "plugin_type_name": _("作业平台"),
                "assignees": "admin,yunweixiaoge",
                "operate_target_string": "127.0.0.1",
                "bk_biz_id": "2",
                "start_time": "1970-08-01 10:00:00+08:00",
                "duration": "130",
                "duration_string": "2m 10s",
                "status_display": _("执行中"),
                "opt_content": _("已经创建作业平台任务，点击查看详情http://www.job.com/"),
            },
        }

        single_content = defaultdict(
            lambda: {
                "level": _("告警级别：致命"),
                "begin_time": _("首次异常: 1970-01-01 00:00:00"),
                "time": _("最近异常: 1970-01-01 00:00:00"),
                "duration": "",
                "target_type": "",
                "data_source": "",
                "content": _("内容: 已持续10分钟, sum(in_user) > 10"),
                "biz": "",
                "target": _("目标: 蓝鲸[2] 127.0.0.1,127.0.0.2 (2)"),
                "dimension": _("维度: 磁盘=C"),
                "detail": _("详情: http://example.com/"),
                "current_value": "",
                "title": "",
                "related_info": _("关联信息: 集群(set1,set2) 模块(module1,module2)"),
            },
            {
                "sms": {
                    "level": _("告警级别：致命"),
                    "time": "",
                    "begin_time": "",
                    "duration": "",
                    "target_type": "",
                    "data_source": "",
                    "content": _("内容: 已持续10分钟, sum(in_user) > 10"),
                    "biz": "",
                    "target": _("目标: 蓝鲸[2] 127.0.0.1,127.0.0.2 (2)"),
                    "dimension": _("维度: 磁盘=C"),
                    "detail": _("告警ID: 12345"),
                    "current_value": "",
                    "title": "",
                },
                "mail": {
                    "level": NoticeRowRenderer.format("mail", _("告警级别"), _("致命")),
                    "time": NoticeRowRenderer.format("mail", _("最近异常"), "1970-01-01 00:00:00"),
                    "begin_time": NoticeRowRenderer.format("mail", _("首次异常"), "1970-01-01 00:00:00"),
                    "duration": NoticeRowRenderer.format("mail", _("持续时间"), _("10分钟")),
                    "target_type": NoticeRowRenderer.format("mail", _("告警对象"), "IP"),
                    "data_source": NoticeRowRenderer.format("mail", _("数据来源"), _("蓝鲸监控")),
                    "content": NoticeRowRenderer.format("mail", _("内容"), _("sum(in_user) > 10, 当前值15")),
                    "biz": NoticeRowRenderer.format("mail", _("告警业务"), _("蓝鲸[2]")),
                    "target": NoticeRowRenderer.format("mail", _("目标"), "127.0.0.1,127.0.0.2 (2)"),
                    "dimension": NoticeRowRenderer.format("mail", _("维度"), _("磁盘=C")),
                    "detail": "",
                    "current_value": NoticeRowRenderer.format("mail", _("当前值"), "15"),
                    "title": "",
                },
            },
        )

        multi_content = defaultdict(
            lambda: {
                "level": _("告警级别：致命"),
                "time": _("最近异常: 1970-01-01 00:00:00"),
                "begin_time": _("首次异常: 1970-01-01 00:00:00"),
                "duration": "",
                "target_type": "",
                "data_source": "",
                "content": _("内容: 已持续10分钟, sum(in_user) > 10,当前值 15%"),
                "biz": "",
                "target": _("目标: 蓝鲸[2] 127.0.0.1,127.0.0.2 (2)"),
                "dimension": _("维度: 磁盘=C"),
                "detail": _("详情: http://example.com/"),
                "current_value": "",
                "title": "",
                "related_info": "",
            },
            {
                "weixin": {
                    "level": _("告警级别：致命"),
                    "time": _("最近异常: 1970-01-01 00:00:00"),
                    "begin_time": _("首次异常: 1970-01-01 00:00:00"),
                    "duration": "",
                    "target_type": "",
                    "data_source": "",
                    "content": _("内容: 已持续10分钟, sum(in_user) > 10,当前值 15%"),
                    "biz": "",
                    "target": _("目标: 蓝鲸[2] 127.0.0.1,127.0.0.2 (2)"),
                    "dimension": _("维度: 磁盘=C"),
                    "detail": "",
                    "current_value": "",
                    "title": _("致命(1)、预警(2)"),
                },
                "sms": {
                    "level": _("告警级别：致命"),
                    "time": "",
                    "begin_time": "",
                    "duration": "",
                    "target_type": "",
                    "data_source": "",
                    "content": _("内容: [致命]磁盘使用率 10:10告警,已持续10分钟,sum(in_user) > 10,当前值 15%"),
                    "biz": "",
                    "target": _("目标: 蓝鲸[2] 127.0.0.1,127.0.0.2 (2)"),
                    "dimension": _("维度: 磁盘=C"),
                    "detail": _("告警ID: 12345"),
                    "current_value": "",
                    "title": _("致命(1)、预警(2)"),
                },
                "mail": {
                    "level": NoticeRowRenderer.format("mail", _("告警级别"), _("致命")),
                    "begin_time": "",
                    "time": NoticeRowRenderer.format(
                        "mail", _("时间范围"), "1970-01-01 00:00:00 - 1970-01-01 10:00:00"
                    ),
                    "duration": "",
                    "target_type": "",
                    "data_source": NoticeRowRenderer.format("mail", _("数据来源"), _("蓝鲸监控")),
                    "content": "",
                    "biz": NoticeRowRenderer.format("mail", _("告警业务"), _("蓝鲸[2]")),
                    "target": "",
                    "dimension": "",
                    "detail": "",
                    "current_value": "",
                    "title": "",
                },
            },
        )

        data = []
        notice_ways = [notice_way for notice_way in api.cmsi.get_msg_type() if notice_way["is_active"]]
        for notice_way in notice_ways:
            context["notice_way"] = notice_way["type"]
            single_error = multi_error = ""
            try:
                single = AlarmNoticeTemplate(
                    template_path_template.format("action", notice_way["type"]), language_suffix=language_suffix
                )
                context["content"] = single_content[notice_way["type"]]
                single = single.render(context)
            except Exception as e:
                logger.info(f"template render error, {e}")
                single = custom_template
                single_error = str(e)

            try:
                multi = AlarmNoticeTemplate(
                    template_path_template.format("converge", notice_way["type"]), language_suffix=language_suffix
                )
                context["content"] = multi_content[notice_way["type"]]
                multi = multi.render(context)
            except Exception as e:
                logger.info(f"template render error, {e}")
                multi = custom_template
                multi_error = str(e)

            data.append(
                {
                    "type": notice_way["type"],
                    "label": _(notice_way["label"]),
                    "messages": [
                        {"name": _("同维度告警通知"), "message": single, "error": single_error},
                        {"name": _("汇总告警通知"), "message": multi, "error": multi_error},
                    ],
                }
            )

        return data


class GetPluginsResource(Resource):
    """
    获取所有的响应事件插件
    """

    class ActionPluginListSlz(serializers.ModelSerializer):
        class Meta:
            model = ActionPlugin
            fields = ("id", "name", "plugin_type", "has_child", "description", "plugin_source")

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        queryset = ActionPlugin.objects.all().exclude(
            plugin_key__in=[ActionPluginType.NOTICE, ActionPluginType.AUTHORIZE]
        )

        internal_data = self.ActionPluginListSlz(
            queryset.filter(plugin_source="builtin"),
            many=True,
        ).data
        all_peripheral_data = []
        all_bkplugin_data = []
        for peripheral_plugin in queryset.exclude(plugin_source="builtin"):
            data = self.ActionPluginListSlz(peripheral_plugin).data

            new_info = peripheral_plugin.get_plugin_template_create_url(**validated_request_data)
            data["description"] = data["description"].format(plugin_url=new_info.get("url", ""))
            data["new_info"] = new_info
            if data["plugin_source"] == "bk_plugin":
                all_bkplugin_data.append(data)
            else:
                all_peripheral_data.append(data)

        rsp_data = [
            {"name": _("内置"), "children": internal_data},
            {"name": _("周边系统"), "children": all_peripheral_data},
            {"name": _("蓝鲸插件"), "children": all_bkplugin_data},
        ]

        return rsp_data


class GetPluginTemplatesResource(Resource):
    """
    获取插件模版列表
    """

    class RequestSerializer(serializers.Serializer):
        plugin_id = serializers.IntegerField(required=True, label="插件ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def get_object(self, plugin_id):
        """获取到对应的插件，不存在则抛出异常"""
        try:
            return ActionPlugin.objects.get(id=plugin_id)
        except ActionPlugin.DoesNotExist:
            raise

    def perform_request(self, validated_request_data):
        plugin_instance = self.get_object(validated_request_data["plugin_id"])
        request_schema = plugin_instance.config_schema.get("template", {})
        rsp_data = plugin_instance.perform_resource_request("template", **validated_request_data)
        return {
            "name": request_schema.get("name", plugin_instance.name),
            "new_info": plugin_instance.get_plugin_template_create_url(**validated_request_data),
            "templates": rsp_data,
        }


class GetTemplateDetailResource(GetPluginTemplatesResource):
    class RequestSerializer(serializers.Serializer):
        plugin_id = serializers.IntegerField(required=True, label="插件ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        template_id = serializers.CharField(required=True, label="系统模版ID")

    def perform_request(self, validated_request_data):
        plugin_instance = self.get_object(validated_request_data["plugin_id"])
        request_schema = plugin_instance.config_schema["detail"]
        detail_params = plugin_instance.perform_resource_request("detail", **validated_request_data)
        rsp_data = []
        for param in detail_params:
            rsp_data.append(self.render_input_template(**param))

        return {"name": request_schema.get("name", plugin_instance.name), "params": rsp_data}

    @staticmethod
    def render_input_template(name="", key="", value="", placeholder="", help_text="", required=True, **kwargs):
        """
        渲染form模版
        :param placeholder:
        :param name:
        :param key:
        :param value:默认值
        :param required:是否必须
        :return:
        """
        if required in [False, "false", "False", "0", 0]:
            required = False

        return {
            "formItemProps": {"label": name or key, "required": required, "property": key, "help_text": help_text},
            "type": "input",
            "key": _(key),
            "value": value,
            "formChildProps": {"placeholder": placeholder},
            "rules": [{"message": _("必填项不可为空"), "required": True, "trigger": "blur"}] if required else [],
        }


class GetDimensionsResource(Resource):
    """
    获取所有的响应事件插件
    """

    def perform_request(self, validated_request_data):
        return [{"key": key, "name": name} for key, name in CONVERGE_DIMENSION.items()]


class GetConvergeFunctionResource(Resource):
    """
    获取所有的响应事件插件
    """

    def perform_request(self, validated_request_data):
        return [
            {
                "key": key,
                "name": name,
                "description": str(CONVERGE_FUNCTION_DESCRIPTION.get(key, "")),
            }
            for key, name in CONVERGE_FUNCTION.items()
            if key not in [ConvergeFunction.COLLECT, ConvergeFunction.COLLECT_ALARM]
        ]


class BatchCreateResource(Resource):
    """
    批量创建处理任务，通过调用后台接口实现
    """

    RequestSerializer = BatchCreateDataSerializer

    def perform_request(self, validated_request_data):
        validated_request_data["creator"] = get_request_username()
        return BatchCreateActionBackendResource().request(**validated_request_data)


class CreateChatGroupResource(Resource):
    """
    一键拉群接口
    """

    class RequestSerializer(serializers.Serializer):
        chat_members = serializers.ListField(child=serializers.CharField(), required=True, label="群成员")
        alert_ids = serializers.ListField(child=serializers.CharField(), required=True, label="告警ID列表")
        content_type = serializers.ListField(
            child=serializers.ChoiceField(
                choices=[(ChatMessageType.DETAIL_URL, _("告警链接")), (ChatMessageType.ALARM_CONTENT, _("告警内容"))]
            ),
            required=True,
            label="发送通知内容",
        )
        bk_biz_id = serializers.CharField(required=True, label="业务ID")

    @staticmethod
    def convert_action_data(validated_request_data):
        try:
            action_config = ActionConfig.objects.get(name=_("「快捷」一键拉群"), is_builtin=True)
        except ActionConfig.DoesNotExist:
            logger.info("config of builtin create-chat-group is not existed")
            raise

        alert_ids = validated_request_data["alert_ids"]
        message_template = "{{content.detail}}"
        if ChatMessageType.ALARM_CONTENT in validated_request_data["content_type"]:
            template_path = "notice/abnormal/action/default_content.jinja"
            if len(alert_ids) > 1:
                template_path = "notice/abnormal/converge/default_content.jinja"
            try:
                message_template = AlarmNoticeTemplate.get_template_source(template_path)
            except TemplateDoesNotExist:
                # 不存在直接用告警模板
                logger.info("notice template does not exist， use user content")
                message_template = "{{user_content}}"

        notice_title = _(GlobalConfig.get("NOTICE_TITLE", "蓝鲸监控"))
        chat_name_template = notice_title + " - {{alarm.name}}[{{alarm.id}}]"
        if len(validated_request_data["alert_ids"]) > 1:
            chat_name_template = notice_title + _(" - 【{}】等{}个告警").format("{{alarm.name}}", len(alert_ids))

        operator = get_request_username()
        action_data = {
            "operate_data_list": [
                {
                    "alert_ids": validated_request_data["alert_ids"],
                    "action_configs": [
                        {
                            "execute_config": {
                                "template_detail": {
                                    "chat_owner": operator,
                                    "chat_name": chat_name_template,
                                    "chat_members": ",".join(validated_request_data["chat_members"]),
                                    "message": message_template,
                                },
                                "template_id": action_config.execute_config["template_id"],
                                "timeout": action_config.execute_config["timeout"],
                            },
                            "plugin_id": action_config.plugin_id,
                            "name": action_config.name,
                            "is_enabled": action_config.is_enabled,
                            "bk_biz_id": action_config.bk_biz_id,
                            "config_id": action_config.id,
                        }
                    ],
                }
            ],
            "bk_biz_id": validated_request_data["bk_biz_id"],
            "creator": operator,
        }
        return action_data

    def perform_request(self, validated_request_data):
        action_data = self.convert_action_data(validated_request_data)
        return BatchCreateActionBackendResource().request(**action_data)


class AssignAlertResource(Resource):
    """
    分派告警给到指定人员
    """

    class RequestSerializer(serializers.Serializer):
        appointees = serializers.ListField(child=serializers.CharField(), required=True, label="指派成员")
        alert_ids = serializers.ListField(child=serializers.CharField(), required=True, label="告警ID列表")
        reason = serializers.CharField(required=True, label="分派原因")
        notice_ways = serializers.ListField(required=True, child=serializers.CharField(), label="通知类型")
        bk_biz_id = serializers.CharField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        operator = get_request_username()
        operator_display_name = get_user_display_name(operator)
        appointees = validated_request_data["appointees"]
        appointees_display_names = [get_user_display_name(appointee) for appointee in appointees]
        appointees_set = set(appointees)
        assign_reason = validated_request_data["reason"]
        alert_ids = validated_request_data["alert_ids"]
        current_time = int(time.time())
        alert_log = AlertLog(
            **dict(
                op_type=AlertLog.OpType.ACTION,
                alert_id=alert_ids,
                description=_("{creator}分派告警给({appointees}), 分派原因：{reason}").format(
                    creator=operator_display_name, appointees=",".join(appointees_display_names), reason=assign_reason
                ),
                time=current_time,
                create_time=current_time,
                event_id=current_time,
            )
        )
        alerts = AlertDocument.mget(alert_ids)
        alert_assignees = {alert.id: set(list(alert.appointee) + list(alert.assignee)) for alert in alerts}
        all_diff_assignees = []
        for alert in alerts:
            # 负责人 + 分派人差集
            diff_assignees = appointees_set.difference(alert_assignees[alert.id])
            all_diff_assignees.append(diff_assignees)
            # 分派人差集，不存在需要更新
            diff_appointees = appointees_set.difference(set(alert.appointee))

            if diff_appointees:
                alert.appointee.extend(list(diff_appointees))
                alert.assignee.extend(list(diff_assignees))

        notice_receivers = set()
        for notice_receiver in all_diff_assignees:
            notice_receivers = notice_receivers | notice_receiver

        assigned_alerts = [
            AlertDocument(id=alert.id, appointee=list(alert.appointee), assignee=list(alert.assignee))
            for alert in alerts
        ]
        AlertLog.bulk_create([alert_log])
        AlertDocument.bulk_create(assigned_alerts, action=BulkActionType.UPDATE)
        validated_request_data["notice_receivers"] = notice_receivers
        validated_request_data["operator"] = operator
        # 可以考虑改成同步
        notify_to_appointee.delay(validated_request_data)
        return {"assigned_alerts": [alert.id for alert in alerts], "notice_receivers": notice_receivers}


class GetActionParamsResource(Resource):
    """
    根据ID获取执行任务参数内容
    """

    RequestSerializer = GetCreateParamsSerializer

    def perform_request(self, validated_request_data):
        action_configs = GetActionParamsBackendResource().request(**validated_request_data)["action_configs"]

        for action_config in action_configs:
            if action_config["execute_config"].get("template_id"):
                # 周边系统刚进行数据格式化
                request_param = {
                    "bk_biz_id": validated_request_data["bk_biz_id"],
                    "plugin_id": action_config["plugin_id"],
                    "template_id": action_config["execute_config"]["template_id"],
                }
                config_detail = action_config["execute_config"]["template_detail"]
                action_params = GetTemplateDetailResource().request(**request_param)["params"]
                for param in action_params:
                    param["value"] = config_detail.get(param["key"]) or param["value"]
                action_config["params"] = action_params
        return action_configs


class GetActionConfigByAlerts(Resource):
    """
    根据告警获取到对应的告警ID
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.CharField(label="业务ID", required=True)
        alert_ids = serializers.ListField(
            label="告警ID集合", required=True, child=serializers.CharField(allow_blank=False)
        )

    def perform_request(self, validated_request_data):
        alert_ids = validated_request_data["alert_ids"]
        hit_results = ActionInstanceDocument.mget_by_alert(alert_ids=alert_ids, fields=["action_config_id", "alert_id"])
        alert_groups = {}
        all_configs = []
        for hit in hit_results:
            conf_id = hit.action_config_id
            if not conf_id:
                continue
            all_configs.append(conf_id)
            for alert in hit.alert_id:
                if alert_groups.get(alert):
                    alert_groups[alert].append(conf_id)
                else:
                    alert_groups[alert] = [conf_id]
        all_configs = {
            str(item["id"]): item
            for item in ActionConfig.objects.exclude(plugin_id=ActionConfig.NOTICE_PLUGIN_ID)
            .filter(id__in=all_configs)
            .values("id", "name")
        }
        config_groups = {}

        for alert_id, configs in alert_groups.items():
            config_key = json.dumps(set(configs))

            if config_key in alert_groups:
                config_groups[config_key]["alert_ids"].append(alert_id)
            else:
                action_configs = [config for config_id, config in all_configs.items() if int(config_id) in configs]
                config_groups[config_key] = {"alert_ids": [alert_id], "action_configs": action_configs}
        return list(config_groups.values())


class CreateDemoActionResource(Resource):
    # RequestSerializer = CreateDemoActionSlz

    def perform_request(self, validated_request_data):
        action_config = validated_request_data
        action_plugin = ActionPluginSlz(instance=ActionPlugin.objects.get(id=validated_request_data["plugin_id"])).data
        demo_action = ActionInstance.objects.create(
            signal="demo",
            strategy_id=0,
            alert_level=1,
            action_config=action_config,
            action_plugin=action_plugin,
            bk_biz_id=action_config["bk_biz_id"],
            assignee=[get_request_username()],
        )
        return {"action_id": demo_action.id}


class GetDemoActionDetailResource(Resource):
    """
    获取调试任务的结果
    """

    class RequestSerializer(serializers.Serializer):
        action_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        demo_action = ActionInstance.objects.get(id=validated_request_data["action_id"])
        return {
            "status": demo_action.status,
            "is_finished": demo_action.status in ActionStatus.END_STATUS,
            "content": demo_action.get_content(),
        }


class RegisterBkPlugin(Resource):
    """
    注册蓝鲸插件套餐类型
    """

    class RequestSerializer(serializers.Serializer):
        plugin_code = serializers.CharField(required=True)

    def perform_request(self, validated_request_data):
        # 1.根据plugin_code获取蓝鲸插件详细部署信息
        response_data = api.bk_plugin.bk_plugin_deployed_info(**validated_request_data)

        # 2.解析蓝鲸插件部署信息
        deployed, plugin_code, plugin_info = parse_bk_plugin_deployed_info(response_data)
        if not deployed:
            return f"failed: bk_plugin: [{plugin_code}] does not deployed"

        # 3.根据 plugin_code update_or_create
        instance, created = ActionPlugin.origin_objects.update_or_create(plugin_key=plugin_code, defaults=plugin_info)
        return "success: {} bk_plugin: [{}]".format("register" if created else "update", instance.name)


class BatchRegisterBkPlugin(Resource):
    """
    批量注册蓝鲸插件套餐类型
    """

    def perform_request(self, validated_request_data):
        # if not get_request().user.is_superuser:
        #     raise PermissionError(_("您无权限批量注册蓝鲸插件类型的相应动作插件，请联系管理员处理"))
        scheduled_register_bk_plugin.delay()
        return _("正在注册蓝鲸插件套餐，注册结果请前往日志查看")
