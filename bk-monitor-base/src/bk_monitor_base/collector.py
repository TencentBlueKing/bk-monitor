from bk_monitor_base.domains.collector.define.declaratives.enums import (
    DISABLE_RETRY_STATUS_SET,
    EXCLUDE_BLUEKING_COLLECT_MAPPING,
    FAILED_STATUS_SET,
    INTERMEDIATE_STATUS_SET,
    SUCCEED_TASK_STATUS_TO_FAILED,
    SUCCESS_STATUS_SET,
    BkMonitorTaskStatus,
    BkTaskAction,
    BkTaskStatus,
    BkTaskStatusMap,
    CollectSetTaskStatus,
    CollectType,
    JobStatus,
    ObjectModelEnum,
    PluginType,
    ReconcileStatus,
    SaveCollectApi,
    TargetNodeType,
    TargetObjectType,
    TaskAction,
    TaskStatus,
    TaskToggleStatus,
)
from bk_monitor_base.domains.collector.define.declaratives.v1alpha1.collect import (
    AssociatedHost,
    CollectConfig,
    CollectLabels,
    CollectMetadata,
    CollectSpec,
    CollectStatus,
    PluginSpec,
    RemoteCollectSpec,
    RemoteHost,
)
from bk_monitor_base.domains.collector.define.declaratives.v1alpha1.collect_set import (
    CollectSetConfig,
    CollectSetLabels,
    CollectSetMetadata,
    CollectSetSpec,
    CollectSetStatus,
    Group,
    Inst,
    MonitorTargetSpec,
    PluginConfigSpec,
    ServiceTemplate,
    SetTemplate,
    SingleInst,
    Target,
    Topo,
)
from bk_monitor_base.domains.collector.define.declaratives.v1alpha1.collect_task import (
    CollectTask,
    CollectTaskLabels,
    CollectTaskMetadata,
    CollectTaskSpec,
    CollectTaskStatus,
)
from bk_monitor_base.domains.collector.define.declaratives.v1alpha1.version import PACKAGE_VERSION
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect import AssociatedHost as AssociatedHostV2
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect import CollectConfig as CollectConfigV2
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect import CollectLabels as CollectLabelsV2
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect import CollectMetadata as CollectMetadataV2
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect import CollectSpec as CollectSpecV2
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect import CollectStatus as CollectStatusV2
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect import PluginSpec as PluginSpecV2
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect import (
    RemoteCollectSpec as RemoteCollectSpecV2,
)
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect import RemoteHost as RemoteHostV2
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect_set import (
    CollectSetConfig as CollectSetConfigV2,
)
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect_set import (
    CollectSetLabels as CollectSetLabelsV2,
)
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect_set import (
    CollectSetMetadata as CollectSetMetadataV2,
)
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect_set import (
    CollectSetSpec as CollectSetSpecV2,
)
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect_set import (
    CollectSetStatus as CollectSetStatusV2,
)
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect_set import Group as GroupV2
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect_set import Inst as InstV2
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect_set import (
    MonitorTargetSpec as MonitorTargetSpecV2,
)
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect_set import (
    PluginConfigSpec as PluginConfigSpecV2,
)
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect_set import (
    ServiceTemplate as ServiceTemplateV2,
)
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect_set import SetTemplate as SetTemplateV2
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect_set import SingleInst as SingleInstV2
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect_set import Target as TargetV2
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.collect_set import Topo as TopoV2
from bk_monitor_base.domains.collector.define.declaratives.v2alpha1.version import PACKAGE_VERSION as PACKAGE_VERSION_V2

__all__ = [
    # collector
    "CollectConfig",
    "CollectMetadata",
    "CollectLabels",
    "CollectStatus",
    "CollectLabels",
    "CollectSpec",
    "RemoteCollectSpec",
    "RemoteHost",
    "AssociatedHost",
    "PluginSpec",
    # collect_set
    "CollectSetConfig",
    "CollectSetMetadata",
    "CollectSetLabels",
    "CollectSetStatus",
    "CollectSetSpec",
    "PluginConfigSpec",
    "MonitorTargetSpec",
    "Group",
    "Topo",
    "SingleInst",
    "Target",
    "Inst",
    "ServiceTemplate",
    "SetTemplate",
    # collect_task
    "CollectTask",
    "CollectTaskMetadata",
    "CollectTaskLabels",
    "CollectTaskStatus",
    "CollectTaskSpec",
    # version
    "PACKAGE_VERSION",
    "PACKAGE_VERSION_V2",
    # collector v2
    "CollectConfigV2",
    "CollectMetadataV2",
    "CollectLabelsV2",
    "CollectStatusV2",
    "CollectSpecV2",
    "RemoteCollectSpecV2",
    "RemoteHostV2",
    "AssociatedHostV2",
    "PluginSpecV2",
    # collect_set v2
    "CollectSetConfigV2",
    "CollectSetMetadataV2",
    "CollectSetLabelsV2",
    "CollectSetStatusV2",
    "CollectSetSpecV2",
    "PluginConfigSpecV2",
    "MonitorTargetSpecV2",
    "GroupV2",
    "TopoV2",
    "SingleInstV2",
    "TargetV2",
    "InstV2",
    "ServiceTemplateV2",
    "SetTemplateV2",
    # enums
    "EXCLUDE_BLUEKING_COLLECT_MAPPING",
    "DISABLE_RETRY_STATUS_SET",
    "SUCCESS_STATUS_SET",
    "FAILED_STATUS_SET",
    "INTERMEDIATE_STATUS_SET",
    "SUCCEED_TASK_STATUS_TO_FAILED",
    "BkTaskStatusMap",
    "JobStatus",
    "ReconcileStatus",
    "CollectSetTaskStatus",
    "BkTaskStatus",
    "BkTaskAction",
    "BkMonitorTaskStatus",
    "TaskStatus",
    "TaskAction",
    "CollectType",
    "PluginType",
    "TaskToggleStatus",
    "SaveCollectApi",
    "ObjectModelEnum",
    "TargetNodeType",
    "TargetObjectType",
    "ReconcileStatus",
    "INTERMEDIATE_STATUS_SET",
]
