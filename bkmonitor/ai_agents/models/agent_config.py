"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """智能体配置"""

    agent_code: str = Field(..., description="智能体代码")
    agent_name: str = Field(..., description="智能体名称")
    llm_model_name: str = Field(..., description="LLM模型名称")
    non_thinking_llm_model_name: str = Field(..., description="非深度思考模型")
    role_prompt: str | None = Field(None, description="角色提示词")
    knowledgebase_ids: list = Field(default_factory=list, description="知识库ID列表")
    knowledge_ids: list = Field(default_factory=list, description="知识ID列表")
    tool_codes: list = Field(default_factory=list, description="工具列表")
    opening_mark: str | None = Field(None, description="智能体开场白")


class AgentConfigManager:
    """智能体配置管理器"""

    _config_cache: dict[str, AgentConfig] = {}

    @classmethod
    def register_agent_config(cls, **kwargs):
        """
        注册智能体配置
        :param kwargs: 智能体配置参数
        """
        pass

    @classmethod
    def get_config(cls, agent_code: str, api_client, force_refresh: bool = False) -> AgentConfig:
        """
        获取智能体配置
        :param agent_code: 智能体代码
        :param force_refresh: 是否强制刷新配置
        :param api_client: API客户端
        :return: AgentConfig实例
        """
        # 检查缓存中是否存在且不需要强制刷新
        if not force_refresh and agent_code in cls._config_cache:
            return cls._config_cache[agent_code]

        # 实时从AIDev平台拉取配置
        try:
            res = api_client.api.retrieve_agent_config(path_params={"agent_code": agent_code})["data"]
        except Exception as e:
            # 添加适当的错误处理或日志记录
            raise ValueError(f"Failed to retrieve agent config: {e}")

        # 处理特殊字段,兼容特殊role
        role_prompt = "\n".join(
            item["content"]
            for item in res["prompt_setting"]["content"]
            if item["role"] == "system" or item["role"] == "hidden-system"
        )

        # 创建配置实例
        # TODO: 待确认knowledge_ids如何配置&获取
        config = AgentConfig(
            agent_code=agent_code,
            agent_name=res["agent_name"],
            llm_model_name=res["prompt_setting"]["llm_code"],
            non_thinking_llm_model_name=res["prompt_setting"]["non_thinking_llm"] or "",
            role_prompt=role_prompt or None,
            knowledgebase_ids=res["knowledgebase_settings"]["knowledgebases"],
            tool_codes=res["related_tools"],
            opening_mark=res["conversation_settings"]["opening_remark"] or None,
        )

        # 更新缓存
        cls._config_cache[agent_code] = config
        return config
