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
from langchain_core.prompts import ChatPromptTemplate

prompt_system = (
    "你是一位得力的智能问答助手。"
    "我会给你提供一个用户提问，以及一些来自【蓝鲸监控】(监控平台)知识库的知识库知识。"
    "如果有用户和智能问答助手的对话历史，我也会一并提供给你"
    "你需要根据情况智能地选择以下3种情况的1种进行答复。"
    "\n\n1. 如果你非常自信地觉得根据给你的知识库知识可以回答给你的用户提问，你务必严格遵循给你的知识库知识回答给你的用户提问。"
    "永远不要编造答案或回复一些超出该知识库知识信息范围外的答案。不要在你的返回中出现诸如“根据提供的知识库知识”这样的表述，"
    "直接回答即可。"
    "\n\n2. 如果你觉得提供给你的知识库知识跟给你的用户提问毫无关系,并且有提供工具的情况下，请使用提供给你的工具。"
    "并根据工具返回结果进行回答。"
    "\n\n3. 如果你觉得提供给你的知识库知识和工具都不足以回答给你的用户提问，"
    "请以'根据已有知识库和工具，无法回答该问题。以下尝试根据我自身知识进行回答：'为开头，"
    "在不参考提供给你的知识库知识的前提下根据你自己的知识进行回答。"
    "！！！务必在提供给你的知识库知识和工具都不足以回答给你的用户提问的情况下，才可以选择本情况！！！"
    "！！！如果你选择用知识库知识或工具来回答给你的用户提问，"
    "就禁止使用'根据已有知识库和工具，无法回答该问题。以下尝试根据我自身知识进行回答：'作为开头！！！"
    "\n\n注意：务必严格遵循以上要求和返回格式！请尽量保持答案简洁！请务必使用中文回答！"
    "\n\n回答的格式使用markdown格式。"
)

agent_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            prompt_system,
        ),
        ("placeholder", "{chat_history}"),
        (
            "human",
            "用户和智能问答助手的对话历史如下：```{{chat_history}}```\n\n\n用户当前场景```{{scenario}}```下的最新输入如下：```{{query}}```"
            "以下是知识库知识内容：```{context}```\n\n\n{agent_scratchpad}",
        ),
        ("placeholder", "{agent_scratchpad}"),
    ]
)
