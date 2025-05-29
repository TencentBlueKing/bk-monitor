"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from django.conf import settings


def _collect_complete_answer(agent):
    """收集完整的回答数据"""
    thinking_content = ""
    answer_content = ""

    try:
        from aidev_agent.services.chat import ExecuteKwargs
    except ImportError:
        print("MetadataDiagnosisAgent: failed to import AIDEV SDK")
        return None

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


def test_metadata_agent():
    """Metadata 排障Agent测试"""

    try:
        from aidev_agent.api.bk_aidev import BKAidevApi
        from aidev_agent.core.extend.models.llm_gateway import ChatModel
        from aidev_agent.services.chat import ChatCompletionAgent
        from aidev_agent.services.pydantic_models import ChatPrompt
    except ImportError:
        print("MetadataDiagnosisAgent: failed to import AIDEV SDK")

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
