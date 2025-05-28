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
        except Exception:
            continue

    return {
        "thinking": thinking_content.strip(),
        "answer": answer_content.strip(),
        "full_response": answer_content.strip(),  # 主要回答内容
    }


def test_simple_agent():
    """简单的Agent工具测试"""

    # 1. 初始化模型和客户端
    llm = ChatModel.get_setup_instance(model="hunyuan-turbos")
    client = BKAidevApi.get_client()

    # 2. 获取工具（这里使用NBA工具作为示例）
    tools = [client.construct_tool("nba_game_assistant")]

    # 3. 构建简单的对话历史（用户提问）
    user_question = "how about recent nba games"
    chat_history = [ChatPrompt(role="user", content=user_question)]

    # 4. 创建Agent
    agent = ChatCompletionAgent(
        chat_model=llm,
        chat_history=chat_history,
        tools=tools,
    )

    result = _collect_complete_answer(agent)
    print(result)
