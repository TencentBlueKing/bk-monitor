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
import datetime
from abc import abstractmethod

from alarm_backends.core.i18n import i18n
from bkmonitor.models.report import (
    ChannelEnum,
    Report,
    ReportChannel,
    ReportSendRecord,
    SendStatusEnum,
)
from bkmonitor.report.utils import send_email, send_wxbot
from constants.new_report import StaffEnum
from constants.report import StaffChoice
from core.drf_resource import api
from core.errors import logger


class BaseReportHandler(object):
    """
    基础订阅管理器
    """

    # 订阅模板路径
    mail_template_path = ""
    wechat_template_path = ""

    def __init__(self, report: Report):
        """
        初始化对应订阅配置
        """
        self.report = report
        self.channels = ReportChannel.objects.filter(report_id=report.id)

    def run(self, channels=None):
        """
        执行订阅
        """
        if not channels:
            channels = self.channels
        # 获取渲染参数
        render_params = self.get_render_params()
        # 渲染订阅内容,获取上下文
        try:
            context = self.render(render_params)
        except Exception as e:
            logger.exception(f"[] failed to send report({self.report.id or self.report.name}), render error: {e}")
            return
        for channel in channels:
            if channel.is_enabled:
                SendChannelHandler(channel).send(context, self.report.send_round, self.report.bk_biz_id)

    @abstractmethod
    def get_render_params(self) -> dict:
        """
        获取渲染参数
        """
        raise NotImplementedError("get_render_params() method is not implemented.")

    @abstractmethod
    def render(self, render_params: dict) -> dict:
        """
        渲染订阅
        """
        raise NotImplementedError("render() method is not implemented.")


class SendChannelHandler(object):
    """
    订阅渠道处理器
    """

    SEND_CLS_MAP = {
        ChannelEnum.USER.value: send_email,
        ChannelEnum.EMAIL.value: send_email,
        ChannelEnum.WXBOT.value: send_wxbot,
    }

    def __init__(self, channel: ReportChannel):
        """
        初始化对应订阅配置
        """
        self.channel = channel
        if not self.SEND_CLS_MAP.get(channel.channel_name):
            raise Exception(f"SEND_CLS_MAP doesn't have channel name: {channel.channel_name}")
        self.send_cls = self.SEND_CLS_MAP[channel.channel_name]

    def send(self, context, send_round, bk_biz_id=None):
        subscribers = self.fetch_subscribers(bk_biz_id)
        if bk_biz_id:
            i18n.set_biz(bk_biz_id)
        # 补充提示词
        if self.channel.send_text:
            context["send_text"] = self.channel.send_text
        result = self.send_cls(context, subscribers)
        if not result:
            logger.exception(
                f"report: {self.channel.report_id} channel: {self.channel.channel_name} send failed,"
                f" send result is null"
            )
            return
        self.update_send_record(result, send_round)

    def update_send_record(self, result, send_round):
        send_time = datetime.datetime.now()
        send_results = []
        # 解析发送结果并记录
        if result.get("errcode", None) is not None:
            send_status = SendStatusEnum.SUCCESS.value if result["errcode"] == 0 else SendStatusEnum.FAILED.value
            send_result = result["errcode"] == 0
            for subscriber in self.channel.subscribers:
                send_results.append({"id": subscriber["id"], "result": send_result})
        else:
            has_failed = False
            has_success = False
            for receiver in result:
                if result[receiver]["result"]:
                    has_success = True
                else:
                    has_failed = True
                if self.channel.channel_name == ChannelEnum.USER.value:
                    send_results.append(
                        {"id": receiver, "type": StaffEnum.USER.value, "result": result[receiver]["result"]}
                    )
                else:
                    send_results.append({"id": receiver, "result": result[receiver]["result"]})

            if not has_failed:
                send_status = SendStatusEnum.SUCCESS.value
            elif not has_success:
                send_status = SendStatusEnum.FAILED.value
            else:
                send_status = SendStatusEnum.PARTIAL_FAILED.value

        send_record = {
            "send_results": send_results,
            "send_status": send_status,
            "send_time": send_time,
        }
        ReportSendRecord.objects.filter(
            report_id=self.channel.report_id, channel_name=self.channel.channel_name, send_round=send_round
        ).update(**send_record)

    def fetch_subscribers(self, bk_biz_id=None):
        """
        获取订阅人列表，解析用户组
        """
        subscribers = []
        if self.channel.channel_name != ChannelEnum.USER.value:
            return [subscriber["id"] for subscriber in self.channel.subscribers]
        user_channel = self.channel
        user_subscribers = user_channel.subscribers
        groups_data = []
        try:
            groups_data = api.monitor.group_list(bk_biz_id=bk_biz_id)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(f"get group list[{bk_biz_id}] error:{e}")
        for user in user_subscribers:
            # 解析用户组
            if user["is_enabled"] and user["type"] == StaffChoice.group:
                for group in groups_data:
                    if user.get("id") == group["id"]:
                        subscribers.extend(group["children"])
            # 解析用户
            if user["type"] == StaffChoice.user:
                if user["is_enabled"]:
                    subscribers.append(user["id"])
                elif user["id"] in subscribers and not user["is_enabled"]:
                    # 如果 is_enabled=False 该用户已取消订阅
                    subscribers.remove(user["id"])
        subscribers = list(set(subscribers) - {"admin", "system"})
        return subscribers
