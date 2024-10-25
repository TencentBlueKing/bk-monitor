# -*- coding: utf-8 -*-
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

from core.drf_resource import api
from metadata.models.data_link import utils
from metadata.models.data_link.constants import DataLinkKind, DataLinkResourceStatus
from metadata.models.data_link.data_link_configs import (
    DataBusConfig,
    VMResultTableConfig,
    VMStorageBindingConfig,
)

logger = logging.getLogger("metadata")


class DataLink(models.Model):
    """
    一条完整的链路资源
    涵盖资源配置按需组装 -> 下发配置申请链路 ->同步元数据 全流程
    """

    BK_STANDARD_V2_TIME_SERIES = "bk_standard_v2_time_series"
    BCS_FEDERAL_PROXY_TIME_SERIES = "bcs_federal_proxy_time_series"
    BCS_FEDERAL_SUBSET_TIME_SERIES = "bcs_federal_subset_time_series"

    DATA_LINK_STRATEGY_CHOICES = (
        (BK_STANDARD_V2_TIME_SERIES, "标准单指标单表时序数据链路"),
        (BCS_FEDERAL_PROXY_TIME_SERIES, "联邦代理时序数据链路"),
        (BCS_FEDERAL_SUBSET_TIME_SERIES, "联邦子集时序数据链路"),
    )

    data_link_name = models.CharField(max_length=255, verbose_name="链路名称", primary_key=True)
    namespace = models.CharField(max_length=255, verbose_name="命名空间", default=settings.DEFAULT_VM_DATA_LINK_NAMESPACE)
    data_link_strategy = models.CharField(max_length=255, verbose_name="链路策略", choices=DATA_LINK_STRATEGY_CHOICES)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)
    storage_type = models.CharField(max_length=255, verbose_name="存储类型")

    class Meta:
        verbose_name = "数据链路"
        verbose_name_plural = verbose_name

    def compose_configs(self, *args, **kwargs):
        """
        生成对应套餐的链路完整配置
        """
        if self.data_link_strategy == "bk_standard_v2_time_series":
            return self.compose_standard_time_series_configs(*args, **kwargs)

    @classmethod
    def compose_standard_time_series_configs(cls, data_source, table_id, vm_cluster_name):
        """
        生成标准单指标单表时序数据链路配置
        @param data_source: 数据源
        @param table_id: 监控平台结果表ID（Metadata中的）
        @param vm_cluster_name: VM集群名称
        """
        logger.info(
            "compose_configs: data_link_name->[%s] ,bk_data_id->[%s],table_id->[%s],vm_cluster_name->[%s] "
            "start to compose configs",
            cls.data_link_name,
            data_source.bk_data_id,
            table_id,
            vm_cluster_name,
        )
        bkbase_data_name = utils.compose_bkdata_data_id_name(data_source.data_name)
        bkbase_vmrt_name = utils.compose_bkdata_table_id(table_id)
        logger.info(
            "compose_configs: data_link_name->[%s] start to use bkbase_data_name->[%s] bkbase_vmrt_name->[%s]to "
            "compose configs",
            cls.data_link_name,
            bkbase_data_name,
            bkbase_vmrt_name,
        )
        try:
            with transaction.atomic():
                # 渲染所需的资源配置
                vm_table_id_ins, _ = VMResultTableConfig.objects.get_or_create(
                    name=bkbase_vmrt_name, data_link_name=cls.data_link_name, namespace=cls.namespace
                )
                vm_storage_ins, _ = VMStorageBindingConfig.objects.get_or_create(
                    name=bkbase_vmrt_name,
                    vm_cluster_name=vm_cluster_name,
                    data_link_name=cls.data_link_name,
                    namespace=cls.namespace,
                )
                sinks = [
                    {
                        "kind": DataLinkKind.VMSTORAGEBINDING.value,
                        "name": bkbase_vmrt_name,
                        "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                    }
                ]
                data_bus_ins, _ = DataBusConfig(
                    name=bkbase_vmrt_name,
                    data_id_name=bkbase_data_name,
                    data_link_name=cls.data_link_name,
                    namespace=cls.namespace,
                )
        except Exception as e:
            logger.error("compose_configs: data_link_name->[%s] error->[%s],rollback!", cls.data_link_name, e)

        configs = [
            vm_table_id_ins.compose_config(),
            vm_storage_ins.compose_config(),
            data_bus_ins.compose_config(sinks),
        ]
        return configs

    @classmethod
    def apply_data_link(cls, *args, **kwargs):
        """
        组装配置并下发数据链路
        声明BkBaseResultTable -> 组装链路资源配置 -> 调用API申请
        """
        from metadata.models.bkdata.result_table import BkBaseResultTable

        try:
            with transaction.atomic():
                # NOTE:新链路下，data_link_name和bkbase_data_name一致
                BkBaseResultTable.objects.get_or_create(
                    data_link_name=cls.data_link_name,
                    bkbase_data_name=cls.data_link_name,
                    defaults={
                        "status": DataLinkResourceStatus.INITIALIZING.value,
                    },
                )
        except Exception as e:
            logger.error(
                "apply_data_link: data_link_name->[%s] create BkBaseResultTable error->[%s]", cls.data_link_name, e
            )

        configs = cls.compose_configs(*args, **kwargs)
        logger.info(
            "apply_data_link: data_link_name->[%s],strategy->[%s] try to use configs->[%s] to apply",
            cls.data_link_name,
            cls.data_link_strategy,
            configs,
        )
        response = api.bkdata.apply_data_link(configs)
        logger.info(
            "apply_data_link: data_link_name->[%s],strategy->[%s] response->[%s]",
            cls.data_link_name,
            cls.data_link_strategy,
            response,
        )

    @classmethod
    def sync_metadata(cls, data_source, table_id, storage_cluster_name):
        """
        同步元数据
        同步此前的计算平台链路记录，设置状态为OK
        """
        from metadata.models.bkdata.result_table import BkBaseResultTable

        bkbase_data_name = utils.compose_bkdata_data_id_name(data_source.data_name)
        bkbase_vmrt_name = utils.compose_bkdata_table_id(table_id)

        try:
            with transaction.atomic():
                BkBaseResultTable.objects.update_or_create(
                    data_link_name=cls.data_link_name,
                    bkbase_data_name=bkbase_data_name,
                    bkbase_vmrt_name=bkbase_vmrt_name,
                    bkbase_table_id=f"{settings.DEFAULT_BKDATA_BIZ_ID}_{bkbase_vmrt_name}",
                    monitor_table_id=table_id,
                    defaults={"storage_type": cls.storage_type, "storage_id": storage_cluster_name},
                )
        except Exception as e:
            logger.error(
                "sync_metadata: data_link_name->[%s],sync_metadata failed,error->{%s],rollback!", cls.data_link_name, e
            )
