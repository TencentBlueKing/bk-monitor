"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from ai_whale.utils import get_agent_code_by_scenario_route
from core.drf_resource import Resource
from rest_framework import serializers
import logging
from django.conf import settings
from ai_agent.utils import get_request_username
from ai_agent.core.aidev_interface import AIDevInterface
from ai_agent.services.metrics_reporter import (
    ai_metrics_decorator,
    AIMetricsReporter,
    extract_command_from_request,
    extract_agent_code_from_request,
    ai_enhanced_streaming_metrics,
)
from core.prometheus import metrics

logger = logging.getLogger("ai_whale")

metrics_reporter = AIMetricsReporter(
    requests_total=metrics.AI_AGENTS_REQUESTS_TOTAL, requests_cost=metrics.AI_AGENTS_REQUESTS_COST_SECONDS
)
aidev_interface = AIDevInterface(
    app_code=settings.AIDEV_AGENT_APP_CODE,
    app_secret=settings.AIDEV_AGENT_APP_SECRET,
    metrics_reporter=metrics_reporter,
)


# -------------------- 会话管理 -------------------- #


class CreateChatSessionResource(Resource):
    """
    创建会话
    """

    class RequestSerializer(serializers.Serializer):
        session_code = serializers.CharField(label="会话代码", required=True)
        session_name = serializers.CharField(label="会话名称", required=True)
        agent_code = serializers.CharField(label="Agent代码", required=False, default=settings.AIDEV_AGENT_APP_CODE)

    @ai_metrics_decorator(ai_metrics_reporter=metrics_reporter)
    def perform_request(self, validated_request_data):
        session_code = validated_request_data.get("session_code")
        session_name = validated_request_data.get("session_name")
        username = get_request_username()
        logger.info(
            "CreateChatSessionResource: try to create session with session_code->[%s], session_name->[%s]",
            session_code,
            session_name,
        )
        session_res = aidev_interface.create_chat_session(params=validated_request_data, username=username)
        return session_res


class RetrieveChatSessionResource(Resource):
    """
    获取会话详情
    """

    class RequestSerializer(serializers.Serializer):
        session_code = serializers.CharField(label="会话代码", required=False, default=None)

    @ai_metrics_decorator(ai_metrics_reporter=metrics_reporter)
    def perform_request(self, validated_request_data):
        session_code = validated_request_data.get("session_code", None)
        username = get_request_username()

        logger.info("RetrieveChatSessionResource: try to retrieve session with session_code->[%s]", session_code)

        if session_code:  # 若指定session_code,则拉取单个会话详情
            logger.info("RetrieveChatSessionResource: try to retrieve session with session_code->[%s]", session_code)
            res = aidev_interface.retrieve_chat_session(session_code=session_code)
        else:  # 当前仅支持拉取主Agent的历史会话
            logger.info("RetrieveChatSessionResource: try to list user sessions,username->[%s]", username)
            res = aidev_interface.list_chat_sessions(username=username)
        return res


class DestroyChatSessionResource(Resource):
    """
    删除会话
    """

    class RequestSerializer(serializers.Serializer):
        session_code = serializers.CharField(label="会话代码", required=True)

    @ai_metrics_decorator(ai_metrics_reporter=metrics_reporter)
    def perform_request(self, validated_request_data):
        session_code = validated_request_data.get("session_code")
        logger.info("DestroyChatSessionResource: try to destroy session with session_code->[%s]", session_code)
        return aidev_interface.destroy_chat_session(session_code=session_code)


class UpdateChatSessionResource(Resource):
    """
    修改会话
    """

    class RequestSerializer(serializers.Serializer):
        session_code = serializers.CharField(label="会话代码", required=True)
        session_name = serializers.CharField(label="会话名称", required=False)
        model = serializers.CharField(label="模型名称", required=False)
        role_info = serializers.DictField(label="角色信息", required=False)

    @ai_metrics_decorator(ai_metrics_reporter=metrics_reporter)
    def perform_request(self, validated_request_data):
        session_code = validated_request_data.get("session_code")
        logger.info("UpdateChatSessionResource: try to modify session with session_code->[%s]", session_code)
        return aidev_interface.update_chat_session(session_code=session_code, params=validated_request_data)


class RenameChatSessionResource(Resource):
    """
    AI智能总结会话标题
    """

    class RequestSerializer(serializers.Serializer):
        session_code = serializers.CharField(label="会话代码", required=True)

    @ai_metrics_decorator(ai_metrics_reporter=metrics_reporter)
    def perform_request(self, validated_request_data):
        session_code = validated_request_data.get("session_code")
        logger.info("RenameChatSessionResource: try to rename session->[%s]", session_code)

        if settings.ENABLE_AI_RENAME:
            return aidev_interface.rename_chat_session(session_code=session_code)
        else:
            return aidev_interface.rename_chat_session_by_user_question(session_code=session_code)


# -------------------- 会话内容管理 -------------------- #
class CreateChatSessionContentResource(Resource):
    """
    创建会话内容
    """

    class RequestSerializer(serializers.Serializer):
        session_code = serializers.CharField(label="会话代码", required=True)
        role = serializers.CharField(label="角色", required=True)
        content = serializers.CharField(label="内容", required=True)
        property = serializers.DictField(label="属性", required=False)

    @ai_metrics_decorator(ai_metrics_reporter=metrics_reporter, extract_command_func=extract_command_from_request)
    def perform_request(self, validated_request_data):
        session_code = validated_request_data.get("session_code")
        property_data = validated_request_data.get("property", {})

        role = validated_request_data.get("role")
        if role == "hidden-role":  # TODO: 避免前端二次插入,临时逻辑
            logger.info(
                "CreateChatSessionContentResource: trying to add system prompt,nothing will do,session_code->[%s]",
                session_code,
            )
            return True

        logger.info(
            "CreateChatSessionContentResource: try to create content with session_code->[%s],property->[%s]",
            session_code,
            property_data,
        )
        return aidev_interface.create_chat_session_content(params=validated_request_data)


class GetChatSessionContentsResource(Resource):
    """
    查询会话内容列表
    """

    class RequestSerializer(serializers.Serializer):
        session_code = serializers.CharField(label="会话代码", required=True)

    @ai_metrics_decorator(ai_metrics_reporter=metrics_reporter)
    def perform_request(self, validated_request_data):
        session_code = validated_request_data.get("session_code")
        logger.info("GetChatSessionContentResource: try to get content with session_code->[%s]", session_code)
        return aidev_interface.get_chat_session_contents(session_code=session_code)


class DestroyChatSessionContentResource(Resource):
    """
    删除单条会话内容(根据id)
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.CharField(label="内容ID", required=True)

    @ai_metrics_decorator(ai_metrics_reporter=metrics_reporter)
    def perform_request(self, validated_request_data):
        id = validated_request_data.get("id")
        logger.info("DestroyChatSessionContentResource: try to delete content,id->[%s]", id)
        return aidev_interface.destroy_chat_session_content(id=id)


class BatchDeleteSessionContentResource(Resource):
    """
    批量删除对话(根据id列表)
    """

    class RequestSerializer(serializers.Serializer):
        ids = serializers.ListField(label="内容ID列表", required=True)

    @ai_metrics_decorator(ai_metrics_reporter=metrics_reporter)
    def perform_request(self, validated_request_data):
        logger.info(
            "BatchDeleteSessionContentResource: try to batch delete content with params->[%s]", validated_request_data
        )
        return aidev_interface.batch_delete_session_contents(params=validated_request_data)


class UpdateChatSessionContentResource(Resource):
    """
    更新单条会话内容(根据id)
    """

    class RequestSerializer(serializers.Serializer):
        session_code = serializers.CharField(label="会话代码", required=True)
        id = serializers.CharField(label="内容ID", required=True)
        role = serializers.CharField(label="角色", required=True)
        content = serializers.CharField(label="内容", required=True)
        status = serializers.CharField(label="状态", required=False, default="loading")
        property = serializers.DictField(label="属性", required=False)

    @ai_metrics_decorator(ai_metrics_reporter=metrics_reporter)
    def perform_request(self, validated_request_data):
        session_code = validated_request_data.get("session_code")
        logger.info("UpdateChatSessionContentResource: try to update content with session_code->[%s]", session_code)
        return aidev_interface.update_chat_session_content(params=validated_request_data)


# -------------------- Agent管理 -------------------- #


class GetAgentInfoResource(Resource):
    """
    获取Agent信息
    """

    class RequestSerializer(serializers.Serializer):
        agent_code = serializers.CharField(label="Agent代码", required=False, default=settings.AIDEV_AGENT_APP_CODE)

    @ai_metrics_decorator(ai_metrics_reporter=metrics_reporter, extract_agent_code_func=extract_agent_code_from_request)
    def perform_request(self, validated_request_data):
        agent_code = validated_request_data.get("agent_code")
        logger.info("GetAgentInfoResource: try to get agent info with agent_code->[%s]", agent_code)
        return aidev_interface.get_agent_info(agent_code=agent_code)


# -------------------- 对话交互 -------------------- #


class CreateChatCompletionResource(Resource):
    """
    创建模型对话 流式
    """

    class RequestSerializer(serializers.Serializer):
        session_code = serializers.CharField(label="会话代码", required=True)
        execute_kwargs = serializers.DictField(label="执行参数", required=True)
        agent_code = serializers.CharField(label="Agent代码", required=False, default=settings.AIDEV_AGENT_APP_CODE)

    @ai_enhanced_streaming_metrics(ai_metrics_reporter=metrics_reporter)
    def perform_request(self, validated_request_data):
        session_code = validated_request_data.get("session_code")
        execute_kwargs = validated_request_data["execute_kwargs"]
        username = get_request_username()

        agent_code = get_agent_code_by_scenario_route()
        switch_agent_by_scene = False
        if (
            agent_code != settings.AIDEV_AGENT_APP_CODE
        ):  # 若根据请求场景获取到的Agent Code与默认Agent Code不一致,则切换Agent
            logger.info("CreateChatCompletionResource: scenario route agent code->[%s],switch it", agent_code)
            switch_agent_by_scene = True

        logger.info(
            "CreateChatCompletionResource: try to create chat completion with session_code->[%s], agent_code->[%s]",
            session_code,
            agent_code,
        )
        return aidev_interface.create_chat_completion(
            session_code=session_code,
            execute_kwargs=execute_kwargs,
            agent_code=agent_code,
            username=username,
            temperature=settings.AIDEV_AGENT_LLM_DEFAULT_TEMPERATURE,
            switch_agent_by_scene=switch_agent_by_scene,
        )
