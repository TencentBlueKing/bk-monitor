"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from django.conf import settings
from django.db import models, transaction
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from core.drf_resource import api
from metadata.models.data_link import utils
from metadata.models.data_link.constants import (
    DataLinkKind,
    DataLinkResourceStatus,
    BASEREPORT_USAGES,
    BASEREPORT_DATABUS_FORMAT,
)
from metadata.models.data_link.data_link_configs import (
    ConditionalSinkConfig,
    DataBusConfig,
    VMResultTableConfig,
    VMStorageBindingConfig,
)
from metadata.models.data_link.utils import get_bkbase_raw_data_id_name
from metadata.models.storage import ClusterInfo

logger = logging.getLogger("metadata")


class DataLink(models.Model):
    """
    一条完整的链路资源
    涵盖资源配置按需组装 -> 下发配置申请链路 ->同步元数据 全流程
    """

    BK_STANDARD_V2_TIME_SERIES = "bk_standard_v2_time_series"
    BCS_FEDERAL_PROXY_TIME_SERIES = "bcs_federal_proxy_time_series"  # 联邦代理集群（父集群）时序链路
    BCS_FEDERAL_SUBSET_TIME_SERIES = "bcs_federal_subset_time_series"  # 联邦集群（子集群）时序链路
    BASEREPORT_TIME_SERIES_V1 = "basereport_time_series_v1"  # 主机基础数据上报时序链路

    DATA_LINK_STRATEGY_CHOICES = (
        (BK_STANDARD_V2_TIME_SERIES, "标准单指标单表时序数据链路"),
        (BCS_FEDERAL_PROXY_TIME_SERIES, "联邦代理时序数据链路"),
        (BCS_FEDERAL_SUBSET_TIME_SERIES, "联邦子集时序数据链路"),
        (BASEREPORT_TIME_SERIES_V1, "主机基础采集时序数据链路"),
    )

    # 各个套餐所需要的链路资源
    STRATEGY_RELATED_COMPONENTS = {
        BK_STANDARD_V2_TIME_SERIES: [VMResultTableConfig, VMStorageBindingConfig, DataBusConfig],
        BCS_FEDERAL_PROXY_TIME_SERIES: [VMResultTableConfig, VMStorageBindingConfig],
        BCS_FEDERAL_SUBSET_TIME_SERIES: [
            VMResultTableConfig,
            VMStorageBindingConfig,
            ConditionalSinkConfig,
            DataBusConfig,
        ],
        BASEREPORT_TIME_SERIES_V1: [VMResultTableConfig, VMStorageBindingConfig, ConditionalSinkConfig, DataBusConfig],
    }

    STORAGE_TYPE_MAP = {
        BK_STANDARD_V2_TIME_SERIES: ClusterInfo.TYPE_VM,
        BCS_FEDERAL_PROXY_TIME_SERIES: ClusterInfo.TYPE_VM,
        BCS_FEDERAL_SUBSET_TIME_SERIES: ClusterInfo.TYPE_VM,
        BASEREPORT_TIME_SERIES_V1: ClusterInfo.TYPE_VM,
    }

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

    def compose_configs(self, *args, **kwargs):
        """
        生成对应套餐的链路完整配置
        """

        # 类似switch的形式，选择对应的组装方式
        switcher = {
            DataLink.BK_STANDARD_V2_TIME_SERIES: self.compose_standard_time_series_configs,
            DataLink.BCS_FEDERAL_PROXY_TIME_SERIES: self.compose_bcs_federal_proxy_time_series_configs,
            DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES: self.compose_bcs_federal_subset_time_series_configs,
            DataLink.BASEREPORT_TIME_SERIES_V1: self.compose_basereport_time_series_configs,
        }
        compose_method = switcher.get(
            self.data_link_strategy,
        )
        return compose_method(*args, **kwargs)

    def compose_basereport_time_series_configs(self, data_source, storage_cluster_name, bk_biz_id, source):
        """
        生成基础采集时序链路配置
        @param data_source: 数据源
        @param table_id: 监控平台结果表ID
        @param storage_cluster_name: 存储集群名称
        @param bk_biz_id: 业务id
        @param source: 数据来源
        @return: config_list 配置列表
        """
        logger.info(
            "compose_basereport_configs: data_link_name->[%s] ,bk_data_id->[%s],table_id->[%s],vm_cluster_name->[%s] "
            "start to compose configs",
            self.data_link_name,
            data_source.bk_data_id,
            storage_cluster_name,
        )

        # 需要注意超出计算平台meta长度限制问题
        bkbase_vmrt_prefix = f"base_{bk_biz_id}_{source}"

        config_list = []
        conditions = []

        try:
            with transaction.atomic():
                # 创建11个VMResultTableConfig和VMStorageBindingConfig
                for usage in BASEREPORT_USAGES:
                    usage_vmrt_name = f"{bkbase_vmrt_prefix}_{usage}"
                    logger.info(
                        "compose_basereport_configs: try to create rt and storage for usage->[%s],name->[%s]",
                        usage,
                        usage_vmrt_name,
                    )

                    # 创建VM ResultTable配置
                    vm_table_id_ins, _ = VMResultTableConfig.objects.get_or_create(
                        name=usage_vmrt_name,
                        data_link_name=self.data_link_name,
                        namespace=self.namespace,
                        bk_biz_id=bk_biz_id,
                        bk_tenant_id=self.bk_tenant_id,
                    )

                    # 创建VM Storage绑定配置
                    vm_storage_ins, _ = VMStorageBindingConfig.objects.get_or_create(
                        name=usage_vmrt_name,
                        vm_cluster_name=storage_cluster_name,
                        data_link_name=self.data_link_name,
                        namespace=self.namespace,
                        bk_biz_id=bk_biz_id,
                        bk_tenant_id=self.bk_tenant_id,
                    )

                    # 添加配置到列表
                    config_list.extend(
                        [
                            vm_table_id_ins.compose_config(),
                            vm_storage_ins.compose_config(),
                        ]
                    )

                    # 为每个usage创建conditional sink条件
                    sinks = [
                        {
                            "kind": "VmStorageBinding",
                            "name": usage_vmrt_name,
                            "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                        }
                    ]

                    relabels = [{"name": "__result_table", "value": usage}]

                    condition = {
                        "match_labels": [{"name": "__result_table", "any": [usage]}],
                        "relabels": relabels,
                        "sinks": sinks,
                    }
                    conditions.append(condition)

                # 创建ConditionalSinkConfig
                vm_conditional_ins, _ = ConditionalSinkConfig.objects.get_or_create(
                    name=self.data_link_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                )

                # 创建DataBusConfig
                data_bus_ins, _ = DataBusConfig.objects.get_or_create(
                    name=self.data_link_name,
                    data_id_name=self.data_link_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=self.bk_tenant_id,
                )

        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "compose_basereport_configs: data_link_name->[%s] error->[%s],rollback!", self.data_link_name, e
            )
            raise e

        logger.info(
            "compose_basereport_configs: data_link_name->[%s] will use conditions->[%s] to compose configs",
            self.data_link_name,
            conditions,
        )

        # 组装conditional sink配置
        vm_conditional_sink_config = vm_conditional_ins.compose_conditional_sink_config(conditions=conditions)

        # 创建conditional sink引用
        conditional_sink = [
            {
                "kind": DataLinkKind.CONDITIONALSINK.value,
                "name": self.data_link_name,
                "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            },
        ]

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

    def compose_bcs_federal_proxy_time_series_configs(self, data_source, table_id, storage_cluster_name):
        """
        生成联邦代理集群（父集群）时序数据链路配置
        """

        logger.info(
            "compose_federal_proxy_configs: data_link_name->[%s] ,bk_data_id->[%s],table_id->[%s],vm_cluster_name->[%s]"
            "start to compose configs",
            self.data_link_name,
            data_source.bk_data_id,
            table_id,
            storage_cluster_name,
        )

        bkbase_data_name = utils.compose_bkdata_data_id_name(data_source.data_name, self.data_link_strategy)
        bkbase_vmrt_name = utils.compose_bkdata_table_id(table_id, self.data_link_strategy)
        bk_biz_id = utils.parse_and_get_rt_biz_id(table_id)

        logger.info(
            "compose_federal_proxy_configs: data_link_name->[%s] start to use bkbase_data_name->[%s] "
            "bkbase_vmrt_name->[%s]to"
            "compose configs",
            self.data_link_name,
            bkbase_data_name,
            bkbase_vmrt_name,
        )

        try:
            with transaction.atomic():
                # 渲染所需的资源配置
                vm_table_id_ins, _ = VMResultTableConfig.objects.get_or_create(
                    name=bkbase_vmrt_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                )
                vm_storage_ins, _ = VMStorageBindingConfig.objects.get_or_create(
                    name=bkbase_vmrt_name,
                    vm_cluster_name=storage_cluster_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "compose_federal_proxy_configs: data_link_name->[%s] error->[%s],rollback!", self.data_link_name, e
            )
            raise e

        configs = [
            vm_table_id_ins.compose_config(),
            vm_storage_ins.compose_config(),
        ]
        return configs

    def compose_bcs_federal_subset_time_series_configs(
        self, data_source, table_id, bcs_cluster_id, storage_cluster_name
    ):
        """
        生成联邦子集群时序数据链路配置
        @param data_source: 数据源
        @param table_id: 监控平台结果表ID
        @param bcs_cluster_id: 联邦子集群ID
        @param storage_cluster_name: 存储集群名称
        @return: config_list 配置列表
        """
        logger.info(
            "compose_federal_sub_configs: data_link_name->[%s] ,bk_data_id->[%s],table_id->[%s],vm_cluster_name->[%s]"
            "start to compose configs",
            self.data_link_name,
            data_source.bk_data_id,
            table_id,
            storage_cluster_name,
        )

        from metadata.models.bcs import BcsFederalClusterInfo

        # 联邦子集群场景下，这里的bkbase_data_name会有一个fed_的前缀
        bkbase_raw_data_name = get_bkbase_raw_data_id_name(data_source=data_source, table_id=table_id)

        bkbase_data_name = utils.compose_bkdata_data_id_name(data_source.data_name, self.data_link_strategy)
        bkbase_vmrt_name = utils.compose_bkdata_table_id(table_id, self.data_link_strategy)

        bk_biz_id = utils.parse_and_get_rt_biz_id(table_id)

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
            return

        config_list, conditions = [], []
        for record in federal_records:
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
        try:
            with transaction.atomic():
                vm_conditional_ins, _ = ConditionalSinkConfig.objects.get_or_create(
                    name=bkbase_vmrt_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                )
                data_bus_ins, _ = DataBusConfig.objects.get_or_create(
                    name=bkbase_vmrt_name,
                    data_id_name=bkbase_raw_data_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "compose_federal_sub_configs: data_link_name->[%s] error->[%s],rollback!", self.data_link_name, e
            )
            raise e

        vm_conditional_sink_config = vm_conditional_ins.compose_conditional_sink_config(conditions=conditions)
        conditional_sink = [
            {
                "kind": DataLinkKind.CONDITIONALSINK.value,
                "name": bkbase_vmrt_name,
                "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            },
        ]
        data_bus_config = data_bus_ins.compose_config(sinks=conditional_sink)
        config_list.extend([vm_conditional_sink_config, data_bus_config])
        return config_list

    def compose_standard_time_series_configs(self, data_source, table_id, storage_cluster_name):
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
        bk_biz_id = utils.parse_and_get_rt_biz_id(table_id)
        logger.info(
            "compose_configs: data_link_name->[%s] start to use bkbase_data_name->[%s] bkbase_vmrt_name->[%s]to "
            "compose configs",
            self.data_link_name,
            bkbase_data_name,
            bkbase_vmrt_name,
        )
        try:
            with transaction.atomic():
                # 渲染所需的资源配置
                vm_table_id_ins, _ = VMResultTableConfig.objects.get_or_create(
                    name=bkbase_vmrt_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                )
                vm_storage_ins, _ = VMStorageBindingConfig.objects.get_or_create(
                    name=bkbase_vmrt_name,
                    vm_cluster_name=storage_cluster_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                )
                sinks = [
                    {
                        "kind": DataLinkKind.VMSTORAGEBINDING.value,
                        "name": bkbase_vmrt_name,
                        "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                    }
                ]
                data_bus_ins, _ = DataBusConfig.objects.get_or_create(
                    name=bkbase_vmrt_name,
                    data_id_name=bkbase_data_name,
                    data_link_name=self.data_link_name,
                    namespace=self.namespace,
                    bk_biz_id=bk_biz_id,
                )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("compose_configs: data_link_name->[%s] error->[%s],rollback!", self.data_link_name, e)
            raise e

        configs = [
            vm_table_id_ins.compose_config(),
            vm_storage_ins.compose_config(),
            data_bus_ins.compose_config(sinks),
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
            configs = self.compose_configs(*args, **kwargs)
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
            raise e.__cause__
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
    def apply_data_link_with_retry(self, configs):
        """
        根据指定配置，申请数据链路，具备重试机制，最多重试四次，最高等待10秒
        @param configs: 链路资源配置
        """
        try:
            response = api.bkdata.apply_data_link({"config": configs})
            return response
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
            storage_cluster_id = ClusterInfo.objects.get(cluster_name=storage_cluster_name).cluster_id
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
        from metadata.models import ClusterInfo, AccessVMRecord

        try:
            storage_cluster_id = ClusterInfo.objects.get(cluster_name=storage_cluster_name).cluster_id
        except ClusterInfo.DoesNotExist:
            logger.error("sync_metadata: storage_cluster_name->[%s] not exist!", storage_cluster_name)
            return

        bkbase_vmrt_prefix = f"base_{bk_biz_id}_{source}"

        try:
            with transaction.atomic():
                # 创建11个VMResultTableConfig和VMStorageBindingConfig
                for usage in BASEREPORT_USAGES:
                    vm_result_table_id = f"{bkbase_vmrt_prefix}_{usage}"
                    result_table_id = f"{self.bk_tenant_id}_{bk_biz_id}_{source}.{usage}"
                    vm_record, _ = AccessVMRecord.objects.get_or_create(
                        result_table_id=result_table_id,
                        vm_result_table_id=vm_result_table_id,
                        storage_cluster_id=storage_cluster_id,
                        vm_cluster_id=storage_cluster_id,
                        bk_base_data_id=datasource.bk_data_id,
                    )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("sync_basereport_metadata: failed to create access vm record! error message->%s", e)
