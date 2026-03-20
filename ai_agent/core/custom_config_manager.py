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
import time
import logging
import requests
import os
from aidev_agent.services.config_manager import AgentConfigManager, AgentConfig, CachedEntry

from aidev_agent.api.abstract_client import AbstractBKAidevResourceManager
from aidev_agent.services.pydantic_models import AgentOptions, IntentRecognition, KnowledgebaseSettings
from bkoauth.django_conf import ENV_NAME
from blueapps.utils.request_provider import get_local_request
from bkoauth.utils import get_client_ip
from django.core.cache import cache as django_cache

logger = logging.getLogger("ai_whale")

# TODO：内部版本使用BKOAUTH 社区版本使用SSM,后续统一迁移至BKAuth
ACCESS_TOKEN_OAUTH_API_URL = os.environ.get("BK_ACCESS_TOKEN_OAUTH_API_URL")  # OAUTH API URL

ENV_MODE = os.environ.get("BKAPP_ENVIRONMENT_CODE", "open")  # 运行环境

MCP_AUTHENTICATION_APP_CODE = os.environ.get("BK_MCP_AUTHENTICATION_APP_CODE", "")  # MCP认证 APP_CODE
MCP_AUTHENTICATION_APP_SECRET = os.environ.get("BK_MCP_AUTHENTICATION_APP_SECRET", "")  # MCP认证 APP_SECRET

MCP_TOKEN_CACHE_PREFIX = "mcp_access_token"
MCP_TOKEN_DEFAULT_EXPIRES_IEOD = 15552000  # ieod: 180 天
MCP_TOKEN_DEFAULT_EXPIRES_OPEN = 43200  # open/SSM: 12 小时
MCP_TOKEN_REFRESH_BUFFER_IEOD = 86400  # ieod: 距过期不足 1 天时触发续期
MCP_TOKEN_REFRESH_BUFFER_OPEN = 3600  # open: 距过期不足 1 小时时触发续期


def _get_username_from_request(request):
    """从 request 中提取用户名，用于缓存 key"""
    return (
        getattr(getattr(request, "user", None), "username", None)
        or request.COOKIES.get("bk_uid", "")
        or request.session.get("bk_uid", "")
        or "unknown"
    )


# -------------------- ieod（内部上云版）BKOAUTH -------------------- #


def _create_access_token_ieod(request, oauth_api_url=ACCESS_TOKEN_OAUTH_API_URL):
    """
    获取用户 access_token 凭证（内部版）
    显式传 need_new_token=0：若当前 Token 有效且剩余 > 300s 则直接返回，不重新生成
    """
    logger.info("_create_access_token_ieod: try to get access_token, using ieod env_mode")
    OAUTH_COOKIES_PARAMS = {"bk_ticket": "bk_ticket", "rtx": "bk_uid"}
    auth_params = dict()
    for k, v in OAUTH_COOKIES_PARAMS.items():
        auth_params[k] = request.COOKIES.get(v) or request.session.get(v) or request.GET.get(v, "")

    params = {
        "app_code": MCP_AUTHENTICATION_APP_CODE,
        "app_secret": MCP_AUTHENTICATION_APP_SECRET,
        "bk_client_ip": get_client_ip(request),
        "grant_type": "authorization_code",
        "env_name": ENV_NAME,
        "need_new_token": 0,
        **auth_params,
    }

    resp = requests.get(oauth_api_url, params=params, timeout=30, verify=False)
    result = resp.json()

    if not result.get("result"):
        raise Exception(f"获取access_token失败: {result.get('message', '')}")

    return result["data"]


def _refresh_access_token_ieod(refresh_token, oauth_api_url=ACCESS_TOKEN_OAUTH_API_URL):
    """
    使用 refresh_token 续期 access_token（内部版 BKOAUTH）
    GET /auth_api/refresh_token/?app_code=...&refresh_token=...&env_name=...&grant_type=refresh_token&need_new_token=0
    """
    refresh_url = oauth_api_url.rstrip("/").rsplit("/token", 1)[0] + "/refresh_token/"

    params = {
        "app_code": MCP_AUTHENTICATION_APP_CODE,
        "refresh_token": refresh_token,
        "env_name": ENV_NAME,
        "grant_type": "refresh_token",
        "need_new_token": 0,
    }

    resp = requests.get(refresh_url, params=params, timeout=30, verify=False)
    result = resp.json()
    if not result.get("result"):
        raise Exception(f"刷新access_token失败: {result.get('message', '')}")
    return result["data"]


# -------------------- open（外部版）SSM -------------------- #


def _create_access_token_open(request, oauth_api_url=ACCESS_TOKEN_OAUTH_API_URL):
    """
    获取用户 access_token 凭证（外部版）
    SSM 接口为 create-or-update 语义，未过期时返回已有 Token
    """
    logger.info("_create_access_token_open: try to get access_token, using open env_mode")
    OAUTH_COOKIES_PARAMS = {"bk_token": "bk_token"}
    auth_params = dict()
    for k, v in OAUTH_COOKIES_PARAMS.items():
        auth_params[k] = request.COOKIES.get(v) or request.session.get(v) or request.GET.get(v, "")

    payload = {
        "grant_type": "authorization_code",
        "id_provider": "bk_login",
        **auth_params,
    }

    headers = {
        "X-Bk-App-Code": MCP_AUTHENTICATION_APP_CODE,
        "X-Bk-App-Secret": MCP_AUTHENTICATION_APP_SECRET,
    }
    resp = requests.post(url=oauth_api_url, json=payload, headers=headers, timeout=30, verify=False)
    result = resp.json()
    if result.get("code") != 0:
        raise Exception(f"获取access_token失败: {result.get('message', '')}")
    return result["data"]


def _refresh_access_token_open(refresh_token, oauth_api_url=ACCESS_TOKEN_OAUTH_API_URL):
    """
    使用 refresh_token 续期 access_token（外部版 SSM）
    POST /api/v1/auth/access-tokens/refresh
    """
    refresh_url = oauth_api_url.rstrip("/") + "/refresh"

    headers = {
        "X-Bk-App-Code": MCP_AUTHENTICATION_APP_CODE,
        "X-Bk-App-Secret": MCP_AUTHENTICATION_APP_SECRET,
    }
    payload = {"refresh_token": refresh_token}

    resp = requests.post(url=refresh_url, json=payload, headers=headers, timeout=30, verify=False)
    result = resp.json()
    if result.get("code") != 0:
        raise Exception(f"刷新access_token失败: {result.get('message', '')}")
    return result["data"]


# -------------------- 统一缓存 + 续期逻辑 -------------------- #


def _get_or_refresh_mcp_token(request):
    """
    带缓存和续期的 MCP Token 获取核心逻辑：
    1. 优先从缓存读取，未过期直接返回
    2. 临近过期时尝试 refresh_token 续期（ieod / open 各自走对应的刷新接口）
    3. 以上均不可用则重新生成（ieod 带 need_new_token=0，open 为 create-or-update 语义）
    """
    username = _get_username_from_request(request)
    is_ieod = ENV_MODE == "ieod"
    env = "ieod" if is_ieod else "open"
    cache_key = f"{MCP_TOKEN_CACHE_PREFIX}:{env}:{username}"
    default_expires = MCP_TOKEN_DEFAULT_EXPIRES_IEOD if is_ieod else MCP_TOKEN_DEFAULT_EXPIRES_OPEN
    refresh_buffer = MCP_TOKEN_REFRESH_BUFFER_IEOD if is_ieod else MCP_TOKEN_REFRESH_BUFFER_OPEN

    cached = django_cache.get(cache_key)
    if cached:
        remaining = cached.get("expires_at", 0) - time.time()
        if remaining > refresh_buffer:
            logger.info(
                "_get_or_refresh_mcp_token: cache hit for user [%s], remaining [%d]s",
                username,
                int(remaining),
            )
            return cached

        if cached.get("refresh_token"):
            try:
                logger.info("_get_or_refresh_mcp_token: refreshing token for user [%s] (env: %s)", username, env)
                if is_ieod:
                    data = _refresh_access_token_ieod(cached["refresh_token"])
                else:
                    data = _refresh_access_token_open(cached["refresh_token"])
                token_info = {
                    "access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token", cached.get("refresh_token")),
                    "expires_at": time.time() + data.get("expires_in", default_expires),
                }
                cache_ttl = max(int(data.get("expires_in", default_expires)) - 60, 60)
                django_cache.set(cache_key, token_info, cache_ttl)
                return token_info
            except Exception as e:
                logger.warning(
                    "_get_or_refresh_mcp_token: refresh failed for user [%s]: %s, will regenerate",
                    username,
                    e,
                )

    logger.info("_get_or_refresh_mcp_token: generating new token for user [%s] (env: %s)", username, env)
    if is_ieod:
        data = _create_access_token_ieod(request)
    else:
        data = _create_access_token_open(request)

    expires_in = data.get("expires_in", default_expires)
    token_info = {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token"),
        "expires_at": time.time() + expires_in,
    }
    cache_ttl = max(int(expires_in) - 60, 60)
    django_cache.set(cache_key, token_info, cache_ttl)
    return token_info


def _get_mcp_auth_info(request):
    """
    获取MCP认证信息（使用缓存版本）
    """
    return {
        "app_code": MCP_AUTHENTICATION_APP_CODE,
        "app_secret": MCP_AUTHENTICATION_APP_SECRET,
        "access_token": get_mcp_access_token(request),
    }


def get_mcp_access_token(request):
    """
    获取用户 access_token 凭证（带缓存和续期）
    """
    token_info = _get_or_refresh_mcp_token(request)
    return token_info["access_token"]


class CustomConfigManager(AgentConfigManager):
    @classmethod
    def get_config(
        cls, agent_code: str, resource_manager: AbstractBKAidevResourceManager, force_refresh: bool = False, **kwargs
    ) -> AgentConfig:
        """
        获取智能体配置
        :param agent_code: 智能体代码
        :param force_refresh: 是否强制刷新配置
        :param resource_manager: API客户端
        :return: AgentConfig实例
        """
        # 检查缓存中是否存在且不需要强制刷新
        if not force_refresh and agent_code in cls._config_cache:
            cached_entry = cls._config_cache[agent_code]
            # 检查缓存是否过期
            if not cached_entry.is_expired(cls.CACHE_TTL):
                return cached_entry.config
            # 如果过期，从缓存中删除
            del cls._config_cache[agent_code]

        # 实时从AIDev平台拉取配置
        try:
            res = resource_manager.retrieve_agent_config(agent_code)
        except Exception as e:
            # 添加适当的错误处理或日志记录
            raise ValueError(f"Failed to retrieve agent config: {e}")

        # 处理特殊字段,兼容特殊role
        role_prompt = "\n".join(
            item["content"]
            for item in res["prompt_setting"]["content"]
            if item["role"] == "system" or item["role"] == "hidden-system"
        )

        # 远端MCP Server配置
        request = get_local_request()  # 获取当前请求
        mcp_server_config = res.get("mcp_server_config", {}).get("mcpServers", {})
        for mcp_server, mcp_config in mcp_server_config.items():
            mcp_config.pop("credential_type", None)
            # mcp_config["headers"] = json.dumps(_get_mcp_auth_info(request))
            # 自定义请求头,鉴权+区分请求来源
            # 从 mcp_server key 中提取权限点,例如: bkop-bcs-metadata -> using_bcs_metadata_mcp
            permission_action = f"using_{mcp_server.split('-', 1)[1].replace('-', '_')}_mcp"
            mcp_config["headers"] = {
                "X-Bk-Request-Source": "bkm-mcp-client",
                "X-Bkapi-Allowed-Headers": "X-Bk-Request-Source,X-Bkapi-Permission-Action",
                "X-Bkapi-Authorization": json.dumps(_get_mcp_auth_info(request)),
                "X-Bkapi-Permission-Action": permission_action,
            }
        # 需要自定义重写鉴权Headers和特殊标识Headers

        # 创建配置实例
        config = AgentConfig(
            agent_code=agent_code,
            agent_name=res["agent_name"],
            llm_model_name=res["prompt_setting"]["llm_code"],
            non_thinking_llm_model_name=res["prompt_setting"]["non_thinking_llm"] or "",
            role_prompt=role_prompt or None,
            knowledgebase_ids=res["knowledgebase_settings"]["knowledgebases"],
            tool_codes=res["related_tools"],
            opening_mark=res["conversation_settings"]["opening_remark"] or None,
            mcp_server_config=mcp_server_config,
            agent_options=AgentOptions(
                intent_recognition_options=IntentRecognition.model_validate(res.get("intent_recognition", {})),
                knowledge_query_options=KnowledgebaseSettings.model_validate(res.get("knowledgebase_settings", {})),
            ),
            command_agent_mapping={
                each["id"]: each["agent_code"] for each in res["conversation_settings"].get("commands", [])
            },
        )

        # 更新缓存
        cls._config_cache[agent_code] = CachedEntry(config, time.time())
        return config
