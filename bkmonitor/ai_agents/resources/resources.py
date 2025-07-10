"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from aidev_agent.services.chat import ExecuteKwargs
from django.http import StreamingHttpResponse

from ai_agents.services.agent_instance import AgentInstanceBuilder
from ai_agents.services.command_handler import CommandProcessor
from core.drf_resource import Resource
from rest_framework import serializers
from ai_agents.services.api_client import AidevApiClientBuilder
import logging
from django.conf import settings

logger = logging.getLogger("ai_agents")


# -------------------- 会话管理 -------------------- #


class CreateChatSessionResource(Resource):
    """
    创建会话
    """

    class RequestSerializer(serializers.Serializer):
        session_code = serializers.CharField(label="会话代码", required=True)
        session_name = serializers.CharField(label="会话名称", required=True)

        # agent_code = serializers.CharField(label="Agent代码", required=False)

    def perform_request(self, validated_request_data):
        session_code = validated_request_data.get("session_code")
        session_name = validated_request_data.get("session_name")
        logger.info(
            "CreateChatSessionResource: try to create session with session_code->[%s], session_name->[%s]",
            session_code,
            session_name,
        )

        # agent_code = validated_request_data.get("agent_code")

        api_client = AidevApiClientBuilder.get_client(
            bk_app_code=settings.AIDEV_AGENT_APP_CODE, bk_app_secret=settings.AIDEV_AGENT_APP_SECRET
        )
        res = api_client.api.create_chat_session(json=validated_request_data)
        return res


class RetrieveChatSessionResource(Resource):
    """
    获取会话详情
    """

    class RequestSerializer(serializers.Serializer):
        session_code = serializers.CharField(label="会话代码", required=True)

    def perform_request(self, validated_request_data):
        session_code = validated_request_data.get("session_code")

        logger.info("RetrieveChatSessionResource: try to retrieve session with session_code->[%s]", session_code)

        api_client = AidevApiClientBuilder.get_client(
            bk_app_code=settings.AIDEV_AGENT_APP_CODE, bk_app_secret=settings.AIDEV_AGENT_APP_SECRET
        )
        res = api_client.api.retrieve_chat_session(path_params={"session_code": session_code})
        return res


class DestroyChatSessionResource(Resource):
    """
    删除会话
    """

    class RequestSerializer(serializers.Serializer):
        session_code = serializers.CharField(label="会话代码", required=True)

    def perform_request(self, validated_request_data):
        session_code = validated_request_data.get("session_code")

        logger.info("DestroyChatSessionResource: try to destroy session with session_code->[%s]", session_code)

        api_client = AidevApiClientBuilder.get_client(
            bk_app_code=settings.AIDEV_AGENT_APP_CODE, bk_app_secret=settings.AIDEV_AGENT_APP_SECRET
        )
        res = api_client.api.destroy_chat_session(path_params={"session_code": session_code})
        return res


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

    def __init__(self):
        super().__init__()
        self.command_processor = CommandProcessor()

    def perform_request(self, validated_request_data):
        session_code = validated_request_data.get("session_code")
        property_data = validated_request_data.get("property", {})

        logger.info(
            "CreateChatSessionContentResource: try to create content with session_code->[%s],property->[%s]",
            session_code,
            property_data,
        )

        # 快捷指令
        try:
            command_data = property_data.get("extra")
            if command_data.get("command"):
                logger.info("CreateChatSessionContentResource: try to process command->[%s]", command_data)
                processed_content = self.command_processor.process_command(command_data)
                validated_request_data["content"] = processed_content
        except Exception as e:  # pylint: disable=broad-except
            logger.error("CreateChatSessionContentResource: process command error->[%s]", e)

        api_client = AidevApiClientBuilder.get_client(
            bk_app_code=settings.AIDEV_AGENT_APP_CODE, bk_app_secret=settings.AIDEV_AGENT_APP_SECRET
        )
        res = api_client.api.create_chat_session_content(json=validated_request_data)
        return res


class GetChatSessionContentsResource(Resource):
    """
    查询会话内容列表
    """

    class RequestSerializer(serializers.Serializer):
        session_code = serializers.CharField(label="会话代码", required=True)

    def perform_request(self, validated_request_data):
        session_code = validated_request_data.get("session_code")
        logger.info("GetChatSessionContentResource: try to get content with session_code->[%s]", session_code)
        api_client = AidevApiClientBuilder.get_client(
            bk_app_code=settings.AIDEV_AGENT_APP_CODE, bk_app_secret=settings.AIDEV_AGENT_APP_SECRET
        )
        res = api_client.api.get_chat_session_contents(params={"session_code": session_code})

        return res


class DestroyChatSessionContentResource(Resource):
    """
    删除单条会话内容(根据id)
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.CharField(label="内容ID", required=True)

    def perform_request(self, validated_request_data):
        id = validated_request_data.get("id")
        api_client = AidevApiClientBuilder.get_client(
            bk_app_code=settings.AIDEV_AGENT_APP_CODE, bk_app_secret=settings.AIDEV_AGENT_APP_SECRET
        )
        res = api_client.api.destroy_chat_session_content(path_params={"id": id})
        return res


class BatchDeleteSessionContentResource(Resource):
    """
    批量删除对话(根据id列表)
    """

    class RequestSerializer(serializers.Serializer):
        ids = serializers.ListField(label="内容ID列表", required=True)

    def perform_request(self, validated_request_data):
        logger.info(
            "BatchDeleteSessionContentResource: try to batch delete content with params->[%s]", validated_request_data
        )

        api_client = AidevApiClientBuilder.get_client(
            bk_app_code=settings.AIDEV_AGENT_APP_CODE, bk_app_secret=settings.AIDEV_AGENT_APP_SECRET
        )

        res = api_client.api.batch_delete_chat_session_content(json=validated_request_data)
        return res


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

    def perform_request(self, validated_request_data):
        session_code = validated_request_data.get("session_code")
        id = validated_request_data.get("id")
        logger.info("UpdateChatSessionContentResource: try to update content with session_code->[%s]", session_code)
        api_client = AidevApiClientBuilder.get_client(
            bk_app_code=settings.AIDEV_AGENT_APP_CODE, bk_app_secret=settings.AIDEV_AGENT_APP_SECRET
        )
        res = api_client.api.update_chat_session_content(path_params={"id": id}, json=validated_request_data)
        return res


# -------------------- Agent管理 -------------------- #


class GetAgentInfoResource(Resource):
    """
    获取Agent信息
    """

    class RequestSerializer(serializers.Serializer):
        agent_code = serializers.CharField(label="Agent代码", required=False, default=settings.AIDEV_AGENT_APP_CODE)

    def perform_request(self, validated_request_data):
        agent_code = validated_request_data.get("agent_code")
        logger.info("GetAgentInfoResource: try to get agent info with agent_code->[%s]", agent_code)
        api_client = AidevApiClientBuilder.get_client(
            bk_app_code=settings.AIDEV_AGENT_APP_CODE, bk_app_secret=settings.AIDEV_AGENT_APP_SECRET
        )
        res = api_client.api.retrieve_agent_config(path_params={"agent_code": agent_code})
        return res


# -------------------- 对话交互 -------------------- #


class StreamingResponseWrapper:
    """流式响应包装器（在视图层处理）"""

    def __init__(self, generator):
        self.generator = generator

    def as_streaming_response(self):
        """转换为 Django 流式响应"""
        sr = StreamingHttpResponse(self.generator)
        sr.headers["Cache-Control"] = "no-cache"
        sr.headers["X-Accel-Buffering"] = "no"
        sr.headers["content-type"] = "text/event-stream"
        return sr


def _handle_streaming_response(agent_instance, execute_kwargs):
    """处理流式响应"""
    logger.info(f"Starting streaming chat completion with kwargs: {execute_kwargs}")

    # 检查 ExecuteKwargs 解析是否正确
    try:
        validated_kwargs = ExecuteKwargs.model_validate(execute_kwargs)
        logger.info(f"CreateChatCompletionResource: Validated execute_kwargs: {validated_kwargs}")
    except Exception as e:
        logger.error(f"CreateChatCompletionResource: ExecuteKwargs validation failed: {e}")
        raise

    def streaming_generator():
        try:
            for chunk in agent_instance.execute(validated_kwargs):
                logger.info(f"CreateChatCompletionResource: Yielding chunk: {chunk}")
                yield chunk
                logger.info(f"CreateChatCompletionResource: Yielded chunk: {chunk}")
        except Exception as error:
            logger.error(f"CreateChatCompletionResource: Error in streaming generator: {error}")
            raise

    return StreamingResponseWrapper(streaming_generator())


class CreateChatCompletionResource(Resource):
    """
    创建模型对话 流式
    """

    class RequestSerializer(serializers.Serializer):
        session_code = serializers.CharField(label="会话代码", required=True)
        execute_kwargs = serializers.DictField(label="执行参数", required=True)
        agent_code = serializers.CharField(label="Agent代码", required=False, default=settings.AIDEV_AGENT_APP_CODE)

    def perform_request(self, validated_request_data):
        session_code = validated_request_data.get("session_code")
        execute_kwargs = validated_request_data["execute_kwargs"]
        agent_code = validated_request_data.get("agent_code")
        logger.info(
            "CreateChatCompletionResource: try to create chat completion with session_code->[%s], agent_code->[%s]",
            session_code,
            agent_code,
        )

        api_client = AidevApiClientBuilder.get_client(
            bk_app_code=settings.AIDEV_AGENT_APP_CODE, bk_app_secret=settings.AIDEV_AGENT_APP_SECRET
        )

        # 传递默认智能体 agent_code 保持和session的创建者一致
        agent_instance = AgentInstanceBuilder.build_agent_instance_by_session(
            session_code=session_code, api_client=api_client, agent_code=agent_code
        )

        # 根据流式配置执行
        if execute_kwargs.get("stream", False):
            logger.info(
                "CreateChatCompletionResource: stream is true, start streaming,session_code->[%s]", session_code
            )
            streaming_wrapper = _handle_streaming_response(agent_instance, execute_kwargs)
            return streaming_wrapper.as_streaming_response()
        return None
