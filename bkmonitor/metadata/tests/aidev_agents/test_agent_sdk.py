"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.config import settings
from aidev_agent.core.extend.models.llm_gateway import ChatModel
from aidev_agent.services.chat import ChatCompletionAgent, ExecuteKwargs
from aidev_agent.services.pydantic_models import ChatPrompt


@pytest.fixture
def add_session():
    client = BKAidevApi.get_client()
    session_code = "1111"
    client.api.create_chat_session(json={"session_code": session_code, "session_name": "testonly"})
    # 添加一些session content
    client.api.create_chat_session_content(
        json={
            "session_code": session_code,
            "role": "user",
            "content": "how about the game",
            "status": "success",
        }
    )
    yield session_code
    result = client.api.get_chat_session_contents(params={"session_code": session_code})
    for each in result.get("data", []):
        _id = each["id"]
        client.api.destroy_chat_session_content(path_params={"id": _id})
    client.api.destroy_chat_session(path_params={"session_code": session_code})


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
def test_common_agent_chat_streaming(add_session):
    llm = ChatModel.get_setup_instance(model="hunyuan-turbos")
    client = BKAidevApi.get_client()
    session_code = add_session
    tool_codes = ["nba_game_assistant"]

    result = client.api.get_chat_session_context(path_params={"session_code": session_code})
    tools = [client.construct_tool(tool_code) for tool_code in tool_codes]
    chat_history = [ChatPrompt.model_validate(each) for each in result.get("data", [])]
    agent = ChatCompletionAgent(
        chat_model=llm,
        chat_history=chat_history,
        tools=tools,
    )
    for each in agent.execute(ExecuteKwargs(stream=True)):
        print(each)
