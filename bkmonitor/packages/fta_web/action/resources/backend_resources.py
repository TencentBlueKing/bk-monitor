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
import copy
import json
import logging
import re
import time
from datetime import datetime

from django.conf import settings
from django.template import TemplateDoesNotExist
from django.utils.translation import ugettext as _
from rest_framework.exceptions import PermissionDenied, ValidationError

from api.itsm.default import TokenVerifyResource
from bkmonitor.action.serializers import (
    ActionConfigDetailSlz,
    ActionPluginSlz,
    BatchCreateDataSerializer,
    CreateChatGroupSerializer,
    GetCreateParamsSerializer,
)
from bkmonitor.documents import AlertLog
from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.base import BulkActionType
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.models import GlobalConfig
from bkmonitor.models.fta import ActionConfig, ActionInstance, ActionPlugin
from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.request import get_request, get_request_username
from bkmonitor.utils.template import AlarmNoticeTemplate, CustomTemplateRenderer, Jinja2Renderer
from bkmonitor.views import serializers
from constants.action import GLOBAL_BIZ_ID, ActionSignal, ChatMessageType
from core.drf_resource import Resource
from fta_web.action.utils import filter_alerts_by_biz

try:
    # 后台接口，需要引用后台代码
    from alarm_backends.core.cache.key import FTA_ACTION_LIST_KEY
    from alarm_backends.core.context import ActionContext
    from alarm_backends.service.fta_action.utils import PushActionProcessor
except BaseException:
    FTA_ACTION_LIST_KEY = None

logger = logging.getLogger(__name__)


class ITSMCallbackResource(Resource):
    """
    获取所有的响应事件插件
    """

    ACTION_ID_MATCH = re.compile(r"\(\s*([\w\|]+)\s*\)")

    class RequestSerializer(serializers.Serializer):
        sn = serializers.CharField(required=True, label="工单号")
        title = serializers.CharField(required=True, label="工单标题")
        updated_by = serializers.CharField(required=True, label="更新人")
        approve_result = serializers.BooleanField(required=True, label="审批结果")
        token = serializers.CharField(required=True, label="校验token")

    def perform_request(self, validated_request_data):
        verify_data = TokenVerifyResource().request({"token": validated_request_data["token"]})
        if not verify_data.get("is_valid", False):
            return {"message": "Error Token", "result": False}

        queryset = ActionInstance.objects.all()

        # 通过title找到对应的Id
        action_id = self.ACTION_ID_MATCH.findall(validated_request_data["title"])
        if not action_id:
            return {"message": "Error ticket", "result": False}
        try:
            action_inst = queryset.get(id=action_id[0])
        except ActionInstance.DoesNotExist:
            return dict(message=_("对应的ID{}不存在").format(action_id), result=False)

        # 推送回调内容至队列进行处理
        PushActionProcessor.push_action_to_execute_queue(
            action_inst, callback_func="approve_callback", kwargs=validated_request_data
        )
        return dict(result=True, message="success")


class BatchCreateActionResource(Resource):
    """
    创建任务接口
    """

    class RequestSerializer(BatchCreateDataSerializer):
        creator = serializers.CharField(required=True, label="执行人")

    def perform_request(self, validated_request_data):
        alert_groups = [
            filter_alerts_by_biz(AlertDocument.mget(ids=data["alert_ids"]), validated_request_data["bk_biz_id"])
            for data in validated_request_data["operate_data_list"]
        ]
        return self._create_actions(validated_request_data, alert_groups)

    def _create_actions(self, validated_request_data, alert_groups):
        operate_data_list = validated_request_data["operate_data_list"]
        creator = validated_request_data["creator"]
        generate_uuid = count_md5([json.dumps(operate_data_list), int(datetime.now().timestamp())])
        action_plugins = {
            str(plugin["id"]): plugin for plugin in ActionPluginSlz(instance=ActionPlugin.objects.all(), many=True).data
        }
        action_logs = []
        handled_alerts = []
        alert_ids = []
        alerts = []
        for operate_data, alerts in zip(operate_data_list, alert_groups):
            if not alerts:
                continue
            alert_ids = [alert.id for alert in alerts]
            for action_config in operate_data["action_configs"]:
                action = ActionInstance.objects.create(
                    signal=ActionSignal.MANUAL,
                    strategy_id=alerts[0].strategy_id or 0,
                    alert_level=alerts[0].severity,
                    alerts=alert_ids,
                    action_config_id=action_config["config_id"],
                    action_config=action_config,
                    action_plugin=action_plugins.get(str(action_config["plugin_id"])),
                    bk_biz_id=validated_request_data["bk_biz_id"],
                    assignee=[creator],
                    generate_uuid=generate_uuid,
                )

                action_logs.append(
                    AlertLog(
                        **dict(
                            op_type=AlertLog.OpType.ACTION,
                            alert_id=action.alerts,
                            description=_("{creator}通过页面创建{plugin_name}任务【{action_name}】进行告警处理").format(
                                plugin_name=action_config.get("plugin_name", _("手动处理")),
                                creator=creator,
                                action_name=action_config.get(
                                    "name",
                                ),
                            ),
                            time=int(time.time()),
                            create_time=int(time.time()),
                            event_id="{}{}".format(int(action.create_time.timestamp()), action.id),
                        )
                    )
                )

            handled_alerts = [
                AlertDocument(
                    id=alert.id, is_handled=True, assignee=list(set([man for man in alert.assignee] + [creator]))
                )
                for alert in alerts
            ]
        actions = PushActionProcessor.push_actions_to_queue(generate_uuid, alerts)
        # 更新告警状态和流转日志
        AlertLog.bulk_create(action_logs)
        AlertDocument.bulk_create(handled_alerts, action=BulkActionType.UPDATE)

        return {"actions": list(actions), "alert_ids": alert_ids}


class CreateChatGroupActionResource(BatchCreateActionResource):
    """跨业务拉群只使用内置套餐，全部告警授权通过后才创建任务。"""

    RequestSerializer = CreateChatGroupSerializer

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
        request = get_request()
        if getattr(request, "token", None):
            raise PermissionDenied()
        jwt = getattr(request, "jwt", None)
        if jwt:
            if (
                not jwt.is_valid
                or not jwt.user.verified
                or not jwt.user.username
                or not jwt.app.verified
                or not jwt.app.app_code
            ):
                raise PermissionDenied()
        else:
            # 旧 ESB 可允许应用自行指定用户名，只信任监控 SaaS 转发的操作者。
            if (
                not settings.SAAS_APP_CODE
                or request.META.get("HTTP_BK_APP_CODE") != settings.SAAS_APP_CODE
                or not request.META.get("HTTP_BK_USERNAME")
            ):
                raise PermissionDenied()
        username = getattr(getattr(request, "user", None), "username", "")
        if not username:
            raise PermissionDenied()

        alert_ids = list(dict.fromkeys(validated_request_data["alert_ids"]))
        alerts_by_id = {alert.id: alert for alert in AlertDocument.mget(ids=alert_ids)}
        if set(alert_ids) != alerts_by_id.keys():
            raise ValidationError(_("部分告警不存在或无权访问，请刷新后重试"))
        alerts = [alerts_by_id[alert_id] for alert_id in alert_ids]
        permission = Permission(username=username)
        # API 服务默认豁免 IAM；跨业务拉群必须显式校验真实操作者。
        permission.skip_check = False
        for bk_biz_id in sorted({int(alert.event.bk_biz_id) for alert in alerts}):
            if not bk_biz_id:
                raise PermissionDenied()
            permission.is_allowed_by_biz(bk_biz_id, ActionEnum.VIEW_EVENT, raise_exception=True)

        params = dict(validated_request_data, alert_ids=alert_ids, bk_biz_id=str(alerts[0].event.bk_biz_id))
        action_data = BatchCreateActionResource().validate_request_data(self.convert_action_data(params))
        return self._create_actions(action_data, [alerts])


class GetActionParamsByConfigResource(Resource):
    """
    创建任务接口
    """

    RequestSerializer = GetCreateParamsSerializer

    def jinja_render(self, template_value, alert_context):
        """
        jinja渲染
        :param alert_context:
        :param template_value:
        :return:
        """
        if isinstance(template_value, str):
            return Jinja2Renderer.render(template_value, alert_context) or template_value
        if isinstance(template_value, dict):
            render_value = {}
            for key, value in template_value.items():
                render_value[key] = self.jinja_render(value, alert_context)
            return render_value
        if isinstance(template_value, list):
            return [self.jinja_render(value, alert_context) for value in template_value]
        return template_value

    def perform_request(self, validated_request_data):
        config_ids = validated_request_data.get("config_ids")
        action_configs = validated_request_data.get("action_configs", [])
        action_id = validated_request_data.get("action_id")

        bk_biz_id = str(validated_request_data["bk_biz_id"])

        if config_ids:
            # 只取请求业务与全局业务下的套餐配置
            action_configs = ActionConfigDetailSlz(
                ActionConfig.objects.filter(id__in=config_ids, bk_biz_id__in=[GLOBAL_BIZ_ID, bk_biz_id]), many=True
            ).data

        alerts = filter_alerts_by_biz(AlertDocument.mget(validated_request_data["alert_ids"]), bk_biz_id)
        action = None
        if action_id:
            try:
                action = ActionInstance.objects.get(id=action_id, bk_biz_id=bk_biz_id)
            except ActionInstance.DoesNotExist:
                logger.info("action(%s) not exist", action_id)

        for action_config in action_configs:
            context_inputs = action_config["execute_config"].get("context_inputs", {})
            alert_context = ActionContext(
                action=action, alerts=alerts, use_alert_snap=True, dynamic_kwargs=context_inputs
            ).get_dictionary()
            CustomTemplateRenderer.render(content="", context=alert_context)
            action_config["execute_config"]["origin_template_detail"] = copy.deepcopy(
                action_config["execute_config"]["template_detail"]
            )
            action_config["execute_config"]["template_detail"] = self.jinja_render(
                action_config["execute_config"]["template_detail"], alert_context
            )
            action_config["alert_ids"] = validated_request_data["alert_ids"]
            action_config["alert_context"] = {
                key: value for key, value in alert_context.items() if isinstance(value, str)
            }
        return {"result": True, "action_configs": action_configs}
