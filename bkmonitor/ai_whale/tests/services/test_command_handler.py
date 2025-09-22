"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from unittest.mock import Mock, patch
from uuid import uuid4

from ai_agent.services.local_command_handler import LocalCommandProcessor
from ai_whale.resources.resources import (
    CreateChatSessionContentResource,
    CreateChatSessionResource,
    DestroyChatSessionResource,
)
from ai_whale.utils import generate_user_content, generate_uuid

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
    mock_trace_data = {
        "trace_data": [
            {
                "start_time": 1,
                "end_time": 100,
                "elapsed_time": 100,
                "kind": 1,
                "status": {"code": 2, "message": ""},
                "span_name": "span1",
                "span_id": "123",
            }
        ]
    }

    context_dict = {"bk_biz_id": 1, "app_name": "SRE", "trace_id": mock_trace_id}

    params = generate_user_content(context_dict=context_dict, command="tracing_analysis")

    property_data = params.get("property", {})
    command_data = property_data.get("extra")

    with patch(
        "ai_whale.local_command_handlers.api.apm_api.query_trace_detail",
        return_value=mock_trace_data,
    ):
        processed_content = command_processor.process_command(command_data)

    # 因为 prompt 经常会改动, == asert 难以维护, 故这里不为空就认为正常
    assert isinstance(processed_content, str) and processed_content.strip(), processed_content


def test_profiling_analysis_command():
    command = "profiling_analysis"

    context_dict = {
        "query_params": json.dumps(
            {
                "bk_biz_id": 1,
                "app_name": "app",
                "service_name": "service",
                "data_type": "cpu/nanoseconds",
                "agg_method": "SUM",
                "start": 1,
                "end": 100,
            }
        )
    }
    from apm_web.profile.diagrams.base import FunctionNode, FunctionTree
    from apm_web.profile.diagrams.tree_converter import TreeConverter

    parent = FunctionNode("parent", "parent", "foo_call", "foo", value=1, values=[1])
    son = FunctionNode("son", "son", "bar_call", "bar", parent=parent, value=1)
    tree = FunctionTree(parent, parent, function_node_map={parent.id: parent, son.id: son})
    converter = TreeConverter(tree, {"type": "cpu", "unit": "nanoseconds"})

    session_code = generate_uuid()
    explanation_command_params = generate_user_content(
        command=command, context_dict=context_dict, session_code=session_code
    )

    with patch("apm_web.profile.views.ProfileQueryViewSet.converter_query", return_value=converter):
        with patch("apm_web.profile.views.ProfileQueryViewSet.get_query_params", return_value=({}, {}, {})):
            processed_content = command_processor.process_command(explanation_command_params["property"]["extra"])

    expected = """
        应用名称: app
        业务ID: 0
        请帮助我分析 Profiling 数据(DOT 描述): digraph "type=[cpu/nanoseconds]" {
N0 [label="foo_call \\n 1.00 (100.00%)"]
N1 [label="bar_call \\n 1.00 (100.00%)"]
N0 -> N1
}
        结果要求: 确保分析准确无误，无需冗余回答内容
    """
    assert expected.strip() == processed_content.strip()
