# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import datetime
import logging

from celery import shared_task
from django.conf import settings
from django.utils.translation import gettext as _

from bkmonitor.models import ActionInstance, ActionPlugin
from bkmonitor.utils.send import NoneTemplateSender
from constants.action import ActionSignal, ActionStatus
from core.drf_resource import api
from fta_web.action.utils import (
    compile_assign_action_config,
    parse_bk_plugin_deployed_info,
)

logger = logging.getLogger("root")


@shared_task(ignore_result=True)
def scheduled_register_bk_plugin():
    """
    批量注册蓝鲸插件到系统中
    """
    request_data = {"has_deployed": True, "distributor_code_name": settings.APP_CODE}

    # 1.批量获取蓝鲸插件部署信息
    response_data = api.bk_plugin.bk_plugin_deployed_info_batch(**request_data)

    logger.info("Begin to register bk_plugin")
    registered_plugins = []
    updated_plugins = []
    failed_plugins = []

    # 2.解析部署信息
    for plugin in response_data.get("results", []):
        deployed, plugin_code, plugin_info = parse_bk_plugin_deployed_info(plugin)
        if not deployed:
            failed_plugins.append(plugin_code)
            logger.info("failed: bk_plugin: [{}] does not deployed".format(plugin_code))
        instance, created = ActionPlugin.origin_objects.update_or_create(plugin_key=plugin_code, defaults=plugin_info)
        registered_plugins.append(plugin_code) if created else updated_plugins.append(plugin_code)
        logger.info("success: {} bk_plugin: [{}]".format("register" if created else "update", instance.name))

    logger.info(
        "registered {} bk_plugin: {}, ".format(len(registered_plugins), registered_plugins),
        "updated {} bk_plugin: {}, ".format(len(updated_plugins), updated_plugins),
        "failed {} bk_plugin: {}".format(len(failed_plugins), failed_plugins),
    )


@shared_task(ignore_result=True)
def notify_to_appointee(validated_request_data):
    """
    通知分派人员
    :return:
    """
    alert_ids = validated_request_data["alert_ids"]
    logger.info("[notify appointee] begin to notice appointee for alert(%s)", alert_ids)
    receivers = list(validated_request_data["notice_receivers"])

    if not receivers:
        logger.info("[notify appointee] finished due to no receivers, request data %s", validated_request_data)
        return

    action = ActionInstance.objects.create(
        signal=ActionSignal.MANUAL,
        action_plugin={"id": 1, "plugin_type": "notice", "plugin_name": _("通知")},
        status=ActionStatus.SLEEP,
        action_config={
            "plugin_id": 1,
            "name": _("告警分派"),
            "is_enabled": True,
            "bk_biz_id": validated_request_data["bk_biz_id"],
            "config_id": None,
        },
        bk_biz_id=validated_request_data["bk_biz_id"],
        assignee=receivers,
        create_user=validated_request_data["operator"],
        strategy_id=0,
        action_config_id=0,
        alerts=alert_ids,
        inputs=validated_request_data,
    )

    action_configs = compile_assign_action_config(validated_request_data)

    try:
        action_params = api.monitor.get_action_params_backend(
            {
                "action_configs": action_configs,
                "alert_ids": alert_ids,
                "action_id": action.id,
                "bk_biz_id": validated_request_data["bk_biz_id"],
            }
        )["action_configs"]
    except BaseException as error:
        logger.exception("[notify appointee] failed: %s, request data %s", str(error), validated_request_data)
        return

    if not action_params:
        logger.info("[notify appointee] finished due to empty params, request data %s", validated_request_data)
        return

    notice_results = {}

    for action_param in action_params:
        execute_config = action_param["execute_config"]
        notice_way = execute_config["context_inputs"]["notice_way"]
        notify_sender = NoneTemplateSender(
            title=execute_config["template_detail"]["title"],
            content=execute_config["template_detail"]["message"],
            context=action_param.get("alert_context", {}),
        )
        notice_results[notice_way] = notify_sender.send(notice_way, receivers)

    action.outputs = {"notice_results": notice_results, "action_params": action_params}
    action.status = ActionStatus.SUCCESS
    action.end_time = datetime.datetime.now()
    action.save()

    logger.info("[notify appointee] finished, notice action(%s)", action.id)
