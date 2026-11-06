from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class UptimeCheckTaskProtocol(str, Enum):
    """
    拨测任务协议
    """

    TCP = "TCP"
    UDP = "UDP"
    HTTP = "HTTP"
    ICMP = "ICMP"


class UptimeCheckNodeIPType(int, Enum):
    """拨测节点IP类型"""

    ALL = 0
    IPv4 = 4
    IPv6 = 6


class UptimeCheckTaskStatus(str, Enum):
    """拨测任务状态"""

    NEW_DRAFT = "new_draft"
    RUNNING = "running"
    STOPED = "stoped"
    STARTING = "starting"
    STOPING = "stoping"
    START_FAILED = "start_failed"
    STOP_FAILED = "stop_failed"


class UptimeCheckTask(BaseModel):
    """拨测任务定义"""

    bk_tenant_id: str = Field(title="租户ID", max_length=128)
    id: int | None = Field(title="任务ID", default=None)
    bk_biz_id: int = Field(title="业务ID")
    name: str = Field(title="任务名称", min_length=1, max_length=128)
    protocol: UptimeCheckTaskProtocol = Field(title="协议")
    config: dict[str, Any] = Field(title="配置")
    labels: dict[str, Any] | None = Field(title="标签", default_factory=dict)
    independent_dataid: bool = Field(
        title="独立业务数据ID", default=False, description="是否使用独立业务数据ID(需要兼容indepentent_dataid字段)"
    )
    check_interval: int = Field(title="拨测周期(分钟)", default=5)
    location: dict[str, str] = Field(title="地区", default_factory=dict)

    # 关联字段
    node_ids: list[int] = Field(title="拨测节点ID列表", default_factory=list)
    group_ids: list[int] = Field(title="拨测分组ID列表", default_factory=list)

    # 非配置字段
    status: UptimeCheckTaskStatus = Field(title="状态", default=UptimeCheckTaskStatus.NEW_DRAFT)
    create_user: str | None = Field(title="创建人", max_length=32, default=None)
    create_time: datetime | None = Field(title="创建时间", default_factory=datetime.now)
    update_user: str | None = Field(title="修改人", max_length=32, default=None)
    update_time: datetime | None = Field(title="更新时间", default_factory=datetime.now)


class UptimeCheckNode(BaseModel):
    """拨测节点定义"""

    bk_tenant_id: str = Field(title="租户ID", max_length=128)
    bk_biz_id: int = Field(title="所属业务ID")
    id: int | None = Field(title="节点ID", default=None)
    name: str = Field(title="节点名称", min_length=1, max_length=50)
    is_common: bool = Field(title="是否为通用节点", default=False)
    biz_scope: list[int] = Field(title="指定业务可见范围", default_factory=list)
    ip_type: UptimeCheckNodeIPType = Field(title="IP类型", default=UptimeCheckNodeIPType.IPv4)

    bk_host_id: int | None = Field(title="主机ID", default=None)
    ip: str | None = Field(title="IP地址", default=None)
    plat_id: int | None = Field(title="云区域ID", default=None)

    location: dict[str, str] = Field(
        title="地区", default_factory=dict, description="示例: {'country': '中国', 'city': '北京'}"
    )
    carrieroperator: str = Field(title="外网运营商", min_length=0, max_length=50)

    # 非配置字段
    create_user: str | None = Field(title="创建人", max_length=32, default=None)
    create_time: datetime | None = Field(title="创建时间", default_factory=datetime.now)
    update_user: str | None = Field(title="修改人", max_length=32, default=None)
    update_time: datetime | None = Field(title="更新时间", default_factory=datetime.now)

    @model_validator(mode="after")
    def check_node(self):
        """校验拨测节点

        bk_host_id和ip、plat_id不能同时为空
        """
        if not self.bk_host_id and (not self.ip and not self.plat_id):
            raise ValueError("bk_host_id和ip、plat_id不能同时为空")
        return self


class UptimeCheckGroup(BaseModel):
    """拨测分组定义"""

    bk_tenant_id: str = Field(title="租户ID", max_length=128)
    id: int | None = Field(title="分组ID", default=None)
    bk_biz_id: int = Field(title="业务ID", ge=0, description="0 表示全局分组")
    name: str = Field(title="分组名称", min_length=1, max_length=50)
    logo: str = Field(title="LOGO", default="", description="LOGO图片的base64形式")
    task_ids: list[int] = Field(title="拨测任务ID列表", default_factory=list)

    # 非配置字段
    create_user: str | None = Field(title="创建人", max_length=32, default=None)
    create_time: datetime | None = Field(title="创建时间", default_factory=datetime.now)
    update_user: str | None = Field(title="修改人", max_length=32, default=None)
    update_time: datetime | None = Field(title="更新时间", default_factory=datetime.now)
