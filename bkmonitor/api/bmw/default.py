# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc

import six
from django.conf import settings

from core.drf_resource.contrib.api import APIResource


class MonitorWorkerAPIGWResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    TIMEOUT = 300
    # 模块名
    module_name = "bkmonitor-worker"

    @property
    def base_url(self):
        stage = "prod" if settings.RUN_MODE == "PRODUCT" else "stag"
        return settings.MONITOR_WORKER_API_BASE_URL or f"{settings.BK_COMPONENT_API_URL}/api/{self.module_name}/{stage}"

    @property
    def label(self):
        return self.__doc__


class CreateTaskResource(MonitorWorkerAPIGWResource):
    """
    创建任务
    """

    action = "/task/"
    method = "POST"


class ReloadDaemonTaskResource(MonitorWorkerAPIGWResource):
    """
    重载常驻任务
    """

    action = "/task/daemon/reload"
    method = "POST"


class ListTaskResource(MonitorWorkerAPIGWResource):
    """
    获取正在运行的任务列表
    """

    action = "/task/"
    method = "GET"
