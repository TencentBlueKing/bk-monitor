"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from aidev_agent.core.extend.models.llm_gateway import ChatModel
from aidev_agent.services.chat import ChatCompletionAgent
from aidev_agent.services.pydantic_models import ChatPrompt
from django.conf import settings
from ai_agents.agent_factory import agent_factory
from ai_agents.agent_factory import DEFAULT_AGENT
from ai_agents.models import AgentConfigManager
import logging

logger = logging.getLogger("ai_agents")


class AgentInstanceBuilder:
    @classmethod
    def build_agent_instance_by_session(cls, session_code, api_client, agent_code):
        """
        通过session_code初始化Agent实例
        :param session_code:    会话代码
        :param api_client:      API客户端实例
        :param agent_code:      Agent代码
        """
        logger.info(
            "AgentInstanceBuilder: try to build agent instance for session_code->[%s],use agent->[%s]",
            session_code,
            agent_code,
        )
        session_context_data = api_client.api.get_chat_session_context(path_params={"session_code": session_code}).get(
            "data", []
        )
        logger.info(
            "AgentInstanceBuilder: session->[%s] get session_context_data->[%s]", session_code, session_context_data
        )

        # 是否需要切换智能体
        switch_agent = False

        try:
            # 获取最后一条用户消息
            last_user_message = (
                next((msg for msg in reversed(session_context_data) if msg["role"] == "user"), None) or {}
            )

            command = last_user_message.get("extra", {}).get("command")

            if command:  # 若存在Command，且该Command映射到了新的Agent,那么在本轮对话中使用新的Agent的配置
                command_agent_code = settings.AIDEV_COMMAND_AGENT_MAPPING.get(command, agent_code)
                switch_agent = True if command_agent_code != agent_code else False
                agent_code = command_agent_code  # 切换Agent
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("AgentInstanceBuilder: get last user message error->[%s]", e)

        if session_context_data and session_context_data[-1]["role"] == "assistant":
            logger.info(
                "AgentInstanceBuilder: session->[%s] last message->[%s] is assistant, remove it",
                session_code,
                session_context_data[-1],
            )
            # TODO: 如果最后一条消息是assistant，且content里有"生成中"三个字，则去掉
            content = session_context_data[-1]["content"]
            if settings.AIDEV_AGENT_AI_GENERATING_KEYWORD in content:  # 只要 content 里有"生成中"三个字即可
                session_context_data.pop()

        # 对话历史 chat_history的记录下沉到 build_agent中
        # chat_history = [ChatPrompt.model_validate(each) for each in session_context_data]

        agent = build_chat_completion_agent(
            api_client=api_client,
            agent_code=agent_code,
            session_context_data=session_context_data,
            switch_agent=switch_agent,
        )
        return agent


def build_chat_completion_agent(api_client, agent_code, session_context_data, switch_agent) -> ChatCompletionAgent:
    logger.info("AgentInstanceBuilder: try to build agent instance with agent_code->[%s]", agent_code)
    config = AgentConfigManager.get_config(agent_code=agent_code, api_client=api_client)

    if switch_agent:  # 若需要切换Agent,则在【本轮对话】中替换System Prompt,并不会在平台侧落地
        logger.info("AgentInstanceBuilder: switch agent to->[%s]", agent_code)
        # 找到最后一条role为system的记录并修改
        for item in reversed(session_context_data):
            if item["role"] == "system":
                item["content"] = config.role_prompt
                break  # 修改最后一条后就退出循环

    # 构造对话上下文历史
    chat_history = [ChatPrompt.model_validate(each) for each in session_context_data]

    auth_headers = {
        "bk_app_code": settings.AIDEV_AGENT_APP_CODE,
        "bk_app_secret": settings.AIDEV_AGENT_APP_SECRET,
    }

    llm_base_url = settings.AIDEV_AGENT_LLM_GW_ENDPOINT

    llm = ChatModel.get_setup_instance(
        model=config.llm_model_name,
        base_url=llm_base_url,
        auth_headers=auth_headers,
        temperature=settings.AIDEV_AGENT_LLM_DEFAULT_TEMPERATURE,
    )

    knowledge_bases = [
        api_client.api.appspace_retrieve_knowledgebase(path_params={"id": _id})["data"]
        for _id in config.knowledgebase_ids
    ]
    knowledge_items = [
        api_client.api.appspace_retrieve_knowledge(path_params={"id": _id})["data"] for _id in config.knowledge_ids
    ]
    tools = [api_client.construct_tool(tool_code) for tool_code in config.tool_codes]

    agent_cls = agent_factory.get(DEFAULT_AGENT)

    return ChatCompletionAgent(
        chat_model=llm,
        role_prompt=config.role_prompt,
        tools=tools,
        knowledge_bases=knowledge_bases,
        knowledge_items=knowledge_items,
        chat_history=chat_history,
        agent_cls=agent_cls,
    )
