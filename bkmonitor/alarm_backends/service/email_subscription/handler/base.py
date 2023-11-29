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
from bkmonitor.models.email_subscription import EmailSubscription


class BaseSubscriptionHandler(object):
    """
    基础订阅管理器
    """

    # 订阅模板名称
    tpl_name = ""
    # 订阅配置校验类
    serializer_class = None

    def __init__(self, subscription_id):
        """
        初始化对应订阅配置
        """
        self.subscription = EmailSubscription.objects.get(id=subscription_id)

    def fetch_subscribers(self):
        """
        获取订阅人列表，解析用户组
        """
        pass

    def parse_frequency(self):
        """
        解析发送频率
        """
        pass

    def is_run_time(self):
        """
        是否到执行时间
        """
        pass

    def send(self):
        """
        发送订阅
        """
        pass

    def render(self):
        """
        渲染订阅
        """
        pass

    def cancel(self):
        """
        取消订阅
        """
        pass
