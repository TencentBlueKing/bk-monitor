"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from django.conf import settings
from django.http import StreamingHttpResponse, JsonResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ai_agent.core.aidev_interface import AIDevInterface
from ai_agent.services.metrics_reporter import AIMetricsReporter
from apps.ai_assistant import metrics
from apps.ai_assistant.handlers.chat import ChatHandler
from apps.ai_assistant.serializers import (
    ChatSerializer,
    CreateChatSessionSerializer,
    UpdateChatSessionSerializer,
    CreateChatCompletionSerializer,
    CreateChatSessionContentSerializer,
    UpdateChatSessionContentSerializer,
    GetChatSessionContentsSerializer,
    BatchDeleteSessionContentSerializer,
    CreateFeedbackSessionContentSerializer,
    GetFeedbackReasonsSessionContentSerializer,
)
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import AI_ASSISTANT
from apps.generic import APIViewSet
from apps.iam.handlers.drf import ViewBusinessPermission


# Create your views here.


class AIAssistantViewSet(APIViewSet):
    def get_permissions(self):
        return [ViewBusinessPermission()]

    @action(methods=["post"], detail=False)
    def chat(self, request, *args, **kwargs):
        """
        @api {POST} /ai_assistant/chat/ AI 聊天
        @apiName AIAssistantChat
        @apiGroup AIAssistant
        @apiDescription AI 聊天

        @apiParam {String} space_uid 空间ID，必填。
        @apiParam {Integer} index_set_id 索引集ID，必填。
        @apiParam {Object} log_data 日志内容，必填。
        @apiParam {Object} query 当前聊天输入内容，必填。
        @apiParam {Object[]} [chat_context] 聊天上下文，可选，默认为空列表。
        @apiParam {String} chat_context.role 角色，必填，可选值为 "user" 或 "assistant"。
        @apiParam {String} chat_context.content 内容，必填。
        @apiParam {String} type 聊天类型，必填。可选值为 "log_interpretation"
        """
        data = self.params_valid(ChatSerializer)

        # 如果没有配置 AIDEV 接口地址，则直接返回错误
        if not FeatureToggleObject.switch(name=AI_ASSISTANT, biz_id=data["bk_biz_id"]):
            return Response({"error": "assistant is not configured"}, status=status.HTTP_501_NOT_IMPLEMENTED)

        result_or_stream = ChatHandler().interpret_log(
            index_set_id=data["index_set_id"],
            log_data=data["log_data"],
            query=data["query"],
            chat_context=data["chat_context"],
            stream=data["stream"],
        )

        if data["stream"]:
            resp = StreamingHttpResponse(result_or_stream, content_type="text/event-stream; charset=utf-8")
            resp.headers["Cache-Control"] = "no-cache"
            resp.headers["X-Accel-Buffering"] = "no"
        else:
            resp = Response(result_or_stream)
        return resp


# 定义指标上报器
metrics_reporter = AIMetricsReporter(
    requests_total=metrics.AI_AGENTS_REQUESTS_TOTAL, requests_cost=metrics.AI_AGENTS_REQUESTS_COST_SECONDS
)

# 定义接口类实例
aidev_interface = AIDevInterface(
    app_code=settings.BK_AIDEV_AGENT_APP_CODE,
    app_secret=settings.BK_AIDEV_AGENT_APP_SECRET,
    metrics_reporter=metrics_reporter,
)


class AIAssistantPermissionMixin:
    """业务权限控制Mixin"""

    def get_permissions(self):
        return [ViewBusinessPermission()]


class AgentInfoViewSet(APIViewSet, AIAssistantPermissionMixin):
    """
    Agent信息管理
    """

    @action(methods=["GET"], detail=False)
    def info(self, request, *args, **kwargs):
        """
        @api {get} /ai_assistant/agent/info
        @apiName get_agent_info
        @apiDescription 获取Agent信息，当前只支持获取默认智能体信息
        @apiGroup AIAssistant

        """
        return JsonResponse(aidev_interface.get_agent_info(agent_code=settings.BK_AIDEV_AGENT_APP_CODE))


class ChatSessionViewSet(APIViewSet, AIAssistantPermissionMixin):
    """
    会话管理
    """

    lookup_field = "session_code"

    def list(self, request, *args, **kwargs):
        """
        @api {get} /ai_assistant/session
        @apiName list_session
        @apiDescription 获取当前用户会话列表
        @apiGroup AIAssistant

        """
        return JsonResponse(aidev_interface.list_chat_sessions(username=request.user.username))

    def create(self, request, *args, **kwargs):
        """
        @api {post} /ai_assistant/session
        @apiName create_session
        @apiDescription 创建会话
        @apiGroup AIAssistant

        """
        params = self.params_valid(CreateChatSessionSerializer)
        return JsonResponse(aidev_interface.create_chat_session(params=params, username=request.user.username))

    def update(self, request, *args, **kwargs):
        """
        @api {put} /ai_assistant/session
        @apiName update_session
        @apiDescription 更新会话
        @apiGroup AIAssistant

        """
        params = self.params_valid(UpdateChatSessionSerializer)
        return JsonResponse(aidev_interface.update_chat_session(session_code=kwargs["session_code"], params=params))

    def retrieve(self, request, *args, **kwargs):
        """
        @api {get} /ai_assistant/session/{session_code}
        @apiName retrieve_session
        @apiDescription 获取单个会话信息
        @apiGroup AIAssistant

        """
        return JsonResponse(aidev_interface.retrieve_chat_session(session_code=kwargs["session_code"]))

    def destroy(self, request, *args, **kwargs):
        """
        @api {delete} /ai_assistant/session/{session_code}
        @apiName destroy_session
        @apiDescription 删除会话
        @apiGroup AIAssistant

        """
        return JsonResponse(aidev_interface.destroy_chat_session(session_code=kwargs["session_code"]))

    @action(methods=["post"], detail=True)
    def ai_rename(self, request, *args, **kwargs):
        """
        @api {get} /ai_assistant/session/{session_code}/ai_rename
        @apiName rename_session
        @apiDescription AI 智能总结会话标题
        @apiGroup AIAssistant

        """
        return JsonResponse(aidev_interface.rename_chat_session(session_code=kwargs["session_code"]))


class ChatSessionContentViewSet(APIViewSet, AIAssistantPermissionMixin):
    """
    会话内容管理
    """

    @action(methods=["get"], detail=False)
    def content(self, request, *args, **kwargs):
        """
        @api {get} /ai_assistant/session_content/content
        @apiName list_session_content
        @apiDescription AI 获取会话内容
        @apiGroup AIAssistant

        """
        params = self.params_valid(GetChatSessionContentsSerializer)
        return JsonResponse(aidev_interface.get_chat_session_contents(session_code=params["session_code"]))

    def create(self, request, *args, **kwargs):
        """
        @api {post} /ai_assistant/session_content
        @apiName create_session_content
        @apiDescription 创建会话内容
        @apiGroup AIAssistant

        """
        params = self.params_valid(CreateChatSessionContentSerializer)
        return JsonResponse(aidev_interface.create_chat_session_content(params=params))

    def update(self, request, *args, **kwargs):
        """
        @api {put} /ai_assistant/session_content
        @apiName update_session_content
        @apiDescription 更新单条会话内容
        @apiGroup AIAssistant

        """
        params = self.params_valid(UpdateChatSessionContentSerializer)
        return JsonResponse(aidev_interface.update_chat_session_content(params=params))

    def destroy(self, request, *args, **kwargs):
        """
        @api {delete} /ai_assistant/session_content/{content_id}
        @apiName destroy_session_content
        @apiDescription 删除单条会话内容
        @apiGroup AIAssistant

        """
        return JsonResponse(aidev_interface.destroy_chat_session_content(id=kwargs["pk"]))

    @action(methods=["post"], detail=False)
    def batch_delete(self, request, *args, **kwargs):
        """
        @api {post} /ai_assistant/session_content/batch_delete
        @apiName batch_delete_session_content
        @apiDescription 批量删除会话内容
        @apiGroup AIAssistant

        """
        params = self.params_valid(BatchDeleteSessionContentSerializer)
        return JsonResponse(aidev_interface.batch_delete_session_contents(params=params))


class SessionFeedbackViewSet(APIViewSet, AIAssistantPermissionMixin):
    """
    会话内容反馈
    """

    def create(self, request, *args, **kwargs):
        """
        @api {post} /ai_assistant/session_feedback
        @apiName create_feedback_session_content
        @apiDescription 创建会话内容反馈
        @apiGroup AIAssistant

        """
        params = self.params_valid(CreateFeedbackSessionContentSerializer)
        return JsonResponse(aidev_interface.create_chat_session_feedback(params=params, username=request.user.username))

    @action(methods=["get"], detail=False)
    def reasons(self, request, *args, **kwargs):
        """
        @api {get} /ai_assistant/session_feedback/reasons
        @apiName get_feedback_reasons_session_content
        @apiDescription 获取反馈原因列表
        @apiGroup AIAssistant
        """
        params = self.params_valid(GetFeedbackReasonsSessionContentSerializer)
        return JsonResponse(aidev_interface.get_feedback_reasons(params=params))


class ChatCompletionViewSet(APIViewSet, AIAssistantPermissionMixin):
    """
    流式会话
    """

    def create(self, request, *args, **kwargs):
        """
        @api {post} /ai_assistant/chat_completion
        @apiName create_chat_completion
        @apiDescription 创建流式会话
        @apiGroup AIAssistant
        """
        params = self.params_valid(CreateChatCompletionSerializer)
        execute_kwargs = params["execute_kwargs"]

        result_or_stream = aidev_interface.create_chat_completion(
            session_code=params["session_code"],
            execute_kwargs=params["execute_kwargs"],
            agent_code=params["agent_code"],
            username=request.user.username,
        )
        if execute_kwargs.get("stream", False):
            return result_or_stream
        else:
            return JsonResponse(result_or_stream)
