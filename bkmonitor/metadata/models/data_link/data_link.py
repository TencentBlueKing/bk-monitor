"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
from copy import deepcopy
from functools import partial
from typing import TYPE_CHECKING, Any, Literal

from django.conf import settings
from django.db import models, transaction
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from core.drf_resource import api
from core.errors.api import BKAPIError
from metadata.config import DATABASE_CONNECTION_NAME
from metadata.models.data_link import utils
from metadata.models.data_link.component_reuse import (
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
    ConditionalSinkConfig,
    DataBusConfig,
    DorisStorageBindingConfig,
    ESStorageBindingConfig,
    ExpandableGroup,
    GraphDataBusConfig,
    GraphRelationBindingConfig,
    GraphRelationConfig,
    ResultTableConfig,
    SurrealDBBindingConfig,
    VMStorageBindingConfig,
)
from metadata.models.data_link.utils import generate_result_table_field_list, get_bkbase_raw_data_id_name
from metadata.models.entity_relation import (
    EntityMeta,
    NAMESPACE_ALL,
    RelationDefinition,
    ResourceDefinition,
)
from metadata.models.storage import ClusterInfo, DorisStorage, ESStorage, SurrealDBStorage
from metadata.models.vm.record import AccessVMRecord

if TYPE_CHECKING:
    from metadata.models import DataSource
    from metadata.models.data_link.data_link_configs import DataLinkResourceConfigBase

logger = logging.getLogger("metadata")

_MISSING_CONFIG_FIELD = object()
SURREALDB_RT_SUFFIX = "_graph"


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
            GraphRelationConfig,
            GraphRelationBindingConfig,
        ],
        BASE_EVENT_V1: [ResultTableConfig, ESStorageBindingConfig, DataBusConfig],
        SYSTEM_PROC_PERF: [ResultTableConfig, VMStorageBindingConfig, BasereportSinkConfig, DataBusConfig],
        SYSTEM_PROC_PORT: [ResultTableConfig, VMStorageBindingConfig, BasereportSinkConfig, DataBusConfig],
        BK_LOG: [ResultTableConfig, ESStorageBindingConfig, DorisStorageBindingConfig, DataBusConfig],
        BK_STANDARD_V2_EVENT: [ResultTableConfig, ESStorageBindingConfig, DataBusConfig],
    }

    # 删除链路时使用的入口组件。
    # 图关系链路的实际子资源由 GraphRelationBindingConfig.delete_config 按写入模式清理。
    STRATEGY_DELETE_COMPONENTS: dict[str, list[type["DataLinkResourceConfigBase"]]] = {
        GRAPH_RELATION_TIME_SERIES: [GraphRelationBindingConfig],
    }

    STORAGE_TYPE_MAP = {
        BK_STANDARD_V2_TIME_SERIES: ClusterInfo.TYPE_VM,
        BK_EXPORTER_TIME_SERIES: ClusterInfo.TYPE_VM,
        BK_STANDARD_TIME_SERIES: ClusterInfo.TYPE_VM,
        BCS_FEDERAL_PROXY_TIME_SERIES: ClusterInfo.TYPE_VM,
        BCS_FEDERAL_SUBSET_TIME_SERIES: ClusterInfo.TYPE_VM,
        BASEREPORT_TIME_SERIES_V1: ClusterInfo.TYPE_VM,
        GRAPH_RELATION_TIME_SERIES: ClusterInfo.TYPE_SURREALDB,
        BASE_EVENT_V1: ClusterInfo.TYPE_ES,
        SYSTEM_PROC_PERF: ClusterInfo.TYPE_VM,
        SYSTEM_PROC_PORT: ClusterInfo.TYPE_VM,
        BK_LOG: ClusterInfo.TYPE_ES,
        BK_STANDARD_V2_EVENT: ClusterInfo.TYPE_ES,
    }

    DATABUS_TRANSFORMER_FORMAT = {
        BK_EXPORTER_TIME_SERIES: BK_EXPORTER_TRANSFORMER_FORMAT,
        BK_STANDARD_TIME_SERIES: BK_STANDARD_TRANSFORMER_FORMAT,
    }

    # DataLink 组件复用 - leftover 策略表
    # key   : (data_link_strategy, component kind)
    # value : "strict" 表示 compose 完成后该 kind 的未消费组件视为脏数据，直接报错；
    #         "keep"   表示允许既有组件残留（既不报错也不删除，也不参与本次下发）。
    # 未声明的 (strategy, kind) 默认按 "strict" 处理。
    REUSE_LEFTOVER_POLICY: dict[tuple[str, type["DataLinkResourceConfigBase"]], Literal["strict", "keep"]] = {}

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
        graph_orphan_surrealdb_table_ids: list[str] = []
        if (
            self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES
            and component_classes == [GraphRelationBindingConfig]
            and not GraphRelationBindingConfig.objects.filter(data_link_name=self.data_link_name).exists()
        ):
            graph_orphan_surrealdb_table_ids = list(
                SurrealDBBindingConfig.objects.filter(data_link_name=self.data_link_name).values_list(
                    "table_id", flat=True
                )
            )
            component_classes = self.get_related_component_classes(
                write_mode=GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB
            )
        for component_class in reversed(component_classes):
            components = component_class.objects.filter(data_link_name=self.data_link_name)
            for component in components:
                logger.info(
                    "delete_data_link: delete data_link_name->[%s] kind->[%s] component->[%s]",
                    self.data_link_name,
                    component.kind,
                    component.name,
                )
                component.delete_config()
        if graph_orphan_surrealdb_table_ids:
            self._delete_graph_surrealdb_storage_records(graph_orphan_surrealdb_table_ids)
        self.delete()

    def _delete_graph_surrealdb_storage_records(self, table_ids: list[str]) -> None:
        """Clean local SurrealDB storage metadata when graph binding anchor is already missing."""
        if not table_ids:
            return
        from metadata.models.storage import ClusterInfo, StorageClusterRecord

        storages = SurrealDBStorage.objects.filter(
            table_id__in=table_ids,
            bk_tenant_id=self.bk_tenant_id,
        )
        storage_cluster_ids = set(storages.values_list("storage_cluster_id", flat=True))
        storage_cluster_ids.update(
            ClusterInfo.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                cluster_type=ClusterInfo.TYPE_SURREALDB,
            ).values_list("cluster_id", flat=True)
        )
        storages.delete()
        if storage_cluster_ids:
            StorageClusterRecord.objects.filter(
                table_id__in=table_ids,
                bk_tenant_id=self.bk_tenant_id,
                cluster_id__in=storage_cluster_ids,
            ).delete()

    def get_related_component_classes(
        self, write_mode: str | None = None
    ) -> list[type["DataLinkResourceConfigBase"]]:
        if write_mode is None and self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES:
            graph_binding = self._get_graph_relation_binding()
            if graph_binding:
                write_mode = graph_binding.write_mode

        component_classes: list[type["DataLinkResourceConfigBase"]] = []
        for cls in self.STRATEGY_RELATED_COMPONENTS[self.data_link_strategy]:
            if isinstance(cls, type) and issubclass(cls, ExpandableGroup):
                component_classes.extend(cls.expand(write_mode))
            else:
                component_classes.append(cls)
        return list(dict.fromkeys(component_classes))

    def get_delete_component_classes(self) -> list[type["DataLinkResourceConfigBase"]]:
        return self.STRATEGY_DELETE_COMPONENTS.get(self.data_link_strategy) or self.get_related_component_classes()

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

        # 类似switch的形式，选择对应的组装方式
        switcher = {
            DataLink.BK_STANDARD_V2_TIME_SERIES: self.compose_standard_time_series_configs,
            DataLink.BK_STANDARD_TIME_SERIES: self.compose_bk_plugin_time_series_config,
            DataLink.BK_EXPORTER_TIME_SERIES: self.compose_bk_plugin_time_series_config,
            DataLink.BCS_FEDERAL_PROXY_TIME_SERIES: self.compose_bcs_federal_proxy_time_series_configs,
            DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES: self.compose_bcs_federal_subset_time_series_configs,
            DataLink.BASEREPORT_TIME_SERIES_V1: self.compose_basereport_time_series_configs,
            DataLink.GRAPH_RELATION_TIME_SERIES: self.compose_graph_relation_time_series_configs,
            DataLink.BASE_EVENT_V1: self.compose_base_event_configs,
            DataLink.SYSTEM_PROC_PERF: partial(
                self.compose_system_proc_configs, data_link_strategy=DataLink.SYSTEM_PROC_PERF
            ),
            DataLink.SYSTEM_PROC_PORT: partial(
                self.compose_system_proc_configs, data_link_strategy=DataLink.SYSTEM_PROC_PORT
            ),
            DataLink.BK_LOG: self.compose_log_configs,
            DataLink.BK_STANDARD_V2_EVENT: self.compose_custom_event_configs,
        }
        method = switcher[self.data_link_strategy]
        kwargs["consumer_group"] = consumer_group
        if existing_context is not None and is_reuse_supported_for(self.data_link_strategy):
            return method(*args, existing_context=existing_context, **kwargs)
        return method(*args, **kwargs)

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

        bkbase_data_name = utils.compose_bkdata_data_id_name(data_source.data_name)
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
            databus_data_id_name = existing_databus.data_id_name if existing_databus is not None else bkbase_data_name

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
                data_id_name=databus_data_id_name,
                defaults={
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

    def _compose_graph_relation_surrealdb_configs(
        self,
        graph_binding_ins: GraphRelationBindingConfig,
        bk_biz_id: int,
        data_source: "DataSource",
        table_id: str,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        if not graph_binding_ins.surrealdb_cluster_name:
            raise ValueError("compose_graph_relation_surrealdb_configs: surrealdb cluster name is empty")
        surrealdb_rt_name = graph_binding_ins.graph_result_table_name or self.compose_surrealdb_table_name(table_id)
        surrealdb_binding_name = graph_binding_ins.surrealdb_binding_component_name
        graph_databus_name = graph_binding_ins.graph_databus_component_name
        surreal_sinks = [
            {
                "kind": DataLinkKind.SURREALDBBINDING.value,
                "name": surrealdb_binding_name,
                "namespace": self.namespace,
            }
        ]
        if settings.ENABLE_MULTI_TENANT_MODE:
            surreal_sinks[0]["tenant"] = self.bk_tenant_id

        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            rt_surreal_ins, _ = ResultTableConfig.objects.update_or_create(
                name=surrealdb_rt_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={"table_id": table_id, "data_type": "graph"},
            )
            SurrealDBStorage.create_table(
                table_id=table_id,
                is_sync_db=False,
                bk_tenant_id=self.bk_tenant_id,
                table_type=graph_binding_ins.table_type,
                vertices=graph_binding_ins.vertices,
                relations=graph_binding_ins.relations,
                storage_cluster_id=ClusterInfo.objects.get(
                    bk_tenant_id=self.bk_tenant_id,
                    cluster_name=graph_binding_ins.surrealdb_cluster_name,
                    cluster_type=ClusterInfo.TYPE_SURREALDB,
                ).cluster_id,
            )
            surrealdb_binding_ins, _ = SurrealDBBindingConfig.objects.update_or_create(
                name=surrealdb_binding_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "surrealdb_cluster_name": graph_binding_ins.surrealdb_cluster_name,
                    "table_id": table_id,
                    "bkbase_result_table_name": surrealdb_rt_name,
                    "table_type": graph_binding_ins.table_type,
                    "vertices": graph_binding_ins.vertices,
                    "relations": graph_binding_ins.relations,
                },
            )
            graph_databus_ins, _ = GraphDataBusConfig.objects.update_or_create(
                name=graph_databus_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "data_id_name": utils.compose_bkdata_data_id_name(data_source.data_name),
                    "bk_data_id": data_source.bk_data_id,
                    "sink_names": [f"{DataLinkKind.SURREALDBBINDING.value}:{surrealdb_binding_name}"],
                    "data_link_strategy": self.data_link_strategy,
                },
            )
            graph_databus_ins.apply_consumer_group(consumer_group)

        return [
            rt_surreal_ins.compose_config(),
            surrealdb_binding_ins.compose_config(),
            graph_databus_ins.compose_config(surreal_sinks),
        ]

    def compose_graph_relation_time_series_configs(
        self,
        bk_biz_id: int,
        data_source: "DataSource",
        table_id: str,
        storage_cluster_name: str = "",
        write_mode: str | None = None,
        consumer_group: str | None = None,
        persist_write_mode: bool = True,
        surrealdb_auto_restore: bool = False,
    ) -> list[dict[str, Any]]:
        """
        生成图关系时序链路配置。

        GraphRelationBindingConfig 负责声明 relation 数据写入目标：
        - vm: 仅下发 VM ResultTable/VmStorageBinding/Databus
        - surrealdb: 仅下发 SurrealDB ResultTable/SurrealDBBinding/GraphDatabus
        - vm_and_surrealdb: 两边都下发
        """
        logger.info(
            "compose_graph_relation_time_series_configs: data_link_name->[%s],bk_data_id->[%s],table_id->[%s],"
            "storage_cluster_name->[%s],write_mode->[%s]",
            self.data_link_name,
            data_source.bk_data_id,
            table_id,
            storage_cluster_name,
            write_mode,
        )

        bkbase_data_name = utils.compose_bkdata_data_id_name(data_source.data_name)
        bkbase_vmrt_name = utils.compose_bkdata_table_id(table_id)
        surrealdb_rt_name = self.compose_surrealdb_table_name(table_id)

        existed_graph_binding = self._get_graph_relation_binding()
        effective_write_mode = (
            GraphRelationBindingConfig.normalize_write_mode(write_mode)
            if write_mode is not None
            else (
                existed_graph_binding.write_mode
                if existed_graph_binding
                else GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB
            )
        )
        should_write_surrealdb = effective_write_mode in (
            GraphRelationBindingConfig.WRITE_MODE_SURREALDB,
            GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
        )

        surrealdb_cluster_name = existed_graph_binding.surrealdb_cluster_name if existed_graph_binding else ""
        if should_write_surrealdb:
            surrealdb_cluster_queryset = ClusterInfo.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                cluster_type=ClusterInfo.TYPE_SURREALDB,
            )
            surrealdb_cluster = (
                surrealdb_cluster_queryset.filter(cluster_name=surrealdb_cluster_name).first()
                if surrealdb_cluster_name
                else (
                    surrealdb_cluster_queryset.filter(is_default_cluster=True).first()
                    or surrealdb_cluster_queryset.order_by("cluster_id").first()
                )
            )
            if not surrealdb_cluster:
                raise ValueError("compose_graph_relation_time_series_configs: not found surrealdb cluster")
            surrealdb_cluster_name = surrealdb_cluster.cluster_name

        queried_vertices, queried_relations = (
            EntityMeta.auto_query_graph_definitions(bk_biz_id=bk_biz_id) if should_write_surrealdb else ([], [])
        )
        if should_write_surrealdb and (not queried_vertices or not queried_relations):
            raise ValueError(
                "compose_graph_relation_time_series_configs: graph definitions are empty, "
                "SurrealDB write requires non-empty vertices and relations"
            )
        graph_vertices = (
            queried_vertices
            if should_write_surrealdb
            else (existed_graph_binding.vertices if existed_graph_binding else [])
        )
        graph_relations = (
            queried_relations
            if should_write_surrealdb
            else (existed_graph_binding.relations if existed_graph_binding else [])
        )
        vm_cluster_name = storage_cluster_name or (existed_graph_binding.vm_cluster_name if existed_graph_binding else "")
        table_type = existed_graph_binding.table_type if existed_graph_binding else "temporary"
        bkbase_result_table_name = (
            existed_graph_binding.bkbase_result_table_name if existed_graph_binding else bkbase_vmrt_name
        ) or bkbase_vmrt_name
        graph_result_table_name = (
            existed_graph_binding.graph_result_table_name if existed_graph_binding else surrealdb_rt_name
        ) or surrealdb_rt_name
        vm_storage_binding_name = (
            existed_graph_binding.vm_binding_component_name if existed_graph_binding else bkbase_result_table_name
        )
        vm_databus_name = (
            existed_graph_binding.vm_databus_component_name if existed_graph_binding else bkbase_result_table_name
        )
        surrealdb_binding_name = (
            existed_graph_binding.surrealdb_binding_component_name if existed_graph_binding else graph_result_table_name
        )
        graph_databus_name = (
            existed_graph_binding.graph_databus_component_name if existed_graph_binding else graph_result_table_name
        )
        graph_binding_defaults = {
            "table_id": table_id,
            "vm_cluster_name": vm_cluster_name,
            "surrealdb_cluster_name": surrealdb_cluster_name,
            "bkbase_result_table_name": bkbase_result_table_name,
            "graph_result_table_name": graph_result_table_name,
            "vm_storage_binding_name": vm_storage_binding_name,
            "vm_databus_name": vm_databus_name,
            "surrealdb_binding_name": surrealdb_binding_name,
            "graph_databus_name": graph_databus_name,
            "table_type": table_type,
            "vertices": graph_vertices,
            "relations": graph_relations,
            "surrealdb_auto_restore": (
                bool(surrealdb_auto_restore)
                and effective_write_mode == GraphRelationBindingConfig.WRITE_MODE_VM
                and persist_write_mode
            ),
        }
        cleanup_graph_binding = existed_graph_binding
        cleanup_write_mode = (
            effective_write_mode
            if existed_graph_binding and existed_graph_binding.write_mode != effective_write_mode
            else None
        )
        graph_binding_model_defaults = {**graph_binding_defaults, "write_mode": effective_write_mode}
        graph_binding_lookup = {
            "name": existed_graph_binding.name if existed_graph_binding else self.data_link_name,
            "data_link_name": self.data_link_name,
            "namespace": self.namespace,
            "bk_biz_id": bk_biz_id,
            "bk_tenant_id": self.bk_tenant_id,
        }
        graph_binding_ins = GraphRelationBindingConfig(
            **graph_binding_lookup,
            **graph_binding_model_defaults,
            status=DataLinkResourceStatus.INITIALIZING.value,
        )
        if existed_graph_binding:
            graph_binding_ins.pk = existed_graph_binding.pk

        graph_binding_persist_defaults = graph_binding_model_defaults if persist_write_mode else graph_binding_defaults
        graph_binding_status_defaults = {
            **graph_binding_persist_defaults,
            "status": DataLinkResourceStatus.INITIALIZING.value,
        }
        if getattr(self, "_defer_graph_binding_update_after_apply", False):
            if persist_write_mode:
                self._graph_binding_update_after_apply = (graph_binding_lookup, graph_binding_model_defaults)
        else:
            GraphRelationBindingConfig.objects.update_or_create(
                **graph_binding_lookup,
                defaults=graph_binding_status_defaults,
            )

        if persist_write_mode and cleanup_write_mode is not None:
            self._graph_write_mode_after_apply = (graph_binding_ins.pk, effective_write_mode)

        configs: list[dict[str, Any]] = []
        if graph_binding_ins.should_write_vm:
            if not graph_binding_ins.vm_cluster_name:
                raise ValueError("compose_graph_relation_time_series_configs: vm cluster name is empty")
            with transaction.atomic(using=DATABASE_CONNECTION_NAME):
                vm_table_id_ins, _ = ResultTableConfig.objects.update_or_create(
                    name=graph_binding_ins.bkbase_result_table_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                    defaults={"table_id": table_id},
                )
                vm_storage_ins, _ = VMStorageBindingConfig.objects.update_or_create(
                    name=graph_binding_ins.vm_binding_component_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                    defaults={
                        "vm_cluster_name": vm_cluster_name,
                        "table_id": table_id,
                        "bkbase_result_table_name": graph_binding_ins.bkbase_result_table_name,
                    },
                )
                sinks = [
                    {
                        "kind": DataLinkKind.VMSTORAGEBINDING.value,
                        "name": graph_binding_ins.vm_binding_component_name,
                        "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                    }
                ]
                if settings.ENABLE_MULTI_TENANT_MODE:
                    sinks[0]["tenant"] = self.bk_tenant_id

                data_bus_ins, _ = DataBusConfig.objects.update_or_create(
                    name=graph_binding_ins.vm_databus_component_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                    defaults={
                        "data_id_name": bkbase_data_name,
                        "bk_data_id": data_source.bk_data_id,
                        "sink_names": [
                            f"{DataLinkKind.VMSTORAGEBINDING.value}:{graph_binding_ins.vm_binding_component_name}"
                        ],
                        "data_link_strategy": self.data_link_strategy,
                    },
                )
                data_bus_ins.apply_consumer_group(consumer_group)
            configs.extend(
                [
                    vm_table_id_ins.compose_config(),
                    vm_storage_ins.compose_config(rt_name=graph_binding_ins.bkbase_result_table_name),
                    data_bus_ins.compose_config(sinks),
                ]
            )

        if graph_binding_ins.should_write_surrealdb:
            configs.extend(
                self._compose_graph_relation_surrealdb_configs(
                    graph_binding_ins=graph_binding_ins,
                    bk_biz_id=bk_biz_id,
                    data_source=data_source,
                    table_id=table_id,
                    consumer_group=consumer_group,
                )
            )
        if cleanup_graph_binding and cleanup_write_mode:
            self._graph_transition_cleanup_after_apply = (cleanup_graph_binding, cleanup_write_mode)
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
        bkbase_data_name = utils.compose_bkdata_data_id_name(data_source.data_name)
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
            databus_data_id_name = existing_databus.data_id_name if existing_databus is not None else bkbase_data_name
            databus, _ = DataBusConfig.objects.update_or_create(
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                namespace=self.namespace,
                data_link_name=self.data_link_name,
                name=databus_name,
                data_id_name=databus_data_id_name,
                defaults={
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
        bcs_cluster_id: str,
        storage_cluster_name: str,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        生成联邦子集群时序数据链路配置
        @param data_source: 数据源
        @param table_id: 监控平台结果表ID
        @param bcs_cluster_id: 联邦子集群ID
        @param storage_cluster_name: 存储集群名称
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

        from metadata.models.bcs import BcsFederalClusterInfo

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

        federal_records = BcsFederalClusterInfo.objects.filter(sub_cluster_id=bcs_cluster_id, is_deleted=False)
        if not federal_records:
            logger.warning(
                "compose_federal_sub_configs: bcs_cluster_id->[%s],data_link_name->[%s],data_id->[%s] does "
                "not belong to any federal topo.return",
                bcs_cluster_id,
                self.data_link_name,
                data_source.bk_data_id,
            )
            return []

        config_list, conditions = [], []
        for record in federal_records:
            if not record.fed_builtin_metric_table_id:
                continue

            # 联邦代理集群的RT名
            proxy_k8s_metric_vmrt_name = utils.compose_bkdata_table_id(record.fed_builtin_metric_table_id)
            relabels = [{"name": "bcs_cluster_id", "value": record.fed_cluster_id}]
            logger.info(
                "compose_federal_sub_configs: data_link_name->[%s] start to compose for fed_cluster_id->[%s],"
                "match_labels ->[%s]",
                self.data_link_name,
                record.fed_cluster_id,
                record.fed_namespaces,
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
                "match_labels": [{"name": "namespace", "any": record.fed_namespaces}],
                "relabels": relabels,
                "sinks": sinks,
            }
            conditions.append(condition)

        logger.info(
            "compose_federal_sub_configs: data_link_name->[%s],bcs_cluster_id->[%s] will use conditions->[%s]to "
            "compose configs",
            self.data_link_name,
            bcs_cluster_id,
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
        bkbase_data_name = utils.compose_bkdata_data_id_name(data_source.data_name, self.data_link_strategy)
        bkbase_vmrt_name = utils.compose_bkdata_table_id(table_id, self.data_link_strategy)
        logger.info(
            "compose_configs: data_link_name->[%s] start to use bkbase_data_name->[%s] bkbase_vmrt_name->[%s]to "
            "compose configs",
            self.data_link_name,
            bkbase_data_name,
            bkbase_vmrt_name,
        )

        # 解析 compose 所需的 name：优先复用既有组件的 name（若同 kind 恰好只有
        # 一条可 claim），否则回退到新生成的 bkbase_vmrt_name 作为新建名称。
        # 存量链路里 table_id / bk_data_id 可能缺失，复用判断只依赖 datalink
        # 下同 kind 组件的一对一关系；同 kind 多条会留给 leftover 校验兜底。
        existing_rt = (
            existing_context.claim(ResultTableConfig, lambda c: True) if existing_context is not None else None
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
            existing_context.claim(DataBusConfig, lambda c: True) if existing_context is not None else None
        )

        databus_name = existing_databus.name if existing_databus is not None else bkbase_vmrt_name
        bkbase_data_name = existing_databus.data_id_name if existing_databus is not None else bkbase_data_name

        # 获取指标组维度配置
        result_table_option = ResultTableOption.objects.filter(
            table_id=table_id, bk_tenant_id=self.bk_tenant_id, name=ResultTableOption.OPTION_METRIC_GROUP_DIMENSIONS
        ).first()
        metric_group_dimensions: list[dict[str, Any]] | None = (
            result_table_option.get_value() if result_table_option is not None else None
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
            vm_storage_ins, _ = VMStorageBindingConfig.objects.update_or_create(
                name=binding_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                # bkbase_result_table_name 必须与最终实际引用的 RT 保持一致：
                # 下发给 BKBase 的 payload 里 spec.data.name 是 vm_table_id_ins.name，
                # 本地 ORM 里这个字段也是 relation.py 用来按 name 回查 ResultTableConfig
                # 的指针。复用时 RT 被 claim 成一个与 binding 不同的 name 时，如果继续
                # 写成 bkbase_vmrt_name（生成名），本地关系会指向不存在的 RT。
                defaults={
                    "table_id": table_id,
                    "bkbase_result_table_name": vm_table_id_ins.name,
                    "vm_cluster_name": storage_cluster_name,
                },
            )
            sink_item = {
                "kind": DataLinkKind.VMSTORAGEBINDING.value,
                # sink 必须指向实际存在的 VMStorageBinding，这里联动 binding_name
                # 而非 bkbase_vmrt_name，以便复用 legacy binding 时 databus 能正确引用。
                "name": binding_name,
                "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            }
            if settings.ENABLE_MULTI_TENANT_MODE:
                sink_item["tenant"] = self.bk_tenant_id
            sinks = [sink_item]

            data_bus_ins, _ = DataBusConfig.objects.update_or_create(
                name=databus_name,
                data_id_name=bkbase_data_name,
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
            # 显式透传 RT 的 name，避免复用后 RT/Binding 被独立 claim 成不同 name 时
            # binding payload 的 spec.data.name 仍然指向 binding 自己的 name（不存在的 RT）。
            vm_storage_ins.compose_config(
                rt_name=vm_table_id_ins.name, metric_group_dimensions=metric_group_dimensions
            ),
            data_bus_ins.compose_config(sinks),
        ]
        return configs

    def _compose_time_series_field_whitelist(self, table_id: str) -> dict[Literal["metrics", "tags"], list[str]] | None:
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

        Returns:
            白名单字典 ``{"metrics": [...], "tags": [...]}``；非白名单模式时返回 ``None``。
        """
        from metadata.models import ResultTableField, ResultTableOption, TimeSeriesGroup, TimeSeriesMetric

        option = ResultTableOption.objects.filter(
            table_id=table_id, bk_tenant_id=self.bk_tenant_id, name=ResultTableOption.OPTION_ENABLE_FIELD_BLACK_LIST
        ).first()
        if not (option and option.value == "false"):
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
        bkbase_data_name = utils.compose_bkdata_data_id_name(data_source.data_name, self.data_link_strategy)
        bkbase_vmrt_name = utils.compose_bkdata_table_id(table_id, self.data_link_strategy)

        # 白名单配置
        whitelist = self._compose_time_series_field_whitelist(table_id)

        # 解析 compose 所需的 name：优先复用既有组件的 name（若同 kind 恰好只有
        # 一条可 claim），否则回退到新生成的 bkbase_vmrt_name 作为新建名称。
        # 存量链路里 table_id / bk_data_id 可能缺失，复用判断只依赖 datalink
        # 下同 kind 组件的一对一关系；同 kind 多条会留给 leftover 校验兜底。
        existing_rt = (
            existing_context.claim(ResultTableConfig, lambda c: True) if existing_context is not None else None
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
            existing_context.claim(DataBusConfig, lambda c: True) if existing_context is not None else None
        )
        databus_name = existing_databus.name if existing_databus is not None else bkbase_vmrt_name
        bkbase_data_name = existing_databus.data_id_name if existing_databus is not None else bkbase_data_name

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
                data_id_name=bkbase_data_name,
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

        transform_format = self.DATABUS_TRANSFORMER_FORMAT.get(self.data_link_strategy)

        configs = [
            vm_table_id_ins.compose_config(),
            # 显式透传 RT 的 name，避免 compose_bk_plugin 场景下开启复用后
            # RT / Binding name 被独立 claim 成不同值时，binding payload 的
            # spec.data.name 仍然指向 "binding.name" 这个并不存在的 RT。
            vm_storage_ins.compose_config(whitelist=whitelist, rt_name=vm_table_id_ins.name),
            data_bus_ins.compose_config(sinks=sinks, transform_format=transform_format),
        ]
        return configs

    def apply_data_link(self, *args, **kwargs):
        """
        组装配置并下发数据链路
        声明BkBaseResultTable -> 组装链路资源配置 -> 调用API申请
        """
        from metadata.models.bkdata.result_table import BkBaseResultTable

        consumer_group: str | None = kwargs.pop("consumer_group", None)
        persist_graph_write_mode = kwargs.pop("persist_graph_write_mode", True)
        if self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES:
            self._clear_graph_relation_apply_state()
        storage_type = self.STORAGE_TYPE_MAP[self.data_link_strategy]
        if self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES:
            storage_type = self._resolve_graph_relation_storage_type(kwargs.get("write_mode"))

        try:
            # NOTE:新链路下，data_link_name和bkbase_data_name一致
            monitor_table_id: str | None = (
                kwargs.get("table_id")
                if self.data_link_strategy != self.BASEREPORT_TIME_SERIES_V1
                else self.data_link_name
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
                and persist_graph_write_mode
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
            table_id=kwargs.get("table_id"),
            bk_tenant_id=self.bk_tenant_id,
        )
        existing_context: ExistingComponentContext | None = (
            ExistingComponentContext.from_datalink(self) if enable_reuse else None
        )

        if self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES:
            kwargs["persist_write_mode"] = persist_graph_write_mode
            return self._apply_graph_relation_data_link_in_transaction(
                args=args,
                kwargs=kwargs,
                existing_context=existing_context,
                bkbase_rt_record=bkbase_rt_record,
                storage_type=storage_type,
                should_update_bkbase_rt_storage_type=should_update_bkbase_rt_storage_type,
                consumer_group=consumer_group,
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
                if existing_context is not None:
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
            if self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES:
                self._clear_graph_relation_apply_state()
            raise
        except Exception as e:  # pylint: disable=broad-except
            logger.error("apply_data_link: data_link_name->[%s] compose config error->[%s]", self.data_link_name, e)
            if self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES:
                self._clear_graph_relation_apply_state()
            raise e

        configs = self.merge_existing_component_configs(configs)

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
            if self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES:
                self._clear_graph_relation_apply_state()
            # 抛出底层错误原因，而非直接RetryError
            raise e.__cause__ if e.__cause__ else e
        except Exception as e:  # pylint: disable=broad-except
            logger.error("apply_data_link: data_link_name->[%s] apply error->[%s]", self.data_link_name, e)
            if self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES:
                self._clear_graph_relation_apply_state()
            raise e

        logger.info(
            "apply_data_link: data_link_name->[%s],strategy->[%s] response->[%s]",
            self.data_link_name,
            self.data_link_strategy,
            response,
        )
        graph_transition_cleanup = None
        graph_write_mode_after_apply = None
        graph_binding_update_after_apply = None
        if self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES:
            graph_transition_cleanup = getattr(self, "_graph_transition_cleanup_after_apply", None)
            graph_write_mode_after_apply = getattr(self, "_graph_write_mode_after_apply", None)
            graph_binding_update_after_apply = getattr(self, "_graph_binding_update_after_apply", None)
        graph_transition_cleanup_succeeded = True
        try:
            if graph_transition_cleanup:
                cleanup_graph_binding, cleanup_write_mode = graph_transition_cleanup
                try:
                    cleanup_graph_binding.transition_write_mode(cleanup_write_mode)
                except Exception as e:  # pylint: disable=broad-except
                    graph_transition_cleanup_succeeded = False
                    logger.warning(
                        "apply_data_link: data_link_name->[%s] cleanup graph write_mode transition failed, "
                        "write_mode->[%s], error->[%s]",
                        self.data_link_name,
                        cleanup_write_mode,
                        e,
                    )
            if graph_binding_update_after_apply and graph_transition_cleanup_succeeded:
                graph_binding_lookup, graph_binding_defaults = graph_binding_update_after_apply
                graph_binding_defaults = {
                    **graph_binding_defaults,
                    "status": DataLinkResourceStatus.INITIALIZING.value,
                }
                GraphRelationBindingConfig.objects.update_or_create(
                    **graph_binding_lookup,
                    defaults=graph_binding_defaults,
                )
            if graph_write_mode_after_apply:
                graph_binding_pk, target_write_mode = graph_write_mode_after_apply
                if graph_transition_cleanup_succeeded:
                    GraphRelationBindingConfig.objects.filter(pk=graph_binding_pk).update(write_mode=target_write_mode)
        finally:
            if self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES:
                self._clear_graph_relation_apply_state()
        if should_update_bkbase_rt_storage_type and graph_transition_cleanup_succeeded:
            bkbase_rt_record.storage_type = storage_type
            bkbase_rt_record.save(update_fields=["storage_type"])

    def _apply_graph_relation_data_link_in_transaction(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        existing_context: "ExistingComponentContext | None",
        bkbase_rt_record: "BkBaseResultTable",
        storage_type: str,
        should_update_bkbase_rt_storage_type: bool,
        consumer_group: str | None = None,
    ) -> None:
        """
        Apply graph relation links atomically with local compose-side metadata.

        Graph compose creates several local child resources before BKBase apply. Keeping
        compose and apply in one DB transaction ensures a failed apply rolls back only
        this attempt's local child-resource changes while preserving the old binding.
        """
        try:
            with transaction.atomic(using=DATABASE_CONNECTION_NAME):
                try:
                    self._defer_graph_binding_update_after_apply = True
                    configs: list[dict[str, Any]] = self.compose_configs(
                        *args,
                        existing_context=existing_context,
                        consumer_group=consumer_group,
                        **kwargs,
                    )
                    if existing_context is not None:
                        self._check_leftover_or_raise(existing_context)
                except ComponentReuseError:
                    logger.error(
                        "apply_data_link: data_link_name->[%s] leftover check failed, "
                        "rollback graph compose-side DB writes in this attempt",
                        self.data_link_name,
                    )
                    raise
                except Exception as e:  # pylint: disable=broad-except
                    logger.error(
                        "apply_data_link: data_link_name->[%s] compose graph config error->[%s]",
                        self.data_link_name,
                        e,
                    )
                    raise e

                logger.info(
                    "apply_data_link: data_link_name->[%s],strategy->[%s] try to use configs->[%s] to apply",
                    self.data_link_name,
                    self.data_link_strategy,
                    configs,
                )
                configs = self.merge_existing_component_configs(configs)
                try:
                    response = self.apply_data_link_with_retry(configs)
                except RetryError as e:
                    logger.error(
                        "apply_data_link: data_link_name->[%s] retry error->[%s]",
                        self.data_link_name,
                        e.__cause__,
                    )
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

                graph_transition_cleanup = getattr(self, "_graph_transition_cleanup_after_apply", None)
                graph_write_mode_after_apply = getattr(self, "_graph_write_mode_after_apply", None)
                graph_binding_update_after_apply = getattr(self, "_graph_binding_update_after_apply", None)
                graph_transition_cleanup_succeeded = True

                if graph_transition_cleanup:
                    cleanup_graph_binding, cleanup_write_mode = graph_transition_cleanup
                    try:
                        cleanup_graph_binding.transition_write_mode(cleanup_write_mode)
                    except Exception as e:  # pylint: disable=broad-except
                        graph_transition_cleanup_succeeded = False
                        logger.warning(
                            "apply_data_link: data_link_name->[%s] cleanup graph write_mode transition failed, "
                            "write_mode->[%s], error->[%s]",
                            self.data_link_name,
                            cleanup_write_mode,
                            e,
                        )
                if graph_binding_update_after_apply and graph_transition_cleanup_succeeded:
                    graph_binding_lookup, graph_binding_defaults = graph_binding_update_after_apply
                    GraphRelationBindingConfig.objects.update_or_create(
                        **graph_binding_lookup,
                        defaults={
                            **graph_binding_defaults,
                            "status": DataLinkResourceStatus.INITIALIZING.value,
                        },
                    )
                if graph_write_mode_after_apply and graph_transition_cleanup_succeeded:
                    graph_binding_pk, target_write_mode = graph_write_mode_after_apply
                    GraphRelationBindingConfig.objects.filter(pk=graph_binding_pk).update(write_mode=target_write_mode)
                if should_update_bkbase_rt_storage_type and graph_transition_cleanup_succeeded:
                    bkbase_rt_record.storage_type = storage_type
                    bkbase_rt_record.save(update_fields=["storage_type"])
        finally:
            self._clear_graph_relation_apply_state()

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
        """检查指定组件中配置后不允许修改的字段。

        只有 BKBase 已有配置与本次配置都包含目标字段时才比较；缺失字段继续按原有
        merge 补缺逻辑处理，避免影响首次下发或历史组件字段不完整的场景。
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

            raise ValueError(
                "merge_component_config: immutable component field changed,"
                f"kind->[{kind}],field->[{immutable_field.display_path}],"
                f"existing_value->[{existing_value}],current_value->[{current_value}]"
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
            if f"resource {name} of kind {kind} not found".lower() in error.message.lower():
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

    def _leftover_policy(self, kind: type["DataLinkResourceConfigBase"]) -> Literal["strict", "keep"]:
        """按 (strategy, kind) 查找 leftover 策略，未声明时默认 ``strict``。"""
        return self.REUSE_LEFTOVER_POLICY.get((self.data_link_strategy, kind), "strict")

    def _check_leftover_or_raise(self, ctx: "ExistingComponentContext") -> None:
        """基于 leftover 策略判定是否抛出 :class:`ComponentReuseError`。

        只把 ``strict`` 策略对应 kind 的残留视作违规；``keep`` 策略的残留会被忽略
        （既不删除、也不本次复用），用于兼容短期脏数据场景。
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

    def _clear_graph_relation_apply_state(self) -> None:
        for attr in (
            "_graph_transition_cleanup_after_apply",
            "_graph_write_mode_after_apply",
            "_graph_binding_update_after_apply",
            "_defer_graph_binding_update_after_apply",
        ):
            if hasattr(self, attr):
                delattr(self, attr)

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
        - ``bkbase_data_name == DataBusConfig.data_id_name``
        - ``storage_type`` / ``storage_cluster_id`` 与 ``ClusterInfo`` 实际记录保持一致。
        """
        from metadata.models import ClusterInfo
        from metadata.models.bkdata.result_table import BkBaseResultTable

        rt_name: str | None = None
        databus_class: type[DataBusConfig | GraphDataBusConfig] = DataBusConfig
        if self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES:
            graph_binding = self._get_graph_relation_binding()
            if graph_binding:
                if graph_binding.should_write_vm:
                    rt_name = graph_binding.bkbase_result_table_name
                    storage_cluster_name = graph_binding.vm_cluster_name or storage_cluster_name
                    storage_type = ClusterInfo.TYPE_VM
                elif graph_binding.should_write_surrealdb:
                    rt_name = graph_binding.graph_result_table_name or self.compose_surrealdb_table_name(table_id)
                    storage_cluster_name = graph_binding.surrealdb_cluster_name or storage_cluster_name
                    storage_type = ClusterInfo.TYPE_SURREALDB
                    databus_class = GraphDataBusConfig

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
        if rt_name:
            rt_queryset = rt_queryset.filter(name=rt_name)
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

        databus_queryset = databus_class.objects.filter(
            bk_tenant_id=self.bk_tenant_id,
            namespace=self.namespace,
            data_link_name=self.data_link_name,
        )
        databus_name = rt_name
        if rt_name and self.data_link_strategy == self.GRAPH_RELATION_TIME_SERIES:
            graph_binding = self._get_graph_relation_binding()
            if graph_binding:
                if databus_class is GraphDataBusConfig and rt_name == graph_binding.graph_result_table_name:
                    databus_name = graph_binding.graph_databus_component_name
                elif databus_class is DataBusConfig and rt_name == graph_binding.bkbase_result_table_name:
                    databus_name = graph_binding.vm_databus_component_name
        if databus_name:
            databus_queryset = databus_queryset.filter(name=databus_name)
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

    def _get_graph_relation_binding(self) -> GraphRelationBindingConfig | None:
        return GraphRelationBindingConfig.objects.filter(
            bk_tenant_id=self.bk_tenant_id,
            namespace=self.namespace,
            data_link_name=self.data_link_name,
        ).first()

    def _resolve_graph_relation_storage_type(self, write_mode: str | None) -> str:
        if write_mode is None:
            graph_binding = self._get_graph_relation_binding()
            write_mode = graph_binding.write_mode if graph_binding else GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB

        return (
            ClusterInfo.TYPE_SURREALDB
            if GraphRelationBindingConfig.normalize_write_mode(write_mode)
            == GraphRelationBindingConfig.WRITE_MODE_SURREALDB
            else ClusterInfo.TYPE_VM
        )

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
