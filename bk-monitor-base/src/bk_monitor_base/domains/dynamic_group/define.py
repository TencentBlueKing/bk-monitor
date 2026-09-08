from typing import Any

from pydantic import Field

from bk_monitor_base.infras.models.base_entity import BaseEntity


class DynamicGroup(BaseEntity):
    """
    动态分组（底座层实体）

    纯粹的领域实体，只包含核心业务字段，不包含UI展示或API特定字段。
    场景层可以继承此类并添加额外字段。
    """

    dynamic_group_id: int | None = Field(description="动态分组主键", default=None)
    dynamic_group_name: str = Field(description="动态分组名称", min_length=1, max_length=255)
    condition_list: list[dict[str, Any]] = Field(description="分组条件列表", default_factory=list)
    object_model_code: str = Field(description="对象模型英文标识", min_length=1, max_length=255)
    space_code: str = Field(description="权限空间code", default="", max_length=128)
    bk_tenant_id: str = Field(description="租户ID", default="system", max_length=64)
    # 关联实例数量
    member_count: int = Field(description="成员数量", default=0)

    def get_bk_biz_id(self) -> int:
        """
        从空间编码中提取业务ID

        :return: 业务ID
        :raises ValueError: 空间编码格式不正确时抛出异常
        """
        if not self.space_code:
            raise ValueError("dynamic group space_code is null")
        parts = self.space_code.split("__")
        if len(parts) != 2:
            raise ValueError(f"invalid space_code format: {self.space_code}")
        return int(parts[1])


class DynamicGroupQueryFilter(BaseEntity):
    """
    动态分组查询过滤条件
    """

    dynamic_group_ids: list[int] = Field(description="动态分组ID列表", default_factory=list)
    space_codes: list[str] = Field(description="空间编码列表", default_factory=list)
    name_keywords: list[str] = Field(description="名称关键词列表(并集查询)", default_factory=list)
    dynamic_group_names: list[str] = Field(description="动态分组名称列表(精确匹配)", default_factory=list)
    object_model_code: str | None = Field(description="对象模型编码", default=None)
    is_return_member_list: bool = Field(description="是否返回成员列表", default=False)
    page: int = Field(description="页码", default=1, ge=1)
    page_size: int = Field(description="每页数量", default=20, ge=1, le=1000)


class DynamicGroupPermission(BaseEntity):
    """
    动态分组权限信息
    """

    edit_allowed: bool = Field(description="是否允许编辑", default=True)
    edit_message: str = Field(description="编辑限制原因", default="")
    delete_allowed: bool = Field(description="是否允许删除", default=True)
    delete_message: str = Field(description="删除限制原因", default="")


class DynamicGroupMember(BaseEntity):
    """
    动态分组成员
    """

    id: int | None = Field(description="主键", default=None)
    dynamic_group_id: int = Field(description="动态分组id")
    member: dict[str, Any] = Field(description="分组成员", default_factory=dict)
