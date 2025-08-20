"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import Mock, patch
from uuid import uuid4

from ai_whale.resources.resources import (
    CreateChatSessionResource,
    CreateChatSessionContentResource,
    DestroyChatSessionResource,
)
from ai_whale.utils import generate_uuid
from ai_agent.services.local_command_handler import LocalCommandProcessor

command_processor = LocalCommandProcessor()  # noqa


def test_explanation_command_processed_by_platform():
    """
    测试平台对于「解读」快捷指令的处理逻辑
    """
    session_code = generate_uuid()
    create_session_res = CreateChatSessionResource().request(session_code=session_code, session_name="test_session")
    assert create_session_res

    explanation_command_params = {
        "session_code": session_code,
        "role": "user",
        "content": "解读",
        "property": {
            "extra": {
                "command": "explanation",
                "context": [
                    {"__key": "content", "__value": "SRE", "content": "SRE", "context_type": "textarea"},
                    {"__key": "scene", "__value": "devops", "scene": "devops", "context_type": "textarea"},
                ],
                "anchor_path_resources": {},
            }
        },
    }
    res = CreateChatSessionContentResource().request(**explanation_command_params)
    assert res["data"]["property"]["extra"]["rendered_content"]

    destroy_chat_session_res = DestroyChatSessionResource().request(session_code=session_code)
    assert destroy_chat_session_res


def test_tracing_analysis_command():
    """
    测试【Tracing分析】快捷指令
    """
    mock_trace_id = uuid4().hex
    mock_req = Mock()
    mock_req.session = {"bk_biz_id": 0}
    mock_trace_data = {"trace_data": "[TRACING DATA]"}

    params = {
        "session_code": generate_uuid(),
        "role": "user",
        "content": "Tracing分析",
        "property": {
            "extra": {
                "command": "tracing_analysis",
                "context": [
                    {"__key": "app_name", "__value": "SRE", "content": "SRE", "context_type": "textarea"},
                    {
                        "__key": "trace_id",
                        "__value": mock_trace_id,
                        "trace_id": mock_trace_id,
                        "context_type": "textarea",
                    },
                ],
                "anchor_path_resources": {},
            }
        },
    }

    property_data = params.get("property", {})
    command_data = property_data.get("extra")

    with patch(
        "ai_whale.services.command_handler.api.apm_api.query_trace_detail",
        return_value=mock_trace_data,
    ):
        with patch("ai_whale.services.command_handler.get_request", return_value=mock_req):
            processed_content = command_processor.process_command(command_data)

    expected = (
        f"请帮助我分析Tracing数据: {mock_trace_data['trace_data']}.\n"
        "        应用名称: SRE\n"
        "        结果要求: 确保分析准确无误，无需冗余回答内容"
    )

    assert processed_content == expected
