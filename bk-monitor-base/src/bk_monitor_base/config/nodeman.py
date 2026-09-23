"""Base 的 NodeMan V3 控制面配置。"""

from typing import ClassVar

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from .base import BaseConfigSettings

NODEMAN_V3_GATEWAY_PATH = "api/bk-nodemgr/prod/"


class NodeManConfig(BaseConfigSettings):
    """集中解析 NodeMan V3 开关和可选地址覆盖。"""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(extra="ignore", validate_by_name=True)

    v3_enabled: bool = Field(default=False, validation_alias="BKAPP_ENABLE_NODEMAN_V3")
    v3_api_base_url: str = Field(default="", validation_alias="BKAPP_BKNODEMAN_V3_API_BASE_URL")

    def resolved_v3_api_base_url(self, bk_api_url: str) -> str:
        """优先使用可选的 V3 地址覆盖，否则从现有网关根地址推导。"""
        override = self.v3_api_base_url.strip()
        if override:
            return f"{override.rstrip('/')}/"
        return f"{bk_api_url.rstrip('/')}/{NODEMAN_V3_GATEWAY_PATH}"
