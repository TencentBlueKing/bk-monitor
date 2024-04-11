# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http:#opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import base64
import copy
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from json import JSONDecodeError
from unittest.mock import MagicMock, patch

import fakeredis
import mock
import pytest
import pytz
from django.conf import settings
from django.db import IntegrityError
from django.test import TestCase, TransactionTestCase
from django.utils.translation import ugettext as _
from elasticsearch_dsl import AttrDict

from alarm_backends.core.alert import Alert, Event
from alarm_backends.core.cache.key import (
    ALERT_SNAPSHOT_KEY,
    CONVERGE_LIST_KEY,
    FTA_ACTION_LIST_KEY,
    FTA_NOTICE_COLLECT_KEY,
    NOISE_REDUCE_ABNORMAL_KEY,
)
from alarm_backends.core.context import ActionContext
from alarm_backends.service.alert.manager.checker.shield import ShieldStatusChecker
from alarm_backends.service.converge.processor import ConvergeProcessor
from alarm_backends.service.converge.shield.shield_obj import AlertShieldObj
from alarm_backends.service.converge.shield.shielder.saas_config import HostShielder
from alarm_backends.service.fta_action.collect.processor import (
    ActionProcessor as CollectActionProcessor,
)
from alarm_backends.service.fta_action.double_check import DoubleCheckHandler
from alarm_backends.service.fta_action.job.processor import (
    ActionProcessor as JobActionProcessor,
)
from alarm_backends.service.fta_action.message_queue.processor import (
    ActionProcessor as MessageQueueActionProcessor,
)
from alarm_backends.service.fta_action.notice.processor import (
    ActionProcessor as NoticeActionProcessor,
)
from alarm_backends.service.fta_action.tasks import (
    NoiseReduceExecuteProcessor,
    NoiseReduceRecordProcessor,
    check_timeout_actions,
    create_actions,
    create_interval_actions,
)
from alarm_backends.service.fta_action.utils import AlertAssignee
from alarm_backends.service.fta_action.webhook.processor import (
    ActionProcessor as WebhookProcessor,
)
from alarm_backends.tests.service.access.data.config import STRATEGY_CONFIG_V3
from api.cmdb.define import Business, Host
from bkmonitor.action.serializers import DutyArrange
from bkmonitor.aiops.alert.utils import (
    DimensionDrillLightManager,
    RecommendMetricManager,
)
from bkmonitor.aiops.utils import ReadOnlyAiSetting
from bkmonitor.documents import AlertLog, EventDocument
from bkmonitor.models import ActionPlugin, CacheRouter, DutyPlan, UserGroup
from bkmonitor.models.aiops import AIFeatureSettings
from bkmonitor.models.fta.action import (
    ActionConfig,
    ActionInstance,
    ConvergeInstance,
    ConvergeRelation,
)
from bkmonitor.utils import time_tools
from bkmonitor.utils.send import NoneTemplateSender, Sender
from bkmonitor.utils.template import (
    AlarmNoticeTemplate,
    Jinja2Renderer,
    NoticeRowRenderer,
)
from bkmonitor.utils.text import cut_line_str_by_max_bytes
from constants import alert as alert_constants
from constants.action import (
    ALL_CONVERGE_DIMENSION,
    ActionPluginType,
    ActionSignal,
    ActionStatus,
    ConvergeStatus,
    ConvergeType,
    FailureType,
    NoticeChannel,
    NoticeWay,
    NotifyStep,
    UserGroupType,
)
from constants.aiops import DIMENSION_DRILL
from constants.alert import EventSeverity, EventStatus
from constants.data_source import KubernetesResultTableLabel
from core.errors.alarm_backends import EmptyAssigneeError
from packages.fta_web.action.resources import AlertDocument

pytestmark = pytest.mark.django_db


def register_builtin_plugins():
    plugins = [
        {
            "id": 1,
            "name": "通知告警",
            "is_enabled": True,
            "is_builtin": True,
            "is_deleted": False,
            "is_peripheral": False,
            "plugin_type": "notice",
            "plugin_key": "notice",
            "plugin_source": "builtin",
            "description": "告警通知是平台内置的套餐类型，由平台自身实现。可以对告警信息基于人进行收敛，可以对接不同的告警通知渠道。 "
            "\n\n* 基于人进行收敛\n* 有告警风暴控制能力\n* 可以定制不同的告警模版\n* 内置基于不同的通知渠道显示的变量\n* "
            "可以自定义各种通知渠道[查看文档]()\n\n更多[查看文档]()",
            "config_schema": {
                "content_template": "发送{{notice_way_display}}告警通知给{{notice_receiver}}{{status_display}}",
                "content_template_with_url": "达到通知告警的执行条件【{{action_signal}}】，已触发告警通知",
                "content_template_without_assignee": "达到通知告警的执行条件【{{action_signal}}】，当前通知人员为空",
                "content_template_shielded": "达到通知告警的执行条件【{{action_signal}}】，因告警已被屏蔽或不在通知时间段，忽略通知发送",
                "content_template_shielded_with_url": "达到通知告警的执行条件【{{action_signal}}】，因告警已被屏蔽忽略通知发送，点击$查看屏蔽策略$",
            },
            "backend_config": [{"function": "execute_notify", "name": "发送通知"}],
        },
        {
            "id": 2,
            "name": "HTTP回调",
            "is_builtin": True,
            "is_deleted": False,
            "is_peripheral": False,
            "plugin_type": "webhook",
            "plugin_key": "webhook",
            "plugin_source": "builtin",
            "description": "",
            "config_schema": {"content_template": "HTTP回调任务【{{action_name}}】处理{{status_display}}"},
            "backend_config": [{"function": "execute_webhook", "name": "HTTP回调"}],
        },
        {
            "id": 3,
            "name": "作业平台",
            "is_builtin": True,
            "is_deleted": False,
            "is_peripheral": True,
            "plugin_source": "peripheral",
            "plugin_type": "job",
            "plugin_key": "job",
            "has_child": True,
            "description": "",
            "config_schema": {
                "template": {
                    "resource_class": "GetJobListResource",
                    "name": "执行方案名称",
                    "resource_module": "api.job.default",
                    "resource_data": "response[*]",
                    "mapping": {
                        "id": "{{bk_job_id}}",
                        "name": "{{name}}",
                        "url": "{{job_site_url}}/api_plan/{{bk_job_id}}",
                    },
                },
                "plugin_url": {
                    "mapping": {"url": "{{job_site_url}}/{{bk_biz_id}}/task_manage/create", "tips": "前往作业平台"}
                },
                "detail": {
                    "name": "全局变量",
                    "resource_class": "GetJobDetailResource",
                    "resource_module": "api.job.default",
                    "request_data_mapping": {"bk_job_id": "{{template_id}}"},
                    "resource_data": "response.global_vars[*]",
                    "mapping": {
                        "key": "{{id}}_{{category}}",
                        "name": "{{name}}",
                        "value": "{{(value or '') if category != 3 else '{{target.host.bk_host_innerip}}'}}",
                        "category": "{{category}}",
                        "placeholder": "{{description}}",
                    },
                },
                "content_template_with_url": "作业平台任务【{{action_name}}】处理{{status_display}}，点击$查看作业详情$",
                "content_template": "作业平台任务【{{action_name}}】处理{{status_display}}, 请关注！！",
            },
            "backend_config": [
                {
                    "function": "create_task",
                    "name": "创建job任务",
                    "resource_class": "ExecuteJobPlanResource",
                    "resource_module": "api.job.default",
                    "inputs": [
                        {"key": "bk_biz_id", "value": "bk_biz_id", "type": "int", "format": "jmespath"},
                        {
                            "key": "job_plan_id",
                            "value": "execute_config.template_id",
                            "type": "int",
                            "format": "jmespath",
                        },
                        {"key": "global_var_list", "value": "global_vars[]", "type": "dict", "format": "jmespath"},
                    ],
                    "outputs": [
                        {"key": "job_instance_id", "value": "response.job_instance_id", "format": "jmespath"},
                        {"key": "job_instance_name", "value": "response.job_instance_name", "format": "jmespath"},
                        {
                            "key": "url",
                            "value": "{{job_site_url}}/{{bk_biz_id}}/execute/step/{{job_instance_id}}",
                            "format": "jinja2",
                        },
                    ],
                    "next_function": "schedule",
                    "need_insert_log": True,
                    "log_template": "作业平台套餐【{{action_name}}】成功创建作业任务，点击$查看任务详情$",
                },
                {
                    "function": "schedule",
                    "name": "轮询job状态",
                    "resource_class": "GetJobInstanceStatusResource",
                    "resource_module": "api.job.default",
                    "inputs": [
                        {
                            "key": "job_instance_id",
                            "value": "pre_node_outputs.job_instance_id",
                            "type": "int",
                            "format": "jmespath",
                        },
                        {"key": "bk_biz_id", "value": "bk_biz_id", "type": "int", "format": "jmespath"},
                    ],
                    "outputs": [
                        {
                            "key": "job_state",
                            "value": "response.job_instance.status",
                            "type": "string",
                            "format": "jmespath",
                        }
                    ],
                    "node_finished_rule": {"key": "job_state", "method": "not in", "value": [1, 2, 7]},
                    "finished_rule": {"key": "job_state", "method": "not in", "value": [1, 2, 7]},
                    "success_rule": {"key": "job_state", "method": "equal", "value": 3},
                    "need_schedule": True,
                    "schedule_timedelta": 2,
                    "next_function": "schedule",
                },
            ],
        },
        {
            "id": 4,
            "name": "标准运维",
            "is_builtin": True,
            "is_deleted": False,
            "is_peripheral": True,
            "plugin_source": "peripheral",
            "plugin_type": "sops",
            "plugin_key": "sops",
            "has_child": True,
            "description": "",
            "config_schema": {
                "template": {
                    "resource_class": "GetTemplateListResource",
                    "name": "流程名称",
                    "resource_module": "api.sops.default",
                    "resource_data": "response[*]",
                    "mapping": {
                        "id": "{{id}}",
                        "name": "{{name}}",
                        "url": "{{sops_site_url}}/template/edit/{{project_id}}/?template_id={{id}}",
                    },
                },
                "plugin_url": {
                    "resource_class": "GetUserProjectDetailResource",
                    "resource_module": "api.sops.default",
                    "resource_data": "response",
                    "mapping": {"url": "{{sops_site_url}}/template/new/{{project_id}}/", "tips": "前往标准运维"},
                },
                "detail": {
                    "name": "任务参数",
                    "resource_class": "GetTemplateInfoResource",
                    "resource_module": "api.sops.default",
                    "request_data_mapping": {"bk_template_id": "{{template_id}}"},
                    "resource_data": "response.pipeline_tree.constants.* | [?show_type == 'show']",
                    "mapping": {"key": "{{key}}", "name": "{{name}}", "value": "{{value.default or value or ''}}"},
                },
                "content_template_with_url": "标准运维任务【{{action_name}}】处理{{status_display}}，点击$查看任务详情$",
                "content_template": "标准运维任务【{{action_name}}】处理{{status_display}}, 请关注！！",
            },
            "backend_config": [
                {
                    "function": "create_task",
                    "name": "创建标准运维任务",
                    "resource_class": "CreateTaskResource",
                    "resource_module": "api.sops.default",
                    "inputs": [
                        {"key": "bk_biz_id", "value": "bk_biz_id", "type": "int", "format": "jmespath"},
                        {
                            "key": "template_id",
                            "value": "execute_config.template_id",
                            "type": "int",
                            "format": "jmespath",
                        },
                        {
                            "key": "constants",
                            "value": "execute_config.template_detail_dict",
                            "type": "dict",
                            "format": "jmespath",
                        },
                        {"key": "name", "value": "action_name", "type": "string", "format": "jmespath"},
                    ],
                    "outputs": [
                        {"key": "task_id", "value": "response.task_id", "format": "jmespath"},
                        {"key": "url", "value": "response.task_url", "format": "jmespath"},
                    ],
                    "next_function": "start_task",
                    "need_insert_log": True,
                    "log_template": "标准运维套餐【{{action_name}}】成功创建任务，点击$查看任务详情$",
                },
                {
                    "function": "start_task",
                    "name": "启动任务",
                    "resource_class": "StartTaskResource",
                    "resource_module": "api.sops.default",
                    "inputs": [
                        {"key": "task_id", "value": "pre_node_outputs.task_id", "type": "int", "format": "jmespath"},
                        {"key": "bk_biz_id", "value": "bk_biz_id", "type": "int", "format": "jmespath"},
                    ],
                    "outputs": [],
                    "next_function": "schedule",
                },
                {
                    "function": "schedule",
                    "name": "轮询状态",
                    "resource_class": "GetTaskStatusResource",
                    "resource_module": "api.sops.default",
                    "inputs": [
                        {"key": "task_id", "value": "pre_node_outputs.task_id", "type": "int", "format": "jmespath"},
                        {"key": "bk_biz_id", "value": "bk_biz_id", "type": "int", "format": "jmespath"},
                    ],
                    "outputs": [
                        {"key": "task_state", "value": "response.state", "type": "string", "format": "jmespath"}
                    ],
                    "finished_rule": {"key": "task_state", "method": "in", "value": ["FAILED", "FINISHED", "REVOKED"]},
                    "success_rule": {"key": "task_state", "method": "in", "value": ["FINISHED"]},
                    "need_schedule": True,
                    "schedule_timedelta": 2,
                    "next_function": "schedule",
                },
            ],
        },
        {
            "id": 5,
            "name": "流程服务",
            "is_builtin": True,
            "is_deleted": False,
            "is_peripheral": True,
            "plugin_source": "peripheral",
            "plugin_type": "common",
            "plugin_key": "itsm",
            "has_child": True,
            "description": "",
            "config_schema": {
                "template": {
                    "resource_class": "CommonBaseResource",
                    "name": "服务名称",
                    "init_kwargs": {"url": "{{bk_paas_inner_host}}/api/c/compapi/v2/itsm/get_services/"},
                    "request_data_mapping": {"display_role": "BK_FTA"},
                    "resource_module": "api.common.default",
                    "resource_data": "response[*]",
                    "mapping": {
                        "id": "{{id}}",
                        "name": "{{name}}",
                        "url": "{{itsm_site_url}}/#/ticket/create?service_id={{id}}",
                    },
                },
                "plugin_url": {
                    "mapping": {"url": "{{itsm_site_url}}/#/project/service/new/basic?project_id=0", "tips": "前往流程服务"}
                },
                "detail": {
                    "name": "提单信息",
                    "resource_class": "CommonBaseResource",
                    "resource_module": "api.common.default",
                    "init_kwargs": {"url": "{{bk_paas_inner_host}}/api/c/compapi/v2/itsm/get_service_detail/"},
                    "request_data_mapping": {"service_id": "{{template_id}}"},
                    "resource_data": "response.fields[*]",
                    "mapping": {
                        "key": "{{key}}",
                        "name": "{{name}}",
                        "value": "{{default or ''}}",
                        "placeholder": "{{desc}}",
                    },
                },
                "content_template_with_url": "故障工单套餐【{{action_name}}】成功创建单据[{{sn}}]，点击$查看工单详情$",
                "content_template": "故障工单套餐【{{action_name}}】处理{{status_display}}, 请关注！！",
            },
            "backend_config": [
                {
                    "function": "create_task",
                    "name": "创建单据",
                    "resource_class": "CommonBaseResource",
                    "resource_module": "api.common.default",
                    "init_kwargs": {
                        "url": "{{bk_paas_inner_host}}/api/c/compapi/v2/itsm/create_ticket/",
                        "method": "POST",
                    },
                    "inputs": [
                        {
                            "key": "service_id",
                            "value": "execute_config.template_id",
                            "type": "int",
                            "format": "jmespath",
                        },
                        {
                            "key": "fields",
                            "value": "execute_config.template_detail[].{key: key, value: value}",
                            "type": "list",
                            "format": "jmespath",
                        },
                        {"key": "creator", "value": "operator", "type": "string", "format": "jmespath"},
                    ],
                    "outputs": [
                        {"key": "sn", "value": "response.sn", "format": "jmespath"},
                        {"key": "id", "value": "response.id", "format": "jmespath"},
                        {"key": "url", "value": "{{itsm_site_url}}#/ticket/detail?id={{id}}", "format": "jinja2"},
                    ],
                    "need_insert_log": True,
                    "log_template": "流程服务套餐【{{action_name}}】已成功创建工单[{{sn}}]，点击$查看工单详情$",
                },
                {
                    "function": "schedule",
                    "name": "轮询状态",
                    "resource_class": "CommonBaseResource",
                    "resource_module": "api.common.default",
                    "init_kwargs": {
                        "url": "{{bk_paas_inner_host}}/api/c/compapi/v2/itsm/get_ticket_status/",
                        "method": "GET",
                    },
                    "inputs": [{"key": "sn", "value": "pre_node_outputs.sn", "type": "string", "format": "jmespath"}],
                    "outputs": [
                        {
                            "key": "current_status",
                            "value": "response.current_status",
                            "type": "string",
                            "format": "jmespath",
                        },
                        {"key": "url", "value": "response.ticket_url", "type": "string", "format": "jmespath"},
                    ],
                    "finished_rule": {"key": "current_status", "method": "equal", "value": "FINISHED"},
                    "need_schedule": True,
                    "schedule_timedelta": 2,
                    "next_function": "schedule",
                },
            ],
        },
    ]
    for plugin in plugins:
        instance, created = ActionPlugin.origin_objects.update_or_create(
            id=plugin.pop("id"), is_builtin=True, defaults=plugin
        )
        print("{} plugin: [{}]".format("register" if created else "update", instance.name))


def get_strategy_dict(group_id):
    notice_action_config = {
        "execute_config": {
            "template_detail": {
                "interval_notify_mode": "standard",  # 间隔模式
                "notify_interval": 7200,  # 通知间隔
                "template": [  # 通知模板配置
                    {
                        "signal": "abnormal",
                    }
                ],
            }
        },
        "id": 55555,
        "plugin_id": 1,
        "plugin_type": "notice",
        "is_enabled": True,
        "bk_biz_id": 2,
        "name": "test_notice",
    }

    strategy_dict = {
        "id": 1,
        "type": "monitor",
        "bk_biz_id": 2,
        "scenario": "os",
        "name": "测试新策略",
        "labels": [],
        "is_enabled": True,
        "items": [],
        "detects": [],
        "notice": {  # 通知设置
            "id": 1,
            "config_id": 55555,  # 套餐ID，如果不选套餐请置为0
            "user_groups": [group_id],  # 告警组ID
            "signal": ["abnormal", "recovered", "ack"],
            # 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
            "options": {
                "converge_config": {
                    "is_enabled": True,
                    "converge_func": "collect",
                    "timedelta": 60,
                    "count": 1,
                    "condition": [
                        {"dimension": "strategy_id", "value": ["self"]},
                        {"dimension": "dimensions", "value": ["self"]},
                        {"dimension": "alert_level", "value": ["self"]},
                        {"dimension": "signal", "value": ["self"]},
                        {"dimension": "bk_biz_id", "value": ["self"]},
                        {"dimension": "notice_receiver", "value": ["self"]},
                        {"dimension": "notice_way", "value": ["self"]},
                        {"dimension": "notice_info", "value": ["self"]},
                    ],
                    "need_biz_converge": True,
                    "sub_converge_config": {
                        "timedelta": 60,
                        "count": 2,
                        "condition": [
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                        ],
                        "converge_func": "collect_alarm",
                    },
                },
                "start_time": "00:00:00",
                "end_time": "23:59:59",
            },
            "config": notice_action_config["execute_config"]["template_detail"],
        },
        "actions": [],
        "notice_action_config": notice_action_config,
    }

    return strategy_dict


def notice_template():
    return [  # 通知模板配置
        {
            "signal": "abnormal",
            # 触发信号：abnormal-告警触发时，recovered-告警恢复时，closed-告警关闭时
            "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n"
            "{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}"
            "\n{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n"
            "{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n"
            "{{content.related_info}}",
            "title_tmpl": "【{{level_name}}】{{business.bk_biz_name}} - " "{{alarm.name}}{{alarm.display_type}}",
        },
        {
            "signal": "recovered",
            "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n"
            "{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}\n"
            "{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n"
            "{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n"
            "{{content.related_info}}",
            "title_tmpl": "【{{level_name}}】{{business.bk_biz_name}} - {{alarm.name}}" "{{alarm.display_type}}",
        },
        {
            "signal": "closed",
            "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n"
            "{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}\n"
            "{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n"
            "{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n"
            "{{content.related_info}}",
            "title_tmpl": "【{{level_name}}】{{business.bk_biz_name}} - {{alarm.name}}" "{{alarm.display_type}}",
        },
    ]


mock.patch("core.drf_resource.api.cmsi.get_msg_type", return_value={}).start()
mock.patch("core.drf_resource.api.cmsi.send_sms", return_value={}).start()
mock.patch("core.drf_resource.api.cmsi.send_msg", return_value={}).start()
mock.patch("alarm_backends.core.context.alarm.Alarm.chart_image", return_value=None).start()
mock.patch("alarm_backends.service.fta_action.utils.run_converge.delay", return_value=11111).start()
mock.patch("alarm_backends.service.fta_action.tasks.run_action.apply_async", return_value=11111).start()
mock.patch("alarm_backends.service.fta_action.tasks.run_webhook_action.apply_async", return_value=11111).start()
mock.patch("alarm_backends.service.fta_action.tasks.run_action.delay", return_value=11111).start()
mock.patch("alarm_backends.service.converge.tasks.run_converge.apply_async", return_value=11111).start()
mock.patch("alarm_backends.service.fta_action.tasks.run_noise_reduce_task.apply_async", return_value=11111).start()
mock.patch("alarm_backends.service.fta_action.tasks.create_action.need_poll", return_value=True).start()


def converge_actions(instances, action_type=ConvergeType.ACTION, is_enabled=True, alerts=None):
    for instance in instances:
        converge_config = copy.deepcopy(
            {
                "is_enabled": is_enabled,
                "converge_func": "collect",
                "timedelta": 60,
                "count": 1,
                "condition": [
                    {"dimension": "strategy_id", "value": ["self"]},
                    {"dimension": "dimensions", "value": ["self"]},
                    {"dimension": "alert_level", "value": ["self"]},
                    {"dimension": "signal", "value": ["self"]},
                    {"dimension": "bk_biz_id", "value": ["self"]},
                    {"dimension": "notice_receiver", "value": ["self"]},
                    {"dimension": "notice_way", "value": ["self"]},
                    {"dimension": "notice_info", "value": ["self"]},
                ],
                "need_biz_converge": True,
                "sub_converge_config": {
                    "timedelta": 60,
                    "count": 2,
                    "condition": [
                        {"dimension": "bk_biz_id", "value": ["self"]},
                        {"dimension": "notice_receiver", "value": ["self"]},
                        {"dimension": "notice_way", "value": ["self"]},
                        {"dimension": "alert_level", "value": ["self"]},
                        {"dimension": "signal", "value": ["self"]},
                    ],
                    "converge_func": "collect_alarm",
                },
            }
        )
        if action_type == ConvergeType.CONVERGE:
            converge_config = copy.deepcopy(
                {
                    "timedelta": 60,
                    "count": 2,
                    "is_enabled": is_enabled,
                    "condition": [
                        {"dimension": "bk_biz_id", "value": ["self"]},
                        {"dimension": "notice_receiver", "value": ["self"]},
                        {"dimension": "notice_way", "value": ["self"]},
                        {"dimension": "alert_level", "value": ["self"]},
                        {"dimension": "signal", "value": ["self"]},
                    ],
                    "converge_func": "collect_alarm",
                }
            )
        cp = ConvergeProcessor(converge_config, instance.id, action_type, alerts=alerts)
        cp.converge_alarm()
        print("$%s converge status " % instance.id, cp.status)


class TestActionProcessor(TransactionTestCase):
    databases = {"monitor_api", "default"}

    def setUp(self):
        CONVERGE_LIST_KEY.client.flushall()
        FTA_ACTION_LIST_KEY.client.flushall()
        ALERT_SNAPSHOT_KEY.client.flushall()
        ActionInstance.objects.all().delete()
        ActionConfig.objects.all().delete()
        ConvergeInstance.objects.all().delete()
        ConvergeRelation.objects.all().delete()
        DutyPlan.objects.all().delete()
        UserGroup.objects.all().delete()
        DutyArrange.objects.all().delete()
        AIFeatureSettings.objects.all().delete()
        register_builtin_plugins()
        settings.ENABLE_MESSAGE_QUEUE = False
        settings.MESSAGE_QUEUE_DSN = ""

        self.ac_data = {
            "execute_config": {
                "template_detail": {
                    "alert": [  # 告警通知配置
                        {
                            "time_range": "00:00:00--23:59:59",  # 生效时间段
                            "notify_interval": 7200,  # 通知间隔
                            "interval_notify_mode": "standard",  # 间隔模式
                            "notify_config": [  # 通知方式配置
                                {"level": 3, "type": ["mail", "weixin"]},  # 级别  # 通知渠道列表
                                {"level": 2, "type": ["mail", "weixin"]},
                                {"level": 1, "type": ["mail", "weixin"]},
                            ],
                        }
                    ],
                    "execution": [  # 执行通知配置
                        {
                            "risk_level": 1,  # 敏感度，1 - 高危，2 - 一般，3 - 无所谓
                            "notify_config": [  # 通知方式
                                {"phase": 3, "type": ["mail", "weixin"]},  # 执行阶段，3-执行前，2-成功时，1-失败时
                                {"phase": 2, "type": ["mail", "weixin"]},
                                {"phase": 1, "type": ["mail", "weixin"]},
                            ],
                        }
                    ],
                    "template": notice_template(),
                },
                "timeout": 600,
            },
            "name": "测试通知套餐",
            "desc": "",
            "is_enabled": True,
            "plugin_id": 1,
            "bk_biz_id": 2,
        }
        self.send_weixin_patcher = patch(
            "core.drf_resource.api.cmsi.send_weixin",
            MagicMock(return_value={"username_check": {"invalid": []}, "message": _("发送成功")}),
        )
        self.send_mail_patcher = patch(
            "core.drf_resource.api.cmsi.send_mail",
            MagicMock(return_value={"username_check": {"invalid": []}, "message": _("发送成功")}),
        )
        self.send_voice_patcher = patch(
            "core.drf_resource.api.cmsi.send_voice",
            MagicMock(return_value={"result": True, "message": "OK"}),
        )
        self.send_wxwork_bot_patcher = patch(
            "bkmonitor.utils.send.Sender.send_wxwork_bot",
            MagicMock(
                return_value={
                    "hihihihihh": {"result": True, "message": ""},
                    "hihihiashihi": {"result": True, "message": ""},
                }
            ),
        )
        self.get_recommended_metrics = patch(
            "bkmonitor.aiops.alert.utils.RecommendMetricManager.fetch_aiops_result",
            MagicMock(return_value={"info": {"recommended_metric_count": 0}, "recommended_metrics": []}),
        )
        self.get_anomaly_dimensions = patch(
            "bkmonitor.aiops.alert.utils.DimensionDrillLightManager.fetch_aiops_result",
            MagicMock(
                return_value={
                    "info": {"anomaly_dimension_count": 2, "anomaly_dimension_value_count": 2},
                }
            ),
        )
        self.get_anomaly_dimensions.start()
        self.get_recommended_metrics.start()

        self.create_alert_log = patch("bkmonitor.documents.AlertLog.bulk_create", MagicMock(return_value=True))

        self.create_alert_patch = patch("bkmonitor.documents.AlertDocument.bulk_create", MagicMock(return_value=True))
        self.create_alert_patch.start()
        self.create_alert_log.start()

        self.send_weixin_patcher.start()
        self.send_mail_patcher.start()
        self.send_voice_patcher.start()

        self.get_biz_patcher = patch(
            "alarm_backends.core.cache.cmdb.business.BusinessManager.get",
            MagicMock(
                return_value=Business(
                    2,
                    bk_biz_name="蓝鲸",
                    bk_biz_developer="admin",
                    bk_biz_maintainer="admin",
                )
            ),
        )
        self.get_all_biz_patcher = patch(
            "alarm_backends.core.cache.cmdb.business.BusinessManager.all",
            MagicMock(
                return_value=[
                    Business(
                        2,
                        bk_biz_name="蓝鲸",
                        bk_biz_developer="admin",
                        bk_biz_maintainer="admin",
                    )
                ]
            ),
        )

        self.get_all_biz_patcher.start()
        self.get_biz_patcher.start()

        self.get_host_patcher = patch(
            "alarm_backends.core.cache.cmdb.host.HostManager.get",
            MagicMock(
                return_value=Host(
                    attrs={
                        "bk_host_innerip": "127.0.0.1",
                        "bk_cloud_id": 0,
                        "bk_host_id": 1,
                        "bk_biz_id": 2,
                        "idc_unit_name": "上海",
                        "net_device_id": 123,
                        "topo_link": {},
                    }
                )
            ),
        )

        self.get_host_patcher.start()

        self.user_group_data = {
            "name": "蓝鲸业务的告警组-全职通知组",
            "desc": "用户组的说明用户组的说明用户组的说明用户组的说明用户组的说明",
            "bk_biz_id": 2,
            "need_duty": True,
            "duty_rules": [1],
            "timezone": "Asia/Shanghai",
            "mention_list": [{"type": "group", "id": "all"}, {"type": "user", "id": "admin"}],
            "alert_notice": [  # 告警通知配置
                {
                    "time_range": "00:00:00--23:59:59",  # 生效时间段
                    "notify_config": [  # 通知方式配置
                        {
                            "level": 3,  # 级别
                            "type": [  # 通知渠道列表
                                "mail",
                                "weixin",
                                "voice",
                            ],
                        },
                        {"level": 2, "type": ["mail", "voice"]},
                        {
                            "level": 1,
                            "type": ["mail", "weixin", "voice", "wxwork-bot"],
                            "chatid": "hihihihihh,hihihiashihi",
                        },
                    ],
                }
            ],
            "action_notice": [  # 执行通知配置
                {
                    "time_range": "00:00:00--23:59:59",  # 生效时间段
                    "notify_config": [  # 通知方式
                        {"phase": 3, "type": ["mail", "weixin", "voice"]},  # 执行阶段，3-执行前，2-成功时，1-失败时
                        {"phase": 2, "type": ["mail", "weixin", "voice"]},
                        {
                            "phase": 1,
                            "type": ["mail", "weixin", "voice", "wxwork-bot"],
                            "chatid": "hihihihihh,hihihiashihi",
                        },
                    ],
                }
            ],
        }
        self.user_group_data_new = {
            "name": "蓝鲸业务的告警组-新的数据格式告警组",
            "desc": "用户组的说明用户组的说明用户组的说明用户组的说明用户组的说明",
            "bk_biz_id": 2,
            "need_duty": True,
            "duty_rules": [1],
            "mention_list": [{"type": "group", "id": "all"}],
            "channels": [NoticeChannel.USER, NoticeChannel.WX_BOT, NoticeChannel.BK_CHAT],
            "alert_notice": [  # 告警通知配置
                {
                    "time_range": "00:00:00--23:59:59",  # 生效时间段
                    "notify_config": [  # 通知方式配置
                        {
                            "level": 3,  # 级别
                            "notice_ways": [
                                {"name": NoticeWay.WEIXIN},
                                {"name": NoticeWay.BK_CHAT, "receivers": ["mail|1", "mini|2"]},
                                {"name": NoticeWay.WX_BOT, "receivers": ["hihihihihh", "hihihiashihi"]},
                            ],
                        },
                        {"level": 2, "notice_ways": [{"name": NoticeWay.MAIL}, {"name": NoticeWay.VOICE}]},
                        {
                            "level": 1,
                            "notice_ways": [
                                {"name": NoticeWay.WEIXIN},
                                {"name": NoticeWay.MAIL},
                                {"name": NoticeWay.BK_CHAT, "receivers": ["mail|1", "mail|2"]},
                                {"name": NoticeWay.WX_BOT, "receivers": ["hihihihihh", "hihihiashihi"]},
                            ],
                        },
                    ],
                }
            ],
            "action_notice": [  # 执行通知配置
                {
                    "time_range": "00:00:00--23:59:59",  # 生效时间段
                    "notify_config": [  # 通知方式
                        {
                            "phase": 3,
                            "notice_ways": [{"name": NoticeWay.MAIL}, {"name": NoticeWay.VOICE}],
                        },  # 执行阶段，3-执行前，2-成功时，1-失败时
                        {"phase": 2, "notice_ways": [{"name": NoticeWay.MAIL}, {"name": NoticeWay.VOICE}]},
                        {
                            "phase": 1,
                            "notice_ways": [
                                {"name": NoticeWay.WEIXIN},
                                {"name": NoticeWay.BK_CHAT, "receivers": ["1", "2"]},
                                {"name": NoticeWay.WX_BOT, "receivers": ["hihihihihh", "hihihiashihi"]},
                            ],
                        },
                    ],
                }
            ],
        }
        self.duty_arranges = []
        local_timezone = pytz.timezone("Asia/Shanghai")
        today_begin = time_tools.datetime2str(datetime.now(tz=local_timezone), "%Y-%m-%d 00:00")
        today_end = time_tools.datetime2str(datetime.now(tz=local_timezone), "%Y-%m-%d 23:59")
        self.duty_plans = [
            {
                "duty_rule_id": 1,
                "is_effective": 1,
                "start_time": time_tools.datetime2str(datetime.now(tz=local_timezone)),
                "finished_time": time_tools.datetime2str(datetime.now(tz=local_timezone) + timedelta(hours=1)),
                "work_times": [{'start_time': today_begin, 'end_time': today_end}],
                "order": 1,
                "users": [
                    {"id": "admin", "display_name": "admin", "logo": "", "type": "user"},
                    {"id": "operator", "display_name": "主机负责人", "logo": "", "type": "group"},
                ],
            },
            {
                "duty_rule_id": 1,
                "start_time": time_tools.datetime2str(datetime.now(tz=local_timezone)),
                "finished_time": "",
                "is_effective": 1,
                "order": 2,
                "work_times": [{'start_time': today_begin, 'end_time': today_end}],
                "users": [{"id": "lisa", "display_name": "xxxxx", "logo": "", "type": "user"}],
            },
        ]
        self.biz_group_users_patch = patch(
            "alarm_backends.service.fta_action.utils.AlertAssignee.get_biz_group_users",
            MagicMock(
                return_value={
                    "operator": ["admin", "andy", "lisa"],
                }
            ),
        )
        self.biz_group_users_utils_patch = patch(
            "alarm_backends.service.fta_action.utils.AlertAssignee.get_biz_group_users",
            MagicMock(
                return_value={
                    "operator": ["admin", "andy", "lisa"],
                }
            ),
        )
        self.biz_group_users_patch.start()
        self.biz_group_users_utils_patch.start()

        event = EventDocument(
            **{
                "bk_biz_id": 2,
                "ip": "127.0.0.1",
                "time": int(time.time()),
                "create_time": int(time.time()),
                "bk_cloud_id": 0,
                "id": 123,
            }
        )
        self.current_time = int(time.time())
        self.alert_info = {
            "id": "1",
            "alert_name": "test",
            "event": event,
            "severity": 1,
            "dedupe_md5": "68e9f0598d72a4b6de2675d491e5b922",
            "begin_time": int(time.time()),
            "create_time": int(time.time()),
            "latest_time": self.current_time,
            "first_anomaly_time": self.current_time,
            "duration": 60,
            "common_dimensions": {},
            "dimensions": [
                AttrDict({"key": "tags.backend", "value": "test_tags", "display_key": "backend", "display_value": "1"}),
                AttrDict(
                    {"key": "bk_target_ip", "value": "127.0.0.1", "display_key": "主机IP", "display_value": "127.0.0.1"}
                ),
                AttrDict({"key": "bk_target_cloud_id", "value": "2", "display_key": "云区域ID", "display_value": "2"}),
            ],
            "extra_info": {"strategy": {}, "agg_dimensions": ["bk_target_cloud_id", "bk_target_ip"]},
            "status": EventStatus.ABNORMAL,
        }
        self.insert_alert_log_patch = patch(
            "bkmonitor.models.fta.action.ActionInstance.insert_alert_log", MagicMock(return_value=None)
        )
        self.insert_alert_log_patch.start()

    def tearDown(self):
        settings.GLOBAL_SHIELD_ENABLED = False
        settings.ENABLE_MESSAGE_QUEUE = False
        ALERT_SNAPSHOT_KEY.client.flushall()
        settings.MESSAGE_QUEUE_DSN = ""
        ActionInstance.objects.all().delete()
        ActionConfig.objects.all().delete()
        ConvergeRelation.objects.all().delete()
        DutyPlan.objects.all().delete()
        UserGroup.objects.all().delete()
        DutyArrange.objects.all().delete()
        self.create_alert_log.stop()
        self.get_biz_patcher.stop()
        self.get_all_biz_patcher.stop()
        self.get_host_patcher.stop()
        self.send_weixin_patcher.stop()
        self.send_mail_patcher.stop()
        self.send_voice_patcher.stop()
        self.biz_group_users_patch.stop()
        self.create_alert_patch.stop()
        self.insert_alert_log_patch.stop()
        self.biz_group_users_utils_patch.stop()
        self.get_anomaly_dimensions.stop()
        self.get_recommended_metrics.stop()

    def test_notify_double_check(self):
        duty_plans = copy.deepcopy(self.duty_plans)
        group = UserGroup.objects.create(**self.user_group_data)
        for duty in duty_plans:
            duty.update({"user_group_id": group.id})
            DutyPlan.objects.create(**duty)

        event = EventDocument(
            **{
                "bk_biz_id": 2,
                "ip": "127.0.0.1",
                "bk_cloud_id": 0,
                "tags": [{"key": "__double_check_result", "value": "SUSPECTED_MISSING_POINTS"}],
            }
        )
        alert = AlertDocument(**{"event": event, "severity": 1})
        notice_info = AlertAssignee(alert, [group.id]).get_notice_receivers()
        DoubleCheckHandler(alert).handle(inputs={"notify_info": notice_info})

        users = {"admin", "andy", "lisa"}
        assert "voice" not in notice_info
        self.assertEqual(set(notice_info["mail"]), users)
        self.assertEqual(set(notice_info["weixin"]), users)
        self.assertEqual(set(notice_info[NoticeWay.WX_BOT]), set("hihihihihh,hihihiashihi".split(",")))

    def test_user_group_receivers_new(self):
        duty_plans = copy.deepcopy(self.duty_plans)
        group = UserGroup.objects.create(**self.user_group_data_new)
        for duty in duty_plans:
            duty.update({"user_group_id": group.id})
            DutyPlan.objects.create(**duty)
        event = EventDocument(**{"bk_biz_id": 2, "ip": "127.0.0.1", "bk_cloud_id": 0})
        alert = AlertDocument(**{"event": event, "severity": 1})
        notice_info = AlertAssignee(alert, [group.id]).get_notice_receivers()
        users = ["admin", "andy", "lisa"]
        self.assertEqual(notice_info["mail"], users)
        self.assertEqual(notice_info["weixin"], users)
        self.assertEqual(set(notice_info[NoticeWay.WX_BOT]), {"hihihihihh", "hihihiashihi"})
        self.assertEqual(set(notice_info[f"{NoticeChannel.BK_CHAT}|mail"]), {"1", "2"})

        user_set = set(users)
        self.assertEqual(notice_info["wxbot_mention_users"], [{"hihihihihh": users, "hihihiashihi": users}])

        p_action = ActionInstance.objects.create(
            inputs={"notify_info": notice_info}, signal=ActionSignal.ABNORMAL, strategy_id=0, is_parent_action=True
        )
        p_action.create_sub_actions()

        self.assertEqual(ActionInstance.objects.filter(is_parent_action=False).count(), 10)

        bkchat_actions = [
            a for a in ActionInstance.objects.filter(is_parent_action=False) if a.inputs["notice_way"] == "bkchat|mail"
        ]
        ac = ActionContext(bkchat_actions[0], alerts=[alert], use_alert_snap=True)
        self.assertEqual(ac.notice_channel, NoticeChannel.BK_CHAT)
        self.assertEqual(ac.notice_way, NoticeWay.MAIL)

        # self.assertEqual(len(ac.alarm.link_layouts), 0)

        wxbot_actions = [
            a
            for a in ActionInstance.objects.filter(is_parent_action=False)
            if a.inputs["notice_way"] == NoticeWay.WX_BOT
        ]
        self.assertEqual(
            {chatid: set(users) for chatid, users in wxbot_actions[0].inputs["mention_users"].items()},
            {"hihihihihh": user_set, "hihihiashihi": user_set},
        )

        ac = ActionContext(wxbot_actions[0], alerts=[alert], use_alert_snap=True)

        self.assertEqual(
            {chatid: set(users) for chatid, users in getattr(ac, "mention_users", {}).items()},
            {"hihihihihh": user_set, "hihihiashihi": user_set},
        )

        # self.assertEqual(len(ac.alarm.link_layouts), 2)

    def test_user_group_receivers(self):
        duty_plans = copy.deepcopy(self.duty_plans)
        group = UserGroup.objects.create(**self.user_group_data)
        for duty in duty_plans:
            duty.update({"user_group_id": group.id})
            DutyPlan.objects.create(**duty)
        event = EventDocument(**{"bk_biz_id": 2, "ip": "127.0.0.1", "bk_cloud_id": 0})
        alert = AlertDocument(**{"event": event, "severity": 1})
        notice_info = AlertAssignee(alert, [group.id]).get_notice_receivers()
        users = ["admin", "andy", "lisa"]
        self.assertEqual(notice_info["mail"], users)
        self.assertEqual(notice_info["weixin"], users)
        self.assertEqual(notice_info["voice"], [users])
        self.assertEqual(set(notice_info[NoticeWay.WX_BOT]), set("hihihihihh,hihihiashihi".split(",")))

        p_action = ActionInstance.objects.create(
            inputs={"notify_info": notice_info}, strategy_id=0, is_parent_action=True
        )
        p_action.create_sub_actions()

        self.assertEqual(ActionInstance.objects.filter(is_parent_action=False).count(), 9)

    def test_notify_with_appointee(self):
        duty_plans = copy.deepcopy(self.duty_plans)
        group = UserGroup.objects.create(**self.user_group_data)
        for duty in duty_plans:
            duty.update({"user_group_id": group.id})
            DutyPlan.objects.create(**duty)
        event = EventDocument(**{"bk_biz_id": 2, "ip": "127.0.0.1", "bk_cloud_id": 0})
        appointee = ["lisa1", "lisa2"]
        alert = AlertDocument(**{"event": event, "severity": 1, "appointee": appointee})
        notice_info = AlertAssignee(alert, [group.id]).get_notice_receivers()
        users = ["admin", "andy", "lisa"]
        self.assertEqual(notice_info["mail"], users)
        self.assertEqual(notice_info["weixin"], users)
        self.assertEqual(notice_info["voice"], [users])

    def test_create_ack_action(self):
        """
        通过策略创建处理
        :return:
        """

        duty_plans = copy.deepcopy(self.duty_plans)
        group = UserGroup.objects.create(**self.user_group_data)
        for duty in duty_plans:
            duty.update({"user_group_id": group.id})
            DutyPlan.objects.create(**duty)

        notice_action_config = {
            "execute_config": {
                "template_detail": {
                    "interval_notify_mode": "standard",  # 间隔模式
                    "notify_interval": 7200,  # 通知间隔
                    "template": notice_template(),
                }
            },
            "id": 55555,
            "plugin_id": 1,
            "plugin_type": "notice",
            "is_enabled": True,
            "bk_biz_id": 2,
            "name": "test_notice",
        }
        strategy_dict = get_strategy_dict(group.id)
        self.alert_info["extra_info"].update(strategy=strategy_dict)
        self.alert_info["id"] = "123123123"

        alert = AlertDocument(**self.alert_info)
        alert.is_ack = True
        alert.is_ack_noticed = False
        alert.ack_operator = "admin"

        ack_log = AlertLog(
            alert_id=list([alert.id]),
            op_type=AlertLog.OpType.ACK,
            create_time=int(time.time()),
            description="测试告警确认通知",
            operator="admin",
        )

        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))
        get_ack_reason = patch(
            "bkmonitor.documents.AlertLog.get_ack_logs", MagicMock(return_value=[ack_log, ack_log, ack_log])
        )

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=notice_action_config),
        )
        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()
        get_ack_reason.start()

        create_actions(1, "ack", alerts=[alert])
        self.assertEqual(
            ActionInstance.objects.filter(
                is_parent_action=True, signal=ActionSignal.ACK, action_config_id=55555
            ).count(),
            1,
        )
        self.assertEqual(
            ActionInstance.objects.get(is_parent_action=True, signal=ActionSignal.ACK, action_config_id=55555).inputs[
                "alert_latest_time"
            ],
            self.current_time,
        )
        self.assertEqual(
            ActionInstance.objects.filter(
                is_parent_action=False, signal=ActionSignal.ACK, action_config_id=55555
            ).count(),
            9,
        )
        self.set_notice_cache()
        for action in ActionInstance.objects.filter(is_parent_action=False, action_config_id=55555):
            try:
                n_ap = NoticeActionProcessor(action_id=action.id)
                n_ap.execute()
            except BaseException as error:
                print("error info", str(error))

        self.assertEqual(
            ActionInstance.objects.filter(is_parent_action=False, status="success", action_config_id=55555).count(), 7
        )

        action_config_patch.stop()
        mget_alert_patch.stop()
        get_alert_patch.stop()
        get_ack_reason.stop()

    @staticmethod
    def set_notice_cache(action_config_id=55555, signal="abnormal"):
        client = FTA_NOTICE_COLLECT_KEY.client

        pipeline = client.pipeline()

        notice_way_mapping = defaultdict(dict)
        action = None
        for action in ActionInstance.objects.filter(is_parent_action=False, action_config_id=action_config_id):
            if action.inputs["notice_way"] != NoticeWay.VOICE:
                notice_way_mapping[action.inputs["notice_way"]].update({action.inputs["notice_receiver"]: action.id})
        for notice_way, mapping in notice_way_mapping.items():
            collect_key = FTA_NOTICE_COLLECT_KEY.get_key(
                **{"notice_way": notice_way, "action_signal": action.signal, "alert_id": action.alerts[0]}
            )
            pipeline.hmset(collect_key, mapping)

        pipeline.execute()

    def test_create_action_by_strategy(self):
        """
        通过策略创建处理
        :return:
        """

        duty_plans = copy.deepcopy(self.duty_plans)
        group = UserGroup.objects.create(**self.user_group_data)
        for duty in duty_plans:
            duty.update({"user_group_id": group.id})
            DutyPlan.objects.create(**duty)

        notice_action_config = {
            "execute_config": {
                "template_detail": {
                    "interval_notify_mode": "standard",  # 间隔模式
                    "notify_interval": 7200,  # 通知间隔
                    "template": notice_template(),
                }
            },
            "id": 55555,
            "plugin_id": 1,
            "plugin_type": "notice",
            "is_enabled": True,
            "bk_biz_id": 2,
            "name": "test_notice",
        }
        strategy_dict = {
            "id": 1,
            "type": "monitor",
            "bk_biz_id": 2,
            "scenario": "os",
            "name": "测试新策略",
            "labels": [],
            "is_enabled": True,
            "items": [],
            "detects": [],
            "notice": {  # 通知设置
                "id": 1,
                "config_id": 55555,  # 套餐ID，如果不选套餐请置为0
                "user_groups": [group.id],  # 告警组ID
                "signal": ["abnormal", "recovered"],
                # 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
                "options": {
                    "converge_config": {
                        "is_enabled": True,
                        "converge_func": "collect",
                        "timedelta": 60,
                        "count": 1,
                        "condition": [
                            {"dimension": "strategy_id", "value": ["self"]},
                            {"dimension": "dimensions", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                            {"dimension": "notice_info", "value": ["self"]},
                        ],
                        "need_biz_converge": True,
                        "sub_converge_config": {
                            "timedelta": 60,
                            "count": 2,
                            "condition": [
                                {"dimension": "bk_biz_id", "value": ["self"]},
                                {"dimension": "notice_receiver", "value": ["self"]},
                                {"dimension": "notice_way", "value": ["self"]},
                                {"dimension": "alert_level", "value": ["self"]},
                                {"dimension": "signal", "value": ["self"]},
                            ],
                            "converge_func": "collect_alarm",
                        },
                    },
                    "start_time": "00:00:00",
                    "end_time": "23:59:59",
                    "exclude_notice_ways": {"recovered": ["voice"]},
                    "chart_image_enabled": False,
                },
                "config": notice_action_config["execute_config"]["template_detail"],
            },
            "actions": [],
        }
        self.alert_info["extra_info"].update(strategy=strategy_dict)
        self.alert_info["id"] = "123123123"

        alert = AlertDocument(**self.alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=notice_action_config),
        )
        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()

        create_actions(1, "abnormal", alerts=[alert])
        self.assertEqual(ActionInstance.objects.filter(is_parent_action=True, action_config_id=55555).count(), 1)
        self.assertEqual(
            ActionInstance.objects.get(is_parent_action=True, action_config_id=55555).inputs["alert_latest_time"],
            self.current_time,
        )
        self.assertEqual(ActionInstance.objects.filter(is_parent_action=False, action_config_id=55555).count(), 9)
        self.set_notice_cache()
        new_voice_action = None

        for action in ActionInstance.objects.filter(is_parent_action=False, action_config_id=55555):
            try:
                n_ap = NoticeActionProcessor(action_id=action.id)
                n_ap.execute()
                if action.inputs["notice_way"] == NoticeWay.VOICE:
                    action.id = None
                    action.status = "converged"
                    action.save()
                    new_voice_action = action
            except BaseException as error:
                print("error info", str(error))

        self.assertEqual(
            ActionInstance.objects.filter(is_parent_action=False, status="success", action_config_id=55555).count(), 7
        )

        new_voice_ap = NoticeActionProcessor(action_id=new_voice_action.id)
        new_voice_ap.execute()
        self.assertFalse(new_voice_ap.context["alarm"].chart_image_enabled)

        new_voice_action.refresh_from_db()
        self.assertEqual(new_voice_action.status, ActionStatus.FAILURE)

        ActionInstance.objects.all().delete()

        alert.status = EventStatus.RECOVERED
        create_actions(1, "recovered", alerts=[alert])
        self.assertEqual(ActionInstance.objects.filter(is_parent_action=False, action_config_id=55555).count(), 8)

        action_config_patch.stop()
        mget_alert_patch.stop()
        get_alert_patch.stop()

    def test_error_content_template_action(self):
        """
        通过策略创建处理
        :return:
        """

        duty_plans = copy.deepcopy(self.duty_plans)
        group = UserGroup.objects.create(**self.user_group_data)
        for duty in duty_plans:
            duty.update({"user_group_id": group.id})
            DutyPlan.objects.create(**duty)

        notice_action_config = {
            "execute_config": {
                "template_detail": {
                    "interval_notify_mode": "standard",  # 间隔模式
                    "notify_interval": 7200,  # 通知间隔
                    "template": notice_template(),
                }
            },
            "id": 55555,
            "plugin_id": 1,
            "plugin_type": "notice",
            "is_enabled": True,
            "bk_biz_id": 2,
            "name": "test_notice",
        }
        self.alert_info["id"] = "123123123"

        alert = AlertDocument(**self.alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=notice_action_config),
        )

        notice_ai = ActionInstance.objects.create(
            action_config=notice_action_config,
            action_config_id=notice_action_config["id"],
            signal="abnormal",
            strategy_id=0,
            alerts=[alert.id],
            inputs={"notice_way": "mail", "notice_receiver": "admin", "notify_info": {"mail": ["admin"]}},
            action_plugin={"id": 2, "plugin_type": ActionPluginType.NOTICE},
        )
        get_actions_patch = patch(
            "alarm_backends.service.fta_action.notice.processor.ActionProcessor.get_same_notice_way_actions",
            MagicMock(return_value={"admin": notice_ai.id}),
        )
        mget_alert_patch.start()
        get_alert_patch.start()
        get_actions_patch.start()
        action_config_patch.start()
        np = NoticeActionProcessor(action_id=notice_ai.id)
        np.execute_notify()
        np.action.refresh_from_db()
        self.assertEqual(np.action.status, ActionStatus.SUCCESS)

        action_config_patch.stop()
        get_actions_patch.stop()
        mget_alert_patch.stop()
        get_alert_patch.stop()

    def test_raise_cache_node_error(self):
        """
        通过策略创建处理
        :return:
        """
        CacheRouter.objects.filter(strategy_score__gte=44444444).delete()

        duty_plans = copy.deepcopy(self.duty_plans)
        group = UserGroup.objects.create(**self.user_group_data)
        for duty in duty_plans:
            duty.update({"user_group_id": group.id})
            DutyPlan.objects.create(**duty)

        notice_action_config = {
            "execute_config": {
                "template_detail": {
                    "interval_notify_mode": "standard",  # 间隔模式
                    "notify_interval": 7200,  # 通知间隔
                    "template": notice_template(),
                }
            },
            "id": 55555,
            "plugin_id": 1,
            "plugin_type": "notice",
            "is_enabled": True,
            "bk_biz_id": 2,
            "name": "test_notice",
        }
        strategy_dict = {
            "id": 44444444,
            "type": "monitor",
            "bk_biz_id": 2,
            "scenario": "os",
            "name": "测试新策略",
            "labels": [],
            "is_enabled": True,
            "items": [],
            "detects": [],
            "notice": {  # 通知设置
                "id": 1,
                "config_id": 55555,  # 套餐ID，如果不选套餐请置为0
                "user_groups": [group.id],  # 告警组ID
                "signal": ["abnormal", "recovered"],
                # 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
                "options": {
                    "converge_config": {
                        "is_enabled": True,
                        "converge_func": "collect",
                        "timedelta": 60,
                        "count": 1,
                        "condition": [
                            {"dimension": "strategy_id", "value": ["self"]},
                            {"dimension": "dimensions", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                            {"dimension": "notice_info", "value": ["self"]},
                        ],
                        "need_biz_converge": True,
                        "sub_converge_config": {
                            "timedelta": 60,
                            "count": 2,
                            "condition": [
                                {"dimension": "bk_biz_id", "value": ["self"]},
                                {"dimension": "notice_receiver", "value": ["self"]},
                                {"dimension": "notice_way", "value": ["self"]},
                                {"dimension": "alert_level", "value": ["self"]},
                                {"dimension": "signal", "value": ["self"]},
                            ],
                            "converge_func": "collect_alarm",
                        },
                    },
                    "start_time": "00:00:00",
                    "end_time": "23:59:59",
                },
                "config": notice_action_config["execute_config"]["template_detail"],
            },
            "actions": [],
        }
        self.alert_info["extra_info"].update(strategy=strategy_dict)
        self.alert_info["id"] = "123123123"

        alert = AlertDocument(**self.alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=notice_action_config),
        )
        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()
        self.assertEqual(create_actions(44444444, "abnormal", alerts=[alert]), [])
        action_config_patch.stop()
        mget_alert_patch.stop()
        get_alert_patch.stop()

    def test_time_range_notice_create(self):
        """
        测试汇总
        :return:
        """
        duty_arranges = [
            {
                "order": 1,
                "users": [{"id": "lisa", "display_name": "管理员", "logo": "", "type": "user"}],
            },
        ]
        user_group = copy.deepcopy(self.user_group_data)
        current_time = datetime.now()
        begin_time = current_time - timedelta(minutes=60)
        end_time = current_time - timedelta(minutes=30)
        user_group["alert_notice"][0]["time_range"] = "{}--{}".format(
            begin_time.strftime("HH:MM"), end_time.strftime("HH:MM")
        )
        group = UserGroup.objects.create(**user_group)
        group.need_duty = False
        group.save()

        for duty in duty_arranges:
            duty.update({"user_group_id": group.id})
            DutyArrange.objects.create(**duty)

        notice_action_config = {
            "execute_config": {
                "template_detail": {
                    "interval_notify_mode": "standard",  # 间隔模式
                    "notify_interval": 7200,  # 通知间隔
                    "template": notice_template(),
                }
            },
            "id": 55555,
            "plugin_id": 1,
            "plugin_type": "notice",
            "is_enabled": True,
            "bk_biz_id": 2,
            "name": "test_notice",
        }
        strategy_dict = {
            "id": 1,
            "type": "monitor",
            "bk_biz_id": 2,
            "scenario": "os",
            "name": "测试新策略",
            "labels": [],
            "is_enabled": True,
            "items": [],
            "detects": [],
            "notice": {  # 通知设置
                "id": 1,
                "config_id": 55555,  # 套餐ID，如果不选套餐请置为0
                "user_groups": [group.id],  # 告警组ID
                "signal": ["abnormal", "recovered"],
                # 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
                "options": {
                    "converge_config": {
                        "is_enabled": True,
                        "converge_func": "collect",
                        "timedelta": 60,
                        "count": 1,
                        "condition": [
                            {"dimension": "strategy_id", "value": ["self"]},
                            {"dimension": "dimensions", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                            {"dimension": "notice_info", "value": ["self"]},
                        ],
                        "need_biz_converge": True,
                        "sub_converge_config": {
                            "timedelta": 60,
                            "count": 2,
                            "condition": [
                                {"dimension": "bk_biz_id", "value": ["self"]},
                                {"dimension": "notice_receiver", "value": ["self"]},
                                {"dimension": "notice_way", "value": ["self"]},
                                {"dimension": "alert_level", "value": ["self"]},
                                {"dimension": "signal", "value": ["self"]},
                            ],
                            "converge_func": "collect_alarm",
                        },
                    },
                    "start_time": "00:00:00",
                    "end_time": "23:59:59",
                },
                "config": notice_action_config["execute_config"]["template_detail"],
            },
            "actions": [],
        }
        self.alert_info["extra_info"].update(strategy=strategy_dict)
        alert = AlertDocument(**self.alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=notice_action_config),
        )
        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()

        actions0 = create_actions(1, "abnormal", alerts=[alert])
        self.assertEqual(len(actions0), 1)
        self.assertEqual(
            ActionInstance.objects.get(id=actions0[0]).get_content()["text"], '达到通知告警的执行条件【告警触发时】，当前通知人员为空'
        )
        group.alert_notice[0]["time_range"] = "00:00--23:59"
        group.save()
        parent_actions = ActionInstance.objects.filter(is_parent_action=True).only(
            "id",
            "need_poll",
            "is_polled",
            "action_config_id",
            "execute_times",
            "strategy_id",
            "signal",
            "alerts",
            "alert_level",
            "dimensions",
            "dimension_hash",
            "strategy_relation_id",
        )
        self.assertEqual(parent_actions.count(), 1)
        self.assertEqual(alert.extra_info["cycle_handle_record"]["1"]["execute_times"], 1)
        time.sleep(1)
        action = parent_actions[0]
        actions1 = create_interval_actions(
            strategy_dict["id"],
            action.signal,
            action.alerts,
            severity=action.alert_level,
            dimensions=action.dimensions,
            dimension_hash=action.dimension_hash,
            relation_id=action.strategy_relation_id,
            execute_times=alert.extra_info["cycle_handle_record"]["1"]["execute_times"],
        )
        self.assertEqual(len(actions1), 6)
        self.assertEqual(ActionInstance.objects.filter(is_parent_action=True).count(), 2)
        mget_alert_patch.stop()
        get_alert_patch.stop()
        action_config_patch.stop()

    def test_interval_notice_create(self):
        """
        测试汇总
        :return:
        """
        duty_arranges = [
            {
                "order": 1,
                "users": [{"id": "lisa", "display_name": "管理员", "logo": "", "type": "user"}],
            },
        ]
        group = UserGroup.objects.create(**self.user_group_data)
        group.need_duty = False
        group.save()

        for duty in duty_arranges:
            duty.update({"user_group_id": group.id})
            DutyArrange.objects.create(**duty)

        notice_action_config = {
            "execute_config": {
                "template_detail": {
                    "interval_notify_mode": "standard",  # 间隔模式
                    "notify_interval": 7200,  # 通知间隔
                    "template": notice_template(),
                }
            },
            "id": 55555,
            "plugin_id": 1,
            "plugin_type": "notice",
            "is_enabled": True,
            "bk_biz_id": 2,
            "name": "test_notice",
        }
        strategy_dict = {
            "id": 1,
            "type": "monitor",
            "bk_biz_id": 2,
            "scenario": "os",
            "name": "测试新策略",
            "labels": [],
            "is_enabled": True,
            "items": [],
            "detects": [],
            "notice": {  # 通知设置
                "id": 1,
                "config_id": 55555,  # 套餐ID，如果不选套餐请置为0
                "user_groups": [group.id],  # 告警组ID
                "signal": ["abnormal", "recovered"],
                # 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
                "options": {
                    "converge_config": {
                        "is_enabled": True,
                        "converge_func": "collect",
                        "timedelta": 60,
                        "count": 1,
                        "condition": [
                            {"dimension": "strategy_id", "value": ["self"]},
                            {"dimension": "dimensions", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                            {"dimension": "notice_info", "value": ["self"]},
                        ],
                        "need_biz_converge": True,
                        "sub_converge_config": {
                            "timedelta": 60,
                            "count": 2,
                            "condition": [
                                {"dimension": "bk_biz_id", "value": ["self"]},
                                {"dimension": "notice_receiver", "value": ["self"]},
                                {"dimension": "notice_way", "value": ["self"]},
                                {"dimension": "alert_level", "value": ["self"]},
                                {"dimension": "signal", "value": ["self"]},
                            ],
                            "converge_func": "collect_alarm",
                        },
                    },
                    "start_time": "00:00:00",
                    "end_time": "23:59:59",
                },
                "config": notice_action_config["execute_config"]["template_detail"],
            },
            "actions": [],
        }
        self.alert_info["extra_info"].update(
            strategy=strategy_dict, cycle_handle_record={"1": {"execute_times": 1, "last_time": int(time.time())}}
        )

        alert = AlertDocument(**self.alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=notice_action_config),
        )
        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()
        actions1 = create_interval_actions(
            alert.strategy["id"],
            ActionSignal.ABNORMAL,
            [alert.id],
            severity=alert.severity,
            relation_id=1,
            execute_times=1,
        )
        self.assertEqual(len(actions1), 6)
        self.assertEqual(ActionInstance.objects.filter(is_parent_action=True).count(), 1)

        alert = Alert(data=alert.to_dict())
        alert.data["is_shielded"] = True
        alert.update_extra_info(
            "cycle_handle_record",
            {"1": {"last_time": int(time.time()) - 7200, "latest_anomaly_time": 123, "execute_times": 3}},
        )
        alert_cache_key = ALERT_SNAPSHOT_KEY.get_key(strategy_id=alert.strategy_id, alert_id=alert.id)
        ALERT_SNAPSHOT_KEY.client.set(alert_cache_key, json.dumps(alert.to_dict()))

        # 执行次数已经到的3次了，如果是第一次的任务过期的任务直接忽略，避免多次
        actions = create_interval_actions(
            alert.strategy["id"],
            ActionSignal.ABNORMAL,
            [alert.id],
            alerts=[alert.to_document()],
            severity=alert.severity,
            relation_id=1,
            execute_times=1,
        )
        self.assertEqual(len(actions), 0)

        ActionInstance.objects.all().delete()
        settings.GLOBAL_SHIELD_ENABLED = True
        # 屏蔽的时候，只产生主任务
        actions = create_interval_actions(
            alert.strategy["id"],
            ActionSignal.ABNORMAL,
            [alert.id],
            severity=alert.severity,
            relation_id=1,
            execute_times=2,
        )
        self.assertEqual(len(actions), 1)
        settings.GLOBAL_SHIELD_ENABLED = False
        ALERT_SNAPSHOT_KEY.client.delete(alert_cache_key)
        mget_alert_patch.stop()
        get_alert_patch.stop()
        action_config_patch.stop()

    def test_job_notice_failed_execute(self):
        duty_plans = copy.deepcopy(self.duty_plans)
        group = UserGroup.objects.create(**self.user_group_data)
        for duty in duty_plans:
            duty.update({"user_group_id": group.id})
            DutyPlan.objects.create(**duty)

        job_config = {
            "execute_config": {
                "template_id": 1000043,
                "template_detail": {"1000005_3": "{{alert.event.ip}}", "1000004_1": "hello, {{alert.event.ip}}"},
                "timeout": 60,
            },
            "name": "uwork重启",
            "desc": "这是描述，这是描述",
            "is_enabled": True,
            "plugin_id": 3,
            "bk_biz_id": 2,
            "id": 4444,
        }

        strategy_dict = {
            "id": 1,
            "type": "monitor",
            "bk_biz_id": 2,
            "scenario": "os",
            "name": "测试新策略",
            "labels": [],
            "is_enabled": True,
            "items": [],
            "detects": [],
            "notice": {  # 通知设置
                "id": 1,
                "config_id": 0,  # 套餐ID，如果不选套餐请置为0
                "user_groups": [group.id],  # 告警组ID
                "signal": ["execute", "execute_failed"],
                # 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
                "options": {
                    "converge_config": {"need_biz_converge": True},  # 告警风暴开关
                    "start_time": "00:00:00",
                    "end_time": "23:59:59",
                },
                "config": {},
            },
            "actions": [  # 如果用户没有选处理动作，请置为空列表
                {
                    "id": 1,
                    "config_id": 4444,  # 套餐ID
                    "signal": ["abnormal", "recovered"],  # 触发信号，abnormal-异常，recovered-恢复，closed-关闭, no_data-无数据时
                    "user_groups": [group.id],  # 告警组ID，提交时请与通知中设置的告警组保持一致
                    "options": {
                        "converge_config": {
                            "is_enabled": True,  # 是否启用
                            "converge_func": "skip_when_success",  # 防御动作
                            "timedelta": 60,  # 防御窗口大小（秒），默认设置为 60
                            "count": 1,  # 执行次数，默认设置为 1
                        },
                        "start_time": "00:00:00",
                        "end_time": "23:59:59",
                    },
                }
            ],
        }
        self.alert_info["extra_info"].update(strategy=strategy_dict)

        alert = AlertDocument(**self.alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=job_config),
        )
        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()
        actions = create_actions(1, "abnormal", alerts=[alert])
        self.assertEqual(len(actions), 1)

        j_ap = JobActionProcessor(action_id=actions[0])
        j_ap.set_finished(ActionStatus.FAILURE)
        self.assertEqual(j_ap.action.status, "failure")
        execute_notify_result = j_ap.action.outputs.get("execute_notify_result")
        self.assertIsNotNone(execute_notify_result)
        self.assertIsNotNone(execute_notify_result.get(NotifyStep.FAILURE))
        action_config_patch.stop()
        mget_alert_patch.stop()
        get_alert_patch.stop()

    def test_job_notice_failed_with_no_assignees(self):
        duty_plans = copy.deepcopy(self.duty_plans)
        group = UserGroup.objects.create(**self.user_group_data)
        for duty in duty_plans:
            duty.update({"user_group_id": group.id})
            duty["users"] = []
            DutyPlan.objects.create(**duty)

        job_config = {
            "execute_config": {
                "template_id": 1000043,
                "template_detail": {"1000005_3": "{{alert.event.ip}}", "1000004_1": "hello, {{alert.event.ip}}"},
                "timeout": 60,
            },
            "name": "uwork重启",
            "desc": "这是描述，这是描述",
            "is_enabled": True,
            "plugin_id": 3,
            "bk_biz_id": 2,
            "id": 4444,
        }

        strategy_dict = {
            "id": 1,
            "type": "monitor",
            "bk_biz_id": 2,
            "scenario": "os",
            "name": "测试新策略",
            "labels": [],
            "is_enabled": True,
            "items": [],
            "detects": [],
            "notice": {  # 通知设置
                "id": 1,
                "config_id": 0,  # 套餐ID，如果不选套餐请置为0
                "user_groups": [group.id],  # 告警组ID
                "signal": ["execute", "execute_failed"],
                # 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
                "options": {
                    "converge_config": {"need_biz_converge": True},  # 告警风暴开关
                    "start_time": "00:00:00",
                    "end_time": "23:59:59",
                },
                "config": {},
            },
            "actions": [  # 如果用户没有选处理动作，请置为空列表
                {
                    "id": 1,
                    "config_id": 4444,  # 套餐ID
                    "signal": ["abnormal", "recovered"],  # 触发信号，abnormal-异常，recovered-恢复，closed-关闭, no_data-无数据时
                    "user_groups": [group.id],  # 告警组ID，提交时请与通知中设置的告警组保持一致
                    "options": {
                        "converge_config": {
                            "is_enabled": True,  # 是否启用
                            "converge_func": "skip_when_success",  # 防御动作
                            "timedelta": 60,  # 防御窗口大小（秒），默认设置为 60
                            "count": 1,  # 执行次数，默认设置为 1
                        },
                        "start_time": "00:00:00",
                        "end_time": "23:59:59",
                    },
                }
            ],
        }
        self.alert_info["extra_info"].update(strategy=strategy_dict)

        alert = AlertDocument(**self.alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=job_config),
        )
        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()
        actions = create_actions(1, "abnormal", alerts=[alert])
        self.assertEqual(len(actions), 1)

        j_ap = JobActionProcessor(action_id=actions[0])
        with self.assertRaises(EmptyAssigneeError):
            task_config = j_ap.function_config.get("create_task")
            j_ap.run_request_action(task_config)

        j_ap.action.status = "running"
        j_ap.create_task()
        self.assertEqual(j_ap.action.status, "failure")
        self.assertEqual(j_ap.action.ex_data["message"], "执行创建job任务出错，获取当前告警策略配置的告警组用户为空，无法执行处理套餐")

        action_config_patch.stop()
        mget_alert_patch.stop()
        get_alert_patch.stop()

    def test_job_with_appointees(self):
        duty_plans = copy.deepcopy(self.duty_plans)
        group = UserGroup.objects.create(**self.user_group_data)
        for duty in duty_plans:
            duty.update({"user_group_id": group.id})
            duty["users"] = []
            DutyPlan.objects.create(**duty)

        job_config = {
            "execute_config": {
                "template_id": 1000043,
                "template_detail": {"1000005_3": "{{alert.event.ip}}", "1000004_1": "hello, {{alert.event.ip}}"},
                "timeout": 60,
            },
            "name": "uwork重启",
            "desc": "这是描述，这是描述",
            "is_enabled": True,
            "plugin_id": 3,
            "bk_biz_id": 2,
            "id": 4444,
        }

        strategy_dict = get_strategy_dict(group.id)
        self.alert_info["extra_info"].update(strategy=strategy_dict)

        alert = AlertDocument(**self.alert_info)
        alert.appointee = ["admin", "lisa"]
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=job_config),
        )
        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()
        actions = create_actions(1, "abnormal", alerts=[alert])
        self.assertEqual(len(actions), 1)

        action_config_patch.stop()
        mget_alert_patch.stop()
        get_alert_patch.stop()

    def test_context_without_action(self):
        alert = AlertDocument(**self.alert_info)
        alert.first_anomaly_time = alert.latest_time - 30 * 60
        alert_context = ActionContext(action=None, alerts=[alert], use_alert_snap=True)
        self.assertEqual(alert_context.target.host.bk_host_innerip, "127.0.0.1")
        self.assertEqual(alert_context.alert, alert)
        self.assertEqual(alert_context.alarm.dimension_string, "云区域ID=2,主机IP=127.0.0.1,backend=1")
        self.assertEqual(alert_context.related_actions, [])
        self.assertEqual(alert_context.alarm.level, alert.severity)
        self.assertTrue(_("已持续") in alert_context.content.content)
        self.assertIsNotNone(alert_context.alarm.callback_message)
        self.assertIsNotNone(alert_context.alarm.new_dimensions)
        self.assertIsNotNone(alert_context.alarm.new_dimensions)
        self.assertTrue(alert_context.alarm.chart_image_enabled)

    def test_user_content_render_error(self):
        alert = AlertDocument(**self.alert_info)
        alert_context = ActionContext(action=None, alerts=[alert], use_alert_snap=True, notice_way="mail")
        context = alert_context.get_dictionary()
        context["content_template"] = "{{json.loads(content.content)}}"
        content_template_path = "notice/abnormal/action/mail_content.jinja"
        render_content = AlarmNoticeTemplate(content_template_path).render(context)
        self.assertTrue(
            _("用户配置的通知模板渲染失败，默认使用系统内置模板，渲染失败可能是使用了不正确的语法，具体请查看策略配置{}").format(alert_context.alarm.strategy_url)
            in render_content
        )

    def _test_user_content_with_custom_title(self, use_custom_title: bool):
        alert = AlertDocument(**self.alert_info)
        ac_data = copy.deepcopy(self.ac_data)

        for template in ac_data["execute_config"]["template_detail"]["template"]:
            template["title_tmpl"] = (
                alert_constants.DEFAULT_TITLE_TEMPLATE,
                "custom" + alert_constants.DEFAULT_TITLE_TEMPLATE,
            )[use_custom_title]

        action = ActionInstance.objects.create(
            alerts=[alert.id],
            signal="abnormal",
            strategy_id=0,
            alert_level=alert.severity,
            status=ActionStatus.SUCCESS,
            bk_biz_id=2,
            inputs={},
            action_config=ac_data,
            action_config_id=0,
            action_plugin={
                "plugin_type": ActionPluginType.NOTICE,
                "name": "通知",
                "plugin_key": ActionPluginType.NOTICE,
            },
        )

        for notice_way in [NoticeWay.WX_BOT, NoticeWay.MAIL, "rtx"]:
            alert_context = ActionContext(action=action, alerts=[alert], use_alert_snap=True, notice_way=notice_way)
            context = alert_context.get_dictionary()

            # 没有使用自定义标题的，内容模板不加标题模板
            if not use_custom_title:
                self.assertEqual(
                    context["content_template"],
                    ac_data["execute_config"]["template_detail"]["template"][0]["message_tmpl"],
                )
                continue

            if notice_way not in [NoticeWay.MAIL, "rtx"]:
                self.assertEqual(
                    context["content_template"],
                    "\n".join(
                        [
                            ac_data["execute_config"]["template_detail"]["template"][0]["title_tmpl"],
                            ac_data["execute_config"]["template_detail"]["template"][0]["message_tmpl"],
                        ]
                    ),
                )
            else:
                self.assertEqual(
                    context["content_template"],
                    ac_data["execute_config"]["template_detail"]["template"][0]["message_tmpl"],
                )

    def test_user_content_with_custom_title(self):
        self._test_user_content_with_custom_title(use_custom_title=False)
        self._test_user_content_with_custom_title(use_custom_title=True)

    def test_en_sender(self):
        language = "zh-cn"
        mail_content_path = Sender.get_language_template_path("notice/abnormal/action/mail_content.jinja", language)
        self.assertEqual(mail_content_path, "notice/abnormal/action/mail_content.jinja")
        language = "en"
        md_content_path = Sender.get_language_template_path("notice/abnormal/action/markdown_content.jinja", language)
        self.assertEqual(md_content_path, "notice/abnormal/action/markdown_content_en.jinja")

    def test_markdown_content_render(self):
        alert = AlertDocument(**self.alert_info)
        action = ActionInstance.objects.create(
            alerts=[alert.id],
            signal="abnormal",
            strategy_id=0,
            alert_level=alert.severity,
            status=ActionStatus.SUCCESS,
            bk_biz_id=2,
            inputs={},
            action_config={},
            action_config_id=0,
            action_plugin={
                "plugin_type": ActionPluginType.NOTICE,
                "name": "通知",
                "plugin_key": ActionPluginType.NOTICE,
            },
        )
        alert_context = ActionContext(action=action, alerts=[alert], use_alert_snap=True, notice_way=NoticeWay.WX_BOT)
        context = alert_context.get_dictionary()
        context["alarm"].log_related_info = "testtesttest"
        content_template_path = "notice/abnormal/action/markdown_content.jinja"
        context["content_template"] = "#test title#12345"
        render_content = AlarmNoticeTemplate(content_template_path).render(context)
        print("render_content", render_content)
        self.assertTrue("**test title: **12345" in render_content)
        content_template_path = "notice/fta_action/markdown_content.jinja"
        operate_content = AlarmNoticeTemplate(content_template_path).render(context)
        print(operate_content)

        alert_context = ActionContext(
            action=action, alerts=[alert, alert], use_alert_snap=True, notice_way=NoticeWay.WX_BOT
        )
        self.assertIsNone(alert_context.alarm.quick_shield_url)

        render_content = AlarmNoticeTemplate(content_template_path).render(alert_context.get_dictionary())
        self.assertFalse("[告警屏蔽]" in render_content)

    def test_render_related_info_markdown(self):
        alert = AlertDocument(**self.alert_info)
        related_info = "".join(["test" for i in range(0, 100)])
        context = ActionContext(
            action=None, alerts=[alert], use_alert_snap=True, notice_way="markdown"
        ).get_dictionary()
        context["alarm"].log_related_info = related_info
        content = Jinja2Renderer.render("{{content.related_info}}", context)
        self.assertEqual(content, f"**关联信息: **集群() 模块()\\n> {related_info}\\n")
        self.assertEqual(context["content"].dimension, "**维度: **\\n> 云区域ID=2\\n> 主机IP=127.0.0.1\\n> backend=1\\n")
        print(context["content"].target_markdown)

    def test_render_k8s_markdown_target(self):
        alert_info = copy.deepcopy(self.alert_info)
        alert_info["event"]["category"] = "kubernetes"
        dd = {"bcs_cluster_id": "fsdfsdf", "namespace": "test", "pod_name": "aaa"}
        alert_info["dimensions"] = [
            {"key": key, "value": value, "display_key": key, "display_value": value} for key, value in dd.items()
        ]
        alert = AlertDocument(**alert_info)
        context = ActionContext(
            action=None, alerts=[alert], use_alert_snap=True, notice_way="markdown"
        ).get_dictionary()
        index = context["content"].target.find("route_path=") + 11
        route_path = base64.b64decode(context["content"].target[index:-1]).decode("utf8")
        self.assertTrue("dashboardId=pod" in route_path)

    def test_render_markdown(self):
        alert = AlertDocument(**self.alert_info)
        related_info = "".join(["test" for i in range(0, 100)])
        context = ActionContext(action=None, alerts=[alert], use_alert_snap=True, notice_way=NoticeWay.WX_BOT)
        context_dict = context.get_dictionary()
        context_dict["alarm"].log_related_info = related_info
        user_content = NoticeRowRenderer.render(Jinja2Renderer.render(context.DEFAULT_TEMPLATE, context_dict), {})
        expected_content = (
            "**首次异常: **{current_time}\n"
            "**最近异常: **{current_time}\n"
            "**内容: **新告警, None\n"
            "**所属空间: **[2]蓝鲸 (业务)\n"
            "**目标: **[127.0.0.1]({host}route/?bizId=2&route_path={route_path})\n"
            "**维度: **\\n> 云区域ID=2\\n> 主机IP=127.0.0.1\\n> backend=1\\n\n"
            "**关联信息: **集群() 模块()\\n> {related_info}\\n\n"
            "**关联指标: **0 个指标,0 个维度\n"
            "**维度下钻: **异常维度 2，异常维度值 2"
        ).format(
            host=settings.BK_MONITOR_HOST,
            route_path=base64.b64encode(b"#/performance/detail/127.0.0.1-0").decode("utf8"),
            related_info=related_info,
            current_time=context.alarm.begin_time.strftime(settings.DATETIME_FORMAT),
        )
        self.assertEqual(expected_content, user_content)

    def test_render_related_info(self):
        alert = AlertDocument(**self.alert_info)
        context = ActionContext(action=None, alerts=[alert], use_alert_snap=True, notice_way="sms").get_dictionary()
        content = Jinja2Renderer.render("{{content.sms_forced_related_info[:8]}}", context)
        self.assertEqual(content, "关联信息: 集群")
        related_info = "".join(["test" for i in range(0, 100)])

        context = ActionContext(action=None, alerts=[alert], use_alert_snap=True, notice_way="sms").get_dictionary()
        context["alarm"].related_info = related_info
        content = Jinja2Renderer.render("{{content.sms_forced_related_info}}", context)
        self.assertEqual(content, f"关联信息: {related_info[:297]}...")

    def test_render_anomaly_dimensions(self):
        alert = AlertDocument(**self.alert_info)
        context = ActionContext(action=None, alerts=[alert], use_alert_snap=True, notice_way="rtx").get_dictionary()
        content = Jinja2Renderer.render("{{content.anomaly_dimensions}}", context)
        self.assertEqual(content, "维度下钻: 异常维度 2，异常维度值 2")

    def test_render_recommended_metrics(self):
        alert = AlertDocument(**self.alert_info)
        context = ActionContext(action=None, alerts=[alert], use_alert_snap=True, notice_way="rtx").get_dictionary()
        content = Jinja2Renderer.render("{{content.recommended_metrics}}", context)
        self.assertEqual(content, "关联指标: 0 个指标,0 个维度")

    def test_ai_setting__config_exist(self):
        alert = AlertDocument(**self.alert_info)
        DimensionDrillLightManager(alert)
        action_context = ActionContext(action=None, alerts=[alert], use_alert_snap=True, notice_way="rtx")
        ai_setting_config = action_context.alarm.ai_setting_config
        ai_setting_config[DIMENSION_DRILL]["is_enabled"] = True

        manager = DimensionDrillLightManager(alert, ReadOnlyAiSetting(alert.event["bk_biz_id"], ai_setting_config))
        assert manager.is_enable() is True

    def test_ai_setting__config_not_exist(self):
        alert = AlertDocument(**self.alert_info)
        action_context = ActionContext(action=None, alerts=[alert], use_alert_snap=True, notice_way="rtx")
        assert action_context.alarm.ai_setting_config is None

        manager = RecommendMetricManager(alert, ReadOnlyAiSetting(alert.event["bk_biz_id"], None))
        assert manager.is_enable() is False

    def test_render_content_length(self):
        alert = AlertDocument(**self.alert_info)
        related_info = "".join(["test" for i in range(0, 1000)])
        context = ActionContext(action=None, alerts=[alert], use_alert_snap=True, notice_way="rtx").get_dictionary()
        context["alarm"].related_info = related_info
        content_template_path = "notice/abnormal/action/markdown_content.jinja"
        content_template = AlarmNoticeTemplate(template_path=content_template_path)
        content1 = content_template.render(context=context)
        context["user_content_length"] = 1024
        content2 = content_template.render(context=context)
        self.assertNotEqual(content1, content2)
        self.assertEqual(len(context["user_content"]), 1024)

    def test_render_content_utf8_length(self):
        """uTF8渲染，最终长度应该少于等于设置长度"""
        alert = AlertDocument(**self.alert_info)
        related_info = "".join(["【" for i in range(0, 1000)])
        context = ActionContext(action=None, alerts=[alert], use_alert_snap=True, notice_way="rtx").get_dictionary()
        context["alarm"].related_info = related_info
        content_template_path = "notice/abnormal/action/markdown_content.jinja"
        content_template = AlarmNoticeTemplate(template_path=content_template_path)
        content1 = content_template.render(context=context)
        context["encoding"] = "utf-8"
        context["user_content_length"] = 1024
        content2 = content_template.render(context=context)
        self.assertNotEqual(content1, content2)
        self.assertLessEqual(len(context["user_content"].encode("utf8")), 1024)

    def test_sender_sms_limit(self):
        settings.SMS_CONTENT_LENGTH = 300
        content = "".join(["000000" for i in range(0, 500)])
        alert = AlertDocument(**self.alert_info)
        context = ActionContext(
            action=None, alerts=[alert], use_alert_snap=True, notice_way=NoticeWay.SMS
        ).get_dictionary()
        context["content_template"] = content
        sender = Sender(context=context, content_template_path="notice/abnormal/action/sms_content.jinja")
        self.assertEqual(len(sender.content), 300)
        content = sender.get_notice_content(NoticeWay.SMS, sender.content)
        self.assertEqual(sender.content, content)

    def test_sender_sms_normal(self):
        settings.SMS_CONTENT_LENGTH = 300
        content = "".join(["0" for i in range(0, 150)])
        alert = AlertDocument(**self.alert_info)
        context = ActionContext(
            action=None, alerts=[alert], use_alert_snap=True, notice_way=NoticeWay.SMS
        ).get_dictionary()
        context["content_template"] = content
        sender = Sender(context=context, content_template_path="notice/abnormal/action/sms_content.jinja")
        print("sender.content: ", sender.content)
        self.assertLess(len(sender.content), 300)
        self.assertFalse("..." in sender.content)

    def test_sender_sms_ch_limit(self):
        settings.SMS_CONTENT_LENGTH = 300
        content = "".join(["【" for i in range(0, 500)])
        alert = AlertDocument(**self.alert_info)
        context = ActionContext(
            action=None, alerts=[alert], use_alert_snap=True, notice_way=NoticeWay.SMS
        ).get_dictionary()
        context["content_template"] = content
        sender = Sender(context=context, content_template_path="notice/abnormal/action/sms_content.jinja")
        self.assertEqual(len(sender.content), 300)

    def test_sender_wxbot_ch_limit(self):
        """
        中文字符(utf8编码计算)的长度一定是小于设定的长度
        """
        settings.NOTICE_MESSAGE_MAX_LENGTH = {NoticeWay.WX_BOT: 4096}
        content = "".join(["【" for i in range(0, 4096)])
        alert = AlertDocument(**self.alert_info)
        context = ActionContext(
            action=None, alerts=[alert], use_alert_snap=True, notice_way=NoticeWay.WX_BOT
        ).get_dictionary()
        context["content_template"] = content
        sender = Sender(context=context, content_template_path="notice/abnormal/action/markdown_content.jinja")
        self.assertLess(len(sender.content), 4096)
        settings.NOTICE_MESSAGE_MAX_LENGTH = {}

    def test_cut_line_str_by_max_bytes(self):
        """
        测试按行分块
        """
        content = "\n".join(["".join(["a" for i in range(0, 200)]) for j in range(0, 5)])
        contents = cut_line_str_by_max_bytes(content, 404, encoding="utf8")
        self.assertEqual(len(contents), 3)

    def test_render_layouts(self):
        content = "\n".join(["".join(["a" for i in range(0, 200)]) for j in range(0, 11)])
        print("content length", len(content))
        mentioned_users = "**mentioned users：**<@admin>"
        layouts = Sender.split_layout_content("markdown", content, mentioned_users)
        # 每个最大值为2046
        self.assertEqual(len(layouts["components"]), 4)
        print("layouts", layouts)

    def test_send_sms_limit(self):
        settings.SMS_CONTENT_LENGTH = 0
        content = "".join(["000000" for i in range(0, 500)])
        sender = NoneTemplateSender(title="1", content=content)
        sender.send_sms([])
        self.assertEqual(len(sender.content), len(content))

        settings.SMS_CONTENT_LENGTH = 500
        sender.send_sms([])
        self.assertEqual(len(sender.content), 500)
        settings.SMS_CONTENT_LENGTH = 0

    def test_send_webot_limit(self):
        settings.NOTICE_MESSAGE_MAX_LENGTH = {"rtx": 0}
        content = "".join(["000000" for i in range(0, 500)])
        sender = NoneTemplateSender(title="1", content=content)
        sender.send("rtx", [])
        send_content = sender.content.encode("utf8")
        self.assertEqual(len(send_content), len(content))

        settings.NOTICE_MESSAGE_MAX_LENGTH = {"rtx": 500}
        sender.send("rtx", [])
        send_content = sender.content.encode("utf8")
        self.assertEqual(len(send_content), 500)
        settings.NOTICE_MESSAGE_MAX_LENGTH = {"rtx": 0}

    def test_action_config_is_enabled_False_execute(self):
        new_ac = copy.deepcopy(self.ac_data)
        new_ac["is_enabled"] = False
        ActionConfig.objects.filter(**new_ac)

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=new_ac),
        )
        action_config_patch.start()

        event = EventDocument(**{"bk_biz_id": 2, "ip": "127.0.0.1", "bk_cloud_id": 0})
        alert = AlertDocument(**{"event": event, "severity": 1, "id": 1})

        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))
        mget_alert_patch.start()
        get_alert_patch.start()

        create_actions(1, "abnormal", alerts=[alert])
        self.assertEqual(ActionInstance.objects.all().count(), 0)
        mget_alert_patch.stop()
        get_alert_patch.stop()
        action_config_patch.stop()

    def test_notice_collect(self):
        """
        测试汇总
        :return:
        """
        self.send_wxwork_bot_patcher.start()
        duty_arranges = [
            {
                "users": [{"id": "lisa", "display_name": "管理员", "logo": "", "type": "user"}],
            },
        ]
        group = UserGroup.objects.create(**self.user_group_data)
        group.need_duty = False
        group.save()
        for duty in duty_arranges:
            duty.update({"user_group_id": group.id})
            DutyArrange.objects.create(**duty)

        notice_action_config = {
            "execute_config": {
                "template_detail": {
                    "interval_notify_mode": "standard",  # 间隔模式
                    "notify_interval": 7200,  # 通知间隔
                    "template": notice_template(),
                }
            },
            "id": 55555,
            "plugin_id": 1,
            "plugin_type": "notice",
            "is_enabled": True,
            "bk_biz_id": 2,
            "name": "test_notice",
        }
        strategy_dict = {
            "id": 1,
            "type": "monitor",
            "bk_biz_id": 2,
            "scenario": "os",
            "name": "测试新策略",
            "labels": [],
            "is_enabled": True,
            "items": [],
            "detects": [],
            "notice": {  # 通知设置
                "id": 1,
                "config_id": 55555,  # 套餐ID，如果不选套餐请置为0
                "user_groups": [group.id],  # 告警组ID
                "signal": ["abnormal", "recovered"],
                # 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
                "options": {
                    "converge_config": {
                        "is_enabled": True,
                        "converge_func": "collect",
                        "timedelta": 60,
                        "count": 1,
                        "condition": [
                            {"dimension": "strategy_id", "value": ["self"]},
                            {"dimension": "dimensions", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                            {"dimension": "notice_info", "value": ["self"]},
                        ],
                        "need_biz_converge": True,
                        "sub_converge_config": {
                            "timedelta": 60,
                            "count": 2,
                            "condition": [
                                {"dimension": "bk_biz_id", "value": ["self"]},
                                {"dimension": "notice_receiver", "value": ["self"]},
                                {"dimension": "notice_way", "value": ["self"]},
                                {"dimension": "alert_level", "value": ["self"]},
                                {"dimension": "signal", "value": ["self"]},
                            ],
                            "converge_func": "collect_alarm",
                        },
                    },
                    "start_time": "00:00:00",
                    "end_time": "23:59:59",
                },
                "config": notice_action_config["execute_config"]["template_detail"],
            },
            "actions": [],
        }
        self.alert_info["extra_info"].update(strategy=strategy_dict)
        alert = AlertDocument(**self.alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=notice_action_config),
        )
        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()

        actions0 = create_actions(1, "abnormal", alerts=[alert])
        self.assertEqual(len(actions0), 6)
        time.sleep(2)
        actions1 = create_actions(1, "abnormal", alerts=[alert])
        self.assertEqual(len(actions1), 6)
        actions0.extend(actions1)

        self.converge_actions(ActionInstance.objects.all())

        self.assertEqual(ConvergeRelation.objects.filter(converge_status=ConvergeStatus.SKIPPED).count(), 4)
        self.assertEqual(ConvergeRelation.objects.filter(converge_status=ConvergeStatus.EXECUTED).count(), 4)
        self.assertEqual(ConvergeRelation.objects.filter(is_primary=True).count(), 4)

        converged_condition_display = []

        primary_relation = ConvergeRelation.objects.filter(is_primary=True).first()
        converge_inst = ConvergeInstance.objects.get(id=primary_relation.converge_id)
        for converged_condition_key in converge_inst.converge_config["converged_condition"]:
            if converged_condition_key == "action_id":
                continue
            converged_condition_display.append(
                str(ALL_CONVERGE_DIMENSION.get(converged_condition_key, converged_condition_key))
            )

        description = "在{}分钟内，当具有相同{}的告警超过{}条以上，在执行相同的处理套餐时，进行告警防御".format(
            converge_inst.converge_config["timedelta"] // 60,
            ",".join(converged_condition_display),
            converge_inst.converge_config["count"],
        )
        self.assertEqual(description, converge_inst.description)
        ac = ActionContext(ActionInstance.objects.get(id=primary_relation.related_id))
        self.assertEqual(description, ac.action_instance.converged_description)

        self.assertEqual(ActionInstance.objects.filter(status=ActionStatus.SKIPPED).count(), 4)

        self.assertEqual(ActionInstance.objects.filter(signal=ActionSignal.COLLECT).count(), 4)

        ActionInstance.objects.filter(is_parent_action=True).update(status=ActionStatus.FAILURE)

        collect_action = [
            ai
            for ai in ActionInstance.objects.filter(signal=ActionSignal.COLLECT)
            if ai.inputs["notice_way"][0] == NoticeWay.WX_BOT
        ][0]
        ac = ActionContext(action=collect_action).get_dictionary()
        user_set = {"admin", "lisa"}

        self.assertEqual(
            {chatid: set(users) for chatid, users in ac["mentioned_users"].items()},
            {"hihihihihh": user_set, "hihihiashihi": user_set},
        )

        ap = CollectActionProcessor(ActionInstance.objects.filter(signal=ActionSignal.COLLECT).first().id)
        ap.collect()

        self.assertEqual(
            ActionInstance.objects.filter(signal=ActionSignal.COLLECT, status__in=ActionStatus.END_STATUS).count(), 1
        )

        related_action_status = {r_a.real_status for r_a in ap.related_actions}
        self.assertEqual(related_action_status, {ap.action.status})

        mget_alert_patch.stop()
        get_alert_patch.stop()
        action_config_patch.stop()
        self.send_wxwork_bot_patcher.stop()

    def test_follow_notice_collect(self):
        """
        测试关注人通知汇总
        :return:
        """
        self.send_wxwork_bot_patcher.start()
        duty_arranges = [
            {
                "users": [{"id": "lisa", "display_name": "管理员", "logo": "", "type": "user"}],
            },
        ]
        group = UserGroup.objects.create(**self.user_group_data)
        group.need_duty = False
        group.save()
        for duty in duty_arranges:
            duty.update({"user_group_id": group.id})
            DutyArrange.objects.create(**duty)

        notice_action_config = {
            "execute_config": {
                "template_detail": {
                    "interval_notify_mode": "standard",  # 间隔模式
                    "notify_interval": 7200,  # 通知间隔
                    "template": notice_template(),
                }
            },
            "id": 55555,
            "plugin_id": 1,
            "plugin_type": "notice",
            "is_enabled": True,
            "bk_biz_id": 2,
            "name": "test_notice",
        }
        strategy_dict = {
            "id": 1,
            "type": "monitor",
            "bk_biz_id": 2,
            "scenario": "os",
            "name": "测试新策略",
            "labels": [],
            "is_enabled": True,
            "items": [],
            "detects": [],
            "notice": {  # 通知设置
                "id": 1,
                "config_id": 55555,  # 套餐ID，如果不选套餐请置为0
                "user_groups": [group.id],  # 告警组ID
                "user_type": UserGroupType.FOLLOWER,
                "signal": ["abnormal", "recovered"],
                # 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
                "options": {
                    "converge_config": {
                        "is_enabled": True,
                        "converge_func": "collect",
                        "timedelta": 60,
                        "count": 1,
                        "condition": [
                            {"dimension": "strategy_id", "value": ["self"]},
                            {"dimension": "dimensions", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                            {"dimension": "notice_info", "value": ["self"]},
                        ],
                        "need_biz_converge": True,
                        "sub_converge_config": {
                            "timedelta": 60,
                            "count": 2,
                            "condition": [
                                {"dimension": "bk_biz_id", "value": ["self"]},
                                {"dimension": "notice_receiver", "value": ["self"]},
                                {"dimension": "notice_way", "value": ["self"]},
                                {"dimension": "alert_level", "value": ["self"]},
                                {"dimension": "signal", "value": ["self"]},
                            ],
                            "converge_func": "collect_alarm",
                        },
                    },
                    "start_time": "00:00:00",
                    "end_time": "23:59:59",
                },
                "config": notice_action_config["execute_config"]["template_detail"],
            },
            "actions": [],
        }
        self.alert_info["extra_info"].update(strategy=strategy_dict)
        alert = AlertDocument(**self.alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=notice_action_config),
        )
        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()

        actions0 = create_actions(1, "abnormal", alerts=[alert])
        self.assertEqual(len(actions0), 6)
        time.sleep(2)
        actions1 = create_actions(1, "abnormal", alerts=[alert])
        self.assertEqual(len(actions1), 6)
        actions0.extend(actions1)

        self.converge_actions(ActionInstance.objects.all())

        self.assertEqual(ConvergeRelation.objects.filter(converge_status=ConvergeStatus.SKIPPED).count(), 4)
        self.assertEqual(ConvergeRelation.objects.filter(converge_status=ConvergeStatus.EXECUTED).count(), 4)
        self.assertEqual(ConvergeRelation.objects.filter(is_primary=True).count(), 4)

        converged_condition_display = []

        primary_relation = ConvergeRelation.objects.filter(is_primary=True).first()
        converge_inst = ConvergeInstance.objects.get(id=primary_relation.converge_id)
        for converged_condition_key in converge_inst.converge_config["converged_condition"]:
            if converged_condition_key == "action_id":
                continue
            converged_condition_display.append(
                str(ALL_CONVERGE_DIMENSION.get(converged_condition_key, converged_condition_key))
            )

        description = "在{}分钟内，当具有相同{}的告警超过{}条以上，在执行相同的处理套餐时，进行告警防御".format(
            converge_inst.converge_config["timedelta"] // 60,
            ",".join(converged_condition_display),
            converge_inst.converge_config["count"],
        )
        self.assertEqual(description, converge_inst.description)
        ac = ActionContext(ActionInstance.objects.get(id=primary_relation.related_id))
        self.assertEqual(description, ac.action_instance.converged_description)

        self.assertEqual(ActionInstance.objects.filter(status=ActionStatus.SKIPPED).count(), 4)

        self.assertEqual(ActionInstance.objects.filter(signal=ActionSignal.COLLECT).count(), 4)

        ActionInstance.objects.filter(is_parent_action=True).update(status=ActionStatus.FAILURE)

        collect_action = [
            ai
            for ai in ActionInstance.objects.filter(signal=ActionSignal.COLLECT)
            if ai.inputs["notice_way"][0] == NoticeWay.WX_BOT
        ][0]
        ac = ActionContext(action=collect_action).get_dictionary()
        user_set = {"admin", "lisa"}

        self.assertEqual(
            {chatid: set(users) for chatid, users in ac["mentioned_users"].items()},
            {"hihihihihh": user_set, "hihihiashihi": user_set},
        )

        ap = CollectActionProcessor(ActionInstance.objects.filter(signal=ActionSignal.COLLECT).first().id)
        ap.collect()

        self.assertEqual(
            ActionInstance.objects.filter(signal=ActionSignal.COLLECT, status__in=ActionStatus.END_STATUS).count(), 1
        )

        related_action_status = {r_a.real_status for r_a in ap.related_actions}
        self.assertEqual(related_action_status, {ap.action.status})

        mget_alert_patch.stop()
        get_alert_patch.stop()
        action_config_patch.stop()
        self.send_wxwork_bot_patcher.stop()

    def test_notice_collect_without_alert(self):
        converge_inst = ConvergeInstance.objects.create(
            converge_type="action", bk_biz_id=2, converge_config={"converged_condition": []}
        )
        ai = ActionInstance.objects.create(
            action_config={},
            action_config_id=0,
            signal="abnormal",
            strategy_id=0,
            status="skipped",
            inputs={"notice_way": "mail", "notice_receiver": "admin", "notify_info": {"mail": ["admin"]}},
            action_plugin={"id": 2, "plugin_type": ActionPluginType.NOTICE},
        )
        ConvergeRelation.objects.create(converge_id=converge_inst.id, related_id=ai.id, related_type="action")
        collect_ai = ActionInstance.objects.create(
            inputs={"converge_id": converge_inst.id},
            bk_biz_id=2,
            signal="collect",
            strategy_id=0,
            action_plugin={"id": 2, "plugin_type": ActionPluginType.NOTICE},
        )
        ap = CollectActionProcessor(collect_ai.id)
        ap.collect()
        self.assertFalse(ap.is_finished)
        ap.collect()
        ap.collect()
        self.assertTrue(ap.is_finished)

    def create_test_action_inst(self, biz_dimension):
        alert_info = copy.deepcopy(self.alert_info)
        alert_info["dimensions"] = [{"key": "bk_biz_id", "value": biz_dimension}]
        alert_info["id"] = 1
        alert = AlertDocument(**alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))
        mget_alert_patch.start()
        get_alert_patch.start()
        new_actions = create_actions(1, "abnormal", alerts=[alert])
        conv_ids = []
        self.converge_actions(ActionInstance.objects.filter(status="received"), ConvergeType.ACTION)
        self.converge_actions(
            ConvergeInstance.objects.filter(converge_type=ConvergeType.ACTION).exclude(id__in=conv_ids),
            ConvergeType.CONVERGE,
        )
        time.sleep(1)
        mget_alert_patch.stop()
        get_alert_patch.stop()
        return len(new_actions) - 1

    def test_notice_multi_collect(self):
        """
        测试汇总
        :return:
        """
        duty_arranges = [
            {
                "users": [{"id": "lisa", "display_name": "管理员", "logo": "", "type": "user"}],
            },
        ]

        user_group_data = {
            "name": "蓝鲸业务的告警组-全职通知组",
            "desc": "用户组的说明用户组的说明用户组的说明用户组的说明用户组的说明",
            "bk_biz_id": 2,
            "alert_notice": [  # 告警通知配置
                {
                    "time_range": "00:00:00--23:59:59",  # 生效时间段
                    "notify_config": [  # 通知方式配置
                        {
                            "level": 3,  # 级别
                            "type": [  # 通知渠道列表
                                "mail",
                                "weixin",
                            ],
                        },
                        {"level": 2, "type": ["mail"]},
                        {
                            "level": 1,
                            "type": ["mail", "weixin", "wxwork-bot"],
                            "chatid": "hihihihihh,hihihiashihi",
                        },
                    ],
                }
            ],
            "action_notice": [  # 执行通知配置
                {
                    "time_range": "00:00:00--23:59:59",  # 生效时间段
                    "notify_config": [  # 通知方式
                        {"phase": 3, "type": ["mail", "weixin"]},  # 执行阶段，3-执行前，2-成功时，1-失败时
                        {"phase": 2, "type": ["mail", "weixin"]},
                        {
                            "phase": 1,
                            "type": ["mail", "weixin", "wxwork-bot"],
                            "chatid": "hihihihihh,hihihiashihi",
                        },
                    ],
                }
            ],
        }
        group = UserGroup.objects.create(**user_group_data)
        for duty in duty_arranges:
            duty.update({"user_group_id": group.id})
            DutyArrange.objects.create(**duty)

        notice_action_config = {
            "execute_config": {
                "template_detail": {
                    "interval_notify_mode": "standard",  # 间隔模式
                    "notify_interval": 7200,  # 通知间隔
                    "template": notice_template(),
                }
            },
            "id": 55555,
            "plugin_id": 1,
            "plugin_type": "notice",
            "is_enabled": True,
            "bk_biz_id": 2,
            "name": "test_notice",
        }
        strategy_dict = {
            "id": 1,
            "type": "monitor",
            "bk_biz_id": 2,
            "scenario": "os",
            "name": "测试新策略",
            "labels": [],
            "is_enabled": True,
            "items": [],
            "detects": [],
            "notice": {  # 通知设置
                "id": 1,
                "config_id": 55555,  # 套餐ID，如果不选套餐请置为0
                "user_groups": [group.id],  # 告警组ID
                "signal": ["abnormal", "recovered"],
                # 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
                "options": {
                    "converge_config": {
                        "is_enabled": True,
                        "converge_func": "collect",
                        "timedelta": 60,
                        "count": 1,
                        "condition": [
                            {"dimension": "strategy_id", "value": ["self"]},
                            {"dimension": "dimensions", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                            {"dimension": "notice_info", "value": ["self"]},
                        ],
                        "need_biz_converge": True,
                        "sub_converge_config": {
                            "timedelta": 60,
                            "count": 2,
                            "condition": [
                                {"dimension": "bk_biz_id", "value": ["self"]},
                                {"dimension": "notice_receiver", "value": ["self"]},
                                {"dimension": "notice_way", "value": ["self"]},
                                {"dimension": "alert_level", "value": ["self"]},
                                {"dimension": "signal", "value": ["self"]},
                            ],
                            "converge_func": "collect_alarm",
                        },
                    },
                    "start_time": "00:00:00",
                    "end_time": "23:59:59",
                },
                "config": notice_action_config["execute_config"]["template_detail"],
            },
            "actions": [],
        }
        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=notice_action_config),
        )
        action_config_patch.start()
        self.alert_info["extra_info"]["strategy"] = strategy_dict
        total_actions = 0

        for bk_biz_id in [2, 3, 4, 5, 6]:
            # 创建不同维度的内容
            total_actions += self.create_test_action_inst(bk_biz_id)

        print("total actions: %s" % total_actions)

        # 产生20个子任务进行汇总操作
        self.assertEqual(
            ConvergeRelation.objects.filter(converge_status=ConvergeStatus.EXECUTED, related_type="action").count(), 20
        )

        # 被业务汇总收敛12个（不同业务维度的）
        self.assertEqual(ActionInstance.objects.filter(status=ActionStatus.SKIPPED).count(), 12)

        # 产生24个汇总，4个业务汇总，20个同维度汇总
        self.assertEqual(ActionInstance.objects.filter(signal=ActionSignal.COLLECT).count(), 24)

        for bk_biz_id in [2, 3, 4, 5, 6]:
            # 创建不通维度的内容
            total_actions += self.create_test_action_inst(bk_biz_id)

        print("total actions: %s" % total_actions)

        self.assertEqual(
            ConvergeRelation.objects.filter(converge_status=ConvergeStatus.EXECUTED, related_type="action").count(), 20
        )
        # 被业务汇总收敛32个
        self.assertEqual(ActionInstance.objects.filter(status=ActionStatus.SKIPPED).count(), 32)

        # 产生24个汇总，四个业务汇总，20个同维度汇总
        self.assertEqual(ActionInstance.objects.filter(signal=ActionSignal.COLLECT).count(), 24)

        action_config_patch.stop()

    def test_transition(self):
        for i in range(10):
            ConvergeRelation.objects.create(
                related_id=i,
                converge_id=1,
                related_type="action",
                is_primary=True,
                converge_status="skipped",
                alerts=[],
            )

        for i in range(10):
            try:
                ConvergeRelation.objects.create(
                    related_id=i,
                    converge_id=1,
                    related_type="action",
                    is_primary=True,
                    converge_status="skipped",
                    alerts=[],
                )
            except IntegrityError as error:
                print(error)
            print(ConvergeRelation.objects.get(related_id=i).id)

    def test_new_notice_multi_collect(self):
        """
        测试汇总
        :return:
        """

        duty_arranges = [
            {
                "users": [{"id": "lisa", "display_name": "管理员", "logo": "", "type": "user"}],
            },
        ]

        user_group_data = copy.deepcopy(self.user_group_data_new)
        user_group_data["need_duty"] = False
        group = UserGroup.objects.create(**user_group_data)
        for duty in duty_arranges:
            duty.update({"user_group_id": group.id})
            DutyArrange.objects.create(**duty)

        notice_action_config = {
            "execute_config": {
                "template_detail": {
                    "interval_notify_mode": "standard",  # 间隔模式
                    "notify_interval": 7200,  # 通知间隔
                    "template": notice_template(),
                }
            },
            "id": 55555,
            "plugin_id": 1,
            "plugin_type": "notice",
            "is_enabled": True,
            "bk_biz_id": 2,
            "name": "test_notice",
        }
        strategy_dict = {
            "id": 1,
            "type": "monitor",
            "bk_biz_id": 2,
            "scenario": "os",
            "name": "测试新策略",
            "labels": [],
            "is_enabled": True,
            "items": [],
            "detects": [],
            "notice": {  # 通知设置
                "id": 1,
                "config_id": 55555,  # 套餐ID，如果不选套餐请置为0
                "user_groups": [group.id],  # 告警组ID
                "signal": ["abnormal", "recovered"],
                # 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
                "options": {
                    "converge_config": {
                        "is_enabled": True,
                        "converge_func": "collect",
                        "timedelta": 60,
                        "count": 1,
                        "condition": [
                            {"dimension": "strategy_id", "value": ["self"]},
                            {"dimension": "dimensions", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                            {"dimension": "notice_info", "value": ["self"]},
                        ],
                        "need_biz_converge": True,
                        "sub_converge_config": {
                            "timedelta": 60,
                            "count": 2,
                            "condition": [
                                {"dimension": "bk_biz_id", "value": ["self"]},
                                {"dimension": "notice_receiver", "value": ["self"]},
                                {"dimension": "notice_way", "value": ["self"]},
                                {"dimension": "alert_level", "value": ["self"]},
                                {"dimension": "signal", "value": ["self"]},
                            ],
                            "converge_func": "collect_alarm",
                        },
                    },
                    "start_time": "00:00:00",
                    "end_time": "23:59:59",
                },
                "config": notice_action_config["execute_config"]["template_detail"],
            },
            "actions": [],
        }
        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=notice_action_config),
        )
        action_config_patch.start()
        self.alert_info["extra_info"]["strategy"] = strategy_dict
        total_actions = 0

        for bk_biz_id in [2, 3, 4, 5, 6]:
            # 创建不同维度的内容
            total_actions += self.create_test_action_inst(bk_biz_id)

        print("total actions: %s" % total_actions)

        # 一共产生了30个子任务，5个主任务
        self.assertEqual(
            ConvergeRelation.objects.filter(converge_status=ConvergeStatus.EXECUTED, related_type="action").count(), 30
        )

        # 被业务汇总收敛18个（微信，邮件， bkchat, 群机器人）
        self.assertEqual(ActionInstance.objects.filter(status=ActionStatus.SKIPPED).count(), 18)

        # 产生36个汇总，6个业务汇总（一个邮件，一个微信，两个企业微信，两个bkchat），30个同维度汇总
        self.assertEqual(ActionInstance.objects.filter(signal=ActionSignal.COLLECT).count(), 36)

        for bk_biz_id in [2, 3, 4, 5, 6]:
            # 创建不通维度的内容
            total_actions += self.create_test_action_inst(bk_biz_id)

        print("total actions: %s" % total_actions)

        # 新产生的任务，都默认是忽略，汇总到同维度告警上
        self.assertEqual(
            ConvergeRelation.objects.filter(converge_status=ConvergeStatus.EXECUTED, related_type="action").count(), 30
        )
        # 当前30个，全部被汇总，加上之前的18个，一共48个
        self.assertEqual(ActionInstance.objects.filter(status=ActionStatus.SKIPPED).count(), 48)

        # 产生36个汇总，6个业务汇总（一个邮件，一个微信，两个企业微信，两个bkchat），30个同维度汇总， 新产生的告警事件全部汇总到这36个
        self.assertEqual(ActionInstance.objects.filter(signal=ActionSignal.COLLECT).count(), 36)

        action_config_patch.stop()

    def test_notice_collect_ignore(self):
        """
        测试忽略汇总
        :return:
        """
        duty_arranges = [
            {
                "users": [{"id": "lisa", "display_name": "管理员", "logo": "", "type": "user"}],
            },
        ]
        group = UserGroup.objects.create(**self.user_group_data)
        group.need_duty = False
        group.save()
        for duty in duty_arranges:
            duty.update({"user_group_id": group.id})
            DutyArrange.objects.create(**duty)

        notice_action_config = {
            "execute_config": {
                "template_detail": {
                    "interval_notify_mode": "standard",  # 间隔模式
                    "notify_interval": 7200,  # 通知间隔
                    "template": [],
                }
            },
            "id": 55555,
            "plugin_id": 1,
            "plugin_type": "notice",
            "is_enabled": True,
            "bk_biz_id": 2,
            "name": "test_notice",
        }
        strategy_dict = {
            "id": 1,
            "type": "monitor",
            "bk_biz_id": 2,
            "scenario": "os",
            "name": "测试新策略",
            "labels": [],
            "is_enabled": True,
            "items": [],
            "detects": [],
            "notice": {  # 通知设置
                "id": 1,
                "config_id": 55555,  # 套餐ID，如果不选套餐请置为0
                "user_groups": [group.id],  # 告警组ID
                "signal": ["abnormal", "recovered"],
                # 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
                "options": {
                    "converge_config": {
                        "converge_func": "collect",
                        "timedelta": 60,
                        "count": 1,
                        "condition": [
                            {"dimension": "strategy_id", "value": ["self"]},
                            {"dimension": "dimensions", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                            {"dimension": "notice_info", "value": ["self"]},
                        ],
                        "need_biz_converge": True,
                        "sub_converge_config": {
                            "timedelta": 60,
                            "count": 2,
                            "condition": [
                                {"dimension": "bk_biz_id", "value": ["self"]},
                                {"dimension": "notice_receiver", "value": ["self"]},
                                {"dimension": "notice_way", "value": ["self"]},
                                {"dimension": "alert_level", "value": ["self"]},
                                {"dimension": "signal", "value": ["self"]},
                            ],
                            "converge_func": "collect_alarm",
                        },
                    },
                    "start_time": "00:00:00",
                    "end_time": "23:59:59",
                },
                "config": notice_action_config["execute_config"]["template_detail"],
            },
            "actions": [],
        }
        self.alert_info["extra_info"].update(strategy=strategy_dict)

        alert = AlertDocument(**self.alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=notice_action_config),
        )
        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()

        actions0 = create_actions(1, "abnormal", alerts=[alert])
        self.assertEqual(len(actions0), 6)
        time.sleep(2)
        actions1 = create_actions(1, "abnormal", alerts=[alert])
        self.assertEqual(len(actions1), 6)

        self.converge_actions(
            ActionInstance.objects.filter(id__in=actions0 + actions1), ConvergeType.ACTION, is_enabled=False
        )

        self.assertEqual(
            ActionInstance.objects.filter(status=ActionStatus.CONVERGED, is_parent_action=False).count(), 10
        )
        self.assertEqual(ActionInstance.objects.filter(status=ActionStatus.CONVERGED, is_parent_action=True).count(), 2)

        mget_alert_patch.stop()
        get_alert_patch.stop()
        action_config_patch.stop()

    def test_notice_shield(self):
        """
        测试通知屏蔽
        :return:
        """
        duty_arranges = [
            {
                "users": [{"id": "lisa", "display_name": "管理员", "logo": "", "type": "user"}],
            },
        ]
        group = UserGroup.objects.create(**self.user_group_data)
        group.need_duty = False
        group.save()
        for duty in duty_arranges:
            duty.update({"user_group_id": group.id})
            DutyArrange.objects.create(**duty)

        start_time = time_tools.strftime_local(datetime.now(tz=timezone.utc) + timedelta(hours=1), _format="%H:%M:%S")
        end_time = time_tools.strftime_local(datetime.now(tz=timezone.utc) + timedelta(hours=2), _format="%H:%M:%S")

        notice_action_config = {
            "execute_config": {
                "template_detail": {
                    "interval_notify_mode": "standard",  # 间隔模式
                    "notify_interval": 7200,  # 通知间隔
                    "template": [  # 通知模板配置
                        {
                            "signal": "abnormal",
                        }
                    ],
                }
            },
            "id": 55555,
            "plugin_id": 1,
            "plugin_type": "notice",
            "is_enabled": True,
            "bk_biz_id": 2,
            "name": "test_notice",
        }
        strategy_dict = {
            "id": 1,
            "type": "monitor",
            "bk_biz_id": 2,
            "scenario": "os",
            "name": "测试新策略",
            "labels": [],
            "is_enabled": True,
            "items": [],
            "detects": [],
            "notice": {  # 通知设置
                "id": 1,
                "config_id": 55555,  # 套餐ID，如果不选套餐请置为0
                "user_groups": [group.id],  # 告警组ID
                "signal": ["abnormal", "recovered"],
                # 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
                "options": {
                    "converge_config": {
                        "is_enabled": True,
                        "converge_func": "collect",
                        "timedelta": 60,
                        "count": 1,
                        "condition": [
                            {"dimension": "strategy_id", "value": ["self"]},
                            {"dimension": "dimensions", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                            {"dimension": "notice_info", "value": ["self"]},
                        ],
                        "need_biz_converge": True,
                        "sub_converge_config": {
                            "timedelta": 60,
                            "count": 2,
                            "condition": [
                                {"dimension": "bk_biz_id", "value": ["self"]},
                                {"dimension": "notice_receiver", "value": ["self"]},
                                {"dimension": "notice_way", "value": ["self"]},
                                {"dimension": "alert_level", "value": ["self"]},
                                {"dimension": "signal", "value": ["self"]},
                            ],
                            "converge_func": "collect_alarm",
                        },
                    },
                    "start_time": start_time,
                    "end_time": end_time,
                },
                "config": notice_action_config["execute_config"]["template_detail"],
            },
            "actions": [],
        }
        self.alert_info["extra_info"].update(strategy=strategy_dict)
        alert = AlertDocument(**self.alert_info)

        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=notice_action_config),
        )

        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()

        actions0 = create_actions(1, "abnormal", alerts=[alert])
        self.assertEqual(len(actions0), 6)

        alert.status = EventStatus.CLOSED
        # 异常状态下不产生告警
        self.assertEqual(create_actions(1, "abnormal", alerts=[alert]), [])

        self.converge_actions(ActionInstance.objects.all())

        self.assertEqual(ConvergeRelation.objects.filter(converge_status=ConvergeStatus.SKIPPED).count(), 0)
        self.assertEqual(ConvergeRelation.objects.filter(converge_status=ConvergeStatus.EXECUTED).count(), 0)
        self.assertEqual(ConvergeRelation.objects.filter(is_primary=True).count(), 0)

        self.assertEqual(ActionInstance.objects.filter(status=ActionStatus.SHIELD).count(), 5)

        mget_alert_patch.stop()
        get_alert_patch.stop()
        action_config_patch.stop()

    def create_shield_group(self):
        duty_arranges = [
            {
                "users": [{"id": "selinagyan", "display_name": "郭燕", "logo": "", "type": "user"}],
            },
        ]
        group = UserGroup.objects.create(**self.user_group_data)
        group.need_duty = False
        group.save()

        for duty in duty_arranges:
            duty.update({"user_group_id": group.id})
            DutyArrange.objects.create(**duty)
        return group

    def test_alert_shield_by_dimensions(self):
        """
        测试通知屏蔽
        :return:
        """
        group = self.create_shield_group()
        strategy_dict = get_strategy_dict(group.id)

        self.alert_info["extra_info"].update(strategy=strategy_dict)

        alert = AlertDocument(**self.alert_info)
        shield_config = {
            "id": 123,
            "is_enabled": True,
            "is_deleted": False,
            "bk_biz_id": 2,
            "category": "dimension",
            "scope_type": "dimension",
            "content": "",
            "begin_time": datetime.now(tz=timezone.utc),
            "end_time": datetime.now(tz=timezone.utc) + timedelta(hours=1),
            "dimension_config": {
                "dimension_conditions": [
                    {
                        "key": "bk_target_ip",
                        "value": [
                            "127.0.0.1",
                        ],
                        "method": "eq",
                        "condition": "and",
                    },
                    {
                        "key": "bk_target_cloud_id",
                        "value": ["0", "2"],
                        "method": "eq",
                        "condition": "or",
                    },
                ]
            },
            "cycle_config": {"type": 1, "week_list": [], "day_list": [], "begin_time": "", "end_time": ""},
        }

        shield_obj = AlertShieldObj(shield_config)
        self.assertTrue(shield_obj.is_match(alert))

        # 不屏蔽状态
        event = EventDocument(**{"bk_biz_id": 2, "ip": "127.0.0.1", "bk_cloud_id": 0})
        alert_info = {
            "id": 1,
            "event": event,
            "severity": 1,
            "begin_time": int(time.time()),
            "create_time": int(time.time()),
            "latest_time": int(time.time()),
            "duration": 60,
            "common_dimensions": {},
            "dimensions": [
                AttrDict({"key": "bk_target_ip", "value": "127.0.0.2"}),
                AttrDict({"key": "bk_target_cloud_id", "value": "2"}),
            ],
            "extra_info": {"strategy": {}},
            "status": EventStatus.ABNORMAL,
        }
        new_alert = AlertDocument(**alert_info)
        self.assertTrue(shield_obj.is_match(new_alert))

        shield_config = {
            "id": 123,
            "is_enabled": True,
            "is_deleted": False,
            "bk_biz_id": 2,
            "category": "dimension",
            "scope_type": "dimension",
            "content": "",
            "begin_time": datetime.now(tz=timezone.utc),
            "end_time": datetime.now(tz=timezone.utc) + timedelta(hours=1),
            "dimension_config": {
                "dimension_conditions": [
                    {
                        "key": "bk_target_ip",
                        "value": [
                            "127.0.0.1",
                        ],
                        "method": "eq",
                        "condition": "and",
                    },
                    {
                        "key": "bk_target_cloud_id",
                        "value": ["0", "2"],
                        "method": "eq",
                        "condition": "and",
                    },
                ]
            },
            "cycle_config": {"type": 1, "week_list": [], "day_list": [], "begin_time": "", "end_time": ""},
        }
        shield_obj = AlertShieldObj(shield_config)
        self.assertFalse(shield_obj.is_match(new_alert))

    def test_k8s_alert_shield_by_ip_topo(self):
        """
        测试通知屏蔽
        :return:
        """
        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "bk_biz_id": 2,
                    "plugin_id": "fta-test",
                    "alert_name": "CPU usage high",
                    "time": int(time.time()),
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target_type": "",
                    "target": "",
                    "category": KubernetesResultTableLabel.kubernetes,
                    "dedupe_keys": ["alert_name", "tags.device", "target_type", "target"],
                    "extra_info": {},
                }
            )
        )
        alert.add_dimension("ip", "127.0.0.1")
        alert.add_dimension("bk_cloud_id", 0)
        alert = alert.to_document()
        shield_config = {
            "id": 123,
            "is_enabled": True,
            "bk_biz_id": 2,
            "category": "scope",
            "scope_type": "ip",
            "begin_time": datetime.now(tz=timezone.utc),
            "end_time": datetime.now(tz=timezone.utc) + timedelta(hours=1),
            "dimension_config": {
                'bk_target_ip': [{'bk_host_id': 281, 'bk_target_ip': '127.0.0.1', 'bk_target_cloud_id': 0}]
            },
            "cycle_config": {"type": 1, "week_list": [], "day_list": [], "begin_time": "", "end_time": ""},
        }

        shield_obj = AlertShieldObj(shield_config)
        self.assertTrue(shield_obj.is_match(alert))

    def test_k8s_alert_shield_by_module_topo(self):
        """
        测试k8s告警根据模块节点进行屏蔽
        :return:
        """
        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "bk_biz_id": 2,
                    "plugin_id": "fta-test",
                    "alert_name": "CPU usage high",
                    "time": int(time.time()),
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target_type": "",
                    "target": "",
                    "category": KubernetesResultTableLabel.kubernetes,
                    "dedupe_keys": ["alert_name", "tags.device", "target_type", "target"],
                    "extra_info": {},
                }
            )
        )
        alert.add_dimension("ip", "127.0.0.1")
        alert.add_dimension("bk_cloud_id", 0)
        alert.add_dimension("bk_topo_node", ["module|8", "set|1"])
        alert = alert.to_document()
        shield_config = {
            "id": 123,
            "is_enabled": True,
            "bk_biz_id": 2,
            "category": "scope",
            "scope_type": "ip",
            "begin_time": datetime.now(tz=timezone.utc),
            "end_time": datetime.now(tz=timezone.utc) + timedelta(hours=1),
            "dimension_config": {'bk_topo_node': [{'bk_obj_id': 'module', 'bk_inst_id': 8}]},
            "cycle_config": {"type": 1, "week_list": [], "day_list": [], "begin_time": "", "end_time": ""},
        }

        shield_obj = AlertShieldObj(shield_config)
        self.assertTrue(shield_obj.is_match(alert))

    def test_alert_shield_by_strategy_dimensions(self):
        group = self.create_shield_group()
        strategy_dict = get_strategy_dict(group.id)
        alert_info = {
            "id": 1,
            "severity": 1,
            "begin_time": int(time.time()),
            "create_time": int(time.time()),
            "latest_time": int(time.time()),
            "duration": 60,
            "common_dimensions": {},
            "dimensions": [
                AttrDict({"key": "bk_target_ip", "value": "127.0.0.1"}),
                AttrDict({"key": "bk_target_cloud_id", "value": "2"}),
            ],
            "extra_info": {"strategy": strategy_dict},
            "status": EventStatus.ABNORMAL,
        }
        test_strategy_alert = AlertDocument(**alert_info)
        # 策略屏蔽支持维度屏蔽
        shield_config = {
            "id": 123,
            "is_enabled": True,
            "is_deleted": False,
            "bk_biz_id": 2,
            "category": "strategy",
            "scope_type": "node",
            "content": "",
            "begin_time": datetime.now(tz=timezone.utc),
            "end_time": datetime.now(tz=timezone.utc) + timedelta(hours=1),
            "dimension_config": {
                "level": [1],
                "bk_topo_node": [{"bk_obj_id": "biz"}],
                "dimension_conditions": [
                    {
                        "key": "bk_target_ip",
                        "value": [
                            "127.0.0.1",
                        ],
                        "method": "eq",
                        "condition": "and",
                    },
                    {
                        "key": "bk_target_cloud_id",
                        "value": ["0", "2"],
                        "method": "eq",
                        "condition": "or",
                    },
                ],
            },
            "cycle_config": {"type": 1, "week_list": [], "day_list": [], "begin_time": "", "end_time": ""},
        }
        shield_obj = AlertShieldObj(shield_config)
        self.assertTrue(shield_obj.is_match(test_strategy_alert))

        shield_config = {
            "id": 123,
            "is_enabled": True,
            "is_deleted": False,
            "bk_biz_id": 2,
            "category": "strategy",
            "scope_type": "ip",
            "content": "",
            "begin_time": datetime.now(tz=timezone.utc),
            "end_time": datetime.now(tz=timezone.utc) + timedelta(hours=1),
            "dimension_config": {
                "level": [1],
                "bk_target_ip": [{"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": 2}],
                "dimension_conditions": [
                    {
                        "key": "bk_target_ip",
                        "value": [
                            "127.0.0.1",
                        ],
                        "method": "eq",
                        "condition": "and",
                    },
                    {
                        "key": "bk_target_cloud_id",
                        "value": ["0", "1", "2", "3"],
                        "method": "include",
                        "condition": "and",
                    },
                ],
            },
            "cycle_config": {"type": 1, "week_list": [], "day_list": [], "begin_time": "", "end_time": ""},
        }
        shield_obj = AlertShieldObj(shield_config)
        self.assertTrue(shield_obj.is_match(test_strategy_alert))

        shield_config = {
            "id": 123,
            "is_enabled": True,
            "is_deleted": False,
            "bk_biz_id": 2,
            "category": "strategy",
            "scope_type": "ip",
            "content": "",
            "begin_time": datetime.now(tz=timezone.utc),
            "end_time": datetime.now(tz=timezone.utc) + timedelta(hours=1),
            "dimension_config": {
                "level": [1],
                "bk_target_ip": [{"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": 2}],
                "dimension_conditions": [
                    {
                        "key": "bk_target_ip",
                        "value": [
                            "127.0.0.1",
                        ],
                        "method": "eq",
                        "condition": "and",
                    },
                    {
                        "key": "bk_target_cloud_id",
                        "value": ["0", "1"],
                        "method": "include",
                        "condition": "and",
                    },
                ],
            },
            "cycle_config": {"type": 1, "week_list": [], "day_list": [], "begin_time": "", "end_time": ""},
        }
        shield_obj = AlertShieldObj(shield_config)
        self.assertFalse(shield_obj.is_match(test_strategy_alert))

    def test_notice_global_shield(self):
        """
        测试通知屏蔽
        :return:
        """
        settings.GLOBAL_SHIELD_ENABLED = True

        group = self.create_shield_group()

        strategy_dict = get_strategy_dict(group.id)
        self.alert_info["extra_info"].update(strategy=strategy_dict)

        alert = AlertDocument(**self.alert_info)

        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=strategy_dict.pop("notice_action_config", {})),
        )
        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()

        actions0 = create_actions(1, "abnormal", alerts=[alert])
        self.assertEqual(len(actions0), 1)
        p_action = ActionInstance.objects.get(id__in=actions0)
        # p_action.is_shielded = True
        self.assertTrue(p_action.inputs["is_alert_shielded"])
        print(p_action.get_content())
        self.assertTrue("因系统全局屏蔽配置， 默认屏蔽当前处理" in p_action.get_content()["text"])

        p_action.inputs["shield_ids"] = [1]
        alert_log = p_action.get_content()
        print(alert_log)
        self.assertTrue("查看屏蔽策略" in alert_log["text"])
        self.assertIsNotNone(alert_log["router_info"])

        settings.GLOBAL_SHIELD_ENABLED = False

        mget_alert_patch.stop()
        get_alert_patch.stop()
        action_config_patch.stop()

    def test_alert_host_shield(self):
        """
        测试通知屏蔽
        :return:
        """
        group = self.create_shield_group()

        strategy_dict = get_strategy_dict(group.id)
        self.alert_info["extra_info"].update(strategy=strategy_dict)

        alert = AlertDocument(**self.alert_info)
        alert.event.target_type = "HOST"

        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=strategy_dict.pop("notice_action_config", {})),
        )
        self.get_host_patcher = patch(
            "alarm_backends.core.cache.cmdb.host.HostManager.get",
            MagicMock(
                return_value=Host(
                    attrs={
                        "bk_host_innerip": "127.0.0.1",
                        "bk_cloud_id": 0,
                        "bk_host_id": 1,
                        "bk_biz_id": 2,
                        "bk_state": "运营中[无告警]",
                        "idc_unit_name": "上海",
                        "net_device_id": 123,
                        "topo_link": {},
                    }
                )
            ),
        )

        self.get_host_patcher.start()
        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()

        actions0 = create_actions(1, "abnormal", alerts=[alert])
        self.assertEqual(len(actions0), 1)
        p_action = ActionInstance.objects.get(id__in=actions0)
        self.assertTrue(p_action.inputs["is_alert_shielded"])
        print(p_action.get_content())
        self.assertTrue("因当前主机状态为屏蔽告警，默认屏蔽当前处理" in p_action.get_content()["text"])

        p_action.inputs["shield_ids"] = [1]
        alert_log = p_action.get_content()
        print(alert_log)
        self.assertTrue("查看屏蔽策略" in alert_log["text"])
        self.assertIsNotNone(alert_log["router_info"])

        settings.GLOBAL_SHIELD_ENABLED = False

        mget_alert_patch.stop()
        get_alert_patch.stop()
        action_config_patch.stop()

    def test_k8s_alert_host_shield(self):
        """
        测试k8s通过主机状态设置为不告警
        :return:
        """
        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "bk_biz_id": 2,
                    "plugin_id": "fta-test",
                    "alert_name": "CPU usage high",
                    "time": int(time.time()),
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target_type": "",
                    "target": "",
                    "category": KubernetesResultTableLabel.kubernetes,
                    "dedupe_keys": ["alert_name", "tags.device", "target_type", "target"],
                    "extra_info": {},
                }
            )
        )
        alert.update_extra_info("agg_dimensions", ["bcs_cluster_id"])
        alert.add_dimension("ip", "127.0.0.1")
        alert.add_dimension("bk_cloud_id", 0)

        host_patcher = patch(
            "alarm_backends.core.cache.cmdb.host.HostManager.get",
            MagicMock(
                return_value=Host(
                    attrs={
                        "bk_host_innerip": "127.0.0.1",
                        "bk_cloud_id": 0,
                        "bk_host_id": 1,
                        "bk_biz_id": 2,
                        "bk_state": "运营中[无告警]",
                        "idc_unit_name": "上海",
                        "net_device_id": 123,
                        "topo_link": {},
                    }
                )
            ),
        )
        host_patcher.start()
        self.assertTrue(HostShielder(alert.to_document()).is_matched())

    def test_create_actions_of_unshielded(self):
        """
        测试通知屏蔽解除
        :return:
        """
        settings.GLOBAL_SHIELD_ENABLED = True
        group = self.create_shield_group()

        strategy_dict = get_strategy_dict(group.id)
        self.alert_info["extra_info"].update(strategy=strategy_dict)

        alert_doc = AlertDocument(**self.alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert_doc]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert_doc))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=strategy_dict.pop("notice_action_config", {})),
        )

        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()
        alert_doc.strategy_id = strategy_dict["id"]
        alert = Alert(data=alert_doc.to_dict())
        ShieldStatusChecker(alerts=[alert]).check_all()
        # 告警屏蔽的状态下创建了通知，因为屏蔽，实际上仅创建了主任务
        actions0 = create_actions(1, "abnormal", alerts=[alert_doc])
        self.assertEqual(len(actions0), 1)
        self.assertTrue(alert.data["is_shielded"])

        settings.GLOBAL_SHIELD_ENABLED = False
        create_actions_mock = patch("alarm_backends.service.fta_action.tasks.create_actions.delay", return_value=1)
        create_actions_mock.start()
        # 解除屏蔽之后，应该创建一个新的通知任务
        checker = ShieldStatusChecker(alerts=[alert])
        checker.check_all()
        self.assertFalse(alert.data["is_shielded"])
        self.assertEqual(ActionInstance.objects.filter(id__in=actions0, need_poll=False).count(), 1)

        self.assertEqual(alert.cycle_handle_record["1"]["execute_times"], 2)
        ActionInstance.objects.filter(id__in=actions0).delete()
        unshielded_actions = create_actions(**checker.unshielded_actions[0])

        # 四个通知方式，产生了5个子任务
        self.assertEqual(len(unshielded_actions), 6)
        parent_action = ActionInstance.objects.get(is_parent_action=True, id__in=unshielded_actions)
        self.assertTrue(parent_action.inputs["is_unshielded"])
        print(parent_action.get_content())
        self.assertTrue("解除屏蔽" in parent_action.get_content()["text"])

        mget_alert_patch.stop()
        get_alert_patch.stop()
        action_config_patch.stop()
        create_actions_mock.stop()

    def test_create_no_action_of_unshielded(self):
        """
        测试通知屏蔽
        :return:
        """

        group = self.create_shield_group()

        strategy_dict = get_strategy_dict(group.id)
        self.alert_info["extra_info"].update(strategy=strategy_dict)

        alert_doc = AlertDocument(**self.alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert_doc]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert_doc))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=strategy_dict.pop("notice_action_config", {})),
        )

        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()
        alert_doc.strategy_id = strategy_dict["id"]
        alert = Alert(data=alert_doc.to_dict())
        actions0 = create_actions(1, "abnormal", alerts=[alert_doc])
        # 告警出发的时候进行了异常通知告警
        ActionInstance.objects.filter(id__in=actions0, is_parent_action=True).update(need_poll=True)
        self.assertEqual(len(actions0), 6)

        settings.GLOBAL_SHIELD_ENABLED = True
        # 进行告警屏蔽
        ShieldStatusChecker(alerts=[alert]).check_all()
        self.assertTrue(alert.data["is_shielded"])

        settings.GLOBAL_SHIELD_ENABLED = False

        # 解除屏蔽之后，检测上一次周期任务
        patch("alarm_backends.service.fta_action.tasks.create_actions.delay", return_value=1).start()
        checker = ShieldStatusChecker(alerts=[alert])
        checker.check_all()
        self.assertFalse(alert.data["is_shielded"])
        # 上一次通知正常发送，所以不会创建对应的屏蔽任务
        self.assertEqual(len(checker.unshielded_actions), 0)
        # 数据保持不变
        self.assertEqual(alert.cycle_handle_record["1"]["execute_times"], 1)
        self.assertEqual(ActionInstance.objects.filter(id__in=actions0, need_poll=True).count(), 1)

        mget_alert_patch.stop()
        get_alert_patch.stop()
        action_config_patch.stop()

    def test_create_no_action_of_recovering_unshielded(self):
        """
        测试恢复周期内不进行解除屏蔽通知
        :return:
        """

        group = self.create_shield_group()

        strategy_dict = get_strategy_dict(group.id)
        self.alert_info["extra_info"].update(strategy=strategy_dict)

        alert_doc = AlertDocument(**self.alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert_doc]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert_doc))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=strategy_dict.pop("notice_action_config", {})),
        )

        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()
        settings.GLOBAL_SHIELD_ENABLED = True
        alert_doc.strategy_id = strategy_dict["id"]
        alert = Alert(data=alert_doc.to_dict())
        actions0 = create_actions(1, "abnormal", alerts=[alert_doc])
        ActionInstance.objects.filter(id__in=actions0, is_parent_action=True).update(need_poll=True)
        self.assertEqual(len(actions0), 1)
        ShieldStatusChecker(alerts=[alert]).check_all()
        self.assertTrue(alert.data["is_shielded"])
        patch("alarm_backends.service.fta_action.tasks.create_actions.delay", return_value=1).start()
        settings.GLOBAL_SHIELD_ENABLED = False
        alert.update_extra_info("is_recovering", True)
        # 在恢复期内进行屏蔽检测，需要忽略屏蔽通知的发送
        checker = ShieldStatusChecker(alerts=[alert])
        checker.check_all()
        self.assertFalse(alert.data["is_shielded"])
        self.assertTrue(alert.data["extra_info"]["ignore_unshield_notice"])
        self.assertEqual(ActionInstance.objects.filter(id__in=actions0, need_poll=True).count(), 1)

        # 伪恢复期内又出现异常点
        alert.update_extra_info("is_recovering", False)
        alert.update_extra_info("need_unshield_notice", True)
        checker = ShieldStatusChecker(alerts=[alert])
        checker.check_all()
        self.assertFalse(alert.data["extra_info"]["need_unshield_notice"])
        mget_alert_patch.stop()
        get_alert_patch.stop()
        action_config_patch.stop()

    def test_message_queue_task(self):
        alert = AlertDocument(**self.alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))
        mget_alert_patch.start()
        get_alert_patch.start()
        action_instance = ActionInstance.objects.create(
            alerts=[alert.id],
            signal="abnormal",
            strategy_id=0,
            alert_level=1,
            bk_biz_id=2,
            dimensions=[],
            action_plugin={"plugin_type": ActionPluginType.MESSAGE_QUEUE},
        )
        settings.ENABLE_MESSAGE_QUEUE = True
        settings.COMPATIBLE_ALARM_FORMAT = False
        settings.MESSAGE_QUEUE_DSN = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0/fta_message_queue"
        processor = MessageQueueActionProcessor(action_id=action_instance.id)
        processor.execute()
        action_instance.refresh_from_db()
        self.assertEqual(action_instance.status, "success")
        alert_from_redis = processor.client.client.brpop(processor.client.key)[1]
        self.assertIsNotNone(alert_from_redis)
        alert_info = processor.context["alarm"].alert_info
        self.assertEqual(alert_from_redis, alert_info)
        settings.ENABLE_MESSAGE_QUEUE = False
        settings.MESSAGE_QUEUE_DSN = ""
        mget_alert_patch.stop()
        get_alert_patch.stop()

    @staticmethod
    def converge_actions(instances, action_type=ConvergeType.ACTION, is_enabled=True, alerts=None):
        for instance in instances:
            converge_config = copy.deepcopy(
                {
                    "is_enabled": is_enabled,
                    "converge_func": "collect",
                    "timedelta": 60,
                    "count": 1,
                    "condition": [
                        {"dimension": "strategy_id", "value": ["self"]},
                        {"dimension": "dimensions", "value": ["self"]},
                        {"dimension": "alert_level", "value": ["self"]},
                        {"dimension": "signal", "value": ["self"]},
                        {"dimension": "bk_biz_id", "value": ["self"]},
                        {"dimension": "notice_receiver", "value": ["self"]},
                        {"dimension": "notice_way", "value": ["self"]},
                        {"dimension": "notice_info", "value": ["self"]},
                    ],
                    "need_biz_converge": True,
                    "sub_converge_config": {
                        "timedelta": 60,
                        "count": 2,
                        "condition": [
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                        ],
                        "converge_func": "collect_alarm",
                    },
                }
            )
            if action_type == ConvergeType.CONVERGE:
                converge_config = copy.deepcopy(
                    {
                        "timedelta": 60,
                        "count": 2,
                        "is_enabled": is_enabled,
                        "condition": [
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                        ],
                        "converge_func": "collect_alarm",
                    }
                )
            cp = ConvergeProcessor(converge_config, instance.id, action_type, alerts=alerts)
            cp.converge_alarm()
            print("$%s converge status " % instance.id, cp.status)

    def test_timeout_action(self):
        before_twenty_minutes = datetime.now(tz=timezone.utc) - timedelta(minutes=20)
        action_config = {"execute_config": {"timeout": 0 * 10 * 60}}
        for i in range(0, 5):
            action_config = {"execute_config": {"timeout": i * 10 * 60}}
            ActionInstance.objects.create(
                signal=ActionSignal.ABNORMAL,
                strategy_id=0,
                alerts=[],
                alert_level=EventSeverity.REMIND,
                status=ActionStatus.RUNNING,
                bk_biz_id=2,
                inputs={"converge_id": 0},
                action_config=action_config,
                action_config_id=action_config.get("id", 0),
                action_plugin={
                    "plugin_type": ActionPluginType.NOTICE,
                    "name": "测试超时",
                    "plugin_key": ActionPluginType.NOTICE,
                },
            )
        ActionInstance.objects.all().update(create_time=before_twenty_minutes)
        print("before_twenty_minutes is ", before_twenty_minutes.timestamp())
        time.sleep(2)

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=action_config),
        )
        action_config_patch.start()
        check_timeout_actions()
        action_config_patch.stop()

        self.assertEqual(ActionInstance.objects.filter(status=ActionStatus.RUNNING).count(), 5)

        action_config = {"execute_config": {"timeout": 10 * 60}}
        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=action_config),
        )
        action_config_patch.start()
        check_timeout_actions()
        action_config_patch.stop()

        self.assertEqual(
            ActionInstance.objects.filter(status=ActionStatus.FAILURE, failure_type=FailureType.TIMEOUT).count(), 5
        )

    def test_webhook_render(self):
        content = json.dumps(
            {
                "ip": "{{target.host.bk_host_innerip}}",
                "source_type": "MONITOR",
                "alarm_type": "{{alarm.callback_message}}",
                "content": "{{alarm.description}}",
                "source_time": "{{alarm.begin_time}}",
                "cc_biz_id": "{{target.business.bk_biz_id}}",
            }
        )
        template_detail = {
            "template_detail": {
                "need_poll": False,
                "notify_interval": 120,
                "interval_notify_mode": "standard",
                "method": "POST",
                "url": "http:",
                "headers": [],
                "authorize": {"auth_type": "none", "auth_config": {}},
                "body": {"data_type": "raw", "params": [], "content": content, "content_type": "json"},
                "query_params": [],
                "failed_retry": {"is_enabled": True, "timeout": 600, "max_retry_times": 2, "retry_interval": 2},
            },
            "timeout": 600,
        }
        action_config = {
            "name": "test",
            "plugin_id": 2,
            "bk_biz_id": 2,
            "desc": "",
            "execute_config": template_detail,
            "is_builtin": False,
        }
        ac = ActionConfig.objects.create(**action_config)

        ai = ActionInstance.objects.create(
            action_config=action_config, action_config_id=ac.id, signal="demo", strategy_id=0, action_plugin={"id": 2}
        )
        wp = WebhookProcessor(action_id=ai.id)
        self.assertTrue(isinstance(json.loads(wp.data), dict))

        template_detail["template_detail"]["body"]["content"] = "not json field"
        ai_str = ActionInstance.objects.create(
            action_config=action_config, action_config_id=ac.id, signal="demo", strategy_id=0, action_plugin={"id": 2}
        )
        wp_str = WebhookProcessor(action_id=ai_str.id)
        with self.assertRaises(JSONDecodeError):
            json.loads(wp_str.data)

    def test_create_action_by_strategy_with_no_duty(self):
        """
        通过策略创建处理
        :return:
        """

        duty_arranges = [
            {
                "users": [
                    {"id": "admin", "display_name": "admin", "logo": "", "type": "user"},
                    {"id": "operator", "display_name": "主机负责人", "logo": "", "type": "group"},
                ],
            },
            {
                "users": [{"id": "lisa", "display_name": "管理员", "logo": "", "type": "user"}],
            },
        ]
        group = UserGroup.objects.create(**self.user_group_data)
        group.need_duty = False
        group.save()
        for duty in duty_arranges:
            duty.update({"user_group_id": group.id})
            DutyArrange.objects.create(**duty)

        notice_action_config = {
            "execute_config": {
                "template_detail": {
                    "interval_notify_mode": "standard",  # 间隔模式
                    "notify_interval": 7200,  # 通知间隔
                    "template": notice_template(),
                }
            },
            "id": 55555,
            "plugin_id": 1,
            "plugin_type": "notice",
            "is_enabled": True,
            "bk_biz_id": 2,
            "name": "test_notice",
        }
        strategy_dict = {
            "id": 1,
            "type": "monitor",
            "bk_biz_id": 2,
            "scenario": "os",
            "name": "测试新策略",
            "labels": [],
            "is_enabled": True,
            "items": [],
            "detects": [],
            "notice": {  # 通知设置
                "id": 1,
                "config_id": 55555,  # 套餐ID，如果不选套餐请置为0
                "user_groups": [group.id],  # 告警组ID
                "signal": ["abnormal", "recovered"],
                # 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
                "options": {
                    "converge_config": {
                        "is_enabled": True,
                        "converge_func": "collect",
                        "timedelta": 60,
                        "count": 1,
                        "condition": [
                            {"dimension": "strategy_id", "value": ["self"]},
                            {"dimension": "dimensions", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                            {"dimension": "notice_info", "value": ["self"]},
                        ],
                        "need_biz_converge": True,
                        "sub_converge_config": {
                            "timedelta": 60,
                            "count": 2,
                            "condition": [
                                {"dimension": "bk_biz_id", "value": ["self"]},
                                {"dimension": "notice_receiver", "value": ["self"]},
                                {"dimension": "notice_way", "value": ["self"]},
                                {"dimension": "alert_level", "value": ["self"]},
                                {"dimension": "signal", "value": ["self"]},
                            ],
                            "converge_func": "collect_alarm",
                        },
                    },
                    "start_time": "00:00:00",
                    "end_time": "23:59:59",
                },
                "config": notice_action_config["execute_config"]["template_detail"],
            },
            "actions": [],
        }
        self.alert_info["extra_info"].update(strategy=strategy_dict)
        self.alert_info["id"] = "123123123"

        alert = AlertDocument(**self.alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))

        action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=notice_action_config),
        )
        mget_alert_patch.start()
        get_alert_patch.start()
        action_config_patch.start()

        create_actions(1, "abnormal", alerts=[alert])
        self.assertEqual(ActionInstance.objects.filter(is_parent_action=True, action_config_id=55555).count(), 1)
        self.assertEqual(ActionInstance.objects.filter(is_parent_action=False, action_config_id=55555).count(), 9)
        new_voice_action = None
        self.set_notice_cache()
        for action in ActionInstance.objects.filter(is_parent_action=False, action_config_id=55555):
            try:
                n_ap = NoticeActionProcessor(action_id=action.id)
                n_ap.execute()
                if action.inputs["notice_way"] == NoticeWay.VOICE:
                    action.id = None
                    action.status = "converged"
                    action.save()
                    new_voice_action = action
            except BaseException as error:
                print("error info", str(error))

        # 企业微信 3个 短信 3个，语音 1个， 企业微信机器人 2个失败
        self.assertEqual(
            ActionInstance.objects.filter(is_parent_action=False, status="success", action_config_id=55555).count(), 7
        )

        new_voice_ap = NoticeActionProcessor(action_id=new_voice_action.id)
        new_voice_ap.execute()

        new_voice_action.refresh_from_db()
        self.assertEqual(new_voice_action.status, ActionStatus.FAILURE)
        self.assertEqual(new_voice_action.failure_type, FailureType.SYSTEM_ABORT)

        # 没有更新主任务状态了，所以去掉了单元测试

        action_config_patch.stop()
        mget_alert_patch.stop()
        get_alert_patch.stop()


class TestNoiseReduce(TestCase):
    databases = {"monitor_api", "default"}

    def setUp(self):
        redis = fakeredis.FakeRedis(decode_responses=True)
        redis.flushall()

        NOISE_REDUCE_ABNORMAL_KEY.client.flushall()
        self.create_alert_patch = patch("bkmonitor.documents.AlertDocument.bulk_create", MagicMock(return_value=True))
        self.create_alert_patch.start()
        self.create_alert_log_patch = patch("bkmonitor.documents.AlertLog.bulk_create", MagicMock(return_value=True))
        self.create_alert_log_patch.start()
        ActionInstance.objects.all().delete()
        register_builtin_plugins()
        self.alert_info = {
            "id": 1,
            "event": EventDocument(
                **{
                    "bk_biz_id": 2,
                    "ip": "127.0.0.1",
                    "time": int(time.time()),
                    "create_time": int(time.time()),
                    "bk_cloud_id": 0,
                    "id": 123,
                }
            ),
            "dedupe_md5": "68e9f0598d72a4b6de2675d491e5b922",
            "severity": 1,
            "begin_time": int(time.time()),
            "create_time": int(time.time()),
            "latest_time": int(time.time()),
            "first_anomaly_time": int(time.time()),
            "duration": 60,
            "common_dimensions": {},
            "dimensions": [
                AttrDict({"key": "bk_target_ip", "value": "127.0.0.1"}),
                AttrDict({"key": "bk_target_cloud_id", "value": "2"}),
            ],
            "extra_info": {"strategy": {}},
            "status": EventStatus.ABNORMAL,
        }
        notice_action_config = {
            "execute_config": {
                "template_detail": {
                    "interval_notify_mode": "standard",  # 间隔模式
                    "notify_interval": 7200,  # 通知间隔
                    "template": [  # 通知模板配置
                        {
                            "signal": "abnormal",
                        }
                    ],
                }
            },
            "id": 55555,
            "plugin_id": 1,
            "plugin_type": "notice",
            "is_enabled": True,
            "bk_biz_id": 2,
            "name": "test_notice",
        }

        self.action_config_patch = patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=notice_action_config),
        )
        self.action_config_patch.start()

    def tearDown(self) -> None:
        ActionInstance.objects.all().delete()
        self.create_alert_patch.stop()
        self.create_alert_log_patch.stop()

    def test_noise_reduce_init_true(self):
        strategy_dict = copy.deepcopy(STRATEGY_CONFIG_V3)
        self.alert_info["extra_info"].update(strategy=strategy_dict)
        self.alert_info["id"] = "123123123"
        strategy_dict["notice"]["id"] = 1

        alert = AlertDocument(**self.alert_info)
        mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=[alert]))
        get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert))
        mget_alert_patch.start()
        get_alert_patch.start()
        create_actions(1, ActionSignal.ABNORMAL, alerts=[alert])
        self.assertEqual(ActionInstance.objects.all().count(), 1)
        processor = NoiseReduceRecordProcessor(strategy_dict["notice"], ActionSignal.ABNORMAL, 1, alert, "xxx")
        client = processor.redis_client
        self.assertEqual(len(client.zrangebyscore(processor.alert_record_key, 0, int(time.time()))), 1)
        self.assertEqual(len(client.zrangebyscore(processor.abnormal_record_key, 0, int(time.time()))), 1)

        execute_processor = NoiseReduceExecuteProcessor(
            processor.noise_reduce_config, processor.strategy_id, alert.first_anomaly_time, alert.severity
        )
        client.zadd(execute_processor.total_record_key, {"aaaa": alert.first_anomaly_time})
        execute_processor.process()

        self.assertEqual(len(client.zrangebyscore(processor.alert_record_key, 0, int(time.time()))), 0)
        self.assertEqual(len(client.zrangebyscore(processor.abnormal_record_key, 0, int(time.time()))), 0)

        self.assertEqual(ActionInstance.objects.all().count(), 1)

        mget_alert_patch.stop()
        get_alert_patch.stop()

    def test_create_multi_alert_action(self):
        def start_alert_mock(alert_docs):
            mget_alert_patch = patch("bkmonitor.documents.AlertDocument.mget", MagicMock(return_value=alert_docs))
            get_alert_patch = patch("bkmonitor.documents.AlertDocument.get", MagicMock(return_value=alert_docs[0]))
            mget_alert_patch.start()
            get_alert_patch.start()
            return mget_alert_patch, get_alert_patch

        def end_alert_mock(mget_alert_patch, get_alert_patch):
            mget_alert_patch.stop()
            get_alert_patch.stop()

        strategy_dict = copy.deepcopy(STRATEGY_CONFIG_V3)
        timezone = "Asia/Shanghai"
        today_begin = time_tools.datetime2str(datetime.now(tz=pytz.timezone(timezone)), format="%Y-%m-%d 00:00")
        today_end = time_tools.datetime2str(datetime.now(), format="%Y-%m-%d 23:59")

        duty_plans = [
            {
                "duty_rule_id": 1,
                "is_effective": 1,
                "start_time": time_tools.datetime2str(datetime.now(tz=pytz.timezone(timezone))),
                "finished_time": time_tools.datetime2str(datetime.now(tz=pytz.timezone(timezone)) + timedelta(hours=1)),
                "work_times": [{'start_time': today_begin, 'end_time': today_end}],
                "order": 1,
                "users": [{"id": "admin", "display_name": "admin", "logo": "", "type": "user"}],
            }
        ]
        user_group_data = {
            "name": "蓝鲸业务的告警组-全职通知组",
            "desc": "用户组的说明用户组的说明用户组的说明用户组的说明用户组的说明",
            "bk_biz_id": 2,
            "need_duty": True,
            "duty_rules": [1],
            "alert_notice": [  # 告警通知配置
                {
                    "time_range": "00:00:00--23:59:59",  # 生效时间段
                    "notify_config": [  # 通知方式配置
                        {
                            "level": 3,  # 级别
                            "type": [  # 通知渠道列表
                                "mail",
                                "weixin",
                                "voice",
                            ],
                        },
                        {"level": 2, "type": ["mail", "voice"]},
                        {"level": 1, "type": ["mail", "weixin", "voice"]},
                    ],
                }
            ],
            "timezone": "Asia/Shanghai",
            "action_notice": [  # 执行通知配置
                {
                    "time_range": "00:00:00--23:59:59",  # 生效时间段
                    "notify_config": [  # 通知方式
                        {"phase": 3, "type": ["mail", "weixin", "voice"]},  # 执行阶段，3-执行前，2-成功时，1-失败时
                        {"phase": 2, "type": ["mail", "weixin", "voice"]},
                        {"phase": 1, "type": ["mail", "weixin", "voice", "wxwork-bot"]},
                    ],
                }
            ],
        }

        duty_plans = copy.deepcopy(duty_plans)
        group = UserGroup.objects.create(**user_group_data)
        for duty in duty_plans:
            duty.update({"user_group_id": group.id})
            DutyPlan.objects.create(**duty)
        strategy_dict["notice"]["user_groups"] = [group.id]

        self.alert_info["extra_info"].update(strategy=strategy_dict)
        self.alert_info["id"] = "123123123"
        strategy_dict["notice"]["id"] = 1
        alert = AlertDocument(**self.alert_info)
        new_alert = AlertDocument(**(copy.deepcopy(self.alert_info)))
        new_alert.id = "newalertid"
        mget, get = start_alert_mock([alert])
        create_actions(1, ActionSignal.ABNORMAL, alerts=[alert])
        end_alert_mock(mget, get)

        mget, get = start_alert_mock([new_alert])
        create_actions(1, ActionSignal.ABNORMAL, alerts=[new_alert])
        end_alert_mock(mget, get)

        mget, get = start_alert_mock([alert, new_alert])

        processor = NoiseReduceRecordProcessor(strategy_dict["notice"], ActionSignal.ABNORMAL, 1, new_alert, "xxx")
        # 两个告警
        self.assertEqual(len(processor.redis_client.zrangebyscore(processor.alert_record_key, 0, int(time.time()))), 2)
        execute_processor = NoiseReduceExecuteProcessor(
            processor.noise_reduce_config, processor.strategy_id, alert.first_anomaly_time, alert.severity
        )
        processor.redis_client.zadd(
            execute_processor.total_record_key, {"aaaa": alert.first_anomaly_time, "bbb": alert.first_anomaly_time}
        )

        execute_processor.process()

        self.assertEqual(ActionInstance.objects.filter(is_parent_action=True).count(), 2)
        self.assertEqual(
            set(ActionInstance.objects.filter(is_parent_action=True).values_list("status", flat=True)),
            {ActionStatus.RECEIVED},
        )
        self.assertEqual(
            set(ActionInstance.objects.filter(is_parent_action=True).values_list("dimension_hash", flat=True)), {""}
        )

        # 每波三个子通知，一共6个
        self.assertEqual(ActionInstance.objects.filter(is_parent_action=False).count(), 6)

        converge_actions(ActionInstance.objects.filter(is_parent_action=False))

        # 两个语音通知不参与收敛流程，直接设置状态为CONVERGED

        self.assertEqual(
            ActionInstance.objects.filter(status=ActionStatus.CONVERGED, is_parent_action=False).count(), 4
        )

        self.assertEqual(ActionInstance.objects.filter(status=ActionStatus.SKIPPED, is_parent_action=False).count(), 2)
        # 收敛的处理，默认执行次数会+1
        self.assertEqual(
            ActionInstance.objects.filter(status=ActionStatus.SKIPPED, is_parent_action=False).first().execute_times, 1
        )

        for action in ActionInstance.objects.filter(status=ActionStatus.CONVERGED, is_parent_action=False):
            np = NoticeActionProcessor(action_id=action.id)
            np.execute()

        end_alert_mock(mget, get)
