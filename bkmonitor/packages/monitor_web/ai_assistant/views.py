"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import os

from rest_framework.decorators import action

from ai_agent.scenarios.bkm_chat.views import QAViewSet


class ChatViewSet(QAViewSet):
    # ai小鲸功能迁移至ai agent模块
    @action(methods=['post'], detail=False, url_path='chat_v2')
    def chat_dispatch(self, request, *args, **kwargs):
        if os.getenv("BK_AI_AGENT_ENABLE"):
            return super().ask_v2(request, *args, **kwargs)
        else:
            return super().ask(request, *args, **kwargs)
