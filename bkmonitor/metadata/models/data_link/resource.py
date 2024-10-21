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
import json
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional

from django.conf import settings
from django.db import models, transaction

from bkmonitor.utils.db import JsonField
from metadata.models import AccessVMRecord
from metadata.models.common import BaseModelWithTime
from metadata.models.data_link import constants, utils
from metadata.models.data_link.constants import DataLinkKind, DataLinkResourceStatus

logger = logging.getLogger("__name__")


class DataLinkStrategyChoices(Enum):
    BkStandardTimeSeriesDataLink = "bk_standard_time_series_data_link"
    FederalProxyClusterDataLink = "federal_proxy_cluster_data_link"


class DataLinkStrategy(ABC):
    """
    数据链路接入套餐抽象类
    """

    name = "base_data_link_strategy"

    @abstractmethod
    def create_configs(self, data_source, table_id, vm_cluster_name):
        pass

    @abstractmethod
    def create_or_update_metadata_records(
        self, data_source, table_id, vm_cluster_name, apply_data, bcs_cluster_id, vm_cluster_id
    ):
        pass

    def _update_or_create_data_link_resource(self, bkbase_data_name, vmrt_name):
        """
        创建/更新 DataLinkResource 记录
        """
        DataLinkResource.objects.update_or_create(
            data_id_name=bkbase_data_name,
            defaults={
                'vm_table_id_name': vmrt_name,
                'vm_binding_name': vmrt_name,
                'data_bus_name': vmrt_name
                if self.name == DataLinkStrategyChoices.BkStandardTimeSeriesDataLink.value
                else None,
            },
        )

    def _bulk_create_or_update_config_records(self, vmrt_name, apply_data, kinds_status_map):
        records = [
            DataLinkResourceConfig(
                kind=kind,
                name=vmrt_name,
                namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                status=status,
                content=apply_data.get(config_key),
            )
            for kind, (status, config_key) in kinds_status_map.items()
        ]
        DataLinkResourceConfig.objects.bulk_create(records)

    def _create_or_update_access_vm_record(
        self, table_id, bcs_cluster_id, vm_cluster_id, data_source, bkbase_data_name, vmrt_name
    ):
        AccessVMRecord.objects.update_or_create(
            result_table_id=table_id,
            defaults={
                "bcs_cluster_id": bcs_cluster_id,
                "vm_cluster_id": vm_cluster_id,
                "bk_base_data_id": data_source.bk_data_id,
                "bk_base_data_name": bkbase_data_name,
                "vm_result_table_id": f"{settings.DEFAULT_BKDATA_BIZ_ID}_{vmrt_name}",
            },
        )


class BkStandardTimeSeriesDataLink(DataLinkStrategy):
    """
    标准单指标单表链路套餐
    需要Kind：DataBus、VmTableId、VmStorageBinding等资源
    """

    name = "bk_standard_time_series_data_link"

    def create_configs(self, data_source, table_id, vm_cluster_name):
        """
        生成单指标单表指标链路的接入配置
        """
        # 1. 根据Metadata的data_name，组装计算平台的data_name
        data_name = data_source.data_name
        bkbase_data_name = utils.get_bkdata_data_id_name(data_name)

        # 2. 根据Metadata的rt.table_id，组装计算平台的vmrt_name
        vmrt_name = utils.get_bkdata_table_id(table_id)

        logger.info(
            "BkStandardTimeSeriesDataLink: will use bkbase_data_name->[%s],vmrt_name->[%s] to create configs",
            bkbase_data_name,
            vmrt_name,
        )
        # 3. 渲染各个资源
        vm_table_id_config = DataLinkResourceConfig.compose_vm_table_id_config(vmrt_name)
        vm_storage_binding_config = DataLinkResourceConfig.compose_vm_storage_binding(
            vmrt_name, vmrt_name, vm_cluster_name
        )
        sinks = DataLinkResourceConfig.compose_vm_data_bus_sinks(vmrt_name)
        vm_data_bus_config = DataLinkResourceConfig.compose_vm_data_bus_config(
            vmrt_name, vmrt_name, bkbase_data_name, sinks
        )

        # 4. 组装下发的配置文件，并返回
        configs = [vm_table_id_config, vm_storage_binding_config, vm_data_bus_config]
        apply_data = {"config": configs}
        return apply_data

    @transaction.atomic
    def create_or_update_metadata_records(
        self, data_source, table_id, vm_cluster_name, apply_data, bcs_cluster_id, vm_cluster_id
    ):
        """
        创建/更新 Metadata中的链路记录数据
        """
        # 1. 根据Metadata的data_name，组装计算平台的data_name
        bkbase_data_name = utils.get_bkdata_data_id_name(data_source.data_name)

        # 2. 根据Metadata的rt.table_id，组装计算平台的vmrt_name
        vmrt_name = utils.get_bkdata_table_id(table_id)

        # 3. 创建监控平台自身的链路记录 AccessVMRecord - DataLinkResource -> DataLinkResourceConfig(各类型资源）
        self._update_or_create_data_link_resource(bkbase_data_name, vmrt_name)
        kinds_status_map = {
            DataLinkKind.RESULTTABLE.value: (DataLinkResourceStatus.CREATING.value, "vm_table_id_config"),
            DataLinkKind.VMSTORAGEBINDING.value: (DataLinkResourceStatus.CREATING.value, "vm_storage_binding_config"),
            DataLinkKind.DATABUS.value: (DataLinkResourceStatus.CREATING.value, "vm_data_bus_config"),
        }
        self._bulk_create_or_update_config_records(vmrt_name, apply_data, kinds_status_map)
        self._create_or_update_access_vm_record(
            table_id, bcs_cluster_id, vm_cluster_id, data_source, bkbase_data_name, vmrt_name
        )

        logger.info("BkStandardTimeSeriesDataLink: create or update metadata records successfully")
        return True


class FederalProxyClusterDataLink(DataLinkStrategy):
    """
    联邦集群代理集群套餐
    需要Kind：VmTableId、VmStorageBinding等资源
    """

    name = "federal_proxy_cluster_data_link"

    def create_configs(self, data_source, table_id, vm_cluster_name):
        """
        生成联邦集群代理集群的接入配置
        """
        # 1. 根据Metadata的rt.table_id，组装计算平台的vmrt_name
        vmrt_name = utils.get_bkdata_table_id(table_id)
        logger.info("FederalProxyClusterDataLink: will use vmrt_name->[%s] to create configs", vmrt_name)
        # 2. 渲染各个资源
        vm_table_id_config = DataLinkResourceConfig.compose_vm_table_id_config(vmrt_name)
        vm_storage_binding_config = DataLinkResourceConfig.compose_vm_storage_binding(
            vmrt_name, vmrt_name, vm_cluster_name
        )

        # 3. 组装下发的配置文件，并返回
        configs = [vm_table_id_config, vm_storage_binding_config]
        apply_data = {"config": configs}
        return apply_data

    def create_or_update_metadata_records(
        self, data_source, table_id, vm_cluster_name, apply_data, bcs_cluster_id, vm_cluster_id
    ):
        """
        创建/更新 Metadata中的链路记录数据
        """
        # 1. 根据Metadata的data_name，组装计算平台的data_name
        bkbase_data_name = utils.get_bkdata_data_id_name(data_source.data_name)

        # 2. 根据Metadata的rt.table_id，组装计算平台的vmrt_name
        vmrt_name = utils.get_bkdata_table_id(table_id)

        # 3. 创建监控平台自身的链路记录 AccessVMRecord - DataLinkResource -> DataLinkResourceConfig(各类型资源）
        self._update_or_create_data_link_resource(bkbase_data_name, vmrt_name)

        kinds_status_map = {
            DataLinkKind.RESULTTABLE.value: (DataLinkResourceStatus.CREATING.value, "vm_table_id_config"),
            DataLinkKind.VMSTORAGEBINDING.value: (DataLinkResourceStatus.CREATING.value, "vm_storage_binding_config"),
        }
        self._bulk_create_or_update_config_records(vmrt_name, apply_data, kinds_status_map)

        self._create_or_update_access_vm_record(
            table_id, bcs_cluster_id, vm_cluster_id, data_source, bkbase_data_name, vmrt_name
        )

        logger.info("FederalProxyClusterDataLink: create or update metadata records successfully")


class DataLinkResource(BaseModelWithTime):
    """
    一条数据链路资源
    """

    data_id_name = models.CharField("数据源名称", max_length=64, null=True, blank=True)
    vm_table_id_name = models.CharField("结果表名称", max_length=64, null=True, blank=True)
    vm_binding_name = models.CharField("vm 存储绑定名称", max_length=64, null=True, blank=True)
    data_bus_name = models.CharField("数据总线名称", max_length=64, null=True, blank=True)
    conditional_sink_name = models.CharField("条件节点名称", max_length=64, null=True, blank=True)

    class Meta:
        verbose_name = "数据链路资源"
        verbose_name_plural = "数据链路资源表"


class DataLinkResourceConfig(BaseModelWithTime):
    """
    数据链路资源配置
    kind+name+namespace构成过滤条件
    """

    kind = models.CharField("资源类型", max_length=32)
    name = models.CharField("资源名称", max_length=64)
    namespace = models.CharField("命名空间", max_length=64, default=settings.DEFAULT_VM_DATA_LINK_NAMESPACE)
    value = JsonField("记录对应的资源信息", null=True, blank=True, help_text="比如针对dataid资源记录申请到的数据源ID")
    status = models.CharField("状态", max_length=32, default="ok")
    content = JsonField("资源配置", null=True, blank=True)

    class Meta:
        verbose_name = "数据源资源配置"
        verbose_name_plural = "数据源资源配置表"

    @classmethod
    def compose_data_id_config(cls, name: str) -> Dict:
        """数据源下发计算平台的资源配置"""
        tpl = """
        {
            "kind": "DataId",
            "metadata": {
                "name": "{{name}}",
                "namespace": "{{namespace}}"
            },
            "spec": {
                "alias": "{{name}}",
                "bizId": {{bk_biz_id}},
                "description": "{{name}}",
                "maintainers": {{maintainers}}
            }
        }
        """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        return utils.compose_config(
            tpl=tpl,
            render_params={
                "name": name,
                "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                "bk_biz_id": settings.DEFAULT_BKDATA_BIZ_ID,
                "maintainers": json.dumps(maintainer),
            },
            err_msg_prefix="compose data_id config",
        )

    @classmethod
    def compose_vm_table_id_config(cls, name: str, data_type: Optional[str] = "metric") -> Dict:
        """组装数据源结果表配置"""
        tpl = """
        {
            "kind": "ResultTable",
            "metadata": {
                "name": "{{name}}",
                "namespace": "{{namespace}}"
            },
            "spec": {
                "alias": "{{name}}",
                "bizId": {{bk_biz_id}},
                "dataType": "{{data_type}}",
                "description": "{{name}}",
                "maintainers": {{maintainers}}
            }
        }
        """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        return utils.compose_config(
            tpl=tpl,
            render_params={
                "name": name,
                "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                "bk_biz_id": settings.DEFAULT_BKDATA_BIZ_ID,
                "data_type": data_type,
                "maintainers": json.dumps(maintainer),
            },
            err_msg_prefix="compose bkdata table_id config",
        )

    @classmethod
    def compose_vm_storage_binding(
        cls,
        name: str,
        rt_name: str,
        vm_name: Optional[str] = None,
        space_type: Optional[str] = None,
        space_id: Optional[str] = None,
    ) -> Dict:
        """组装数据源原始数据配置"""
        tpl = """
        {
            "kind": "VmStorageBinding",
            "metadata": {
                "name": "{{name}}",
                "namespace": "{{namespace}}"
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "{{rt_name}}",
                    "namespace": "{{namespace}}"
                },
                "maintainers": {{maintainers}},
                "storage": {
                    "kind": "VmStorage",
                    "name": "{{vm_name}}",
                    "namespace": "{{namespace}}"
                }
            }
        }
        """
        from metadata.models.vm.utils import get_vm_cluster_id_name

        if not vm_name:
            vm_cluster = get_vm_cluster_id_name(space_type=space_type, space_id=space_id)
            vm_name = vm_cluster.get("cluster_name")
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        return utils.compose_config(
            tpl=tpl,
            render_params={
                "name": name,
                "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                "rt_name": rt_name,
                "vm_name": vm_name,
                "maintainers": json.dumps(maintainer),
            },
            err_msg_prefix="compose vm storage binding config",
        )

    @classmethod
    def compose_conditional_sink_config(cls, name: str, conditions: List) -> Dict:
        """组装条件处理配置"""
        tpl = """
        {
            "kind": "ConditionalSink",
            "metadata": {
                "namespace": "{{namespace}}",
                "name": "{{name}}"
            },
            "spec": {
                "conditions": {{conditions}}
            }
        }
        """
        return utils.compose_config(
            tpl=tpl,
            render_params={
                "name": name,
                "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                "conditions": json.dumps(conditions),
            },
            err_msg_prefix="compose vm conditional sink config",
        )

    @classmethod
    def compose_vm_data_bus_sinks(cls, name: str) -> List:
        """组装数据总线配置"""
        sinks = [
            {
                "kind": DataLinkKind.VMSTORAGEBINDING.value,
                "name": name,
                "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            }
        ]
        return sinks

    @classmethod
    def compose_vm_data_bus_config(
        cls,
        name: str,
        sink_name: str,
        data_id_name: str,
        sinks: List,
        transform_kind: Optional[str] = constants.DEFAULT_METRIC_TRANSFORMER_KIND,
        transform_name: Optional[str] = constants.DEFAULT_METRIC_TRANSFORMER,
        transform_format: Optional[str] = constants.DEFAULT_METRIC_TRANSFORMER_FORMAT,
    ) -> Dict:
        """通过data_id获取资源配置"""
        tpl = """
        {
            "kind": "Databus",
            "metadata": {
                "name": "{{name}}",
                "namespace": "{{namespace}}"
            },
            "spec": {
                "maintainers": {{maintainers}},
                "sinks": {{sinks}},
                "sources": [
                    {
                        "kind": "DataId",
                        "name": "{{data_id_name}}",
                        "namespace": "{{namespace}}"
                    }
                ],
                "transforms": [
                    {
                        "kind": "{{transform_kind}}",
                        "name": "{{transform_name}}",
                        "format": "{{transform_format}}"
                    }
                ]
            }
        }
        """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        return utils.compose_config(
            tpl=tpl,
            render_params={
                "name": name,
                "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                "sinks": json.dumps(sinks),
                "sink_name": sink_name,
                "data_id_name": data_id_name,
                "transform_kind": transform_kind,
                "transform_name": transform_name,
                "transform_format": transform_format,
                "maintainers": json.dumps(maintainer),
            },
            err_msg_prefix="compose vm databus config",
        )
