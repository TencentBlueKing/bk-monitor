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
import logging
import re
import time
from collections import defaultdict

from django.conf import settings
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from bkmonitor.documents import AlertDocument
from bkmonitor.models import ConvergeInstance, ConvergeRelation
from bkmonitor.utils.template import Jinja2Renderer, NoticeRowRenderer
from bkmonitor.utils.time_tools import hms_string, strftime_local
from constants.action import (
    ACTION_DISPLAY_STATUS_DICT,
    ActionPluginType,
    ActionStatus,
    ConvergeStatus,
    ConvergeType,
)

from . import BaseContextObject
from .utils import get_notice_display_mapping

logger = logging.getLogger("fta_action.run")
link_re = re.compile(r"\$\s*[\w\|]+\s*\$")


class ActionInstanceContext(BaseContextObject):
    """
    告警信息对象
    """

    STATUS_COLOR = {ActionStatus.FAILURE: "#EA3636", ActionStatus.SUCCESS: "#34d97b"}

    @cached_property
    def name(self):
        """
        处理套餐名称
        """
        return self.parent.action.name

    @cached_property
    def plugin_type_name(self):
        """
        套餐类型名称
        """
        return self.parent.action.action_plugin["name"]

    @cached_property
    def assignees(self):
        """
        负责人
        :return:
        """
        return ",".join(getattr(self.parent.action, "assignee", []))

    @cached_property
    def operate_target_string(self):
        """
        执行对象:直接用目标IP， 这个不太好确定
        :return:
        """
        if self.parent.action.action_plugin["plugin_type"] == ActionPluginType.NOTICE:
            return get_notice_display_mapping(getattr(self.parent, "notice_way", ""))

        return self.parent.alarm.target_string

    @cached_property
    def start_time(self):
        """
        创建任务时间
        :return:
        """
        return strftime_local(self.parent.action.create_time)

    @cached_property
    def end_time(self):
        """
        任务结束时间
        :return:
        """
        end_time = self.parent.action.end_time
        return strftime_local(end_time) if end_time else "--"

    @cached_property
    def duration(self):
        """
        处理记录的持续时间
        """
        create_timestamp = int(self.parent.action.create_time.timestamp())
        if self.parent.action.end_time:
            # 已经结束的，直接用结束时间来计算
            return int(self.parent.action.end_time.timestamp()) - create_timestamp

        # 否则用当前时间与开始时间来做减法
        return int(time.time()) - create_timestamp

    @cached_property
    def duration_string(self):
        """
        持续时间字符串
        :return:
        """
        return hms_string(self.duration)

    @cached_property
    def status_display(self):
        """
        状态展示
        """
        return ACTION_DISPLAY_STATUS_DICT.get(self.parent.action.status, self.parent.action.status)

    @cached_property
    def status_reason_display(self):
        """
        状态展示
        """
        return ACTION_DISPLAY_STATUS_DICT.get(self.parent.action.status, self.parent.action.status)

    @cached_property
    def opt_content(self):
        """
        处理记录当前的执行内容
        """
        content_obj = self.parent.action.get_content(
            **{
                "status_display": self.parent.action.get_status_display(),
                "action_name": self.parent.action.action_plugin["name"],
            }
        )
        if content_obj.get("url") and not self.parent.is_external_channel:
            # 仅内部渠道支持url查看的内容
            links = link_re.findall(content_obj["text"])
            if links:
                return content_obj["text"].replace(links[0], _("查看详情{}").format(content_obj["url"]))
            return _("{},点击查看详情{}").format(content_obj["text"], content_obj["url"])
        return content_obj["text"]

    @cached_property
    def defensed_alerts(self):
        """
        防御的告警
        :return:
        """
        conv_id = self.converge_id
        if conv_id is None:
            return []
        alerts = []
        for cr in ConvergeRelation.objects.filter(converge_id=conv_id, converge_status=ConvergeStatus.SKIPPED):
            alerts.extend(cr.alerts)
        return AlertDocument.mget(list(set(alerts)))

    @cached_property
    def defensed_alerts_info(self):
        """
        防御的告警信息
        :return:
        """
        return self.parent.get_alerts_dict(self.defensed_alerts)

    @cached_property
    def converge_id(self):
        """
        防御的告警
        :return:
        """
        try:
            return ConvergeRelation.objects.get(
                related_id=self.parent.action.id, related_type=ConvergeType.ACTION
            ).converge_id
        except ConvergeRelation.DoesNotExist:
            return None

    @cached_property
    def converged_description(self):
        """收敛描述"""
        if self.converge_id is None:
            return ""
        try:
            return ConvergeInstance.objects.get(id=self.converge_id).description
        except ConvergeInstance.DoesNotExist:
            return ""

    @cached_property
    def template_detail(self):
        """
        请求参数
        :return:
        """
        try:
            template_detail = self.parent.action.action_config["execute_config"]["template_detail"]
            template_detail = self.jinja_render(template_detail)
        except BaseException:
            template_detail = {}
        return json.dumps(template_detail)

    def jinja_render(self, template_value):
        """
        做jinja渲染
        :param template_value:
        :return:
        """
        if isinstance(template_value, str):
            return Jinja2Renderer.render(template_value, self.parent.get_dictionary())
        if isinstance(template_value, dict):
            render_value = {}
            for key, value in template_value.items():
                render_value[key] = self.jinja_render(value)
            return render_value
        if isinstance(template_value, list):
            return [self.jinja_render(value) for value in template_value]
        return template_value

    @cached_property
    def notice_status_color(self):
        """
        通知状态颜色配置
        :return:
        """
        return self.STATUS_COLOR.get(self.parent.action.status, "#3a84ff")

    @cached_property
    def trigger_alerts(self):
        return AlertDocument.mget(self.parent.action.alerts)

    @cached_property
    def content_template(self):
        return self.parent.DEFAULT_ACTION_TEMPLATE

    @cached_property
    def detail_url(self):
        if self.parent.is_external_channel:
            return None
        return settings.ACTION_DETAIL_URL.format(
            bk_biz_id=self.parent.business.bk_biz_id,
            action_id=self.action_id,
        )

    @cached_property
    def action_id(self):
        """ES存储的处理记录id"""
        return "{}{}".format(int(self.parent.action.create_time.timestamp()), self.parent.action.id)

    @cached_property
    def detail_link(self):
        if self.parent.is_external_channel:
            return None
        return '<a target="_blank" href="{detail_url}">{detail_url}<a>'.format(detail_url=self.detail_url)

    @cached_property
    def opt_content_markdown(self):
        """
        处理记录当前的执行内容
        """
        content_obj = self.parent.action.get_content(
            **{
                "status_display": self.parent.action.get_status_display(),
                "action_name": self.parent.action.action_plugin["name"],
            }
        )
        if content_obj.get("url") and not self.parent.is_external_channel:
            # 仅内部渠道可以展示url的内容
            links = link_re.findall(content_obj["text"])
            if links:
                return content_obj["text"].replace(links[0], _("[查看详情]({})").format(content_obj["url"]))
            return _("{},[点击查看详情]({})").format(content_obj["text"], content_obj["url"])
        return content_obj["text"]


class ActionInstanceContent(ActionInstanceContext):
    Fields = (
        "name",
        "plugin_type_name",
        "assignees",
        "operate_target_string",
        "start_time",
        "end_time",
        "duration_string",
        "status_display",
        "opt_content",
        "detail_link",
    )

    Labels = {
        "name": defaultdict(lambda: _lazy("套餐名称")),
        "plugin_type_name": defaultdict(lambda: _lazy("套餐类型")),
        "assignees": defaultdict(lambda: _lazy("负责人")),
        "operate_target_string": defaultdict(lambda: _lazy("操作对象")),
        "start_time": defaultdict(lambda: _lazy("开始时间")),
        "end_time": defaultdict(lambda: _lazy("结束时间")),
        "duration_string": defaultdict(lambda: _lazy("执行时长")),
        "status_display": defaultdict(lambda: _lazy("执行状态")),
        "opt_content": defaultdict(lambda: _lazy("具体内容")),
        "detail_link": defaultdict(lambda: _lazy("处理链接")),
    }

    def __getattribute__(self, item):
        """
        取值时自动获取相应通知类型的值
        """
        if item in object.__getattribute__(self, "Fields"):
            content_type = getattr(self.parent, "action_notice_way", "mail")
            if content_type in settings.MD_SUPPORTED_NOTICE_WAYS:
                # 所有支持markdown语法的通知方式，默认用markdown格式
                content_type = "markdown"
            if hasattr(self, "{}_{}".format(item, content_type)):
                value = object.__getattribute__(self, "{}_{}".format(item, content_type))
            else:
                value = super(ActionInstanceContent, self).__getattribute__(item)

            if value is None:
                return ""
            else:
                return NoticeRowRenderer.format(content_type, self.Labels[item][content_type], value)

        return super(ActionInstanceContent, self).__getattribute__(item)
