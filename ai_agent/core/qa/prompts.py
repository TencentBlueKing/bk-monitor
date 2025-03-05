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

rag_sys_prompt = (
    "你是一个私有知识库智能问答助手。"
    "你必须严格遵循给你的 context 回答给你的 query，永远不要编造答案或回复一些超出该 context 信息范围外的答案。"
    "请尽量保持答案简洁！请务必使用中文回答！如果给定的 context 中包含链接，请在你的回答中包含这些链接！"
    "不要出现诸如“根据提供的 context，”这样的表述！"
)
rag_usr_prompt = """
以下是 query 内容: '''{query}'''

以下是 context 内容: '''{context}'''
"""

query_rewrite_sys_prompt = (
    "给你一段 context，以及一个意图可能不够明确或表述可能不够清晰的用户 query，请你根据该 context 推测用户 query 可能是想问什么？\n"
    '1. 如果你觉得该 query 跟 context 毫不相关，请直接返回"无关"。\n'
    "2. 如果你觉得该 query 跟 context 有一定的关系，请对该 query 进行重写，使其表述清晰无歧义且意图明确，"
    '并将重写后的 query 返回，格式："Rewritten Query: xxx"。'
    "注意：你返回的 query 务必可以根据给定的 context 进行回答！"
    "只返回 query 本身即可，不要返回其他任何内容！重写的 query 务必保持简洁！不要啰嗦！"
)
query_rewrite_usr_prompt = """
以下是 query 内容: '''{query}'''

以下是 context 内容: '''{context}'''
"""
