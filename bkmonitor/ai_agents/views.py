# Create your views here.
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from ai_agents.resources.resources import (
    GetAgentInfoResource,
    CreateChatSessionResource,
    RetrieveChatSessionResource,
    DestroyChatSessionResource,
    UpdateChatSessionContentResource,
    CreateChatSessionContentResource,
    GetChatSessionContentsResource,
    DestroyChatSessionContentResource,
    CreateChatCompletionResource,
)
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class AgentViewSet(ResourceViewSet):
    def get_permissions(self):
        return []

    resource_routes = [ResourceRoute("GET", GetAgentInfoResource, endpoint="info")]


class SessionViewSet(ResourceViewSet):
    def get_permissions(self):
        return []

    resource_routes = [
        ResourceRoute("POST", CreateChatSessionResource),
        ResourceRoute("GET", RetrieveChatSessionResource),
        ResourceRoute("DELETE", DestroyChatSessionResource, pk_field="session_code"),
    ]


class SessionContentViewSet(ResourceViewSet):
    def get_permissions(self):
        return []

    resource_routes = [
        ResourceRoute("POST", CreateChatSessionContentResource),
        ResourceRoute("GET", GetChatSessionContentsResource),
        ResourceRoute("PUT", UpdateChatSessionContentResource, pk_field="session_code"),
        ResourceRoute("DELETE", DestroyChatSessionContentResource, pk_field="id"),
    ]


class ChatCompletionViewSet(ResourceViewSet):
    def get_permissions(self):
        return []

    resource_routes = [ResourceRoute("POST", CreateChatCompletionResource)]
