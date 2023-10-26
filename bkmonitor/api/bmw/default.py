# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2022 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import abc

import six
from core.drf_resource.contrib.api import APIResource
from django.conf import settings


class ApmAPIGWResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    TIMEOUT = 300
    base_url_statement = None

    # 模块名
    module_name = "bkmonitor-worker"

    @property
    def base_url(self):
        return f"{settings.BK_COMPONENT_API_URL}/api/{self.module_name}/prod"

    @property
    def label(self):
        return self.__doc__


class CreateTaskResource(ApmAPIGWResource):
    """
    创建任务
    """

    action = "/task/"
    method = "POST"
