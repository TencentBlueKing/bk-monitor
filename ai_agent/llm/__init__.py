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
import os
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Union

from django.conf import settings
from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI


class LLMProvider(Enum):
    """大语言模型提供商"""

    ZHIPU = "zhipuai"
    HUNYUAN = "hunyuan"
    DEEPSEEK = "deepseek"
    SILICON_FLOW = "silicon_flow"
    BLUEKING = "blueking"


class LLMModel(Enum):
    """大语言模型"""

    GLM_4_PLUS = "GLM-4-Plus"
    GLM_4_AIR = "GLM-4-Air"
    GLM_4_AIR_0111 = "GLM-4-Air-0111"
    HUNYUAN_TURBO = "hunyuan-turbo"
    DEEPSEEK_CHAT = "deepseek-chat"
    SILICON_FLOW_DEEPSEEK_V3 = "deepseek-ai/DeepSeek-V3"


@dataclass
class LLMConfig:
    """大语言模型配置类，用于管理不同 LLM 服务商的配置信息。

    Attributes:
        provider (Provider): LLM 服务提供商，当前支持：
            - ZHIPU: 智谱 AI, api_key 环境变量: ZHIPU_API_KEY
            - HUNYUAN: 腾讯混元, api_key 环境变量: HUNYUAN_API_KEY
            - DEEPSEEK: DeepSeek, api_key 环境变量: DEEPSEEK_API_KEY
            - SILICON_FLOW: 硅基流动, api_key 环境变量: SILICON_FLOW_API_KEY
        model (str): 使用的模型名称，需要根据不同服务商提供的模型选择
        temperature (float): 采样温度参数，控制输出的随机性：
            - 0: 输出最确定性的结果
            - 1: 输出最具创造性的结果
            默认值为 0
        api_key (Optional[str]): API 访问密钥：
            - 如果提供，直接使用该值
            - 如果为 None，将从环境变量中读取
        base_url (Optional[str]): API 服务的基础 URL：
            - 如果提供，直接使用该值
            - 如果为 None，将使用服务商的默认地址
    """

    provider: LLMProvider
    model: Union[str, LLMModel]
    temperature: float = 0
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    callbacks: Optional[List[BaseCallbackHandler]] = None


def get_llm(config: LLMConfig) -> ChatOpenAI:
    """
    获取大语言模型实例
    """
    model = config.model
    if isinstance(model, LLMModel):
        model = model.value

    if config.provider == LLMProvider.ZHIPU:
        api_key_env = "ZHIPU_API_KEY"
        base_url = "https://open.bigmodel.cn/api/paas/v4/"
    elif config.provider == LLMProvider.HUNYUAN:
        api_key_env = "HUNYUAN_API_KEY"
        base_url = "https://api.hunyuan.cloud.tencent.com/v1"
    elif config.provider == LLMProvider.DEEPSEEK:
        api_key_env = "DEEPSEEK_API_KEY"
        base_url = "https://api.deepseek.com/v1"
    elif config.provider == LLMProvider.SILICON_FLOW:
        api_key_env = "SILICON_FLOW_API_KEY"
        base_url = "https://api.siliconflow.cn/v1"
    elif config.provider == LLMProvider.BLUEKING:
        config.api_key = "empty"
        base_url = f"{settings.AIDEV_API_BASE_URL}/appspace/gateway/llm/v1"
        default_headers = {
            "x-bkapi-authorization": json.dumps(
                {
                    "bk_app_code": settings.BK_PLUGIN_APP_INFO.get("bk_app_code", settings.APP_CODE),
                    "bk_app_secret": settings.BK_PLUGIN_APP_INFO.get("bk_app_secret", settings.SECRET_KEY),
                    "bk_username": "admin",
                }
            )
        }
    else:
        raise ValueError(f"Invalid provider: {config.provider}")

    if not config.api_key:
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ValueError(f"{api_key_env} is not set")
    else:
        api_key = config.api_key

    kwargs = {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "temperature": config.temperature,
    }

    if default_headers:
        kwargs["default_headers"] = default_headers

    if config.callbacks:
        kwargs["callbacks"] = config.callbacks

    llm = ChatOpenAI(**kwargs)

    return llm
