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

from django.http import StreamingHttpResponse

from ai_agent.core.qa.agent import StreamingQAAgent

"""
AI小鲸 小助手
"""
import json

from django.conf import settings
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.drf_resource import api
from monitor.models import GlobalConfig


class ChatV2Serializer(serializers.Serializer):
    query = serializers.CharField(required=True, allow_blank=False)
    type = serializers.CharField(required=True, allow_blank=False)
    polish = serializers.BooleanField(required=False, default=True)


class QAViewSet(viewsets.GenericViewSet):
    @action(methods=['get'], detail=False, url_path='join')
    def apply_join(self, request, *args, **kwargs):
        username = request.user.username
        config, is_new = GlobalConfig.objects.get_or_create(key="AI_USER_LIST")
        if is_new:
            config.value = json.dumps([username])
        else:
            ul = json.loads(config.value)
            if username in ul:
                return Response({"result": "already joined!"})
            ul.append(username)
            config.value = json.dumps(ul)
        config.save()
        return Response({"result": "joined!"})

    # @action(methods=['post'], detail=False, url_path='chat')
    def ask(self, request, *args, **kwargs):
        # 如果没有配置 AIDEV 接口地址，则直接返回错误
        if not settings.AIDEV_API_BASE_URL:
            return Response({'error': 'AIDEV assistant is not configured'}, status=status.HTTP_501_NOT_IMPLEMENTED)
        if not settings.AIDEV_KNOWLEDGE_BASE_IDS:
            return Response({'error': 'knowledge base is not configured'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ChatV2Serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = serializer.validated_data
        params.update(
            {
                "knowledge_base_id": settings.AIDEV_KNOWLEDGE_BASE_IDS,
                "stream": True,
            }
        )
        # 切换index_specific
        params.update(
            {
                "type": "index_specific",
                "index_query_kwargs": [
                    {
                        "index_name": "full_text",
                        "index_value": params["query"],
                        "knowledge_base_id": knowledge_base_id,
                    }
                    for knowledge_base_id in settings.AIDEV_KNOWLEDGE_BASE_IDS
                ],
            }
        )
        results = api.aidev.create_knowledgebase_query(params)

        return results

    # @action(methods=['post'], detail=False, url_path='chat_v2')
    def ask_v2(self, request, *args, **kwargs):
        # 带场景的对话
        # 如果没有配置 AIDEV 接口地址，则直接返回错误
        if not settings.AIDEV_API_BASE_URL:
            return Response({'error': 'AIDEV assistant is not configured'}, status=status.HTTP_501_NOT_IMPLEMENTED)
        if not settings.AIDEV_KNOWLEDGE_BASE_IDS:
            return Response({'error': 'knowledge base is not configured'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ChatV2Serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = serializer.validated_data
        query = params['query']

        def event_stream():
            agent = StreamingQAAgent()

            data_field = {"text": "content", "reference_doc": "documents"}
            for chunk in agent.generate_answer(query):
                event_type, data = chunk
                yield "data: " + json.dumps({"event": event_type, data_field[event_type]: data}) + "\n\n"

            yield "data: [DONE]\n\n"

        return StreamingHttpResponse(
            event_stream(), content_type='text/event-stream', headers={'X-Accel-Buffering': 'no'}  # 禁用Nginx缓冲
        )

        # def generate_stream():
        #     try:
        #         # 第一阶段：立即返回知识库检索结果
        #         documents = retrieve.run({"query": params['query'], "k": 5})
        #         yield json.dumps({"event": "reference_doc", "documents": documents}) + "\n"
        #
        #         # 第二阶段：并发处理问答生成
        #         with ThreadPoolExecutor() as executor:
        #             future = executor.submit(answer_with_documents, params['query'], documents)
        #
        #             # 轮询获取处理进度
        #             while not future.done():
        #                 time.sleep(0.1)  # 避免CPU空转
        #                 if future._result:  # 如果有中间结果
        #                     yield json.dumps({"event": "text", "content": future._result}) + "\n"
        #
        #             final_result = future.result()
        #             yield json.dumps({"event": "done", "content": final_result}) + "\n"
        #
        #     except Exception as e:
        #         yield json.dumps({"type": "error", "message": str(e)}) + "\n"
        #
        # # 创建流式响应
        # response = StreamingHttpResponse(
        #     generate_stream(),
        #     content_type='text/event-stream'
        # )
        # response['Cache-Control'] = 'no-cache'
        # return response
        #
        #
        # # documents = retrieve.run({"query": params['query'], "k": 5})
        #
        # # result= answer_with_documents(params['query'], documents)
