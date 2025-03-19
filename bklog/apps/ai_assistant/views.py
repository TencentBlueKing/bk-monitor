from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.ai_assistant.handlers.chat import ChatHandler
from apps.ai_assistant.serializers import ChatSerializer
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
