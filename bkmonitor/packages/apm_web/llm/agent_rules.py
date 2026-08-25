"""用于判断一个服务“可能是 Agent”的统一规则。

我们的原则是宁可把少量普通 LLM 服务也标成 Agent，也不要漏掉真实 Agent。
网关先按较宽松的条件多取一些 Span，Adapter 再判断哪些确实是 AI 步骤。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

# 判断服务可能是 Agent 的七个字段；任意一个有值就给服务增加 Agent 能力标签。
AGENT_FEATURE_FIELDS = (
    "gen_ai.operation.name",
    "gen_ai.agent.id",
    "gen_ai.agent.name",
    "gen_ai.provider.name",
    "gen_ai.request.model",
    "gen_ai.response.model",
    "gen_ai.tool.name",
)

# 字段还没转换成统一格式前，网关先检查这些来源字段。这里故意多取，减少漏查。
RAW_CANDIDATE_FIELDS = (
    *(f"attributes.{field}" for field in AGENT_FEATURE_FIELDS),
    "attributes.gen_ai.system",
    "attributes.gen_ai.span.kind",
    "attributes.gen_ai.entity.name",
    "attributes.gen_ai.chain.name",
    "attributes.gen_ai.prompts.0.role",
    "attributes.gen_ai.prompt.0.role",
    "attributes.gen_ai.completion.0.role",
    "attributes.agent.info.id",
    "attributes.agent.info.name",
    "attributes.agent.session.session_code",
    "attributes.agent.session.caller_executor",
    "attributes.chain.workflow",
    "attributes.tool.name",
    "attributes.traceloop.span.kind",
    "attributes.traceloop.entity.name",
)

# 如果来源没有稳定字段，再检查这些常见 Span 名称；它们只用于初步筛选。
RAW_CANDIDATE_TERMS = (
    "span_name: *.AGENT",
    "span_name: *.LLM",
    "span_name: *.TOOL",
    'span_name: "chain.workflow"',
    'span_name: "chat_model.generate"',
    'span_name: "tool.execution"',
    'span_name: "langgraph.workflow"',
    'span_name: "chatmodel.chat"',
    'span_name: "model.task"',
    'span_name: "model_node.task"',
    'span_name: "tools.task"',
    'span_name: "chain.task"',
)

# 发送给 flatten_span 的单个 Lucene OR 表达式；不能拆成多个 filters（会变成 AND）。
RAW_CANDIDATE_QUERY = (
    "("
    + " OR ".join(
        [
            *(f"_exists_:{field}" for field in RAW_CANDIDATE_FIELDS),
            *RAW_CANDIDATE_TERMS,
        ]
    )
    + ")"
)

# 概览统计只扫描模型调用 Span；工具调用次数只读取查询返回的 total。
# 这些仍是来源字段，最终数值继续交给 Adapter 归一化。
RAW_LLM_QUERY = (
    "("
    + " OR ".join(
        (
            "_exists_:attributes.gen_ai.usage.input_tokens",
            "_exists_:attributes.gen_ai.usage.output_tokens",
            "_exists_:attributes.llm.usage.total_tokens",
            'attributes.gen_ai.span.kind:"LLM"',
            "span_name: *.LLM",
            'span_name: "chat_model.generate"',
            'span_name: "chatmodel.chat"',
            'span_name: "model.task"',
            'span_name: "model_node.task"',
        )
    )
    + ")"
)

RAW_TOOL_QUERY = (
    "("
    + " OR ".join(
        (
            'attributes.gen_ai.operation.name:"execute_tool"',
            "_exists_:attributes.gen_ai.tool.name",
            "_exists_:attributes.tool.name",
            "span_name: *.TOOL",
            'span_name: "tool.execution"',
            'span_name: "tools.task"',
        )
    )
    + ")"
)

RAW_AGENT_IDENTITY_QUERY = (
    "("
    + " OR ".join(
        (
            "_exists_:attributes.gen_ai.agent.id",
            "_exists_:attributes.gen_ai.agent.name",
            "_exists_:attributes.gen_ai.agent.description",
            "_exists_:attributes.agent.info.id",
            "_exists_:attributes.agent.info.name",
            "_exists_:attributes.agent.info.description",
        )
    )
    + ")"
)


def agent_feature_hits(steps: Iterable[Mapping[str, Any]]) -> list[str]:
    """返回哪些字段让我们认为这个服务可能是 Agent。

    输入输出示例::

        输入: [{"attributes": {"gen_ai.request.model": "gpt-4o"}}, {"attributes": {"gen_ai.tool.name": "add"}}]
        输出: ["gen_ai.request.model", "gen_ai.tool.name"]

    七个字段是 OR 关系；返回非空就给服务增加 Agent 能力标签。
    """
    materialized = list(steps)
    return [
        field
        for field in AGENT_FEATURE_FIELDS
        if any(
            isinstance(step.get("attributes"), Mapping) and step["attributes"].get(field) not in (None, "")
            for step in materialized
        )
    ]


def is_background_task_candidate(span: Mapping[str, Any]) -> bool:
    """判断候选 Span 是否为已知的纯工具后台轮询。"""
    attributes = span.get("attributes")
    attrs = attributes if isinstance(attributes, Mapping) else {}
    values = (span.get("span_name"), attrs.get("http.path"))
    return any(isinstance(value, str) and "seedance_query_task" in value.lower() for value in values)
