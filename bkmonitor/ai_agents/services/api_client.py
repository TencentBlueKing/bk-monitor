"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkapi_client_core.django_helper import _get_client_by_settings
from bkapi_client_core.django_helper import get_client_by_request as _get_client_by_request
from bkapi_client_core.django_helper import get_client_by_username as _get_client_by_username
from bkapi_client_core.utils import generic_type_partial as _partial

from aidev_agent.api.base import ApiProtocol
from aidev_agent.api.bkaidev_client.client import Client
from django.conf import settings

AIDEV_APIGW_ENDPOINT = settings.AIDEV_APIGW_ENDPOINT


class AidevApiClientBuilder(ApiProtocol):
    @classmethod
    def get_client(cls, bk_app_code=settings.APP_CODE, bk_app_secret=settings.SECRET_KEY) -> Client:
        # 现阶段 暂未支持一个大的app_code下管理多个子智能体,因此需要基于不同的智能体code去获取
        return _get_client_by_settings(
            Client, endpoint=AIDEV_APIGW_ENDPOINT, bk_app_code=bk_app_code, bk_app_secret=bk_app_secret
        )

    @classmethod
    def get_client_by_request(cls, request):
        return _partial(Client, _get_client_by_request)(request, endpoint=AIDEV_APIGW_ENDPOINT)

    @classmethod
    def get_client_by_username(cls, username):
        return _partial(Client, _get_client_by_username)(username, endpoint=AIDEV_APIGW_ENDPOINT)
