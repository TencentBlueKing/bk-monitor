import datetime
import enum
from typing import Literal, NotRequired

import pydantic
from typing_extensions import TypedDict


class SpaceTypeEnum(str, enum.Enum):
    """空间类型枚举"""

    BKCC = "bkcc"
    BCS = "bcs"
    BKCI = "bkci"
    BKSAAS = "bksaas"
    DEFAULT = "default"
    ALL = "all"


class SpaceStatus(str, enum.Enum):
    """空间状态枚举"""

    NORMAL = "normal"
    DISABLED = "disabled"


# 空间类型名称映射
space_type_name_map = {
    SpaceTypeEnum.BKCC: "蓝鲸业务",
    SpaceTypeEnum.BCS: "容器项目",
    SpaceTypeEnum.BKCI: "研发项目",
    SpaceTypeEnum.BKSAAS: "SaaS应用",
    SpaceTypeEnum.DEFAULT: "监控项目",
    SpaceTypeEnum.ALL: "全部",
}


class RelationCluster(TypedDict):
    """
    关联的集群信息
    """

    # 集群ID
    cluster_id: str
    # 集群命名空间列表，如果为空，则表示全部命名空间
    namespaces: list[str]
    # 集群类型, shared: 共享集群, standalone: 独立集群
    cluster_type: Literal["shared", "standalone"]


class SpaceConfig(TypedDict):
    """
    空间配置
    """

    # 关联的BCS项目ID列表, BKCC空间关联BCS项目
    relation_bcs_project_ids: NotRequired[list[str]]
    # 关联的蓝鲸业务ID，BKCI空间关联的BKCI业务
    relation_bk_biz_id: NotRequired[int]
    # 关联的集群信息, BKCI/BKSaaS空间关联的集群
    relation_clusters: NotRequired[list[RelationCluster]]


class Space(pydantic.BaseModel):
    """空间对象"""

    bk_biz_id: int = pydantic.Field(title="蓝鲸业务ID", description="蓝鲸业务ID，BKCC是业务ID，其他类型是空间ID取负值")
    uid: str = pydantic.Field(
        title="空间ID", max_length=128, pattern=r"^.*__.*$", description="空间UID，格式为 space_type_id__space_id"
    )
    bk_tenant_id: str = pydantic.Field(title="蓝鲸租户ID", max_length=64, min_length=1)
    type: SpaceTypeEnum = pydantic.Field(title="空间类型")
    name: str = pydantic.Field(title="空间名称", max_length=128, min_length=1)
    status: SpaceStatus = pydantic.Field(title="空间状态")
    timezone: str = pydantic.Field(title="时区", default="Asia/Shanghai", min_length=1)
    language: str = pydantic.Field(title="语言", default="zh-cn", min_length=1)
    configs: SpaceConfig = pydantic.Field(title="空间配置", default={})
    is_global: bool = pydantic.Field(title="是否是全局空间", default=False)

    creator: str = pydantic.Field("", title="创建者", max_length=64)
    create_time: datetime.datetime | None = pydantic.Field(None, title="创建时间")
    updater: str = pydantic.Field("", title="更新者", max_length=64)
    update_time: datetime.datetime | None = pydantic.Field(None, title="更新时间")

    @pydantic.computed_field
    def type_name(self) -> str:
        """
        空间类型名称
        """
        return space_type_name_map[self.type]
