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
from urllib.parse import urljoin

from django.conf import settings
from django.utils.functional import cached_property
from kubernetes import client


class BcsKubeClient:
    def __init__(self, cluster_id):
        self.cluster_id = cluster_id

    @property
    def auth(self):
        host = urljoin(
            f"{settings.BCS_API_GATEWAY_SCHEMA}://{settings.BCS_API_GATEWAY_HOST}:{settings.BCS_API_GATEWAY_PORT}",
            f"/clusters/{self.cluster_id}",
        )
        return client.Configuration(
            host=host,
            api_key={"authorization": settings.BCS_API_GATEWAY_TOKEN},
            api_key_prefix={"authorization": "Bearer"},
        )

    @cached_property
    def api(self):
        return client.AppsV1Api(client.ApiClient(self.auth))

    @cached_property
    def core_api(self):
        return client.CoreV1Api(client.ApiClient(self.auth))
