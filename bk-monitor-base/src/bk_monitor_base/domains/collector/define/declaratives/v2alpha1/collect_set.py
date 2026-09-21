import uuid
from ipaddress import IPv4Address
from typing import Any, ClassVar

from pydantic import Field
from typing_extensions import deprecated, override

from bk_monitor_base.domains.collector.define.declaratives.enums import (
    CollectSetTaskStatus,
    CollectType,
    ReconcileStatus,
)
from bk_monitor_base.infras.declaratives.definitions import ApiVersion, Kind, Labels, Metadata, Resource, Spec, Status
from bk_monitor_base.infras.declaratives.definitions.enums import ObjectSelectType, OSType, TargetInstType

from .collect import CollectLabels, PluginSpec, RemoteCollectSpec
from .version import PACKAGE_VERSION


@deprecated("Inst类似乎并没有使用， 在CollectSet中用 CollectLabels 也不符合设计")
class Inst(Spec):
    labels: CollectLabels
    ip: IPv4Address | None = Field(description="原始下发主机IP")
    plugin_runtime_param: list[dict[str, Any]] = Field(default_factory=list, description="插件运行配置")
    unique_id: str = Field(default="", description="分组后实例标识")
    collect_enable: bool = True
    retry_request_time: int = 0


class Target(Spec):
    # note: 在TOPO就是动态分组ID, 在INST中就是实例ID, 在分组中就是分组ID
    id: int
    target_type: ObjectSelectType | None = None
    collect_params: list[dict[str, Any]] = Field(default_factory=list, description="插件运行时配置")
    collect_enable: bool = True
    retry_request_time: int = 0

    bk_biz_id: int | None
    object_model_code: str
    # 目标实例类型字段，用以判断下发配置时目标实例类型：主机实例 or 服务实例
    target_inst_type: TargetInstType = Field(default=TargetInstType.HOST)


class SingleInst(Target):
    """单实例目标"""

    target_type: ObjectSelectType | None = ObjectSelectType.INST
    ip: IPv4Address | None = Field(default=None, description="下发主机IP")
    bk_cloud_id: int | None
    bk_os_type: str = OSType.LINUX
    bk_inst_id: int


class Topo(Target):
    """拓扑目标"""

    target_type: ObjectSelectType | None = ObjectSelectType.TOPO
    pk_id: str
    bk_obj_id: str
    bk_inst_id: int
    dynamic_topo_id: int


class Group(Target):
    """动态分组目标"""

    target_type: ObjectSelectType | None = ObjectSelectType.GROUP
    dynamic_group_id: int


class ServiceTemplate(Target):
    """服务模板目标"""

    target_type: ObjectSelectType | None = ObjectSelectType.SERVICE_TEMPLATE
    service_template_id: int


class SetTemplate(Target):
    """集群模板目标"""

    target_type: ObjectSelectType | None = ObjectSelectType.SET_TEMPLATE
    set_template_id: int


class MonitorTargetSpec(Spec):
    inst_list: list[SingleInst]
    topo_list: list[Topo]
    group_list: list[Group]
    service_template_list: list[ServiceTemplate] = Field(default_factory=list)
    set_template_list: list[SetTemplate] = Field(default_factory=list)


class PluginConfigSpec(Spec):
    """Plugin Config Spec"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="采集配置id")
    plugin: PluginSpec | None = None
    remote_collect_info: RemoteCollectSpec = Field(description="远程采集信息")
    collect_type: CollectType = CollectType.BK_PLUGIN_COLLECT
    interval: str = "60s"
    method: str = ""
    config_version: int = 1
    timeout: str = "60s"


class CollectSetSpec(Spec):
    """spec for collect set"""

    monitor_template_id: int = Field(description="监控模板ID")
    plugins: list[PluginConfigSpec]
    monitor_targets: MonitorTargetSpec | None = None
    # 强制对CollectConfig应用collectSet的collect_enable状态
    force_update_collect: bool = False


class CollectSetStatus(Status):
    """Basic status"""

    task_status: CollectSetTaskStatus | None = None
    message: str = Field(default="", description="采集任务集合运行详情")
    reconcile_status: ReconcileStatus | None = None  # 协调状态；当前用于限制页面编辑采集任务


class CollectSetLabels(Labels):
    """Labels for a Collect"""

    monitor_template_id: int = Field(description="监控模板ID")

    @classmethod
    @override
    def default(cls):
        return cls(monitor_template_id=0)


class CollectSetMetadata(Metadata):
    """Metadata for a Collect"""

    labels: CollectSetLabels = Field(default_factory=CollectSetLabels.default)


class CollectSetConfig(Resource):
    """Basic CollectSet"""

    kind: ClassVar[Kind] = Kind("CollectSet")
    api_version: ClassVar[ApiVersion] = PACKAGE_VERSION
    spec: CollectSetSpec
    status: CollectSetStatus = Field(default_factory=CollectSetStatus)
    metadata: CollectSetMetadata

    @override
    @classmethod
    def validate_filters(cls, filters: dict[str, Any]) -> None:
        if not ("uid" in filters or "monitor_template_id" in filters):
            raise ValueError("CollectSet requires at least 'uid' or 'monitor_template_id' as filter")


__all__ = [
    "CollectSetConfig",
    "CollectSetLabels",
    "CollectSetMetadata",
    "CollectSetSpec",
    "CollectSetStatus",
    "Group",
    "Inst",
    "MonitorTargetSpec",
    "PluginConfigSpec",
    "ServiceTemplate",
    "SetTemplate",
    "SingleInst",
    "Target",
    "Topo",
]
