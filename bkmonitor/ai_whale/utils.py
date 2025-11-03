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
import uuid
from django.conf import settings
from bkmonitor.utils.request import get_request


def generate_uuid():
    """
    生成uuid
    """
    return str(uuid.uuid4())


def generate_user_content(
    command: str,
    context_dict: dict[str, str] = {},
    role: str = "user",
    content: str = "",
    cite: str = "",
    session_code: str | None = None,
) -> dict:
    """
    快速获取前端 POST /session_content 的请求体, 测试时使用
    NOTE: context_type 都被设为了 'input' 类型
    """

    if session_code is None:
        session_code = generate_uuid()

    content_property = {
        "extra": {
            "anchor_path_resources": {},
            "cite": cite,
            "command": command,
            "context": [
                {key: value, "__key": key, "__value": value, "__label": "[test label]", "context_type": "input"}
                for key, value in context_dict.items()
            ],
        },
    }

    return {"content": content, "property": content_property, "role": role, "session_code": session_code}


def collect_streaming_response(generator):
    """
    收集流式响应并汇总所有数据

    参数:
        generator: 流式响应生成器

    返回:
        完整的内容字符串或解析后的JSON对象（如果所有chunk都是JSON）
    """
    full_content = ""
    json_chunks = []

    for chunk in generator:
        # 从日志看，chunk是bytes类型，需要解码
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8")

        # 处理SSE格式 (data: {...}\n\n)
        if chunk.startswith("data:"):
            try:
                json_str = chunk.strip()[5:]  # 去掉'data:'和前后空白
                if json_str:  # 防止空数据
                    data = json.loads(json_str)
                    json_chunks.append(data)
                    if data.get("event") == "done":
                        print(f"done,data->{data}")
                        full_content = data.get("content", "")
            except json.JSONDecodeError:
                # 如果不是JSON，直接拼接原始数据
                # full_content += chunk
                pass

    # 如果所有chunk都是JSON格式，返回解析后的列表
    if json_chunks:
        # 可以选择返回完整内容或原始JSON数据
        return {"full_content": full_content, "json_chunks": json_chunks}
    # 否则返回原始拼接的内容
    return full_content


def get_agent_code_by_scenario_route():
    """
    根据场景路由,获取对应的Agent Code,默认使用主智能体
    Agent路由能力
    """
    route = None
    try:
        request = get_request()
        route = request.headers.get("Monitor-Route-Name")
    except Exception:  # pylint: disable=broad-except
        pass

    agent_code = settings.AIDEV_SCENE_AGENT_CODE_MAPPING.get(route, settings.AIDEV_AGENT_APP_CODE)

    return agent_code
