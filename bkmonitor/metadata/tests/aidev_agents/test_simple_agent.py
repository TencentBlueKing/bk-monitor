#!/usr/bin/env python3
"""
最简化的AI Agent工具测试
单轮对话，带工具调用，返回完整回答数据
"""

import json
from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.core.extend.models.llm_gateway import ChatModel
from aidev_agent.services.chat import ChatCompletionAgent, ExecuteKwargs
from aidev_agent.services.pydantic_models import ChatPrompt
from django.conf import settings


def _collect_complete_answer(agent):
    """收集完整的回答数据"""
    thinking_content = ""
    answer_content = ""

    for chunk in agent.execute(ExecuteKwargs(stream=True)):
        # 跳过非数据行
        if not chunk.startswith("data: "):
            continue

        # 跳过结束标记
        if chunk.strip() == "data: [DONE]":
            break

        try:
            # 解析JSON数据
            json_str = chunk[6:].strip()  # 移除 "data: " 前缀
            data = json.loads(json_str)

            event_type = data.get("event", "")
            content = data.get("content", "")

            # 收集不同类型的内容
            if event_type == "think":
                thinking_content += content
            elif event_type == "text":
                answer_content += content

        except json.JSONDecodeError:
            continue
        except Exception:  # pylint: disable=broad-except
            continue

    return {
        "thinking": thinking_content.strip(),
        "answer": answer_content.strip(),
        "full_response": answer_content.strip(),  # 主要回答内容
    }


def test_simple_agent():
    """简单的Agent工具测试"""

    # 1. 初始化模型和客户端
    llm_model_name = settings.AIDEV_LLM_MODEL_NAME
    llm = ChatModel.get_setup_instance(model=llm_model_name)
    client = BKAidevApi.get_client()

    # 2. 获取工具（工具注册在AIDEV平台）
    tool_code_list = settings.AIDEV_METADATA_TOOL_CODE_LIST
    tools = [client.construct_tool(tool_code) for tool_code in tool_code_list]

    # 3. 构建简单的对话历史（用户提问）
    user_question = "请帮我分析123456的链路情况"

    with open("metadata/agents/prompts/diagnostic.md", encoding="utf-8") as f:
        prompt = f.read()

    chat_history = [ChatPrompt(role="system", content=prompt), ChatPrompt(role="user", content=user_question)]

    # 4. 创建Agent实例
    agent = ChatCompletionAgent(
        chat_model=llm,
        chat_history=chat_history,
        tools=tools,
    )

    result = _collect_complete_answer(agent)
    print(result)
