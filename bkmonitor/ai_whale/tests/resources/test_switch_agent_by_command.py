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
from aidev_agent.api.bk_aidev import BKAidevApi
from ai_whale.utils import generate_uuid, collect_streaming_response
from django.conf import settings
from aidev_agent.services.config_manager import AgentConfigManager

api_client = BKAidevApi.get_client(app_code=settings.AIDEV_AGENT_APP_CODE, app_secret=settings.AIDEV_AGENT_APP_SECRET)


def test_switch_agent_by_command_metadata():
    """
    测试通过快捷指令方式切换Agent
    案例: 监控链路元数据排障场景
    """
    session_code = generate_uuid()

    settings.AIDEV_COMMAND_AGENT_MAPPING = {
        "metadata_diagnosis": "test-metadata",
    }

    basic_config = AgentConfigManager.get_config(
        agent_code=settings.AIDEV_AGENT_APP_CODE,
        resource_manager=api_client,
    )

    create_res = CreateChatSessionResource().request(
        session_code=session_code, session_name="test_switch_agent_by_command"
    )

    assert create_res

    # 初始化System Prompt
    create_sys_content_res = CreateChatSessionContentResource().request(
        session_code=session_code, role="hidden-system", content=basic_config.role_prompt
    )

    assert create_sys_content_res

    # 创建问题 -- 大Agent
    create_question_res = CreateChatSessionContentResource().request(
        session_code=session_code, role="user", content="告警包含哪几个级别？"
    )

    assert create_question_res

    # 获取对话上下文
    session_context_data = api_client.api.get_chat_session_context(path_params={"session_code": session_code}).get(
        "data", []
    )

    assert session_context_data

    params = {"session_code": session_code, "execute_kwargs": {"stream": True}}

    # 流式响应拼接
    generator = CreateChatCompletionResource().request(params)
    result = collect_streaming_response(generator)

    # 插入AI回答
    create_ai_answer_res = CreateChatSessionContentResource().request(
        session_code=session_code, role="ai", content=result["full_content"]
    )

    assert create_ai_answer_res

    # 替换测试用的数据源ID
    metadata_diagnosis_command_params = {
        "session_code": session_code,
        "role": "user",
        "content": "链路元数据排障",
        "property": {
            "extra": {
                "command": "metadata_diagnosis",
                "context": [
                    {"__key": "bk_data_id", "__value": "123", "bk_data_id": "123", "context_type": "textarea"},
                ],
                "anchor_path_resources": {},
            }
        },
    }

    create_command_res = CreateChatSessionContentResource().request(**metadata_diagnosis_command_params)

    assert create_command_res

    # 获取对话上下文
    session_context_data = api_client.api.get_chat_session_context(path_params={"session_code": session_code}).get(
        "data", []
    )

    assert session_context_data

    params = {"session_code": session_code, "execute_kwargs": {"stream": True}}

    # 流式响应拼接
    generator = CreateChatCompletionResource().request(params)
    result = collect_streaming_response(generator)

    assert result

    DestroyChatSessionResource().request(session_code=session_code)


def test_switch_agent_by_command_promql_helper():
    """
    测试通过快捷指令方式切换Agent
    案例: PromQL Helper
    """
    session_code = generate_uuid()

    settings.AIDEV_COMMAND_AGENT_MAPPING = {
        "metadata_diagnosis": "promql_helper_xxx",
    }

    basic_config = AgentConfigManager.get_config(agent_code=settings.AIDEV_AGENT_APP_CODE, resource_manager=api_client)

    create_res = CreateChatSessionResource().request(
        session_code=session_code, session_name="test_switch_agent_by_command"
    )

    assert create_res

    # 初始化System Prompt
    create_sys_content_res = CreateChatSessionContentResource().request(
        session_code=session_code, role="hidden-system", content=basic_config.role_prompt
    )

    assert create_sys_content_res

    # 创建问题 -- 大Agent
    create_question_res = CreateChatSessionContentResource().request(
        session_code=session_code, role="user", content="告警包含哪几个级别？"
    )

    assert create_question_res

    # 获取对话上下文
    session_context_data = api_client.api.get_chat_session_context(path_params={"session_code": session_code}).get(
        "data", []
    )

    assert session_context_data

    params = {"session_code": session_code, "execute_kwargs": {"stream": True}}

    # 流式响应拼接
    generator = CreateChatCompletionResource().request(params)
    result = collect_streaming_response(generator)

    # 插入AI回答
    create_ai_answer_res = CreateChatSessionContentResource().request(
        session_code=session_code, role="ai", content=result["full_content"]
    )

    assert create_ai_answer_res

    promql_helper_command_params = {
        "session_code": session_code,
        "role": "user",
        "content": "PromQL助手",
        "property": {
            "extra": {
                "command": "promql_helper",
                "context": [
                    {
                        "__key": "promql",
                        "__value": "bkmonitor:system:disk:in_use",
                        "promql": "bkmonitor:system:disk:in_use",
                        "context_type": "textarea",
                    },
                    {
                        "__key": "user_demand",
                        "__value": "请帮我按照目标IP进行聚合,找到最大值对应的IP",
                        "user_demand": "请帮我按照目标IP进行聚合,找到最大值对应的IP",
                        "context_type": "textarea",
                    },
                ],
                "anchor_path_resources": {},
            }
        },
    }

    create_command_res = CreateChatSessionContentResource().request(**promql_helper_command_params)

    assert create_command_res

    # 获取对话上下文
    session_context_data = api_client.api.get_chat_session_context(path_params={"session_code": session_code}).get(
        "data", []
    )

    assert session_context_data

    params = {"session_code": session_code, "execute_kwargs": {"stream": True}}

    # 流式响应拼接
    generator = CreateChatCompletionResource().request(params)
    result = collect_streaming_response(generator)

    assert result

    DestroyChatSessionResource().request(session_code=session_code)
