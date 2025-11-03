"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from ai_whale.resources.resources import (
    CreateChatCompletionResource,
    CreateChatSessionContentResource,
    CreateChatSessionResource,
    DestroyChatSessionResource,
)
from ai_whale.utils import generate_uuid


def test_chat_completion_with_fast_command():
    """
    测试带有快捷指令的LLM对话
    """

    session_code = generate_uuid()

    create_session_res = CreateChatSessionResource().request(session_code=session_code, session_name="test_session")
    assert create_session_res

    translate_command_params = {
        "session_code": session_code,
        "role": "user",
        "content": "翻译",
        "property": {
            "extra": {
                "command": "translate",
                "context": [
                    {"__key": "content", "__value": "你好", "content": "你好", "context_type": "textarea"},
                    {"__key": "language", "__value": "english", "language": "english", "context_type": "textarea"},
                ],
                "anchor_path_resources": {},
            }
        },
    }

    CreateChatSessionContentResource().request(**translate_command_params)

    chat_completion_params = {"session_code": session_code, "execute_kwargs": {"stream": True}}
    chat_completion_res = CreateChatCompletionResource().request(**chat_completion_params)
    for chunk in chat_completion_res:
        print(chunk)  # 输出每个响应块

    destroy_chat_session_res = DestroyChatSessionResource().request(session_code=session_code)
    assert destroy_chat_session_res


def test_chat_completion_with_non_streaming_mode():
    """
    测试非流式模式的LLM对话
    """
    session_code = generate_uuid()

    create_session_res = CreateChatSessionResource().request(session_code=session_code, session_name="test_session")
    assert create_session_res

    translate_command_params = {
        "session_code": session_code,
        "role": "user",
        "content": "翻译",
        "property": {
            "extra": {
                "command": "translate",
                "context": [
                    {"__key": "content", "__value": "你好", "content": "你好", "context_type": "textarea"},
                    {"__key": "language", "__value": "english", "language": "english", "context_type": "textarea"},
                ],
                "anchor_path_resources": {},
            }
        },
    }

    CreateChatSessionContentResource().request(**translate_command_params)

    chat_completion_params = {"session_code": session_code, "execute_kwargs": {"stream": False}}
    chat_completion_res = CreateChatCompletionResource().request(**chat_completion_params)
    print(chat_completion_res)
