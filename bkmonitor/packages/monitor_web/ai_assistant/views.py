"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import requests
from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response


class ChatSerializer(serializers.Serializer):
    session_id = serializers.CharField(required=False, allow_blank=True, default="")
    input = serializers.CharField(required=True, allow_blank=False)


class ChatViewSet(viewsets.GenericViewSet):
    @action(methods=['post'], detail=False, url_path='chat')
    def chat(self, request, *args, **kwargs):
        # 如果没有配置 AI 接口地址，则直接返回错误
        if not settings.BK_MONITOR_AI_API_URL:
            return Response({'error': 'AI assistant is not configured'}, status=status.HTTP_501_NOT_IMPLEMENTED)

        serializer = ChatSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        url = f"{settings.BK_MONITOR_AI_API_URL}/api/chat/"

        try:
            response = requests.post(url, json=serializer.validated_data, stream=True)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        def event_stream():
            for line in response.iter_lines(chunk_size=10):
                if not line:
                    continue

                result = line.decode('utf-8') + '\n\n'
                yield result

        # 返回 StreamingHttpResponse
        sr = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        sr.headers["Cache-Control"] = "no-cache"
        sr.headers["X-Accel-Buffering"] = "no"
        return sr
