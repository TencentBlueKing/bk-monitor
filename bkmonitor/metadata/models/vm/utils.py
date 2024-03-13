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
import random
from typing import Dict, Optional

from django.conf import settings
from django.db.models import Q

from core.drf_resource import api
from metadata.models.vm.bk_data import BkDataAccessor, access_vm
from metadata.models.vm.config import BkDataStorageWithDataID
from metadata.models.vm.constants import BKDATA_NS_TIMESTAMP_DATA_ID_LIST, TimestampLen

logger = logging.getLogger("metadata")


def refine_bkdata_kafka_info():
    from metadata.models import ClusterInfo

    """获取接入计算平台时，使用的 kafka 信息"""
    kafka_clusters = ClusterInfo.objects.filter(cluster_type=ClusterInfo.TYPE_KAFKA).values("cluster_id", "domain_name")
    kafka_domain_cluster_id = {obj["domain_name"]: obj["cluster_id"] for obj in kafka_clusters}
    # 通过集群平台获取可用的 kafka host
    bkdata_kafka_data = api.bkdata.get_kafka_info()[0]
    bkdata_kafka_host_list = bkdata_kafka_data.get("ip_list", "").split(",")

    # NOTE: 获取 metadata 和接口返回的交集，然后任取其中一个; 如果不存在，则直接报错
    existed_host_list = list(set(bkdata_kafka_host_list) & set(kafka_domain_cluster_id.keys()))
    if not existed_host_list:
        logger.error("bkdata kafka host not registered ClusterInfo, bkdata resp: %s", json.dumps(bkdata_kafka_data))
        raise ValueError("bkdata kafka host not registered ClusterInfo")

    # 返回数据
    host = random.choice(existed_host_list)
    cluster_id = kafka_domain_cluster_id[host]
    logger.info("refine exist kafka, cluster_id: %s, host: %s", cluster_id, host)
    return {"cluster_id": cluster_id, "host": host}


def access_bkdata(bk_biz_id: int, table_id: str, data_id: int):
    """根据类型接入计算平台

    1. 仅针对接入 influxdb 类型

    当出现异常时，记录日志，然后通过告警进行通知
    """
    logger.info("bk_biz_id: %s, table_id: %s, data_id: %s start access vm", bk_biz_id, table_id, data_id)

    from metadata.models import AccessVMRecord, KafkaStorage, Space, SpaceVMInfo

    # NOTE: 0 业务没有空间信息，不需要查询或者创建空间及空间关联的 vm
    space_data = {}
    try:
        # NOTE: 这里 bk_biz_id 为整型
        space_data = Space.objects.get_space_info_by_biz_id(int(bk_biz_id))
    except Exception as e:
        logger.error("get space error by biz_id: %s, error: %s", bk_biz_id, e)

    # 如果不在空间接入 vm 的记录中，则创建记录
    if (
        space_data
        and not SpaceVMInfo.objects.filter(
            space_type=space_data["space_type"], space_id=space_data["space_id"]
        ).exists()
    ):
        SpaceVMInfo.objects.create_record(space_type=space_data["space_type"], space_id=space_data["space_id"])

    # 检查是否已经写入 kafka storage，如果已经存在，认为已经接入 vm，则直接返回
    if AccessVMRecord.objects.filter(result_table_id=table_id).exists():
        logger.info("table_id: %s has already been created", table_id)
        return

    # 获取数据源类型、集群等信息
    data_type_cluster = get_data_type_cluster(data_id)
    data_type = data_type_cluster.get("data_type")

    # 获取 vm 集群名称
    vm_cluster = get_vm_cluster_id_name(space_data.get("space_type", ""), space_data.get("space_id", ""))
    vm_cluster_name = vm_cluster.get("cluster_name")
    # 调用接口接入数据平台
    bcs_cluster_id = data_type_cluster.get("bcs_cluster_id")
    data_name_and_topic = get_bkbase_data_name_and_topic(table_id)
    timestamp_len = get_timestamp_len(data_id)
    try:
        vm_data = access_vm_by_kafka(table_id, data_name_and_topic["data_name"], vm_cluster_name, timestamp_len)
    except Exception as e:
        logger.error("access vm error, %s", e)
        return

    # 如果接入返回为空，则直接返回
    if vm_data.get("err_msg"):
        logger.error("access vm error")
        return

    # 创建 KafkaStorage 和 AccessVMRecord 记录
    try:
        if not vm_data.get("kafka_storage_exist"):
            KafkaStorage.create_table(
                table_id=table_id,
                is_sync_db=True,
                storage_cluster_id=vm_data["cluster_id"],
                topic=data_name_and_topic["topic_name"],
                use_default_format=False,
            )
    except Exception as e:
        logger.error("create KafkaStorage error for access vm: %s", e)

    try:
        AccessVMRecord.objects.create(
            data_type=data_type,
            result_table_id=table_id,
            bcs_cluster_id=bcs_cluster_id,
            storage_cluster_id=vm_data["cluster_id"],
            vm_cluster_id=vm_cluster["cluster_id"],
            bk_base_data_id=vm_data["bk_data_id"],
            vm_result_table_id=vm_data["clean_rt_id"],
        )
    except Exception as e:
        logger.error("create AccessVMRecord error for access vm: %s", e)

    logger.info("bk_biz_id: %s, table_id: %s, data_id: %s access vm successfully", bk_biz_id, table_id, data_id)

    # NOTE: 针对 bcs 添加合流流程
    # 1. 当前环境允许合流操作
    # 2. 合流的目的rt存在
    # 3. 当出现异常时，记录对应日志
    if (
        settings.BCS_DATA_CONVERGENCE_CONFIG.get("is_enabled")
        and settings.BCS_DATA_CONVERGENCE_CONFIG.get("k8s_metric_rt")
        and settings.BCS_DATA_CONVERGENCE_CONFIG.get("custom_metric_rt")
        and bcs_cluster_id
    ):
        try:
            data_name_and_dp_id = get_bcs_convergence_data_name_and_dp_id(table_id)
            clean_data = BkDataAccessor(
                bk_table_id=data_name_and_dp_id["data_name"],
                data_hub_name=data_name_and_dp_id["data_name"],
                timestamp_len=timestamp_len,
            ).clean
            clean_data["result_table_id"] = (
                settings.BCS_DATA_CONVERGENCE_CONFIG["k8s_metric_rt"]
                if data_type == AccessVMRecord.BCS_CLUSTER_K8S
                else settings.BCS_DATA_CONVERGENCE_CONFIG["custom_metric_rt"]
            )
            clean_data["processing_id"] = data_name_and_dp_id["dp_id"]
            # 创建清洗
            api.bkdata.databus_cleans(**clean_data)
            # 启动
            api.bkdata.start_databus_cleans(
                result_table_id=clean_data["result_table_id"],
                storages=["kafka"],
                processing_id=data_name_and_dp_id["dp_id"],
            )
        except Exception as e:
            logger.error(
                "bcs convergence create or start data clean error, table_id: %s, params: %s, error: %s",
                table_id,
                json.dumps(clean_data),
                e,
            )


def access_vm_by_kafka(table_id: str, raw_data_name: str, vm_cluster_name: str, timestamp_len: int) -> Dict:
    """通过 kafka 配置接入 vm"""
    from metadata.models import BkDataStorage, KafkaStorage, ResultTable

    kafka_storage_exist, storage_cluster_id = True, 0
    try:
        kafka_storage = KafkaStorage.objects.get(table_id=table_id)
        storage_cluster_id = kafka_storage.storage_cluster_id
    except Exception as e:
        logger.info("query kafka storage error %s", e)
        kafka_storage_exist = False

    # 如果不存在，则直接创建
    if not kafka_storage_exist:
        try:
            kafka_data = refine_bkdata_kafka_info()
        except Exception as e:
            logger.error("get bkdata kafka host error, table_id: %s, error: %s", table_id, e)
            return {"err_msg": f"request vm api error, {e}"}
        storage_cluster_id = kafka_data["cluster_id"]
        try:
            vm_data = access_vm(
                raw_data_name=raw_data_name,
                vm_cluster=vm_cluster_name,
                timestamp_len=timestamp_len,
            )
            vm_data["cluster_id"] = storage_cluster_id
            return vm_data
        except Exception as e:
            logger.error("request vm api error, table_id: %s, error: %s", table_id, e)
            return {"err_msg": f"request vm api error, {e}"}
    # 创建清洗和入库 vm
    bk_base_data = BkDataStorage.objects.filter(table_id=table_id).first()
    if not bk_base_data:
        bk_base_data = BkDataStorage.objects.create(table_id=table_id)
    if bk_base_data.raw_data_id == -1:
        result_table = ResultTable.objects.get(table_id=table_id)
        bk_base_data.create_databus_clean(result_table)
    # 重新读取一遍数据
    bk_base_data.refresh_from_db()
    raw_data_name = get_bkbase_data_name_and_topic(table_id)["data_name"]
    clean_data = BkDataAccessor(
        bk_table_id=raw_data_name, data_hub_name=raw_data_name, vm_cluster=vm_cluster_name, timestamp_len=timestamp_len
    ).clean
    clean_data.update(
        {
            "bk_biz_id": settings.DEFAULT_BKDATA_BIZ_ID,
            "raw_data_id": bk_base_data.raw_data_id,
            "clean_config_name": raw_data_name,
            "kafka_storage_exist": kafka_storage_exist,
        }
    )
    clean_data["json_config"] = json.dumps(clean_data["json_config"])
    try:
        bkbase_result_table_id = api.bkdata.databus_cleans(**clean_data)["result_table_id"]
        # 启动
        api.bkdata.start_databus_cleans(result_table_id=bkbase_result_table_id, storages=["kafka"])
    except Exception as e:
        logger.error(
            "create or start data clean error, table_id: %s, params: %s, error: %s", table_id, json.dumps(clean_data), e
        )
        return {"err_msg": f"request clean api error, {e}"}
    # 接入 vm
    try:
        storage_params = BkDataStorageWithDataID(bk_base_data.raw_data_id, raw_data_name, vm_cluster_name).value
        api.bkdata.create_data_storages(**storage_params)
        return {
            "clean_rt_id": f"{settings.DEFAULT_BKDATA_BIZ_ID}_{raw_data_name}",
            "bk_data_id": bk_base_data.raw_data_id,
            "cluster_id": storage_cluster_id,
            "kafka_storage_exist": kafka_storage_exist,
        }
    except Exception as e:
        logger.error("create vm storage error, %s", e)
        return {"err_msg": f"request vm storage api error, {e}"}


def get_data_type_cluster(data_id: int) -> Dict:
    from metadata.models import AccessVMRecord, BCSClusterInfo

    # NOTE: data id 不允许跨集群
    bcs_cluster = BCSClusterInfo.objects.filter(Q(K8sMetricDataID=data_id) | Q(CustomMetricDataID=data_id)).first()
    # 获取对应的类型
    data_type = AccessVMRecord.ACCESS_VM
    bcs_cluster_id = None
    if not bcs_cluster:
        data_type = AccessVMRecord.USER_CUSTOM
    elif bcs_cluster.K8sMetricDataID == data_id:
        data_type = AccessVMRecord.BCS_CLUSTER_K8S
        bcs_cluster_id = bcs_cluster.cluster_id
    else:
        data_type = AccessVMRecord.BCS_CLUSTER_CUSTOM
        bcs_cluster_id = bcs_cluster.cluster_id
    return {"data_type": data_type, "bcs_cluster_id": bcs_cluster_id}


def get_vm_cluster_id_name(space_type: str, space_id: str, vm_cluster_name: Optional[str] = "") -> Dict:
    """获取 vm 集群 ID 和名称

    1. 如果 vm 集群名称存在，则需要查询到对应的ID，如果查询不到，则需要抛出异常
    2. 如果 vm 集群名称不存在，则需要查询空间是否已经接入过，如果已经接入过，则可以直接获取
    3. 如果没有接入过，则需要使用默认值
    """
    from metadata.models import ClusterInfo, SpaceVMInfo

    # vm 集群名称存在
    if vm_cluster_name:
        clusters = ClusterInfo.objects.filter(cluster_type=ClusterInfo.TYPE_VM, cluster_name=vm_cluster_name)
        if not clusters.exists():
            logger.error(
                "query vm cluster error, vm_cluster_name: %s not found, please register to clusterinfo", vm_cluster_name
            )
            raise ValueError(f"vm_cluster_name: {vm_cluster_name} not found")
        cluster = clusters.first()
        return {"cluster_id": cluster.cluster_id, "cluster_name": cluster.cluster_name}
    elif space_type and space_id:
        objs = SpaceVMInfo.objects.filter(space_type=space_type, space_id=space_id)
        if not objs.exists():
            logger.warning("space_type: %s, space_id: %s not access vm", space_type, space_id)
        else:
            try:
                cluster = ClusterInfo.objects.get(cluster_id=objs.first().vm_cluster_id)
            except Exception:
                logger.error(
                    "space_type: %s, space_id: %s, cluster_id: %s not found",
                    space_type,
                    space_id,
                    objs.first().vm_cluster_id,
                )
                raise ValueError(f"space_type: {space_type}, space_id: {space_id} not found vm cluster")
            return {"cluster_id": cluster.cluster_id, "cluster_name": cluster.cluster_name}

    # 获取默认 VM 集群
    clusters = ClusterInfo.objects.filter(cluster_type=ClusterInfo.TYPE_VM, is_default_cluster=True)
    if not clusters.exists():
        logger.error("not found vm default cluster")
        raise ValueError("not found vm default cluster")
    cluster = clusters.first()
    return {"cluster_id": cluster.cluster_id, "cluster_name": cluster.cluster_name}


def get_bkbase_data_name_and_topic(table_id: str) -> Dict:
    """获取 bkbase 的结果表名称"""
    # 如果以 '__default__'结尾，则取前半部分
    if table_id.endswith("__default__"):
        table_id = table_id.split(".__default__")[0]
    name = f"{table_id.replace('-', '_').replace('.', '_').replace('__', '_')[-40:]}"
    # NOTE: 清洗结果表不能出现双下划线
    vm_name = f"vm_{name}".replace('__', '_')

    return {"data_name": vm_name, "topic_name": f"{vm_name}{settings.DEFAULT_BKDATA_BIZ_ID}"}


def get_bcs_convergence_data_name_and_dp_id(table_id: str) -> Dict:
    """获取 bcs 合流对应的结果表及数据处理 ID"""
    if table_id.endswith("__default__"):
        table_id = table_id.split(".__default__")[0]
    name = f"{table_id.replace('-', '_').replace('.', '_').replace('__', '_')[-40:]}"
    # NOTE: 清洗结果表不能出现双下划线
    return {"data_name": f"dp_{name}", "dp_id": f"{settings.DEFAULT_BKDATA_BIZ_ID}_{name}_dp_metric_all"}


def get_timestamp_len(data_id: Optional[int] = None, etl_config: Optional[str] = None) -> int:
    """通过 data id 或者 etl config 获取接入 vm 是清洗时间的长度

    1. 如果 data id 在指定的白名单中，则为 纳米
    2. 其它，则为 毫秒
    """
    if data_id and data_id in BKDATA_NS_TIMESTAMP_DATA_ID_LIST:
        return TimestampLen.NANOSECOND_LEN.value

    return TimestampLen.MILLISECOND_LEN.value
