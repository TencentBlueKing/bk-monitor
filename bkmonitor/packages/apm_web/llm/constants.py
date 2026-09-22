"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from functools import cached_property

from constants.apm import CachedEnum
from django.utils.translation import gettext_lazy as _


class CalculationType(CachedEnum):
    # 输入 Token 数
    INPUT_TOKENS = "input_tokens"
    # 输出 Token 数
    OUTPUT_TOKENS = "output_tokens"
    # 总 Token 数
    TOTAL_TOKENS = "total_tokens"
    # 缓存 Token 数
    CACHE_TOKENS = "cache_tokens"
    # 缓存读取、写入 Token 数，与执行线统计字段一致
    CACHE_READ_INPUT_TOKENS = "cache_read_input_tokens"
    CACHE_WRITE_INPUT_TOKENS = "cache_write_input_tokens"
    # 模型调用次数
    MODEL_CALL_COUNT = "model_call_count"
    # 操作次数
    OPERATION_COUNT = "operation_count"
    # 平均耗时，与 AVG_DURATION 语义相同，LLM 侧沿用前端既有取值名
    DURATION = "duration"
    # 请求数，与 REQUEST_TOTAL 语义相同，LLM 侧沿用前端既有取值名
    REQUEST_COUNT = "request_count"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]

    @cached_property
    def label(self) -> str:
        labels = {
            self.INPUT_TOKENS: _("输入 Token 数"),
            self.OUTPUT_TOKENS: _("输出 Token 数"),
            self.TOTAL_TOKENS: _("总 Token 数"),
            self.CACHE_TOKENS: _("缓存 Token 数"),
            self.CACHE_READ_INPUT_TOKENS: _("缓存读取 Token 数"),
            self.CACHE_WRITE_INPUT_TOKENS: _("缓存写入 Token 数"),
            self.MODEL_CALL_COUNT: _("模型调用次数"),
            self.OPERATION_COUNT: _("操作次数"),
            self.DURATION: _("平均耗时"),
            self.REQUEST_COUNT: _("请求数"),
        }
        return labels.get(self) or self.value


class SpanType:
    """Span 的 LLM 语义层级，由 adapter 依据操作名归类，执行线构造与统计侧共用。"""

    AGENT = "AGENT"
    LLM = "LLM"
    TOOL = "TOOL"


# gen_ai.operation.name -> Span 语义层级，未登记的取值（检索、任务等）不归类。
SPAN_TYPES: dict[str, str] = {
    "invoke_workflow": SpanType.AGENT,
    "create_agent": SpanType.AGENT,
    "invoke_agent": SpanType.AGENT,
    "plan": SpanType.AGENT,
    "execute_tool": SpanType.TOOL,
    "chat": SpanType.LLM,
    "generate_content": SpanType.LLM,
    "text_completion": SpanType.LLM,
    "fetch_response": SpanType.LLM,
    "embeddings": SpanType.LLM,
}

STANDARD_FIELDS: set[str] = {
    "error.type",
    "user.id",
    "user.name",
    "user.hash",
    "gen_ai.operation.name",
    "gen_ai.provider.name",
    "gen_ai.conversation.id",
    "gen_ai.agent.id",
    "gen_ai.agent.name",
    "gen_ai.agent.description",
    "gen_ai.agent.version",
    "gen_ai.request.model",
    "gen_ai.request.stream",
    "gen_ai.request.temperature",
    "gen_ai.request.reasoning.level",
    "gen_ai.response.id",
    "gen_ai.response.model",
    "gen_ai.response.status",
    "gen_ai.response.finish_reasons",
    "gen_ai.response.time_to_first_chunk",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "gen_ai.usage.cache_read.input_tokens",
    "gen_ai.usage.cache_write.input_tokens",
    "gen_ai.usage.reasoning.output_tokens",
    "gen_ai.system_instructions",
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "gen_ai.tool.definitions",
    "gen_ai.tool.name",
    "gen_ai.tool.description",
    "gen_ai.tool.type",
    "gen_ai.tool.call.id",
    "gen_ai.tool.call.arguments",
    "gen_ai.tool.call.result",
}
