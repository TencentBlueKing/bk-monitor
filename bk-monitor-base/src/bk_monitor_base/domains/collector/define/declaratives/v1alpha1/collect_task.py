# pyright: reportIncompatibleVariableOverride=false
# pyright: reportAssignmentType=false
import uuid
from datetime import datetime
from typing import Any, ClassVar

from pydantic import Field

from bk_monitor_base.domains.collector.define.declaratives.enums import CollectType, TaskStatus
from bk_monitor_base.infras.declaratives.definitions import ApiVersion, Kind, Labels, Metadata, Resource, Spec, Status

from .collect import RemoteHost
from .version import PACKAGE_VERSION


class CollectTaskSpec(Spec):
    """Basic spec for collect"""

    interval: str = "60s"
    config_version: int = 1
    timeout: str = "60s"
    remote_collect_hosts: list[RemoteHost] = Field(default_factory=list, description="远程采集主机")
    plugin_runtime_param: list[dict[str, Any]] = Field(default_factory=list, description="插件运行配置")
    plugin_primary_id: int = Field(description="插件主键id")
    bk_biz_id: int | None = Field(default=None, description="原始下发主机所在业务")

    api_param: dict[str, Any] = Field(default_factory=dict, description="调用的api参数，可选")
    task_status: TaskStatus = Field(default=TaskStatus.DEPLOY_SUCCEED, description="期望本次下发实现的状态")


class CollectTaskStatus(Status):
    """Basic status"""

    task_status: TaskStatus
    message: str = Field(default="", description="采集任务运行详情")
    collect_enable: bool
    last_retry_time: int = 0
    deployed_spec_hash: str = Field(default="", description="下发到平台的配置，空表示没有下发或者为历史数据")
    deployed_at: datetime | None = Field(default=None, description="最后下发时间")
    delete_failures: int = Field(default=0, description="连续删除失败次数")


class CollectTaskLabels(Labels):
    type: CollectType = Field(description="采集类型，包括蓝鲸、硬件、sql等")
    collect_task_id: int | str = Field(default_factory=int, description="蓝鲸|作业-采集任务ID")
    config_uid: uuid.UUID = Field(description="对应的CollectConfig的uid")
    template_id: int = Field(description="对应的采集模板的id")

    def has_valid_collect_task_id(self):
        return str(self.collect_task_id) not in ["", "0"]


class CollectTaskMetadata(Metadata):
    """Metadata for a CollectTask"""

    labels: CollectTaskLabels = Field(default_factory=CollectTaskLabels.default)


class CollectTask(Resource):
    """采集任务"""

    kind: ClassVar[Kind] = Kind("CollectTask")
    api_version: ClassVar[ApiVersion] = ApiVersion(PACKAGE_VERSION)
    spec: CollectTaskSpec
    status: CollectTaskStatus
    metadata: CollectTaskMetadata
