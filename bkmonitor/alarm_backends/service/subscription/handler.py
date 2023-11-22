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


class BaseSubscriptionProcessor(object):
    """
    基础订阅处理器
    """

    def __init__(
        self,
    ):
        """
        获取对应订阅配置
        """
        pass

    def fetch_subscribers(self):
        """
        获取订阅者列表，解析用户组
        """
        pass

    def parse_frequency(self):
        """
        解析订阅发送频率
        """
        pass

    def send_email(self):
        pass

    def send_wxbot(self):
        pass

    def render(self):
        """
        渲染邮件订阅内容
        """
        pass


class ClusteringSubscriptionProcessor(BaseSubscriptionProcessor):
    """
    日志聚类订阅处理器
    """

    def render(self):
        """
        渲染邮件订阅内容
        """
        pass


class SceneSubscriptionProcessor(BaseSubscriptionProcessor):
    """
    观测场景订阅处理器
    """

    def render(self):
        """
        渲染邮件订阅内容
        """
        pass


class DashboardSubscriptionProcessor(BaseSubscriptionProcessor):
    """
    仪表盘订阅处理器
    """

    def render(self):
        """
        渲染邮件订阅内容
        """
        pass
