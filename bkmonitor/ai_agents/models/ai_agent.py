"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import models
from aidev_agent.api import BKAidevApi


class AgentConfig(models.Model):
    """
    智能体配置
    """

    # Agent基础标识
    agent_code = models.CharField("智能体代码", max_length=128, db_index=True)
    agent_name = models.CharField("智能体名称", max_length=128)

    # Agent基础配置信息
    llm_model_name = models.CharField("LLM模型名称", max_length=128)
    non_thinking_llm_model_name = models.CharField("非深度思考模型", max_length=128)
    role_prompt = models.TextField("角色提示词", null=True, blank=True)

    # Agent 知识库&意图识别配置信息
    knowledgebase_ids = models.JSONField("知识库ID列表", default=list)

    # Agent 工具配置
    tool_codes = models.JSONField("工具列表", default=list)

    # Agent 前端交互配置
    opening_mark = models.TextField("智能体开场白", null=True, blank=True)

    class Meta:
        verbose_name = "智能体配置"
        verbose_name_plural = "智能体配置"

    @classmethod
    def sync_config_by_agent_code(cls, agent_code: str):
        """
        根据agent_code同步配置 (create or update 模式)
        :param agent_code: 智能体代码
        """
        client = BKAidevApi.get_client()

        try:
            # 1. 调用API获取配置
            res = client.api.retrieve_agent_config(path_params={"agent_code": agent_code})["data"]
        except Exception as e:
            raise ValueError(f"Failed to retrieve agent config: {e}")

        # 2. 提取提示词内容（拼接所有system角色的提示词）
        role_prompt = "\n".join(
            item["content"] for item in res["prompt_setting"]["content"] if item["role"] == "system"
        )

        # 3. 准备update_or_create的数据字典
        config_data = {
            "agent_name": res["agent_name"],
            "llm_model_name": res["prompt_setting"]["llm_code"],
            "non_thinking_llm_model_name": res["prompt_setting"]["non_thinking_llm"] or "",
            "role_prompt": role_prompt or None,
            "knowledgebase_ids": res["knowledgebase_settings"]["knowledgebases"],
            "tool_codes": res["related_tools"],
            "opening_mark": res["conversation_settings"]["opening_remark"] or None,
        }

        # 4. 执行原子操作 (create or update)
        obj, created = cls.objects.update_or_create(agent_code=agent_code, defaults=config_data)

        return obj
