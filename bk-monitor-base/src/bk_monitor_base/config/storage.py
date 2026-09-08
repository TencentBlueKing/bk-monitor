from enum import Enum
from typing import Self, final

from pydantic import Field, model_validator

from .base import BaseConfigModel


@final
class StorageType(str, Enum):
    """存储类型"""

    BKREPO = "bkrepo"
    LOCAL = "local"


@final
class StorageName(str, Enum):
    """存储名称"""

    DEFAULT = "default"
    JOB = "job"
    BKMONITOR = "bkmonitor"


class BkRepoStorageConfig(BaseConfigModel):
    """蓝鲸仓库存储配置"""

    bucket: str = Field(title="存储桶")
    project: str = Field(title="项目代码")
    url: str = Field(title="仓库地址")
    username: str = Field(title="用户名")
    password: str = Field(title="密码")


class LocalStorageConfig(BaseConfigModel):
    """本地存储配置"""

    path: str = Field(title="存储路径")


class StorageConfig(BaseConfigModel):
    """存储配置

    支持的存储类型:
    - bkrepo: 蓝鲸仓库存储
    - local: 本地存储
    """

    type: StorageType = Field(default=StorageType.LOCAL, title="存储类型")
    bkrepo: BkRepoStorageConfig | None = Field(default=None, title="蓝鲸仓库存储配置")
    local: LocalStorageConfig | None = Field(default=LocalStorageConfig(path="media"), title="本地存储配置")

    @model_validator(mode="after")
    def check_storage_config(self) -> Self:
        """检查配置是否合法"""
        storage_config = getattr(self, self.type, None)
        if storage_config is None:
            raise ValueError(f"存储配置{self.type}不能为空")
        return self
