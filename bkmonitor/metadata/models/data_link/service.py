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
from metadata.models.bcs import BcsFederalClusterInfo
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


@atomic(config.DATABASE_CONNECTION_NAME)
def create_vm_data_link(
    table_id: str,
    data_name: str,
    vm_cluster_name: str,
    vm_cluster_id: Optional[int] = None,
    bcs_cluster_id: Optional[str] = None,
):
    # 获取数据源名称对应的资源，便于后续组装整个链路
    logger.info(
        "create_vm_data_link: create vm data link for table_id: %s, data_name: %s, vm_cluster_name: %s",
        table_id,
        data_name,
        vm_cluster_name,
    )

    data_id_name = utils.get_bkdata_data_id_name(data_name)
    name = utils.get_bkdata_table_id(table_id)
    # 渲染资源
    vm_table_id_config = DataLinkResourceConfig.compose_vm_table_id_config(name)
    vm_storage_binding_config = DataLinkResourceConfig.compose_vm_storage_binding(name, name, vm_cluster_name)
    sinks = [
        {
            "kind": DataLinkKind.VMSTORAGEBINDING.value,
            "name": name,
            "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        }
    ]
    vm_data_bus_config = DataLinkResourceConfig.compose_vm_data_bus_config(name, name, data_id_name, sinks)

    # 是否是联邦集群的代理集群，若是，则无需创建DATABUS
    is_fed_cluster = bcs_cluster_id and BcsFederalClusterInfo.objects.filter(fed_cluster_id=bcs_cluster_id).exists()
    configs = [vm_table_id_config, vm_storage_binding_config]

    if not is_fed_cluster:
        configs.append(vm_data_bus_config)

    logger.info("create_vm_data_link: apply configs: %s,is_fed_cluster: %s", configs, is_fed_cluster)

    # 调用计算平台接口，申请V4链路
    api.bkdata.apply_data_link({"config": configs})

    logger.info("create_vm_data_link: apply success")

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
    ]

    # 只有非联邦集群的代理集群时，才需要DATABUS
    if not is_fed_cluster:
        records.append(
            DataLinkResourceConfig(
                kind=DataLinkKind.DATABUS.value,
                name=name,
                namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                status=DataLinkResourceStatus.OK.value,
                content=vm_data_bus_config,
            ),
        )

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
        "create_vm_data_link: create vm data link for table_id: %s, data_name: %s, vm_cluster_name: %s success",
        table_id,
        data_name,
        vm_cluster_name,
    )


@atomic(config.DATABASE_CONNECTION_NAME)
def create_fed_vm_data_link(
    table_id: str,
    data_name: str,
    vm_cluster_name: str,
    vm_cluster_id: Optional[int] = None,
    bcs_cluster_id: Optional[str] = None,
):
    from metadata.models import AccessVMRecord, ClusterInfo

    # 如果不是集群，则直接忽略
    if not bcs_cluster_id:
        return
    # 判断是否为联邦集群的子集群，如果不是，则直接返回
    objs = BcsFederalClusterInfo.objects.filter(sub_cluster_id=bcs_cluster_id)
    if not (objs.exists() and utils.is_k8s_metric_data_id(data_name)):
        logger.info("not federal sub cluster or not builtin datasource")
        return

    # 获取数据源名称对应的资源，便于后续组装整个链路
    logger.info(
        "create_fed_vm_data_link for table_id: %s, data_name: %s, vm_cluster_name: %s",
        table_id,
        data_name,
        vm_cluster_name,
    )
    # NOTE: 这里需要兼容 data_id为V3链路，此前已经接入过VM的情形
    data_id_name = utils.get_bkdata_data_id_name(data_name)
    try:
        api.bkdata.get_data_link(
            kind=DataLinkKind.get_choice_value(DataLinkKind.DATAID.value),
            namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            name=data_id_name,
        )
    except Exception:  # pylint: disable=broad-except
        logger.info(
            "create_fed_vm_data_link: data_id_name->{} does not exist in bkbase ,now try to use v3 data_id_name".format(
                data_id_name
            )
        )
        vm_record = AccessVMRecord.objects.filter(result_table_id=table_id)
        if not vm_record:
            logger.error("create_fed_vm_data_link: data_id_name does not exists in anywhere!")
            return
        data_id_name = utils.get_bkdata_data_id_name_v3(vm_record.first().vm_result_table_id)

    logger.info("create_fed_vm_data_link: data_id_name->%s", data_id_name)

    # 满足计算平台 40 长度的限制
    name = f"{utils.get_bkdata_table_id(table_id)}_fed"
    # 针对联邦做处理
    # 下发资源
    config_list, data_links, conditions = [], [], []
    for obj in objs:
        builtin_name = utils.get_bkdata_table_id(obj.fed_builtin_metric_table_id)
        match_labels = [{"name": "namespace", "value": ns} for ns in obj.fed_namespaces]
        relabels = [{"name": "bcs_cluster_id", "value": obj.fed_cluster_id}]
        sinks = [
            {"kind": "VmStorageBinding", "name": builtin_name, "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE}
        ]
        conditions.append({"match_labels": match_labels, "relabels": relabels, "sinks": sinks})
        logger.info(
            "composed datalink config,name->{},builtin_name->{},match_labels->{},relabels->{},sinks->{}".format(
                name, builtin_name, match_labels, relabels, sinks
            )
        )
        # 添加rt及和存储的关联
        rt_config = DataLinkResourceConfig.compose_vm_table_id_config(builtin_name)
        vm_storage_binding_config = DataLinkResourceConfig.compose_vm_storage_binding(
            builtin_name, builtin_name, vm_cluster_name
        )
        config_list.extend([rt_config, vm_storage_binding_config])
        data_links.append(
            {
                "raw_rt_id": obj.fed_builtin_metric_table_id,
                "rt_name": builtin_name,
                "rt_config": rt_config,
                "vm_storage_binding_name": builtin_name,
                "vm_storage_binding_config": vm_storage_binding_config,
            }
        )
    vm_conditional_sink_config = DataLinkResourceConfig.compose_conditional_sink_config(name, conditions)
    conditional_sink = [
        {
            "kind": DataLinkKind.CONDITIONALSINK.value,
            "name": name,
            "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        },
    ]
    vm_data_bus_config = DataLinkResourceConfig.compose_vm_data_bus_config(name, name, data_id_name, conditional_sink)
    config_list.extend([vm_conditional_sink_config, vm_data_bus_config])
    # 下发资源
    data = {"config": config_list}
    try:
        logger.info("create_fed_vm_data_link start to apply data link")
        api.bkdata.apply_data_link(data)
    except Exception as e:
        logger.error("create_fed_vm_data_link apply data link error: %s", e)
        return
    # 根据存储创建多条记录
    records, vm_records = [], []
    # 如果 vm 集群ID不存在，则通过集群名称获取

    if not vm_cluster_id:
        vm_cluster_id = ClusterInfo.objects.get(cluster_name=vm_cluster_name).cluster_id

    for dl in data_links:
        DataLinkResource.objects.update_or_create(
            data_id_name=data_id_name,
            vm_table_id_name=dl["rt_name"],
            vm_binding_name=dl["vm_storage_binding_name"],
            defaults={"data_bus_name": name, "sink_name": name},
        )
        records.append(
            DataLinkResourceConfig(
                kind=DataLinkKind.RESULTTABLE.value,
                name=name,
                namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                status=DataLinkResourceStatus.OK.value,
                content=dl["rt_config"],
            )
        )
        records.append(
            DataLinkResourceConfig(
                kind=DataLinkKind.VMSTORAGEBINDING.value,
                name=name,
                namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                status=DataLinkResourceStatus.OK.value,
                content=dl["vm_storage_binding_config"],
            )
        )
        vm_records.append(
            AccessVMRecord(
                result_table_id=dl["raw_rt_id"],
                bcs_cluster_id=bcs_cluster_id,
                vm_cluster_id=vm_cluster_id,
                bk_base_data_id=-1,
                vm_result_table_id=f"{settings.DEFAULT_BKDATA_BIZ_ID}_{dl['rt_name']}",
            )
        )

    # 状态设置为正常
    records.extend(
        [
            DataLinkResourceConfig(
                kind=DataLinkKind.DATABUS.value,
                name=name,
                namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                status=DataLinkResourceStatus.OK.value,
                content=vm_data_bus_config,
            ),
            DataLinkResourceConfig(
                kind=DataLinkKind.CONDITIONALSINK.value,
                name=name,
                namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                status=DataLinkResourceStatus.OK.value,
                content=vm_conditional_sink_config,
            ),
        ]
    )
    DataLinkResourceConfig.objects.bulk_create(records)
    # 创建 vm 记录
    from metadata.models import AccessVMRecord

    AccessVMRecord.objects.bulk_create(vm_records)

    logger.info(
        "create_fed_vm_data_link for table_id: %s, data_name: %s, vm_cluster_name: %s success",
        table_id,
        data_name,
        vm_cluster_name,
    )
