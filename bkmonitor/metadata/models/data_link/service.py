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
from typing import Dict, Optional, Type

from django.conf import settings
from django.db.transaction import atomic

from core.drf_resource import api
from metadata import config
from metadata.models import AccessVMRecord, ClusterInfo, DataSource
from metadata.models.bcs import BcsFederalClusterInfo
from metadata.models.data_link import utils
from metadata.models.data_link.constants import DataLinkKind, DataLinkResourceStatus
from metadata.models.data_link.resource import (
    DataLinkResource,
    DataLinkResourceConfig,
    DataLinkStrategy,
    FederalSubClusterDataLink,
)

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


def get_bkbase_v4_datalink_status(
    name: str, kind: str, namespace: Optional[str] = settings.DEFAULT_VM_DATA_LINK_NAMESPACE
) -> Dict:
    """
    根据name和kind，获取在计算平台实际的资源状态配置
    """
    # dataids resulttables vmstoragebindings databuses conditionalsinks
    data_link_config = api.bkdata.get_data_link(kind=kind, namespace=namespace, name=name)
    return data_link_config


@atomic(config.DATABASE_CONNECTION_NAME)
def create_data_link(
    table_id: str,
    storage_name: str,
    strategy_cls: Type[DataLinkStrategy],
    storage_type: str = ClusterInfo.TYPE_VM,
    data_source: DataSource = None,
    bcs_cluster_id: Optional[str] = None,
):
    """
    接入计算平台链路，根据不同的套餐构建接入配置并完成接入
    """

    # 0. 实例化策略
    strategy = strategy_cls()
    logger.info(
        "create_data_link: start to create data link for table_id->[%s], storage_name->[%s],storage_type->[%s],"
        "bk_data_id->[%s],strategy->[%s]",
        table_id,
        storage_name,
        storage_type,
        data_source.bk_data_id,
        strategy.name,
    )

    # 1. 创建配置
    apply_configs = strategy.create_configs(data_source, table_id, storage_name)
    logger.info("create_data_link: will use configs->[%s] to apply data link", apply_configs)

    # 2. 调用计算平台API，创建数据链路
    response = api.bkdata.apply_data_link(apply_configs)
    logger.info("create_data_link: apply data link response->[%s]", response)

    # NOTE: 为了和历史的InfluxDBClusterInfo区分开，现改用StorageName + StorageType的方式，获取对应存储集群
    storage_id = ClusterInfo.objects.get(cluster_name=storage_name, storage_type=storage_type).cluster_id
    # 3. 创建&同步监控平台自身的DB记录
    strategy.create_or_update_metadata_records(
        data_source, table_id, storage_name, apply_configs, bcs_cluster_id, storage_id
    )

    logger.info(
        "create_data_link: strategy->[%s],table_id->[%s],bk_data_id->[%s].",
        strategy.name,
        table_id,
        data_source.bk_data_id,
    )


@atomic(config.DATABASE_CONNECTION_NAME)
def create_vm_data_link(
    table_id: str,
    data_source: DataSource,
    vm_cluster_name: str,
    vm_cluster_id: Optional[int] = None,
    bcs_cluster_id: Optional[str] = None,
):
    """
    接入计算平台VM，创建V4链路
    @param table_id: 数据源对应的结果表ID
    @param data_source: 数据源
    @param vm_cluster_name: VM集群名称
    @param vm_cluster_id: VM集群ID
    @param bcs_cluster_id: BCS集群ID
    """
    # 0. 首先取到该数据源在监控平台自身的数据源名称
    data_name = data_source.data_name
    logger.info(
        "create_vm_data_link: create vm data link for table_id: %s, data_id: %s, data_name: %s,vm_cluster_name: %s",
        table_id,
        data_source.bk_data_id,
        data_name,
        vm_cluster_name,
    )

    # 1. 拼接接入V4链路需要的信息[vm_table_id_config，vm_storage_binding_config,vm_data_bus_config]
    # 1.1 这里的data_id_name即根据计算平台规则拼接出的计算平台对应的数据名称（唯一标识），用于DataBus等信息的组装
    data_id_name = utils.get_bkdata_data_id_name(data_name)
    vmrt_name = utils.get_bkdata_table_id(table_id)
    # 1.2 渲染资源
    vm_table_id_config = DataLinkResourceConfig.compose_vm_table_id_config(vmrt_name)
    vm_storage_binding_config = DataLinkResourceConfig.compose_vm_storage_binding(vmrt_name, vmrt_name, vm_cluster_name)
    sinks = [
        {
            "kind": DataLinkKind.VMSTORAGEBINDING.value,
            "name": vmrt_name,
            "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        }
    ]
    # 1.3 渲染DATABUS配置
    vm_data_bus_config = DataLinkResourceConfig.compose_vm_data_bus_config(vmrt_name, vmrt_name, data_id_name, sinks)

    # 1.4 是否是联邦集群的代理集群，若是，则无需创建DATABUS
    is_fed_cluster = bcs_cluster_id and BcsFederalClusterInfo.objects.filter(fed_cluster_id=bcs_cluster_id).exists()
    configs = [vm_table_id_config, vm_storage_binding_config]
    if not is_fed_cluster:
        configs.append(vm_data_bus_config)

    logger.info("create_vm_data_link: apply configs: %s,is_fed_cluster: %s", configs, is_fed_cluster)

    # 2. 调用计算平台接口，申请V4链路
    api.bkdata.apply_data_link({"config": configs})

    logger.info("create_vm_data_link: apply success")

    # 3. 创建监控平台自身的链路记录 AccessVMRecord - DataLinkResource -> DataLinkResourceConfig(各类型资源）
    DataLinkResource.objects.update_or_create(
        data_id_name=data_id_name,
        vm_table_id_name=vmrt_name,
        defaults={"vm_binding_name": vmrt_name, "data_bus_name": vmrt_name},
    )
    # 状态设置为正常
    records = [
        DataLinkResourceConfig(
            kind=DataLinkKind.RESULTTABLE.value,
            name=vmrt_name,
            namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            status=DataLinkResourceStatus.OK.value,
            content=vm_table_id_config,
        ),
        DataLinkResourceConfig(
            kind=DataLinkKind.VMSTORAGEBINDING.value,
            name=vmrt_name,
            namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            status=DataLinkResourceStatus.OK.value,
            content=vm_storage_binding_config,
        ),
    ]

    # 4. 只有非联邦集群的代理集群时，才需要DATABUS
    if not is_fed_cluster:
        records.append(
            DataLinkResourceConfig(
                kind=DataLinkKind.DATABUS.value,
                name=vmrt_name,
                namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                status=DataLinkResourceStatus.OK.value,
                content=vm_data_bus_config,
            ),
        )

    DataLinkResourceConfig.objects.bulk_create(records)
    # 5. 创建 vm 记录
    from metadata.models import AccessVMRecord, ClusterInfo

    if not vm_cluster_id:
        vm_cluster_id = ClusterInfo.objects.get(cluster_name=vm_cluster_name).cluster_id
    # NOTE：这里的接入VM记录，现统一将对应的计算平台数据ID和数据名称存储下来，方便后续使用
    AccessVMRecord.objects.create(
        result_table_id=table_id,
        bcs_cluster_id=bcs_cluster_id,
        vm_cluster_id=vm_cluster_id,
        bk_base_data_id=data_source.bk_data_id,  # 计算平台数据ID，纯V4链路的数据ID本身就来源于计算平台
        bk_base_data_name=data_id_name,  # 计算平台数据名称，根据对应协议拼接而成
        vm_result_table_id=f"{settings.DEFAULT_BKDATA_BIZ_ID}_{vmrt_name}",
    )

    # 6. 成功，打印日志结束
    logger.info(
        "create_vm_data_link: create vm data link for table_id: %s, data_name: %s, vm_cluster_name: %s success",
        table_id,
        data_name,
        vm_cluster_name,
    )


@atomic(config.DATABASE_CONNECTION_NAME)
def create_fed_vm_data_link_v2(
    table_id: str,
    data_source: DataSource,
    storage_name: str,
    storage_type: str = ClusterInfo.TYPE_VM,
    bcs_cluster_id: Optional[str] = None,
):
    objs = BcsFederalClusterInfo.objects.filter(sub_cluster_id=bcs_cluster_id)
    if not objs.exists():
        logger.info(
            "create_fed_vm_data_link： data_id->[%s] ,cluster_id->[%s] is not federal sub cluster or not "
            "builtin datasource",
            data_source.bk_data_id,
            bcs_cluster_id,
        )
        return

    bkbase_data_name = utils.get_bkdata_data_id_name(data_source.data_name)
    bkbase_data_id = data_source.bk_data_id

    # 兼容此前已经接入过VM的情形，即独立集群改造为联邦集群子集群
    vm_record = AccessVMRecord.objects.filter(result_table_id=table_id)
    if vm_record.exists():
        bkbase_data_name = vm_record.first().bk_base_data_name
        bkbase_data_id = vm_record.first().bk_base_data_id

    logger.info(
        "create_fed_vm_data_link: will use bkbase_data_name->[%s],bkbase_data_id->[%s].bk_data_id->[%s]",
        bkbase_data_name,
        bkbase_data_id,
        data_source.bk_data_id,
    )

    strategy_cls = FederalSubClusterDataLink()
    apply_data = strategy_cls.create_sub_clusters_federal_data_link_configs(
        table_id=table_id,
        federal_objs=objs,
        bkbase_data_name=bkbase_data_name,
    )

    response = api.bkdata.apply_data_link(apply_data)
    logger.info("create_fed_vm_data_link: response->[%s]", response)

    storage_id = ClusterInfo.objects.get(cluster_name=storage_name, storage_type=storage_type).cluster_id
    strategy_cls.create_or_update_metadata_records_for_federal(
        bcs_cluster_id=bcs_cluster_id,
        vm_cluster_id=storage_id,
        bkbase_data_id=bkbase_data_id,
        bkbase_data_name=bkbase_data_name,
    )


@atomic(config.DATABASE_CONNECTION_NAME)
def create_fed_vm_data_link(
    table_id: str,
    data_source: DataSource,
    vm_cluster_name: str,
    vm_cluster_id: Optional[int] = None,
    bcs_cluster_id: Optional[str] = None,
):
    """
    针对联邦集群，创建联邦子集群->联邦代理集群的汇聚（复制）链路，只有联邦集群子集群需要创建
    @param table_id: 数据源对应的结果表ID
    @param data_source: 数据源
    @param vm_cluster_name: VM集群名称
    @param vm_cluster_id: VM集群ID
    @param bcs_cluster_id: BCS集群ID
    """
    from metadata import models
    from metadata.models import AccessVMRecord, ClusterInfo

    # 0. 首先取到该数据源在监控平台自身的数据源名称
    data_name = data_source.data_name

    # 0.1 如果不是集群相关的data_id，则直接返回
    if not bcs_cluster_id:
        logger.info(
            "create_fed_vm_data_link： data_id->[%s] is not belong to any cluster, ignore it ", data_source.bk_data_id
        )
        return

    # 1. 判断是否为联邦集群的子集群，如果不是，则直接返回
    objs = BcsFederalClusterInfo.objects.filter(sub_cluster_id=bcs_cluster_id)
    if not (objs.exists() and utils.is_k8s_metric_data_id(data_name)):
        logger.info(
            "create_fed_vm_data_link： data_id->[%s] ,cluster_id->[%s] is not federal sub cluster or not "
            "builtin datasource",
            data_source.bk_data_id,
            bcs_cluster_id,
        )
        return

    # 2. 获取数据源名称对应的资源，便于后续组装整个链路
    logger.info(
        "create_fed_vm_data_link for table_id->[%s], bk_data_id->[%s],data_name->[%s], vm_cluster_name->[%s]",
        table_id,
        data_source.bk_data_id,
        data_name,
        vm_cluster_name,
    )

    # 2.1 NOTE: 这里需要兼容此前已经接入过VM的情形,接入VM时的data_id_name统一从AccessVMRecord中获取
    vm_record = models.AccessVMRecord.objects.filter(result_table_id=table_id)
    # 2.1.1 如果存在对应的VM接入记录，说明属于 原先接入过监控的独立集群改造为联邦集群子集群（V3），直接使用其原先的链路信息(计算平台数据名称&ID）
    if vm_record.exists():
        data_id_name = vm_record.first().bk_base_data_name
        bkbase_data_id = vm_record.first().bk_base_data_id
        logger.info(
            "create_fed_vm_data_link: vm_record exists,will use data_id_name->[%s],bkbase_data_id->["
            "%s].bk_data_id->[%s]",
            data_id_name,
            bkbase_data_id,
            data_source.bk_data_id,
        )
    else:
        # 2.1.2 如果不存在对应的VM接入记录，说明属于新创建的联邦集群子集群，按照V4标准拼接信息
        data_id_name = utils.get_bkdata_data_id_name(data_name)
        bkbase_data_id = data_source.bk_data_id
        logger.info(
            "create_fed_vm_data_link: vm_record not exists,will use data_id_name->[%s],bkbase_data_id->[%s],"
            "bk_data_id->[%s]",
            data_id_name,
            bkbase_data_id,
            data_source.bk_data_id,
        )

    # if data_id_name == "":
    #     data_id_name = utils.get_bkdata_data_id_name(data_name)

    logger.info(
        "create_fed_vm_data_link: data_id_name->[%s],bkbase_data_id->[%s].bk_data_id->[%s]",
        data_id_name,
        bkbase_data_id,
        data_source.bk_data_id,
    )

    # 3. 渲染创建联邦汇聚链路的资源信息 [vm_conditional_sink_config, vm_data_bus_config]
    # 满足计算平台 40 长度的限制
    vmrt_name = f"{utils.get_bkdata_table_id(table_id)}_fed"
    # 针对联邦做处理
    config_list, data_links, conditions = [], [], []
    for obj in objs:
        builtin_name = utils.get_bkdata_table_id(obj.fed_builtin_metric_table_id)  # 该联邦拓扑的代理集群的内置（K8S指标）指标RT
        if not obj.fed_namespaces:
            logger.info(
                "create_fed_vm_data_link: fed_sub_record->[%s] has no fed_namespaces, ignore it", obj.fed_sub_record
            )
        match_labels = [{"name": "namespace", "value": ns} for ns in obj.fed_namespaces]  # 该子集群被联邦纳管的命名空间列表
        relabels = [{"name": "bcs_cluster_id", "value": obj.fed_cluster_id}]
        sinks = [
            {"kind": "VmStorageBinding", "name": builtin_name, "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE}
        ]
        conditions.append({"match_labels": match_labels, "relabels": relabels, "sinks": sinks})
        # conditions = DataLinkResourceConfig.compose(conditions(fed_sub_record))
        logger.info(
            "composed datalink config,name->{},builtin_name->{},match_labels->{},relabels->{},sinks->{}".format(
                vmrt_name, builtin_name, match_labels, relabels, sinks
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
    vm_conditional_sink_config = DataLinkResourceConfig.compose_conditional_sink_config(vmrt_name, conditions)
    conditional_sink = [
        {
            "kind": DataLinkKind.CONDITIONALSINK.value,
            "name": vmrt_name,
            "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        },
    ]
    vm_data_bus_config = DataLinkResourceConfig.compose_vm_data_bus_config(
        vmrt_name, vmrt_name, data_id_name, conditional_sink
    )
    config_list.extend([vm_conditional_sink_config, vm_data_bus_config])

    # 4. 调用计算平台接口，申请创建链路
    data = {"config": config_list}
    try:
        logger.info("create_fed_vm_data_link start to apply data link")
        api.bkdata.apply_data_link(data)
    except Exception as e:
        logger.error("create_fed_vm_data_link apply data link error->[%s]", str(e))
        return

    # 5. 创建监控平台自身的链路记录数据 AccessVMRecord -> DataLinkResource -> DataLinkResourceConfig 1->1->n
    records, vm_records = [], []

    # 如果 vm 集群ID不存在，则通过集群名称获取
    if not vm_cluster_id:
        vm_cluster_id = ClusterInfo.objects.get(cluster_name=vm_cluster_name).cluster_id

    for dl in data_links:
        DataLinkResource.objects.update_or_create(
            data_id_name=data_id_name,
            vm_table_id_name=dl["rt_name"],
            vm_binding_name=dl["vm_storage_binding_name"],
            defaults={"data_bus_name": vmrt_name, "conditional_sink_name": vmrt_name},
        )
        records.append(
            DataLinkResourceConfig(
                kind=DataLinkKind.RESULTTABLE.value,
                name=vmrt_name,
                namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                status=DataLinkResourceStatus.OK.value,
                content=dl["rt_config"],
            )
        )
        records.append(
            DataLinkResourceConfig(
                kind=DataLinkKind.VMSTORAGEBINDING.value,
                name=vmrt_name,
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
                bk_base_data_id=bkbase_data_id,  # 计算平台的数据ID
                bk_base_data_name=data_id_name,  # 计算平台的数据名称
                vm_result_table_id=f"{settings.DEFAULT_BKDATA_BIZ_ID}_{dl['rt_name']}",
            )
        )

    # 6. 状态设置为正常
    records.extend(
        [
            DataLinkResourceConfig(
                kind=DataLinkKind.DATABUS.value,
                name=vmrt_name,
                namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                status=DataLinkResourceStatus.OK.value,
                content=vm_data_bus_config,
            ),
            DataLinkResourceConfig(
                kind=DataLinkKind.CONDITIONALSINK.value,
                name=vmrt_name,
                namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                status=DataLinkResourceStatus.OK.value,
                content=vm_conditional_sink_config,
            ),
        ]
    )
    DataLinkResourceConfig.objects.bulk_create(records)
    # 7. 创建 vm 记录
    # NOTE：这里的接入VM记录，现统一将对应的计算平台数据ID和数据名称存储下来，方便后续使用
    from metadata.models import AccessVMRecord

    AccessVMRecord.objects.bulk_create(vm_records)

    # 8. 创建成功，打印日志并返回
    logger.info(
        "create_fed_vm_data_link for table_id->%s, data_name->[%s], vm_cluster_name->[%s],bk_base_data_name->[%s],"
        "bk_base_data_id->[%s] success",
        table_id,
        data_name,
        vm_cluster_name,
        data_id_name,
        bkbase_data_id,
    )
