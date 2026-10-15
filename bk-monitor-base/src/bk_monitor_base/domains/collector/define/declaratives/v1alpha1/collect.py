import uuid
from datetime import datetime
from ipaddress import IPv4Address
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from bk_monitor_base.domains.collector.define.declaratives.enums import CollectType, ReconcileStatus, TaskStatus
from bk_monitor_base.infras.caches.md5 import count_md5
from bk_monitor_base.infras.declaratives.definitions import ApiVersion, Kind, Labels, Metadata, Resource, Spec, Status
from bk_monitor_base.infras.declaratives.definitions.enums import BkGroupType, ObjectSelectType, OSType, TargetInstType

from .version import PACKAGE_VERSION


class PluginSpec(BaseModel):
    """Plugin Spec"""

    object: int = Field(description="插件主键id")
    id: str
    type: str
    version: int
    display_name: str | None = None
    is_support_remote: bool


class AssociatedHost(Spec):
    ip: IPv4Address | None = Field(default=None, description="关联实例的IP")
    bk_biz_id: int | None = Field(default=None, description="关联实例所在业务")
    bk_cloud_id: int | None = Field(default=None, description="关联实例所在云区域")


class RemoteHost(Spec):
    id: str = Field(description="远程主机id")
    ip: IPv4Address = Field(description="远程主机IP")
    bk_biz_id: int
    bk_host_id: int | None = Field(default=None)
    bk_os_type: str | None = Field(default=None, description="操作系统类型，数字字符串，Linux为1")
    bk_cloud_id: int
    model_config = ConfigDict(frozen=True)  # pyright: ignore[reportUnannotatedClassAttribute]


class RemoteCollectSpec(Spec):
    is_remote_collect: bool = Field(description="是否开启远程采集")
    remote_collect_hosts: list[RemoteHost] = Field(default_factory=list, description="远程采集主机")
    plugin_param: dict[str, Any] = Field(default_factory=dict, description="插件配置")

    @classmethod
    def default(cls):
        return cls(is_remote_collect=False)


class CollectSpec(Spec):
    """Basic spec for collect"""

    plugin: PluginSpec | None = None
    type: CollectType = CollectType.BK_PLUGIN_COLLECT
    interval: str = "60s"
    method: str = ""
    config_version: int = 1
    timeout: str = "60s"
    associated_host: AssociatedHost | None = Field(
        default_factory=lambda: AssociatedHost(), description="关联实例的主机信息"
    )
    remote_collect_info: RemoteCollectSpec = Field(
        default_factory=lambda: RemoteCollectSpec(is_remote_collect=False), description="远程采集信息"
    )
    plugin_runtime_param: list[dict[str, Any]] = Field(default_factory=list, description="插件运行配置")
    unique_id: str
    collect_enable: bool = True
    # retry_request_time: int = 0
    bk_obj_id: str | None = ""
    monitor_template_id: int = Field(description="监控模板ID")
    # 目标实例类型字段,用以判断下发配置时目标实例类型：主机 or 服务实例
    target_inst_type: TargetInstType = Field(default=TargetInstType.HOST)
    bk_biz_id: int | None = None
    is_skip: bool = Field(default=False, description="是否跳过该采集项的下发")

    @classmethod
    def default(cls):
        return cls(associated_host=None, unique_id="", monitor_template_id=-1, target_inst_type=TargetInstType.HOST)

    @property
    def spec_hash(self) -> str:
        """计算spec的校验码"""
        return count_md5(self.dict(exclude={"config_version"}))


class CollectStatus(Status):
    """Basic status"""

    meta_task_id: str = Field(default="", description="CollectTask的uid")
    bk_collect_task_id: str = "0"
    task_status: TaskStatus = TaskStatus.PENDING
    message: str = Field(default="", description="采集任务运行详情")
    retry_request_time: int = 0
    deployed_spec_hash: str = Field(default="", description="下发到平台的配置，空表示没有下发或者为历史数据")
    deployed_at: datetime | None = Field(default=None, description="完成部署的时间")
    reconcile_status: ReconcileStatus | None = None
    consecutive_failures: int = Field(default=0, description="任务连续失败次数")

    def has_valid_bk_collect_task_id(self):
        return self.bk_collect_task_id not in ["", "0"]


class CollectLabels(Labels):
    """Labels for a Collect"""

    monitor_template_id: int = Field(default=0, description="监控模板主键ID")
    config_id: uuid.UUID = Field(description="Set中采集配置ID")
    bk_object_code: str = Field(description="对象模型code")

    bk_os_type: str = OSType.LINUX
    # cmdb_event 获取的实例id
    final_inst_id: int | None = Field(description="最终下发实例id")
    final_ip: IPv4Address | None = Field(default=None, description="最终下发主机IP")
    final_biz_id: int | None = Field(default=None, description="最终下发主机所在业务")
    final_cloud_id: int | None = Field(default=None, description="最终下发主机所在云区域")

    plugin_primary_id: int = Field(default=0, description="插件主键ID")
    plugin_type: str = Field(default="", description="插件类型")
    plugin_id: str = Field(default="", description="插件ID, 功能实际为插件code")

    # 确定任务所属模板关联实例
    bk_inst_id: int = Field(description="关联实例id")  # 模板关联实例如果是组类型，则表示组内包含的某实例id
    bk_group_id: int | None = Field(default=None, description="实例所属组id")
    bk_group_type: BkGroupType | None = Field(default=None, description="实例所属组类型")

    collect_enable: bool

    @property
    def inst_obj_source(self):
        # 获取INST解析来源
        if self.bk_group_type == BkGroupType.GROUP:
            return f"{BkGroupType.GROUP}-{self.bk_group_id}"
        elif self.bk_group_type == BkGroupType.TOPO:
            return f"{BkGroupType.TOPO}-{self.bk_group_id}"
        elif self.bk_group_type == BkGroupType.TOPO_SERVICE:
            return BkGroupType.TOPO_SERVICE
        elif self.bk_group_type == BkGroupType.SERVICE_TEMPLATE:
            return BkGroupType.SERVICE_TEMPLATE
        elif self.bk_group_type == BkGroupType.SET_TEMPLATE:
            return BkGroupType.SET_TEMPLATE
        else:
            return ObjectSelectType.INST

    @classmethod
    def default(cls):  # pyright: ignore[reportImplicitOverride]
        return CollectLabels(
            config_id=uuid.uuid4(),
            bk_object_code="",
            bk_inst_id=0,
            final_inst_id=0,
            collect_enable=False,
        )


class CollectMetadata(Metadata):
    """Metadata for a Collect"""

    labels: CollectLabels = Field(default_factory=CollectLabels.default)


class CollectConfig(Resource):
    """Basic Collect"""

    kind: ClassVar[Kind] = Kind("Collect")
    api_version: ClassVar[ApiVersion] = ApiVersion(PACKAGE_VERSION)
    spec: CollectSpec
    status: CollectStatus = Field(default_factory=CollectStatus)
    metadata: CollectMetadata
    deployed_spec_hash: str = Field(default="", description="下发到平台的配置，空表示没有下发或者为历史数据")
    deployed_at: datetime | None = Field(default=None, description="最后下发时间")
