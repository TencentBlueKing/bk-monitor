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
from typing import Dict, Optional

from django.conf import settings
from django.db.transaction import atomic

from core.drf_resource import api
from metadata import config
from metadata.models.data_link import utils
from metadata.models.data_link.constants import DataLinkKind, DataLinkResourceStatus
from metadata.models.data_link.resource import DataLinkResource, DataLinkResourceConfig

logger = logging.getLogger("metadata")


@atomic(config.DATABASE_CONNECTION_NAME)
def apply_data_id(data_name: str) -> bool:
    """下发 data_id 资源，并记录对应的资源及配置"""
    logger.info("apply data_id for data_name: %s", data_name)

    data_id_name = utils.get_bkdata_data_id_name(data_name)
    data_id_config = DataLinkResourceConfig.compose_data_id_config(data_id_name)
    if not data_id_config:
        return False
    # 调用接口创建 data_id 资源
    api.bkdata.apply_data_link({"config": [data_id_config]})
    # 记录资源及配置
    # NOTE: 注意新创建的数据源都是单指标单标, 包含 es
    DataLinkResource.objects.create(data_id_name=data_id_name)
    DataLinkResourceConfig.objects.create(
        kind=DataLinkKind.DATAID.value,
        name=data_id_name,
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        status=DataLinkResourceStatus.PENDING.value,
        content=data_id_config,
    )
    logger.info("apply data_id for data_name: %s success", data_name)
    return True


def get_data_id(data_name: str, namespace: Optional[str] = settings.DEFAULT_VM_DATA_LINK_NAMESPACE) -> Dict:
    """获取数据源对应的 data_id"""
    data_id_name = utils.get_bkdata_data_id_name(data_name)
    data_id_config = api.bkdata.get_data_link(
        kind=DataLinkKind.get_choice_value(DataLinkKind.DATAID.value), namespace=namespace, name=data_id_name
    )
    # 解析数据获取到数据源ID
    phase = data_id_config.get("status", {}).get("phase")
    # 如果状态不是处于正常的终态，则返回 None
    if phase == DataLinkResourceStatus.OK.value:
        data_id = int(data_id_config.get("metadata", {}).get("annotations", {}).get("dataId", 0))
        DataLinkResourceConfig.objects.filter(
            kind=DataLinkKind.DATAID.value, name=data_id_name, namespace=namespace
        ).update(status=phase or DataLinkResourceStatus.PENDING.value, value=data_id)
        return {"status": phase, "data_id": data_id}

    DataLinkResourceConfig.objects.filter(
        kind=DataLinkKind.DATAID.value, name=data_id_name, namespace=namespace
    ).update(status=phase or DataLinkResourceStatus.PENDING.value)
    return {"status": phase, "data_id": None}


def create_vm_data_link(
    table_id: str,
    data_name: str,
    vm_cluster_name: str,
    vm_cluster_id: Optional[int] = None,
    bcs_cluster_id: Optional[str] = None,
):
    # 获取数据源名称对应的资源，便于后续组装整个链路
    logger.info(
        "create vm data link for table_id: %s, data_name: %s, vm_cluster_name: %s", table_id, data_name, vm_cluster_name
    )

    data_id_name = utils.get_bkdata_data_id_name(data_name)
    name = utils.get_bkdata_table_id(table_id)
    # 渲染资源
    vm_table_id_config = DataLinkResourceConfig.compose_vm_table_id_config(name)
    vm_storage_binding_config = DataLinkResourceConfig.compose_vm_storage_binding(name, name, vm_cluster_name)
    vm_data_bus_config = DataLinkResourceConfig.compose_vm_data_bus_config(name, name, data_id_name)
    # 下发资源
    data = {"config": [vm_table_id_config, vm_storage_binding_config, vm_data_bus_config]}
    api.bkdata.apply_data_link(data)
    # 创建记录
    DataLinkResource.objects.update_or_create(
        data_id_name=data_id_name,
        vm_table_id_name=name,
        defaults={"vm_binding_name": name, "data_bus_name": name},
    )
    # 状态设置为正常
    records = [
        DataLinkResourceConfig(
            kind=DataLinkKind.RESULTTABLE.value,
            name=name,
            namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            status=DataLinkResourceStatus.OK.value,
            content=vm_table_id_config,
        ),
        DataLinkResourceConfig(
            kind=DataLinkKind.VMSTORAGEBINDING.value,
            name=name,
            namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            status=DataLinkResourceStatus.OK.value,
            content=vm_storage_binding_config,
        ),
        DataLinkResourceConfig(
            kind=DataLinkKind.DATABUS.value,
            name=name,
            namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            status=DataLinkResourceStatus.OK.value,
            content=vm_data_bus_config,
        ),
    ]
    DataLinkResourceConfig.objects.bulk_create(records)
    # 创建 vm 记录
    from metadata.models import AccessVMRecord, ClusterInfo

    if not vm_cluster_id:
        vm_cluster_id = ClusterInfo.objects.get(cluster_name=vm_cluster_name).cluster_id
    # NOTE: 不需要关心计算平台data_id, 这里设置为-1
    AccessVMRecord.objects.create(
        result_table_id=table_id,
        bcs_cluster_id=bcs_cluster_id,
        vm_cluster_id=vm_cluster_id,
        bk_base_data_id=-1,
        vm_result_table_id=f"{settings.DEFAULT_BKDATA_BIZ_ID}_{name}",
    )

    logger.info(
        "create vm data link for table_id: %s, data_name: %s, vm_cluster_name: %s success",
        table_id,
        data_name,
        vm_cluster_name,
    )
