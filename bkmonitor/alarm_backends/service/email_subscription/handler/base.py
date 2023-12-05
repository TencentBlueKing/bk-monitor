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

from alarm_backends.service.email_subscription.utils import send_email, send_wxbot
from bkmonitor.models.email_subscription import (
    ChannelEnum,
    EmailSubscription,
    SendStatusEnum,
    SubscriptionChannel,
    SubscriptionSendRecord,
)
from constants.report import StaffChoice
from core.drf_resource import api


class BaseSubscriptionHandler(object):
    """
    基础订阅管理器
    """

    # 订阅模板路径
    title_template_path = ""
    content_template_path = ""
    # 订阅配置校验类
    serializer_class = None

    def __init__(self, subscription: EmailSubscription):
        """
        初始化对应订阅配置
        """
        self.subscription = subscription
        self.channels = SubscriptionChannel.objects.filter(subscription_id=subscription.id)

    def run(self):
        """
        执行订阅
        """
        # 获取渲染参数
        render_params = self.get_render_params()
        # 渲染订阅内容,获取上下文
        context = self.render(render_params)

        # 根据渠道分别发送，记录最新发送轮次
        # self.subscription.send_round = self.subscription.send_round + 1 if self.subscription.send_round else 1
        # self.subscription.save()
        for channel in self.channels:
            SendChannelHandler(channel).send(context, self.subscription.bk_biz_id)

    def get_render_params(self) -> dict:
        """
        获取渲染参数
        """
        pass

    def render(self, render_params: dict) -> dict:
        """
        渲染订阅
        """
        pass


class SendChannelHandler(object):
    """
    订阅渠道处理器
    """

    send_cls_map = {
        ChannelEnum.USER.value: send_email,
        ChannelEnum.EMAIL.value: send_email,
        ChannelEnum.WXBOT.value: send_wxbot,
    }

    def __init__(self, channel: SubscriptionChannel):
        """
        初始化对应订阅配置
        """
        self.channel = channel
        self.send_cls = self.send_cls_map[channel.channel_name]

    def send(self, context, send_round=1, bk_biz_id=None):
        subscribers = self.fetch_subscribers(bk_biz_id)
        result = self.send_cls(context, subscribers)
        send_time = datetime.datetime.now()
        # 解析发送结果并记录
        send_results = []
        has_failed = False
        has_success = False
        for receiver in result:
            if result[receiver]["result"]:
                has_success = True
            else:
                has_failed = True
            if self.channel.channel_name == ChannelEnum.USER.value:
                send_results.append({"id": receiver, "type": StaffChoice.user, "result": result[receiver]["result"]})
            else:
                send_results.append({"id": receiver, "result": result[receiver]["result"]})

        if not has_failed:
            send_status = SendStatusEnum.SUCCESS.value
        elif not has_success:
            send_status = SendStatusEnum.FAILED.value
        else:
            send_status = SendStatusEnum.PARTIAL_FAILED.value

        send_record = {
            "subscription_id": self.channel.subscription_id,
            "channel_name": self.channel.channel_name,
            "send_results": send_results,
            "send_status": send_status,
            "send_time": send_time,
            # "send_round": send_round
        }
        SubscriptionSendRecord.objects.create(**send_record)

    def fetch_subscribers(self, bk_biz_id=None):
        """
        获取订阅人列表，解析用户组
        """
        subscribers = []
        if self.channel.channel_name != ChannelEnum.USER.value:
            return [subscriber["id"] for subscriber in self.channel.subscribers]
        user_channel = self.channel
        user_subscribers = user_channel.subscribers
        groups_data = api.monitor.group_list(bk_biz_id)
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
        subscribers = list(set(subscribers))
        if "admin" in subscribers:
            subscribers.remove("admin")
        if "system" in subscribers:
            subscribers.remove("system")
        return subscribers
