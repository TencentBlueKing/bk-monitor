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

from django.conf import settings
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import Tool


from ai_agent.core.qa.retriever import retrieve
from ai_agent.llm import get_llm, LLMConfig, LLMProvider, LLMModel

"""
QA Agent
"""

private_qa_agent_prompt_system = (
    "你是一位得力的智能问答助手。"
    "我会给你提供一个用户提问，以及一些来自私域知识库的知识库知识。"
    "你需要根据情况智能地选择以下3种情况的1种进行答复。"
    "\n\n1. 如果你非常自信地觉得根据给你的知识库知识可以回答给你的用户提问，你务必严格遵循给你的知识库知识回答给你的用户提问。"
    "永远不要编造答案或回复一些超出该知识库知识信息范围外的答案。不要在你的返回中出现诸如“根据提供的知识库知识”这样的表述，"
    "直接回答即可。"
    "\n\n2. 如果你觉得提供给你的知识库知识跟给你的用户提问毫无关系，而更倾向于使用提供给你的工具，请使用提供给你的工具。"
    "并根据工具返回结果进行回答。"
    "\n\n3. 如果你觉得提供给你的知识库知识和工具都不足以回答给你的用户提问，"
    "请以'根据已有知识库和工具，无法回答该问题。以下尝试根据我自身知识进行回答：'为开头，"
    "在不参考提供给你的知识库知识的前提下根据你自己的知识进行回答。"
    "！！！务必在提供给你的知识库知识和工具都不足以回答给你的用户提问的情况下，才可以选择本情况！！！"
    "！！！如果你选择用知识库知识或工具来回答给你的用户提问，"
    "就禁止使用'根据已有知识库和工具，无法回答该问题。以下尝试根据我自身知识进行回答：'作为开头！！！"
    "\n\n注意：务必严格遵循以上要求和返回格式！请尽量保持答案简洁！请务必使用中文回答！"
)

private_qa_agent_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            private_qa_agent_prompt_system,
        ),
        ("placeholder", "{chat_history}"),
        (
            "human",
            "以下是知识库知识内容：```{context}```\n\n\n以下是用户提问内容：```{query}```\n\n{agent_scratchpad}",
        ),
        ("placeholder", "{agent_scratchpad}"),
    ]
)


_llm = get_llm(LLMConfig(provider=LLMProvider.BLUEKING, model=LLMModel.HUNYUAN_TURBO))

_tools = [
#     Tool(
#     name="KnowledgeSearch",
#     func=retrieve,
#     description=retrieve.__doc__,
# )
]


class StreamEventType:
    NO = ""
    TEXT = "text"
    THINK = "think"
    REFERENCE_DOC = "reference_doc"
    ERROR = "error"
    DONE = "done"


def check_retrieve_result(documents, score_threshold=0.35):
    return list(filter(lambda doc: doc["metadata"]["__score__"] > score_threshold, documents))

def filter_documents_with_tag(documents, tag=""):
    if not tag:
        return documents
    return list(filter(lambda doc: tag in doc["metadata"]["tags"], documents))


class QaAgent:
    # 知识库检索支持tag过滤应在接口层实现
    knowledge_tag = "蓝鲸监控"

    def __init__(self, llm=_llm, tools=None, prompt=private_qa_agent_prompt):
        tools = tools or []
        agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
        self.agent_executor = AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, verbose=True)

    def generate_answer(self, query):
        documents = retrieve(query)
        # 通过filter_documents_with_tag函数，将文档列表中的标签不包含指定标签的文档过滤掉，剩余的文档列表命名为指定标签文档
        documents = filter_documents_with_tag(documents)
        # 通过check_retrieve_result函数，将文档列表中的分数低于阈值的文档过滤掉，剩余的文档列表命名为可信文档
        trusted_documents = check_retrieve_result(documents)

        yield self.make_event_stream_token(StreamEventType.REFERENCE_DOC, trusted_documents)
        if not trusted_documents:
            yield self.make_event_stream_token(StreamEventType.TEXT, "我不知道。" + self.reject_guide_answer())
            return
        context = "\n\n".join([doc["page_content"] for doc in trusted_documents])
        for each in self.agent_executor.stream({"query": query, "context": context}):
            if "output" not in each:
                continue
            yield self.make_event_stream_token(StreamEventType.TEXT, each["output"])

        yield "data: [DONE]\n\n"

    def reject_guide_answer(self):
        link_tmp = """<a href="{doc_link}" target="_blank">【BK助手】</a>"""
        return "\n您可以尝试换个问法或点击立即联系" + link_tmp.format(doc_link=self._get_wx_link() or "")

    @classmethod
    def _get_wx_link(cls):
        for item in settings.BK_DATA_ROBOT_LINK_LIST:
            if item["icon_name"] == "icon-kefu":
                return item["link"]

    @classmethod
    def make_event_stream_token(cls, event_type, content):
        data_field = {"text": "content", "reference_doc": "documents", "reject": "content"}
        return "data: " + json.dumps({"event": event_type, data_field[event_type]: content}) + "\n\n"


QA_AGENT = QaAgent()

def main():
    for content in QA_AGENT.generate_answer("如何配置监控策略?"):
        print(content)


if __name__ == "__main__":
    main()
