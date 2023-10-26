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
from typing import List, Optional

from django.core.cache import cache

from metadata import config, models
from metadata.utils import consul_tools


def get_transfer_cluster(enable_cache: Optional[bool] = True) -> List[str]:
    """通过 consul 路径获取 transfer 集群

    TODO: 变动不频繁，是否增加缓存
    """
    cache_key = "cached_transfer_cluster"
    if enable_cache and cache_key in cache:
        return cache.get(cache_key)
    prefix_path = "%s/v1/" % config.CONSUL_PATH
    # 根据前缀，返回路径
    hash_consul = consul_tools.HashConsul()
    result_data = hash_consul.list(prefix_path)
    if not result_data[1]:
        return []

    # 解析并获取集群名称
    ret_data = []
    for data in result_data[1]:
        ret_data.append(data["Key"].split(prefix_path)[-1].split("/")[0])
    transfer_cluster = list(set(ret_data))
    # 缓存一个小时
    cache.set(cache_key, transfer_cluster, 60 * 60)
    return transfer_cluster


def check_transfer_cluster_exist(transfer_cluster_id: str) -> bool:
    """校验 transfer 集群是否存在"""
    if transfer_cluster_id in get_transfer_cluster():
        return True

    return False


def check_kafka_cluster_exist(kafka_cluster_id: int) -> bool:
    """校验 kafka 集群存在"""
    if models.ClusterInfo.objects.filter(
        cluster_type=models.ClusterInfo.TYPE_KAFKA, cluster_id=kafka_cluster_id
    ).exists():
        return True

    return False


def check_influxdb_cluster_exist(influxdb_cluster_id: int) -> bool:
    """校验 influxdb 集群存在"""
    if models.ClusterInfo.objects.filter(
        cluster_type=models.ClusterInfo.TYPE_INFLUXDB, cluster_id=influxdb_cluster_id
    ).exists():
        return True

    return False


def check_es_cluster_exist(es_cluster_id: int) -> bool:
    """校验 es 集群存在"""
    if models.ClusterInfo.objects.filter(cluster_type=models.ClusterInfo.TYPE_ES, cluster_id=es_cluster_id).exists():
        return True

    return False


def check_vm_cluster_exist(vm_cluster_id: int) -> bool:
    """校验 vm 集群存在"""
    if models.ClusterInfo.objects.filter(cluster_type=models.ClusterInfo.TYPE_VM, cluster_id=vm_cluster_id).exists():
        return True

    return False


def check_data_pipeline_used(data_pipeline_name: str) -> bool:
    """校验链路是否在使用"""
    if models.DataPipelineDataSource.objects.filter(data_pipeline_name=data_pipeline_name).exists():
        return True

    return False
