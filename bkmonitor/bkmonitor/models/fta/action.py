"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import inspect
import json
import logging
import time
from collections import defaultdict
from datetime import datetime
from importlib import import_module
from typing import Any

import jmespath
from django.conf import settings
from django.db import models
from django.utils.translation import gettext as _

from bkmonitor.documents import AlertLog
from bkmonitor.utils.db import JsonField
from bkmonitor.utils.model_manager import AbstractRecordModel, ModelManager
from bkmonitor.utils.template import Jinja2Renderer
from constants.action import (
    ACTION_DISPLAY_STATUS_DICT,
    ACTION_STATUS_CHOICES,
    CONVERGE_FUNC_CHOICES,
    FAILURE_TYPE_CHOICES,
    NOTIFY_DESC,
    STATUS_NOTIFY_DICT,
    ActionNoticeType,
    ActionPluginType,
    ActionSignal,
    ActionStatus,
    ConvergeStatus,
    ConvergeType,
    NoticeWay,
    UserGroupType,
    VoiceNoticeMode,
)
from constants.alert import EVENT_SEVERITY, EventSeverity
from core.errors.api import BKAPIError

logger = logging.getLogger(__name__)


def default_list():
    return []


def default_dict():
    return {}


class ActionPlugin(AbstractRecordModel):
    """
    响应动作插件表定义
    """

    plugin_type = models.CharField(
        "插件类型",
        choices=(
            ("notice", "通知"),
            ("webhook", "HTTP回调"),
            ("job", "作业平台"),
            ("sops", "标准运维"),
            ("itsm", "流程服务"),
            ("common", "通用插件"),
        ),
        max_length=64,
        null=False,
    )

    plugin_key = models.CharField(
        "插件key, 一个唯一的确定值",
        choices=(
            ("notice", "通知"),
            ("webhook", "HTTP回调"),
            ("job", "作业平台"),
            ("sops", "标准运维"),
            ("itsm", "流程服务"),
            ("common", "通用插件"),
        ),
        max_length=64,
        default="common",
        null=False,
    )
    name = models.CharField("插件名称", max_length=64, null=False)
    description = models.TextField("详细描述，markdown文本", default="", blank=True)
    is_builtin = models.BooleanField("是否内置", default=False)
    is_peripheral = models.BooleanField("是否周边系统", default=False)
    plugin_source = models.CharField(
        "插件来源",
        choices=(
            ("builtin", "内置"),
            ("peripheral", "周边系统"),
            ("bk_plugin", "蓝鲸插件"),
        ),
        max_length=64,
        default="builtin",
        null=False,
    )
    has_child = models.BooleanField("是否有子级联", default=False)
    category = models.CharField("插件分类", max_length=64, null=False)
    # 事件执行分类：回调类，轮询类，直调 需要放到这里吗？
    config_schema: dict[str, Any] = JsonField("参数配置格式")  # type: ignore
    """
    比如标准运维：
    返回前端的样例
    {"template":{
          "formItemProps": {
            "label": "选择模版",
            "required": True,
            "property": "ALARM_MOBILE_URL",
            "help_text": "请选择标准运维的模版"
            },
          "type": "select",
          "key": "template_id",
          "value": "",
          "formChildProps": {
            "placeholder": "",
          },
          "rules": [{required: true, message: "必填项", trigger: "blur"}],
          "data"{
          "type":"api",
          "url": "{site_url}/fta/get_template_list/",
          # 向远端请求的url
          "properties":{
                "key": "template_id",
                # 名称
                "name": "template_name",
                # 跳转链接
                "refer_url":"template_url" }
          "remote":{
                "url":"xxx", // 远端请求url
                "properties":{
                } // 远端请求的属性配置
          }
        },
    "detail":{
            "key"："detail",
            "name": "模版参数配置"
            "url"：/o/bk_sops/get_template_detail/{templates.template_id}
            "type": "form"
        }
    }
    // 后台交互配置
    """
    backend_config = JsonField("后台执行格式")
    """
    轮询类：
    {
        "create": {"url": "xxx",
        "method": "GET",
        "data":json.dumps({"task_id": {{task_id}}})
        ""
        },
        "execute": {"url": "xxx",
        "method": "GET",
        "data":json.dumps({"task_id": {{task_id}}})
        },
        "schedule":{
        "url": "xxx",
        "method": "GET",
        "data":json.dumps({"task_id": {{task_id}}}),
        "interval": 1
        }
    }
    回调类: 需提供一个回调接口
    {
        "execute": {"url": "xxx",
        "method": "GET",
        "data":json.dumps({"task_id": {{task_id}}})
        }
        "callback_url":"xxx"
    }
    """

    class Meta:
        verbose_name = "响应动作插件"
        verbose_name_plural = "响应动作插件"
        db_table = "action_plugin"

    PUBLIC_PARAMS = {
        "bk_paas_inner_host": settings.BK_COMPONENT_API_URL.rstrip("/"),
        "bk_paas_host": settings.BK_PAAS_HOST.rstrip("/"),
        "job_site_url": settings.JOB_URL.rstrip("/"),
        "sops_site_url": settings.BK_SOPS_HOST.rstrip("/"),
        "itsm_site_url": settings.BK_ITSM_HOST.rstrip("/"),
        "itsm_v4_site_url": settings.BK_ITSM_V4_HOST.rstrip("/"),
        "itsm_v4_api_url": settings.BK_ITSM_V4_API_URL.rstrip("/"),
        "itsm_v4_system_id": settings.BK_ITSM_V4_SYSTEM_ID,
        "incident_saas_site_url": settings.BK_INCIDENT_SAAS_HOST.rstrip("/"),  # 故障分析SaaS URL
    }

    @staticmethod
    def get_request_data(data_mapping, validate_request_data):
        validate_request_data.update(ActionPlugin.PUBLIC_PARAMS)
        return json.loads(Jinja2Renderer.render(json.dumps(data_mapping), validate_request_data))

    def perform_resource_request(self, req_type, **kwargs) -> list:
        request_schema: dict[str, Any] = self.config_schema[req_type]

        try:
            resource_module = import_module(request_schema.get("resource_module", ""))
        except ImportError as err:
            logger.exception(err)
            return []

        source_class = request_schema["resource_class"]
        if not hasattr(resource_module, source_class):
            return []

        request_class = getattr(resource_module, source_class)
        kwargs.update(self.get_request_data(request_schema.get("request_data_mapping", {}), kwargs))
        data = {"response": request_class(**request_schema.get("init_kwargs", {})).request(**kwargs)}

        data = jmespath.search(request_schema["resource_data"], data) or []
        data = data if isinstance(data, list) else [data]
        mapping = request_schema["mapping"]
        rsp_data = []

        for item in data:
            # 遍历所有内容
            item.update(self.PUBLIC_PARAMS)
            rsp_data.append({key: Jinja2Renderer.render(value, item) for key, value in mapping.items()})
        return rsp_data

    def get_plugin_template_create_url(self, **kwargs):
        """
        获取周边系统的url请求
        :param kwargs:请求参数
        :return:创建url
        """
        url_schema = self.config_schema.get("plugin_url")
        if not url_schema:
            return {"url": "", "tips": ""}

        if url_schema.get("resource_class"):
            try:
                url_info = self.perform_resource_request("plugin_url", **kwargs)
            except BKAPIError as error:
                logger.warning(f"failed to get_plugin_template_create_url: {error}")
                url_info = None
            url_info = url_info[0] if url_info else {}
        else:
            kwargs.update(self.PUBLIC_PARAMS)
            url_info = {key: Jinja2Renderer.render(value, kwargs) for key, value in url_schema["mapping"].items()}

        return url_info


class ActionConfig(AbstractRecordModel):
    NOTICE_PLUGIN_ID = 1

    is_builtin = models.BooleanField("是否内置", default=False)
    name = models.CharField("套餐名称", max_length=128, null=False)
    desc = models.TextField("套餐描述", default="")
    bk_biz_id = models.CharField("业务ID", max_length=64, null=False)
    plugin_id = models.CharField("插件ID", max_length=64, null=False)
    execute_config = JsonField("执行任务参数配置")

    app = models.CharField("所属应用", max_length=128, default="", blank=True, null=True)
    path = models.CharField("资源路径", max_length=128, default="", blank=True, null=True)
    hash = models.CharField("原始配置摘要", max_length=64, default="", blank=True, null=True)
    snippet = models.TextField("配置片段", default="", blank=True, null=True)

    class Meta:
        verbose_name = "自愈套餐"
        verbose_name_plural = "自愈套餐"
        db_table = "action_config"
        ordering = ("-update_time", "-id")


class ActionInstance(AbstractRecordModel):
    """任务执行模块"""

    id = models.BigAutoField("主键", primary_key=True)

    signal = models.CharField(
        "触发信号",
        choices=ActionSignal.ACTION_SIGNAL_CHOICE,
        max_length=64,
        null=False,
        help_text="触发该事件的告警信号，如告警异常，告警恢复，告警关闭等",
    )
    strategy_id = models.IntegerField("策略ID", null=False)
    strategy = JsonField("策略快照", null=False, default={})
    strategy_relation_id = models.IntegerField("策略关联关系", default=0)
    dimensions = JsonField("关联的维度信息", null=False, default=[])
    dimension_hash = models.CharField("匹配策略的维度哈希", max_length=64, default="")
    # alerts 目前可能只会有一个，以后可能有多个，所以以后考虑可以用mysql的jsonfield
    alerts = JsonField("关联的告警", null=False, default=[])
    alert_level = models.IntegerField("告警级别", choices=EVENT_SEVERITY, default=EventSeverity.REMIND)

    status = models.CharField("执行状态", choices=ACTION_STATUS_CHOICES, max_length=64, default=ActionStatus.RECEIVED)
    failure_type = models.CharField(
        "失败类型", choices=FAILURE_TYPE_CHOICES, max_length=64, help_text="失败的时候标志失败类型", null=True
    )
    ex_data = JsonField("执行异常信息", default={})

    create_time = models.DateTimeField("创建时间", auto_now_add=True, blank=True)
    end_time = models.DateTimeField("结束时间", blank=True, null=True)

    update_time = models.DateTimeField("最后修改时间", auto_now=True, blank=True)
    # 记录action的执行内容
    action_plugin = JsonField("事件对应的插件信息", default={})
    action_config = JsonField("关联配置信息的快照", default={})
    action_config_id = models.IntegerField("关联配置信息ID", null=False, default=0)
    bk_biz_id = models.CharField("业务ID", max_length=64)

    # 任务需要拆分的，需要将子任务添加到DB中，当存在子任务的时候，父任务不做任务处理，子任务都完成的时候，父任务也完成
    is_parent_action = models.BooleanField("是否为主任务", default=False, db_index=True)
    parent_action_id = models.BigIntegerField("父任务ID", default=0)
    sub_actions = JsonField("子任务ID", default=[])

    assignee = JsonField("负责人", default=[])
    inputs = JsonField("任务的输入参数", default={}, help_text="譬如发送人，执行人等")
    outputs = JsonField("任务的输出参数", default={})
    real_status = models.CharField("真实执行状态", choices=ACTION_STATUS_CHOICES, max_length=64, default="")

    is_polled = models.BooleanField("是否已经创建周期任务", default=False)
    need_poll = models.BooleanField(
        "是否需要创建周期任务",
        default=False,
        db_index=True,
    )
    execute_times = models.IntegerField("执行次数", default=0)
    generate_uuid = models.CharField("创建批次", max_length=32, db_index=True, default="")

    objects = models.Manager()

    class Meta:
        verbose_name = "自愈执行动作"
        verbose_name_plural = "自愈执行动作"
        db_table = "action_instance"
        index_together = (("create_time", "status"), ("create_time", "signal"), ("status", "signal", "update_time"))

    def get_context(self):
        """
        获取上下文输入参数
        :return:
        """
        if self.signal == ActionSignal.COLLECT:
            return {key: value[0] if isinstance(value, list) else value for key, value in self.inputs.items()}
        return self.inputs

    def create_sub_actions(self, need_create=True):
        """
        创建通知子任务
        :return:
        """
        # 分别创建负责人和关注人通知
        sub_actions = self.batch_create_sub_actions() + self.batch_create_sub_actions(followed=True)
        if sub_actions and need_create:
            ActionInstance.objects.bulk_create(sub_actions)
        logger.info("create sub notice actions %s for parent action %s", len(sub_actions), self.id)
        return sub_actions

    def batch_create_sub_actions(self, followed=False):
        """
        根据notify分批次实现
        """
        notify_info = self.inputs.get("notify_info", {})
        if followed:
            # 如果是关注人通知，则用follower的配置
            notify_info = self.inputs.get("follow_notify_info", {})
        sub_actions = []
        exclude_notice_ways = self.inputs.get("exclude_notice_ways", [])
        mention_users_list = notify_info.pop("wxbot_mention_users", [])
        wxbot_mention_users = defaultdict(list)
        for mention_users_dict in mention_users_list:
            for chat_id, users in mention_users_dict.items():
                wxbot_mention_users[chat_id].extend(users)
        wxbot_mention_users = {chat_id: set(users) for chat_id, users in wxbot_mention_users.items()}
        for notice_way, notice_receivers in notify_info.items():
            if notice_way in exclude_notice_ways:
                # 当前的通知方式被排除，不创建对应的具体通知
                continue
            if notice_way == NoticeWay.VOICE:
                # 判断通知模式
                voice_notice_mode = self.inputs.get("voice_notice_mode", VoiceNoticeMode.PARALLEL)
                if voice_notice_mode == VoiceNoticeMode.SERIAL:
                    # 串行通知，将通知人员列表的列表 合并为一个通知人员列表 为单个列表(并去重)创建子任务
                    # [["user1", "user2"], ["user3", "user2"]] -> [["user1", "user2", "user3"]]
                    combined = [user for sublist in notice_receivers if isinstance(sublist, list) for user in sublist]
                    if combined:
                        notice_receivers = [list(dict.fromkeys(combined))]
                    else:
                        # 如果合并后没有有效用户，记录日志并跳过语音通知
                        logger.warning(
                            f"[create_sub_actions] action({self.id}) alerts({self.alerts}) "
                            f"no valid users found after merging, notice_receivers: {notice_receivers}"
                        )
                        continue

            for notice_receiver in notice_receivers:
                if not notice_receiver:
                    continue
                sub_actions.append(
                    self.create_sub_notice_action(notice_way, notice_receiver, wxbot_mention_users, followed)
                )
        return sub_actions

    def create_sub_notice_action(self, notice_way, notice_receiver, mention_users=None, followed=False):
        """
        创建一个处理套餐
        :param notice_way:通知方式
        :param notice_receiver:接收人员
        :param mention_users:提醒人员
        :return:
        """
        inputs = {
            "notice_way": notice_way,
            "notice_receiver": notice_receiver,
            "mention_users": mention_users,
            "followed": followed,
        }
        inputs.update(self.inputs)
        sub_action = ActionInstance(inputs=inputs, parent_action_id=self.id, is_parent_action=False)
        for field, value in self.__dict__.items():
            if field in ["id", "_state", "inputs", "parent_action_id", "is_parent_action"]:
                continue
            setattr(sub_action, field, value)
        return sub_action

    @property
    def is_alarm_time(self):
        """
        是否在告警时间内
        :return: bool
        """
        # 如果是通知类型的套餐，在生成处理记录的时候，已经根据当时的时间匹配到对应的通知配置，并存放到 notify_item 字段
        # 所以只需要看 notify_item 这个字段是否为空就可以了

        return bool(self.inputs.get("notify_item"))

    @property
    def name(self):
        return self.action_config.get("name", "demo")

    @property
    def notice_status(self):
        return NOTIFY_DESC.get(STATUS_NOTIFY_DICT.get(self.status))

    @property
    def is_empty_notice(self):
        """
        通知任务是否为空
        :return:
        """
        if not self.is_parent_action:
            return False
        if ActionInstance.objects.filter(generate_uuid=self.generate_uuid, parent_action_id=self.id).exists():
            # 当前主任务存在子任务的情况下，默认为False
            return False
        return True

    @property
    def is_shielded(self):
        """
        主任务是否被屏蔽
        :return:
        """
        if not self.is_parent_action:
            return False
        if self.inputs.get("is_alert_shielded", False):
            # 当前主任务存在子任务的情况下，默认为False
            return True
        return False

    @property
    def is_unshielded(self):
        """
        主任务是否为解除屏蔽通知
        """
        if not self.is_parent_action:
            return False
        if self.inputs.get("is_unshielded", False):
            # 如果为解除屏蔽的条件，则认为是解除屏蔽通知
            return True
        return False

    @property
    def is_upgrade_notice(self):
        """
        主任务是否为解除屏蔽通知
        """
        if not self.is_parent_action:
            return False
        if self.inputs.get("notice_type") == "upgrade":
            # 如果有升级的条件标识，则认为是升级通知
            return True
        return False

    @property
    def is_first_process(self):
        """
        是否为第一次触达告警处理
        1、当前信号为异常或者无数据告警
        2、非周期任务
        3、为普通的处理方式
        """
        return (
            self.signal in [ActionSignal.ABNORMAL, ActionSignal.NO_DATA]
            and self.execute_times == 1
            and self.inputs.get("notice_type") == ActionNoticeType.NORMAL
        )

    def get_content(self, **kwargs):
        content_template = kwargs.pop("content_template", "")
        need_action_link = kwargs.pop("need_action_url", False)
        kwargs.update(self.inputs or {})
        kwargs.update(self.outputs or {})
        # 对于蓝鲸插件类型
        # 如果蓝鲸插件的返回值中存在url，则视为蓝鲸插件执行结束，将此url作为「查看详情」的跳转链接
        # 否则，视为蓝鲸插件未结束或失败，将查询插件执行状态/结果的schedule_url作为「查看详情」的跳转链接
        have_url = True if (kwargs.get("url", "") or kwargs.get("bkplugin_schedule_url", "")) else False
        if have_url and not kwargs.get("url", ""):
            kwargs["url"] = kwargs.get("bkplugin_schedule_url")
        kwargs["status_display"] = kwargs.get("status_display", self.get_status_display())
        kwargs["action_name"] = kwargs.get("action_name", self.name)
        kwargs["action_signal"] = (
            ActionSignal.ACTION_SIGNAL_DICT.get(ActionSignal.UNSHIELDED)
            if self.is_unshielded
            else ActionSignal.ACTION_SIGNAL_DICT.get(self.signal)
        )
        if self.is_upgrade_notice:
            kwargs["action_signal"] = ActionSignal.ACTION_SIGNAL_DICT.get(ActionSignal.UPGRADE)
        action_plugin_type = (
            ActionPluginType.NOTICE if self.signal == ActionSignal.COLLECT else self.action_plugin.get("plugin_type")
        )
        if not content_template:
            config_schema = self.action_plugin.get("config_schema", {})
            content_template = (
                config_schema.get("content_template_with_url", "")
                if have_url or self.is_parent_action
                else config_schema.get("content_template", "")
            )

            if self.is_empty_notice:
                # 当主任务没有任何通知人员的情况下，获取内容模板发生变化
                content_template = config_schema.get("content_template_without_assignee", content_template)

                if self.is_shielded:
                    if self.inputs.get("shield_detail"):
                        content_template = _("达到通知告警的执行条件【{{{{action_signal}}}}】, {}").format(
                            self.inputs["shield_detail"]
                        )
                    else:
                        content_template = config_schema.get("content_template_shielded", content_template)
                    if self.inputs.get("shield_ids"):
                        content_template = config_schema.get("content_template_shielded_with_url", content_template)
                        # 告警屏蔽跳转，路由由前端拼接，忽略 url 参数
                        # ?bizId={biz_id}/#/alarm-shield-detail/{shield_id}
                        kwargs["router_info"] = {
                            "router_name": "alarm-shield-detail",
                            "params": {"biz_id": self.bk_biz_id, "shield_id": self.inputs["shield_ids"][0]},
                        }
                action_plugin_type = ActionPluginType.COMMON

            if need_action_link and have_url is False:
                # 如果需要详情链接，并且当前任务没有第三方链接
                content_template = _("{}点击$查看任务详情$").format(_(content_template))
        if self.status == ActionStatus.WAITING:
            approve_info = self.outputs.get("approve_info")
            if approve_info:
                content_template = _("套餐【{{action_name}}】触发异常防御审批，点击$查看工单详情$")
                kwargs["url"] = "{bk_itsm_host}#/ticket/detail?id={ticket_id}".format(
                    bk_itsm_host=settings.BK_ITSM_HOST, ticket_id=approve_info.get("id")
                )
        content_template = content_template or _("%s执行{{status_display}}") % self.action_config.get(
            "name", _("处理套餐")
        )
        text = Jinja2Renderer.render(content_template, kwargs)

        content = {
            "text": text,
            "action_plugin_type": action_plugin_type,
        }

        if "router_info" in kwargs:
            content["router_info"] = kwargs["router_info"]
        else:
            default_url = settings.ACTION_DETAIL_URL.format(bk_biz_id=self.bk_biz_id, action_id=self.es_action_id)
            content["url"] = kwargs.get("url", default_url)

        return content

    def get_status_display(self):
        """
        获取状态展示内容，失败的时候，需要加上失败原因
        :return:
        """
        status_display = ACTION_DISPLAY_STATUS_DICT.get(self.status, self.notice_status)
        if self.status in [ActionStatus.FAILURE, ActionStatus.SKIPPED]:
            status_display = _("{}，错误信息{}").format(status_display, self.ex_data.get("message", "--"))
        if self.action_plugin["plugin_type"] == ActionPluginType.WEBHOOK and self.status == ActionStatus.SUCCESS:
            status_display = _("{}，返回内容:{}").format(status_display, self.ex_data.get("message", "--"))
        return status_display

    @property
    def es_action_id(self):
        return f"{int(self.create_time.timestamp())}{self.id}"

    def insert_alert_log(self, description=None, content_template="", notice_way_display=""):
        if self.parent_action_id or not self.alerts or self.signal == ActionSignal.COLLECT:
            # 如果为子任务，直接不插入日志记录
            return
        if description is None:
            description = json.dumps(
                self.get_content(
                    **{
                        "notice_way_display": notice_way_display
                        or NoticeWay.NOTICE_WAY_MAPPING.get(self.inputs.get("notice_way"), ""),
                        "status_display": self.get_status_display(),
                        "action_name": self.action_config.get("name", ""),
                        "content_template": content_template,
                        "need_action_url": self.status == ActionStatus.FAILURE,
                    }
                )
            )

        action_log = dict(
            op_type=AlertLog.OpType.ACTION,
            alert_id=self.alerts,
            description=description,
            time=int(time.time()),
            create_time=int(time.time()),
            event_id=self.es_action_id,
        )
        AlertLog.bulk_create([AlertLog(**action_log)])
        logger.info("[fta action] action(%s), alerts(%s): %s", self.id, self.alerts, description)

    @classmethod
    def get_count_group_by_config(cls, bk_biz_id, begin_time: datetime, end_time: datetime = None):
        """
        获取区间内的策略执行次数
        """
        queryset = cls.objects.filter(update_time__gte=begin_time, bk_biz_id=bk_biz_id, parent_action_id=0).exclude(
            signal=ActionSignal.COLLECT
        )
        if end_time:
            queryset = queryset.filter(update_time__gte=end_time)

        return queryset.values("action_config_id").annotate(dcount=models.Count("action_config_id")).order_by("dcount")

    def replay_blocked_notice(self):
        """
        重新发送被熔断的通知

        :return: 重放结果列表，每个元素包含 success 和 error 信息
        """
        retry_params_list = self.ex_data.get("retry_params", [])
        if not retry_params_list:
            logger.warning(f"[replay blocked notice] action({self.id}) no retry_params found")
            return []

        results = []
        for retry_param in retry_params_list:
            api_module_path = retry_param["api_module"]
            resource_name = retry_param["resource"]
            try:
                args = retry_param.get("args", ())
                kwargs = retry_param.get("kwargs", {})

                # 核心逻辑：动态导入模块，获取类或方法，然后调用
                ret = None

                # 方式1：尝试将 api_module_path 作为完整模块路径导入
                # 例如：api_module_path="api.cmsi.default", resource_name="SendVoice"
                try:
                    api_module = import_module(api_module_path)
                    resource = getattr(api_module, resource_name, None)
                    if resource is not None:
                        # 如果是类，实例化后调用；如果是函数，直接调用
                        if inspect.isclass(resource):
                            ret = resource()(*args, **kwargs)
                        else:
                            ret = resource(*args, **kwargs)
                except ImportError:
                    # 导入失败，尝试方式2
                    pass

                # 方式2：如果方式1失败，尝试将最后一个点号后的部分作为类名
                # 例如：api_module_path="bkmonitor.utils.send.Sender", resource_name="send_wxwork_layouts"
                if ret is None and "." in api_module_path:
                    try:
                        module_path, class_name = api_module_path.rsplit(".", 1)
                        api_module = import_module(module_path)
                        api_class = getattr(api_module, class_name, None)
                        if api_class and inspect.isclass(api_class):
                            func = getattr(api_class, resource_name, None)
                            if func is not None:
                                # 尝试直接通过类调用（类方法/静态方法）
                                try:
                                    ret = func(*args, **kwargs)
                                except TypeError:
                                    # 如果是实例方法，需要先实例化
                                    ret = getattr(api_class(), resource_name)(*args, **kwargs)
                    except (ImportError, AttributeError, TypeError):
                        pass

                if ret is None:
                    raise ImportError(f"Cannot import module or class: {api_module_path}")

                logger.info(
                    f"[replay blocked notice] action({self.id}) strategy({self.strategy_id}) "
                    f"replay success: {api_module_path}.{resource_name}, result: {ret}"
                )
                results.append({"success": True, "result": ret, "api": f"{api_module_path}.{resource_name}"})
            except Exception as e:
                logger.exception(
                    f"[replay blocked notice] action({self.id}) strategy({self.strategy_id}) "
                    f"replay failed: {api_module_path}.{resource_name}, error: {e}"
                )
                results.append({"success": False, "error": str(e), "api": f"{api_module_path}.{resource_name}"})

        return results


class ActionInstanceLog(models.Model):
    """
    告警的处理 log 表
    用来记录处理步骤

    INFO 级别以上的会在界面展示
    DEBUG 级别及以下的信息用作内部数据
    """

    LEVEL_CHOICES = (
        (0, "NOT_SET"),
        (10, "DEBUG"),
        (20, "INFO"),
        (30, "WARNING"),
        (40, "ERROR"),
        (50, "CRITICAL"),
    )
    id = models.BigAutoField("主键", primary_key=True)
    action_instance_id = models.IntegerField(null=False, blank=False, db_index=True)
    content = models.TextField("步骤记录")
    time = models.DateTimeField("备注时间", auto_now=True)
    step_name = models.CharField("步骤名", max_length=32, default=None, null=True)
    level = models.SmallIntegerField(
        "信息等级", choices=LEVEL_CHOICES, help_text="同python logging level定义", default=None, null=True
    )

    @property
    def action_instance(self):
        if self.action_instance_id:
            return ActionInstance.objects.get(id=self.action_instance_id)

    class Meta:
        verbose_name = "自愈执行动作日志"
        verbose_name_plural = "自愈执行动作日志"
        db_table = "action_instance_log"


class ConvergeInstance(AbstractRecordModel):
    CONVERGE_TYPE_COLORS = (
        ("network-attack", "success"),
        ("network-quality", "success"),
        ("host-quality", "success"),
        ("analyze", "success"),
        ("collect_alarm", "success"),
        ("defence", "danger"),
        ("convergence", "primary"),  # 优先显示主告警的状态
    )

    NOTIFY_STATUSES = (
        ("sent", _("已发送")),
        ("new", _("尚未发送")),
        ("", _("无内容")),
    )

    id = models.BigAutoField("主键", primary_key=True)

    is_visible = models.BooleanField("是否可见", default=True)
    converge_config = JsonField()
    converge_func = models.CharField(
        "收敛事件类型", choices=CONVERGE_FUNC_CHOICES, max_length=128, null=True, blank=True, db_index=True
    )
    converge_type = models.CharField(
        null=False,
        blank=False,
        db_index=True,
        max_length=64,
        choices=[("converge", "收敛事件"), ("action", "处理事件")],
    )

    bk_biz_id = models.IntegerField("业务编码", db_index=True)
    dimension = models.CharField("收敛维度", max_length=128, unique=True, db_index=True)
    description = models.TextField("描述")
    content = models.TextField("内容")
    detail = models.TextField("详情", blank=True, null=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True, blank=True, db_index=True)
    end_time = models.DateTimeField("事件结束时间", blank=True, null=True)
    notify_status = models.CharField("消息提醒状态", blank=True, null=True, choices=NOTIFY_STATUSES, max_length=4)

    objects = models.Manager()

    def converged_actions(self):
        """
        获取当前收敛对应的所有action
        :return:
        """
        related_ids = [inst.related_id for inst in ConvergeRelation.objects.filter(converge_id=self.id)]
        if self.converge_type == "converge":
            # 仅支持两层收敛，所以最多再获取一次处理事件信息
            # 已经结束的收敛事件，不再发送通知
            converge_ids = [
                item.id for item in ConvergeInstance.objects.filter(id__in=related_ids) if item.is_visible is False
            ]
            related_ids = ConvergeRelation.objects.filter(
                converge_id__in=converge_ids, related_type="action"
            ).values_list("related_id", flat=True)
        return ActionInstance.objects.filter(id__in=set(related_ids))

    @property
    def description_display(self):
        if not self.description:
            return self.description
        return _(self.description)

    def get_context(self):
        return self.converge_config.get("converged_condition", {})

    class Meta:
        verbose_name = "自愈收敛动作"
        verbose_name_plural = "自愈收敛动作"
        db_table = "converge_instance"
        ordering = ("-id",)


class ConvergeRelation(models.Model):
    """
    Converge 的 many_to_many 关联
    """

    id = models.BigAutoField("主键", primary_key=True)
    converge_id = models.BigIntegerField(null=False, blank=False, db_index=True)
    related_id = models.BigIntegerField(null=False, blank=False, db_index=True)
    related_type = models.CharField(
        null=False,
        blank=False,
        db_index=True,
        max_length=64,
        choices=[(ConvergeType.CONVERGE, _("收敛事件")), (ConvergeType.ACTION, _("处理事件"))],
    )
    is_primary = models.BooleanField("主要告警", default=False)
    converge_status = models.CharField(
        "收敛状态", choices=ConvergeStatus.CHOICES, max_length=32, default=ConvergeStatus.SKIPPED
    )
    alerts = JsonField("防御的告警列表", default=[])

    objects = ModelManager()

    class Meta:
        unique_together = ("converge_id", "related_id", "related_type")
        verbose_name = "自愈收敛关联表"
        verbose_name_plural = "自愈收敛关联表"
        db_table = "converge_relation"

    @property
    def converge_instance(self):
        """
        关联到Incident的快速写法
        :return QuerySet: Incident
        """
        if self.converge_id:
            return ConvergeInstance.objects.get(id=self.converge_id)

    @property
    def relate_instance(self):
        """
        关联到AlarmInstance的快速写法
        :return QuerySet: AlarmInstance
        """
        if not self.related_id:
            return None
        if self.related_type == "action":
            return ActionInstance.objects.get(id=self.related_id)
        return ConvergeInstance.objects.get(id=self.related_id)

    def __unicode__(self):
        return f"Inc-{self.converge_id} | relate_instance-{self.relate_instance.id}({self.relate_instance})"


class StrategyActionConfigRelation(AbstractRecordModel):
    """
    策略响应动作配置关联表
    """

    class RelateType:
        NOTICE = "NOTICE"
        ACTION = "ACTION"

    RELATE_TYPE_CHOICES = (
        (RelateType.NOTICE, _("通知")),
        (RelateType.ACTION, _("处理动作")),
    )

    strategy_id = models.IntegerField("故障自愈的策略ID", null=False, db_index=True)
    config_id = models.IntegerField("响应动作配置ID", null=False, db_index=True)
    relate_type = models.CharField("关联类型", max_length=32, choices=RELATE_TYPE_CHOICES, default=RelateType.NOTICE)
    signal = models.JSONField("触发信号", default=default_list)
    user_groups = models.JSONField("用户组", default=default_list)
    user_type = models.CharField("人员类型", default=UserGroupType.MAIN, choices=UserGroupType.CHOICE, max_length=32)
    options = models.JSONField("高级设置", default=default_dict)

    class Meta:
        verbose_name = "策略响应动作配置关联表"
        verbose_name_plural = "策略响应动作配置关联表"
        db_table = "strategy_action_relation"

    @property
    def validated_user_groups(self):
        return [group_id for group_id in self.user_groups if group_id]
