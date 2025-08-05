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

from ai_agents.services.command_handler import *  # noqa
from ai_agents.utils import generate_uuid

command_processor = CommandProcessor()  # noqa


def test_translate_command():
    """
    测试【翻译】快捷指令
    """
    params = {
        "session_code": generate_uuid(),
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

    property_data = params.get("property", {})
    command_data = property_data.get("extra")
    processed_content = command_processor.process_command(command_data)

    expected = (
        "\n"
        "        请将以下内容翻译为english:\n"
        "        你好\n"
        "        翻译要求: 确保翻译准确无误，无需冗余回答内容\n"
        "        "
    )
    assert processed_content == expected


def test_explanation_command():
    """
    测试【解释】快捷指令
    """
    params = {
        "session_code": generate_uuid(),
        "role": "user",
        "content": "翻译",
        "property": {
            "extra": {
                "command": "explanation",
                "context": [{"__key": "content", "__value": "SRE", "content": "SRE", "context_type": "textarea"}],
                "anchor_path_resources": {},
            }
        },
    }

    property_data = params.get("property", {})
    command_data = property_data.get("extra")
    processed_content = command_processor.process_command(command_data)

    expected = "\n        请解释以下内容SRE\n        解释要求: 确保解释准确无误，无需冗余回答内容\n        "
    assert processed_content == expected


def test_tracing_analysis_command():
    """
    测试【Tracing分析】快捷指令
    """
    mock_trace_id = uuid4().hex
    mock_req = Mock()
    mock_req.session = {"bk_biz_id": 0}
    mock_trace_data = {'trace_data': '[TRACING DATA]'}

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
        "ai_agents.services.command_handler.api.apm_api.query_trace_detail",
        return_value=mock_trace_data,
    ):
        with patch("ai_agents.services.command_handler.get_request", return_value=mock_req):
            processed_content = command_processor.process_command(command_data)

    expected = (
        f"\n        请分析 trace: {mock_trace_data['trace_data']}"
        "\n        结果要求: 确保分析准确无误，无需冗余回答内容\n        "
    )

    assert processed_content == expected
