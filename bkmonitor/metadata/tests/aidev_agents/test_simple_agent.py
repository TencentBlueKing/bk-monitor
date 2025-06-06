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
import time
import uuid
import pytest
from aidev_agent.packages.langchain.tools.base import Tool, make_structured_tool
from django.conf import settings
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
        except Exception:  # pylint: disable=broad-except
            continue

    return {
        "thinking": thinking_content.strip(),
        "answer": answer_content.strip(),
        "full_response": answer_content.strip(),  # 主要回答内容
    }


def generate_uuid():
    return str(uuid.uuid4())


def test_metadata_agent_with_tools():
    """Metadata 排障Agent测试"""

    # 1. 初始化模型和客户端
    llm_model_name = settings.AIDEV_LLM_MODEL_NAME
    llm = ChatModel.get_setup_instance(model=llm_model_name)
    client = BKAidevApi.get_client()

    # 2. 获取工具（工具注册在AIDEV平台）
    # tool_code_list = settings.AIDEV_METADATA_TOOL_CODE_LIST
    tool_code_list = ["bkm-query-meta"]
    tools = [client.construct_tool(tool_code) for tool_code in tool_code_list]

    tool_settings = {}

    handmake_tools = [make_structured_tool(Tool.model_validate(tool_settings))]

    # 3. 构建简单的对话历史（用户提问）
    user_question = "请帮我分析1575025的链路情况"

    with open("metadata/agents/prompts/diagnostic.md", encoding="utf-8") as f:
        prompt = f.read()

    chat_history = [ChatPrompt(role="system", content=prompt), ChatPrompt(role="user", content=user_question)]

    # 4. 创建Agent实例
    agent = ChatCompletionAgent(
        chat_model=llm,
        chat_history=chat_history,
    )

    result = _collect_complete_answer(agent)
    print(result)


def test_init_agent_with_agent_code():
    client = BKAidevApi.get_client()
    agent_code = "aidev-metadata"
    agent = client.construct_agent(agent_code)
    assert agent


def test_session_management():
    """
    测试Session管理
    """
    client = BKAidevApi.get_client()

    # 生成一个随机的会话ID
    session_code = generate_uuid()

    # 创建一个会话
    create_session_res = client.api.create_chat_session(
        json={"session_code": session_code, "session_name": "ctenetliu-test-20250603"}
    )
    assert create_session_res

    # 获取一个会话
    retrieve_session_res = client.api.retrieve_chat_session(path_params={"session_code": session_code})
    assert retrieve_session_res

    # 创建会话
    create_session_content_res = client.api.create_chat_session_content(
        json={
            "session_code": session_code,
            "role": "user",
            "content": "hello world",
            "status": "success",
        }
    )

    session_content_id = create_session_content_res["data"]["id"]
    assert session_content_id

    # 更新session content
    update_session_content_res = client.api.update_chat_session_content(
        path_params={"id": session_content_id},
        json={
            "session_code": session_code,
            "role": "user",
            "content": "what is python",
            "status": "success",
        },
    )
    assert update_session_content_res

    # 获取session_contents
    get_session_contents_res = client.api.get_chat_session_contents(
        params={"session_code": session_code}
    )
    assert get_session_contents_res

    # 删除会话内容
    delete_session_content_res = client.api.destroy_chat_session_content(path_params={"id": session_content_id})
    assert delete_session_content_res

    result = client.api.get_chat_session_contents(params={"session_code": session_code})
    assert len(result["data"]) == 0

    # 删除会话
    delete_session_res = client.api.destroy_chat_session(path_params={"session_code": session_code})
    assert delete_session_res

    # 预期会404 Error
    with pytest.raises(Exception):
        client.api.retrieve_chat_session(path_params={"session_code": session_code})


def test_agent_chat_with_session():
    client = BKAidevApi.get_client()

    session_code = generate_uuid()

    timestamp = int(time.time())

    create_session_res = client.api.create_chat_session(
        json={"session_code": session_code, "session_name": f"ct-test-{timestamp}"}
    )
    assert create_session_res

    model = create_session_res["data"]["model"]
    llm = ChatModel.get_setup_instance(model=model)

    system_chat_history_list = create_session_res["data"]["role_info"]["content"]

    for system_chat_history in system_chat_history_list:
        create_session_system_res = client.api.create_chat_session_content(
            json={
                "session_code": session_code,
                "role": "role",
                "content": system_chat_history["content"],
                "status": "success",
            }
        )
        assert create_session_system_res

    # 添加session content
    create_session_user_content_res = client.api.create_chat_session_content(
        json={
            "session_code": session_code,
            "role": "user",
            "content": "什么是SRE?",
            "status": "success",
        }
    )
    assert create_session_user_content_res

    # client.api.create_chat_completion(session_code)

    session_context = client.api.get_chat_session_context(path_params={"session_code": session_code})
    assert session_context

    chat_history = [ChatPrompt.model_validate(each) for each in session_context.get("data", [])]

    # Agent初始化 和 session_code无关
    agent = ChatCompletionAgent(
        chat_model=llm,
        chat_history=chat_history,
    )

    llm_response_list = []
    for each in agent.execute(ExecuteKwargs(stream=True, session_code=session_code)):
        print(each)
        llm_response_list.append(each)

    session_context = client.api.get_chat_session_context(path_params={"session_code": session_code})
    assert session_context

    get_session_contents_res = client.api.get_chat_session_contents(
        params={"session_code": session_code}
    )
    assert get_session_contents_res

    # 删除会话
    delete_session_res = client.api.destroy_chat_session(path_params={"session_code": session_code})
    assert delete_session_res

