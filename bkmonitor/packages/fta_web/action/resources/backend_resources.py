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
from collections import defaultdict

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
from bkmonitor.utils.template import CustomTemplateRenderer, Jinja2Renderer, jinja_render
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


class GetDemoActionContextResource(Resource):
    """
    基于真实告警预览套餐变量渲染

    接收 alert_ids + 变量字典，构建告警上下文并在原始对象上完成 Jinja2 渲染后返回。
    不传 variables 则仅返回序列化后的上下文字典。
    """

    class RequestSerializer(serializers.Serializer):
        alert_ids = serializers.ListField(child=serializers.CharField(), required=True, label="告警ID列表")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        variables = serializers.DictField(required=False, default={}, label="待渲染的变量字典")

    @classmethod
    def build_fake_action(cls, alerts, alert_ids, bk_biz_id):
        """构造伪 ActionInstance 用于上下文构建，不入库。参考 do_create_action 的构建逻辑。"""
        from alarm_backends.core.control.strategy import Strategy
        from constants.alert import EventSeverity

        alert = alerts[0]
        strategy_id = alert.strategy_id or 0
        strategy = Strategy(strategy_id).config if strategy_id else {}
        if not strategy:
            strategy = alert.strategy or {}

        try:
            alert_level = alert.severity or EventSeverity.REMIND
        except (ValueError, TypeError):
            alert_level = EventSeverity.REMIND

        # 业务ID：优先从告警事件获取，参考 do_create_action
        try:
            action_bk_biz_id = alert.event.bk_biz_id or bk_biz_id
        except Exception:
            action_bk_biz_id = bk_biz_id

        assignee = cls.get_alert_assignee(alert, strategy)

        alert_create_time = alert.create_time
        alert_end_time = alert.latest_time or datetime.now()

        inputs = {"alert_latest_time": alert.latest_time, "is_alert_shielded": False, "shield_ids": []}

        default_dict = defaultdict(str)

        return ActionInstance(
            id=0,
            signal=ActionSignal.DEMO,
            strategy_id=strategy_id,
            strategy=strategy,
            strategy_relation_id=0,
            dimensions=[],
            dimension_hash="",
            alerts=alert_ids,
            alert_level=alert_level,
            status="received",
            failure_type="",
            ex_data=default_dict,
            create_time=alert_create_time,
            end_time=alert_end_time,
            update_time=alert_create_time,
            action_plugin=default_dict,
            action_config=default_dict,
            action_config_id=0,
            bk_biz_id=action_bk_biz_id,
            is_parent_action=False,
            parent_action_id=0,
            sub_actions=[],
            assignee=assignee,
            inputs=inputs,
            outputs=default_dict,
            real_status="",
            is_polled=False,
            need_poll=False,
            execute_times=0,
            generate_uuid="",
        )

    @staticmethod
    def get_alert_assignee(alert, strategy):
        """基于策略 notice 配置，通过 AlertAssigneeManager 获取告警负责人。参考 do_create_action 中的分派逻辑。"""
        from alarm_backends.service.fta_action.tasks.alert_assign import AlertAssigneeManager

        notice = strategy.get("notice", {})
        assignee = []
        if notice:
            try:
                assign_mode = notice.get("options", {}).get("assign_mode")
                upgrade_config = notice.get("options", {}).get("upgrade_config", {})
                assignee_manager = AlertAssigneeManager(
                    alert,
                    notice_user_groups=notice.get("user_groups"),
                    assign_mode=assign_mode,
                    upgrade_config=upgrade_config,
                )
                assignee = assignee_manager.get_appointees() or assignee_manager.get_origin_notice_receivers()
            except Exception:
                logger.exception("通过 AlertAssigneeManager 获取 assignee 失败, alert(%s)", alert.id)

        if not assignee:
            # 兜底：从告警文档已有字段获取
            alert_dict = alert.to_dict()
            assignee = alert_dict.get("appointee") or alert_dict.get("assignee") or []

        return assignee

    def perform_request(self, validated_request_data):
        alert_ids = validated_request_data["alert_ids"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        variables = validated_request_data.get("variables", {})

        alerts = AlertDocument.mget(ids=alert_ids)
        if not alerts:
            raise ValueError(_("告警不存在或已过期: {}").format(alert_ids))

        fake_action = self.build_fake_action(alerts, alert_ids, bk_biz_id)

        try:
            context = ActionContext(action=fake_action, alerts=alerts, use_alert_snap=True).get_dictionary()
            rendered_variables = {key: jinja_render(value, context) for key, value in variables.items()}
        except Exception as e:
            logger.exception("基于真实告警构建上下文失败: %s", e)
            raise ValueError(_("基于真实告警构建上下文失败: {}").format(e))

        return {"variables": rendered_variables}
