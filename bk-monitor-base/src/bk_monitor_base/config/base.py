"""
配置基类

提供统一的配置基类，自动支持忽略多余字段。
所有配置类应继承这些基类，而不是直接继承 pydantic 的 BaseModel 或 BaseSettings。
"""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseConfigModel(BaseModel):
    """
    配置模型基类

    自动设置 extra="ignore"，允许配置文件中存在未定义的字段。
    所有继承自 BaseModel 的配置类都应使用此类作为基类。
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", populate_by_name=True)


class BaseConfigSettings(BaseSettings):
    """
    配置设置基类

    自动设置 extra="ignore"，允许配置文件中存在未定义的字段。
    所有继承自 BaseSettings 的配置类都应使用此类作为基类。
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(extra="ignore")
