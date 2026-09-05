"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import inspect
import json
import logging
from copy import deepcopy
from functools import partial
from typing import TYPE_CHECKING, Any, Literal

from django.conf import settings
from django.db import models, transaction
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api
from core.errors.api import BKAPIError
from metadata.config import DATABASE_CONNECTION_NAME
from metadata.models.data_link import utils
from metadata.models.data_link.component_reuse import (
    ALL_DATA_LINK_COMPONENT_KINDS,
    ComponentReuseError,
    ExistingComponentContext,
    is_reuse_enabled_for,
    is_reuse_supported_for,
)
from metadata.models.data_link.constants import (
    BASEREPORT_DATABUS_FORMAT,
    BASEREPORT_USAGES,
    BK_EXPORTER_TRANSFORMER_FORMAT,
    BK_STANDARD_TRANSFORMER_FORMAT,
    SYSTEM_PROC_PERF_BASEREPORT_METRIC_TYPE,
    SYSTEM_PROC_PERF_DATABUS_FORMAT,
    SYSTEM_PROC_PORT_BASEREPORT_METRIC_TYPE,
    SYSTEM_PROC_PORT_DATABUS_FORMAT,
    DataLinkImmutableField,
    DataLinkKind,
    DataLinkResourceStatus,
)
from metadata.models.data_link.data_link_configs import (
    BasereportSinkConfig,
    ChannelBindingConfig,
    ConditionalSinkConfig,
    DataBusConfig,
    DorisStorageBindingConfig,
    ESStorageBindingConfig,
    ResultTableConfig,
    SurrealDBBindingConfig,
    VMStorageBindingConfig,
)
from metadata.models.data_link.utils import generate_result_table_field_list, get_bkbase_raw_data_id_name
from metadata.models.space.constants import EtlConfigs, SpaceTypes, SYSTEM_BASE_DATA_ETL_CONFIGS
from metadata.models.storage import ClusterInfo, DorisStorage, ESStorage, SurrealDBStorage
from metadata.models.vm.record import AccessVMRecord

if TYPE_CHECKING:
    from metadata.models import DataSource, ResultTable
    from metadata.models.data_link.data_link_configs import DataLinkResourceConfigBase

logger = logging.getLogger("metadata")

_MISSING_CONFIG_FIELD = object()
SURREALDB_RT_SUFFIX = "_graph"
DATABUS_MONITOR_LABEL_PREFIX = "bk-monitor/"
DATABUS_MONITOR_LABEL_SPACE_TYPE = f"{DATABUS_MONITOR_LABEL_PREFIX}space-type"
DATABUS_MONITOR_LABEL_DATA_SCENE = f"{DATABUS_MONITOR_LABEL_PREFIX}data-scene"
DATABUS_MONITOR_LABEL_DATA_TYPE = f"{DATABUS_MONITOR_LABEL_PREFIX}data-type"
DATABUS_MONITOR_LABEL_OTHER = "other"

CUSTOM_FORMAT_VM_INTERMEDIATE_FIELDS: tuple[tuple[str, str], ...] = (
    ("metric", "string"),
    ("value", "double"),
    ("dimensions", "text"),
    ("time", "long"),
)

DATABUS_MONITOR_SPACE_TYPES = {
    SpaceTypes.BKCC.value,
    SpaceTypes.BKCI.value,
    SpaceTypes.BKSAAS.value,
}
DATABUS_MONITOR_METRIC_STRATEGIES = {
    "bk_standard_v2_time_series",
    "bk_exporter_time_series",
    "bk_standard_time_series",
    "bcs_federal_proxy_time_series",
    "bcs_federal_subset_time_series",
    "basereport_time_series_v1",
    "system_proc_perf",
    "system_proc_port",
}
DATABUS_MONITOR_GRAPH_STRATEGIES = {"graph_relation_time_series"}
DATABUS_MONITOR_EVENT_STRATEGIES = {"bk_standard_v2_event", "base_event_v1"}
DATABUS_MONITOR_LOG_STRATEGIES = {"bk_log"}
DATABUS_MONITOR_K8S_STRATEGIES = {
    "bcs_federal_proxy_time_series",
    "bcs_federal_subset_time_series",
}
DATABUS_MONITOR_PLUGIN_STRATEGIES = {"bk_exporter_time_series", "bk_standard_time_series"}
DATABUS_MONITOR_SYSTEM_STRATEGIES = {
    "basereport_time_series_v1",
    "base_event_v1",
    "system_proc_perf",
    "system_proc_port",
}
DATABUS_MONITOR_UPTIMECHECK_ETL_CONFIGS = {
    EtlConfigs.BK_UPTIMECHECK_HEARTBEAT.value,
    EtlConfigs.BK_UPTIMECHECK_HTTP.value,
    EtlConfigs.BK_UPTIMECHECK_TCP.value,
    EtlConfigs.BK_UPTIMECHECK_UDP.value,
}
DATABUS_MONITOR_PLUGIN_ETL_CONFIGS = {
    EtlConfigs.BK_EXPORTER.value,
    EtlConfigs.BK_STANDARD.value,
}
DATABUS_MONITOR_CUSTOM_ETL_CONFIGS = {
    EtlConfigs.BK_STANDARD_V2_TIME_SERIES.value,
    EtlConfigs.BK_STANDARD_V2_EVENT.value,
}
DATABUS_MONITOR_SYSTEM_DATA_LABELS = {
    "pingserver.base,pingserver",
    "bkmonitorbeat_gather_up",
    "system_base",
}
DATABUS_MONITOR_BCS_DATA_NAME_FIELD_MAP = {
    "k8s_metric": "K8sMetricDataID",
    "custom_metric": "CustomMetricDataID",
    "k8s_event": "K8sEventDataID",
    "custom_event": "CustomEventDataID",
    "system_log": "SystemLogDataID",
    "custom_log": "CustomLogDataID",
}


def _resolve_databus_monitor_space_type(table: "ResultTable | None", data_source: "DataSource") -> str:
    """推导 Databus 数据归属的空间类型。"""

    space_uid = getattr(data_source, "space_uid", "") or ""
    space_type = space_uid.partition("__")[0] if "__" in space_uid else ""
    if space_type in DATABUS_MONITOR_SPACE_TYPES:
        return space_type

    bk_biz_id = getattr(table, "bk_biz_id", 0) if table is not None else 0
    if bk_biz_id > 0:
        return SpaceTypes.BKCC.value
    if bk_biz_id < 0:
        from metadata.models.space import Space

        bk_tenant_id = getattr(data_source, "bk_tenant_id", None) or getattr(table, "bk_tenant_id", None)
        spaces = Space.objects.filter(id=abs(bk_biz_id))
        if bk_tenant_id:
            spaces = spaces.filter(bk_tenant_id=bk_tenant_id)
        space_type = spaces.values_list("space_type_id", flat=True).first() or ""
        if space_type in DATABUS_MONITOR_SPACE_TYPES:
            return space_type

    space_type = getattr(data_source, "space_type_id", "") or ""
    return space_type if space_type in DATABUS_MONITOR_SPACE_TYPES else DATABUS_MONITOR_LABEL_OTHER


def _resolve_databus_monitor_data_type(strategy: str, data_source: "DataSource") -> str:
    """推导 Databus 承载的数据类型。"""

    if strategy in DATABUS_MONITOR_GRAPH_STRATEGIES:
        return "graph"

    source_label = getattr(data_source, "source_label", "") or ""
    type_label = getattr(data_source, "type_label", "") or ""
    if source_label == DataSourceLabel.BK_APM and type_label == DataTypeLabel.LOG:
        return "trace"

    type_mapping = {
        DataTypeLabel.TIME_SERIES: "metric",
        DataTypeLabel.EVENT: "event",
        DataTypeLabel.TRACE: "trace",
        DataTypeLabel.LOG: "log",
    }
    if type_label in type_mapping:
        return type_mapping[type_label]
    if strategy in DATABUS_MONITOR_METRIC_STRATEGIES:
        return "metric"
    if strategy in DATABUS_MONITOR_EVENT_STRATEGIES:
        return "event"
    if strategy in DATABUS_MONITOR_LOG_STRATEGIES:
        return "log"
    return DATABUS_MONITOR_LABEL_OTHER


def _is_bcs_cluster_data_source(data_source: "DataSource") -> bool:
    """判断 DataSource 是否属于当前租户的 BCS 集群。"""

    bk_tenant_id = getattr(data_source, "bk_tenant_id", None)
    bk_data_id = getattr(data_source, "bk_data_id", None)
    data_name = getattr(data_source, "data_name", "") or ""
    if not bk_tenant_id or not bk_data_id or not data_name.startswith("bcs_"):
        return False

    from metadata.models.bcs import BCSClusterInfo

    for usage, field_name in DATABUS_MONITOR_BCS_DATA_NAME_FIELD_MAP.items():
        suffix = f"_{usage}"
        if not data_name.endswith(suffix):
            continue
        cluster_id = data_name[len("bcs_") : -len(suffix)]
        if cluster_id:
            return BCSClusterInfo.objects.filter(
                bk_tenant_id=bk_tenant_id,
                cluster_id=cluster_id,
                **{field_name: bk_data_id},
            ).exists()
        break

    # 仅对命名不符合当前规范的存量 BCS DataSource 使用兼容查询，避免普通链路扫描集群表。
    return (
        BCSClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id)
        .filter(
            models.Q(K8sMetricDataID=bk_data_id)
            | models.Q(CustomMetricDataID=bk_data_id)
            | models.Q(K8sEventDataID=bk_data_id)
            | models.Q(CustomEventDataID=bk_data_id)
            | models.Q(SystemLogDataID=bk_data_id)
            | models.Q(CustomLogDataID=bk_data_id)
        )
        .exists()
    )


def _resolve_databus_monitor_data_scene(
    strategy: str,
    table: "ResultTable | None",
    data_source: "DataSource",
) -> str:
    """按领域优先、接入方式次之的顺序推导数据场景。"""

    source_label = getattr(data_source, "source_label", "") or ""
    type_label = getattr(data_source, "type_label", "") or ""
    etl_config = getattr(data_source, "etl_config", "") or ""
    table_label = getattr(table, "label", "") if table is not None else ""
    data_label = getattr(table, "data_label", "") if table is not None else ""

    if strategy in DATABUS_MONITOR_GRAPH_STRATEGIES:
        return "relation"
    if source_label == DataSourceLabel.BK_APM or table_label == "apm":
        return "apm"
    if (
        strategy in DATABUS_MONITOR_K8S_STRATEGIES
        or table_label == "kubernetes"
        or _is_bcs_cluster_data_source(data_source)
    ):
        return "k8s"
    if table_label == "uptimecheck" or etl_config in DATABUS_MONITOR_UPTIMECHECK_ETL_CONFIGS:
        return "uptimecheck"
    if strategy in DATABUS_MONITOR_PLUGIN_STRATEGIES or etl_config in DATABUS_MONITOR_PLUGIN_ETL_CONFIGS:
        return "plugin"
    if (
        strategy in DATABUS_MONITOR_SYSTEM_STRATEGIES
        or etl_config in SYSTEM_BASE_DATA_ETL_CONFIGS
        or data_label in DATABUS_MONITOR_SYSTEM_DATA_LABELS
        or (
            table is not None
            and getattr(table, "is_builtin", False)
            and source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
        )
    ):
        return "system"
    if strategy in DATABUS_MONITOR_LOG_STRATEGIES or source_label == DataSourceLabel.BK_LOG_SEARCH:
        return "log"
    if type_label == DataTypeLabel.LOG:
        return "log"
    if (
        source_label == DataSourceLabel.CUSTOM
        or getattr(data_source, "is_custom_source", False)
        or etl_config in DATABUS_MONITOR_CUSTOM_ETL_CONFIGS
        or strategy in DATABUS_MONITOR_EVENT_STRATEGIES
        or strategy == "bk_standard_v2_time_series"
        or (table is not None and getattr(table, "is_custom_table", False))
    ):
        return "custom"
    return DATABUS_MONITOR_LABEL_OTHER


def compose_databus_monitor_labels(
    strategy: str,
    table: "ResultTable | None",
    data_source: "DataSource",
) -> dict[str, str]:
    """基于监控侧链路上下文生成 Databus metadata labels。"""

    label_values = {
        DATABUS_MONITOR_LABEL_SPACE_TYPE: _resolve_databus_monitor_space_type(table, data_source),
        DATABUS_MONITOR_LABEL_DATA_SCENE: _resolve_databus_monitor_data_scene(strategy, table, data_source),
        DATABUS_MONITOR_LABEL_DATA_TYPE: _resolve_databus_monitor_data_type(strategy, data_source),
    }
    return {key: str(value or DATABUS_MONITOR_LABEL_OTHER) for key, value in label_values.items()}


CUSTOM_EVENT_CLEAN_RULES: list[dict[str, Any]] = [
    {"input_id": "__raw_data", "output_id": "json_data", "operator": {"type": "json_de", "error_strategy": "drop"}},
    {
        "input_id": "json_data",
        "output_id": "items",
        "operator": {"type": "get", "key_index": [{"type": "key", "value": "data"}], "missing_strategy": None},
    },
    {"input_id": "items", "output_id": "iter_item", "operator": {"type": "iter"}},
    {
        "input_id": "iter_item",
        "output_id": "event_name",
        "operator": {"type": "assign", "key_index": "event_name"},
    },
    {
        "input_id": "iter_item",
        "output_id": "target",
        "operator": {"type": "assign", "key_index": "target", "output_type": "string"},
    },
    {
        "input_id": "iter_item",
        "output_id": "dimensions",
        "operator": {"type": "assign", "key_index": "dimension", "output_type": "dict"},
    },
    {
        "input_id": "iter_item",
        "output_id": "event",
        "operator": {"type": "assign", "key_index": "event", "output_type": "dict"},
    },
    {
        "input_id": "iter_item",
        "output_id": "time",
        "operator": {
            "type": "assign",
            "key_index": "timestamp",
            "output_type": "timestamp",
            "in_place_time_parsing": {
                "from": {"format": "%s", "zone": 0},
                "to": "millis",
                "interval_format": "ms",
                "now_if_parse_failed": True,
            },
        },
    },
    {
        "input_id": "iter_item",
        "output_id": "timestamp",
        "operator": {
            "type": "assign",
            "key_index": "timestamp",
            "output_type": "timestamp",
            "is_time_field": True,
            "time_format": {"format": "%s", "zone": 0},
            "in_place_time_parsing": {
                "from": {"format": "%s", "zone": 0},
                "interval_format": "ms",
                "to": "second",
                "now_if_parse_failed": True,
            },
        },
    },
]


class DataLink(models.Model):
    """
    一条完整的链路资源
    涵盖资源配置按需组装 -> 下发配置申请链路 ->同步元数据 全流程
    """

    BK_STANDARD_V2_EVENT = "bk_standard_v2_event"
    BK_STANDARD_V2_TIME_SERIES = "bk_standard_v2_time_series"  # 标准单指标单表时序链路
    BK_EXPORTER_TIME_SERIES = "bk_exporter_time_series"  # 采集插件 -- 固定指标单表(metric_name)时序链路
    BK_STANDARD_TIME_SERIES = "bk_standard_time_series"  # 采集插件 -- 固定指标单表(metric_name)时序链路
    BCS_FEDERAL_PROXY_TIME_SERIES = "bcs_federal_proxy_time_series"  # 联邦代理集群（父集群）时序链路
    BCS_FEDERAL_SUBSET_TIME_SERIES = "bcs_federal_subset_time_series"  # 联邦集群（子集群）时序链路
    BASEREPORT_TIME_SERIES_V1 = "basereport_time_series_v1"  # 主机基础数据上报时序链路
    GRAPH_RELATION_TIME_SERIES = "graph_relation_time_series"  # 图关系时序链路
    SYSTEM_PROC_PERF = "system_proc_perf"  # 系统进程性能链路
    SYSTEM_PROC_PORT = "system_proc_port"  # 系统进程端口链路
    BASE_EVENT_V1 = "base_event_v1"  # 基础事件链路
    BK_LOG = "bk_log"  # 日志链路
    CUSTOM_FORMAT_VM = "custom_format_vm"
    CUSTOM_FORMAT_ES = "custom_format_es"
    CUSTOM_FORMAT_DORIS = "custom_format_doris"
    DATA_LINK_STRATEGY_CHOICES = (
        (BK_STANDARD_V2_EVENT, "标准自定义事件链路"),
        (BK_STANDARD_V2_TIME_SERIES, "标准单指标单表时序数据链路"),
        (BK_EXPORTER_TIME_SERIES, "采集插件时序数据链路"),
        (BK_STANDARD_TIME_SERIES, "STANDARD采集插件时序数据链路"),
        (BCS_FEDERAL_PROXY_TIME_SERIES, "联邦代理时序数据链路"),
        (BCS_FEDERAL_SUBSET_TIME_SERIES, "联邦子集时序数据链路"),
        (BASEREPORT_TIME_SERIES_V1, "主机基础采集时序数据链路"),
        (GRAPH_RELATION_TIME_SERIES, "图关系时序数据链路"),
        (BASE_EVENT_V1, "基础事件链路"),
        (SYSTEM_PROC_PERF, "系统进程性能链路"),
        (SYSTEM_PROC_PORT, "系统进程端口链路"),
        (BK_LOG, "日志链路"),
        (CUSTOM_FORMAT_VM, "自定义格式 VM 链路"),
        (CUSTOM_FORMAT_ES, "自定义格式 Elasticsearch 链路"),
        (CUSTOM_FORMAT_DORIS, "自定义格式 Doris 链路"),
    )

    # 各个套餐所需要的链路资源
    STRATEGY_RELATED_COMPONENTS: dict[str, list[type["DataLinkResourceConfigBase"]]] = {
        BK_STANDARD_V2_TIME_SERIES: [ResultTableConfig, VMStorageBindingConfig, DataBusConfig],
        BK_EXPORTER_TIME_SERIES: [ResultTableConfig, VMStorageBindingConfig, DataBusConfig],
        BK_STANDARD_TIME_SERIES: [ResultTableConfig, VMStorageBindingConfig, DataBusConfig],
        BCS_FEDERAL_PROXY_TIME_SERIES: [ResultTableConfig, VMStorageBindingConfig],
        BCS_FEDERAL_SUBSET_TIME_SERIES: [
            ResultTableConfig,
            VMStorageBindingConfig,
            ConditionalSinkConfig,
            DataBusConfig,
        ],
        BASEREPORT_TIME_SERIES_V1: [
            ResultTableConfig,
            VMStorageBindingConfig,
            BasereportSinkConfig,
            ConditionalSinkConfig,
            DataBusConfig,
        ],
        GRAPH_RELATION_TIME_SERIES: [
            ResultTableConfig,
            VMStorageBindingConfig,
            SurrealDBBindingConfig,
            DataBusConfig,
        ],
        BASE_EVENT_V1: [ResultTableConfig, ESStorageBindingConfig, DataBusConfig],
        SYSTEM_PROC_PERF: [ResultTableConfig, VMStorageBindingConfig, BasereportSinkConfig, DataBusConfig],
        SYSTEM_PROC_PORT: [ResultTableConfig, VMStorageBindingConfig, BasereportSinkConfig, DataBusConfig],
        BK_LOG: [ResultTableConfig, ESStorageBindingConfig, DorisStorageBindingConfig, DataBusConfig],
        BK_STANDARD_V2_EVENT: [ResultTableConfig, ESStorageBindingConfig, DataBusConfig],
        CUSTOM_FORMAT_VM: [ResultTableConfig, ChannelBindingConfig, VMStorageBindingConfig, DataBusConfig],
        CUSTOM_FORMAT_ES: [ResultTableConfig, ESStorageBindingConfig, DataBusConfig],
        CUSTOM_FORMAT_DORIS: [ResultTableConfig, DorisStorageBindingConfig, DataBusConfig],
    }

    STORAGE_TYPE_MAP = {
        BK_STANDARD_V2_TIME_SERIES: ClusterInfo.TYPE_VM,
        BK_EXPORTER_TIME_SERIES: ClusterInfo.TYPE_VM,
        BK_STANDARD_TIME_SERIES: ClusterInfo.TYPE_VM,
        BCS_FEDERAL_PROXY_TIME_SERIES: ClusterInfo.TYPE_VM,
        BCS_FEDERAL_SUBSET_TIME_SERIES: ClusterInfo.TYPE_VM,
        BASEREPORT_TIME_SERIES_V1: ClusterInfo.TYPE_VM,
        GRAPH_RELATION_TIME_SERIES: ClusterInfo.TYPE_VM,
        BASE_EVENT_V1: ClusterInfo.TYPE_ES,
        SYSTEM_PROC_PERF: ClusterInfo.TYPE_VM,
        SYSTEM_PROC_PORT: ClusterInfo.TYPE_VM,
        BK_LOG: ClusterInfo.TYPE_ES,
        BK_STANDARD_V2_EVENT: ClusterInfo.TYPE_ES,
        CUSTOM_FORMAT_VM: ClusterInfo.TYPE_VM,
        CUSTOM_FORMAT_ES: ClusterInfo.TYPE_ES,
        CUSTOM_FORMAT_DORIS: ClusterInfo.TYPE_DORIS,
    }

    DATABUS_TRANSFORMER_FORMAT = {
        BK_EXPORTER_TIME_SERIES: BK_EXPORTER_TRANSFORMER_FORMAT,
        BK_STANDARD_TIME_SERIES: BK_STANDARD_TRANSFORMER_FORMAT,
    }

    # DataLink 组件复用 - leftover 策略表
    # key   : (data_link_strategy, component kind)
    # value : "strict" 表示 compose 完成后该 kind 的未消费组件视为脏数据，直接报错；
    #         "keep"   表示允许既有组件残留（既不报错也不删除，也不参与本次下发）。
    #         "delete" 表示 apply 成功后删除未被本次 compose 返回的组件。
    # 未声明的 (strategy, kind) 默认按 "strict" 处理。
    REUSE_LEFTOVER_POLICY: dict[tuple[str, type["DataLinkResourceConfigBase"]], Literal["strict", "keep", "delete"]] = {
        # 日志在 ES / Doris 间切换时，需要保留旧存储绑定以支持历史分段查询；
        # compose 只会认领当前生效的绑定，因此旧绑定不应被视为脏数据。
        (BK_LOG, ESStorageBindingConfig): "keep",
        (BK_LOG, DorisStorageBindingConfig): "keep",
        (GRAPH_RELATION_TIME_SERIES, ResultTableConfig): "delete",
        (GRAPH_RELATION_TIME_SERIES, VMStorageBindingConfig): "delete",
        (GRAPH_RELATION_TIME_SERIES, SurrealDBBindingConfig): "delete",
        (GRAPH_RELATION_TIME_SERIES, DataBusConfig): "delete",
    }

    bk_data_id = models.IntegerField(verbose_name="关联数据源ID", default=0)
    table_ids = models.JSONField(verbose_name="关联结果表ID列表", default=list)

    data_link_name = models.CharField(max_length=255, verbose_name="链路名称", primary_key=True)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")
    namespace = models.CharField(
        max_length=255, verbose_name="命名空间", default=settings.DEFAULT_VM_DATA_LINK_NAMESPACE
    )
    data_link_strategy = models.CharField(max_length=255, verbose_name="链路策略", choices=DATA_LINK_STRATEGY_CHOICES)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "数据链路"
        verbose_name_plural = verbose_name

    def delete_data_link(self):
        """删除数据链路"""
        logger.info("delete_data_link: data_link_name->[%s]", self.data_link_name)
        component_classes = self.get_delete_component_classes()
        for component_class in reversed(component_classes):
            components = component_class.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                namespace=self.namespace,
                data_link_name=self.data_link_name,
            )
            for component in components:
                logger.info(
                    "delete_data_link: delete data_link_name->[%s] kind->[%s] component->[%s]",
                    self.data_link_name,
                    component.kind,
                    component.name,
                )
                component.delete_config()
        self.delete()

    def get_related_component_classes(self) -> list[type["DataLinkResourceConfigBase"]]:
        if self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES:
            from metadata.models.result_table import GraphRelationV4DataLinkOption, ResultTableOption

            option_record = ResultTableOption.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                table_id__in=self.table_ids,
                name=ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
            ).first()
            if option_record is not None:
                option = GraphRelationV4DataLinkOption.from_option_value(option_record.get_value())
                component_classes = [ResultTableConfig]
                if option.should_write_vm:
                    component_classes.append(VMStorageBindingConfig)
                if option.should_write_surrealdb:
                    component_classes.append(SurrealDBBindingConfig)
                component_classes.append(DataBusConfig)
                return component_classes

        return list(dict.fromkeys(self.STRATEGY_RELATED_COMPONENTS[self.data_link_strategy]))

    def get_delete_component_classes(self) -> list[type["DataLinkResourceConfigBase"]]:
        return self.STRATEGY_RELATED_COMPONENTS[self.data_link_strategy]

    def _get_compose_method(self):
        """获取当前 strategy 对应的配置组装方法。"""

        switcher = {
            DataLink.BK_STANDARD_V2_TIME_SERIES: self.compose_standard_time_series_configs,
            DataLink.BK_STANDARD_TIME_SERIES: self.compose_bk_plugin_time_series_config,
            DataLink.BK_EXPORTER_TIME_SERIES: self.compose_bk_plugin_time_series_config,
            DataLink.BCS_FEDERAL_PROXY_TIME_SERIES: self.compose_bcs_federal_proxy_time_series_configs,
            DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES: self.compose_bcs_federal_subset_time_series_configs,
            DataLink.BASEREPORT_TIME_SERIES_V1: self.compose_basereport_time_series_configs,
            DataLink.GRAPH_RELATION_TIME_SERIES: self.compose_graph_relation_v4_time_series_configs,
            DataLink.BASE_EVENT_V1: self.compose_base_event_configs,
            DataLink.SYSTEM_PROC_PERF: partial(
                self.compose_system_proc_configs, data_link_strategy=DataLink.SYSTEM_PROC_PERF
            ),
            DataLink.SYSTEM_PROC_PORT: partial(
                self.compose_system_proc_configs, data_link_strategy=DataLink.SYSTEM_PROC_PORT
            ),
            DataLink.BK_LOG: self.compose_log_configs,
            DataLink.BK_STANDARD_V2_EVENT: self.compose_custom_event_configs,
            DataLink.CUSTOM_FORMAT_VM: self.compose_custom_format_configs,
            DataLink.CUSTOM_FORMAT_ES: self.compose_custom_format_configs,
            DataLink.CUSTOM_FORMAT_DORIS: self.compose_custom_format_configs,
        }
        return switcher[self.data_link_strategy]

    def compose_configs(
        self,
        *args,
        existing_context: "ExistingComponentContext | None" = None,
        consumer_group: str | None = None,
        **kwargs,
    ):
        """
        生成对应套餐的链路完整配置

        ``existing_context`` 由上层根据 strategy 灰度开关或 RT option 单表开关决定是否构造。
        本层只负责确认当前 compose 分支已经接入 ``existing_context`` 形参，避免把该参数
        透传给尚未改造的 strategy。
        """

        method = self._get_compose_method()
        kwargs["consumer_group"] = consumer_group
        if existing_context is not None and is_reuse_supported_for(self.data_link_strategy):
            return method(*args, existing_context=existing_context, **kwargs)
        return method(*args, **kwargs)

    @staticmethod
    def _compose_custom_format_vm_intermediate_fields() -> list[dict[str, Any]]:
        """按固定四元组生成自定义指标内部 ResultTable 字段。"""

        return [
            {
                "field_name": field_name,
                "field_alias": field_name,
                "field_type": field_type,
                "is_dimension": False,
                "field_index": index,
            }
            for index, (field_name, field_type) in enumerate(CUSTOM_FORMAT_VM_INTERMEDIATE_FIELDS)
        ]

    def compose_custom_format_configs(
        self,
        bk_biz_id: int,
        data_source: "DataSource",
        table_id: str,
        storage_cluster_name: str = "",
        inner_kafka_channel_name: str = "",
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        """组装自定义格式的 VM、Elasticsearch 或 Doris 单目标链路。"""
        from metadata.models import ResultTableOption
        from metadata.models.result_table import CustomFormatV4DataLinkOption

        option_record = ResultTableOption.objects.get(
            bk_tenant_id=self.bk_tenant_id,
            table_id=table_id,
            name=ResultTableOption.OPTION_CUSTOM_FORMAT_V4_DATA_LINK,
        )
        option = CustomFormatV4DataLinkOption.from_option_value(option_record.get_value())
        expected_strategy = {
            ClusterInfo.TYPE_VM: self.CUSTOM_FORMAT_VM,
            ClusterInfo.TYPE_ES: self.CUSTOM_FORMAT_ES,
            ClusterInfo.TYPE_DORIS: self.CUSTOM_FORMAT_DORIS,
        }[option.target_storage_type]
        if self.data_link_strategy != expected_strategy:
            raise ValueError(
                f"自定义格式目标存储与链路策略不一致: target={option.target_storage_type}, "
                f"strategy={self.data_link_strategy}"
            )

        clean_rules = [rule.model_dump() for rule in option.clean_rules]
        if option.target_storage_type == ClusterInfo.TYPE_VM:
            fields = self._compose_custom_format_vm_intermediate_fields()
        else:
            fields = generate_result_table_field_list(table_id=table_id, bk_tenant_id=self.bk_tenant_id)
        vm_whitelist: dict[Literal["metrics", "tags"], list[str]] | None = None
        if option.target_storage_type == ClusterInfo.TYPE_VM:
            vm_whitelist = self._compose_custom_format_vm_whitelist(table_id)
        data_id_name = utils.get_registered_bkdata_data_id_name(data_source, namespace=self.namespace)
        clean_name = f"{self.data_link_name}_clean"
        clean_consumer_group = consumer_group or f"bkmonitor_{self.data_link_name}_clean"
        clean_transform = {
            "kind": "Clean",
            "rules": clean_rules,
            "filter_rules": option.filter_rules,
        }

        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            result_table, _ = ResultTableConfig.objects.update_or_create(
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                namespace=self.namespace,
                data_link_name=self.data_link_name,
                name=self.data_link_name,
                defaults={"table_id": table_id, "data_type": "log"},
            )
            configs: list[dict[str, Any]] = [result_table.compose_config(fields=fields)]

            if option.target_storage_type == ClusterInfo.TYPE_ES:
                storage = ESStorage.objects.filter(bk_tenant_id=self.bk_tenant_id, table_id=table_id).first()
                if storage is None:
                    raise ValueError(f"自定义格式 ResultTable({table_id}) 缺少 ESStorage")
                storage_option = option.es_storage_config
                assert storage_option is not None
                binding, _ = ESStorageBindingConfig.objects.update_or_create(
                    bk_tenant_id=self.bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    namespace=self.namespace,
                    data_link_name=self.data_link_name,
                    name=self.data_link_name,
                    defaults={
                        "table_id": table_id,
                        "bkbase_result_table_name": result_table.name,
                        "es_cluster_name": storage.storage_cluster.cluster_name,
                        "timezone": storage_option.timezone,
                    },
                )
                sink = {"kind": DataLinkKind.ESSTORAGEBINDING.value, "name": binding.name, "namespace": self.namespace}
                configs.append(
                    binding.compose_config(
                        storage_cluster_name=storage.storage_cluster.cluster_name,
                        write_alias_format=f"write_%Y%m%d_{table_id.replace('.', '_')}",
                        unique_field_list=storage_option.unique_field_list,
                        json_field_list=storage_option.json_field_list,
                        rt_name=result_table.name,
                    )
                )
            elif option.target_storage_type == ClusterInfo.TYPE_DORIS:
                storage = DorisStorage.objects.filter(bk_tenant_id=self.bk_tenant_id, table_id=table_id).first()
                if storage is None:
                    raise ValueError(f"自定义格式 ResultTable({table_id}) 缺少 DorisStorage")
                storage_option = option.doris_storage_config
                assert storage_option is not None
                binding, _ = DorisStorageBindingConfig.objects.update_or_create(
                    bk_tenant_id=self.bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    namespace=self.namespace,
                    data_link_name=self.data_link_name,
                    name=self.data_link_name,
                    defaults={
                        "table_id": table_id,
                        "bkbase_result_table_name": result_table.name,
                        "doris_cluster_name": storage.storage_cluster.cluster_name,
                    },
                )
                sink = {"kind": DataLinkKind.DORISBINDING.value, "name": binding.name, "namespace": self.namespace}
                configs.append(
                    binding.compose_config(
                        storage_cluster_name=storage.storage_cluster.cluster_name,
                        storage_keys=storage_option.storage_keys,
                        json_fields=storage_option.json_fields,
                        field_config_group=storage_option.field_config_group,
                        original_json_fields=storage_option.original_json_fields,
                        expires=f"{storage.expire_days}d",
                        flush_timeout=storage_option.flush_timeout,
                        rt_name=result_table.name,
                    )
                )
            else:
                if not storage_cluster_name:
                    raise ValueError("自定义格式 VM 链路缺少 VM 集群")
                if not inner_kafka_channel_name:
                    raise ValueError("自定义格式 VM 链路缺少 inner KafkaChannel")
                channel_binding, _ = ChannelBindingConfig.objects.update_or_create(
                    bk_tenant_id=self.bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    namespace=self.namespace,
                    data_link_name=self.data_link_name,
                    name=self.data_link_name,
                    defaults={
                        "bkbase_result_table_name": result_table.name,
                        "channel_name": inner_kafka_channel_name,
                    },
                )
                vm_binding, _ = VMStorageBindingConfig.objects.update_or_create(
                    bk_tenant_id=self.bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    namespace=self.namespace,
                    data_link_name=self.data_link_name,
                    name=self.data_link_name,
                    defaults={
                        "table_id": table_id,
                        "bkbase_result_table_name": result_table.name,
                        "vm_cluster_name": storage_cluster_name,
                    },
                )
                sink = {
                    "kind": DataLinkKind.CHANNELBINDING.value,
                    "name": channel_binding.name,
                    "namespace": self.namespace,
                }
                configs.extend(
                    [
                        channel_binding.compose_config(),
                        vm_binding.compose_config(whitelist=vm_whitelist, rt_name=result_table.name),
                    ]
                )

                shipper_name = f"{self.data_link_name}_shipper"
                shipper, _ = DataBusConfig.objects.update_or_create(
                    bk_tenant_id=self.bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    namespace=self.namespace,
                    data_link_name=self.data_link_name,
                    name=shipper_name,
                    defaults={
                        "data_id_name": result_table.name,
                        "bk_data_id": data_source.bk_data_id,
                        "source_kind": DataLinkKind.RESULTTABLE.value,
                        "source_name": result_table.name,
                        "role": "vm_shipper",
                        "consumer_group": f"bkmonitor_{self.data_link_name}_shipper",
                        "sink_names": [f"{DataLinkKind.VMSTORAGEBINDING.value}:{vm_binding.name}"],
                    },
                )
                vm_sink = {
                    "kind": DataLinkKind.VMSTORAGEBINDING.value,
                    "name": vm_binding.name,
                    "namespace": self.namespace,
                }
                configs.append(
                    shipper.compose_config(
                        sinks=[vm_sink],
                        transforms=[
                            {
                                "kind": "PreDefinedLogic",
                                "name": "avro_to_metric",
                                "tags": [],
                                "fields": [],
                                "schemaless": True,
                            }
                        ],
                    )
                )

            if settings.ENABLE_MULTI_TENANT_MODE:
                sink["tenant"] = self.bk_tenant_id
            clean_databus, _ = DataBusConfig.objects.update_or_create(
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                namespace=self.namespace,
                data_link_name=self.data_link_name,
                name=clean_name,
                defaults={
                    "data_id_name": data_id_name,
                    "bk_data_id": data_source.bk_data_id,
                    "source_kind": DataLinkKind.DATAID.value,
                    "source_name": data_id_name,
                    "role": "clean",
                    "consumer_group": clean_consumer_group,
                    "sink_names": [f"{sink['kind']}:{sink['name']}"],
                },
            )
            configs.append(clean_databus.compose_config(sinks=[sink], transforms=[clean_transform]))
            return configs

    def compose_custom_event_configs(
        self,
        bk_biz_id: int,
        data_source: "DataSource",
        table_id: str,
        existing_context: ExistingComponentContext | None = None,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        """生成自定义事件链路

        Args:
            bk_biz_id: 业务ID
            data_source: 数据源
            table_id: 结果表ID
            existing_context: 既有组件复用上下文。显式传入时按同 kind 组件唯一性
                尝试复用已有组件；默认不启用复用。
        """
        from metadata.models import ResultTableOption

        logger.info(
            "compose_custom_event_configs: data_link_name->[%s],bk_biz_id->[%s],data_source->[%s],table_id->[%s]",
            self.data_link_name,
            bk_biz_id,
            data_source,
            table_id,
        )

        es_storage = ESStorage.objects.filter(bk_tenant_id=self.bk_tenant_id, table_id=table_id).first()
        if not es_storage:
            raise ValueError("compose_custom_event_configs: lack storage config")

        config_list = []
        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            existing_rt = (
                existing_context.claim(ResultTableConfig, lambda c: True) if existing_context is not None else None
            )
            rt_name = existing_rt.name if existing_rt is not None else self.data_link_name

            existing_binding = (
                existing_context.claim(ESStorageBindingConfig, lambda c: True) if existing_context is not None else None
            )
            binding_name = existing_binding.name if existing_binding is not None else self.data_link_name

            existing_databus = (
                existing_context.claim(DataBusConfig, lambda c: True) if existing_context is not None else None
            )
            databus_name = existing_databus.name if existing_databus is not None else self.data_link_name
            databus_data_id_name = (
                existing_databus.data_id_name
                if existing_databus is not None
                else utils.get_registered_bkdata_data_id_name(data_source, namespace=self.namespace)
            )

            es_table_ins, _ = ResultTableConfig.objects.update_or_create(
                name=rt_name,
                namespace=self.namespace,
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                data_link_name=self.data_link_name,
                defaults={"table_id": table_id},
            )

            es_storage_ins, _ = ESStorageBindingConfig.objects.update_or_create(
                name=binding_name,
                namespace=self.namespace,
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                data_link_name=self.data_link_name,
                defaults={
                    "table_id": table_id,
                    "bkbase_result_table_name": es_table_ins.name,
                    "es_cluster_name": es_storage.storage_cluster.cluster_name,
                    "timezone": es_storage.time_zone,
                },
            )

            fields = generate_result_table_field_list(table_id=table_id, bk_tenant_id=self.bk_tenant_id)
            index_name = table_id.replace(".", "_")
            write_alias = f"write_%Y%m%d_{index_name}"
            unique_field_list = ResultTableOption.objects.get(
                bk_tenant_id=self.bk_tenant_id, table_id=table_id, name=ResultTableOption.OPTION_ES_DOCUMENT_ID
            ).get_value()

            databus_ins, _ = DataBusConfig.objects.update_or_create(
                name=databus_name,
                namespace=self.namespace,
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                data_link_name=self.data_link_name,
                defaults={
                    "data_id_name": databus_data_id_name,
                    "bk_data_id": data_source.bk_data_id,
                    "sink_names": [f"{DataLinkKind.ESSTORAGEBINDING.value}:{es_storage_ins.name}"],
                },
            )
            databus_ins.apply_consumer_group(consumer_group)

            es_rt_config = es_table_ins.compose_config(fields=fields)
            es_binding_config = es_storage_ins.compose_config(
                storage_cluster_name=es_storage.storage_cluster.cluster_name,
                write_alias_format=write_alias,
                unique_field_list=unique_field_list,
                json_field_list=["event", "dimension"],
                rt_name=es_table_ins.name,
            )

            sinks = [
                {
                    "kind": DataLinkKind.ESSTORAGEBINDING.value,
                    "name": es_storage_ins.name,
                    "namespace": self.namespace,
                }
            ]
            if settings.ENABLE_MULTI_TENANT_MODE:
                sinks[0]["tenant"] = self.bk_tenant_id

            databus_config = databus_ins.compose_log_config(
                sinks=sinks,
                rules=CUSTOM_EVENT_CLEAN_RULES,
            )

        config_list = [es_rt_config, es_binding_config, databus_config]
        logger.info(
            "compose_custom_event_configs: data_link_name->[%s] composed configs successfully,config_list->[%s]",
            self.data_link_name,
            config_list,
        )
        return config_list

    @classmethod
    def compose_surrealdb_table_name(cls, table_id: str) -> str:
        graph_table_id = table_id.replace(".__default__", f"{SURREALDB_RT_SUFFIX}.__default__", 1)
        if graph_table_id == table_id:
            graph_table_id = f"{table_id}{SURREALDB_RT_SUFFIX}"
        return utils.compose_bkdata_table_id(graph_table_id)

    @staticmethod
    def _strip_bkbase_biz_prefix(bkbase_table_id: str) -> str:
        prefix, sep, table_name = bkbase_table_id.partition("_")
        if sep and prefix.isdigit():
            return table_name
        return bkbase_table_id

    @classmethod
    def resolve_graph_relation_vm_result_table_name(
        cls,
        bk_tenant_id: str,
        table_id: str,
        default_name: str,
    ) -> str:
        existing_vm_record = AccessVMRecord.objects.filter(
            bk_tenant_id=bk_tenant_id,
            result_table_id=table_id,
        ).last()
        if existing_vm_record and existing_vm_record.vm_result_table_id:
            return cls._strip_bkbase_biz_prefix(existing_vm_record.vm_result_table_id)
        return default_name

    def compose_graph_relation_v4_time_series_configs(
        self,
        bk_biz_id: int,
        data_source: "DataSource",
        table_id: str,
        storage_cluster_name: str = "",
        existing_context: "ExistingComponentContext | None" = None,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        """根据 ResultTableOption 一次性组装 Graph Relation V4 的完整期望状态。"""
        from metadata.models import ResultTableOption
        from metadata.models.result_table import GraphRelationV4DataLinkOption

        option_record = ResultTableOption.objects.get(
            bk_tenant_id=self.bk_tenant_id,
            table_id=table_id,
            name=ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
        )
        option = GraphRelationV4DataLinkOption.from_option_value(option_record.get_value())
        default_vm_name = self.resolve_graph_relation_vm_result_table_name(
            bk_tenant_id=self.bk_tenant_id,
            table_id=table_id,
            default_name=utils.compose_bkdata_table_id(table_id),
        )
        surrealdb_name = self.compose_surrealdb_table_name(table_id)

        configs: list[dict[str, Any]] = []
        if option.should_write_vm:
            if not storage_cluster_name:
                access_vm_record = AccessVMRecord.objects.filter(
                    bk_tenant_id=self.bk_tenant_id,
                    result_table_id=table_id,
                ).last()
                if access_vm_record:
                    vm_cluster = ClusterInfo.objects.filter(
                        bk_tenant_id=self.bk_tenant_id,
                        cluster_id=access_vm_record.vm_cluster_id,
                        cluster_type=ClusterInfo.TYPE_VM,
                    ).first()
                    storage_cluster_name = vm_cluster.cluster_name if vm_cluster else ""
            if not storage_cluster_name:
                raise ValueError("compose_graph_relation_v4_time_series_configs: vm cluster name is empty")

            existing_vm_rt = (
                existing_context.claim(ResultTableConfig, lambda component: component.data_type != "graph")
                if existing_context is not None
                else None
            )
            existing_vm_binding = (
                existing_context.claim(VMStorageBindingConfig, lambda component: True)
                if existing_context is not None
                else None
            )
            existing_vm_databus = (
                existing_context.claim(
                    DataBusConfig,
                    lambda component: any(
                        sink_name.startswith(f"{DataLinkKind.VMSTORAGEBINDING.value}:")
                        for sink_name in component.sink_names
                    ),
                )
                if existing_context is not None
                else None
            )
            vm_rt_name = existing_vm_rt.name if existing_vm_rt is not None else default_vm_name
            vm_binding_name = existing_vm_binding.name if existing_vm_binding is not None else vm_rt_name
            vm_databus_name = existing_vm_databus.name if existing_vm_databus is not None else vm_rt_name
            vm_data_id_name = (
                existing_vm_databus.data_id_name
                if existing_vm_databus is not None
                else utils.get_registered_bkdata_data_id_name(data_source, namespace=self.namespace)
            )

            result_table_option = ResultTableOption.objects.filter(
                table_id=table_id,
                bk_tenant_id=self.bk_tenant_id,
                name=ResultTableOption.OPTION_METRIC_GROUP_DIMENSIONS,
            ).first()
            metric_group_dimensions = result_table_option.get_value() if result_table_option else None
            configs.extend(
                self._compose_vm_time_series_component_configs(
                    bk_biz_id=bk_biz_id,
                    data_source=data_source,
                    table_id=table_id,
                    storage_cluster_name=storage_cluster_name,
                    rt_name=vm_rt_name,
                    binding_name=vm_binding_name,
                    databus_name=vm_databus_name,
                    bkbase_data_name=vm_data_id_name,
                    metric_group_dimensions=metric_group_dimensions,
                    consumer_group=consumer_group,
                )
            )

        if option.should_write_surrealdb:
            surrealdb_storage = SurrealDBStorage.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                table_id=table_id,
            ).first()
            if surrealdb_storage is None:
                raise ValueError(
                    f"compose_graph_relation_v4_time_series_configs: surrealdb storage not found, table_id={table_id}"
                )

            existing_surrealdb_rt = (
                existing_context.claim(ResultTableConfig, lambda component: component.data_type == "graph")
                if existing_context is not None
                else None
            )
            existing_surrealdb_binding = (
                existing_context.claim(SurrealDBBindingConfig, lambda component: True)
                if existing_context is not None
                else None
            )
            existing_surrealdb_databus = (
                existing_context.claim(
                    DataBusConfig,
                    lambda component: any(
                        sink_name.startswith(f"{DataLinkKind.SURREALDBBINDING.value}:")
                        for sink_name in component.sink_names
                    ),
                )
                if existing_context is not None
                else None
            )
            graph_rt_name = existing_surrealdb_rt.name if existing_surrealdb_rt is not None else surrealdb_name
            graph_binding_name = (
                existing_surrealdb_binding.name if existing_surrealdb_binding is not None else graph_rt_name
            )
            graph_databus_name = (
                existing_surrealdb_databus.name if existing_surrealdb_databus is not None else graph_rt_name
            )
            graph_data_id_name = (
                existing_surrealdb_databus.data_id_name
                if existing_surrealdb_databus is not None
                else utils.get_registered_bkdata_data_id_name(data_source, namespace=self.namespace)
            )
            with transaction.atomic(using=DATABASE_CONNECTION_NAME):
                graph_rt, _ = ResultTableConfig.objects.update_or_create(
                    name=graph_rt_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                    defaults={"table_id": table_id, "data_type": "graph"},
                )
                graph_binding, _ = SurrealDBBindingConfig.objects.update_or_create(
                    name=graph_binding_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                    defaults={
                        "surrealdb_cluster_name": surrealdb_storage.storage_cluster.cluster_name,
                        "table_id": table_id,
                        "bkbase_result_table_name": graph_rt.name,
                        "table_type": surrealdb_storage.table_type,
                        "vertices": surrealdb_storage.vertices,
                        "relations": surrealdb_storage.relations,
                    },
                )
                graph_sink = {
                    "kind": DataLinkKind.SURREALDBBINDING.value,
                    "name": graph_binding.name,
                    "namespace": self.namespace,
                }
                if settings.ENABLE_MULTI_TENANT_MODE:
                    graph_sink["tenant"] = self.bk_tenant_id
                graph_databus, _ = DataBusConfig.objects.update_or_create(
                    name=graph_databus_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                    defaults={
                        "data_id_name": graph_data_id_name,
                        "bk_data_id": data_source.bk_data_id,
                        "sink_names": [f"{graph_sink['kind']}:{graph_sink['name']}"],
                        # Transfer consumer group 只用于 VM 分支承接原消费位点。
                        # SurrealDB 分支必须使用独立消费组，避免与 VM Databus
                        # 竞争同一 Kafka 分区；同时清理早期错误写入的共享值。
                        "consumer_group": "",
                    },
                )

            configs.extend(
                [
                    graph_rt.compose_config(),
                    graph_binding.compose_config(),
                    graph_databus.compose_config([graph_sink], transforms=[]),
                ]
            )

        return configs

    def compose_log_configs(
        self,
        bk_biz_id: int,
        data_source: "DataSource",
        table_id: str,
        existing_context: ExistingComponentContext | None = None,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        """生成日志链路配置

        Args:
            bk_biz_id: 业务ID
            data_source: 数据源
            table_id: 结果表ID
            storage_cluster_name: 存储集群名称
            existing_context: 既有组件复用上下文。显式传入时按同 kind 组件唯一性
                尝试复用已有组件；默认不启用复用。
        """
        from metadata.models import ResultTableOption
        from metadata.models.result_table import LogV4DataLinkOption

        logger.info(
            "compose_log_configs: data_link_name->[%s],bk_biz_id->[%s],data_source->[%s],table_id->[%s]",
            self.data_link_name,
            bk_biz_id,
            data_source,
            table_id,
        )
        es_storage = ESStorage.objects.filter(bk_tenant_id=self.bk_tenant_id, table_id=table_id).first()
        doris_storage = DorisStorage.objects.filter(bk_tenant_id=self.bk_tenant_id, table_id=table_id).first()

        config_list: list[dict[str, Any]] = []
        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            # 获取结果表选项
            option = ResultTableOption.objects.get(
                bk_tenant_id=self.bk_tenant_id, table_id=table_id, name=ResultTableOption.OPTION_V4_LOG_DATA_LINK
            ).value
            datalink_option = LogV4DataLinkOption(**json.loads(option))

            fields = generate_result_table_field_list(table_id=table_id, bk_tenant_id=self.bk_tenant_id)
            clean_rules = [clean_rule.model_dump() for clean_rule in datalink_option.clean_rules]

            existing_rt = (
                existing_context.claim(ResultTableConfig, lambda c: True) if existing_context is not None else None
            )
            rt_name = existing_rt.name if existing_rt is not None else self.data_link_name

            # 创建结果表配置
            result_table, _ = ResultTableConfig.objects.update_or_create(
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                namespace=self.namespace,
                data_link_name=self.data_link_name,
                name=rt_name,
                defaults={"table_id": table_id},
            )

            # 创建存储绑定配置
            databus_sinks: list[dict[str, Any]] = []
            bingding_configs: list[dict[str, Any]] = []

            # 创建ES存储绑定配置
            if es_storage and datalink_option.es_storage_config:
                storage_option = datalink_option.es_storage_config
                existing_binding = (
                    existing_context.claim(ESStorageBindingConfig, lambda c: True)
                    if existing_context is not None
                    else None
                )
                binding_name = existing_binding.name if existing_binding is not None else self.data_link_name
                binding, _ = ESStorageBindingConfig.objects.update_or_create(
                    bk_tenant_id=self.bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    namespace=self.namespace,
                    data_link_name=self.data_link_name,
                    name=binding_name,
                    defaults={
                        "es_cluster_name": es_storage.storage_cluster.cluster_name,
                        "timezone": es_storage.time_zone,
                        "table_id": table_id,
                        "bkbase_result_table_name": result_table.name,
                    },
                )

                # 生成索引规则
                index_name = table_id.replace(".", "_")
                write_alias = f"write_%Y%m%d_{index_name}"

                bingding_configs.append(
                    binding.compose_config(
                        storage_cluster_name=es_storage.storage_cluster.cluster_name,
                        write_alias_format=write_alias,
                        unique_field_list=storage_option.unique_field_list,
                        json_field_list=storage_option.json_field_list,
                        rt_name=result_table.name,
                    )
                )
                databus_sinks.append(
                    {
                        "kind": DataLinkKind.ESSTORAGEBINDING.value,
                        "name": binding.name,
                        "namespace": self.namespace,
                    }
                )

            # 创建 Doris 存储绑定配置
            if doris_storage and datalink_option.doris_storage_config:
                storage_option = datalink_option.doris_storage_config
                existing_binding = (
                    existing_context.claim(DorisStorageBindingConfig, lambda c: True)
                    if existing_context is not None
                    else None
                )
                binding_name = existing_binding.name if existing_binding is not None else self.data_link_name
                binding, _ = DorisStorageBindingConfig.objects.update_or_create(
                    bk_tenant_id=self.bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    namespace=self.namespace,
                    data_link_name=self.data_link_name,
                    name=binding_name,
                    defaults={
                        "table_id": table_id,
                        "bkbase_result_table_name": result_table.name,
                        "doris_cluster_name": doris_storage.storage_cluster.cluster_name,
                    },
                )
                bingding_configs.append(
                    binding.compose_config(
                        storage_cluster_name=doris_storage.storage_cluster.cluster_name,
                        storage_keys=storage_option.storage_keys,
                        json_fields=storage_option.json_fields,
                        field_config_group=storage_option.field_config_group,
                        original_json_fields=storage_option.original_json_fields,
                        expires=f"{doris_storage.expire_days}d",
                        flush_timeout=storage_option.flush_timeout,
                        rt_name=result_table.name,
                    )
                )
                databus_sinks.append(
                    {
                        "kind": DataLinkKind.DORISBINDING.value,
                        "name": binding.name,
                        "namespace": self.namespace,
                    }
                )

            # 补充租户ID
            if settings.ENABLE_MULTI_TENANT_MODE:
                for sink in databus_sinks:
                    sink["tenant"] = self.bk_tenant_id

            # 如果没有任何存储绑定配置，则抛出异常
            if not bingding_configs:
                raise ValueError("至少需要一个存储绑定配置")

            # 创建数据总线配置
            existing_databus = (
                existing_context.claim(DataBusConfig, lambda c: True) if existing_context is not None else None
            )
            databus_name = existing_databus.name if existing_databus is not None else self.data_link_name
            databus_data_id_name = (
                existing_databus.data_id_name
                if existing_databus is not None
                else utils.get_registered_bkdata_data_id_name(data_source, namespace=self.namespace)
            )
            databus, _ = DataBusConfig.objects.update_or_create(
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                namespace=self.namespace,
                data_link_name=self.data_link_name,
                name=databus_name,
                defaults={
                    "data_id_name": databus_data_id_name,
                    "bk_data_id": data_source.bk_data_id,
                    "sink_names": [f"{sink['kind']}:{sink['name']}" for sink in databus_sinks],
                },
            )
            databus.apply_consumer_group(consumer_group)

            # 组装配置
            config_list.extend(
                [
                    result_table.compose_config(fields=fields),
                    *bingding_configs,
                    databus.compose_log_config(sinks=databus_sinks, rules=clean_rules),
                ]
            )

        return config_list

    def compose_system_proc_configs(
        self,
        data_link_strategy: str,
        data_source: "DataSource",
        table_id: str,
        storage_cluster_name: str,
        bk_biz_id: int,
        prefix: str | None = None,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        生成系统进程链路配置
        """
        logger.info(
            "compose_system_proc_configs: data_link_name->[%s],bk_biz_id->[%s],data_link_strategy->[%s],data_source->[%s],table_id->[%s],storage_cluster_name->[%s]",
            self.data_link_name,
            bk_biz_id,
            data_link_strategy,
            data_source,
            table_id,
            storage_cluster_name,
        )

        if prefix is None:
            bkbase_vmrt_prefix = f"base_{bk_biz_id}"
        else:
            bkbase_vmrt_prefix = prefix

        if bkbase_vmrt_prefix:
            bkbase_vmrt_name = f"{bkbase_vmrt_prefix}_{data_link_strategy}"
        else:
            bkbase_vmrt_name = data_link_strategy
        bkbase_vmrt_cmdb_name = f"{bkbase_vmrt_name}_cmdb"
        cmdb_table_id = f"{table_id}_cmdb"

        transform_format_map = {
            DataLink.SYSTEM_PROC_PERF: SYSTEM_PROC_PERF_DATABUS_FORMAT,
            DataLink.SYSTEM_PROC_PORT: SYSTEM_PROC_PORT_DATABUS_FORMAT,
        }
        basereport_metric_type_map = {
            DataLink.SYSTEM_PROC_PERF: SYSTEM_PROC_PERF_BASEREPORT_METRIC_TYPE,
            DataLink.SYSTEM_PROC_PORT: SYSTEM_PROC_PORT_BASEREPORT_METRIC_TYPE,
        }

        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            vm_table_id_ins, _ = ResultTableConfig.objects.update_or_create(
                name=bkbase_vmrt_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={"table_id": table_id},
            )

            vm_storage_ins, _ = VMStorageBindingConfig.objects.update_or_create(
                name=bkbase_vmrt_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "table_id": table_id,
                    "bkbase_result_table_name": bkbase_vmrt_name,
                    "vm_cluster_name": storage_cluster_name,
                },
            )

            vm_table_id_ins_cmdb, _ = ResultTableConfig.objects.update_or_create(
                name=bkbase_vmrt_cmdb_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={"table_id": cmdb_table_id},
            )

            vm_storage_ins_cmdb, _ = VMStorageBindingConfig.objects.update_or_create(
                name=bkbase_vmrt_cmdb_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "table_id": cmdb_table_id,
                    "bkbase_result_table_name": bkbase_vmrt_cmdb_name,
                    "vm_cluster_name": storage_cluster_name,
                },
            )

            basereport_sink_ins, _ = BasereportSinkConfig.objects.update_or_create(
                name=self.data_link_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "vm_storage_binding_names": [vm_storage_ins.name, vm_storage_ins_cmdb.name],
                    "result_table_ids": [table_id, cmdb_table_id],
                },
            )
            sink_item = {
                "kind": DataLinkKind.BASEREPORTSINK.value,
                "name": self.data_link_name,
                "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                **({"tenant": self.bk_tenant_id} if settings.ENABLE_MULTI_TENANT_MODE else {}),
            }

            data_bus_ins, _ = DataBusConfig.objects.update_or_create(
                name=self.data_link_name,
                data_id_name=self.data_link_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "bk_data_id": data_source.bk_data_id,
                    "sink_names": [f"{sink_item['kind']}:{sink_item['name']}"],
                },
            )
            data_bus_ins.apply_consumer_group(consumer_group)

        configs = [
            vm_table_id_ins.compose_config(),
            vm_storage_ins.compose_config(),
            vm_table_id_ins_cmdb.compose_config(),
            vm_storage_ins_cmdb.compose_config(),
        ]
        configs.append(
            basereport_sink_ins.compose_config(
                vmrt_prefix="",
                metric_type_to_vm_storage_binding_name={
                    basereport_metric_type_map[data_link_strategy]: vm_storage_ins.name,
                    f"{basereport_metric_type_map[data_link_strategy]}_cmdb": vm_storage_ins_cmdb.name,
                },
            )
        )
        configs.append(
            data_bus_ins.compose_config(sinks=[sink_item], transform_format=transform_format_map[data_link_strategy])
        )
        return configs

    def compose_basereport_time_series_configs(
        self,
        data_source: "DataSource",
        storage_cluster_name: str,
        bk_biz_id: int,
        source: str,
        prefix: str | None = None,
        extra_source: str | None = None,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        生成基础采集时序链路配置
        @param data_source: 数据源
        @param storage_cluster_name: 存储集群名称
        @param bk_biz_id: 业务id
        @param source: 数据来源
        @param extra_source: 额外主机维度数据来源
        @return: config_list 配置列表
        """
        logger.info(
            "compose_basereport_configs: data_link_name->[%s],bk_biz_id->[%s],bk_data_id->[%s],vm_cluster_name->[%s] "
            "start to compose configs",
            self.data_link_name,
            bk_biz_id,
            data_source.bk_data_id,
            storage_cluster_name,
        )

        # 需要注意超出计算平台meta长度限制问题
        if prefix is None:
            bkbase_vmrt_prefix = f"base_{bk_biz_id}_{source}"
        else:
            bkbase_vmrt_prefix = prefix

        config_list = []
        basereport_result_table_ids = []
        basereport_vm_storage_binding_names = []
        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            # 创建11个ResultTableConfig和VMStorageBindingConfig
            for usage in BASEREPORT_USAGES:
                if bkbase_vmrt_prefix:
                    usage_vmrt_name = f"{bkbase_vmrt_prefix}_{usage}"
                else:
                    usage_vmrt_name = usage
                usage_cmdb_level_vmrt_name = f"{usage_vmrt_name}_cmdb"
                # 关联监控平台结果表ID（monitor table_id），用于配置与元数据关联
                usage_monitor_table_id = f"{self.bk_tenant_id}_{bk_biz_id}_{source}.{usage}"
                usage_monitor_cmdb_table_id = f"{self.bk_tenant_id}_{bk_biz_id}_{source}.{usage}_cmdb"
                basereport_result_table_ids.extend([usage_monitor_table_id, usage_monitor_cmdb_table_id])
                logger.info(
                    "compose_basereport_configs: try to create rt and storage for usage->[%s],name->[%s]",
                    usage,
                    usage_vmrt_name,
                )

                # 创建VM ResultTable配置
                vm_table_id_ins, _ = ResultTableConfig.objects.update_or_create(
                    name=usage_vmrt_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                    defaults={"table_id": usage_monitor_table_id},
                )
                vm_table_id_ins_cmdb, _ = ResultTableConfig.objects.update_or_create(
                    name=usage_cmdb_level_vmrt_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                    defaults={"table_id": usage_monitor_cmdb_table_id},
                )

                # 创建VM Storage绑定配置
                vm_storage_ins, _ = VMStorageBindingConfig.objects.update_or_create(
                    name=usage_vmrt_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                    defaults={
                        "table_id": usage_monitor_table_id,
                        "bkbase_result_table_name": usage_vmrt_name,
                        "vm_cluster_name": storage_cluster_name,
                    },
                )
                vm_storage_ins_cmdb, _ = VMStorageBindingConfig.objects.update_or_create(
                    name=usage_cmdb_level_vmrt_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                    defaults={
                        "table_id": usage_monitor_cmdb_table_id,
                        "bkbase_result_table_name": usage_cmdb_level_vmrt_name,
                        "vm_cluster_name": storage_cluster_name,
                    },
                )
                basereport_vm_storage_binding_names.extend([vm_storage_ins.name, vm_storage_ins_cmdb.name])

                # 添加配置到列表
                config_list.extend(
                    [
                        vm_table_id_ins.compose_config(),
                        vm_table_id_ins_cmdb.compose_config(),
                        vm_storage_ins.compose_config(),
                        vm_storage_ins_cmdb.compose_config(),
                    ]
                )

            # 创建DataBusConfig
            data_bus_ins, _ = DataBusConfig.objects.update_or_create(
                name=self.data_link_name,
                data_id_name=self.data_link_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "bk_data_id": data_source.bk_data_id,
                    "sink_names": [f"{DataLinkKind.BASEREPORTSINK.value}:{self.data_link_name}"],
                },
            )
            data_bus_ins.apply_consumer_group(consumer_group)
            basereport_sink_ins, _ = BasereportSinkConfig.objects.update_or_create(
                name=self.data_link_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "vm_storage_binding_names": basereport_vm_storage_binding_names,
                    "result_table_ids": basereport_result_table_ids,
                },
            )

        basereport_sink_ref = {
            "kind": DataLinkKind.BASEREPORTSINK.value,
            "name": self.data_link_name,
            "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        }
        if settings.ENABLE_MULTI_TENANT_MODE:
            basereport_sink_ref["tenant"] = self.bk_tenant_id

        # 组装data bus配置
        data_bus_config = data_bus_ins.compose_config(
            sinks=[basereport_sink_ref], transform_format=BASEREPORT_DATABUS_FORMAT
        )

        config_list.extend(
            [
                basereport_sink_ins.compose_config(vmrt_prefix=bkbase_vmrt_prefix, include_cmdb=True),
                data_bus_config,
            ]
        )

        if extra_source:
            config_list.extend(
                self._compose_basereport_time_series_extra_dimension_configs(
                    data_source=data_source,
                    storage_cluster_name=storage_cluster_name,
                    bk_biz_id=bk_biz_id,
                    extra_source=extra_source,
                    consumer_group=consumer_group,
                )
            )

        logger.info(
            "compose_basereport_configs: data_link_name->[%s] composed %d configs successfully",
            self.data_link_name,
            len(config_list),
        )

        return config_list

    def _compose_basereport_time_series_extra_dimension_configs(
        self,
        data_source: "DataSource",
        storage_cluster_name: str,
        bk_biz_id: int,
        extra_source: str,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        生成基础采集额外主机维度链路配置。
        """
        logger.info(
            "compose_basereport_extra_dimension_configs: data_link_name->[%s],bk_biz_id->[%s],"
            "bk_data_id->[%s],vm_cluster_name->[%s],extra_source->[%s] start to compose configs",
            self.data_link_name,
            bk_biz_id,
            data_source.bk_data_id,
            storage_cluster_name,
            extra_source,
        )
        extra_data_link_name = f"{self.data_link_name}_{extra_source}"
        bkbase_vmrt_prefix = f"base_{bk_biz_id}_{extra_source}"
        config_list = []
        result_table_ids = []
        vm_storage_binding_names = []

        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            for usage in BASEREPORT_USAGES:
                usage_vmrt_name = f"{bkbase_vmrt_prefix}_{usage}"
                usage_monitor_table_id = f"{self.bk_tenant_id}_{bk_biz_id}_{extra_source}.{usage}"
                result_table_ids.append(usage_monitor_table_id)

                vm_table_id_ins, _ = ResultTableConfig.objects.update_or_create(
                    name=usage_vmrt_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                    defaults={"table_id": usage_monitor_table_id},
                )
                vm_storage_ins, _ = VMStorageBindingConfig.objects.update_or_create(
                    name=usage_vmrt_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                    defaults={
                        "table_id": usage_monitor_table_id,
                        "bkbase_result_table_name": usage_vmrt_name,
                        "vm_cluster_name": storage_cluster_name,
                    },
                )
                vm_storage_binding_names.append(vm_storage_ins.name)

                config_list.extend([vm_table_id_ins.compose_config(), vm_storage_ins.compose_config()])

            data_bus_ins, _ = DataBusConfig.objects.update_or_create(
                name=extra_data_link_name,
                data_id_name=self.data_link_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "bk_data_id": data_source.bk_data_id,
                    "sink_names": [f"{DataLinkKind.BASEREPORTSINK.value}:{extra_data_link_name}"],
                },
            )
            data_bus_ins.apply_consumer_group(consumer_group)
            basereport_sink_ins, _ = BasereportSinkConfig.objects.update_or_create(
                name=extra_data_link_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "vm_storage_binding_names": vm_storage_binding_names,
                    "result_table_ids": result_table_ids,
                },
            )

        basereport_sink_ref = {
            "kind": DataLinkKind.BASEREPORTSINK.value,
            "name": extra_data_link_name,
            "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        }
        if settings.ENABLE_MULTI_TENANT_MODE:
            basereport_sink_ref["tenant"] = self.bk_tenant_id

        config_list.append(basereport_sink_ins.compose_config(vmrt_prefix=bkbase_vmrt_prefix))
        config_list.append(
            data_bus_ins.compose_config(
                sinks=[basereport_sink_ref],
                transform_format=BASEREPORT_DATABUS_FORMAT,
                transform_options={"extra_dims": True},
            )
        )

        logger.info(
            "compose_basereport_extra_dimension_configs: data_link_name->[%s],extra_source->[%s] composed %d configs",
            self.data_link_name,
            extra_source,
            len(config_list),
        )
        return config_list

    def compose_base_event_configs(
        self,
        data_source: "DataSource",
        table_id: str,
        storage_cluster_name: str,
        bk_biz_id: int,
        timezone: int = 0,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        生成基础事件链路配置(固定逻辑)
        @param data_source: 数据源
        @param table_id: 监控平台结果表ID
        @param storage_cluster_name: 存储集群名称(ES)
        @param bk_biz_id: 业务id
        @param timezone: 时区 默认0时区
        """
        from metadata.models import ResultTableOption

        component_name = f"base_{bk_biz_id}_agent_event"

        logger.info(
            "compose_base_event_configs: data_link_name->[%s],bk_biz_id->[%s],bk_data_id->[%s],es_cluster_name->[%s],table_id->[%s]"
            "start to compose configs",
            self.data_link_name,
            bk_biz_id,
            data_source.bk_data_id,
            storage_cluster_name,
            table_id,
        )

        config_list = []

        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            es_table_ins, _ = ResultTableConfig.objects.update_or_create(
                name=component_name,
                namespace=self.namespace,
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                data_link_name=self.data_link_name,
                defaults={"table_id": table_id},
            )

            es_storage_ins, _ = ESStorageBindingConfig.objects.update_or_create(
                name=component_name,
                namespace=self.namespace,
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                data_link_name=self.data_link_name,
                defaults={
                    "table_id": table_id,
                    "bkbase_result_table_name": component_name,
                    "es_cluster_name": storage_cluster_name,
                    "timezone": timezone,
                },
            )

            fields = generate_result_table_field_list(table_id=table_id, bk_tenant_id=self.bk_tenant_id)
            index_name = table_id.replace(".", "_")
            write_alias = f"write_%Y%m%d_{index_name}"
            unique_field_list = json.loads(
                ResultTableOption.objects.get(table_id=table_id, name="es_unique_field_list").value
            )

            databus_ins, _ = DataBusConfig.objects.update_or_create(
                name=component_name,
                namespace=self.namespace,
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                data_link_name=self.data_link_name,
                data_id_name=component_name,
                defaults={
                    "bk_data_id": data_source.bk_data_id,
                    "sink_names": [f"{DataLinkKind.ESSTORAGEBINDING.value}:{component_name}"],
                },
            )
            databus_ins.apply_consumer_group(consumer_group)

            es_rt_config = es_table_ins.compose_config(fields=fields)
            es_binding_config = es_storage_ins.compose_config(
                storage_cluster_name=storage_cluster_name,
                write_alias_format=write_alias,
                unique_field_list=unique_field_list,
            )
            databus_config = databus_ins.compose_base_event_config()

            config_list.extend([es_rt_config, es_binding_config, databus_config])
            logger.info(
                "compose_base_event_configs: data_link_name->[%s] composed configs successfully,config_list->[%s]",
                self.data_link_name,
                config_list,
            )

        return config_list

    def compose_bcs_federal_proxy_time_series_configs(
        self,
        bk_biz_id: int,
        data_source: "DataSource",
        table_id: str,
        storage_cluster_name: str,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        生成联邦代理集群（父集群）时序数据链路配置
        """

        logger.info(
            "compose_federal_proxy_configs: data_link_name->[%s],bk_biz_id->[%s],bk_data_id->[%s],table_id->[%s],vm_cluster_name->[%s]"
            "start to compose configs",
            self.data_link_name,
            bk_biz_id,
            data_source.bk_data_id,
            table_id,
            storage_cluster_name,
        )

        bkbase_data_name = utils.compose_bkdata_data_id_name(data_source.data_name, self.data_link_strategy)
        bkbase_vmrt_name = utils.compose_bkdata_table_id(table_id, self.data_link_strategy)

        logger.info(
            "compose_federal_proxy_configs: data_link_name->[%s] start to use bkbase_data_name->[%s] "
            "bkbase_vmrt_name->[%s]to"
            "compose configs",
            self.data_link_name,
            bkbase_data_name,
            bkbase_vmrt_name,
        )

        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            # 渲染所需的资源配置
            vm_table_id_ins, _ = ResultTableConfig.objects.update_or_create(
                name=bkbase_vmrt_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={"table_id": table_id},
            )
            vm_storage_ins, _ = VMStorageBindingConfig.objects.update_or_create(
                name=bkbase_vmrt_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "table_id": table_id,
                    "bkbase_result_table_name": bkbase_vmrt_name,
                    "vm_cluster_name": storage_cluster_name,
                },
            )

        configs = [
            vm_table_id_ins.compose_config(),
            vm_storage_ins.compose_config(),
        ]
        return configs

    def compose_bcs_federal_subset_time_series_configs(
        self,
        bk_biz_id: int,
        data_source: "DataSource",
        table_id: str,
        storage_cluster_name: str,
        federation_routes: list[dict[str, Any]],
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        生成联邦子集群时序数据链路配置
        @param data_source: 数据源
        @param table_id: 监控平台结果表ID
        @param storage_cluster_name: 存储集群名称
        @param federation_routes: 已由联邦领域服务完成租户过滤、冲突检查和排序的路由列表
        @return: config_list 配置列表
        """
        logger.info(
            "compose_federal_sub_configs: data_link_name->[%s],bk_biz_id->[%s],bk_data_id->[%s],table_id->[%s],vm_cluster_name->[%s]"
            "start to compose configs",
            self.data_link_name,
            bk_biz_id,
            data_source.bk_data_id,
            table_id,
            storage_cluster_name,
        )

        # 联邦子集群场景下，这里的bkbase_data_name会有一个fed_的前缀
        bkbase_raw_data_name = get_bkbase_raw_data_id_name(data_source=data_source, table_id=table_id)
        bkbase_data_name = utils.compose_bkdata_data_id_name(data_source.data_name, self.data_link_strategy)
        bkbase_vmrt_name = utils.compose_bkdata_table_id(table_id, self.data_link_strategy)

        logger.info(
            "compose_federal_sub_configs: data_link_name->[%s] start to use bkbase_data_name->[%s] "
            "bkbase_vmrt_name->[%s]to"
            "compose configs",
            self.data_link_name,
            bkbase_data_name,
            bkbase_vmrt_name,
        )

        if not federation_routes:
            raise ValueError(
                f"compose_federal_sub_configs: data_link_name({self.data_link_name}) federation_routes is empty"
            )

        config_list, conditions = [], []
        for route in federation_routes:
            # 联邦代理集群的RT名
            proxy_k8s_metric_vmrt_name = utils.compose_bkdata_table_id(route["target_metric_table_id"])
            relabels = [{"name": "bcs_cluster_id", "value": route["fed_cluster_id"]}]
            logger.info(
                "compose_federal_sub_configs: data_link_name->[%s] start to compose for fed_cluster_id->[%s],"
                "match_labels ->[%s]",
                self.data_link_name,
                route["fed_cluster_id"],
                route["namespaces"],
            )
            # 联邦集群链路格式调整,由原先的每一个Namespace一个Condition变更为每一个联邦拓扑一个Condition，通过any方式进行匹配
            sinks = [
                {
                    "kind": "VmStorageBinding",
                    "name": proxy_k8s_metric_vmrt_name,
                    "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                }
            ]
            if settings.ENABLE_MULTI_TENANT_MODE:
                sinks[0]["tenant"] = self.bk_tenant_id

            condition = {
                "match_labels": [{"name": "namespace", "any": route["namespaces"]}],
                "relabels": relabels,
                "sinks": sinks,
            }
            conditions.append(condition)

        logger.info(
            "compose_federal_sub_configs: data_link_name->[%s] will use conditions->[%s]to compose configs",
            self.data_link_name,
            conditions,
        )

        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            vm_conditional_ins, _ = ConditionalSinkConfig.objects.update_or_create(
                name=bkbase_vmrt_name,
                namespace=self.namespace,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "data_link_name": self.data_link_name,
                    "bk_biz_id": bk_biz_id,
                },
            )
            data_bus_ins, _ = DataBusConfig.objects.update_or_create(
                name=bkbase_vmrt_name,
                namespace=self.namespace,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "data_id_name": bkbase_raw_data_name,
                    "data_link_name": self.data_link_name,
                    "bk_biz_id": bk_biz_id,
                    "bk_data_id": data_source.bk_data_id,
                    "sink_names": [f"{DataLinkKind.CONDITIONALSINK.value}:{bkbase_vmrt_name}"],
                },
            )
            data_bus_ins.apply_consumer_group(consumer_group)

        vm_conditional_sink_config = vm_conditional_ins.compose_conditional_sink_config(conditions=conditions)
        conditional_sink = [
            {
                "kind": DataLinkKind.CONDITIONALSINK.value,
                "name": bkbase_vmrt_name,
                "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            },
        ]
        if settings.ENABLE_MULTI_TENANT_MODE:
            conditional_sink[0]["tenant"] = self.bk_tenant_id

        data_bus_config = data_bus_ins.compose_config(sinks=conditional_sink)
        config_list.extend([vm_conditional_sink_config, data_bus_config])
        return config_list

    def _compose_vm_time_series_component_configs(
        self,
        *,
        bk_biz_id: int,
        data_source: "DataSource",
        table_id: str,
        storage_cluster_name: str,
        rt_name: str,
        binding_name: str,
        databus_name: str,
        bkbase_data_name: str,
        metric_group_dimensions: list[dict[str, Any]] | None = None,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        """按已解析的稳定名称创建普通 VM 组件。"""
        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            vm_table_id_ins, _ = ResultTableConfig.objects.update_or_create(
                name=rt_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={"table_id": table_id, "data_type": "metric"},
            )
            vm_storage_ins, _ = VMStorageBindingConfig.objects.update_or_create(
                name=binding_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "table_id": table_id,
                    "bkbase_result_table_name": vm_table_id_ins.name,
                    "vm_cluster_name": storage_cluster_name,
                },
            )
            sink_item = {
                "kind": DataLinkKind.VMSTORAGEBINDING.value,
                "name": vm_storage_ins.name,
                "namespace": self.namespace,
            }
            if settings.ENABLE_MULTI_TENANT_MODE:
                sink_item["tenant"] = self.bk_tenant_id
            sinks = [sink_item]

            data_bus_ins, _ = DataBusConfig.objects.update_or_create(
                name=databus_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "data_id_name": bkbase_data_name,
                    "bk_data_id": data_source.bk_data_id,
                    "sink_names": [f"{sink_item['kind']}:{sink_item['name']}"],
                },
            )
            data_bus_ins.apply_consumer_group(consumer_group)

        return [
            vm_table_id_ins.compose_config(),
            vm_storage_ins.compose_config(
                rt_name=vm_table_id_ins.name,
                metric_group_dimensions=metric_group_dimensions,
            ),
            data_bus_ins.compose_config(sinks),
        ]

    def compose_standard_time_series_configs(
        self,
        bk_biz_id: int,
        data_source: "DataSource",
        table_id: str,
        storage_cluster_name: str,
        existing_context: "ExistingComponentContext | None" = None,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        生成标准单指标单表时序数据链路配置 -- bk_standard_v2

        @param data_source: 数据源
        @param table_id: 监控平台结果表ID（Metadata中的）
        @param storage_cluster_name: VM集群名称
        @param existing_context: 已有组件复用上下文；由灰度开关控制，仅当当前
            strategy 同时出现在 ``settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES``
            与 ``component_reuse.REUSE_ENABLED_STRATEGIES`` 时由上层注入。非 None 时
            compose 会尝试按 ``table_id`` / ``data_id_name`` 从已有组件池中认领名称，
            避免迁移/改名场景下重复创建组件。未认领到时回退到 ``bkbase_vmrt_name``
            新建语义。

        注意：``vm_cluster_name`` 放在 defaults 中，允许复用既有 binding 时同步更新 VM 集群名称；
        ``DataBusConfig`` 仍按 ``data_id_name`` 作为稳定查询条件命中既有记录。
        """

        from metadata.models import ResultTableOption

        logger.info(
            "compose_configs: data_link_name->[%s] ,bk_data_id->[%s],table_id->[%s],vm_cluster_name->[%s] "
            "start to compose configs",
            self.data_link_name,
            data_source.bk_data_id,
            table_id,
            storage_cluster_name,
        )
        bkbase_vmrt_name = utils.compose_bkdata_table_id(table_id, self.data_link_strategy)

        # 解析 compose 所需的 name：优先复用既有组件的 name，否则回退到新生成的
        # bkbase_vmrt_name。bk_exporter 允许同时存在主 RT 和 _cmdb RT，需要按 slot 分别 claim；
        # 其他插件链路仍保持同 kind 一对一，歧义组件留给 leftover 校验兜底。
        existing_rt = (
            existing_context.claim(ResultTableConfig, lambda component: component.data_type != "graph")
            if existing_context is not None
            else None
        )
        rt_name = bkbase_vmrt_name
        if existing_rt:
            rt_name = existing_rt.name
        else:
            # 复用已有AccessVMRecord记录的vm_result_table_id作为结果表名称
            existing_vm_record = AccessVMRecord.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                result_table_id=table_id,
            ).last()
            if existing_vm_record:
                # 需要剔除业务ID前缀
                vmrt_id = existing_vm_record.vm_result_table_id
                rt_name = vmrt_id.split("_", 1)[-1]

        existing_binding = (
            existing_context.claim(VMStorageBindingConfig, lambda c: True) if existing_context is not None else None
        )
        binding_name = existing_binding.name if existing_binding is not None else bkbase_vmrt_name

        existing_databus = (
            existing_context.claim(
                DataBusConfig,
                lambda component: (
                    not any(
                        sink_name.startswith(f"{DataLinkKind.SURREALDBBINDING.value}:")
                        for sink_name in component.sink_names
                    )
                ),
            )
            if existing_context is not None
            else None
        )

        databus_name = existing_databus.name if existing_databus is not None else bkbase_vmrt_name
        bkbase_data_name = (
            existing_databus.data_id_name
            if existing_databus is not None
            else utils.get_registered_bkdata_data_id_name(data_source, namespace=self.namespace)
        )
        logger.info(
            "compose_configs: data_link_name->[%s] start to use bkbase_data_name->[%s] bkbase_vmrt_name->[%s]to "
            "compose configs",
            self.data_link_name,
            bkbase_data_name,
            bkbase_vmrt_name,
        )

        # 获取指标组维度配置
        result_table_option = ResultTableOption.objects.filter(
            table_id=table_id, bk_tenant_id=self.bk_tenant_id, name=ResultTableOption.OPTION_METRIC_GROUP_DIMENSIONS
        ).first()
        metric_group_dimensions: list[dict[str, Any]] | None = (
            result_table_option.get_value() if result_table_option is not None else None
        )

        return self._compose_vm_time_series_component_configs(
            bk_biz_id=bk_biz_id,
            data_source=data_source,
            table_id=table_id,
            storage_cluster_name=storage_cluster_name,
            rt_name=rt_name,
            binding_name=binding_name,
            databus_name=databus_name,
            bkbase_data_name=bkbase_data_name,
            metric_group_dimensions=metric_group_dimensions,
            consumer_group=consumer_group,
        )

    def _compose_time_series_field_whitelist(
        self, table_id: str, *, force: bool = False
    ) -> dict[Literal["metrics", "tags"], list[str]] | None:
        """组装采集插件时序结果表的指标/维度白名单。

        仅当结果表显式关闭字段黑名单（``enable_field_black_list == "false"`` 即启用白名单模式）时
        才返回白名单，否则返回 ``None`` 表示不下发白名单。

        白名单来源说明：
            - ``metrics``：取 ``ResultTableField`` 中的指标字段，并叠加 ``TimeSeriesMetric`` 中的活跃指标。
              在 ``TimeSeriesMetric`` 中已不活跃 / 被禁用的指标不会放行；未被 ``TimeSeriesMetric``
              记录的 RT 指标维持原行为（仍放行）。
            - ``tags``：取 ``ResultTableField`` 中的维度字段，并用活跃指标的 ``tag_list`` 补全。
              因为 ``TimeSeriesGroup`` 通过 ``field_list`` 创建指标时，维度只记录在
              ``TimeSeriesMetric.tag_list`` 中，并不会同步写入 ``ResultTableField``，仅依赖 RT 会丢维度。

        Args:
            table_id: 监控侧结果表 ID。
            force: 是否忽略结果表选项并强制生成白名单。

        Returns:
            白名单字典 ``{"metrics": [...], "tags": [...]}``；非白名单模式时返回 ``None``。
        """
        from metadata.models import ResultTableField, ResultTableOption, TimeSeriesGroup, TimeSeriesMetric

        option = ResultTableOption.objects.filter(
            table_id=table_id, bk_tenant_id=self.bk_tenant_id, name=ResultTableOption.OPTION_ENABLE_FIELD_BLACK_LIST
        ).first()
        if not force and not (option and option.value == "false"):
            return None

        # 先汇总 TimeSeriesMetric 的活跃状态与维度信息。
        # 注意：TimeSeriesGroup 是软删除模型，需过滤 is_delete=False，避免拿到历史软删记录把
        # 已退场 group 的指标/维度误带入（同一 table_id 不会存在多个活跃 group，取一条即可）。
        active_metric_names: set[str] = set()
        inactive_metric_names: set[str] = set()
        active_metric_tags: set[str] = set()
        ts_group = TimeSeriesGroup.objects.filter(
            table_id=table_id, bk_tenant_id=self.bk_tenant_id, is_delete=False
        ).first()
        if ts_group:
            ts_metrics = TimeSeriesMetric.objects.filter(group_id=ts_group.time_series_group_id).values_list(
                "field_name", "is_active", "scope_id", "tag_list"
            )
            for field_name, is_active, scope_id, tag_list in ts_metrics:
                # 活跃指标：is_active=True 且未落在被手动禁用的分组（scope_id=DISABLE_SCOPE_ID）。
                if is_active and scope_id != TimeSeriesMetric.DISABLE_SCOPE_ID:
                    active_metric_names.add(field_name)
                    active_metric_tags.update(tag_list or [])
                else:
                    inactive_metric_names.add(field_name)
            # 同名指标可能同时存在活跃与不活跃记录（多分组），只要任一分组活跃即视为活跃。
            inactive_metric_names -= active_metric_names

        result_table_fields = ResultTableField.objects.filter(
            table_id=table_id, bk_tenant_id=self.bk_tenant_id, is_disabled=False
        )
        metrics, tags = [], []
        # 去重集合：保证幂等且保留列表的稳定追加顺序。
        metric_set: set[str] = set()
        tag_set: set[str] = set()
        for field in result_table_fields:
            if field.tag == ResultTableField.FIELD_TAG_METRIC:
                # 在 TimeSeriesMetric 中明确为不活跃/禁用的指标不放行到白名单。
                # 未被 TimeSeriesMetric 记录的指标维持原行为（仍然放行）。
                if field.field_name in inactive_metric_names:
                    continue
                if field.field_name not in metric_set:
                    metric_set.add(field.field_name)
                    metrics.append(field.field_name)
            elif field.tag == ResultTableField.FIELD_TAG_DIMENSION:
                if field.field_name not in tag_set:
                    tag_set.add(field.field_name)
                    tags.append(field.field_name)

        # 直接补全 TimeSeriesMetric 中的活跃指标及其维度（排序保证输出稳定）。
        for metric in sorted(active_metric_names):
            if metric not in metric_set:
                metric_set.add(metric)
                metrics.append(metric)
        for tag in sorted(active_metric_tags):
            if tag not in tag_set:
                tag_set.add(tag)
                tags.append(tag)

        return {"metrics": metrics, "tags": tags}

    def _compose_custom_format_vm_whitelist(self, table_id: str) -> dict[Literal["metrics", "tags"], list[str]] | None:
        """按最终指标配置决定自定义格式 VM 是否下发白名单。"""

        from metadata.models import TimeSeriesGroup

        time_series_group = TimeSeriesGroup.objects.filter(
            table_id=table_id,
            bk_tenant_id=self.bk_tenant_id,
            is_delete=False,
        ).first()
        if time_series_group is not None and time_series_group.is_auto_discovery():
            return None

        whitelist = self._compose_time_series_field_whitelist(table_id, force=True)
        if not whitelist or not whitelist["metrics"]:
            raise ValueError(f"自定义格式固定指标 ResultTable({table_id}) 缺少有效指标字段")
        return whitelist

    def compose_bk_plugin_time_series_config(
        self,
        bk_biz_id: int,
        data_source: "DataSource",
        table_id: str,
        storage_cluster_name: str,
        existing_context: "ExistingComponentContext | None" = None,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        生成采集插件时序数据链路配置 -- bk_standard & bk_exporter

        当 ``existing_context`` 非 None 时（由灰度开关控制），会尝试基于
        ``table_id`` / ``data_id_name`` 从已有组件池中认领名称，用于复用历史组件避免
        重复创建。未认领到时回退到 ``bkbase_vmrt_name`` 新建语义。

        注意：``vm_cluster_name`` 放在 defaults 中，允许复用既有 binding 时同步更新 VM 集群名称；
        ``DataBusConfig`` 仍按 ``data_id_name`` 作为稳定查询条件命中既有记录。
        """
        bkbase_vmrt_name = utils.compose_bkdata_table_id(table_id, self.data_link_strategy)
        cmdb_table_id = f"{table_id}_cmdb"
        exporter_cmdb_enabled = False
        if self.data_link_strategy == self.BK_EXPORTER_TIME_SERIES:
            from metadata.models.result_table import ResultTableOption

            cmdb_level_option = ResultTableOption.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                table_id=table_id,
                name=ResultTableOption.OPTION_CMDB_LEVEL_CONFIG,
            ).first()
            cmdb_levels = cmdb_level_option.get_value() if cmdb_level_option is not None else None
            exporter_cmdb_enabled = isinstance(cmdb_levels, list) and bool(cmdb_levels)

        # 白名单配置
        whitelist = self._compose_time_series_field_whitelist(table_id)

        # 解析 compose 所需的 name：优先复用既有组件的 name（若同 kind 恰好只有
        # 一条可 claim），否则回退到新生成的 bkbase_vmrt_name 作为新建名称。
        # 存量链路里 table_id / bk_data_id 可能缺失，复用判断只依赖 datalink
        # 下同 kind 组件的一对一关系；同 kind 多条会留给 leftover 校验兜底。
        if existing_context is not None:
            if self.data_link_strategy == self.BK_EXPORTER_TIME_SERIES:
                existing_rt = existing_context.claim(
                    ResultTableConfig,
                    lambda c: c.table_id != cmdb_table_id and not c.name.endswith("_cmdb"),
                )
            else:
                existing_rt = existing_context.claim(ResultTableConfig, lambda c: True)
        else:
            existing_rt = None
        rt_name = bkbase_vmrt_name
        if existing_rt:
            rt_name = existing_rt.name
        else:
            # 复用已有AccessVMRecord记录的vm_result_table_id作为结果表名称
            existing_vm_record = AccessVMRecord.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                result_table_id=table_id,
            ).last()
            if existing_vm_record:
                # 需要剔除业务ID前缀
                vmrt_id = existing_vm_record.vm_result_table_id
                rt_name = vmrt_id.split("_", 1)[-1]

        cmdb_rt_name = f"{rt_name}_cmdb"
        existing_cmdb_rt = None
        if existing_context is not None and self.data_link_strategy == self.BK_EXPORTER_TIME_SERIES:
            existing_cmdb_rt = existing_context.claim(
                ResultTableConfig,
                lambda c: c.table_id == cmdb_table_id or c.name == cmdb_rt_name,
            )
            if existing_cmdb_rt is not None:
                cmdb_rt_name = existing_cmdb_rt.name

        should_compose_cmdb_rt = exporter_cmdb_enabled or existing_cmdb_rt is not None
        if self.data_link_strategy == self.BK_EXPORTER_TIME_SERIES and not should_compose_cmdb_rt:
            should_compose_cmdb_rt = ResultTableConfig.objects.filter(
                name=cmdb_rt_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_tenant_id=self.bk_tenant_id,
            ).exists()

        existing_binding = (
            existing_context.claim(VMStorageBindingConfig, lambda c: True) if existing_context is not None else None
        )
        binding_name = existing_binding.name if existing_binding is not None else bkbase_vmrt_name

        existing_databus = (
            existing_context.claim(DataBusConfig, lambda c: True) if existing_context is not None else None
        )
        databus_name = existing_databus.name if existing_databus is not None else bkbase_vmrt_name
        bkbase_data_name = (
            existing_databus.data_id_name
            if existing_databus is not None
            else utils.get_registered_bkdata_data_id_name(data_source, namespace=self.namespace)
        )

        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            # 渲染所需的资源配置
            vm_table_id_ins, _ = ResultTableConfig.objects.update_or_create(
                name=rt_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={"table_id": table_id},
            )
            vm_table_id_ins_cmdb = None
            if should_compose_cmdb_rt:
                vm_table_id_ins_cmdb, _ = ResultTableConfig.objects.update_or_create(
                    name=cmdb_rt_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                    defaults={"table_id": cmdb_table_id},
                )
            vm_storage_ins, _ = VMStorageBindingConfig.objects.update_or_create(
                name=binding_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                # bkbase_result_table_name 必须与最终实际引用的 RT 保持一致：
                # 下发给 BKBase 的 payload 里 spec.data.name 是 vm_table_id_ins.name，
                # 本地 ORM 里这个字段也是 metadata/models/data_link/relation.py 用来按
                # name 回查 ResultTableConfig 的指针。复用场景下 RT 被 claim 成
                # legacy_rt 而 binding 被 claim 成 legacy_binding 时，如果继续写成
                # bkbase_vmrt_name（生成名），本地关系就会指向一张不存在的 RT。
                defaults={
                    "table_id": table_id,
                    "bkbase_result_table_name": vm_table_id_ins.name,
                    "vm_cluster_name": storage_cluster_name,
                },
            )
            sink_item = {
                "kind": DataLinkKind.VMSTORAGEBINDING.value,
                # sink 必须指向实际存在的 VMStorageBinding，因此这里联动 binding_name
                # 而非 bkbase_vmrt_name，以便在复用 legacy binding 时 databus 能正确引用。
                "name": binding_name,
                "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            }
            if settings.ENABLE_MULTI_TENANT_MODE:
                sink_item["tenant"] = self.bk_tenant_id

            sinks = [sink_item]

            data_bus_ins, _ = DataBusConfig.objects.update_or_create(
                name=databus_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "data_id_name": bkbase_data_name,
                    "bk_data_id": data_source.bk_data_id,
                    "sink_names": [f"{sink_item['kind']}:{sink_item['name']}"],
                },
            )
            data_bus_ins.apply_consumer_group(consumer_group)

        transform_format = self.DATABUS_TRANSFORMER_FORMAT.get(self.data_link_strategy)
        transform_options = None
        if exporter_cmdb_enabled and vm_table_id_ins_cmdb is not None:
            bkbase_cmdb_table_id = vm_table_id_ins_cmdb.bkbase_table_id or (
                f"{vm_table_id_ins_cmdb.datalink_biz_ids.data_biz_id}_{vm_table_id_ins_cmdb.name}"
            )
            transform_options = {
                "exporter_cmdb": True,
                "exporter_cmdb_rt": bkbase_cmdb_table_id,
            }

        configs = [vm_table_id_ins.compose_config()]
        if vm_table_id_ins_cmdb is not None:
            configs.append(vm_table_id_ins_cmdb.compose_config())
        configs.extend(
            [
                # 显式透传 RT 的 name，避免 compose_bk_plugin 场景下开启复用后
                # RT / Binding name 被独立 claim 成不同值时，binding payload 的
                # spec.data.name 仍然指向 "binding.name" 这个并不存在的 RT。
                vm_storage_ins.compose_config(whitelist=whitelist, rt_name=vm_table_id_ins.name),
                data_bus_ins.compose_config(
                    sinks=sinks,
                    transform_format=transform_format,
                    transform_options=transform_options,
                ),
            ]
        )
        return configs

    def _get_databus_monitor_label_table(self) -> "ResultTable | None":
        """仅在链路唯一关联一张结果表时返回对应的监控侧 ResultTable。"""

        from metadata.models import ResultTable

        table_ids = {table_id for table_id in self.table_ids if table_id}
        if len(table_ids) != 1:
            return None

        table_id = table_ids.pop()
        table = ResultTable.objects.filter(bk_tenant_id=self.bk_tenant_id, table_id=table_id).first()
        if table is None:
            logger.warning(
                "get_databus_monitor_label_table: result table not found, omit table label, "
                "data_link_name->[%s],bk_tenant_id->[%s],table_id->[%s]",
                self.data_link_name,
                self.bk_tenant_id,
                table_id,
            )
        return table

    @staticmethod
    def _inject_databus_monitor_labels(
        configs: list[dict[str, Any]],
        monitor_labels: dict[str, str],
    ) -> None:
        """替换 Databus 中由监控侧统一托管的 metadata labels。"""

        for config in configs:
            if config.get("kind") != DataLinkKind.DATABUS.value:
                continue

            metadata = config["metadata"]
            labels = metadata.setdefault("labels", {})
            metadata["labels"] = {
                key: value for key, value in labels.items() if not key.startswith(DATABUS_MONITOR_LABEL_PREFIX)
            }
            metadata["labels"].update(monitor_labels)

    def apply_data_link(self, *args, **kwargs):
        """
        组装配置并下发数据链路
        声明BkBaseResultTable -> 组装链路资源配置 -> 调用API申请
        """
        from metadata.models.bkdata.result_table import BkBaseResultTable

        consumer_group: str | None = kwargs.pop("consumer_group", None)
        force_cleanup_absent_components = kwargs.pop("cleanup_absent_components", False)
        storage_type = kwargs.pop("storage_type", None)
        compose_arguments = inspect.signature(self._get_compose_method()).bind_partial(*args, **kwargs).arguments
        data_source = compose_arguments.get("data_source")
        table_id = compose_arguments.get("table_id")

        graph_relation_option = None
        if self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES:
            from metadata.models.result_table import GraphRelationV4DataLinkOption, ResultTableOption

            option_record = ResultTableOption.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                table_id=table_id,
                name=ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
            ).first()
            if option_record is None:
                raise ValueError(
                    "apply_data_link: legacy graph relation entry is disabled, "
                    f"table_id({table_id}) requires "
                    f"{ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK} option"
                )
            graph_relation_option = GraphRelationV4DataLinkOption.from_option_value(option_record.get_value())

        if storage_type is None:
            storage_type = self.STORAGE_TYPE_MAP[self.data_link_strategy]
            if graph_relation_option is not None:
                storage_type = (
                    ClusterInfo.TYPE_VM if graph_relation_option.should_write_vm else ClusterInfo.TYPE_SURREALDB
                )

        try:
            # NOTE:新链路下，data_link_name和bkbase_data_name一致
            monitor_table_id: str | None = (
                table_id if self.data_link_strategy != self.BASEREPORT_TIME_SERIES_V1 else self.data_link_name
            )
            bkbase_rt_record, _ = BkBaseResultTable.objects.get_or_create(
                bk_tenant_id=self.bk_tenant_id,
                data_link_name=self.data_link_name,
                defaults={
                    "monitor_table_id": monitor_table_id,
                    "bkbase_data_name": self.data_link_name,
                    "storage_type": storage_type,
                    "status": DataLinkResourceStatus.INITIALIZING.value,
                },
            )
            should_update_bkbase_rt_storage_type = (
                self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES
                and bkbase_rt_record.storage_type != storage_type
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "apply_data_link: data_link_name->[%s] create BkBaseResultTable error->[%s]", self.data_link_name, e
            )
            raise e

        # 组件复用开关：strategy 级灰度或 RT option 单表开关任一命中，且代码侧已接入时，
        # 才会构造 existing_context 并交给 compose 分支；table_id 为空时不查 RT option。
        enable_reuse = is_reuse_enabled_for(
            self.data_link_strategy,
            table_id=table_id,
            bk_tenant_id=self.bk_tenant_id,
        )
        existing_context: ExistingComponentContext | None = (
            ExistingComponentContext.from_datalink(self)
            if enable_reuse
            or self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES
            or force_cleanup_absent_components
            else None
        )

        # 把 compose（含内部 update_or_create）和 leftover 校验放进同一个外层事务：
        #
        # compose_*_configs 内部各自有同一个 metadata DB alias 的 atomic 包住三类组件的
        # update_or_create，所以在没有外层事务时，这几条写入会在 compose 返回时就
        # 被提交。随后如果 _check_leftover_or_raise 发现有孤儿组件、抛
        # ComponentReuseError，本次新建/更新的 RT/Binding/DataBus 已经持久化到本地库，
        # 失败的 apply 会留下"compose 已落库但 apply 被拒"的脏状态；反复重试还会持续
        # 积累本地脏数据，与"发现多余组件就直接报错、避免继续制造不可控状态"的设计初衷相反。
        #
        # 解决方式：把两者都裹在最外层 atomic() 里，compose 内部的 atomic() 会降级为
        # savepoint，外层异常触发时连带一起回滚，保证 "apply 不通过 -> 本地无副作用"。
        try:
            with transaction.atomic(using=DATABASE_CONNECTION_NAME):
                configs: list[dict[str, Any]] = self.compose_configs(
                    *args,
                    existing_context=existing_context,
                    consumer_group=consumer_group,
                    **kwargs,
                )
                if existing_context is not None and not force_cleanup_absent_components:
                    # compose 已跑完，本次 apply 的所有既有组件认领都已完成；
                    # 此时 pool 中剩下的就是"未被 compose 消费的既有组件"，按策略决定是否放行。
                    # 一旦 strict 策略不通过会抛 ComponentReuseError，连带上面的 compose
                    # 写入一起回滚，避免失败的 apply 留下持久化副作用。
                    self._check_leftover_or_raise(existing_context)
        except ComponentReuseError as e:
            logger.error(
                "apply_data_link: data_link_name->[%s] leftover check failed, "
                "rollback compose-side DB writes in this attempt, error->[%s]",
                self.data_link_name,
                e,
            )
            raise
        except Exception as e:  # pylint: disable=broad-except
            logger.error("apply_data_link: data_link_name->[%s] compose config error->[%s]", self.data_link_name, e)
            raise e

        configs = self.merge_existing_component_configs(configs)
        if data_source is None and self.bk_data_id:
            from metadata.models.data_source import DataSource

            data_source = DataSource.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                bk_data_id=self.bk_data_id,
            ).first()
        if data_source is None:
            logger.warning(
                "apply_data_link: data_source missing, skip databus monitor labels, data_link_name->[%s]",
                self.data_link_name,
            )
        else:
            monitor_labels = compose_databus_monitor_labels(
                strategy=self.data_link_strategy,
                table=self._get_databus_monitor_label_table(),
                data_source=data_source,
            )
            self._inject_databus_monitor_labels(configs, monitor_labels)
        components_to_delete = self._get_absent_components_to_delete(
            configs,
            force_delete=force_cleanup_absent_components,
        )

        logger.info(
            "apply_data_link: data_link_name->[%s],strategy->[%s] try to use configs->[%s] to apply",
            self.data_link_name,
            self.data_link_strategy,
            configs,
        )
        try:
            response = self.apply_data_link_with_retry(configs)
        except RetryError as e:
            logger.error("apply_data_link: data_link_name->[%s] retry error->[%s]", self.data_link_name, e.__cause__)
            # 抛出底层错误原因，而非直接RetryError
            raise e.__cause__ if e.__cause__ else e
        except Exception as e:  # pylint: disable=broad-except
            logger.error("apply_data_link: data_link_name->[%s] apply error->[%s]", self.data_link_name, e)
            raise e

        logger.info(
            "apply_data_link: data_link_name->[%s],strategy->[%s] response->[%s]",
            self.data_link_name,
            self.data_link_strategy,
            response,
        )
        self._cleanup_absent_components(components_to_delete)
        if should_update_bkbase_rt_storage_type:
            bkbase_rt_record.storage_type = storage_type
            bkbase_rt_record.save(update_fields=["storage_type"])

    @classmethod
    def _fill_missing_dict(cls, target: dict[str, Any], existing: dict[str, Any]) -> None:
        """把旧配置中存在、当前配置中缺失的字段补到 target，当前配置已有值保持优先。

        target 是本次 compose 配置的工作副本，existing 是 BKBase 查询回来的旧配置工作副本。
        这里不做覆盖，只做补缺：
        - target 已有普通字段时保持本次 compose 结果；
        - target 和 existing 对应值都是 dict 时继续递归补缺；
        - target 缺少字段时直接搬入 existing 中的值。
        """
        for key, existing_value in existing.items():
            if key not in target:
                target[key] = existing_value
            # 暂时不支持嵌套覆盖，除非后续有需求
            # elif isinstance(existing_value, dict) and isinstance(target[key], dict):
            #     cls._fill_missing_dict(target[key], existing_value)

    @classmethod
    def merge_component_config(cls, existing_config: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        """把 BKBase 侧已有配置与本次配置合并，过滤掉 status 等运行态字段。

        单个组件的合并策略：
        1. 以本次 compose 出来的 config 作为最终 payload 主体，保证代码侧声明的配置优先；
        2. 只从 BKBase 旧配置里读取 metadata.labels、metadata.annotations 和 spec；
        3. 旧配置只用于补齐本次 config 缺失的字段，不覆盖本次 config 已声明的字段；
        4. metadata.name、namespace、tenant、resourceVersion、status 等非配置字段不从旧配置回填；
        5. metadata/spec 属于组件标准结构，缺失时直接报错，避免吞掉异常后生成不完整 payload。
        """
        existing_config = deepcopy(existing_config)
        merged_config = config
        cls.check_component_immutable_fields(existing_config, merged_config)

        existing_metadata = existing_config["metadata"]
        merged_metadata = merged_config["metadata"]
        # 合并metadata，仅处理labels和annotations
        for metadata_key in ("labels", "annotations"):
            if metadata_key not in existing_metadata:
                continue
            if metadata_key not in merged_metadata:
                merged_metadata[metadata_key] = existing_metadata[metadata_key]
                continue
            cls._fill_missing_dict(merged_metadata[metadata_key], existing_metadata[metadata_key])

        # 合并spec
        cls._fill_missing_dict(merged_config["spec"], existing_config["spec"])

        return merged_config

    @classmethod
    def _get_component_field_value(cls, config: dict[str, Any], field_path: tuple[str, ...]) -> Any:
        current: Any = config
        for key in field_path:
            if not isinstance(current, dict) or key not in current:
                return _MISSING_CONFIG_FIELD
            current = current[key]
        return current

    @classmethod
    def check_component_immutable_fields(cls, existing_config: dict[str, Any], config: dict[str, Any]) -> None:
        """检查并恢复指定组件中配置后不允许修改的字段。

        只有 BKBase 已有配置与本次配置都包含目标字段时才比较；缺失字段继续按原有
        merge 补缺逻辑处理，避免影响首次下发或历史组件字段不完整的场景。字段值
        冲突时保留 BKBase 已有值并记录告警，不阻断组件其他配置的变更。
        """
        kind = config.get("kind")
        if not kind:
            return

        for immutable_field in DataLinkImmutableField.fields_for_kind(kind):
            existing_value = cls._get_component_field_value(existing_config, immutable_field.field_path)
            current_value = cls._get_component_field_value(config, immutable_field.field_path)
            if existing_value is _MISSING_CONFIG_FIELD or current_value is _MISSING_CONFIG_FIELD:
                continue
            if existing_value == current_value:
                continue

            field_parent = config
            for key in immutable_field.field_path[:-1]:
                field_parent = field_parent[key]
            field_parent[immutable_field.field_path[-1]] = existing_value
            logger.warning(
                "merge_component_config: immutable component field changed,keep existing value,"
                "kind->[%s],field->[%s],existing_value->[%s],current_value->[%s]",
                kind,
                immutable_field.display_path,
                existing_value,
                current_value,
            )

    def get_existing_component_config(
        self,
        kind: str,
        name: str,
        namespace: str,
    ) -> dict[str, Any] | None:
        """直接查询 BKBase 组件配置；只把明确不存在视为可忽略。"""
        bkbase_kind = DataLinkKind.get_choice_value(kind)
        if not bkbase_kind:
            logger.info("get_existing_component_config: kind is not valid,kind->[%s]", kind)
            return None

        try:
            return api.bkdata.get_data_link(
                bk_tenant_id=self.bk_tenant_id,
                kind=bkbase_kind,
                namespace=namespace,
                name=name,
            )
        except BKAPIError as error:
            # 这里必须直接区分 not found 与其它 API 异常：资源不存在可以继续 apply，
            # 权限、网关或服务异常则要抛出，避免误判为“无旧配置”后覆盖 BKBase 侧真实状态。
            error_data = error.data if isinstance(error.data, dict) else {}
            is_bkbase_v4_not_found = str(error_data.get("code")) == "1558025"
            is_legacy_not_found = f"resource {name} of kind {kind} not found".lower() in error.message.lower()
            if is_bkbase_v4_not_found or is_legacy_not_found:
                return None
            logger.error(
                "get_existing_component_config: bkbase api error,kind->[%s],name->[%s],namespace->[%s],error->[%s]",
                kind,
                name,
                namespace,
                error,
            )
            raise

    def merge_existing_component_configs(self, configs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """下发前查询 BKBase 侧已有组件配置，并把配置字段合并进本次 payload。

        合并策略：
        - 组件明确 not found 时视为无旧配置，其它 API 异常继续抛出；
        - 仅合并 metadata.labels、metadata.annotations 和 spec；
        - 本次 compose 配置优先，旧配置只补当前缺失字段，status 等运行态字段不回填。
        """

        merged_configs: list[dict[str, Any]] = []
        for config in configs:
            metadata = config["metadata"]
            kind = config["kind"]
            name = metadata["name"]
            namespace = metadata["namespace"]

            # 校验配置是否合法
            if not kind or not name or not namespace:
                raise ValueError(
                    f"merge_existing_component_configs: kind->[{kind}],name->[{name}],namespace->[{namespace}] "
                    "is invalid"
                )

            # 查询已有配置
            existing_config = self.get_existing_component_config(kind, name, namespace)
            if not isinstance(existing_config, dict):
                merged_configs.append(config)
                continue

            # 合并配置
            merged_configs.append(self.merge_component_config(existing_config, config))
        return merged_configs

    def _leftover_policy(
        self,
        kind: type["DataLinkResourceConfigBase"],
    ) -> Literal["strict", "keep", "delete"]:
        """按 (strategy, kind) 查找 leftover 策略，未声明时默认 ``strict``。"""
        return self.REUSE_LEFTOVER_POLICY.get((self.data_link_strategy, kind), "strict")

    def _check_leftover_or_raise(self, ctx: "ExistingComponentContext") -> None:
        """基于 leftover 策略判定是否抛出 :class:`ComponentReuseError`。

        只把 ``strict`` 策略对应 kind 的残留视作违规；``keep`` 和 ``delete`` 都允许
        compose 继续，后者会在 BKBase apply 成功后由期望状态收敛逻辑删除。
        """
        leftover_map = ctx.leftover()
        if not leftover_map:
            return

        violations = {kind: items for kind, items in leftover_map.items() if self._leftover_policy(kind) == "strict"}
        if not violations:
            logger.info(
                "apply_data_link: data_link_name->[%s] strategy->[%s] leftover ignored by policy: %s",
                self.data_link_name,
                self.data_link_strategy,
                {kind.__name__: [c.name for c in items] for kind, items in leftover_map.items()},
            )
            return

        raise ComponentReuseError(
            data_link_name=self.data_link_name,
            strategy=self.data_link_strategy,
            violations=violations,
        )

    @staticmethod
    def _component_identity_from_config(
        config: dict[str, Any], default_tenant: str
    ) -> tuple[str, str, str, str] | None:
        metadata = config.get("metadata")
        kind = config.get("kind")
        if not kind or not isinstance(metadata, dict):
            return None
        name = metadata.get("name")
        namespace = metadata.get("namespace")
        if not name or not namespace:
            return None
        return kind, metadata.get("tenant") or default_tenant, namespace, name

    def _get_absent_components_to_delete(
        self,
        configs: list[dict[str, Any]],
        *,
        force_delete: bool = False,
    ) -> list["DataLinkResourceConfigBase"]:
        """找出当前 DataLink 中未出现在 compose 期望配置里的受管组件。"""
        desired_identities = {
            identity
            for config in configs
            if (identity := self._component_identity_from_config(config, self.bk_tenant_id)) is not None
        }
        components_to_delete: list[DataLinkResourceConfigBase] = []
        for component_class in ALL_DATA_LINK_COMPONENT_KINDS:
            policy = self._leftover_policy(component_class)
            if not force_delete and policy != "delete":
                continue
            if policy == "keep":
                continue
            components = component_class.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                namespace=self.namespace,
                data_link_name=self.data_link_name,
            )
            for component in components:
                identity = (
                    component.kind,
                    component.bk_tenant_id,
                    component.namespace,
                    component.name,
                )
                if identity not in desired_identities:
                    components_to_delete.append(component)

        delete_priority = {
            DataLinkKind.DATABUS.value: 0,
            DataLinkKind.CHANNELBINDING.value: 1,
            DataLinkKind.VMSTORAGEBINDING.value: 1,
            DataLinkKind.SURREALDBBINDING.value: 1,
            DataLinkKind.ESSTORAGEBINDING.value: 1,
            DataLinkKind.DORISBINDING.value: 1,
            DataLinkKind.RESULTTABLE.value: 2,
        }
        return sorted(components_to_delete, key=lambda component: delete_priority.get(component.kind, 1))

    @staticmethod
    def _is_remote_component_not_found(error: Exception) -> bool:
        if isinstance(error, BKAPIError):
            code = str(error.data.get("code", "")).lower()
            message = str(error.data.get("message", "")).lower()
            return code in {"404", "not_found", "resource_not_found"} or "not found" in message
        return False

    def _cleanup_absent_components(self, components: list["DataLinkResourceConfigBase"]) -> None:
        """BKBase apply 成功后尽力清理不再属于期望状态的组件。"""
        for component in components:
            try:
                component.delete_config()
            except Exception as error:  # pylint: disable=broad-except
                if self._is_remote_component_not_found(error):
                    logger.info(
                        "cleanup_absent_components: remote component already absent, delete local record, "
                        "data_link_name->[%s],kind->[%s],name->[%s]",
                        self.data_link_name,
                        component.kind,
                        component.name,
                    )
                    component.delete()
                    continue
                logger.warning(
                    "cleanup_absent_components: delete failed, keep local record for retry, "
                    "data_link_name->[%s],kind->[%s],name->[%s],error->[%s]",
                    self.data_link_name,
                    component.kind,
                    component.name,
                    error,
                )

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=10))
    def apply_data_link_with_retry(self, configs: list[dict[str, Any]]):
        """
        根据指定配置，申请数据链路，具备重试机制，最多重试四次，最高等待10秒
        @param configs: 链路资源配置
        """
        try:
            return api.bkdata.apply_data_link(bk_tenant_id=self.bk_tenant_id, config=configs)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "apply_data_link: data_link_name->[%s] apply error->[%s],configs->[%s]", self.data_link_name, e, configs
            )
            raise e

    def sync_metadata(
        self,
        table_id,
        storage_cluster_name: str | None = None,
        storage_type: str | None = None,
        storage_cluster_id: int | None = None,
    ):
        """
        从本次 apply 落库的 ResultTableConfig / DataBusConfig 读实名回填 BkBaseResultTable。

        集群定位支持两种方式（二选一，``storage_cluster_id`` 优先）：
        - 方式一：传 ``storage_cluster_id``，直接查 ``ClusterInfo`` 反查 ``cluster_type``。
        - 方式二：传 ``storage_cluster_name``（可选 ``storage_type``，默认 ``ClusterInfo.TYPE_VM``），
          按 ``(bk_tenant_id, cluster_type, cluster_name)`` 唯一键命中 ``ClusterInfo``。

        不变式：
        - ``bkbase_rt_name == ResultTableConfig.name``
        - ``bkbase_table_id == f"{rt.datalink_biz_ids.data_biz_id}_{rt.name}"``
        - 联邦子集链路不声明独立 ResultTable，兼容使用 ``ConditionalSinkConfig.name`` 回填上述两个字段
        - ``bkbase_data_name == DataBusConfig.data_id_name``
        - ``storage_type`` / ``storage_cluster_id`` 与 ``ClusterInfo`` 实际记录保持一致。
        """
        from metadata.models import ClusterInfo
        from metadata.models.bkdata.result_table import BkBaseResultTable

        try:
            if storage_cluster_id is not None:
                cluster = ClusterInfo.objects.get(bk_tenant_id=self.bk_tenant_id, cluster_id=storage_cluster_id)
            else:
                # 兼容旧调用：未显式传 storage_type 时按 VM 处理，避免改变 VM/Fed 行为。
                resolved_storage_type = storage_type or ClusterInfo.TYPE_VM
                cluster = ClusterInfo.objects.get(
                    bk_tenant_id=self.bk_tenant_id,
                    cluster_name=storage_cluster_name,
                    cluster_type=resolved_storage_type,
                )
            resolved_storage_cluster_id = cluster.cluster_id
            resolved_storage_type = cluster.cluster_type
        except ClusterInfo.DoesNotExist:
            logger.error(
                "sync_metadata: storage cluster not exist! cluster_id->[%s] cluster_name->[%s] storage_type->[%s]",
                storage_cluster_id,
                storage_cluster_name,
                storage_type,
            )
            return

        rt_queryset = ResultTableConfig.objects.filter(
            bk_tenant_id=self.bk_tenant_id,
            namespace=self.namespace,
            data_link_name=self.data_link_name,
            table_id=table_id,
        )
        if self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES:
            rt_queryset = rt_queryset.filter(
                data_type="graph" if resolved_storage_type == ClusterInfo.TYPE_SURREALDB else "metric"
            )
        rt_queryset = rt_queryset.order_by("-last_modify_time", "-id")
        rt_count = rt_queryset.count()
        rt = rt_queryset.first()
        if rt_count == 0:
            logger.warning(
                "sync_metadata: data_link_name->[%s] table_id->[%s] ResultTableConfig not found, "
                "will record partial BkBaseResultTable",
                self.data_link_name,
                table_id,
            )
        elif rt_count > 1:
            logger.error(
                "sync_metadata: data_link_name->[%s] table_id->[%s] got multiple ResultTableConfig, "
                "selected name->[%s] to record BkBaseResultTable",
                self.data_link_name,
                table_id,
                rt.name if rt else "",
            )

        databus_queryset = DataBusConfig.objects.filter(
            bk_tenant_id=self.bk_tenant_id,
            namespace=self.namespace,
            data_link_name=self.data_link_name,
        )
        if self.data_link_strategy in {
            self.CUSTOM_FORMAT_VM,
            self.CUSTOM_FORMAT_ES,
            self.CUSTOM_FORMAT_DORIS,
        }:
            databus_queryset = databus_queryset.filter(role="clean")
        if self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES:
            sink_kind = (
                DataLinkKind.SURREALDBBINDING.value
                if resolved_storage_type == ClusterInfo.TYPE_SURREALDB
                else DataLinkKind.VMSTORAGEBINDING.value
            )
            databus_queryset = databus_queryset.filter(sink_names__icontains=f"{sink_kind}:")
        databus_queryset = databus_queryset.order_by("-last_modify_time", "-id")
        databus_count = databus_queryset.count()
        databus = databus_queryset.first()
        if databus_count == 0:
            logger.warning(
                "sync_metadata: data_link_name->[%s] DataBusConfig not found, will record partial BkBaseResultTable",
                self.data_link_name,
            )
        elif databus_count > 1:
            logger.error(
                "sync_metadata: data_link_name->[%s] got multiple DataBusConfig, "
                "selected name->[%s] to record BkBaseResultTable",
                self.data_link_name,
                databus.name if databus else "",
            )

        defaults = {
            "monitor_table_id": table_id,
            "storage_type": resolved_storage_type,
            "storage_cluster_id": resolved_storage_cluster_id,
            "status": DataLinkResourceStatus.OK.value,
        }
        if rt:
            bkbase_rt_name = rt.name
            defaults.update(
                {
                    "bkbase_rt_name": bkbase_rt_name,
                    # 优先使用ResultTableConfig记录的bkbase_table_id，因为重建链路的所属业务并不稳定
                    "bkbase_table_id": rt.bkbase_table_id
                    if rt.bkbase_table_id
                    else f"{rt.datalink_biz_ids.data_biz_id}_{bkbase_rt_name}",
                }
            )
        elif self.data_link_strategy == self.BCS_FEDERAL_SUBSET_TIME_SERIES:
            conditional_sink = (
                ConditionalSinkConfig.objects.filter(
                    bk_tenant_id=self.bk_tenant_id,
                    namespace=self.namespace,
                    data_link_name=self.data_link_name,
                )
                .order_by("-last_modify_time", "-id")
                .first()
            )
            if conditional_sink:
                bkbase_rt_name = conditional_sink.name
                defaults.update(
                    {
                        "bkbase_rt_name": bkbase_rt_name,
                        "bkbase_table_id": f"{conditional_sink.datalink_biz_ids.data_biz_id}_{bkbase_rt_name}",
                    }
                )
        if databus:
            defaults["bkbase_data_name"] = databus.data_id_name

        try:
            with transaction.atomic(using=DATABASE_CONNECTION_NAME):
                BkBaseResultTable.objects.update_or_create(
                    bk_tenant_id=self.bk_tenant_id,
                    data_link_name=self.data_link_name,
                    defaults=defaults,
                )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("sync_metadata: data_link_name->[%s],sync_metadata failed,error->[%s]", self.data_link_name, e)

    def sync_basereport_metadata(self, bk_biz_id, storage_cluster_name, source, datasource, extra_source=None):
        """
        同步元数据
        同步全套链路信息 AccessVMRecord,
        """
        from metadata.models import AccessVMRecord, ClusterInfo

        try:
            storage_cluster_id = ClusterInfo.objects.get(
                bk_tenant_id=self.bk_tenant_id, cluster_name=storage_cluster_name
            ).cluster_id
        except ClusterInfo.DoesNotExist:
            logger.error("sync_metadata: storage_cluster_name->[%s] not exist!", storage_cluster_name)
            return

        try:
            with transaction.atomic(using=DATABASE_CONNECTION_NAME):
                # 创建11个ResultTableConfig和VMStorageBindingConfig
                for source_item in [source, extra_source]:
                    if not source_item:
                        continue
                    bkbase_vmrt_prefix = f"base_{bk_biz_id}_{source_item}"
                    for usage in BASEREPORT_USAGES:
                        vm_result_table_id = f"{bk_biz_id}_{bkbase_vmrt_prefix}_{usage}"
                        result_table_id = f"{self.bk_tenant_id}_{bk_biz_id}_{source_item}.{usage}"
                        AccessVMRecord.objects.update_or_create(
                            bk_tenant_id=self.bk_tenant_id,
                            result_table_id=result_table_id,
                            bk_base_data_id=datasource.bk_data_id,
                            bk_base_data_name=datasource.data_name,
                            defaults={
                                "vm_result_table_id": vm_result_table_id,
                                "vm_cluster_id": storage_cluster_id,
                                "storage_cluster_id": storage_cluster_id,
                            },
                        )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("sync_basereport_metadata: failed to create access vm record! error message->%s", e)
