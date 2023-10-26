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

import elasticsearch5
import requests

from alarm_backends.service.selfmonitor.healthz.checker.checker import CheckerRegister
from metadata.models.storage import ClusterInfo

# from .checker import CheckerRegister

logger = logging.getLogger(__name__)

register = CheckerRegister.elasticsearch

ES_CLUSTER_STATUS = {
    "red": 2,
    "yellow": 1,
    "green": 0,
}


def get_es_client(cluster_info):
    api_url = f"http://{cluster_info.domain_name}:{cluster_info.port}"
    try:
        requests.get(api_url, auth=(cluster_info.username, cluster_info.password), timeout=5)
    except Exception as err:
        return False, err
    else:
        connection_info = {
            "hosts": ["{}:{}".format(cluster_info.domain_name, cluster_info.port)],
            "verify_certs": cluster_info.is_ssl_verify,
            "use_ssl": cluster_info.is_ssl_verify,
        }
        if cluster_info.username is not None and cluster_info.password is not None:
            connection_info["http_auth"] = (cluster_info.username, cluster_info.password)
        es_client = elasticsearch5.Elasticsearch(**connection_info)
        return True, es_client


def cluster_status(result):
    """Elasticsearch集群状态"""
    health_list = []
    clusters_info = ClusterInfo.objects.filter(cluster_type=ClusterInfo.TYPE_ES, version__gte="7")
    for cluster in clusters_info:
        status, es_client = get_es_client(cluster)
        if status:
            health = es_client.cluster.health()
            health_list.append(
                {
                    "name": "{cluster_name}".format(cluster_name=health["cluster_name"]),
                    "status": ES_CLUSTER_STATUS[health["status"]],
                    "value": "",
                    "message": health["status"],
                }
            )
        else:
            domain_name = cluster.domain_name
            port = cluster.port
            health_list.append(
                {
                    "name": "{cluster_name}".format(cluster_name=cluster.cluster_name),
                    "status": 4,
                    "value": "",
                    "message": "connect hosts:{}:{} error, message is {}.".format(domain_name, port, es_client),
                }
            )
    return result.ok(value=health_list)


@register.status()
def elasticsearch_status(manager, result):
    """Elasticsearch状态"""
    return cluster_status(result)


@register.abnormal_index()
def get_abnormal_index(manager, result):
    """Elasticsearch集群中存在非正常index"""
    abnormal_index_list = []
    filter_dict = {"cluster_type": "elasticsearch"}
    clusters_info = ClusterInfo.objects.filter(**filter_dict)
    for cluster in clusters_info:
        status, es_client = get_es_client(cluster)
        if status:
            health = es_client.cluster.health()
            red_indices = [
                index["index"] for index in es_client.cat.indices(params={"health": "red", "format": "json"})
            ]
            yellow_indices = [
                index["index"] for index in es_client.cat.indices(params={"health": "yellow", "format": "json"})
            ]
            abnormal_index_list.append(
                {
                    "name": "{cluster_name}".format(cluster_name=health["cluster_name"]),
                    "status": 0 if len(red_indices + yellow_indices) == 0 else 2,
                    "message": "状态为red的index:{}；状态为yellow的index:{}".format(red_indices, yellow_indices),
                    "value": len(red_indices + yellow_indices),
                }
            )

    return result.ok(value=abnormal_index_list)


@register.active_shards()
def get_active_shards(manager, result):
    """Elasticsearch当前集群shard用量"""
    shard_list = []
    filter_dict = {"cluster_type": "elasticsearch"}
    clusters_info = ClusterInfo.objects.filter(**filter_dict)
    for cluster in clusters_info:
        status, es_client = get_es_client(cluster)
        if status:
            health = es_client.cluster.health()
            shard_list.append(
                {
                    "name": "{cluster_name}".format(cluster_name=health["cluster_name"]),
                    "status": 0,
                    "message": "ES{cluster_name}集群shard用量：{active_shards}".format(
                        cluster_name=health["cluster_name"], active_shards=health["active_shards"]
                    ),
                    "value": health["active_shards"],
                }
            )
    return result.ok(value=shard_list)


@register.active_shards.percent()
def get_shard_percent(manager, result):
    """Elasticsearch当前集群shard可用性"""
    shard_percent_list = []
    filter_dict = {"cluster_type": "elasticsearch"}
    clusters_info = ClusterInfo.objects.filter(**filter_dict)
    for cluster in clusters_info:
        status, es_client = get_es_client(cluster)
        if status:
            health = es_client.cluster.health()
            active_shards_percent_as_number = health["active_shards_percent_as_number"]
            msg = {
                "name": "{cluster_name}".format(cluster_name=health["cluster_name"]),
                "status": 0,
                "message": "ES{cluster_name}集群shard可用性：{active_shards_percent_as_number}".format(
                    cluster_name=health["cluster_name"],
                    active_shards_percent_as_number=health["active_shards_percent_as_number"],
                ),
                "value": active_shards_percent_as_number,
            }
            shard_percent_list.append(msg)
            if active_shards_percent_as_number != 100:
                return result.fail("{}集群shard可用性例: {}%".format(health['cluster_name'], active_shards_percent_as_number))

        return result.ok(value=shard_percent_list)
