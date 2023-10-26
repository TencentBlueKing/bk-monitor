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

from django.core.management.base import BaseCommand

from metadata.models import CustomReportSubscription


class Command(BaseCommand):
    """
    bk-collector自定义上报v2新配置升级后卸除v1旧配置命令
    """

    def handle(self, **kwargs):
        # 针对proxy为手动停用状态的机器卸载proxy v1配置
        CustomReportSubscription.refresh_collector_custom_conf(None, "bkmonitorproxy", "remove")
