"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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

from django.utils.translation import gettext as _

from api.itsm.default import TokenVerifyResource
from bkmonitor.action.serializers import (
    ActionConfigDetailSlz,
    ActionPluginSlz,
    BatchCreateDataSerializer,
    GetCreateParamsSerializer,
)
from bkmonitor.documents import AlertLog
from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.base import BulkActionType
from bkmonitor.models.fta import ActionConfig, ActionInstance, ActionPlugin
from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.template import CustomTemplateRenderer, Jinja2Renderer
from bkmonitor.utils.user import get_user_display_name
from bkmonitor.views import serializers
from constants.action import ActionSignal
from core.drf_resource import Resource

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
        operate_data_list = validated_request_data["operate_data_list"]
        creator = validated_request_data["creator"]
        generate_uuid = count_md5([json.dumps(operate_data_list), int(datetime.now().timestamp())])
        action_plugins = {
            str(plugin["id"]): plugin for plugin in ActionPluginSlz(instance=ActionPlugin.objects.all(), many=True).data
        }
        action_logs = []
        handled_alerts = []
        alert_ids = []
        for operate_data in operate_data_list:
            alert_ids = operate_data["alert_ids"]
            alerts = AlertDocument.mget(ids=alert_ids)
            if not alerts:
                continue
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

                display_name = get_user_display_name(creator)
                action_logs.append(
                    AlertLog(
                        **dict(
                            op_type=AlertLog.OpType.ACTION,
                            alert_id=action.alerts,
                            description=_("{creator}通过页面创建{plugin_name}任务【{action_name}】进行告警处理").format(
                                plugin_name=action_config.get("plugin_name", _("手动处理")),
                                creator=display_name,
                                action_name=action_config.get("name"),
                            ),
                            time=int(time.time()),
                            create_time=int(time.time()),
                            event_id=f"{int(action.create_time.timestamp())}{action.id}",
                            operator=creator,
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

        if config_ids:
            action_configs = ActionConfigDetailSlz(ActionConfig.objects.filter(id__in=config_ids), many=True).data

        alerts = AlertDocument.mget(validated_request_data["alert_ids"])
        action = None
        if action_id:
            try:
                action = ActionInstance.objects.get(id=action_id)
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
