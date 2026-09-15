"""业务结果表 Graph V4 option 中的 SurrealDBBinding 写入配置。"""

from pydantic import BaseModel, ConfigDict, Field


class GraphSurrealDBWriteConfig(BaseModel):
    """SurrealDBBinding.spec 中的图写入参数。"""

    model_config = ConfigDict(extra="forbid")

    timeout: int | None = Field(default=None, strict=True, gt=0, description="写入超时时间，单位秒")
    window: int | None = Field(default=None, strict=True, gt=0, description="顶点合并及关系有效窗口，单位秒")
    concurrency: int | None = Field(default=None, strict=True, gt=0, description="写入请求并发数")

    def binding_spec(self) -> dict:
        """返回需要合并到 SurrealDBBinding.spec 的显式配置。"""
        return self.model_dump(exclude_none=True)
