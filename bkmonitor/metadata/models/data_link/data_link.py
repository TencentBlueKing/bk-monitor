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
from functools import partial
from typing import TYPE_CHECKING, Any, Literal

from django.conf import settings
from django.db import models, transaction
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from core.drf_resource import api
from metadata.models.data_link import utils
from metadata.models.data_link.constants import (
    BASEREPORT_DATABUS_FORMAT,
    BASEREPORT_USAGES,
    BK_EXPORTER_TRANSFORMER_FORMAT,
    BK_STANDARD_TRANSFORMER_FORMAT,
    SYSTEM_PROC_PERF_DATABUS_FORMAT,
    SYSTEM_PROC_PORT_DATABUS_FORMAT,
    DataLinkKind,
    DataLinkResourceStatus,
)
from metadata.models.data_link.data_link_configs import (
    ConditionalSinkConfig,
    DataBusConfig,
    DorisStorageBindingConfig,
    ESStorageBindingConfig,
    ResultTableConfig,
    VMStorageBindingConfig,
)
from metadata.models.data_link.utils import generate_result_table_field_list, get_bkbase_raw_data_id_name
from metadata.models.storage import ClusterInfo, DorisStorage, ESStorage

if TYPE_CHECKING:
    from metadata.models import DataSource
    from metadata.models.data_link.data_link_configs import DataLinkResourceConfigBase

logger = logging.getLogger("metadata")


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
        BASEREPORT_TIME_SERIES_V1: [ResultTableConfig, VMStorageBindingConfig, ConditionalSinkConfig, DataBusConfig],
        BASE_EVENT_V1: [ResultTableConfig, ESStorageBindingConfig, DataBusConfig],
        SYSTEM_PROC_PERF: [ResultTableConfig, VMStorageBindingConfig, DataBusConfig],
        SYSTEM_PROC_PORT: [ResultTableConfig, VMStorageBindingConfig, DataBusConfig],
        BK_LOG: [ResultTableConfig, ESStorageBindingConfig, DorisStorageBindingConfig, DataBusConfig],
        BK_STANDARD_V2_EVENT: [ResultTableConfig, ESStorageBindingConfig, DataBusConfig],
    }

    STORAGE_TYPE_MAP = {
        BK_STANDARD_V2_TIME_SERIES: ClusterInfo.TYPE_VM,
        BK_EXPORTER_TIME_SERIES: ClusterInfo.TYPE_VM,
        BK_STANDARD_TIME_SERIES: ClusterInfo.TYPE_VM,
        BCS_FEDERAL_PROXY_TIME_SERIES: ClusterInfo.TYPE_VM,
        BCS_FEDERAL_SUBSET_TIME_SERIES: ClusterInfo.TYPE_VM,
        BASEREPORT_TIME_SERIES_V1: ClusterInfo.TYPE_VM,
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
        component_classes = self.STRATEGY_RELATED_COMPONENTS[self.data_link_strategy]
        for component_class in reversed(component_classes):
            components = component_class.objects.filter(data_link_name=self.data_link_name)
            for component in components:
                component.delete_config()
        self.delete()

    def compose_configs(self, *args, **kwargs):
        """
        生成对应套餐的链路完整配置
        """

        # 类似switch的形式，选择对应的组装方式
        switcher = {
            DataLink.BK_STANDARD_V2_TIME_SERIES: self.compose_standard_time_series_configs,
            DataLink.BK_STANDARD_TIME_SERIES: self.compose_bk_plugin_time_series_config,
            DataLink.BK_EXPORTER_TIME_SERIES: self.compose_bk_plugin_time_series_config,
            DataLink.BCS_FEDERAL_PROXY_TIME_SERIES: self.compose_bcs_federal_proxy_time_series_configs,
            DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES: self.compose_bcs_federal_subset_time_series_configs,
            DataLink.BASEREPORT_TIME_SERIES_V1: self.compose_basereport_time_series_configs,
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
        return switcher[self.data_link_strategy](*args, **kwargs)

    def compose_custom_event_configs(
        self,
        bk_biz_id: int,
        data_source: "DataSource",
        table_id: str,
    ) -> list[dict[str, Any]]:
        """生成自定义事件链路

        Args:
            bk_biz_id: 业务ID
            data_source: 数据源
            table_id: 结果表ID
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
        with transaction.atomic():
            es_table_ins, _ = ResultTableConfig.objects.update_or_create(
                name=self.data_link_name,
                namespace=self.namespace,
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                data_link_name=self.data_link_name,
                defaults={"table_id": table_id},
            )

            es_storage_ins, _ = ESStorageBindingConfig.objects.update_or_create(
                name=self.data_link_name,
                namespace=self.namespace,
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                data_link_name=self.data_link_name,
                es_cluster_name=es_storage.storage_cluster.cluster_name,
                timezone=es_storage.time_zone,  # 时区,默认0时区
                defaults={"table_id": table_id, "bkbase_result_table_name": self.data_link_name},
            )

            fields = generate_result_table_field_list(table_id=table_id, bk_tenant_id=self.bk_tenant_id)
            index_name = table_id.replace(".", "_")
            write_alias = f"write_%Y%m%d_{index_name}"
            unique_field_list = ResultTableOption.objects.get(
                bk_tenant_id=self.bk_tenant_id, table_id=table_id, name=ResultTableOption.OPTION_ES_DOCUMENT_ID
            ).get_value()

            databus_ins, _ = DataBusConfig.objects.update_or_create(
                name=self.data_link_name,
                namespace=self.namespace,
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                data_link_name=self.data_link_name,
                data_id_name=bkbase_data_name,
                defaults={
                    "bk_data_id": data_source.bk_data_id,
                    "sink_names": [f"{DataLinkKind.ESSTORAGEBINDING.value}:{es_storage_ins.name}"],
                },
            )

            es_rt_config = es_table_ins.compose_config(fields=fields)
            es_binding_config = es_storage_ins.compose_config(
                storage_cluster_name=es_storage.storage_cluster.cluster_name,
                write_alias_format=write_alias,
                unique_field_list=unique_field_list,
                json_field_list=["event", "dimension"],
            )
            databus_config = databus_ins.compose_log_config(
                sinks=[
                    {
                        "kind": DataLinkKind.ESSTORAGEBINDING.value,
                        "name": es_storage_ins.name,
                        "namespace": self.namespace,
                    }
                ],
                rules=CUSTOM_EVENT_CLEAN_RULES,
            )

        config_list = [es_rt_config, es_binding_config, databus_config]
        logger.info(
            "compose_custom_event_configs: data_link_name->[%s] composed configs successfully,config_list->[%s]",
            self.data_link_name,
            config_list,
        )
        return config_list

    def compose_log_configs(
        self,
        bk_biz_id: int,
        data_source: "DataSource",
        table_id: str,
    ) -> list[dict[str, Any]]:
        """生成日志链路配置

        Args:
            bk_biz_id: 业务ID
            data_source: 数据源
            table_id: 结果表ID
            storage_cluster_name: 存储集群名称
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
        with transaction.atomic():
            # 获取结果表选项
            option = ResultTableOption.objects.get(
                bk_tenant_id=self.bk_tenant_id, table_id=table_id, name=ResultTableOption.OPTION_V4_LOG_DATA_LINK
            ).value
            datalink_option = LogV4DataLinkOption(**json.loads(option))

            fields = generate_result_table_field_list(table_id=table_id, bk_tenant_id=self.bk_tenant_id)
            clean_rules = [clean_rule.model_dump() for clean_rule in datalink_option.clean_rules]

            # 创建结果表配置
            result_table, _ = ResultTableConfig.objects.update_or_create(
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                namespace=self.namespace,
                data_link_name=self.data_link_name,
                name=self.data_link_name,
                defaults={"table_id": table_id},
            )

            # 创建存储绑定配置
            databus_sinks: list[dict[str, Any]] = []
            bingding_configs: list[dict[str, Any]] = []

            # 创建ES存储绑定配置
            if es_storage and datalink_option.es_storage_config:
                storage_option = datalink_option.es_storage_config
                binding, _ = ESStorageBindingConfig.objects.update_or_create(
                    bk_tenant_id=self.bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    namespace=self.namespace,
                    data_link_name=self.data_link_name,
                    name=self.data_link_name,
                    defaults={
                        "es_cluster_name": es_storage.storage_cluster.cluster_name,
                        "timezone": es_storage.time_zone,
                        "table_id": table_id,
                        "bkbase_result_table_name": self.data_link_name,
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
                binding, _ = DorisStorageBindingConfig.objects.update_or_create(
                    bk_tenant_id=self.bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    namespace=self.namespace,
                    data_link_name=self.data_link_name,
                    name=self.data_link_name,
                    defaults={
                        "table_id": table_id,
                        "bkbase_result_table_name": self.data_link_name,
                        "doris_cluster_name": doris_storage.storage_cluster.cluster_name,
                    },
                )
                bingding_configs.append(
                    binding.compose_config(
                        storage_cluster_name=doris_storage.storage_cluster.cluster_name,
                        storage_keys=storage_option.storage_keys,
                        json_fields=storage_option.json_fields,
                        field_config_group=storage_option.field_config_group,
                        expires=f"{doris_storage.expire_days}d",
                        flush_timeout=storage_option.flush_timeout,
                    )
                )
                databus_sinks.append(
                    {
                        "kind": DataLinkKind.DORISBINDING.value,
                        "name": binding.name,
                        "namespace": self.namespace,
                    }
                )

            # 如果没有任何存储绑定配置，则抛出异常
            if not bingding_configs:
                raise ValueError("至少需要一个存储绑定配置")

            # 创建数据总线配置
            databus, _ = DataBusConfig.objects.update_or_create(
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                namespace=self.namespace,
                data_link_name=self.data_link_name,
                name=self.data_link_name,
                data_id_name=bkbase_data_name,
                defaults={
                    "bk_data_id": data_source.bk_data_id,
                    "sink_names": [f"{sink['kind']}:{sink['name']}" for sink in databus_sinks],
                },
            )

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

        transform_format_map = {
            DataLink.SYSTEM_PROC_PERF: SYSTEM_PROC_PERF_DATABUS_FORMAT,
            DataLink.SYSTEM_PROC_PORT: SYSTEM_PROC_PORT_DATABUS_FORMAT,
        }

        with transaction.atomic():
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
                vm_cluster_name=storage_cluster_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={"table_id": table_id, "bkbase_result_table_name": bkbase_vmrt_name},
            )

            sink_item = {
                "kind": DataLinkKind.VMSTORAGEBINDING.value,
                "name": bkbase_vmrt_name,
                "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            }
            if settings.ENABLE_MULTI_TENANT_MODE:
                sink_item["tenant"] = self.bk_tenant_id

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

        return [
            vm_table_id_ins.compose_config(),
            vm_storage_ins.compose_config(),
            data_bus_ins.compose_config(sinks=[sink_item], transform_format=transform_format_map[data_link_strategy]),
        ]

    def compose_basereport_time_series_configs(
        self,
        data_source: "DataSource",
        storage_cluster_name: str,
        bk_biz_id: int,
        source: str,
        prefix: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        生成基础采集时序链路配置
        @param data_source: 数据源
        @param storage_cluster_name: 存储集群名称
        @param bk_biz_id: 业务id
        @param source: 数据来源
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
        conditions = []

        with transaction.atomic():
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
                    vm_cluster_name=storage_cluster_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                    defaults={"table_id": usage_monitor_table_id, "bkbase_result_table_name": usage_vmrt_name},
                )
                vm_storage_ins_cmdb, _ = VMStorageBindingConfig.objects.update_or_create(
                    name=usage_cmdb_level_vmrt_name,
                    vm_cluster_name=storage_cluster_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                    defaults={
                        "table_id": usage_monitor_cmdb_table_id,
                        "bkbase_result_table_name": usage_cmdb_level_vmrt_name,
                    },
                )

                # 添加配置到列表
                config_list.extend(
                    [
                        vm_table_id_ins.compose_config(),
                        vm_table_id_ins_cmdb.compose_config(),
                        vm_storage_ins.compose_config(),
                        vm_storage_ins_cmdb.compose_config(),
                    ]
                )

                # 为每个usage创建conditional sink条件
                sink_item = {
                    "kind": "VmStorageBinding",
                    "name": usage_vmrt_name,
                    "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                }
                if settings.ENABLE_MULTI_TENANT_MODE:
                    sink_item["tenant"] = self.bk_tenant_id

                sinks = [sink_item]

                sink_item_cmdb = {
                    "kind": "VmStorageBinding",
                    "name": usage_cmdb_level_vmrt_name,
                    "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                }
                if settings.ENABLE_MULTI_TENANT_MODE:
                    sink_item_cmdb["tenant"] = self.bk_tenant_id

                sinks_cmdb = [sink_item_cmdb]

                condition = {
                    "match_labels": [{"name": "__result_table", "any": [usage]}],
                    "sinks": sinks,
                }
                cmdb_condition = {
                    "match_labels": [{"name": "__result_table", "any": [f"{usage}_cmdb"]}],
                    "sinks": sinks_cmdb,
                }
                conditions.append(condition)
                conditions.append(cmdb_condition)

            # 创建ConditionalSinkConfig
            vm_conditional_ins, _ = ConditionalSinkConfig.objects.get_or_create(
                name=self.data_link_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
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
                    "sink_names": [f"{DataLinkKind.CONDITIONALSINK.value}:{self.data_link_name}"],
                },
            )

        logger.info(
            "compose_basereport_configs: data_link_name->[%s] will use conditions->[%s] to compose configs",
            self.data_link_name,
            conditions,
        )

        # 组装conditional sink配置
        vm_conditional_sink_config = vm_conditional_ins.compose_conditional_sink_config(conditions=conditions)

        # 创建conditional sink引用
        conditional_sink_item = {
            "kind": DataLinkKind.CONDITIONALSINK.value,
            "name": self.data_link_name,
            "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        }
        if settings.ENABLE_MULTI_TENANT_MODE:
            conditional_sink_item["tenant"] = self.bk_tenant_id

        conditional_sink = [conditional_sink_item]

        # 组装data bus配置
        data_bus_config = data_bus_ins.compose_config(
            sinks=conditional_sink, transform_format=BASEREPORT_DATABUS_FORMAT
        )

        # 添加conditional sink和data bus配置到配置列表
        config_list.extend([vm_conditional_sink_config, data_bus_config])

        logger.info(
            "compose_basereport_configs: data_link_name->[%s] composed %d configs successfully",
            self.data_link_name,
            len(config_list),
        )

        return config_list

    def compose_base_event_configs(
        self, data_source: "DataSource", table_id: str, storage_cluster_name: str, bk_biz_id: int, timezone: int = 0
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

        with transaction.atomic():
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
                es_cluster_name=storage_cluster_name,
                timezone=timezone,  # 时区,默认0时区
                defaults={"table_id": table_id, "bkbase_result_table_name": component_name},
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
        self, bk_biz_id: int, data_source: "DataSource", table_id: str, storage_cluster_name: str
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

        with transaction.atomic():
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
                vm_cluster_name=storage_cluster_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={"table_id": table_id, "bkbase_result_table_name": bkbase_vmrt_name},
            )

        configs = [
            vm_table_id_ins.compose_config(),
            vm_storage_ins.compose_config(),
        ]
        return configs

    def compose_bcs_federal_subset_time_series_configs(
        self, bk_biz_id: int, data_source: "DataSource", table_id: str, bcs_cluster_id: str, storage_cluster_name: str
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

        with transaction.atomic():
            vm_conditional_ins, _ = ConditionalSinkConfig.objects.get_or_create(
                name=bkbase_vmrt_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
            )
            data_bus_ins, _ = DataBusConfig.objects.update_or_create(
                name=bkbase_vmrt_name,
                data_id_name=bkbase_raw_data_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "bk_data_id": data_source.bk_data_id,
                    "sink_names": [f"{DataLinkKind.CONDITIONALSINK.value}:{bkbase_vmrt_name}"],
                },
            )

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
        self, bk_biz_id: int, data_source: "DataSource", table_id: str, storage_cluster_name: str
    ) -> list[dict[str, Any]]:
        """
        生成标准单指标单表时序数据链路配置
        @param data_source: 数据源
        @param table_id: 监控平台结果表ID（Metadata中的）
        @param storage_cluster_name: VM集群名称
        """
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
        with transaction.atomic():
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
                vm_cluster_name=storage_cluster_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={"table_id": table_id, "bkbase_result_table_name": bkbase_vmrt_name},
            )
            sinks = [
                {
                    "kind": DataLinkKind.VMSTORAGEBINDING.value,
                    "name": bkbase_vmrt_name,
                    "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                }
            ]
            if settings.ENABLE_MULTI_TENANT_MODE:
                sinks[0]["tenant"] = self.bk_tenant_id

            data_bus_ins, _ = DataBusConfig.objects.update_or_create(
                name=bkbase_vmrt_name,
                data_id_name=bkbase_data_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={
                    "bk_data_id": data_source.bk_data_id,
                    "sink_names": [f"{DataLinkKind.VMSTORAGEBINDING.value}:{bkbase_vmrt_name}"],
                },
            )

        configs = [
            vm_table_id_ins.compose_config(),
            vm_storage_ins.compose_config(),
            data_bus_ins.compose_config(sinks),
        ]
        return configs

    def compose_bk_plugin_time_series_config(
        self, bk_biz_id: int, data_source: "DataSource", table_id: str, storage_cluster_name: str
    ) -> list[dict[str, Any]]:
        """
        生成采集插件时序数据链路配置 -- bk_standard & bk_exporter
        """
        from metadata.models import ResultTableField, ResultTableOption

        bkbase_data_name = utils.compose_bkdata_data_id_name(data_source.data_name, self.data_link_strategy)
        bkbase_vmrt_name = utils.compose_bkdata_table_id(table_id, self.data_link_strategy)

        # 白名单配置
        whitelist: dict[Literal["metrics", "tags"], list[str]] | None = None
        option = ResultTableOption.objects.filter(
            table_id=table_id, bk_tenant_id=self.bk_tenant_id, name=ResultTableOption.OPTION_ENABLE_FIELD_BLACK_LIST
        ).first()
        if option and option.value == "false":
            result_table_fields = ResultTableField.objects.filter(
                table_id=table_id, bk_tenant_id=self.bk_tenant_id, is_disabled=False
            )
            metrics, tags = [], []
            for field in result_table_fields:
                if field.tag == ResultTableField.FIELD_TAG_METRIC:
                    metrics.append(field.field_name)
                elif field.tag == ResultTableField.FIELD_TAG_DIMENSION:
                    tags.append(field.field_name)
            whitelist = {"metrics": metrics, "tags": tags}

        with transaction.atomic():
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
                vm_cluster_name=storage_cluster_name,
                data_link_name=self.data_link_name,
                namespace=self.namespace,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=self.bk_tenant_id,
                defaults={"table_id": table_id, "bkbase_result_table_name": bkbase_vmrt_name},
            )
            sink_item = {
                "kind": DataLinkKind.VMSTORAGEBINDING.value,
                "name": bkbase_vmrt_name,
                "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            }
            if settings.ENABLE_MULTI_TENANT_MODE:
                sink_item["tenant"] = self.bk_tenant_id

            sinks = [sink_item]

            data_bus_ins, _ = DataBusConfig.objects.update_or_create(
                name=bkbase_vmrt_name,
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

        transform_format = self.DATABUS_TRANSFORMER_FORMAT.get(self.data_link_strategy)

        configs = [
            vm_table_id_ins.compose_config(),
            vm_storage_ins.compose_config(whitelist=whitelist),
            data_bus_ins.compose_config(sinks=sinks, transform_format=transform_format),
        ]
        return configs

    def apply_data_link(self, *args, **kwargs):
        """
        组装配置并下发数据链路
        声明BkBaseResultTable -> 组装链路资源配置 -> 调用API申请
        """
        from metadata.models.bkdata.result_table import BkBaseResultTable

        try:
            # NOTE:新链路下，data_link_name和bkbase_data_name一致
            BkBaseResultTable.objects.get_or_create(
                data_link_name=self.data_link_name,
                monitor_table_id=kwargs.get("table_id")
                if self.data_link_strategy != self.BASEREPORT_TIME_SERIES_V1
                else self.data_link_name,
                bkbase_data_name=self.data_link_name,
                storage_type=self.STORAGE_TYPE_MAP[self.data_link_strategy],
                defaults={
                    "status": DataLinkResourceStatus.INITIALIZING.value,
                },
                bk_tenant_id=self.bk_tenant_id,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "apply_data_link: data_link_name->[%s] create BkBaseResultTable error->[%s]", self.data_link_name, e
            )
            raise e

        try:
            configs: list[dict[str, Any]] = self.compose_configs(*args, **kwargs)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("apply_data_link: data_link_name->[%s] compose config error->[%s]", self.data_link_name, e)
            raise e
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

    def sync_metadata(self, data_source, table_id, storage_cluster_name):
        """
        同步元数据
        同步此前的计算平台链路记录，设置状态为OK
        """
        from metadata.models import ClusterInfo
        from metadata.models.bkdata.result_table import BkBaseResultTable

        bkbase_data_name = utils.compose_bkdata_data_id_name(data_source.data_name, self.data_link_strategy)
        bkbase_vmrt_name = utils.compose_bkdata_table_id(table_id, self.data_link_strategy)

        # 现阶段默认都为VM存储类型
        storage_type = ClusterInfo.TYPE_VM

        try:
            storage_cluster_id = ClusterInfo.objects.get(
                bk_tenant_id=self.bk_tenant_id, cluster_name=storage_cluster_name
            ).cluster_id
        except ClusterInfo.DoesNotExist:
            logger.error("sync_metadata: storage_cluster_name->[%s] not exist!", storage_cluster_name)
            return

        try:
            with transaction.atomic():
                BkBaseResultTable.objects.update_or_create(
                    data_link_name=self.data_link_name,
                    monitor_table_id=table_id,
                    storage_type=self.STORAGE_TYPE_MAP[self.data_link_strategy],
                    defaults={
                        "bkbase_rt_name": bkbase_vmrt_name,
                        "bkbase_data_name": bkbase_data_name,
                        "bkbase_table_id": f"{settings.DEFAULT_BKDATA_BIZ_ID}_{bkbase_vmrt_name}",
                        "storage_type": storage_type,
                        "storage_cluster_id": storage_cluster_id,
                    },
                )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "sync_metadata: data_link_name->[%s],sync_metadata failed,error->{%s],rollback!", self.data_link_name, e
            )

    def sync_basereport_metadata(self, bk_biz_id, storage_cluster_name, source, datasource):
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

        bkbase_vmrt_prefix = f"base_{bk_biz_id}_{source}"

        try:
            with transaction.atomic():
                # 创建11个ResultTableConfig和VMStorageBindingConfig
                for usage in BASEREPORT_USAGES:
                    vm_result_table_id = f"{bk_biz_id}_{bkbase_vmrt_prefix}_{usage}"
                    result_table_id = f"{self.bk_tenant_id}_{bk_biz_id}_{source}.{usage}"
                    vm_record, _ = AccessVMRecord.objects.update_or_create(
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
