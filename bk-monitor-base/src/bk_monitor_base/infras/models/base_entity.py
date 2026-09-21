from datetime import datetime

from django.utils.timezone import now
from pydantic import BaseModel, ConfigDict, Field


class BaseEntity(BaseModel):
    created_at: datetime = Field(default_factory=now, description="创建时间")
    updated_at: datetime = Field(default_factory=now, description="更新时间")
    created_by: str = Field(default="系统", max_length=100, description="创建人")
    updated_by: str = Field(default="系统", max_length=100, description="修改人")

    model_config = ConfigDict(from_attributes=True, use_enum_values=True, validate_by_alias=True, validate_by_name=True)  # pyright: ignore[reportUnannotatedClassAttribute]
