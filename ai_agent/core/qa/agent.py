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

from langchain.agents import AgentExecutor, Tool
from langchain.agents.chat.base import ChatAgent

from ai_agent.core.qa.retriever import answer_with_documents, retrieve
from ai_agent.llm import LLMConfig, LLMModel, LLMProvider, get_llm


class StreamingQAAgent:
    def __init__(self):
        self.tools = [
            Tool(
                name="retrieve_knowledgebase",
                func=retrieve.run,
                description=retrieve.__doc__,
            ),
            Tool(
                name="answer_with_documents",
                func=answer_with_documents,
                description=answer_with_documents.__doc__,
            ),
        ]
        self.agent = self._initialize_agent()

    def _initialize_agent(self):
        llm = get_llm(LLMConfig(provider=LLMProvider.BLUEKING, model=LLMModel.HUNYUAN_TURBO))
        agent = ChatAgent.from_llm_and_tools(llm=llm, tools=self.tools)
        # 使用ConversationalReactAgent作为基础
        return AgentExecutor.from_agent_and_tools(
            agent=agent, tools=self.tools, verbose=True, return_intermediate_steps=True
        )

    def generate_answer(self, query):
        """流式生成回答"""
        for step in self.agent.stream(query):
            print("***", step)
            if "intermediate_steps" in step:
                yield "reference_doc", step["intermediate_steps"][0][1]
            if "output" in step:
                # 最终输出流式处理
                for token in stream_llm_response(step["output"]):
                    yield "text", token
            # if isinstance(step, dict) and "actions" in step:
            #     continue
            # elif isinstance(step, AgentFinish):
            #     for token in stream_llm_response(step.return_values['output']):
            #         partial_result += token
            #         yield token
            # else:
            #     yield step


def stream_llm_response(text, chunk_size=20):
    """模拟LLM流式输出"""
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]
