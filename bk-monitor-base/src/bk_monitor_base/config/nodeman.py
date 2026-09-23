"""NodeMan V3 控制面路由配置，供监控 SaaS 和 Base 共用。"""

import os

NODEMAN_V3_GATEWAY_PATH = "api/bk-nodemgr/prod/"


def is_nodeman_v3_enabled() -> bool:
    """仅显式启用时切换控制面；未设置和 false 均保持 V2。"""
    return os.getenv("BKAPP_ENABLE_NODEMAN_V3", "false").lower() == "true"


def nodeman_v3_base_url(bk_api_url: str) -> str:
    """优先使用可选的 V3 地址覆盖，否则从现有网关根地址推导。"""
    override = os.getenv("BKAPP_BKNODEMAN_V3_API_BASE_URL", "").strip()
    if override:
        return f"{override.rstrip('/')}/"
    return f"{bk_api_url.rstrip('/')}/{NODEMAN_V3_GATEWAY_PATH}"
