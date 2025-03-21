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
from typing import List

from django.conf import settings

from ai_agent.core.errors import KnowledgeNotConfig

from core.drf_resource import api

"""
知识库检索
"""


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
