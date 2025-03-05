# -*- coding: utf-8 -*-
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
from typing import List, Union

from django.conf import settings
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

from ai_agent.core.errors import KnowledgeNotConfig
from ai_agent.core.qa import Decision
from ai_agent.core.qa.prompts import (
    query_rewrite_sys_prompt,
    query_rewrite_usr_prompt,
    rag_sys_prompt,
    rag_usr_prompt,
)
from ai_agent.llm import LLMConfig, LLMModel, LLMProvider, get_llm
from core.drf_resource import api

"""
知识库检索
"""


@tool("retrieve_knowledgebase")
def retrieve(query: str) -> List[dict]:
    """
    进行知识库检索，获取与查询相关的文档信息

    Args:
        query (str): 用户查询的问题或关键词

    Returns:
        List[dict]: 包含检索结果的字典列表，每个字典对应一个文档及其元数据

    Raises:
        KnowledgeNotConfig: 当知识库ID未配置时抛出异常
    """

    knowledgebase_ids = settings.AIDEV_KNOWLEDGE_BASE_IDS
    if not knowledgebase_ids:
        raise KnowledgeNotConfig("AIDEV_KNOWLEDGE_BASE_IDS not configured in settings")

    data = {
        "query": query,
        "topk": 5,
        "index_query_kwargs": [
            {
                "index_name": "full_text",
                "index_value": query,
                "knowledge_base_id": _id,
            }
            for _id in knowledgebase_ids
        ],
        "type": "index_specific",
    }
    result = api.aidev.only_knowledgebase_query(data)
    return result["documents"]


def parse_retrieved_results(query, context_docs_with_scores, reject_threshold, qa_results):
    """解析检索结果"""
    context_contents = [doc.page_content for doc, _ in context_docs_with_scores]
    emb_scores = [emb_score for _, emb_score in context_docs_with_scores]
    context_resources = [doc.metadata["path"] for doc, _ in context_docs_with_scores]
    fine_grained_scores = emb_scores

    contexts_emb_recalled = []
    contexts_lowly_relevant = []
    contexts_moderately_relevant = []
    contexts_highly_relevant = []
    for context, emb_score, fine_grained_score, context_resource in zip(
        context_contents, emb_scores, fine_grained_scores, context_resources
    ):
        contexts_emb_recalled.append(
            {
                "context": context,
                "emb_score": emb_score,
                "fine_grained_score": fine_grained_score,
                "context_resource": context_resource,
            }
        )
        if fine_grained_score < reject_threshold[0]:
            contexts_lowly_relevant.append(
                {
                    "context": context,
                    "emb_score": emb_score,
                    "fine_grained_score": fine_grained_score,
                    "context_resource": context_resource,
                }
            )
        elif reject_threshold[0] <= fine_grained_score < reject_threshold[1]:
            contexts_moderately_relevant.append(
                {
                    "context": context,
                    "emb_score": emb_score,
                    "fine_grained_score": fine_grained_score,
                    "context_resource": context_resource,
                }
            )
        elif fine_grained_score >= reject_threshold[1]:
            contexts_highly_relevant.append(
                {
                    "context": context,
                    "emb_score": emb_score,
                    "fine_grained_score": fine_grained_score,
                    "context_resource": context_resource,
                }
            )

    if qa_results is not None:
        qa_results["query"] = query
        for res_type, res in zip(
            [
                "contexts_emb_recalled",
                "contexts_lowly_relevant",
                "contexts_moderately_relevant",
                "contexts_highly_relevant",
            ],
            [
                contexts_emb_recalled,
                contexts_lowly_relevant,
                contexts_moderately_relevant,
                contexts_highly_relevant,
            ],
        ):
            if res is not None:
                qa_results[res_type] = res

    return contexts_emb_recalled, contexts_lowly_relevant, contexts_moderately_relevant, contexts_highly_relevant


def make_decision(contexts_emb_recalled, contexts_lowly_relevant, contexts_highly_relevant):
    """决策分类"""
    if len(contexts_lowly_relevant) == len(contexts_emb_recalled):
        # 如果所有文档都是超低分，则直接拒绝回答问题
        return Decision.REJECT
    elif len(contexts_highly_relevant) > 0:
        # 如果存在超高分文档，则直接使用超高分文档进行回答
        return Decision.ANSWER
    else:
        # 其他情况：如果存在一些可能是 query【意图不明确】或【描述不清】导致的中间分相关文档，根据中分相关文档进行 query 重写
        return Decision.REWRITE


def answer_with_documents(inputs) -> Union[AgentFinish, AgentAction]:
    """
    执行智能问答，基于知识库的检索结果进行回答

    Args:
        inputs:包含query 和 docs两个信息, 同时放在inputs中，json编码成字符串
            query: 表示用户的问题
            docs: 表示已经检索到的知识库信息



    Returns:
        AgentAction or AgentFinish
    """
    # todo 待支持上下文
    # context = []
    try:
        inputs = json.loads(inputs)
    except Exception:
        pass
    query = inputs["query"]
    docs = inputs["docs"]
    # 设置知识库相关度阈值
    reject_threshold = (0.05, 0.35)
    # 检索和结果解析
    context_docs_with_scores = [(Document(**item), item["metadata"]["__score__"]) for item in docs]
    (
        contexts_emb_recalled,
        contexts_lowly_relevant,
        contexts_moderately_relevant,
        contexts_highly_relevant,
    ) = parse_retrieved_results(query, context_docs_with_scores, reject_threshold, qa_results=None)

    # 决策分类和实施
    decision = make_decision(contexts_emb_recalled, contexts_lowly_relevant, contexts_highly_relevant)
    if decision == Decision.REJECT:
        answer = "根据已有知识库，无法回答该问题。"
        final_decision = AgentAction(tool="continue", tool_input={}, log=str(answer))
    elif decision == Decision.ANSWER:
        context = "\n\n".join([context["context"] for context in contexts_highly_relevant])
        rag_sys_msg = SystemMessage(content=rag_sys_prompt)
        rag_usr_msg = HumanMessage(content=rag_usr_prompt.format(query=query, context=context))
        answer = chat(rag_sys_msg, rag_usr_msg)
        final_decision = AgentFinish(return_values={"output": answer}, log="")
    else:
        # Decision.REWRITE
        answer, final_decision = rewrite_answer(query, contexts_moderately_relevant)
        if not final_decision:
            final_decision = AgentFinish(return_values={"output": answer}, log="")
    return final_decision


def chat(sys_prompt, usr_prompt):
    prompt = ChatPromptTemplate.from_messages([sys_prompt, usr_prompt])
    llm = get_llm(LLMConfig(provider=LLMProvider.BLUEKING, model=LLMModel.HUNYUAN_TURBO))
    chain = prompt | llm | StrOutputParser()
    try:
        resp = chain.invoke({})
    except Exception as exp:
        raise RuntimeError(f"smart_qa query error: \n{exp}")
    return resp


def rewrite_answer(query, contexts_moderately_relevant):
    """实施重写决策"""
    sorted_contexts_moderately_relevant = sorted(
        contexts_moderately_relevant,
        key=lambda x: x["fine_grained_score"],
        reverse=True,
    )
    raw_rewritten_queries = []
    rewritten_queries = []
    for i in range(len(contexts_moderately_relevant)):
        context = contexts_moderately_relevant[i]["context"]
        query_rewrite_sys_msg = SystemMessage(content=query_rewrite_sys_prompt)
        query_rewrite_usr_msg = HumanMessage(content=query_rewrite_usr_prompt.format(query=query, context=context))
        rewritten_query = chat(query_rewrite_sys_msg, query_rewrite_usr_msg)
        raw_rewritten_queries.append(rewritten_query)
        prefix = "Rewritten Query: "
        if rewritten_query.startswith(prefix):
            rewritten_query = rewritten_query[len(prefix) :]
        prefix = '"Rewritten Query: '
        if rewritten_query.startswith(prefix):
            rewritten_query = rewritten_query[len(prefix) : -len('"')]
        rewritten_queries.append(rewritten_query)
    if all([rewritten_query == "无关" for rewritten_query in rewritten_queries]):
        answer = "根据已有知识库，无法回答该问题。"
        final_decision = AgentAction(tool="continue", tool_input={}, log=str(answer))
    else:
        suggestion_queries_and_links = []
        for rewritten_query, sorted_context_moderately_relevant in zip(
            rewritten_queries, sorted_contexts_moderately_relevant
        ):
            if rewritten_query != "无关":
                link = sorted_context_moderately_relevant["context_resource"]
                suggestion_query_and_link = rewritten_query + f" ({link})"
                suggestion_queries_and_links.append(suggestion_query_and_link)
        formatted_suggestions = "\n".join(
            [
                f"{i + 1}. {suggestion_query_and_link}"
                for i, suggestion_query_and_link in enumerate(suggestion_queries_and_links)
            ]
        )
        answer = f"抱歉，您是不是想问：\n{formatted_suggestions}\n如果都不是，请重新描述您的问题。"
        final_decision = AgentFinish(return_values={"output": answer}, log="")

    return answer, final_decision
