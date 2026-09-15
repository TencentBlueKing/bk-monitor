"""业务结果表 Graph V4 option 中的 SurrealDBBinding 写入配置。"""

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GraphSurrealDBWriteConfig(BaseModel):
    """SurrealDBBinding.spec 中的图写入参数。"""

    model_config = ConfigDict(extra="forbid")

    timeout: int | None = Field(default=None, strict=True, gt=0, description="写入超时时间，单位秒")
    window: int | None = Field(default=None, strict=True, gt=0, description="顶点合并及关系有效窗口，单位秒")
    concurrency: int | None = Field(default=None, strict=True, gt=0, description="写入请求并发数")

    @classmethod
    def from_option_value(cls, value: Any) -> "GraphSurrealDBWriteConfig":
        """解析独立 ResultTableOption 中直接保存的 BKBase Binding 配置。"""
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, dict):
            raise TypeError("SurrealDBBinding 写入配置必须是对象")
        return cls.model_validate(value)
